import os
import time
import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI

# Guarded LangChain imports to avoid startup crash if versions are incompatible
try:
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # type: ignore
    from langchain_core.runnables.history import RunnableWithMessageHistory  # type: ignore
    from langchain_community.chat_message_histories import ChatMessageHistory  # type: ignore
    from langchain.callbacks import AsyncIteratorCallbackHandler  # type: ignore
    LANGCHAIN_AVAILABLE = True
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore
    MessagesPlaceholder = None  # type: ignore
    RunnableWithMessageHistory = None  # type: ignore
    ChatMessageHistory = None  # type: ignore
    AsyncIteratorCallbackHandler = None  # type: ignore
    LANGCHAIN_AVAILABLE = False

load_dotenv()


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="User's plain-language business context and request")
    company_name: Optional[str] = Field(None, description="Optional company or product name to include")
    jurisdiction: Optional[str] = Field(None, description="Optional governing law or location context, e.g., 'New York, USA'")
    tone: Optional[str] = Field(
        None,
        description="Optional tone/style guidance (e.g., 'formal, clear, conservative risk posture')",
    )


class StartSessionRequest(BaseModel):
    system_prompt: Optional[str] = Field(None, description="Override system behavior")
    metadata: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: ChatMessage


class SetDocumentRequest(BaseModel):
    html: str = Field(..., description="The current base HTML document to modify")
    title: Optional[str] = None


app = FastAPI(title="AI Contract Generator API", version="0.1.0")

# CORS: configure via env CORS_ALLOW_ORIGINS as CSV, default "*"
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SYSTEM_PROMPT = (
    "You are a senior technology and privacy attorney. Generate long-form, production-ready "
    "Terms of Service in GitHub-Flavored Markdown (GFM). Use clear section headings and numbering, "
    "tables and lists where appropriate, and consistent defined terms. Include comprehensive "
    "clauses suitable for a cloud cybersecurity SaaS, including but not limited to: Definitions; "
    "Eligibility; Accounts; Acceptable Use; Access and Security; Intellectual Property; Customer "
    "Data and Privacy; Subprocessors; Confidentiality; Warranties and Disclaimers; Indemnification; "
    "Limitation of Liability; Term and Termination; Suspension; Fees and Payment (if relevant); Beta "
    "Features; Export Controls; Government Use; Governing Law; Venue; Dispute Resolution (with optional "
    "arbitration); Notices; Changes to the Service; Changes to Terms; Force Majeure; Assignment; Entire "
    "Agreement; Severability; and Contact. Return ONLY Markdown. Do not use code fences."
)

# State for conversational sessions (in-memory). Replace with Redis/DB in production.
SESSION_HISTORY: Dict[str, "ChatMessageHistory"] = {}
SESSION_META: Dict[str, Dict[str, Any]] = {}


def _build_user_prompt(data: GenerateRequest) -> str:
    parts = [
        "Context provided by the user describing business and needs:",
        data.prompt.strip(),
        "\nOutput requirements:",
        "- Return ONLY GitHub-Flavored Markdown (no code fences, no backticks).",
        "- Use #, ##, ### headings with consistent numbering; include a table of contents.",
        "- Ensure consistent defined terms and cross-references.",
        "- Be Verbose and Detailed",
        "- Target 10+ printed pages equivalent when rendered (substantial detail and clauses).",
        "- Use numbered sections and subsections (e.g., 1., 1.1., 1.1.1).",
        "- Use a table of contents to navigate the document.",
        "- Use a footer to include a copyright notice and contact information.",
        "- Use a header to include the document title and version number.",
        "- Include placeholders where user specifics are unknown (e.g., Company Name, Address).",
    ]
    if data.company_name:
        parts.append(f"- Company Name: {data.company_name}")
    if data.jurisdiction:
        parts.append(f"- Governing Law / Location Context: {data.jurisdiction}")
    if data.tone:
        parts.append(f"- Tone: {data.tone}")
    return "\n".join(parts)


def _create_stream_with_retries(client: "OpenAI", *, messages, temperature: float, max_tokens: int):
    max_attempts = 3
    base_delay = 0.5
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if attempt == max_attempts:
                break
            time.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore[misc]


async def _create_stream_with_retries_async(
    client: "AsyncOpenAI", *, messages, temperature: float, max_tokens: int
):
    max_attempts = 3
    base_delay = 0.5
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if attempt == max_attempts:
                break
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore[misc]


@app.post("/api/generate")
async def generate_contract(data: GenerateRequest):
    if OpenAI is None:
        return JSONResponse(
            status_code=500,
            content={
                "error": "OpenAI SDK not installed. Ensure backend dependencies are installed.",
            },
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    # Prefer async client to avoid blocking event loop during network I/O
    async_client = AsyncOpenAI(api_key=api_key) if AsyncOpenAI is not None else None
    client = OpenAI(api_key=api_key) if async_client is None else None

    system_message = {"role": "system", "content": SYSTEM_PROMPT}
    user_message = {"role": "user", "content": _build_user_prompt(data)}

    # Limit output tokens conservatively to reduce context-length errors
    max_tokens_env = os.getenv("OPENAI_MAX_TOKENS")
    try:
        max_tokens = int(max_tokens_env) if max_tokens_env else 16000
    except ValueError:
        max_tokens = 16000

    async def _event_stream() -> AsyncGenerator[bytes, None]:
        try:
            # Create downstream stream after sending prelude so clients see immediate output
            if async_client is not None:
                stream = await _create_stream_with_retries_async(
                    async_client,
                    messages=[system_message, user_message],
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
                async for chunk in stream:  # type: ignore[arg-type]
                    try:
                        delta = chunk.choices[0].delta.content or ""
                    except Exception:
                        delta = ""
                    if delta:
                        yield delta.encode("utf-8", errors="ignore")
                        await asyncio.sleep(0)
            else:
                stream = _create_stream_with_retries(
                    client,  # type: ignore[arg-type]
                    messages=[system_message, user_message],
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
                for chunk in stream:  # type: ignore[assignment]
                    try:
                        delta = chunk.choices[0].delta.content or ""
                    except Exception:
                        delta = ""
                    if delta:
                        yield delta.encode("utf-8", errors="ignore")
        except Exception as exc:
            # Emit minimal error in-stream; full HTML page already started
            msg = f"\n\nStreaming error: {str(exc)}\n"
            yield msg.encode("utf-8", errors="ignore")

    return StreamingResponse(
        _event_stream(),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stream-test")
async def stream_test():
    async def _gen() -> AsyncGenerator[bytes, None]:
        yield b"start\n"
        for i in range(1, 6):
            yield f"tick {i}\n".encode("utf-8")
            await asyncio.sleep(0.3)
        yield b"end\n"

    return StreamingResponse(
        _gen(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------- LangChain conversational endpoints ----------

def _get_or_create_history(session_id: str) -> "ChatMessageHistory":
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    history = SESSION_HISTORY.get(session_id)
    if history is None:
        history = ChatMessageHistory()
        SESSION_HISTORY[session_id] = history
    return history


@app.post("/api/session/start")
async def start_session(payload: StartSessionRequest):
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    session_id = str(uuid.uuid4())
    SESSION_META[session_id] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system_prompt": payload.system_prompt or SYSTEM_PROMPT,
        "metadata": payload.metadata or {},
    }
    SESSION_HISTORY[session_id] = ChatMessageHistory()
    return {"session_id": session_id}


@app.get("/api/session/{session_id}/history")
async def get_history(session_id: str):
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    history = SESSION_HISTORY.get(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="session not found")
    messages = [
        {"role": m.type, "content": m.content} for m in history.messages  # type: ignore[attr-defined]
    ]
    return {"session_id": session_id, "messages": messages, "meta": SESSION_META.get(session_id, {})}


@app.post("/api/session/{session_id}/clear")
async def clear_history(session_id: str):
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    SESSION_HISTORY[session_id] = ChatMessageHistory()
    return {"ok": True}


@app.get("/api/session/list")
async def list_sessions():
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    return {
        "sessions": [
            {"session_id": sid, **meta} for sid, meta in SESSION_META.items()
        ]
    }


@app.post("/api/session/{session_id}/document")
async def set_document(session_id: str, payload: SetDocumentRequest):
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    meta = SESSION_META.get(session_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="session not found")
    meta["document_html"] = payload.html
    if payload.title:
        meta["document_title"] = payload.title
    return {"ok": True}


@app.post("/api/chat")
async def chat_stream(req: ChatRequest):
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available on server")
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    session_meta = SESSION_META.get(req.session_id)
    if session_meta is None:
        raise HTTPException(status_code=404, detail="session not found")

    # Build LCEL chain with memory placeholder
    base_doc = session_meta.get("document_html")
    system_text = session_meta.get("system_prompt") or SYSTEM_PROMPT
    if base_doc:
        system_text = (
            system_text
            + "\n\nYou are continuing an editing session. The current base Markdown document is provided below.\n"
            + "Apply user instructions as surgical edits to this base, preserving headings, numbering, anchors, and tables.\n"
            + "Return ONLY updated Markdown (no backticks, no code fences).\n\n"
            + "<BASE_DOCUMENT>\n" + base_doc + "\n</BASE_DOCUMENT>\n"
        )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        temperature=0.2,
        streaming=True,
    )

    # Streaming callback and async iterator
    callback = AsyncIteratorCallbackHandler()

    # Do not bind callbacks here to avoid passing callbacks twice via config
    chain = prompt | llm

    # Wrap with history storage
    def _get_history(_: str) -> ChatMessageHistory:
        return _get_or_create_history(req.session_id)

    chain_with_history = RunnableWithMessageHistory(
        chain,
        _get_history,
        input_messages_key="input",
        history_messages_key="history",
        output_messages_key="output",
    )

    # Kick off generation concurrently so we can stream tokens
    async def _consumer_task():
        try:
            await chain_with_history.ainvoke(
                {"input": req.message.content},
                config={
                    "configurable": {"session_id": req.session_id},
                    "callbacks": [callback],
                },
            )
        except Exception as exc:  # pragma: no cover
            print(exc)
            await callback.on_llm_error(exc, run_id=None)
        finally:
            # Mark the async iterator as complete if not already signaled by the LLM end event
            try:
                callback.done.set()  # type: ignore[attr-defined]
            except Exception:
                pass

    asyncio.create_task(_consumer_task())

    async def _gen() -> AsyncGenerator[bytes, None]:
        yield b"{"  # start of JSON stream wrapper
        first = True
        try:
            async for token in callback.aiter():
                part = token.get("content") if isinstance(token, dict) else str(token)
                if part:
                    if first:
                        yield b"\"data\":\""
                        first = False
                    yield part.replace("\\", "\\\\").replace("\"", "\\\"").encode("utf-8")
        except Exception as exc:
            print(exc)
        finally:
            if first:
                yield b"\"data\":\"\""
            yield b"\"}"

    return StreamingResponse(
        _gen(),
        media_type="application/json; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


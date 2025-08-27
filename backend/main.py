import os
import time
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - allows importing file without deps installed
    OpenAI = None  # type: ignore


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="User's plain-language business context and request")
    company_name: Optional[str] = Field(None, description="Optional company or product name to include")
    jurisdiction: Optional[str] = Field(None, description="Optional governing law or location context, e.g., 'New York, USA'")
    tone: Optional[str] = Field(
        None,
        description="Optional tone/style guidance (e.g., 'formal, clear, conservative risk posture')",
    )


app = FastAPI(title="AI Contract Generator API", version="0.1.0")

# Liberal CORS for MVP; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SYSTEM_PROMPT = (
    "You are a senior technology and privacy attorney. Generate long-form, production-ready "
    "Terms of Service in well-structured, semantic HTML. Use consistent defined terms and "
    "section numbering. Include comprehensive clauses suitable for a cloud cybersecurity SaaS, "
    "including but not limited to: Definitions; Eligibility; Accounts; Acceptable Use; Access and "
    "Security; Intellectual Property; Customer Data and Privacy; Subprocessors; Confidentiality; "
    "Warranties and Disclaimers; Indemnification; Limitation of Liability; Term and Termination; "
    "Suspension; Fees and Payment (if relevant); Beta Features; Export Controls; Government Use; "
    "Governing Law; Venue; Dispute Resolution (with optional arbitration); Notices; Changes to the "
    "Service; Changes to Terms; Force Majeure; Assignment; Entire Agreement; Severability; and "
    "Contact."
)


def _build_user_prompt(data: GenerateRequest) -> str:
    parts = [
        "Context provided by the user describing business and needs:",
        data.prompt.strip(),
        "\nOutput requirements:",
        "- Return ONLY HTML within a single <article> root; do not include backticks or explanations.",
        "- Use semantic HTML (h1-h6, section, article, aside, ol/ul, dl, details, table when appropriate).",
        "- Include a table of contents with anchor links.",
        "- Ensure consistent defined terms and cross-references.",
        "- Target 10+ printed pages equivalent when rendered (substantial detail and clauses).",
        "- Use numbered sections and subsections (e.g., 1., 1.1., 1.1.1).",
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
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
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

    client = OpenAI(api_key=api_key)

    system_message = {"role": "system", "content": SYSTEM_PROMPT}
    user_message = {"role": "user", "content": _build_user_prompt(data)}

    # Limit output tokens conservatively to reduce context-length errors
    max_tokens_env = os.getenv("OPENAI_MAX_TOKENS")
    try:
        max_tokens = int(max_tokens_env) if max_tokens_env else 4000
    except ValueError:
        max_tokens = 4000

    try:
        stream = _create_stream_with_retries(
            client,
            messages=[system_message, user_message],
            temperature=0.2,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # pragma: no cover
        message = str(exc)
        status = 502
        if "maximum context length" in message or "max_tokens" in message:
            status = 413  # payload too large / context too long
        raise HTTPException(status_code=status, detail=f"Downstream model error: {message}")

    async def _event_stream() -> AsyncGenerator[bytes, None]:
        # Yield minimal HTML prelude so browsers render progressively if users open endpoint directly
        yield b"<article class=\"tos-document\">"
        try:
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content or ""
                except Exception:
                    delta = ""
                if delta:
                    yield delta.encode("utf-8", errors="ignore")
        finally:
            yield b"</article>"

    return StreamingResponse(_event_stream(), media_type="text/html; charset=utf-8")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


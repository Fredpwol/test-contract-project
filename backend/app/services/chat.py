import os
from typing import AsyncGenerator, Optional

try:
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder  # type: ignore
    from langchain_core.runnables.history import RunnableWithMessageHistory  # type: ignore
    from langchain_community.chat_message_histories import ChatMessageHistory  # type: ignore
    from langchain.callbacks import AsyncIteratorCallbackHandler  # type: ignore
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore
    MessagesPlaceholder = None  # type: ignore
    RunnableWithMessageHistory = None  # type: ignore
    ChatMessageHistory = None  # type: ignore
    AsyncIteratorCallbackHandler = None  # type: ignore

from ..config import load_settings, DEFAULT_SYSTEM_PROMPT


def ensure_langchain():
    if ChatOpenAI is None:
        raise RuntimeError("LangChain not available on server")


async def stream_chat(*, session_id: str, input_text: str, base_doc: Optional[str] = None, system_prompt: Optional[str] = None, get_history_cb=None) -> AsyncGenerator[str, None]:
    ensure_langchain()
    settings = load_settings()

    prompts = settings.prompts or {}
    system_text = system_prompt or prompts.get("system", {}).get("contract_generation") or DEFAULT_SYSTEM_PROMPT
    if base_doc:
        editing_block = prompts.get("system", {}).get("editing_context") or (
            "You are continuing an editing session. The current base Markdown document is provided below.\n"
            "Apply user instructions as surgical edits to this base, preserving headings, numbering, anchors, and tables.\n"
            "Return ONLY updated Markdown (no backticks, no code fences).\n"
        )
        system_text = (
            system_text + "\n\n" + editing_block + "\n\n<BASE_DOCUMENT>\n" + base_doc + "\n</BASE_DOCUMENT>\n"
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.2,
        streaming=True,
    )

    callback = AsyncIteratorCallbackHandler()
    chain = prompt | llm

    chain_with_history = RunnableWithMessageHistory(
        chain,
        get_history_cb,
        input_messages_key="input",
        history_messages_key="history",
        output_messages_key="output",
    )

    async def _consumer():
        try:
            await chain_with_history.ainvoke(
                {"input": input_text},
                config={
                    "configurable": {"session_id": session_id},
                    "callbacks": [callback],
                },
            )
        except Exception as exc:  # pragma: no cover
            await callback.on_llm_error(exc, run_id=None)
        finally:
            try:
                callback.done.set()  # type: ignore[attr-defined]
            except Exception:
                pass

    import asyncio

    asyncio.create_task(_consumer())

    async for token in callback.aiter():
        yield token.get("content") if isinstance(token, dict) else str(token)



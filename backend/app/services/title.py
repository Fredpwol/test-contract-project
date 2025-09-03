from typing import Optional

from openai import AsyncOpenAI

from ..config import load_settings
from ..utils import retry_async


async def generate_session_title(*, user_input: str, base_doc_markdown: Optional[str] = None) -> str:
    settings = load_settings()
    if not settings.openai_api_key:
        # Fallback: simple heuristic from input
        return _fallback_title(user_input)

    async_client = AsyncOpenAI(api_key=settings.openai_api_key)

    prompts = settings.prompts or {}
    instruction = prompts.get("title", {}).get("instruction") or (
        "You are naming a legal document editing session. Generate a concise, professional 3-7 word title based on the user's request and, if provided, the current Markdown document. Prefer specific nouns (e.g., company name, jurisdiction) and keep it neutral. Return ONLY the title text without quotes."
    )
    content = f"User request:\n{user_input.strip()}\n"
    if base_doc_markdown:
        content += "\nDocument excerpt (may be truncated):\n" + base_doc_markdown[:4000]

    async def _create():
        return await async_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            max_tokens=32,
        )

    try:
        resp = await retry_async(_create)
        text = (resp.choices[0].message.content or "").strip()
        return text or _fallback_title(user_input)
    except Exception:
        return _fallback_title(user_input)


def _fallback_title(user_input: str) -> str:
    s = user_input.strip()
    if len(s) > 60:
        s = s[:57] + "…"
    # Capitalize first letter, naive fallback
    return s[:1].upper() + s[1:]



import os
import inspect
from typing import AsyncGenerator, Optional

from openai import OpenAI, AsyncOpenAI

from ..config import load_settings, DEFAULT_SYSTEM_PROMPT
from ..utils import retry_async, retry_sync, async_sleep_yield


def build_user_prompt(*, prompt: str, company_name: Optional[str], jurisdiction: Optional[str], tone: Optional[str]) -> str:
    parts = [
        "Context provided by the user describing business and needs:",
        prompt.strip(),
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
    if company_name:
        parts.append(f"- Company Name: {company_name}")
    if jurisdiction:
        parts.append(f"- Governing Law / Location Context: {jurisdiction}")
    if tone:
        parts.append(f"- Tone: {tone}")
    return "\n".join(parts)


async def stream_contract_md(*, data) -> AsyncGenerator[str, None]:
    settings = load_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    async_client = AsyncOpenAI(api_key=api_key)

    prompts = settings.prompts or {}
    sys_prompt = (
        prompts.get("system", {}).get("contract_generation")
        or DEFAULT_SYSTEM_PROMPT
    )
    generation_template = prompts.get("user", {}).get("generation_requirements")

    system_message = {"role": "system", "content": sys_prompt}
    user_message = {
        "role": "user",
        "content": (
            generation_template.format(context=build_user_prompt(
                prompt=data.prompt,
                company_name=data.company_name,
                jurisdiction=data.jurisdiction,
                tone=data.tone,
            )) if generation_template else build_user_prompt(
                prompt=data.prompt,
                company_name=data.company_name,
                jurisdiction=data.jurisdiction,
                tone=data.tone,
            )
        ),
    }

    async def _create_stream():
        result = async_client.chat.completions.create(
            model=settings.openai_model,
            messages=[system_message, user_message],
            temperature=0.2,
            max_tokens=settings.openai_max_tokens,
            stream=True,
        )
        if inspect.isawaitable(result):
            return await result
        return result

    stream = await retry_async(_create_stream)

    async for chunk in stream:  # type: ignore
        try:
            delta = chunk.choices[0].delta.content or ""
        except Exception:
            delta = ""
        if delta:
            yield delta
            await async_sleep_yield()



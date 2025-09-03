import os
from dataclasses import dataclass
from typing import List, Optional
import pathlib
import yaml


@dataclass(frozen=True)
class Settings:
    openai_api_key: Optional[str]
    openai_model: str
    openai_max_tokens: int
    cors_allow_origins: List[str]
    prompts: dict


def load_settings() -> Settings:
    cors_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors = [o.strip() for o in cors_env.split(",") if o.strip()] or ["*"]
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    max_tokens_env = os.getenv("OPENAI_MAX_TOKENS")
    try:
        max_tokens = int(max_tokens_env) if max_tokens_env else 16000
    except ValueError:
        max_tokens = 16000
    prompts = _load_prompts()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=model,
        openai_max_tokens=max_tokens,
        cors_allow_origins=cors,
        prompts=prompts,
    )


def _load_prompts() -> dict:
    # Look for prompts.yml in backend root (parent of app/)
    backend_root = pathlib.Path(__file__).resolve().parents[1]
    prompts_path = backend_root / "prompts.yml"
    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        return {}

# Default system prompt preserved for fallback
DEFAULT_SYSTEM_PROMPT = "You are a senior technology and privacy attorney. Return ONLY Markdown."



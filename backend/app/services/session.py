import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from copy import deepcopy

try:
    from langchain_community.chat_message_histories import ChatMessageHistory  # type: ignore
except Exception:  # pragma: no cover
    ChatMessageHistory = None  # type: ignore


SESSION_HISTORY: Dict[str, "ChatMessageHistory"] = {}
SESSION_META: Dict[str, Dict[str, Any]] = {}


def ensure_langchain_available():
    if ChatMessageHistory is None:
        raise RuntimeError("LangChain not available on server")


from ..config import DEFAULT_SYSTEM_PROMPT


def start_session(*, system_prompt: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    ensure_langchain_available()
    session_id = str(uuid.uuid4())
    SESSION_META[session_id] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system_prompt": system_prompt or DEFAULT_SYSTEM_PROMPT,
        "metadata": metadata or {},
    }
    SESSION_HISTORY[session_id] = ChatMessageHistory()
    return session_id


def get_history(session_id: str):
    ensure_langchain_available()
    history = SESSION_HISTORY.get(session_id)
    if history is None:
        raise KeyError("session not found")
    return history


def clear_history(session_id: str):
    ensure_langchain_available()
    SESSION_HISTORY[session_id] = ChatMessageHistory()


def list_sessions():
    ensure_langchain_available()
    # Return a deep-copied view to avoid accidental client-side mutation affecting server state
    items = []
    for sid, meta in SESSION_META.items():
        item = {"session_id": sid}
        item.update(deepcopy(meta))
        items.append(item)
    return items


def set_document(session_id: str, html: str, title: Optional[str] = None):
    ensure_langchain_available()
    meta = SESSION_META.get(session_id)
    if meta is None:
        raise KeyError("session not found")
    meta["document_html"] = html
    if title:
        meta["document_title"] = title



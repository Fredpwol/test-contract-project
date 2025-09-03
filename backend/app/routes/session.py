from fastapi import APIRouter, HTTPException

from ..schemas import StartSessionRequest, SetDocumentRequest
from ..services.session import (
    start_session as svc_start_session,
    list_sessions as svc_list_sessions,
    clear_history as svc_clear_history,
    get_history as svc_get_history,
    set_document as svc_set_document,
)
from ..services.session import SESSION_META

router = APIRouter()


@router.post("/session/start")
async def start_session(payload: StartSessionRequest):
    try:
        sid = svc_start_session(system_prompt=payload.system_prompt, metadata=payload.metadata)
        return {"session_id": sid}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/session/{session_id}/history")
async def get_history(session_id: str):
    try:
        history = svc_get_history(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    messages = [
        {"role": m.type, "content": m.content} for m in history.messages  # type: ignore[attr-defined]
    ]
    from ..services.session import SESSION_META

    return {"session_id": session_id, "messages": messages, "meta": SESSION_META.get(session_id, {})}


@router.post("/session/{session_id}/clear")
async def clear_history(session_id: str):
    try:
        svc_clear_history(session_id)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/session/list")
async def list_sessions():
    try:
        return {"sessions": svc_list_sessions()}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/session/{session_id}/document")
async def set_document(session_id: str, payload: SetDocumentRequest):
    try:
        svc_set_document(session_id, html=payload.html, title=payload.title)
        return {"ok": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/session/{session_id}/title")
async def set_title(session_id: str, payload: dict):
    meta = SESSION_META.get(session_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="session not found")
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    meta["document_title"] = title
    return {"ok": True, "title": title}



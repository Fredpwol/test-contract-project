from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest
from ..services.session import get_history as svc_get_history, SESSION_META
from ..services.chat import stream_chat
from ..services.title import generate_session_title
from ..utils import json_stream_wrapper

router = APIRouter()


@router.post("/chat")
async def chat_stream(req: ChatRequest):
    try:
        meta = SESSION_META.get(req.session_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="session not found")

        base_doc = meta.get("document_html")

        def _get_history(_: str):
            return svc_get_history(req.session_id)

        # Generate a session title on first prompt if missing
        if not meta.get("document_title") and req.message and req.message.content:
            try:
                title = await generate_session_title(user_input=req.message.content, base_doc_markdown=base_doc)
                if title:
                    meta["document_title"] = title
            except Exception:
                pass

        async def generator() -> AsyncGenerator[str, None]:
            async for token in stream_chat(
                session_id=req.session_id,
                input_text=req.message.content,
                base_doc=base_doc,
                system_prompt=meta.get("system_prompt"),
                get_history_cb=_get_history,
            ):
                yield token

        return StreamingResponse(
            json_stream_wrapper(generator()),
            media_type="application/json; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))



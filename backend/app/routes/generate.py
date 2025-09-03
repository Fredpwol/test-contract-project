from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from ..schemas import GenerateRequest
from ..services.generation import stream_contract_md

router = APIRouter()


@router.post("/generate")
async def generate_contract(data: GenerateRequest):
    try:
        async def _event_stream() -> AsyncGenerator[bytes, None]:
            try:
                async for delta in stream_contract_md(data=data):
                    if delta:
                        yield delta.encode("utf-8", errors="ignore")
            except RuntimeError as exc:
                # configuration errors
                raise HTTPException(status_code=500, detail=str(exc))

        return StreamingResponse(
            _event_stream(),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        return JSONResponse(status_code=500, content={"error": str(exc)})



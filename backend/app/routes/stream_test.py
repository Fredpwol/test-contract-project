import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/stream-test")
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



import asyncio
import time
from typing import Any, AsyncGenerator, Optional


async def async_sleep_yield():
    # Help cooperative multitasking in streaming loops
    await asyncio.sleep(0)


def retry_sync(fn, *, attempts: int = 3, base_delay: float = 0.5):
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if attempt == attempts:
                break
            time.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore[misc]


async def retry_async(fn, *, attempts: int = 3, base_delay: float = 0.5):
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if attempt == attempts:
                break
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore[misc]


def json_stream_wrapper(generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
    async def _wrapped() -> AsyncGenerator[bytes, None]:
        yield b"{"
        first = True
        try:
            async for part in generator:
                if part:
                    if first:
                        yield b"\"data\":\""
                        first = False
                    yield (
                        part.replace("\\", "\\\\").replace("\"", "\\\"")
                    ).encode("utf-8")
        finally:
            if first:
                yield b"\"data\":\"\""
            yield b"\"}"

    return _wrapped()



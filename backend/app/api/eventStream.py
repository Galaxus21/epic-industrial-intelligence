"""Server-Sent Events response shared by every streaming endpoint.

"no-transform" stops a proxy from compressing the stream. The Next.js server in front of the API
gzips responses by default, and a gzipped stream arrives in one piece when it ends, so the
browser would see no progress until the last event.

A heartbeat comment goes out whenever the stream has been silent for a while. The Next.js rewrite
proxy aborts an upstream request after 30 s without data (`experimental.proxyTimeout`, default
30000 ms in next 14.2.5, router-utils/proxy-request.js) and leaves the browser's stream hanging
open; a local model loading or answering easily takes longer than that between two events. SSE
clients ignore lines that start with ":" (frontend/src/lib/api.ts skips every non-"data:" line).
"""
import asyncio
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

sseHeaders = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
# A third of the proxy's 30 s idle cutoff, so one late heartbeat still leaves a margin.
HEARTBEAT_INTERVAL_SECONDS = 10.0
HEARTBEAT_COMMENT = ": keep-alive\n\n"


def eventStreamResponse(
    events: AsyncIterator[str],
    heartbeatSeconds: float = HEARTBEAT_INTERVAL_SECONDS,
) -> StreamingResponse:
    return StreamingResponse(
        withHeartbeat(events, heartbeatSeconds), media_type="text/event-stream", headers=sseHeaders,
    )


async def withHeartbeat(
    events: AsyncIterator[str],
    intervalSeconds: float = HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncIterator[str]:
    """Yield every event unchanged, plus a heartbeat comment after each silent interval."""
    iterator = events.__aiter__()
    pending = asyncio.ensure_future(iterator.__anext__())
    try:
        while True:
            finished, _ = await asyncio.wait({pending}, timeout=intervalSeconds)
            if not finished:
                yield HEARTBEAT_COMMENT
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            yield event
            pending = asyncio.ensure_future(iterator.__anext__())
    finally:
        await _stopSource(pending, iterator)


async def _stopSource(pending: asyncio.Future, iterator: AsyncIterator[str]) -> None:
    # A client that disconnects closes this generator; the source must stop too, or its model call keeps running.
    if not pending.done():
        pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    closeSource = getattr(iterator, "aclose", None)
    if closeSource is not None:
        await closeSource()

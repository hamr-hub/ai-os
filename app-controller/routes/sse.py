from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import asyncio

from core.deps import sse_push_manager as _sse_push_manager

sse_router = APIRouter(prefix="/manage/sse")


@sse_router.get("/stream")
async def sse_stream(category: str = "all"):
    queue = _sse_push_manager.subscribe(category)
    try:
        async def event_generator():
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    if message == "event: close\ndata: {}\n\n":
                        break
                    yield message
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception:
        _sse_push_manager.unsubscribe(category, queue)


@sse_router.get("/categories")
async def get_categories():
    return {"categories": _sse_push_manager.get_categories()}


@sse_router.get("/connections")
async def get_connections(category: Optional[str] = None):
    return {"count": _sse_push_manager.get_connection_count(category)}


@sse_router.get("/history/{category}")
async def get_history(category: str, limit: int = 20):
    return {"history": _sse_push_manager.get_history(category, limit)}


@sse_router.get("/stats")
async def get_stats():
    return _sse_push_manager.get_stats()

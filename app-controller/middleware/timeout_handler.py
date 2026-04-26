from fastapi import Request, HTTPException
import asyncio
from core.logger import setup_logger

logger = setup_logger()


class TimeoutHandlerMiddleware:
    """Request timeout middleware.

    NOTE: Streaming endpoints (/v1/chat/completions with stream=True) are excluded
    from the global timeout so the connection can stay open for the full stream.
    """

    STREAMING_PATH_PREFIXES = ("/v1/chat/completions", "/v1/completions")
    LONG_RUNNING_PATH_PREFIXES = ("/manage/models/",)

    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds

    async def __call__(self, request: Request, call_next):
        # Skip timeout for streaming endpoints — they hold the connection open
        if any(request.url.path.startswith(p) for p in self.STREAMING_PATH_PREFIXES):
            return await call_next(request)

        # Skip timeout for long-running operations (model switch/start/stop)
        if any(request.url.path.startswith(p) for p in self.LONG_RUNNING_PATH_PREFIXES):
            return await call_next(request)

        try:
            response = await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request timeout after {self.timeout_seconds}s: {request.url}")
            raise HTTPException(
                status_code=504,
                detail=f"Request timeout after {self.timeout_seconds} seconds"
            )

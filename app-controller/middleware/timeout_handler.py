from fastapi import Request, HTTPException
import asyncio
from datetime import datetime
from core.logger import setup_logger

logger = setup_logger()

class TimeoutHandlerMiddleware:
    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
    
    async def __call__(self, request: Request, call_next):
        try:
            response = await asyncio.wait_for(call_next(request), timeout=self.timeout_seconds)
            return response
        except asyncio.TimeoutError:
            logger.error(f"Request timeout after {self.timeout_seconds}s: {request.url}")
            raise HTTPException(
                status_code=504,
                detail=f"Request timeout after {self.timeout_seconds} seconds"
            )
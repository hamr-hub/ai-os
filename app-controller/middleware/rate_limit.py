from fastapi import Request, HTTPException
from datetime import datetime, timedelta
from typing import Dict, Optional
from core.logger import setup_logger

logger = setup_logger()

class RateLimitMiddleware:
    def __init__(self, max_requests: int = 200, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, Dict[str, int]] = {}
        self.allowed_ips = {"127.0.0.1", "localhost", "::1"}
    
    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        
        if client_ip in self.allowed_ips:
            response = await call_next(request)
            return response
        
        now = datetime.now()
        
        if client_ip not in self.clients:
            self.clients[client_ip] = {"count": 0, "start_time": now}
        
        client_data = self.clients[client_ip]
        
        elapsed = (now - client_data["start_time"]).total_seconds()
        if elapsed >= self.window_seconds:
            client_data["count"] = 0
            client_data["start_time"] = now
        
        if client_data["count"] >= self.max_requests:
            wait_time = int(self.window_seconds - elapsed)
            logger.warning(f"Rate limit exceeded for {client_ip}: {client_data['count']}/{self.max_requests}")
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Please try again in {wait_time} seconds."
            )
        
        client_data["count"] += 1
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(self.max_requests - client_data["count"])
        
        return response
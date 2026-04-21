from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import traceback
from core.logger import setup_logger

logger = setup_logger()

class ControllerException(Exception):
    def __init__(self, message: str, code: int = 500, details: dict = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

class ModelNotFoundException(ControllerException):
    def __init__(self, model_name: str):
        super().__init__(f"Model {model_name} not found", code=404)

class InsufficientMemoryException(ControllerException):
    def __init__(self, available: int, required: int):
        super().__init__(
            f"Insufficient GPU memory available",
            code=503,
            details={"available": available, "required": required}
        )

class TooManyRequestsException(ControllerException):
    def __init__(self, active: int, limit: int, queue_length: int = 0):
        if queue_length > 0:
            message = f"Too Many Requests: {active}/{limit} concurrent requests, {queue_length} in queue"
            details = {"active": active, "limit": limit, "queue_length": queue_length}
        else:
            message = f"Too Many Requests: {active}/{limit} concurrent requests"
            details = {"active": active, "limit": limit}
        super().__init__(message, code=429, details=details)

class ModelServiceUnavailableException(ControllerException):
    def __init__(self, model_name: str, reason: str = ""):
        msg = f"Model service unavailable for {model_name}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, code=503)

class ServiceStartTimeoutException(ControllerException):
    def __init__(self, service_name: str, timeout: int = 120):
        super().__init__(
            f"Service {service_name} failed to start within {timeout}s",
            code=504,
            details={"service": service_name, "timeout": timeout}
        )

class GPUResourceExhaustedException(ControllerException):
    def __init__(self, gpu_id: int = 0, details: dict = None):
        msg = f"GPU {gpu_id} resources exhausted"
        super().__init__(msg, code=503, details=details or {})

class ConfigurationException(ControllerException):
    def __init__(self, message: str, config_key: str = ""):
        details = {"config_key": config_key} if config_key else {}
        super().__init__(message, code=500, details=details)

class RedisConnectionException(ControllerException):
    def __init__(self, host: str = "", port: int = 0):
        msg = "Redis connection failed"
        details = {}
        if host:
            details["host"] = host
            details["port"] = port
        super().__init__(msg, code=503, details=details)

class RateLimitExceededException(ControllerException):
    def __init__(self, limit: int, window: int, retry_after: int):
        super().__init__(
            f"Rate limit exceeded: {limit} requests per {window}s",
            code=429,
            details={"limit": limit, "window": window, "retry_after": retry_after}
        )

async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error {exc.status_code} at {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error at {request.url}: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "code": 500,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )

async def controller_exception_handler(request: Request, exc: ControllerException):
    logger.error(f"Controller error {exc.code} at {request.url}: {exc.args[0]}")
    content = {
        "error": exc.args[0],
        "code": exc.code,
        "timestamp": datetime.now().isoformat(),
        "path": str(request.url)
    }
    if exc.details:
        content["details"] = exc.details
    return JSONResponse(status_code=exc.code, content=content)
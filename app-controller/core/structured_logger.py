import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
import uuid

class StructuredLogger:
    def __init__(self, name: str = "ai_controller"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _format_log(self, level: str, message: str, **kwargs) -> str:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.upper(),
            "message": message,
            **kwargs
        }
        return json.dumps(log_entry)
    
    def debug(self, message: str, **kwargs):
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(self._format_log("debug", message, **kwargs))
    
    def info(self, message: str, **kwargs):
        self.logger.info(self._format_log("info", message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(self._format_log("warning", message, **kwargs))
    
    def error(self, message: str, **kwargs):
        self.logger.error(self._format_log("error", message, **kwargs))
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(self._format_log("critical", message, **kwargs))
    
    def log_request(self, endpoint: str, method: str, status_code: int, 
                    duration: float, model: Optional[str] = None,
                    request_id: Optional[str] = None):
        self.info(
            "Request completed",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=round(duration, 3),
            model=model,
            request_id=request_id
        )
    
    def log_model_event(self, model: str, event: str, **kwargs):
        self.info(
            f"Model {event}",
            model=model,
            event=event,
            **kwargs
        )
    
    def log_gpu_status(self, gpu_status: Dict):
        self.info(
            "GPU status updated",
            **gpu_status
        )
    
    def log_error(self, error: Exception, context: str = "", **kwargs):
        self.error(
            str(error),
            error_type=type(error).__name__,
            context=context,
            **kwargs
        )

class RequestContext:
    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.endpoint = ""
        self.method = ""
        self.model = ""
    
    @property
    def duration(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "duration": round(self.duration, 3),
            "endpoint": self.endpoint,
            "method": self.method,
            "model": self.model
        }

def setup_structured_logger(name: str = "ai_controller") -> StructuredLogger:
    return StructuredLogger(name)
from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List
from pydantic import BaseModel, Field

from core.deps import agent_system as _agent_system
from middleware.auth import request_is_authenticated

command_router = APIRouter(prefix="/manage/command")


class CommandRequest(BaseModel):
    command: Optional[str] = Field(default=None, description="Command to execute")
    argv: Optional[List[str]] = Field(default=None, description="Command and arguments as an array")
    timeout: int = Field(default=30, ge=1, le=120, description="Timeout in seconds")


class ValidateRequest(BaseModel):
    command: Optional[str] = Field(default=None, description="Command to validate")
    argv: Optional[List[str]] = Field(default=None, description="Command and arguments as an array")


def _extract_command_payload(request: CommandRequest | ValidateRequest):
    if request.argv:
        return request.argv
    if request.command:
        return request.command
    raise HTTPException(status_code=400, detail="command or argv is required")


def _require_command_auth(request: Request):
    if not request_is_authenticated(request):
        raise HTTPException(status_code=403, detail="command execution requires a valid admin token")


@command_router.post("/execute")
async def execute_command(body: CommandRequest, request: Request):
    _require_command_auth(request)
    result = await _agent_system.execute_command(_extract_command_payload(body), body.timeout)
    if result.get("status") == "rejected":
        raise HTTPException(status_code=403, detail=result.get("reason", "Command rejected"))
    return result


@command_router.post("/validate")
async def validate_command(request: ValidateRequest):
    return _agent_system.validate_command(_extract_command_payload(request))


@command_router.get("/result/{command_id}")
async def get_command_result(command_id: str):
    result = _agent_system.get_command_result(command_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Command '{command_id}' not found")
    return result


@command_router.delete("/cancel/{command_id}")
async def cancel_command(command_id: str):
    return _agent_system.cancel_command(command_id)


@command_router.get("/list")
async def list_commands(status_filter: Optional[str] = None):
    return {"commands": _agent_system.list_commands(status_filter)}


@command_router.get("/history")
async def get_history(limit: int = 20):
    return {"history": _agent_system.get_history(limit)}


@command_router.get("/stats")
async def get_stats():
    return _agent_system.get_stats()


@command_router.get("/system-info")
async def get_system_info(request: Request):
    _require_command_auth(request)
    return await _agent_system.get_system_info()

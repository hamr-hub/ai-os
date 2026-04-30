from fastapi import APIRouter, HTTPException, Request
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from core.deps import agent_system as _agent_system

command_router = APIRouter(prefix="/manage/command")


class CommandRequest(BaseModel):
    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(default=30, ge=1, le=120, description="Timeout in seconds")


class ValidateRequest(BaseModel):
    command: str = Field(..., description="Command to validate")


@command_router.post("/execute")
async def execute_command(request: CommandRequest):
    result = await _agent_system.execute_command(request.command, request.timeout)
    if result.get("status") == "rejected":
        raise HTTPException(status_code=403, detail=result.get("reason", "Command rejected"))
    return result


@command_router.post("/validate")
async def validate_command(request: ValidateRequest):
    return _agent_system.validate_command(request.command)


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
async def get_system_info():
    return await _agent_system.get_system_info()

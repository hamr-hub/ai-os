from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import asyncio

from core.deps import (
    gpu_memory_manager as _gpu_memory_manager,
    model_hub as _model_hub,
    download_task_manager as _download_task_manager,
    model_pool_manager as _model_pool_manager,
    model_engine_scheduler as _model_engine_scheduler,
    llm_service_manager as _llm_service_manager,
    sse_push_manager as _sse_push_manager,
)

hub_router = APIRouter(prefix="/manage/hub")


class DownloadRequest(BaseModel):
    model_name: str = Field(..., description="Model name/ID to download")
    source: str = Field(default="hf", description="Source: hf, ms, local")
    save_dir: Optional[str] = None
    auto_start: bool = Field(default=True, description="Auto start download task")
    hf_token: Optional[str] = Field(default=None, description="HuggingFace API token (overrides config/env)")
    allow_patterns: Optional[List[str]] = Field(default=None, description="File patterns to include in download")
    ignore_patterns: Optional[List[str]] = Field(default=None, description="File patterns to exclude from download")
    max_workers: Optional[int] = Field(default=None, description="Max parallel download workers")
    force_download: bool = Field(default=False, description="Force re-download even if model exists locally")


class DeployRequest(BaseModel):
    model_name: str = Field(..., description="Model name to deploy")
    engine_type: Optional[str] = Field(default=None, description="Engine: vllm, sglang, llamacpp")
    source: Optional[str] = Field(default=None, description="Download source if needed")
    port: Optional[int] = None
    force: bool = False


class SwitchRequest(BaseModel):
    model_name: str = Field(..., description="Target model name")
    engine_type: Optional[str] = None
    priority: str = "normal"
    port: Optional[int] = None


@hub_router.get("/models")
async def list_local_models():
    _model_hub.initialize()
    return {"models": _model_hub.list_local_models(), "source_info": _model_hub.get_source_info()}


@hub_router.get("/models/{model_name}")
async def get_model_info(model_name: str):
    info = _model_hub.get_model_info(model_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found locally")
    return info


@hub_router.get("/search")
async def search_models(keyword: str, source: str = "all", limit: int = 10, sort: Optional[str] = None):
    results = _model_engine_scheduler.search(keyword, source, limit, sort=sort)
    serialized = []
    for r in results:
        serialized.append({
            "name": r.name,
            "source": r.source,
            "size_b": r.size_b,
            "quant": r.quant,
            "required_gb": r.required_gb,
            "feasible": r.feasible,
            "model_id": r.model_id,
            "local_path": r.local_path,
            "description": r.description,
        })
    return {"results": serialized, "total": len(serialized), "keyword": keyword, "source": source}


@hub_router.get("/recommend")
async def recommend_model(keyword: str, source: str = "all", capabilities: Optional[str] = None):
    caps = capabilities.split(",") if capabilities else None
    result = _model_engine_scheduler.recommend(keyword, source, caps)
    if result.get("recommended"):
        rec = result["recommended"]
        result["recommended"] = {
            "name": rec.name,
            "source": rec.source,
            "size_b": rec.size_b,
            "quant": rec.quant,
            "feasible": rec.feasible,
        }
    return result


@hub_router.post("/download")
async def download_model(request: DownloadRequest):
    result = _download_task_manager.create_task(
        request.model_name, request.source,
        save_dir=request.save_dir, auto_start=request.auto_start,
        hf_token=request.hf_token,
        allow_patterns=request.allow_patterns,
        ignore_patterns=request.ignore_patterns,
        max_workers=request.max_workers,
        force_download=request.force_download,
    )
    return result


@hub_router.get("/download/{task_id}/status")
async def get_download_status(task_id: str):
    status = _download_task_manager.get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return status


@hub_router.delete("/download/{task_id}")
async def cancel_download(task_id: str):
    return _download_task_manager.cancel_task(task_id)


@hub_router.post("/download/{task_id}/retry")
async def retry_download(task_id: str):
    return _download_task_manager.retry_task(task_id)


@hub_router.get("/downloads")
async def list_downloads(status_filter: Optional[str] = None):
    return {"tasks": _download_task_manager.list_tasks(status_filter), "stats": _download_task_manager.get_stats()}


@hub_router.post("/deploy")
async def deploy_model(request: DeployRequest):
    result = await _model_engine_scheduler.deploy_model(
        request.model_name, request.engine_type,
        source=request.source, port=request.port, force=request.force,
    )
    return result


@hub_router.post("/undeploy/{model_name}")
async def undeploy_model(model_name: str):
    result = await _model_engine_scheduler.undeploy_model(model_name)
    return result


@hub_router.post("/switch")
async def switch_model(request: SwitchRequest):
    result = await _model_engine_scheduler.switch_model(
        request.model_name, request.engine_type,
        priority=request.priority, port=request.port,
    )
    return result


@hub_router.get("/engines")
async def list_engines():
    return {
        "engines": _model_engine_scheduler.get_available_engines(),
        "active_service": _model_engine_scheduler.get_active_service(),
    }


@hub_router.get("/deployment/summary")
async def deployment_summary():
    return _model_engine_scheduler.get_deployment_summary()


@hub_router.get("/switch/history")
async def switch_history(limit: int = 20):
    return {"history": _model_engine_scheduler.get_switch_history(limit)}


@hub_router.post("/auto-deploy")
async def auto_deploy(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    model_name = body.get("model_name")
    source = body.get("source", "hf")
    engine_type = body.get("engine_type", "vllm")
    port = body.get("port", 8000)
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name required")

    gpu_info = _gpu_memory_manager.get_gpu_info()
    feasibility = _gpu_memory_manager.check_model_feasibility(model_name)
    if feasibility and not feasibility.get("feasible"):
        return {
            "status": "rejected",
            "reason": "insufficient_gpu_memory",
            "feasibility": feasibility,
            "gpu_info": gpu_info,
        }

    pool_entry = _model_pool_manager.get_pool_detail(model_name)
    if pool_entry and pool_entry.get("download_status") == "completed":
        load_result = _model_pool_manager.load_model(model_name, engine_type, port)
        return {"status": "deployed_from_pool", "result": load_result}

    download_result = _download_task_manager.create_task(model_name, source)
    if download_result.get("status") == "error":
        return {"status": "download_failed", "reason": download_result.get("message")}
    if download_result.get("status") == "already_exists":
        local_path = download_result.get("local_path")
        _model_pool_manager.register_from_download(model_name, local_path, source)
        load_result = _model_pool_manager.load_model(model_name, engine_type, port)
        return {"status": "deployed_existing", "result": load_result, "local_path": local_path}

    return {
        "status": "download_started",
        "task_id": download_result.get("task_id"),
        "model_name": model_name,
        "message": "Download started. Model will auto-load after completion.",
        "gpu_feasibility": feasibility,
    }

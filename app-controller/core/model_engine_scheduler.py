import logging
import asyncio
import time
from typing import Dict, Optional, List, Any

from core.gpu_memory_checker import GPUMemoryChecker
from core.llm_service_manager import _MAX_RESTART_ATTEMPTS

logger = logging.getLogger("ai_controller.model_engine_scheduler")

_ENGINE_PRIORITY = {"vllm": 0, "sglang": 1, "llamacpp": 2}

_ENGINE_CAPABILITIES = {
    "vllm": {
        "supports_images": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
        "supports_speculative_decoding": True,
        "best_for": ["large_models", "production", "tool_calling", "multimodal"],
    },
    "sglang": {
        "supports_images": True,
        "supports_tool_calling": False,
        "supports_streaming": True,
        "supports_speculative_decoding": False,
        "best_for": ["high_throughput", "batch_inference", "fast_startup"],
    },
    "llamacpp": {
        "supports_images": False,
        "supports_tool_calling": False,
        "supports_streaming": True,
        "supports_speculative_decoding": False,
        "best_for": ["small_models", "quantized_models", "low_memory", "gguf"],
    },
}


class ModelEngineScheduler:

    def __init__(
        self,
        config=None,
        gpu_memory_manager=None,
        model_hub=None,
        download_manager=None,
        model_pool=None,
        llm_service_manager=None,
        engine_manager_mode: str = "subprocess",
    ):
        self._config = config
        self._gpu_mgr = gpu_memory_manager
        self._model_hub = model_hub
        self._download_mgr = download_manager
        self._model_pool = model_pool
        self._llm_mgr = llm_service_manager
        self._engine_manager_mode = engine_manager_mode
        self._switching_lock = asyncio.Lock()
        self._active_service: Optional[str] = None
        self._switch_history: List[Dict] = []
        self._max_history = 50
        self._engine_model_registry: Dict[str, Dict] = {}
        self._orchestrator = None

    def _cfg_get(self, cfg: Any, key: str, default=None):
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        return getattr(cfg, key, default)

    def _get_model_engine_from_config(self, model_name: str) -> str:
        if not self._config:
            return "vllm"
        model_cfg = None
        if hasattr(self._config, 'get_model'):
            model_cfg = self._config.get_model(model_name)
        elif isinstance(self._config, dict):
            model_cfg = self._config.get('models', {}).get(model_name)
        return self._cfg_get(model_cfg, "engine_type", "vllm") if model_cfg else "vllm"

    def _engine_mode(self) -> str:
        return getattr(self, "_engine_manager_mode", "subprocess")

    def _list_services(self) -> List[Dict]:
        if not self._llm_mgr:
            return []
        try:
            services = self._llm_mgr.list_services()
        except Exception:
            return []
        return services if isinstance(services, list) else []

    def _infer_service_engine(self, model_name: str, service: Optional[Dict] = None) -> str:
        if service:
            engine_type = service.get("engine_type")
            if engine_type:
                return engine_type
            service_name = service.get("service_name", "")
            if "-" in service_name:
                prefix = service_name.split("-", 1)[0]
                if prefix in _ENGINE_CAPABILITIES:
                    return prefix
        registry_engine = self._engine_model_registry.get(model_name, {}).get("engine")
        if registry_engine:
            return registry_engine
        return self._get_model_engine_from_config(model_name)

    def _is_engine_enabled(self, engine_type: str) -> bool:
        if engine_type == "vllm":
            return True
        engines_cfg = {}
        if isinstance(self._config, dict):
            engines_cfg = self._config.get("engines", {})
        elif hasattr(self._config, "engines"):
            engines_cfg = getattr(self._config, "engines") or {}
        engine_cfg = self._cfg_get(engines_cfg, engine_type, {})
        return bool(self._cfg_get(engine_cfg, "enabled", True))

    def _build_model_pool_from_config(self) -> Dict[str, Dict]:
        if not self._config:
            return {}
        pool = {}
        models_dict = {}
        if hasattr(self._config, 'models'):
            models_dict = self._config.models
        elif isinstance(self._config, dict):
            models_dict = self._config.get('models', {})
        for name, cfg in models_dict.items():
            pool[name] = {
                "engine": cfg.engine_type if hasattr(cfg, 'engine_type') else cfg.get("engine_type", "vllm"),
                "port": cfg.port if hasattr(cfg, 'port') else cfg.get("port", 8000),
                "model_path": cfg.model_path if hasattr(cfg, 'model_path') else cfg.get("model_path"),
                "required_memory": cfg.required_memory if hasattr(cfg, 'required_memory') else cfg.get("required_memory", "8GB"),
                "supports_images": cfg.supports_images if hasattr(cfg, 'supports_images') else cfg.get("supports_images", False),
                "supports_tool_calling": cfg.supports_tool_calling if hasattr(cfg, 'supports_tool_calling') else cfg.get("supports_tool_calling", False),
                "preload": cfg.preload if hasattr(cfg, 'preload') else cfg.get("preload", False),
                "keep_alive": cfg.keep_alive if hasattr(cfg, 'keep_alive') else cfg.get("keep_alive", True),
            }
            if hasattr(cfg, 'vllm_params') and cfg.vllm_params:
                pool[name]["vllm_params"] = cfg.vllm_params
            if hasattr(cfg, 'sglang_params') and cfg.sglang_params:
                pool[name]["sglang_params"] = cfg.sglang_params
            if hasattr(cfg, 'llamacpp_params') and cfg.llamacpp_params:
                pool[name]["llamacpp_params"] = cfg.llamacpp_params
        return pool

    def get_model_pool(self) -> Dict[str, Dict]:
        base = self._build_model_pool_from_config()
        for name, reg in self._engine_model_registry.items():
            if name in base:
                base[name].update({
                    "runtime_engine": reg.get("engine"),
                    "runtime_status": reg.get("status"),
                })
            else:
                base[name] = {
                    "engine": reg.get("engine", "vllm"),
                    "port": reg.get("port", 8000),
                    "model_path": reg.get("model_path"),
                    "required_memory": reg.get("required_memory", "unknown"),
                    "status": reg.get("status"),
                    "source": "runtime_registry",
                }
        return base

    def _sync_config_to_registry(self):
        if not self._config:
            return
        models_dict = {}
        if hasattr(self._config, 'models'):
            models_dict = self._config.models
        elif isinstance(self._config, dict):
            models_dict = self._config.get('models', {})
        for name, cfg in models_dict.items():
            if name not in self._engine_model_registry:
                preload = cfg.preload if hasattr(cfg, 'preload') else cfg.get("preload", False)
                engine = cfg.engine_type if hasattr(cfg, 'engine_type') else cfg.get("engine_type", "vllm")
                port = cfg.port if hasattr(cfg, 'port') else cfg.get("port", 8000)
                self._engine_model_registry[name] = {
                    "engine": engine,
                    "port": port,
                    "status": "config_defined",
                    "preload_intended": preload,
                }

    def show_gpu(self) -> Dict:
        if not self._gpu_mgr:
            return {"available": False, "message": "No GPU manager configured"}
        summary = self._gpu_mgr.get_memory_summary()
        summary["available"] = True
        return summary

    def get_realtime_gpu_info(self, device_id: int = 0) -> Dict:
        if not self._gpu_mgr:
            return {"available": False, "reason": "no_gpu_manager"}
        info = self._gpu_mgr.get_realtime_info(device_id)
        if not info:
            return {"available": False, "reason": "gpu_info_unavailable", "device_id": device_id}
        info["available"] = True
        info["timestamp"] = time.time()
        return info

    def get_all_gpu_realtime(self) -> Dict:
        if not self._gpu_mgr:
            return {"available": False, "devices": []}
        all_info = self._gpu_mgr.get_all_gpu_info()
        return {
            "available": True,
            "device_count": len(all_info),
            "devices": all_info,
            "backend": self._gpu_mgr.backend,
            "total_loaded_memory_gb": self._gpu_mgr.get_loaded_memory_gb(),
            "timestamp": time.time(),
        }

    def search(self, keyword: str, source: str = "all", limit: int = 10, sort: Optional[str] = None) -> List:
        if not self._model_hub:
            return []
        results = self._model_hub.search_models(keyword, source, limit, sort=sort)
        for r in results:
            if hasattr(r, 'size_b') and r.size_b and self._gpu_mgr:
                feasibility = self._gpu_mgr.check_model_feasibility(
                    "", size_b=r.size_b, quant=r.quant if hasattr(r, 'quant') else None,
                )
                if hasattr(r, 'feasible'):
                    r.feasible = feasibility["feasible"]
                if hasattr(r, 'required_gb'):
                    r.required_gb = feasibility.get("required_gb")
        return results

    def recommend_engine(self, model_name: str, required_capabilities: Optional[List[str]] = None) -> str:
        cfg = None
        if self._config and hasattr(self._config, 'get_model'):
            cfg = self._config.get_model(model_name)
        if cfg and hasattr(cfg, 'engine_type') and cfg.engine_type:
            return cfg.engine_type
        quant = GPUMemoryChecker.parse_model_quant(model_name)
        if quant in ("gguf", "awq", "gptq", "4bit"):
            return "llamacpp" if quant == "gguf" else "vllm"
        required = required_capabilities or []
        for engine_name, caps in _ENGINE_CAPABILITIES.items():
            if all(caps.get(cap, False) for cap in required if cap in caps):
                return engine_name
        if self._gpu_mgr:
            free_gb = self._gpu_mgr.get_total_free_gb()
            if free_gb < 8:
                return "llamacpp"
            elif free_gb < 16:
                return "vllm"
        return "vllm"

    def recommend(self, keyword: str, source: str = "all", capabilities: Optional[List[str]] = None) -> Dict:
        gpu_info = self.show_gpu()
        results = self.search(keyword, source)
        engine = self.recommend_engine(keyword, capabilities)
        best = None
        if results:
            feasible = [r for r in results if hasattr(r, 'feasible') and r.feasible is True]
            if feasible:
                feasible.sort(key=lambda r: getattr(r, 'size_b', float('inf')) or float('inf'))
                best = feasible[0]
            else:
                best = results[0]
        return {
            "gpu_info": gpu_info,
            "recommended": best,
            "recommended_engine": engine,
            "engine_capabilities": _ENGINE_CAPABILITIES.get(engine, {}),
            "candidates": results[:5],
        }

    def switch_engine(
        self, model_name: str, engine_type: str, port: Optional[int] = None,
    ) -> Dict:
        if engine_type not in _ENGINE_CAPABILITIES:
            return {"success": False, "reason": f"unsupported_engine: {engine_type}"}
        if not self._is_engine_enabled(engine_type):
            return {
                "success": False,
                "reason": "engine_disabled",
                "detail": f"引擎 {engine_type} 当前未启用。",
            }
        if not port:
            port = self._find_available_port(engine_type)

        from core.vllm_manager import get_current_model_info
        current_info = get_current_model_info()

        if current_info and current_info.get("running") and current_info.get("name"):
            existing_registry = self._engine_model_registry.get(current_info["name"], {})
            current_engine = existing_registry.get("engine") or self._get_model_engine_from_config(current_info["name"])
            if current_info["name"] == model_name and current_engine == engine_type:
                return {
                    "success": True,
                    "reason": "already_running_same_engine",
                    "model": current_info["name"],
                    "engine": engine_type,
                    "port": current_info.get("port") or port,
                    "service_name": current_info.get("service"),
                }

        engine_mode = self._engine_mode()

        if engine_mode == "systemd" and current_info and current_info.get("running"):
            pass
        else:
            if not self._llm_mgr:
                return {"success": False, "reason": "no_llm_service_manager"}
            existing = self._llm_mgr.get_service_by_model(model_name)
            if existing and existing.get("status") == "running":
                existing_engine = self._infer_service_engine(model_name, existing)
                if existing_engine == engine_type:
                    return {
                        "success": True,
                        "reason": "already_running_same_engine",
                        "service": existing,
                    }

        if self._gpu_mgr:
            is_current_model = (
                engine_mode == "systemd"
                and current_info
                and current_info.get("running")
                and current_info.get("name") == model_name
            )
            services = self._list_services()
            has_running_service = (
                (current_info and current_info.get("running"))
                or any(svc.get("status") == "running" for svc in services)
            )
            if not is_current_model and not has_running_service:
                feasibility = self._gpu_mgr.check_model_feasibility(model_name)
                if not feasibility.get("feasible", True):
                    return {
                        "success": False,
                        "reason": "insufficient_gpu_memory",
                        "feasibility": feasibility,
                        "suggestion": f"需要 {feasibility.get('required_gb', '?')}GB，可用 {feasibility.get('available_gb', '?')}GB",
                    }

        self._engine_model_registry[model_name] = {
            "engine": engine_type,
            "port": port,
            "status": "switching",
            "requested_at": time.time(),
        }

        if engine_mode == "systemd" and engine_type != "vllm" and not self._llm_mgr:
            self._engine_model_registry[model_name]["status"] = "failed"
            self._engine_model_registry[model_name]["error"] = "non_vllm_not_supported_in_systemd"
            return {
                "success": False,
                "reason": "non_vllm_engine_not_supported_in_systemd_mode",
                "detail": f"引擎 {engine_type} 在 systemd 模式下不支持，仅支持 vllm。",
            }

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._do_engine_switch(model_name, engine_type, port))
        except RuntimeError:
            logger.warning("No running event loop for engine switch, will execute on next loop cycle")
        return {
            "success": True,
            "reason": "switch_initiated",
            "model": model_name,
            "engine_type": engine_type,
            "port": port,
            "status": "switching",
            "message": "引擎切换已启动，可通过 /manage/scheduler/status 查询进度",
        }

    async def _do_engine_switch(
        self, model_name: str, engine_type: str, port: int,
    ) -> Dict:
        async with self._switching_lock:
            try:
                if self._engine_mode() == "systemd":
                    return await self._do_systemd_engine_switch(model_name, engine_type, port)
                else:
                    return await self._do_subprocess_engine_switch(model_name, engine_type, port)
            except Exception as e:
                logger.error("Engine switch failed for %s: %s", model_name, e)
                if model_name in self._engine_model_registry:
                    self._engine_model_registry[model_name]["status"] = "failed"
                    self._engine_model_registry[model_name]["error"] = str(e)
                return {"success": False, "reason": str(e)}

    async def _do_systemd_engine_switch(
        self, model_name: str, engine_type: str, port: int,
    ) -> Dict:
        from core.vllm_manager import (
            stop_vllm_service, start_vllm_service,
            get_current_model_info, _update_vllm_script,
            refresh_vllm_port_cache, discover_vllm_port,
            _build_vllm_health_url,
        )

        current_info = get_current_model_info()
        previous_model = current_info.get("name") if current_info and current_info.get("running") else None
        previous_model_path = current_info.get("path") if current_info else None

        model_path = None
        if self._model_hub:
            model_path = self._model_hub.get_model_local_path(model_name)
        if not model_path and self._config:
            if hasattr(self._config, 'get_model'):
                cfg = self._config.get_model(model_name)
                if cfg and hasattr(cfg, 'model_path') and cfg.model_path:
                    model_path = cfg.model_path
                elif isinstance(cfg, dict) and cfg.get("model_path"):
                    model_path = cfg.get("model_path")
        if not model_path:
            import os as _os
            model_path = _os.path.join("/mnt/pve_models", model_name)

        if engine_type != "vllm" and not self._llm_mgr:
            return {
                "success": False,
                "reason": "non_vllm_engine_not_supported_in_systemd_mode",
                "detail": f"引擎 {engine_type} 在 systemd 模式下不支持，仅支持 vllm。",
            }

        if current_info and current_info.get("running"):
            if engine_type == "vllm":
                logger.info("Stopping current systemd vllm service for vllm engine switch (model=%s)", previous_model)
                stop_vllm_service()
                await asyncio.sleep(5)
            elif self._llm_mgr:
                logger.info("Stopping current systemd vllm service for non-vllm engine switch (model=%s → %s)", previous_model, engine_type)
                stop_vllm_service()
                await asyncio.sleep(5)

        if self._gpu_mgr:
            self._gpu_mgr.unregister_loaded_model(previous_model) if previous_model else None
            await asyncio.sleep(2)

        if engine_type == "vllm":
            script_ok = _update_vllm_script(model_path, model_name)
            if not script_ok:
                self._engine_model_registry[model_name]["status"] = "failed"
                self._engine_model_registry[model_name]["error"] = "config_update_failed"
                return {"success": False, "reason": "config_update_failed"}

            refresh_vllm_port_cache()

            start_ok = start_vllm_service()
            if not start_ok:
                self._engine_model_registry[model_name]["status"] = "failed"
                self._engine_model_registry[model_name]["error"] = "systemd_start_failed"
                return {"success": False, "reason": "systemd_start_failed"}

            ready = False
            for attempt in range(120):
                await asyncio.sleep(2)
                try:
                    port = discover_vllm_port()
                    import httpx
                    async with httpx.AsyncClient(timeout=3) as client:
                        resp = await client.get(_build_vllm_health_url(port))
                        if resp.status_code == 200:
                            ready = True
                            break
                except Exception:
                    pass
                if attempt % 15 == 0:
                    logger.info("Waiting for vllm systemd service ready... (%ds)", attempt * 2)

            if not ready:
                self._engine_model_registry[model_name]["status"] = "failed"
                self._engine_model_registry[model_name]["error"] = "systemd_service_not_ready"
                return {"success": False, "reason": "systemd_service_not_ready"}

            if self._gpu_mgr:
                self._gpu_mgr.register_loaded_model(model_name, device_id=0)

            self._engine_model_registry[model_name].update({
                "status": "running",
                "service_name": "vllm-aiclient",
                "switched_at": time.time(),
            })
            self._active_service = "vllm-aiclient"
            self._record_switch(model_name, engine_type, port, "systemd_engine_switch")
            logger.info("Systemd engine switch completed: %s → %s on port %d", model_name, engine_type, port)
            return {
                "success": True,
                "model": model_name,
                "engine_type": engine_type,
                "port": port,
                "service_name": "vllm-aiclient",
                "previous_model": previous_model,
            }
        else:
            if not self._llm_mgr:
                self._engine_model_registry[model_name]["status"] = "failed"
                self._engine_model_registry[model_name]["error"] = "no_llm_service_manager"
                return {"success": False, "reason": "no_llm_service_manager_for_non_vllm_engine"}

            service_name = f"{engine_type}-{model_name.split('/')[-1]}"
            result = self._llm_mgr.start_service(
                service_name, model_name, engine_type, port,
                model_path=model_path,
            )
            if result.get("status") != "started":
                self._engine_model_registry[model_name]["status"] = "failed"
                return {"success": False, "reason": result.get("message", "start_failed"), "detail": result}

            ready = await self._llm_mgr.wait_for_ready(service_name, port, timeout=120)
            if not ready:
                self._llm_mgr.stop_service(service_name)
                self._engine_model_registry[model_name]["status"] = "failed"
                self._engine_model_registry[model_name]["error"] = "service_not_ready"
                return {"success": False, "reason": "service_not_ready"}

            if self._gpu_mgr:
                self._gpu_mgr.register_loaded_model(model_name, device_id=0)

            self._engine_model_registry[model_name].update({
                "status": "running",
                "service_name": service_name,
                "switched_at": time.time(),
            })
            self._active_service = service_name
            self._record_switch(model_name, engine_type, port, "systemd_engine_switch_non_vllm")
            logger.info("Systemd engine switch (non-vllm) completed: %s → %s on port %d", model_name, engine_type, port)
            return {
                "success": True,
                "model": model_name,
                "engine_type": engine_type,
                "port": port,
                "service_name": service_name,
                "previous_model": previous_model,
            }

    async def _stop_all_services(self, exclude_model: Optional[str] = None):
        if not self._llm_mgr:
            return []
        stopped_models = []
        for svc in list(self._llm_mgr.list_services()):
            if svc.get("status") != "running":
                continue
            svc_model = svc.get("model", "")
            if exclude_model and svc_model == exclude_model:
                continue
            self._llm_mgr.stop_service(svc["service_name"])
            if svc_model:
                stopped_models.append(svc_model)
        await asyncio.sleep(3)
        for model in stopped_models:
            if self._gpu_mgr:
                self._gpu_mgr.unregister_loaded_model(model)
            if model in self._engine_model_registry:
                self._engine_model_registry[model]["status"] = "stopped"
        return stopped_models

    async def _do_subprocess_engine_switch(
        self, model_name: str, engine_type: str, port: int,
    ) -> Dict:
        if self._gpu_mgr:
            feasibility = self._gpu_mgr.check_model_feasibility(model_name)
            if not feasibility.get("feasible", True):
                freed = await self._free_up_memory_for(model_name)
                if not freed:
                    self._engine_model_registry[model_name]["status"] = "failed"
                    self._engine_model_registry[model_name]["error"] = "insufficient_memory"
                    return {"success": False, "reason": "insufficient_gpu_memory"}
        await self._stop_all_services()
        model_path = None
        if self._model_hub:
            model_path = self._model_hub.get_model_local_path(model_name)
        if not model_path and self._config:
            if hasattr(self._config, 'get_model'):
                cfg = self._config.get_model(model_name)
                if cfg and hasattr(cfg, 'model_path') and cfg.model_path:
                    model_path = cfg.model_path
                elif isinstance(cfg, dict) and cfg.get("model_path"):
                    model_path = cfg.get("model_path")
        if not self._llm_mgr:
            return {"success": False, "reason": "no_llm_service_manager"}
        service_name = f"{engine_type}-{model_name.split('/')[-1]}"
        result = self._llm_mgr.start_service(
            service_name, model_name, engine_type, port,
            model_path=model_path,
        )
        if result.get("status") != "started":
            self._engine_model_registry[model_name]["status"] = "failed"
            return {"success": False, "reason": result.get("message", "start_failed"), "detail": result}
        ready = await self._llm_mgr.wait_for_ready(service_name, port, timeout=120)
        if not ready:
            self._llm_mgr.stop_service(service_name)
            self._engine_model_registry[model_name]["status"] = "failed"
            self._engine_model_registry[model_name]["error"] = "service_not_ready"
            return {"success": False, "reason": "service_not_ready"}
        if self._gpu_mgr:
            self._gpu_mgr.register_loaded_model(model_name, device_id=0)
        self._engine_model_registry[model_name].update({
            "status": "running",
            "service_name": service_name,
            "switched_at": time.time(),
        })
        self._active_service = service_name
        self._record_switch(model_name, engine_type, port, "engine_switch")
        logger.info("Engine switch completed: %s → %s on port %d", model_name, engine_type, port)
        return {
            "success": True,
            "model": model_name,
            "engine_type": engine_type,
            "port": port,
            "service_name": service_name,
        }

    async def deploy_model(
        self, model_name: str, engine_type: Optional[str] = None,
        source: Optional[str] = None, port: Optional[int] = None,
        force: bool = False,
    ) -> Dict:
        if not engine_type:
            engine_type = self.recommend_engine(model_name)
        if not port:
            port = self._find_available_port(engine_type)
        feasibility = None
        if self._gpu_mgr:
            feasibility = self._gpu_mgr.check_model_feasibility(model_name)
            if not feasibility["feasible"] and not force:
                return {
                    "success": False,
                    "reason": "insufficient_gpu_memory",
                    "feasibility": feasibility,
                }
        service_name = f"{engine_type}-{model_name.split('/')[-1]}"
        dl_result = None
        if self._download_mgr and source:
            dl_result = await self._ensure_model_downloaded(model_name, source)
        async with self._switching_lock:
            current = self._llm_mgr.get_service_by_model(model_name) if self._llm_mgr else None
            if current and current.get("status") == "running" and not force:
                self._active_service = service_name
                self._engine_model_registry[model_name] = {
                    "engine": engine_type, "port": port, "status": "running",
                    "service_name": current.get("service_name"),
                }
                return {
                    "success": True,
                    "reason": "already_running",
                    "service": current,
                }
            if force and self._llm_mgr:
                for svc in self._llm_mgr.list_services():
                    if svc.get("model") == model_name:
                        self._llm_mgr.stop_service(svc["service_name"])
                        await asyncio.sleep(2)
            model_path = None
            if self._model_hub:
                model_path = self._model_hub.get_model_local_path(model_name)
            if not self._llm_mgr:
                return {"success": False, "reason": "no_llm_service_manager"}
            result = self._llm_mgr.start_service(
                service_name, model_name, engine_type, port,
                model_path=model_path,
            )
            if result.get("status") != "started":
                return {"success": False, "reason": result.get("message", "start_failed"), "detail": result}
            ready = await self._llm_mgr.wait_for_ready(service_name, port, timeout=120)
            if not ready:
                self._llm_mgr.stop_service(service_name)
                return {"success": False, "reason": "service_not_ready", "detail": result}
            if self._gpu_mgr:
                self._gpu_mgr.register_loaded_model(model_name, device_id=0)
            self._active_service = service_name
            self._engine_model_registry[model_name] = {
                "engine": engine_type, "port": port, "status": "running",
                "service_name": service_name, "deployed_at": time.time(),
            }
            self._record_switch(model_name, engine_type, port, "deploy")
            return {
                "success": True,
                "service_name": service_name,
                "engine_type": engine_type,
                "model": model_name,
                "port": port,
                "feasibility": feasibility,
                "download": dl_result,
            }

    async def undeploy_model(self, model_name: str) -> Dict:
        async with self._switching_lock:
            if not self._llm_mgr:
                return {"success": False, "reason": "no_llm_service_manager"}
            service = self._llm_mgr.get_service_by_model(model_name)
            if not service:
                return {"success": False, "reason": "model_not_running"}
            service_name = service.get("service_name", "")
            stopped = self._llm_mgr.stop_service(service_name)
            if not stopped:
                return {"success": False, "reason": "stop_failed"}
            if self._gpu_mgr:
                self._gpu_mgr.unregister_loaded_model(model_name)
            if model_name in self._engine_model_registry:
                self._engine_model_registry[model_name]["status"] = "stopped"
            if self._active_service == service_name:
                self._active_service = None
            self._record_switch(model_name, "", 0, "undeploy")
            await asyncio.sleep(3)
            return {"success": True, "model": model_name, "service_name": service_name}

    async def switch_model(
        self, target_model: str, engine_type: Optional[str] = None,
        priority: str = "normal", port: Optional[int] = None,
    ) -> Dict:
        if not engine_type:
            engine_type = self.recommend_engine(target_model)
        if not port:
            port = self._find_available_port(engine_type)
        feasibility = None
        async with self._switching_lock:
            target_service = self._llm_mgr.get_service_by_model(target_model) if self._llm_mgr else None
            if target_service and target_service.get("status") == "running":
                current_engine = self._infer_service_engine(target_model, target_service)
                if current_engine == engine_type:
                    self._active_service = target_service["service_name"]
                    self._record_switch(target_model, engine_type, port, "select_existing")
                    return {
                        "success": True,
                        "reason": "already_running",
                        "service": target_service,
                    }
            if self._gpu_mgr:
                feasibility = self._gpu_mgr.check_model_feasibility(target_model)
                if not feasibility.get("feasible", True):
                    freed = await self._free_up_memory_for(target_model)
                    if not freed:
                        return {
                            "success": False,
                            "reason": "insufficient_gpu_memory",
                            "feasibility": feasibility,
                            "suggestion": f"需要 {feasibility.get('required_gb', '?')}GB，可用 {feasibility.get('available_gb', '?')}GB",
                        }
            stopped_models = await self._stop_all_services(exclude_model=None)
            model_path = None
            if self._model_hub:
                model_path = self._model_hub.get_model_local_path(target_model)
            service_name = f"{engine_type}-{target_model.split('/')[-1]}"
            result = self._llm_mgr.start_service(
                service_name, target_model, engine_type, port,
                model_path=model_path,
            )
            if result.get("status") != "started":
                return {"success": False, "reason": result.get("message", "start_failed"), "detail": result}
            ready = await self._llm_mgr.wait_for_ready(service_name, port, timeout=120)
            if not ready:
                self._llm_mgr.stop_service(service_name)
                return {"success": False, "reason": "service_not_ready"}
            if self._gpu_mgr:
                self._gpu_mgr.register_loaded_model(target_model, device_id=0)
            self._active_service = service_name
            self._engine_model_registry[target_model] = {
                "engine": engine_type, "port": port, "status": "running",
                "service_name": service_name, "switched_at": time.time(),
            }
            self._record_switch(target_model, engine_type, port, "switch")
            return {
                "success": True,
                "service_name": service_name,
                "engine_type": engine_type,
                "model": target_model,
                "port": port,
                "stopped_models": stopped_models,
            }

    async def auto_deploy_model(
        self, model_name: str,
        engine_type: Optional[str] = None,
        port: Optional[int] = None,
        download_if_missing: bool = False,
        source: Optional[str] = None,
    ) -> Dict:
        if not engine_type:
            engine_type = self.recommend_engine(model_name)
        if not port:
            port = self._find_available_port(engine_type)
        if self._gpu_mgr:
            feasibility = self._gpu_mgr.check_model_feasibility(model_name)
            if not feasibility.get("feasible", True):
                return {
                    "success": False,
                    "stage": "memory_check",
                    "reason": "insufficient_gpu_memory",
                    "feasibility": feasibility,
                    "suggestion": f"需要 {feasibility.get('required_gb', '?')}GB，可用 {feasibility.get('available_gb', '?')}GB",
                }
        if download_if_missing and source and self._download_mgr:
            dl_result = await self._ensure_model_downloaded(model_name, source)
            if dl_result.get("status") == "failed":
                return {"success": False, "stage": "download", "reason": dl_result.get("status")}
        return await self.deploy_model(model_name, engine_type, source, port)

    async def _free_up_memory_for(self, target_model: str) -> bool:
        if not self._gpu_mgr:
            return False
        feasibility = self._gpu_mgr.check_model_feasibility(target_model)
        if feasibility["feasible"]:
            return True
        if self._engine_mode() == "systemd":
            from core.vllm_manager import stop_vllm_service, get_current_model_info
            current_info = get_current_model_info()
            if current_info and current_info.get("running"):
                current_model = current_info.get("name", "")
                if current_model != target_model:
                    logger.info("Stopping systemd vllm service to free memory for %s", target_model)
                    stop_vllm_service()
                    if self._gpu_mgr:
                        self._gpu_mgr.unregister_loaded_model(current_model)
                    if current_model in self._engine_model_registry:
                        self._engine_model_registry[current_model]["status"] = "stopped"
                    await asyncio.sleep(5)
                    new_feasibility = self._gpu_mgr.check_model_feasibility(target_model)
                    if new_feasibility["feasible"]:
                        return True
        if self._llm_mgr:
            services = self._llm_mgr.list_services()
            services.sort(key=lambda s: s.get("uptime_seconds", 0))
            for svc in services:
                model = svc.get("model", "")
                if model == target_model:
                    continue
                self._llm_mgr.stop_service(svc["service_name"])
                self._gpu_mgr.unregister_loaded_model(model)
                if model in self._engine_model_registry:
                    self._engine_model_registry[model]["status"] = "stopped"
                await asyncio.sleep(3)
                new_feasibility = self._gpu_mgr.check_model_feasibility(target_model)
                if new_feasibility["feasible"]:
                    return True
        return False

    async def _ensure_model_downloaded(self, model_name: str, source: str) -> Dict:
        if not self._download_mgr:
            return {"status": "skipped", "reason": "no_download_manager"}
        local_path = None
        if self._model_hub:
            local_path = self._model_hub.get_model_local_path(model_name)
        if local_path:
            return {"status": "already_exists", "local_path": local_path}
        dl_result = self._download_mgr.create_task(model_name, source)
        if dl_result.get("status") == "already_exists":
            return dl_result
        task_id = dl_result.get("task_id")
        if not task_id:
            return dl_result
        for _ in range(300):
            await asyncio.sleep(1)
            status = self._download_mgr.get_status(task_id)
            if not status:
                break
            if status["status"] in ("completed", "failed", "cancelled"):
                return status
        return {"status": "timeout", "task_id": task_id}

    def _find_available_port(self, engine_type: str) -> int:
        base_ports = {"vllm": 8000, "sglang": 8100, "llamacpp": 8200}
        base = base_ports.get(engine_type, 8000)
        if not self._llm_mgr:
            return base
        used_ports = set()
        for svc in self._llm_mgr.list_services():
            used_ports.add(svc.get("port", 0))
        for offset in range(10):
            port = base + offset
            if port not in used_ports:
                return port
        return base

    def _record_switch(self, model: str, engine: str, port: int, action: str):
        record = {
            "timestamp": time.time(),
            "model": model,
            "engine": engine,
            "port": port,
            "action": action,
        }
        self._switch_history.append(record)
        if len(self._switch_history) > self._max_history:
            self._switch_history = self._switch_history[-self._max_history:]

    def get_switch_history(self, limit: int = 20) -> List[Dict]:
        return self._switch_history[-limit:]

    def get_active_service(self) -> Optional[Dict]:
        if not self._llm_mgr or not self._active_service:
            return None
        return self._llm_mgr.get_service_status(self._active_service)

    def get_available_engines(self) -> Dict[str, Dict]:
        return dict(_ENGINE_CAPABILITIES)

    def get_scheduler_status(self) -> Dict:
        gpu_summary = self.show_gpu()
        services = self._llm_mgr.list_services() if self._llm_mgr else []
        model_pool = self.get_model_pool()
        return {
            "active_service": self._active_service,
            "gpu": gpu_summary,
            "running_services": services,
            "running_count": len([s for s in services if s.get("status") == "running"]),
            "model_pool_size": len(model_pool),
            "engine_registry": self._engine_model_registry,
            "switch_history_count": len(self._switch_history),
            "last_switch": self._switch_history[-1] if self._switch_history else None,
            "available_engines": list(_ENGINE_CAPABILITIES.keys()),
        }

    def get_deployment_summary(self) -> Dict:
        gpu = self.show_gpu()
        services = self._llm_mgr.list_services() if self._llm_mgr else []
        loaded = self._gpu_mgr.get_loaded_models() if self._gpu_mgr else {}
        return {
            "gpu": gpu,
            "running_services": services,
            "loaded_models": list(loaded.keys()),
            "active_service": self._active_service,
            "switch_history_count": len(self._switch_history),
        }

    async def _health_watcher_loop(self, interval: int = 5):
        logger.info("Engine health watcher started (interval=%ds)", interval)
        while True:
            try:
                if not self._llm_mgr:
                    await asyncio.sleep(interval)
                    continue
                services = self._llm_mgr.list_services()
                for svc in services:
                    name = svc.get("service_name", "")
                    if svc.get("status") == "stopped":
                        exit_code = svc.get("exit_code", -1)
                        logger.warning(
                            "Service %s died (exit_code=%s), attempting auto-restart",
                            name, exit_code,
                        )
                        model = self._llm_mgr._models.get(name, "")
                        if model and model in self._engine_model_registry:
                            reg = self._engine_model_registry[model]
                            if reg.get("status") == "running":
                                reg["status"] = "crashed"
                                reg["exit_code"] = exit_code
                        if self._llm_mgr.get_restart_count(name) < _MAX_RESTART_ATTEMPTS:
                            if self._orchestrator and self._orchestrator.is_switching:
                                logger.info("Skipping auto-restart for %s: model switch in progress", name)
                                continue
                            result = self._llm_mgr.auto_restart(name)
                            if result.get("status") == "started":
                                logger.info("Auto-restarted service %s (pid=%s)", name, result.get("pid"))
                                if model and model in self._engine_model_registry:
                                    self._engine_model_registry[model]["status"] = "restarting"
                                    port = self._llm_mgr._ports.get(name, 8000)
                                    ready = await self._llm_mgr.wait_for_ready(name, port, timeout=120)
                                    if ready:
                                        self._engine_model_registry[model]["status"] = "running"
                                        logger.info("Auto-restart service %s ready", name)
                                    else:
                                        self._engine_model_registry[model]["status"] = "failed"
                                        logger.error("Auto-restart service %s failed readiness", name)
                            else:
                                logger.error("Auto-restart failed for %s: %s", name, result)
                        else:
                            logger.error("Service %s exceeded max restart attempts", name)
                            if model and model in self._engine_model_registry:
                                self._engine_model_registry[model]["status"] = "dead"
                    elif svc.get("status") == "running":
                        healthy = await self._llm_mgr.check_http_health(name)
                        if not healthy:
                            logger.warning("Service %s process alive but HTTP unhealthy", name)
                for name, reg in self._engine_model_registry.items():
                    if reg.get("preload_intended") and reg.get("status") in ("stopped", "crashed", "dead"):
                        if self._active_service:
                            logger.debug("Skipping preload for %s: active service %s is running", name, self._active_service)
                            continue
                        service = self._llm_mgr.get_service_by_model(name) if self._llm_mgr else None
                        if not service or service.get("status") != "running":
                            logger.info("Preload model %s not running, attempting deploy", name)
                            engine = reg.get("engine", "vllm")
                            port = reg.get("port", 8000)
                            try:
                                result = await self.deploy_model(name, engine_type=engine, port=port)
                                if result.get("success"):
                                    logger.info("Preload redeployed %s successfully", name)
                                else:
                                    logger.warning("Preload redeploy failed for %s: %s", name, result.get("reason"))
                            except Exception as e:
                                logger.error("Preload redeploy error for %s: %s", name, e)
            except Exception as e:
                logger.error("Health watcher loop error: %s", e)
            await asyncio.sleep(interval)

import re
import os
import json
import logging
import hashlib
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger("ai_controller.model_hub")

_HF_ENDPOINT_DEFAULT = "https://hf-mirror.com"

_SOURCE_PRIORITY = ["local", "huggingface", "modelscope"]

_MODEL_EXTENSIONS = ['.safetensors', '.bin', '.pt', '.gguf', '.onnx']

_CONFIG_FILES = ['config.json', 'tokenizer_config.json', 'tokenizer.json', 'special_tokens_map.json']


@dataclass
class SearchResult:
    name: str
    source: str
    size_b: Optional[float] = None
    quant: Optional[str] = None
    required_gb: Optional[float] = None
    feasible: Optional[bool] = None
    model_id: Optional[str] = None
    description: Optional[str] = None
    local_path: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    downloads: Optional[int] = None
    architecture: Optional[str] = None


@dataclass
class LocalModelInfo:
    name: str
    path: str
    total_size_bytes: int
    quant: str
    architecture: Optional[str] = None
    config_exists: bool = False
    last_modified: Optional[float] = None

    @property
    def size_gb(self) -> float:
        return self.total_size_bytes / (1024 ** 3)


class MultiSourceModelHub:

    def __init__(self, config=None, gpu_memory_manager=None):
        self._config = config
        self._gpu_memory_manager = gpu_memory_manager
        self._local_models: Dict[str, LocalModelInfo] = {}
        self._model_metadata: Dict[str, Dict] = {}
        self._hf_endpoint = _HF_ENDPOINT_DEFAULT
        self._save_root = "/mnt/pve_models"
        self._initialized = False

        if config:
            if hasattr(config, 'vllm') and config.vllm:
                self._save_root = config.vllm.get("model_base_path", self._save_root)
                self._hf_endpoint = config.vllm.get("hf_endpoint", self._hf_endpoint)
            if hasattr(config, 'engines') and config.engines:
                hub_cfg = config.engines.get("hub", {})
                if hub_cfg:
                    self._save_root = hub_cfg.get("save_root", self._save_root)
                    self._hf_endpoint = hub_cfg.get("hf_endpoint", self._hf_endpoint)

    def initialize(self):
        if self._initialized:
            return
        self._scan_local_models()
        self._initialized = True
        logger.info(
            "ModelHub initialized, local_models=%d, save_root=%s",
            len(self._local_models), self._save_root,
        )

    def _scan_local_models(self):
        if not os.path.isdir(self._save_root):
            logger.warning("Local model directory not found: %s", self._save_root)
            return
        for entry in os.listdir(self._save_root):
            full_path = os.path.join(self._save_root, entry)
            if not os.path.isdir(full_path):
                continue
            info = self._analyze_local_model(entry, full_path)
            if info:
                self._local_models[entry] = info

    def _analyze_local_model(self, name: str, path: str) -> Optional[LocalModelInfo]:
        total_size = 0
        has_config = False
        architecture = None
        last_modified = None

        for root, _, files in os.walk(path):
            for f in files:
                full_file = os.path.join(root, f)
                if any(f.endswith(ext) for ext in _MODEL_EXTENSIONS):
                    total_size += os.path.getsize(full_file)
                if f in _CONFIG_FILES:
                    has_config = True
                    if f == 'config.json':
                        try:
                            with open(full_file, 'r') as fh:
                                cfg = json.load(fh)
                                architecture = cfg.get("model_type", cfg.get("architectures", [None])[0])
                        except Exception:
                            pass
            try:
                mt = os.path.getmtime(root)
                if last_modified is None or mt > last_modified:
                    last_modified = mt
            except Exception:
                pass

        if total_size == 0:
            return None

        quant = self._parse_quant(name) or self._detect_quant_from_files(path) or "fp16"
        return LocalModelInfo(
            name=name,
            path=path,
            total_size_bytes=total_size,
            quant=quant,
            architecture=architecture,
            config_exists=has_config,
            last_modified=last_modified,
        )

    def _detect_quant_from_files(self, path: str) -> Optional[str]:
        for root, _, files in os.walk(path):
            for f in files:
                fl = f.lower()
                if fl.endswith('.gguf'):
                    return "gguf"
                if 'awq' in fl:
                    return "awq"
                if 'gptq' in fl:
                    return "gptq"
        return None

    def _parse_size(self, model_name: str) -> Optional[float]:
        patterns = [
            r'(\d+(?:\.\d+)?)\s*B',
            r'[-](\d+(?:\.\d+)?)B[-]',
            r'[-](\d+(?:\.\d+)?)B$',
            r'^(\d+(?:\.\d+)?)B',
        ]
        for pat in patterns:
            m = re.search(pat, model_name, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    def _parse_quant(self, model_name: str) -> Optional[str]:
        quant_patterns = [
            (r'(4bit|int4|4[-_]bit)', "4bit"),
            (r'(8bit|int8|8[-_]bit)', "8bit"),
            (r'(fp16|fp[-_]16)', "fp16"),
            (r'(bf16|bf[-_]16)', "bf16"),
            (r'(awq|AWQ)', "awq"),
            (r'(gptq|GPTQ)', "gptq"),
            (r'(gguf|GGUF)', "gguf"),
            (r'(nvfp4|NVFP4)', "nvfp4"),
        ]
        for pat, label in quant_patterns:
            if re.search(pat, model_name, re.IGNORECASE):
                return label
        return None

    def get_model_local_path(self, model_name: str) -> Optional[str]:
        short_name = model_name.split('/')[-1]
        if short_name in self._local_models:
            return self._local_models[short_name].path
        direct_path = os.path.join(self._save_root, short_name)
        if os.path.isdir(direct_path):
            return direct_path
        full_path = os.path.join(self._save_root, model_name)
        if os.path.isdir(full_path):
            return full_path
        return None

    def is_model_local(self, model_name: str) -> bool:
        return self.get_model_local_path(model_name) is not None

    def list_local_models(self) -> List[Dict]:
        self.initialize()
        results = []
        for name, info in self._local_models.items():
            result = {
                "name": name,
                "path": info.path,
                "size_gb": round(info.size_gb, 2),
                "quant": info.quant,
                "architecture": info.architecture,
                "config_exists": info.config_exists,
                "source": "local",
            }
            if self._gpu_memory_manager:
                feasibility = self._gpu_memory_manager.check_model_feasibility(
                    name, model_path=info.path,
                )
                result["feasibility"] = feasibility
            results.append(result)
        return results

    def search_models(self, keyword: str, source: str = "all", limit: int = 10) -> List[SearchResult]:
        self.initialize()
        results = []
        if source in ("local", "all"):
            results.extend(self._search_local(keyword, limit))
        if source in ("huggingface", "hf", "all"):
            results.extend(self._search_hf(keyword, limit))
        if source in ("modelscope", "ms", "all"):
            results.extend(self._search_ms(keyword, limit))

        seen = set()
        deduped = []
        for r in results:
            key = (r.name.lower(), r.size_b, r.quant)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:limit]

    def _search_local(self, keyword: str, limit: int) -> List[SearchResult]:
        results = []
        kw = keyword.lower()
        for name, info in self._local_models.items():
            if kw in name.lower():
                size_b = self._parse_size(name)
                quant = info.quant
                feasible = None
                required_gb = None
                if self._gpu_memory_manager:
                    feasibility = self._gpu_memory_manager.check_model_feasibility(
                        name, size_b=size_b, quant=quant, model_path=info.path,
                    )
                    feasible = feasibility["feasible"]
                    required_gb = feasibility.get("required_gb")
                results.append(SearchResult(
                    name=name, source="local",
                    size_b=size_b, quant=quant,
                    required_gb=required_gb, feasible=feasible,
                    model_id=name, local_path=info.path,
                    architecture=info.architecture,
                ))
        return results[:limit]

    def _search_hf(self, keyword: str, limit: int) -> List[SearchResult]:
        try:
            from huggingface_hub import HfApi
            api = HfApi(endpoint=self._hf_endpoint)
            models = api.list_models(search=keyword, limit=limit, sort="downloads")
            results = []
            for m in models:
                size_b = self._parse_size(m.id)
                quant = self._parse_quant(m.id)
                local_path = self.get_model_local_path(m.id)
                source = "local" if local_path else "huggingface"
                feasible = None
                required_gb = None
                if size_b and self._gpu_memory_manager:
                    feasibility = self._gpu_memory_manager.check_model_feasibility(
                        "", size_b=size_b, quant=quant,
                    )
                    feasible = feasibility["feasible"]
                    required_gb = feasibility.get("required_gb")
                results.append(SearchResult(
                    name=m.id, source=source,
                    size_b=size_b, quant=quant,
                    required_gb=required_gb, feasible=feasible,
                    model_id=m.id, local_path=local_path,
                ))
            return results[:limit]
        except ImportError:
            logger.warning("huggingface_hub not installed, skipping HF search")
            return []
        except Exception as e:
            logger.error("HF search failed: %s", e)
            return []

    def _search_ms(self, keyword: str, limit: int) -> List[SearchResult]:
        try:
            from modelscope.hub.api import HubApi
            api = HubApi()
            models = api.list_models(keyword=keyword, limit=limit)
            results = []
            for m in models:
                name = m.name if hasattr(m, 'name') else str(m)
                size_b = self._parse_size(name)
                quant = self._parse_quant(name)
                local_path = self.get_model_local_path(name)
                source = "local" if local_path else "modelscope"
                feasible = None
                required_gb = None
                if size_b and self._gpu_memory_manager:
                    feasibility = self._gpu_memory_manager.check_model_feasibility(
                        "", size_b=size_b, quant=quant,
                    )
                    feasible = feasibility["feasible"]
                    required_gb = feasibility.get("required_gb")
                results.append(SearchResult(
                    name=name, source=source,
                    size_b=size_b, quant=quant,
                    required_gb=required_gb, feasible=feasible,
                    model_id=name, local_path=local_path,
                ))
            return results[:limit]
        except ImportError:
            logger.warning("modelscope not installed, skipping MS search")
            return []
        except Exception as e:
            logger.error("MS search failed: %s", e)
            return []

    def download_model(
        self, model_name: str, source: str = "hf",
        save_dir: Optional[str] = None,
    ) -> Dict:
        local_path = self.get_model_local_path(model_name)
        if local_path:
            return {"status": "already_exists", "local_path": local_path, "source": "local"}

        target_dir = save_dir or os.path.join(self._save_root, model_name.split("/")[-1])

        if source in ("huggingface", "hf"):
            return self._download_hf(model_name, target_dir)
        elif source in ("modelscope", "ms"):
            return self._download_ms(model_name, target_dir)
        return {"status": "error", "message": f"Unknown source: {source}"}

    def _download_hf(self, model_name: str, target_dir: str) -> Dict:
        try:
            from huggingface_hub import snapshot_download
            local_path = snapshot_download(
                repo_id=model_name,
                local_dir=target_dir,
                resume_download=True,
                endpoint=self._hf_endpoint,
            )
            self._register_downloaded_model(model_name, local_path)
            return {"status": "completed", "local_path": local_path, "source": "huggingface"}
        except Exception as e:
            logger.error("HF download failed: %s", e)
            return {"status": "error", "message": str(e), "source": "huggingface"}

    def _download_ms(self, model_name: str, target_dir: str) -> Dict:
        try:
            from modelscope.hub.snapshot_download import snapshot_download as ms_download
            local_path = ms_download(model_id=model_name, cache_dir=target_dir)
            self._register_downloaded_model(model_name, local_path)
            return {"status": "completed", "local_path": local_path, "source": "modelscope"}
        except Exception as e:
            logger.error("MS download failed: %s", e)
            return {"status": "error", "message": str(e), "source": "modelscope"}

    def _register_downloaded_model(self, model_name: str, local_path: str):
        short_name = model_name.split('/')[-1]
        info = self._analyze_local_model(short_name, local_path)
        if info:
            self._local_models[short_name] = info
        logger.info("Registered downloaded model: %s at %s", model_name, local_path)

    def get_model_info(self, model_name: str) -> Optional[Dict]:
        short_name = model_name.split('/')[-1]
        if short_name in self._local_models:
            info = self._local_models[short_name]
            return {
                "name": short_name,
                "path": info.path,
                "size_gb": round(info.size_gb, 2),
                "quant": info.quant,
                "architecture": info.architecture,
                "config_exists": info.config_exists,
                "source": "local",
            }
        return None

    def get_source_info(self) -> Dict:
        self.initialize()
        return {
            "local_models_count": len(self._local_models),
            "save_root": self._save_root,
            "hf_endpoint": self._hf_endpoint,
            "sources": _SOURCE_PRIORITY,
            "initialized": self._initialized,
        }

    def refresh_local_models(self) -> int:
        self._local_models.clear()
        self._scan_local_models()
        logger.info("Refreshed local models, found %d", len(self._local_models))
        return len(self._local_models)

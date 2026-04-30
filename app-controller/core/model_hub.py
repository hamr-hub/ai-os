import re
import os
import json
import logging
import hashlib
import time
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("ai_controller.model_hub")

_HF_ENDPOINT_DEFAULT = "https://hf-mirror.com"

_SOURCE_PRIORITY = ["local", "huggingface", "modelscope", "openxlab"]

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
        self._hf_token: Optional[str] = None
        self._ms_token: Optional[str] = None
        self._save_root = "/mnt/pve_models"
        self._max_workers = 8
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
                    self._hf_token = hub_cfg.get("hf_token", self._hf_token)
                    self._ms_token = hub_cfg.get("ms_token", self._ms_token)
                    self._max_workers = hub_cfg.get("max_workers", self._max_workers)

        hf_env_token = os.environ.get("HF_TOKEN") or os.environ.get("hf_token")
        if hf_env_token:
            if not self._hf_token:
                self._hf_token = hf_env_token
        ms_env_token = os.environ.get("MS_TOKEN") or os.environ.get("ms_token")
        if ms_env_token:
            if not self._ms_token:
                self._ms_token = ms_env_token

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

    def search_models(self, keyword: str, source: str = "all", limit: int = 10, sort: Optional[str] = None) -> List[SearchResult]:
        self.initialize()
        results = []
        if source in ("local", "all"):
            results.extend(self._search_local(keyword, limit))
        if source in ("huggingface", "hf", "all"):
            results.extend(self._search_hf(keyword, limit))
        if source in ("modelscope", "ms", "all"):
            results.extend(self._search_ms(keyword, limit))
        if source in ("openxlab", "oxl", "all"):
            results.extend(self._search_oxl(keyword, limit))

        seen = set()
        deduped = []
        for r in results:
            key = (r.name.lower(), r.size_b, r.quant)
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        if sort:
            deduped = self._sort_results(deduped, sort)

        return deduped[:limit]

    _SORT_FIELDS = {
        "size": "size_b",
        "quant": "quant",
        "required_gb": "required_gb",
        "feasible": "feasible",
        "downloads": "downloads",
        "name": "name",
    }

    def _sort_results(self, results: List[SearchResult], sort: str) -> List[SearchResult]:
        desc = False
        field_name = sort
        if sort.startswith("-"):
            desc = True
            field_name = sort[1:]
        attr = self._SORT_FIELDS.get(field_name, field_name)
        def _key(r: SearchResult):
            v = getattr(r, attr, None)
            if v is None:
                if attr == "feasible":
                    return 0
                if attr in ("size_b", "required_gb", "downloads"):
                    return float('inf') if not desc else -1
                return ""
            if isinstance(v, bool):
                return 1 if v else 0
            return v
        return sorted(results, key=_key, reverse=desc)

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

    def _search_hf(self, keyword: str, limit: int, hf_token: Optional[str] = None) -> List[SearchResult]:
        try:
            from huggingface_hub import HfApi
            token = hf_token or self._hf_token
            api = HfApi(endpoint=self._hf_endpoint, token=token)
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

    def _search_oxl(self, keyword: str, limit: int) -> List[SearchResult]:
        try:
            import urllib.request
            import urllib.parse
            url = f"https://openxlab.org.cn/api/v1/models?keyword={urllib.parse.quote(keyword)}&limit={limit}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            results = []
            models = data.get("data", data.get("models", []))
            if isinstance(models, list):
                for m in models:
                    name = m.get("name", m.get("model_name", ""))
                    model_id = m.get("id", name)
                    size_b = None
                    if m.get("size"):
                        size_b = float(m["size"])
                    quant = self._parse_quant(name)
                    local_path = self.get_model_local_path(name)
                    source = "local" if local_path else "openxlab"
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
                        model_id=model_id, local_path=local_path,
                        description=m.get("description"),
                        downloads=m.get("downloads"),
                    ))
            return results[:limit]
        except Exception as e:
            logger.error("OXL search failed: %s", e)
            return []

    def _download_oxl(self, model_name: str, target_dir: str) -> Dict:
        try:
            import urllib.request
            url = f"https://openxlab.org.cn/api/v1/models/{model_name}/download"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            download_url = data.get("download_url", data.get("url", ""))
            if not download_url:
                return {"status": "error", "message": "No download URL found", "source": "openxlab"}
            os.makedirs(target_dir, exist_ok=True)
            import subprocess
            cmd = ["git", "clone", download_url, target_dir]
            if os.path.exists(target_dir):
                cmd = ["git", "pull", "--rebase"]
                result = subprocess.run(cmd, cwd=target_dir, capture_output=True, text=True, timeout=300)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                return {"status": "error", "message": result.stderr[:200], "source": "openxlab"}
            self._register_downloaded_model(model_name, target_dir)
            return {"status": "completed", "local_path": target_dir, "source": "openxlab"}
        except Exception as e:
            logger.error("OXL download failed: %s", e)
            return {"status": "error", "message": str(e), "source": "openxlab"}

    def download_model(
        self, model_name: str, source: str = "hf",
        save_dir: Optional[str] = None,
        hf_token: Optional[str] = None,
        ms_token: Optional[str] = None,
        allow_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        max_workers: Optional[int] = None,
        force_download: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        local_path = self.get_model_local_path(model_name)
        if local_path and not force_download:
            return {"status": "already_exists", "local_path": local_path, "source": "local"}

        target_dir = save_dir or os.path.join(self._save_root, model_name.split("/")[-1])
        effective_hf_token = hf_token or self._hf_token
        effective_ms_token = ms_token or self._ms_token
        workers = max_workers or self._max_workers
        allow = allow_patterns
        ignore = ignore_patterns

        if source in ("huggingface", "hf"):
            return self._download_hf(model_name, target_dir, effective_hf_token, allow, ignore, workers, force_download, progress_callback)
        elif source in ("modelscope", "ms"):
            return self._download_ms(model_name, target_dir, effective_ms_token, allow, ignore, workers, resume_download=True, progress_callback=progress_callback)
        elif source in ("openxlab", "oxl"):
            return self._download_oxl(model_name, target_dir)
        return {"status": "error", "message": f"Unknown source: {source}"}

    def _download_hf(
        self, model_name: str, target_dir: str,
        hf_token: Optional[str] = None,
        allow_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        max_workers: int = 8,
        force_download: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        try:
            from huggingface_hub import snapshot_download

            tqdm_class = None
            if progress_callback:
                try:
                    from tqdm import tqdm

                    class ProgressTqdm(tqdm):
                        def update(self, n=1):
                            result = super().update(n)
                            if progress_callback and self.total and self.total > 0:
                                pct = min(100.0, (self.n / self.total) * 100)
                                progress_callback(pct)
                            return result

                    tqdm_class = ProgressTqdm
                except ImportError:
                    pass

            kwargs = {
                "repo_id": model_name,
                "local_dir": target_dir,
                "resume_download": True,
                "endpoint": self._hf_endpoint,
                "max_workers": max_workers,
                "force_download": force_download,
            }
            if hf_token:
                kwargs["token"] = hf_token
            if allow_patterns:
                kwargs["allow_patterns"] = allow_patterns
            if ignore_patterns:
                kwargs["ignore_patterns"] = ignore_patterns
            if tqdm_class:
                kwargs["tqdm_class"] = tqdm_class
            local_path = snapshot_download(**kwargs)
            self._register_downloaded_model(model_name, local_path)
            return {"status": "completed", "local_path": local_path, "source": "huggingface"}
        except Exception as e:
            logger.error("HF download failed: %s", e)
            return {"status": "error", "message": str(e), "source": "huggingface"}

    def _download_ms(
        self, model_name: str, target_dir: str,
        ms_token: Optional[str] = None,
        allow_patterns: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        max_workers: int = 8,
        resume_download: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        try:
            from modelscope.hub.snapshot_download import snapshot_download as ms_download
            kwargs = {
                "model_id": model_name,
                "local_dir": target_dir,
                "max_workers": max_workers,
                "resume_download": resume_download,
            }
            if ms_token:
                kwargs["cookies"] = {"token": ms_token}
            if allow_patterns:
                kwargs["allow_patterns"] = allow_patterns
            if ignore_patterns:
                kwargs["ignore_patterns"] = ignore_patterns
            local_path = ms_download(**kwargs)
            if progress_callback:
                progress_callback(100.0)
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

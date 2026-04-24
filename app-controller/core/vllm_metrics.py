import re
import httpx
from datetime import datetime
from typing import Dict, Optional


class VLLMMetricsScraper:
    VLLM_METRIC_KEYS = {
        "vllm:num_requests_running": "running_requests",
        "vllm:num_requests_waiting": "waiting_requests",
        "vllm:gpu_cache_usage_perc": "gpu_cache_usage",
        "vllm:cpu_cache_usage_perc": "cpu_cache_usage",
        "vllm:avg_generation_throughput": "generation_throughput",
        "vllm:avg_prompt_throughput": "prompt_throughput",
        "vllm:iteration_tokens_total": "iteration_tokens_total",
        "vllm:num_batched_tokens": "batched_tokens",
        "vllm:max_num_seqs": "max_num_seqs",
        "vllm:max_model_len": "max_model_len",
        "vllm:gpu_prefix_cache_hit_rate_perc": "prefix_cache_hit_rate",
    }

    HISTOGRAM_SUM_KEYS = {
        "vllm:time_to_first_token_seconds": "time_to_first_token",
        "vllm:time_per_output_token_seconds": "time_per_output_token",
        "vllm:e2e_request_latency_seconds": "e2e_request_latency",
    }

    def __init__(self, vllm_port: int = 8000):
        self._vllm_port = vllm_port
        self._metrics_cache: Optional[Dict] = None
        self._cache_time: Optional[datetime] = None
        self._cache_interval = 5.0

    async def scrape_metrics(self) -> Dict:
        url = f"http://localhost:{self._vllm_port}/metrics"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return {}
                return self._parse_prometheus_text(resp.text)
        except Exception:
            return {}

    def _parse_prometheus_text(self, text: str) -> Dict:
        gauge_values = {}
        histogram_sums = {}

        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for metric_key, alias in self.VLLM_METRIC_KEYS.items():
                if line.startswith(metric_key + " ") or line.startswith(metric_key + "{"):
                    match = re.search(r'=([\d.eE+-]+)', line)
                    if match:
                        try:
                            gauge_values[alias] = float(match.group(1))
                        except ValueError:
                            pass
                    elif line.startswith(metric_key + " ") and not "{" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                gauge_values[alias] = float(parts[1])
                            except ValueError:
                                pass

            for metric_key, alias in self.HISTOGRAM_SUM_KEYS.items():
                sum_line = metric_key + "_sum"
                if line.startswith(sum_line + " ") or line.startswith(sum_line + "{"):
                    match = re.search(r'=([\d.eE+-]+)', line)
                    if match:
                        try:
                            histogram_sums[alias] = float(match.group(1))
                        except ValueError:
                            pass
                    elif line.startswith(sum_line + " ") and not "{" in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                histogram_sums[alias] = float(parts[1])
                            except ValueError:
                                pass

        result = {}
        for alias in self.VLLM_METRIC_KEYS.values():
            result[alias] = gauge_values.get(alias, 0)

        for alias in self.HISTOGRAM_SUM_KEYS.values():
            result[alias] = histogram_sums.get(alias, 0)

        result["vllm_available"] = len(gauge_values) > 0 or len(histogram_sums) > 0
        result["scraped_at"] = datetime.now().isoformat()

        return result

    def get_cached_metrics(self) -> Optional[Dict]:
        if self._metrics_cache is not None:
            return self._metrics_cache
        return None

    async def scrape_and_cache(self) -> Dict:
        metrics = await self.scrape_metrics()
        if metrics:
            self._metrics_cache = metrics
            self._cache_time = datetime.now()
        return metrics

    def get_default_metrics(self) -> Dict:
        defaults = {}
        for alias in self.VLLM_METRIC_KEYS.values():
            defaults[alias] = 0
        for alias in self.HISTOGRAM_SUM_KEYS.values():
            defaults[alias] = 0
        defaults["vllm_available"] = False
        defaults["scraped_at"] = ""
        return defaults

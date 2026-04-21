import asyncio
import httpx
import json
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from .logger import setup_logger

logger = setup_logger()

class TestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

class FeatureType(Enum):
    IMAGE = "image"
    TOOLS = "tools"
    CHAT = "chat"

@dataclass
class TestResult:
    test_name: str
    feature_type: FeatureType
    status: TestStatus
    duration: float
    metrics: Dict[str, Any]
    error: Optional[str] = None
    details: Optional[str] = None

@dataclass
class ModelTestReport:
    model_name: str
    test_timestamp: str
    overall_status: str
    feature_support: Dict[str, bool]
    performance_metrics: Dict[str, Any]
    resource_utilization: Dict[str, Any]
    test_results: List[TestResult]
    errors: List[str]
    warnings: List[str]

class ModelTestingFramework:
    def __init__(self, scheduler, gpu_monitor):
        self.scheduler = scheduler
        self.gpu_monitor = gpu_monitor
        self._test_lock = asyncio.Lock()
        self._test_in_progress = False
        self._previous_reports: Dict[str, ModelTestReport] = {}
        
        self.STANDARD_TEST_PROMPT = "Hello! Please respond with a brief greeting message in English."
        self.STANDARD_TOOL_PROMPT = "What is the current weather in Beijing? Use the weather tool if available."
        self.STANDARD_IMAGE_PROMPT = "Describe the content of this image in detail."
        
        self.TEST_TIMEOUT = 60
        self.WARMUP_DELAY = 5
        self.MIN_TOKENS_FOR_TPS = 50

    async def run_tests(self, model_name: str) -> ModelTestReport:
        async with self._test_lock:
            if self._test_in_progress:
                logger.warning(f"Test already in progress, skipping {model_name}")
                return ModelTestReport(
                    model_name=model_name,
                    test_timestamp=datetime.now().isoformat(),
                    overall_status="skipped",
                    feature_support={},
                    performance_metrics={},
                    resource_utilization={},
                    test_results=[],
                    errors=["Test already in progress"],
                    warnings=[]
                )
            
            self._test_in_progress = True
            try:
                return await self._execute_tests(model_name)
            finally:
                self._test_in_progress = False

    async def _execute_tests(self, model_name: str) -> ModelTestReport:
        start_time = datetime.now()
        test_results: List[TestResult] = []
        errors: List[str] = []
        warnings: List[str] = []
        feature_support: Dict[str, bool] = {}
        
        logger.info(f"Starting comprehensive tests for model: {model_name}")
        
        if not self.scheduler.is_model_available(model_name):
            errors.append(f"Model {model_name} is not available")
            return ModelTestReport(
                model_name=model_name,
                test_timestamp=start_time.isoformat(),
                overall_status="failed",
                feature_support={},
                performance_metrics={},
                resource_utilization={},
                test_results=[],
                errors=errors,
                warnings=[]
            )
        
        if not self.scheduler.is_model_running(model_name):
            logger.info(f"Model {model_name} not running, starting...")
            success = await self.scheduler.start_model(model_name)
            if not success:
                errors.append(f"Failed to start model {model_name}")
                return ModelTestReport(
                    model_name=model_name,
                    test_timestamp=start_time.isoformat(),
                    overall_status="failed",
                    feature_support={},
                    performance_metrics={},
                    resource_utilization={},
                    test_results=[],
                    errors=errors,
                    warnings=[]
                )
            await asyncio.sleep(self.WARMUP_DELAY)
        
        resource_start = self._get_system_resources()
        
        test_results.append(await self._test_chat_basic(model_name))
        test_results.append(await self._test_chat_streaming(model_name))
        test_results.append(await self._test_tool_integration(model_name))
        
        supports_images = self.scheduler.get_model_supports_images(model_name)
        if supports_images:
            test_results.append(await self._test_image_processing(model_name))
        else:
            test_results.append(self._create_skipped_test("image_processing", FeatureType.IMAGE, "Model does not support images"))
        
        feature_support = {
            "image": supports_images and any(
                r.status == TestStatus.PASSED for r in test_results 
                if r.feature_type == FeatureType.IMAGE
            ),
            "tools": any(r.status == TestStatus.PASSED for r in test_results if r.feature_type == FeatureType.TOOLS),
            "chat": any(r.status == TestStatus.PASSED for r in test_results if r.feature_type == FeatureType.CHAT)
        }
        
        resource_end = self._get_system_resources()
        resource_utilization = self._calculate_resource_utilization(resource_start, resource_end)
        
        performance_metrics = self._calculate_performance_metrics(test_results)
        
        overall_status = self._determine_overall_status(test_results, errors)
        
        if any(r.status == TestStatus.FAILED for r in test_results):
            warnings.append("Some tests failed, check details")
        
        report = ModelTestReport(
            model_name=model_name,
            test_timestamp=start_time.isoformat(),
            overall_status=overall_status,
            feature_support=feature_support,
            performance_metrics=performance_metrics,
            resource_utilization=resource_utilization,
            test_results=test_results,
            errors=errors,
            warnings=warnings
        )
        
        self._previous_reports[model_name] = report
        
        logger.info(f"Tests completed for {model_name}: {overall_status}")
        return report

    async def _test_chat_basic(self, model_name: str) -> TestResult:
        start_time = time.time()
        test_name = "chat_basic"
        
        try:
            port = self.scheduler.get_model_port(model_name)
            url = f"http://localhost:{port}/v1/chat/completions"
            
            async with httpx.AsyncClient(timeout=self.TEST_TIMEOUT) as client:
                response = await client.post(
                    url,
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": self.STANDARD_TEST_PROMPT}],
                        "max_tokens": 50,
                        "temperature": 0.7
                    }
                )
                response.raise_for_status()
                result = response.json()
            
            duration = time.time() - start_time
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            token_count = result.get("usage", {}).get("completion_tokens", 0)
            tps = token_count / duration if duration > 0 else 0
            
            if not content.strip():
                return TestResult(
                    test_name=test_name,
                    feature_type=FeatureType.CHAT,
                    status=TestStatus.FAILED,
                    duration=duration,
                    metrics={"tps": tps, "token_count": token_count},
                    error="Empty response content"
                )
            
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.CHAT,
                status=TestStatus.PASSED,
                duration=duration,
                metrics={"tps": tps, "token_count": token_count, "response_length": len(content)}
            )
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.CHAT,
                status=TestStatus.FAILED,
                duration=duration,
                metrics={},
                error=str(e)
            )

    async def _test_chat_streaming(self, model_name: str) -> TestResult:
        start_time = time.time()
        test_name = "chat_streaming"
        
        try:
            port = self.scheduler.get_model_port(model_name)
            url = f"http://localhost:{port}/v1/chat/completions"
            
            async with httpx.AsyncClient(timeout=self.TEST_TIMEOUT) as client:
                response = await client.post(
                    url,
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": self.STANDARD_TEST_PROMPT}],
                        "max_tokens": 50,
                        "temperature": 0.7,
                        "stream": True
                    },
                    timeout=self.TEST_TIMEOUT
                )
                response.raise_for_status()
                
                content = ""
                token_count = 0
                chunks_received = 0
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk_data = line[6:]
                        if chunk_data == "[DONE]":
                            break
                        try:
                            json_chunk = json.loads(chunk_data)
                            delta = json_chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                content += delta["content"]
                                token_count += 1
                            chunks_received += 1
                        except:
                            pass
            
            duration = time.time() - start_time
            tps = token_count / duration if duration > 0 else 0
            
            if chunks_received == 0:
                return TestResult(
                    test_name=test_name,
                    feature_type=FeatureType.CHAT,
                    status=TestStatus.FAILED,
                    duration=duration,
                    metrics={"tps": tps, "chunks_received": chunks_received},
                    error="No streaming chunks received"
                )
            
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.CHAT,
                status=TestStatus.PASSED,
                duration=duration,
                metrics={"tps": tps, "token_count": token_count, "chunks_received": chunks_received, "response_length": len(content)}
            )
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.CHAT,
                status=TestStatus.FAILED,
                duration=duration,
                metrics={},
                error=str(e)
            )

    async def _test_tool_integration(self, model_name: str) -> TestResult:
        start_time = time.time()
        test_name = "tool_integration"
        
        try:
            port = self.scheduler.get_model_port(model_name)
            url = f"http://localhost:{port}/v1/chat/completions"
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get the current weather for a location",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string", "description": "The city name"}
                            },
                            "required": ["location"]
                        }
                    }
                }
            ]
            
            async with httpx.AsyncClient(timeout=self.TEST_TIMEOUT) as client:
                response = await client.post(
                    url,
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": self.STANDARD_TOOL_PROMPT}],
                        "tools": tools,
                        "tool_choice": "auto",
                        "max_tokens": 100
                    }
                )
                response.raise_for_status()
                result = response.json()
            
            duration = time.time() - start_time
            message = result.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            if tool_calls:
                return TestResult(
                    test_name=test_name,
                    feature_type=FeatureType.TOOLS,
                    status=TestStatus.PASSED,
                    duration=duration,
                    metrics={"tool_calls_count": len(tool_calls), "tool_name": tool_calls[0].get("function", {}).get("name")}
                )
            else:
                return TestResult(
                    test_name=test_name,
                    feature_type=FeatureType.TOOLS,
                    status=TestStatus.PASSED,
                    duration=duration,
                    metrics={"tool_calls_count": 0},
                    details="Model responded without tool call (valid behavior)"
                )
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.TOOLS,
                status=TestStatus.FAILED,
                duration=duration,
                metrics={},
                error=str(e)
            )

    async def _test_image_processing(self, model_name: str) -> TestResult:
        start_time = time.time()
        test_name = "image_processing"
        
        try:
            test_image_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            
            port = self.scheduler.get_model_port(model_name)
            url = f"http://localhost:{port}/v1/chat/completions"
            
            async with httpx.AsyncClient(timeout=self.TEST_TIMEOUT) as client:
                response = await client.post(
                    url,
                    json={
                        "model": model_name,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": self.STANDARD_IMAGE_PROMPT},
                                {"type": "image_url", "image_url": {"url": test_image_base64}}
                            ]
                        }],
                        "max_tokens": 100,
                        "temperature": 0.7
                    }
                )
                response.raise_for_status()
                result = response.json()
            
            duration = time.time() - start_time
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            token_count = result.get("usage", {}).get("completion_tokens", 0)
            tps = token_count / duration if duration > 0 else 0
            
            if not content.strip():
                return TestResult(
                    test_name=test_name,
                    feature_type=FeatureType.IMAGE,
                    status=TestStatus.FAILED,
                    duration=duration,
                    metrics={"tps": tps, "token_count": token_count},
                    error="Empty response content for image prompt"
                )
            
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.IMAGE,
                status=TestStatus.PASSED,
                duration=duration,
                metrics={"tps": tps, "token_count": token_count, "response_length": len(content)}
            )
        
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                test_name=test_name,
                feature_type=FeatureType.IMAGE,
                status=TestStatus.FAILED,
                duration=duration,
                metrics={},
                error=str(e)
            )

    def _create_skipped_test(self, test_name: str, feature_type: FeatureType, reason: str) -> TestResult:
        return TestResult(
            test_name=test_name,
            feature_type=feature_type,
            status=TestStatus.SKIPPED,
            duration=0.0,
            metrics={},
            details=f"Skipped: {reason}"
        )

    def _get_system_resources(self) -> Dict[str, Any]:
        gpu_status = self.gpu_monitor.get_gpu_status()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": cpu_percent,
                "cores": psutil.cpu_count()
            },
            "memory": {
                "total_mb": memory.total // (1024 ** 2),
                "available_mb": memory.available // (1024 ** 2),
                "used_mb": memory.used // (1024 ** 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": disk.total // (1024 ** 3),
                "used_gb": disk.used // (1024 ** 3),
                "free_gb": disk.free // (1024 ** 3),
                "percent": disk.percent
            },
            "gpu": gpu_status if gpu_status else None
        }

    def _calculate_resource_utilization(self, start: Dict, end: Dict) -> Dict[str, Any]:
        return {
            "test_duration_seconds": (datetime.fromisoformat(end["timestamp"]) - datetime.fromisoformat(start["timestamp"])).total_seconds(),
            "cpu": {
                "start_percent": start["cpu"]["percent"],
                "end_percent": end["cpu"]["percent"],
                "avg_percent": (start["cpu"]["percent"] + end["cpu"]["percent"]) / 2
            },
            "memory": {
                "start_used_mb": start["memory"]["used_mb"],
                "end_used_mb": end["memory"]["used_mb"],
                "delta_mb": end["memory"]["used_mb"] - start["memory"]["used_mb"]
            },
            "disk": {
                "start_used_gb": start["disk"]["used_gb"],
                "end_used_gb": end["disk"]["used_gb"],
                "delta_gb": end["disk"]["used_gb"] - start["disk"]["used_gb"]
            },
            "gpu": {
                "available": start["gpu"] is not None,
                "start_utilization": start["gpu"]["utilization"] if start["gpu"] else 0,
                "end_utilization": end["gpu"]["utilization"] if end["gpu"] else 0,
                "start_memory_used_mb": start["gpu"]["used_memory"] // (1024 ** 2) if start["gpu"] else 0,
                "end_memory_used_mb": end["gpu"]["used_memory"] // (1024 ** 2) if end["gpu"] else 0,
                "start_temperature": start["gpu"]["temperature"] if start["gpu"] else 0,
                "end_temperature": end["gpu"]["temperature"] if end["gpu"] else 0
            } if start["gpu"] else {"available": False}
        }

    def _calculate_performance_metrics(self, test_results: List[TestResult]) -> Dict[str, Any]:
        chat_tests = [r for r in test_results if r.feature_type == FeatureType.CHAT and r.status == TestStatus.PASSED]
        image_tests = [r for r in test_results if r.feature_type == FeatureType.IMAGE and r.status == TestStatus.PASSED]
        
        all_tps_values = []
        all_latencies = []
        
        for result in test_results:
            if result.status == TestStatus.PASSED:
                if "tps" in result.metrics:
                    all_tps_values.append(result.metrics["tps"])
                if result.duration > 0:
                    all_latencies.append(result.duration)
        
        return {
            "chat": {
                "tests_passed": len(chat_tests),
                "avg_tps": sum(r.metrics.get("tps", 0) for r in chat_tests) / len(chat_tests) if chat_tests else 0,
                "avg_token_count": sum(r.metrics.get("token_count", 0) for r in chat_tests) / len(chat_tests) if chat_tests else 0,
                "avg_latency": sum(r.duration for r in chat_tests) / len(chat_tests) if chat_tests else 0
            },
            "image": {
                "tests_passed": len(image_tests),
                "avg_tps": sum(r.metrics.get("tps", 0) for r in image_tests) / len(image_tests) if image_tests else 0,
                "avg_latency": sum(r.duration for r in image_tests) / len(image_tests) if image_tests else 0
            },
            "overall": {
                "avg_tps": sum(all_tps_values) / len(all_tps_values) if all_tps_values else 0,
                "avg_latency": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
                "tests_passed": len([r for r in test_results if r.status == TestStatus.PASSED]),
                "tests_total": len(test_results),
                "pass_rate": (len([r for r in test_results if r.status == TestStatus.PASSED]) / len(test_results)) * 100 if test_results else 0
            }
        }

    def _determine_overall_status(self, test_results: List[TestResult], errors: List[str]) -> str:
        if errors:
            return "failed"
        
        passed = sum(1 for r in test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in test_results if r.status == TestStatus.FAILED)
        
        if failed > 0:
            return "degraded"
        elif passed == len(test_results):
            return "passed"
        else:
            return "partial"

    def get_previous_report(self, model_name: str) -> Optional[ModelTestReport]:
        return self._previous_reports.get(model_name)

    def get_all_reports(self) -> Dict[str, ModelTestReport]:
        return self._previous_reports

    def clear_reports(self):
        self._previous_reports.clear()

    async def run_comparative_analysis(self, model_names: Optional[List[str]] = None) -> Dict[str, Any]:
        if model_names is None:
            model_names = self.scheduler.get_available_models()
        
        reports = []
        for model_name in model_names:
            report = await self.run_tests(model_name)
            reports.append(report)
        
        return self._generate_comparative_report(reports)

    def _generate_comparative_report(self, reports: List[ModelTestReport]) -> Dict[str, Any]:
        sorted_by_tps = sorted(reports, key=lambda r: r.performance_metrics["overall"]["avg_tps"], reverse=True)
        sorted_by_pass_rate = sorted(reports, key=lambda r: r.performance_metrics["overall"]["pass_rate"], reverse=True)
        
        best_tps = sorted_by_tps[0] if sorted_by_tps else None
        best_pass_rate = sorted_by_pass_rate[0] if sorted_by_pass_rate else None
        
        comparison = []
        for report in reports:
            comparison.append({
                "model_name": report.model_name,
                "overall_status": report.overall_status,
                "avg_tps": report.performance_metrics["overall"]["avg_tps"],
                "avg_latency": report.performance_metrics["overall"]["avg_latency"],
                "pass_rate": report.performance_metrics["overall"]["pass_rate"],
                "feature_support": report.feature_support,
                "errors_count": len(report.errors),
                "warnings_count": len(report.warnings),
                "resource_usage": {
                    "cpu_avg": report.resource_utilization["cpu"]["avg_percent"],
                    "memory_delta_mb": report.resource_utilization["memory"]["delta_mb"]
                }
            })
        
        return {
            "comparison_timestamp": datetime.now().isoformat(),
            "total_models_tested": len(reports),
            "best_performing": {
                "by_tps": best_tps.model_name if best_tps else None,
                "by_pass_rate": best_pass_rate.model_name if best_pass_rate else None
            },
            "rankings": {
                "by_tps": [r.model_name for r in sorted_by_tps],
                "by_pass_rate": [r.model_name for r in sorted_by_pass_rate]
            },
            "detailed_comparison": comparison,
            "summary": {
                "passed_count": sum(1 for r in reports if r.overall_status == "passed"),
                "degraded_count": sum(1 for r in reports if r.overall_status == "degraded"),
                "failed_count": sum(1 for r in reports if r.overall_status == "failed"),
                "avg_tps_across_models": sum(r.performance_metrics["overall"]["avg_tps"] for r in reports) / len(reports) if reports else 0,
                "avg_pass_rate": sum(r.performance_metrics["overall"]["pass_rate"] for r in reports) / len(reports) if reports else 0
            }
        }
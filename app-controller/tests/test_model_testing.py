import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from core.model_testing import (
    ModelTestingFramework,
    TestStatus,
    FeatureType,
    TestResult,
    ModelTestReport
)

class TestModelTestingFramework:
    @pytest.fixture
    def mock_scheduler(self):
        scheduler = Mock()
        scheduler.is_model_available = Mock(return_value=True)
        scheduler.is_model_running = Mock(return_value=True)
        scheduler.get_model_port = Mock(return_value=8000)
        scheduler.get_model_supports_images = Mock(return_value=False)
        scheduler.start_model = AsyncMock(return_value=True)
        return scheduler
    
    @pytest.fixture
    def mock_gpu_monitor(self):
        gpu_monitor = Mock()
        gpu_monitor.get_gpu_status = Mock(return_value={
            "status": "available",
            "gpu_count": 1,
            "name": "Test GPU",
            "total_memory": 16 * 1024 ** 3,
            "used_memory": 8 * 1024 ** 3,
            "available_memory": 8 * 1024 ** 3,
            "temperature": 60,
            "utilization": 50,
            "power_draw": 100,
            "power_limit": 200,
            "power_percent": 50,
            "fan_speed": 30,
            "clock_sm": 1500,
            "clock_mem": 7000,
            "memory_utilization": 50,
            "primary": {
                "name": "Test GPU",
                "total_memory": 16 * 1024 ** 3,
                "used_memory": 8 * 1024 ** 3,
                "available_memory": 8 * 1024 ** 3,
                "temperature": 60,
                "utilization": 50,
                "power_draw": 100,
                "power_limit": 200,
                "power_percent": 50
            },
            "all_gpus": []
        })
        return gpu_monitor
    
    @pytest.fixture
    def framework(self, mock_scheduler, mock_gpu_monitor):
        return ModelTestingFramework(mock_scheduler, mock_gpu_monitor)
    
    @pytest.mark.asyncio
    async def test_run_tests_model_not_available(self, framework, mock_scheduler):
        mock_scheduler.is_model_available.return_value = False
        
        report = await framework.run_tests("test-model")
        
        assert report.model_name == "test-model"
        assert report.overall_status == "failed"
        assert "Model test-model is not available" in report.errors
    
    @pytest.mark.asyncio
    async def test_run_tests_model_not_running(self, framework, mock_scheduler):
        mock_scheduler.is_model_running.return_value = False
        
        async def mock_aiter_lines():
            yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
            yield 'data: [DONE]'
        
        with patch("core.model_testing.httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Hello!"}}],
                "usage": {"completion_tokens": 5}
            }
            mock_response.raise_for_status = Mock()
            mock_response.aiter_lines = mock_aiter_lines
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            report = await framework.run_tests("test-model")
            
            mock_scheduler.start_model.assert_called_once_with("test-model")
            assert report.overall_status in ["passed", "partial"]
    
    def test_create_skipped_test(self, framework):
        result = framework._create_skipped_test("test_name", FeatureType.CHAT, "Test reason")
        
        assert result.test_name == "test_name"
        assert result.feature_type == FeatureType.CHAT
        assert result.status == TestStatus.SKIPPED
        assert result.duration == 0.0
        assert result.details == "Skipped: Test reason"
    
    def test_get_system_resources(self, framework, mock_gpu_monitor):
        resources = framework._get_system_resources()
        
        assert "timestamp" in resources
        assert "cpu" in resources
        assert "memory" in resources
        assert "disk" in resources
        assert "gpu" in resources
        assert resources["gpu"]["status"] == "available"
    
    def test_calculate_resource_utilization(self, framework):
        start = {
            "timestamp": "2024-01-01T00:00:00",
            "cpu": {"percent": 20, "cores": 8},
            "memory": {"used_mb": 4096, "available_mb": 4096, "total_mb": 8192, "percent": 50},
            "disk": {"used_gb": 50, "free_gb": 50, "total_gb": 100, "percent": 50},
            "gpu": {
                "utilization": 30,
                "used_memory": 4 * 1024 ** 3,
                "temperature": 50
            }
        }
        
        end = {
            "timestamp": "2024-01-01T00:00:10",
            "cpu": {"percent": 60, "cores": 8},
            "memory": {"used_mb": 6144, "available_mb": 2048, "total_mb": 8192, "percent": 75},
            "disk": {"used_gb": 51, "free_gb": 49, "total_gb": 100, "percent": 51},
            "gpu": {
                "utilization": 80,
                "used_memory": 8 * 1024 ** 3,
                "temperature": 70
            }
        }
        
        utilization = framework._calculate_resource_utilization(start, end)
        
        assert utilization["test_duration_seconds"] == 10
        assert utilization["cpu"]["avg_percent"] == 40
        assert utilization["memory"]["delta_mb"] == 2048
        assert utilization["gpu"]["start_utilization"] == 30
        assert utilization["gpu"]["end_utilization"] == 80
    
    def test_calculate_performance_metrics(self, framework):
        test_results = [
            TestResult(
                test_name="chat_basic",
                feature_type=FeatureType.CHAT,
                status=TestStatus.PASSED,
                duration=0.5,
                metrics={"tps": 10, "token_count": 5, "response_length": 20}
            ),
            TestResult(
                test_name="chat_streaming",
                feature_type=FeatureType.CHAT,
                status=TestStatus.PASSED,
                duration=1.0,
                metrics={"tps": 8, "token_count": 8, "chunks_received": 8}
            ),
            TestResult(
                test_name="tool_integration",
                feature_type=FeatureType.TOOLS,
                status=TestStatus.PASSED,
                duration=0.3,
                metrics={"tool_calls_count": 1}
            ),
            TestResult(
                test_name="image_processing",
                feature_type=FeatureType.IMAGE,
                status=TestStatus.SKIPPED,
                duration=0.0,
                metrics={},
                details="Skipped"
            )
        ]
        
        metrics = framework._calculate_performance_metrics(test_results)
        
        assert metrics["chat"]["tests_passed"] == 2
        assert metrics["chat"]["avg_tps"] == 9.0
        assert metrics["chat"]["avg_token_count"] == 6.5
        assert metrics["overall"]["tests_passed"] == 3
        assert metrics["overall"]["tests_total"] == 4
        assert metrics["overall"]["pass_rate"] == 75.0
    
    def test_determine_overall_status(self, framework):
        test_results_passed = [
            TestResult("test1", FeatureType.CHAT, TestStatus.PASSED, 1.0, {}),
            TestResult("test2", FeatureType.TOOLS, TestStatus.PASSED, 1.0, {})
        ]
        assert framework._determine_overall_status(test_results_passed, []) == "passed"
        
        test_results_failed = [
            TestResult("test1", FeatureType.CHAT, TestStatus.FAILED, 1.0, {}, error="Error"),
            TestResult("test2", FeatureType.TOOLS, TestStatus.PASSED, 1.0, {})
        ]
        assert framework._determine_overall_status(test_results_failed, []) == "degraded"
        
        test_results_with_errors = [
            TestResult("test1", FeatureType.CHAT, TestStatus.PASSED, 1.0, {})
        ]
        assert framework._determine_overall_status(test_results_with_errors, ["Fatal error"]) == "failed"
    
    def test_generate_comparative_report(self, framework):
        report1 = ModelTestReport(
            model_name="model1",
            test_timestamp="2024-01-01T00:00:00",
            overall_status="passed",
            feature_support={"chat": True, "tools": True, "image": False},
            performance_metrics={
                "overall": {"avg_tps": 20, "avg_latency": 0.5, "pass_rate": 100}
            },
            resource_utilization={"cpu": {"avg_percent": 50}, "memory": {"delta_mb": 1024}},
            test_results=[],
            errors=[],
            warnings=[]
        )
        
        report2 = ModelTestReport(
            model_name="model2",
            test_timestamp="2024-01-01T00:01:00",
            overall_status="passed",
            feature_support={"chat": True, "tools": False, "image": True},
            performance_metrics={
                "overall": {"avg_tps": 30, "avg_latency": 0.3, "pass_rate": 100}
            },
            resource_utilization={"cpu": {"avg_percent": 60}, "memory": {"delta_mb": 2048}},
            test_results=[],
            errors=[],
            warnings=[]
        )
        
        comparison = framework._generate_comparative_report([report1, report2])
        
        assert comparison["total_models_tested"] == 2
        assert comparison["best_performing"]["by_tps"] == "model2"
        assert comparison["best_performing"]["by_pass_rate"] == "model1"
        assert comparison["rankings"]["by_tps"] == ["model2", "model1"]
        assert len(comparison["detailed_comparison"]) == 2
        assert comparison["summary"]["passed_count"] == 2
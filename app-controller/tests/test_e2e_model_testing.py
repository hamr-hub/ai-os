"""End-to-end tests for the Model Testing Framework"""
import pytest
import asyncio
import httpx
import json
import threading
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


class TestE2EModelTesting:
    """End-to-end tests for model testing framework integration"""

    @pytest.fixture
    def client(self):
        """Create a TestClient with whitelist bypassed"""
        with patch('core.monitor.GPUMonitor.get_gpu_status') as mock_gpu_status:
            mock_gpu_status.return_value = {
                "status": "available",
                "gpu_count": 1,
                "total_memory": 24 * 1024 ** 3,
                "used_memory": 5 * 1024 ** 3,
                "available_memory": 19 * 1024 ** 3,
                "primary": {
                    "total_memory": 24 * 1024 ** 3,
                    "used_memory": 5 * 1024 ** 3,
                    "available_memory": 19 * 1024 ** 3
                },
                "all_gpus": []
            }
            with patch('core.sys_ctl.SystemController.is_service_running') as mock_is_running:
                mock_is_running.return_value = True
                with patch('middleware.admin_whitelist.AdminWhitelistMiddleware._is_allowed_ip', return_value=True):
                    from main import app
                    from fastapi.testclient import TestClient
                    with TestClient(app) as client:
                        yield client

    def _make_mock_report(self, model_name="test-model", overall_status="passed",
                          feature_support=None, performance_metrics=None,
                          resource_utilization=None):
        """Helper to create a mock test report"""
        report = MagicMock()
        report.model_name = model_name
        report.test_timestamp = datetime.now().isoformat()
        report.overall_status = overall_status
        report.feature_support = feature_support or {"chat": True, "tools": True, "image": False}
        report.performance_metrics = performance_metrics or {
            "overall": {"avg_tps": 20.0, "avg_latency": 0.5, "pass_rate": 100.0}
        }
        report.resource_utilization = resource_utilization or {
            "cpu": {"avg_percent": 50},
            "memory": {"delta_mb": 1024},
            "gpu": {"available": True, "end_utilization": 80, "end_temperature": 60}
        }
        report.test_results = []
        report.errors = []
        report.warnings = []
        return report

    def test_switch_and_test_endpoint(self, client):
        """Test the switch and test endpoint"""
        with patch('main.scheduler') as mock_scheduler:
            mock_scheduler.is_model_available.return_value = True
            mock_scheduler.switch_model = AsyncMock(return_value=True)
            mock_scheduler.get_model_port.return_value = 8000
            mock_scheduler.mark_model_selected = MagicMock()

            with patch('main.model_tester') as mock_tester:
                mock_tester.run_tests = AsyncMock(return_value=self._make_mock_report("test-model"))

                response = client.post("/v1/test/model/test-model/switch-and-test")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "completed"
                assert data["message"] == "Successfully switched to test-model and completed tests"
                assert "report" in data
                assert data["report"]["model_name"] == "test-model"
                assert data["report"]["overall_status"] == "passed"

    def test_model_test_endpoint(self, client):
        """Test the model test endpoint"""
        with patch('main.scheduler') as mock_scheduler:
            mock_scheduler.is_model_available.return_value = True
            mock_scheduler.is_model_running.return_value = True
            mock_scheduler.get_model_port.return_value = 8000

            with patch('main.model_tester') as mock_tester:
                mock_tester.run_tests = AsyncMock(return_value=self._make_mock_report(
                    feature_support={"chat": True, "tools": True, "image": True}
                ))

                response = client.post("/v1/test/model/test-model")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "completed"
                assert data["message"] == "Tests completed for test-model"
                assert "report" in data
                assert data["report"]["feature_support"]["image"] == True

    def test_get_report_endpoint(self, client):
        """Test getting a single test report"""
        with patch('main.model_tester') as mock_tester:
            mock_report = self._make_mock_report(
                feature_support={"chat": True, "tools": False, "image": True},
                performance_metrics={"overall": {"avg_tps": 15.0, "avg_latency": 0.6, "pass_rate": 75.0}},
                resource_utilization={}
            )
            mock_report.test_timestamp = "2024-01-01T00:00:00"
            mock_tester.get_previous_report.return_value = mock_report

            response = client.get("/v1/test/report/test-model")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "found"
            assert data["report"]["model_name"] == "test-model"
            assert data["report"]["feature_support"]["tools"] == False

    def test_get_all_reports_endpoint(self, client):
        """Test getting all test reports"""
        with patch('main.model_tester') as mock_tester:
            report1 = self._make_mock_report(model_name="model1")
            report2 = self._make_mock_report(model_name="model2", overall_status="degraded",
                                             feature_support={"chat": True, "tools": False, "image": True},
                                             performance_metrics={"overall": {"avg_tps": 15.0}},
                                             resource_utilization={})

            mock_tester.get_all_reports.return_value = {"model1": report1, "model2": report2}

            response = client.get("/v1/test/reports")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "reports" in data
            assert len(data["reports"]) == 2
            assert "model1" in data["reports"]
            assert "model2" in data["reports"]

    def test_comparative_analysis_endpoint(self, client):
        """Test the comparative analysis endpoint"""
        with patch('main.model_tester') as mock_tester:
            mock_analysis = {
                "comparison_timestamp": datetime.now().isoformat(),
                "total_models_tested": 2,
                "best_performing": {"by_tps": "model2", "by_pass_rate": "model1"},
                "rankings": {"by_tps": ["model2", "model1"], "by_pass_rate": ["model1", "model2"]},
                "detailed_comparison": [
                    {"model_name": "model1", "avg_tps": 20.0, "pass_rate": 100.0},
                    {"model_name": "model2", "avg_tps": 30.0, "pass_rate": 75.0}
                ],
                "summary": {
                    "passed_count": 1,
                    "degraded_count": 1,
                    "failed_count": 0,
                    "avg_tps_across_models": 25.0,
                    "avg_pass_rate": 87.5
                }
            }

            mock_tester.run_comparative_analysis = AsyncMock(return_value=mock_analysis)

            response = client.post("/v1/test/comparative", json={"model_names": ["model1", "model2"]})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["message"] == "Comparative analysis completed"
            assert "analysis" in data
            assert data["analysis"]["total_models_tested"] == 2
            assert data["analysis"]["best_performing"]["by_tps"] == "model2"

    def test_test_status_endpoint(self, client):
        """Test getting test framework status"""
        with patch('main.model_tester') as mock_tester:
            mock_tester.get_all_reports.return_value = {
                "model1": MagicMock(),
                "model2": MagicMock()
            }

            response = client.get("/v1/test/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["models_tested_count"] == 2
            assert "model1" in data["models_tested"]
            assert "model2" in data["models_tested"]

    def test_clear_reports_endpoint(self, client):
        """Test clearing all test reports"""
        with patch('main.model_tester') as mock_tester:
            mock_tester.clear_reports = MagicMock()

            response = client.delete("/v1/test/reports")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["message"] == "All test reports cleared"
            mock_tester.clear_reports.assert_called_once()

    def test_model_not_available_error(self, client):
        """Test error handling when model is not available"""
        with patch('main.scheduler') as mock_scheduler:
            mock_scheduler.is_model_available.return_value = False

            response = client.post("/v1/test/model/unknown-model")

            assert response.status_code == 404
            data = response.json()
            error_message = data.get("detail", "") or data.get("error", "")
            if isinstance(error_message, dict):
                error_message = error_message.get("message", "")
            assert "Model unknown-model not found" in str(error_message)

    def test_switch_and_test_failure(self, client):
        """Test switch and test failure scenario"""
        with patch('main.scheduler') as mock_scheduler:
            mock_scheduler.is_model_available.return_value = True
            mock_scheduler.switch_model = AsyncMock(return_value=False)

            response = client.post("/v1/test/model/test-model/switch-and-test")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["message"] == "Failed to switch to model test-model"

    def test_concurrent_test_protection(self, client):
        """Test that concurrent tests are protected by lock"""
        with patch('main.scheduler') as mock_scheduler:
            mock_scheduler.is_model_available.return_value = True
            mock_scheduler.is_model_running.return_value = True
            mock_scheduler.get_model_port.return_value = 8000

            with patch('main.model_tester') as mock_tester:
                call_count = [0]

                async def mock_run_tests(model_name):
                    call_count[0] += 1
                    return self._make_mock_report(model_name, feature_support={"chat": True})

                mock_tester.run_tests = AsyncMock(side_effect=mock_run_tests)

                responses = []

                def make_request():
                    response = client.post("/v1/test/model/test-model")
                    responses.append(response)

                thread1 = threading.Thread(target=make_request)
                thread2 = threading.Thread(target=make_request)

                thread1.start()
                thread2.start()
                thread1.join()
                thread2.join()

                assert len(responses) == 2
                assert responses[0].status_code == 200
                assert responses[1].status_code == 200

    def test_report_not_found(self, client):
        """Test handling when report is not found"""
        with patch('main.model_tester') as mock_tester:
            mock_tester.get_previous_report.return_value = None

            response = client.get("/v1/test/report/nonexistent-model")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "not_found"
            assert "No test report found" in data["message"]

    def test_no_reports_available(self, client):
        """Test when no reports are available"""
        with patch('main.model_tester') as mock_tester:
            mock_tester.get_all_reports.return_value = {}

            response = client.get("/v1/test/reports")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "no_reports"
            assert "No test reports available" in data["message"]
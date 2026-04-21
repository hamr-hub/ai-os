"""End-to-end tests for the Model Testing Framework"""
import pytest
import asyncio
import httpx
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

class TestE2EModelTesting:
    """End-to-end tests for model testing framework integration"""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app with testing endpoints"""
        from main import app
        return app

    @pytest.mark.asyncio
    async def test_switch_and_test_endpoint(self, mock_app):
        """Test the switch and test endpoint"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.scheduler') as mock_scheduler:
                mock_scheduler.is_model_available.return_value = True
                mock_scheduler.switch_model = AsyncMock(return_value=True)
                mock_scheduler.get_model_port.return_value = 8000
                
                with patch('main.model_tester') as mock_tester:
                    mock_report = MagicMock()
                    mock_report.model_name = "test-model"
                    mock_report.test_timestamp = datetime.now().isoformat()
                    mock_report.overall_status = "passed"
                    mock_report.feature_support = {"chat": True, "tools": True, "image": False}
                    mock_report.performance_metrics = {
                        "overall": {"avg_tps": 20.0, "avg_latency": 0.5, "pass_rate": 100.0}
                    }
                    mock_report.resource_utilization = {
                        "cpu": {"avg_percent": 50},
                        "memory": {"delta_mb": 1024},
                        "gpu": {"available": True, "end_utilization": 80, "end_temperature": 60}
                    }
                    mock_report.test_results = []
                    mock_report.errors = []
                    mock_report.warnings = []
                    
                    mock_tester.run_tests = AsyncMock(return_value=mock_report)
                    
                    response = client.post("/v1/test/model/test-model/switch-and-test")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "completed"
                    assert data["message"] == "Successfully switched to test-model and completed tests"
                    assert "report" in data
                    assert data["report"]["model_name"] == "test-model"
                    assert data["report"]["overall_status"] == "passed"

    @pytest.mark.asyncio
    async def test_model_test_endpoint(self, mock_app):
        """Test the model test endpoint"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.scheduler') as mock_scheduler:
                mock_scheduler.is_model_available.return_value = True
                mock_scheduler.is_model_running.return_value = True
                mock_scheduler.get_model_port.return_value = 8000
                
                with patch('main.model_tester') as mock_tester:
                    mock_report = MagicMock()
                    mock_report.model_name = "test-model"
                    mock_report.test_timestamp = datetime.now().isoformat()
                    mock_report.overall_status = "passed"
                    mock_report.feature_support = {"chat": True, "tools": True, "image": True}
                    mock_report.performance_metrics = {
                        "overall": {"avg_tps": 25.0, "avg_latency": 0.4, "pass_rate": 100.0}
                    }
                    mock_report.resource_utilization = {
                        "cpu": {"avg_percent": 60},
                        "memory": {"delta_mb": 2048},
                        "gpu": {"available": True, "end_utilization": 90, "end_temperature": 70}
                    }
                    mock_report.test_results = []
                    mock_report.errors = []
                    mock_report.warnings = []
                    
                    mock_tester.run_tests = AsyncMock(return_value=mock_report)
                    
                    response = client.post("/v1/test/model/test-model")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "completed"
                    assert data["message"] == "Tests completed for test-model"
                    assert "report" in data
                    assert data["report"]["feature_support"]["image"] == True

    @pytest.mark.asyncio
    async def test_get_report_endpoint(self, mock_app):
        """Test getting a single test report"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.model_tester') as mock_tester:
                mock_report = MagicMock()
                mock_report.model_name = "test-model"
                mock_report.test_timestamp = "2024-01-01T00:00:00"
                mock_report.overall_status = "passed"
                mock_report.feature_support = {"chat": True, "tools": False, "image": True}
                mock_report.performance_metrics = {
                    "overall": {"avg_tps": 15.0, "avg_latency": 0.6, "pass_rate": 75.0}
                }
                mock_report.resource_utilization = {}
                mock_report.test_results = []
                mock_report.errors = []
                mock_report.warnings = []
                
                mock_tester.get_previous_report.return_value = mock_report
                
                response = client.get("/v1/test/report/test-model")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "found"
                assert data["report"]["model_name"] == "test-model"
                assert data["report"]["feature_support"]["tools"] == False

    @pytest.mark.asyncio
    async def test_get_all_reports_endpoint(self, mock_app):
        """Test getting all test reports"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.model_tester') as mock_tester:
                report1 = MagicMock()
                report1.model_name = "model1"
                report1.test_timestamp = "2024-01-01T00:00:00"
                report1.overall_status = "passed"
                report1.feature_support = {"chat": True, "tools": True, "image": False}
                report1.performance_metrics = {"overall": {"avg_tps": 20.0}}
                report1.resource_utilization = {}
                report1.test_results = []
                report1.errors = []
                report1.warnings = []
                
                report2 = MagicMock()
                report2.model_name = "model2"
                report2.test_timestamp = "2024-01-01T00:01:00"
                report2.overall_status = "degraded"
                report2.feature_support = {"chat": True, "tools": False, "image": True}
                report2.performance_metrics = {"overall": {"avg_tps": 15.0}}
                report2.resource_utilization = {}
                report2.test_results = []
                report2.errors = []
                report2.warnings = []
                
                mock_tester.get_all_reports.return_value = {"model1": report1, "model2": report2}
                
                response = client.get("/v1/test/reports")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "reports" in data
                assert len(data["reports"]) == 2
                assert "model1" in data["reports"]
                assert "model2" in data["reports"]

    @pytest.mark.asyncio
    async def test_comparative_analysis_endpoint(self, mock_app):
        """Test the comparative analysis endpoint"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
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

    @pytest.mark.asyncio
    async def test_test_status_endpoint(self, mock_app):
        """Test getting test framework status"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
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

    @pytest.mark.asyncio
    async def test_clear_reports_endpoint(self, mock_app):
        """Test clearing all test reports"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.model_tester') as mock_tester:
                mock_tester.clear_reports = MagicMock()
                
                response = client.delete("/v1/test/reports")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["message"] == "All test reports cleared"
                mock_tester.clear_reports.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_not_available_error(self, mock_app):
        """Test error handling when model is not available"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.scheduler') as mock_scheduler:
                mock_scheduler.is_model_available.return_value = False
                
                response = client.post("/v1/test/model/unknown-model")
                
                assert response.status_code == 404
                data = response.json()
                error_message = data.get("detail", "") or data.get("error", "")
                if isinstance(error_message, dict):
                    error_message = error_message.get("message", "")
                assert "Model unknown-model not found" in str(error_message)

    @pytest.mark.asyncio
    async def test_switch_and_test_failure(self, mock_app):
        """Test switch and test failure scenario"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.scheduler') as mock_scheduler:
                mock_scheduler.is_model_available.return_value = True
                mock_scheduler.switch_model = AsyncMock(return_value=False)
                
                response = client.post("/v1/test/model/test-model/switch-and-test")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "failed"
                assert data["message"] == "Failed to switch to model test-model"

    @pytest.mark.asyncio
    async def test_concurrent_test_protection(self, mock_app):
        """Test that concurrent tests are protected by lock"""
        from fastapi.testclient import TestClient
        import threading
        
        with TestClient(mock_app) as client:
            with patch('main.scheduler') as mock_scheduler:
                mock_scheduler.is_model_available.return_value = True
                mock_scheduler.is_model_running.return_value = True
                mock_scheduler.get_model_port.return_value = 8000
                
                with patch('main.model_tester') as mock_tester:
                    call_count = [0]
                    
                    async def mock_run_tests(model_name):
                        call_count[0] += 1
                        
                        mock_report = MagicMock()
                        mock_report.model_name = model_name
                        mock_report.test_timestamp = datetime.now().isoformat()
                        mock_report.overall_status = "passed"
                        mock_report.feature_support = {"chat": True}
                        mock_report.performance_metrics = {"overall": {"avg_tps": 10.0}}
                        mock_report.resource_utilization = {}
                        mock_report.test_results = []
                        mock_report.errors = []
                        mock_report.warnings = []
                        return mock_report
                    
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

    @pytest.mark.asyncio
    async def test_report_not_found(self, mock_app):
        """Test handling when report is not found"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.model_tester') as mock_tester:
                mock_tester.get_previous_report.return_value = None
                
                response = client.get("/v1/test/report/nonexistent-model")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "not_found"
                assert "No test report found" in data["message"]

    @pytest.mark.asyncio
    async def test_no_reports_available(self, mock_app):
        """Test when no reports are available"""
        from fastapi.testclient import TestClient
        
        with TestClient(mock_app) as client:
            with patch('main.model_tester') as mock_tester:
                mock_tester.get_all_reports.return_value = {}
                
                response = client.get("/v1/test/reports")
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "no_reports"
                assert "No test reports available" in data["message"]
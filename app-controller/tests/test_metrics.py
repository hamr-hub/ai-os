import pytest
from core.metrics import MetricsCollector
from datetime import datetime

class TestMetricsCollector:
    @pytest.fixture
    def metrics(self):
        m = MetricsCollector()
        m.reset()
        return m

    def test_initial_state(self, metrics):
        assert metrics.start_time is not None
        assert len(metrics.request_counts) == 0
        assert len(metrics.error_counts) == 0
        assert len(metrics.response_times) == 0
        assert len(metrics.model_requests) == 0

    def test_record_request(self, metrics):
        metrics.record_request("/v1/chat/completions", 200, 0.5, "gemma-2-9b")
        
        assert metrics.request_counts["/v1/chat/completions"] == 1
        assert "/v1/chat/completions" not in metrics.error_counts
        assert len(metrics.response_times) == 1
        assert metrics.model_requests["gemma-2-9b"] == 1

    def test_record_error(self, metrics):
        metrics.record_request("/v1/chat/completions", 500, 0.5, "gemma-2-9b")
        
        assert metrics.error_counts["/v1/chat/completions"] == 1

    def test_get_metrics(self, metrics):
        metrics.record_request("/v1/chat/completions", 200, 0.5, "gemma-2-9b")
        metrics.record_request("/v1/chat/completions", 200, 1.0, "gemma-2-9b")
        
        result = metrics.get_metrics()
        
        assert "uptime" in result
        assert result["total_requests"] == 2
        assert result["total_errors"] == 0
        assert result["response_time"]["average"] == 0.75
        assert result["response_time"]["max"] == 1.0
        assert result["response_time"]["min"] == 0.5
        assert result["model_requests"]["gemma-2-9b"] == 2

    def test_response_time_limit(self, metrics):
        for i in range(1010):
            metrics.record_request("/test", 200, float(i) / 1000)
        
        assert len(metrics.response_times) == 1000

    def test_health_score(self, metrics):
        assert metrics.get_health_score() == 100.0
        
        metrics.record_request("/test", 200, 0.5)
        metrics.record_request("/test", 500, 0.5)
        
        assert metrics.get_health_score() == 50.0

    def test_reset(self, metrics):
        metrics.record_request("/test", 200, 0.5)
        old_start_time = metrics.start_time
        
        metrics.reset()
        
        assert len(metrics.request_counts) == 0
        assert len(metrics.response_times) == 0
        assert metrics.start_time > old_start_time
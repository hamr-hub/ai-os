import pytest
from unittest.mock import Mock, patch, MagicMock
from core.rate_limiter import RateLimiter
import redis
import json

class TestRateLimiter:
    @pytest.fixture
    def mock_redis(self):
        mock = Mock()
        mock.ping.return_value = True
        mock.incr.return_value = 1
        mock.decr.return_value = 0
        mock.get.return_value = b'1'
        mock.set.return_value = True
        mock.delete.return_value = True
        mock.rpush.return_value = 1
        mock.lpop.return_value = None
        mock.llen.return_value = 0
        mock.keys.return_value = []
        mock.lrem.return_value = 0
        return mock

    def test_connect_failure(self):
        with patch('redis.from_url') as mock_from_url:
            mock_from_url.return_value.ping.side_effect = Exception("Connection failed")
            limiter = RateLimiter()
            assert limiter.client is None

    def test_increment_request(self, mock_redis):
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.increment_request("gemma-2-9b")
        
        assert result == 1
        mock_redis.incr.assert_called_once()

    def test_decrement_request(self, mock_redis):
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.decrement_request("gemma-2-9b")
        
        assert result == 0
        mock_redis.decr.assert_called_once()

    def test_decrement_request_negative(self, mock_redis):
        mock_redis.decr.return_value = -1
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.decrement_request("gemma-2-9b")
        
        assert result == 0
        mock_redis.set.assert_called_once()

    def test_acquire_request_atomic_success(self, mock_redis):
        limiter = RateLimiter()
        limiter.client = mock_redis
        pipe = MagicMock()
        pipe.__enter__.return_value = pipe
        pipe.__exit__.return_value = False
        pipe.get.return_value = b'1'
        mock_redis.pipeline.return_value = pipe

        result = limiter.acquire_request("gemma-2-9b", 4)

        assert result is True
        pipe.watch.assert_called_once()
        pipe.multi.assert_called_once()
        pipe.incr.assert_called_once()
        pipe.execute.assert_called_once()

    def test_acquire_request_atomic_full(self, mock_redis):
        limiter = RateLimiter()
        limiter.client = mock_redis
        pipe = MagicMock()
        pipe.__enter__.return_value = pipe
        pipe.__exit__.return_value = False
        pipe.get.return_value = b'4'
        mock_redis.pipeline.return_value = pipe

        result = limiter.acquire_request("gemma-2-9b", 4)

        assert result is False
        pipe.unwatch.assert_called_once()
        pipe.execute.assert_not_called()

    def test_get_active_requests(self, mock_redis):
        mock_redis.get.return_value = b'5'
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.get_active_requests("gemma-2-9b")
        
        assert result == 5

    def test_is_available(self, mock_redis):
        mock_redis.get.return_value = b'3'
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        assert limiter.is_available("gemma-2-9b", 4) is True
        assert limiter.is_available("gemma-2-9b", 3) is False

    def test_reset_counter(self, mock_redis):
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        limiter.reset_counter("gemma-2-9b")
        
        mock_redis.delete.assert_called_once()

    def test_enqueue_request(self, mock_redis):
        mock_redis.set.return_value = True
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        request_id = limiter.enqueue_request("gemma-2-9b", {"prompt": "test"})
        
        assert len(request_id) > 0
        mock_redis.set.assert_called_once()
        mock_redis.rpush.assert_called_once()

    def test_dequeue_request_empty(self, mock_redis):
        mock_redis.lpop.return_value = None
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.dequeue_request("gemma-2-9b")
        
        assert result is None

    def test_dequeue_request_success(self, mock_redis):
        mock_redis.lpop.side_effect = [b'test-request-id']
        mock_redis.get.return_value = json.dumps({
            "id": "test-request-id",
            "model_name": "gemma-2-9b",
            "data": {"prompt": "test"},
            "priority": "critical",
            "priority_level": 4,
            "enqueued_at": "2024-01-01T00:00:00",
            "status": "queued"
        })
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.dequeue_request("gemma-2-9b")
        
        assert result is not None
        assert result["status"] == "processing"

    def test_get_queue_length(self, mock_redis):
        mock_redis.llen.side_effect = [2, 3, 4, 1]
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.get_queue_length("gemma-2-9b")
        
        assert result == 10

    def test_cancel_request_not_found(self, mock_redis):
        mock_redis.get.return_value = None
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.cancel_request("nonexistent-id")
        
        assert result is False

    def test_cancel_request_queued(self, mock_redis):
        mock_redis.get.return_value = json.dumps({
            "id": "test-id",
            "model_name": "gemma-2-9b",
            "priority": "high",
            "priority_level": 3,
            "status": "queued"
        })
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.cancel_request("test-id")
        
        assert result is True
        mock_redis.lrem.assert_called_once_with('ai_controller:queue:gemma-2-9b:3', 0, 'test-id')

    def test_get_request_status(self, mock_redis):
        mock_redis.get.return_value = json.dumps({
            "id": "test-id",
            "status": "processing"
        })
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.get_request_status("test-id")
        
        assert result is not None
        assert result["status"] == "processing"

    def test_clear_queue(self, mock_redis):
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        limiter.clear_queue("gemma-2-9b")
        
        mock_redis.delete.assert_called_once_with(
            'ai_controller:queue:gemma-2-9b:1',
            'ai_controller:queue:gemma-2-9b:2',
            'ai_controller:queue:gemma-2-9b:3',
            'ai_controller:queue:gemma-2-9b:4'
        )

    def test_get_all_queue_status(self, mock_redis):
        mock_redis.keys.return_value = [
            b'ai_controller:queue:gemma-2-9b:1',
            b'ai_controller:queue:gemma-2-9b:4'
        ]
        mock_redis.llen.side_effect = [1, 2, 0, 0]
        mock_redis.get.return_value = b'2'
        limiter = RateLimiter()
        limiter.client = mock_redis
        
        result = limiter.get_all_queue_status()
        
        assert "gemma-2-9b" in result
        assert result["gemma-2-9b"]["queue_length"] == 3

    def test_no_redis_client(self):
        limiter = RateLimiter()
        limiter.client = None
        
        assert limiter.increment_request("test") == 0
        assert limiter.decrement_request("test") == 0
        assert limiter.get_active_requests("test") == 0
        assert limiter.is_available("test", 1) is True
        assert limiter.acquire_request("test", 1) is False
        assert limiter.enqueue_request("test", {}) == ""
        assert limiter.dequeue_request("test") is None
        assert limiter.cancel_request("test") is False

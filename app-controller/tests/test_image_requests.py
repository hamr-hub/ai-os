import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import base64
import io
from PIL import Image

@pytest.fixture
def client():
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
            
            from main import app
            with TestClient(app) as client:
                yield client

def create_test_image():
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.read()

def encode_image_to_base64(image_bytes):
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"

class TestImageValidation:
    def test_validate_image_success(self, client):
        image_data = create_test_image()
        base64_image = encode_image_to_base64(image_data)
        
        response = client.post(
            "/v1/images/validate",
            json={"image_data": base64_image}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "Image validation successful"
        assert "image_info" in data
        assert data["image_info"]["valid"] == True
        assert data["image_info"]["width"] == 100
        assert data["image_info"]["height"] == 100
        assert data["image_info"]["format"] == "png"

    def test_validate_image_invalid_base64(self, client):
        response = client.post(
            "/v1/images/validate",
            json={"image_data": "invalid-base64-data"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Failed to decode" in data["message"]

    def test_validate_image_empty_data(self, client):
        response = client.post(
            "/v1/images/validate",
            json={"image_data": ""}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False

    def test_validate_image_unsupported_format(self, client):
        img = Image.new('RGB', (100, 100), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='ICO')
        buffer.seek(0)
        base64_image = f"data:image/x-icon;base64,{base64.b64encode(buffer.read()).decode('utf-8')}"
        
        response = client.post(
            "/v1/images/validate",
            json={"image_data": base64_image}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Unsupported image format" in data["message"]

class TestImageUpload:
    def test_upload_image_success(self, client):
        image_data = create_test_image()
        
        response = client.post(
            "/v1/images/upload",
            files={"file": ("test.png", image_data, "image/png")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Image uploaded successfully" in data["message"]
        assert "image_info" in data

    def test_upload_image_too_large(self, client):
        large_img = Image.new('RGB', (10000, 10000), color='red')
        buffer = io.BytesIO()
        large_img.save(buffer, format='PNG')
        buffer.seek(0)
        
        response = client.post(
            "/v1/images/upload",
            files={"file": ("large.png", buffer.read(), "image/png")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Image dimensions exceed maximum allowed size" in data["message"]

    def test_upload_image_invalid_file(self, client):
        response = client.post(
            "/v1/images/upload",
            files={"file": ("invalid.txt", b"not an image", "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "Invalid image data" in data["message"]

class TestChatCompletionsWithImages:
    def test_chat_completions_with_image(self, client):
        image_data = create_test_image()
        base64_image = encode_image_to_base64(image_data)
        
        with patch('core.scheduler.Scheduler.is_model_available') as mock_available:
            mock_available.return_value = True
            
            with patch('core.scheduler.Scheduler.acquire_request') as mock_acquire:
                mock_acquire.return_value = True
                
                with patch('core.scheduler.Scheduler.is_model_running') as mock_running:
                    mock_running.return_value = True
                    
                    with patch('httpx.AsyncClient') as mock_client:
                        mock_response = Mock()
                        mock_response.raise_for_status = Mock()
                        mock_response.json = Mock(return_value={
                            "id": "test-id",
                            "object": "chat.completion",
                            "created": 0,
                            "model": "gemma-4-31b",
                            "choices": [{"message": {"role": "assistant", "content": "This is a red image"}}]
                        })
                        
                        mock_post = AsyncMock(return_value=mock_response)
                        mock_client.return_value.__aenter__.return_value.post = mock_post
                        
                        response = client.post(
                            "/v1/chat/completions",
                            json={
                                "model": "gemma-4-31b",
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "What's in this image?"},
                                            {"type": "image_url", "image_url": {"url": base64_image}}
                                        ]
                                    }
                                ]
                            }
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert "id" in data
                        assert data["choices"][0]["message"]["content"] == "This is a red image"

    def test_chat_completions_with_multiple_images(self, client):
        image_data1 = create_test_image()
        image_data2 = create_test_image()
        base64_image1 = encode_image_to_base64(image_data1)
        base64_image2 = encode_image_to_base64(image_data2)
        
        with patch('core.scheduler.Scheduler.is_model_available') as mock_available:
            mock_available.return_value = True
            
            with patch('core.scheduler.Scheduler.acquire_request') as mock_acquire:
                mock_acquire.return_value = True
                
                with patch('core.scheduler.Scheduler.is_model_running') as mock_running:
                    mock_running.return_value = True
                    
                    with patch('httpx.AsyncClient') as mock_client:
                        mock_response = Mock()
                        mock_response.raise_for_status = Mock()
                        mock_response.json = Mock(return_value={
                            "id": "test-id",
                            "object": "chat.completion",
                            "created": 0,
                            "model": "gemma-4-31b",
                            "choices": [{"message": {"role": "assistant", "content": "Two red images"}}]
                        })
                        
                        mock_post = AsyncMock(return_value=mock_response)
                        mock_client.return_value.__aenter__.return_value.post = mock_post
                        
                        response = client.post(
                            "/v1/chat/completions",
                            json={
                                "model": "gemma-4-31b",
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "Compare these images:"},
                                            {"type": "image_url", "image_url": {"url": base64_image1}},
                                            {"type": "image_url", "image_url": {"url": base64_image2}}
                                        ]
                                    }
                                ]
                            }
                        )
                        
                        assert response.status_code == 200

    def test_chat_completions_with_invalid_image(self, client):
        with patch('core.scheduler.Scheduler.is_model_available') as mock_available:
            mock_available.return_value = True
            
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gemma-4-31b",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What's in this image?"},
                                {"type": "image_url", "image_url": {"url": "data:image/png;base64,invalid-base64"}}
                            ]
                        }
                    ]
                }
            )
            
            assert response.status_code == 422

class TestImageInfo:
    def test_get_image_info(self, client):
        response = client.get("/v1/images/info")
        
        assert response.status_code == 200
        data = response.json()
        assert "max_size_mb" in data
        assert "supported_formats" in data
        assert "endpoints" in data
        assert data["max_size_mb"] == 10
        assert "png" in data["supported_formats"]
        assert "jpg" in data["supported_formats"]
        assert "jpeg" in data["supported_formats"]

class TestImageMetrics:
    def test_image_request_metrics_recorded(self, client):
        image_data = create_test_image()
        base64_image = encode_image_to_base64(image_data)
        
        with patch('core.scheduler.Scheduler.is_model_available') as mock_available:
            mock_available.return_value = True
            
            with patch('core.scheduler.Scheduler.acquire_request') as mock_acquire:
                mock_acquire.return_value = True
                
                with patch('core.scheduler.Scheduler.is_model_running') as mock_running:
                    mock_running.return_value = True
                    
                    with patch('httpx.AsyncClient') as mock_client:
                        mock_response = Mock()
                        mock_response.raise_for_status = Mock()
                        mock_response.json = Mock(return_value={
                            "id": "test-id",
                            "object": "chat.completion",
                            "created": 0,
                            "model": "gemma-4-31b",
                            "choices": [{"message": {"role": "assistant", "content": "OK"}}]
                        })
                        
                        mock_post = AsyncMock(return_value=mock_response)
                        mock_client.return_value.__aenter__.return_value.post = mock_post
                        
                        client.post(
                            "/v1/chat/completions",
                            json={
                                "model": "gemma-4-31b",
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "What's this?"},
                                            {"type": "image_url", "image_url": {"url": base64_image}}
                                        ]
                                    }
                                ]
                            }
                        )
        
        response = client.get("/manage/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "image_requests" in data
        assert data["image_requests"]["total"] >= 1
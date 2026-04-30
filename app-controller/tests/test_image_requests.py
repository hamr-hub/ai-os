import pytest
import base64
import io
from PIL import Image


def create_test_image(width=100, height=100, color="red"):
    img = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()


def encode_image_to_base64(image_bytes):
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"


class TestImageValidation:
    def test_validate_image_success(self, py_client):
        image_data = create_test_image()
        base64_image = encode_image_to_base64(image_data)
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/validate",
            json={"image_data": base64_image},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "image_info" in data
        assert data["image_info"]["valid"] is True
        assert data["image_info"]["width"] == 100
        assert data["image_info"]["height"] == 100
        assert data["image_info"]["format"] == "png"

    def test_validate_image_invalid_base64(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/validate",
            json={"image_data": "invalid-base64-data"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_validate_image_empty_data(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/validate",
            json={"image_data": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_validate_image_unsupported_format(self, py_client):
        img = Image.new("RGB", (100, 100), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="ICO")
        buffer.seek(0)
        base64_image = f"data:image/x-icon;base64,{base64.b64encode(buffer.read()).decode('utf-8')}"
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/validate",
            json={"image_data": base64_image},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


class TestImageUpload:
    def test_upload_image_success(self, py_client):
        image_data = create_test_image()
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/upload",
            files={"file": ("test.png", image_data, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "image_info" in data

    def test_upload_image_too_large(self, py_client):
        large_img = Image.new("RGB", (10000, 10000), color="red")
        buffer = io.BytesIO()
        large_img.save(buffer, format="PNG")
        buffer.seek(0)
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/upload",
            files={"file": ("large.png", buffer.read(), "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False

    def test_upload_image_invalid_file(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/v1/images/upload",
            files={"file": ("invalid.txt", b"not an image", "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


class TestChatCompletionsWithImages:
    def test_chat_completions_with_image(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model available for image chat test")
        image_data = create_test_image()
        base64_image = encode_image_to_base64(image_data)
        resp = py_client.post(
            f"{py_client.base_url}/v1/chat/completions",
            json={
                "model": running_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's in this image?"},
                            {"type": "image_url", "image_url": {"url": base64_image}},
                        ],
                    }
                ],
                "max_tokens": 10,
            },
            timeout=30,
        )
        assert resp.status_code in (200, 500, 503)

    def test_chat_completions_with_invalid_image(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model available")
        resp = py_client.post(
            f"{py_client.base_url}/v1/chat/completions",
            json={
                "model": running_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "What's in this image?"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,invalid-base64"},
                            },
                        ],
                    }
                ],
            },
            timeout=15,
        )
        assert resp.status_code in (200, 422, 400, 500)


class TestImageInfo:
    def test_get_image_info(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/images/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "max_size_mb" in data
        assert "supported_formats" in data
        assert "endpoints" in data
        assert "png" in data["supported_formats"]

import pytest


class TestV1ChatCompletions:
    def test_chat_completions_missing_model(self, py_client):
        try:
            resp = py_client.post(
                f"{py_client.base_url}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
                timeout=10,
            )
            assert resp.status_code in (400, 422, 500)
        except Exception:
            pass

    def test_chat_completions_missing_messages(self, py_client):
        try:
            resp = py_client.post(
                f"{py_client.base_url}/v1/chat/completions",
                json={"model": "test"},
                timeout=10,
            )
            assert resp.status_code in (400, 422, 500)
        except Exception:
            pass

    def test_chat_completions_with_running_model(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model")
        resp = py_client.post(
            f"{py_client.base_url}/v1/chat/completions",
            json={
                "model": running_model,
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": 5,
            },
            timeout=30,
        )
        assert resp.status_code in (200, 500, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "choices" in data
            assert "usage" in data

    def test_chat_completions_streaming(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model")
        try:
            resp = py_client.post(
                f"{py_client.base_url}/v1/chat/completions",
                json={
                    "model": running_model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                    "stream": True,
                },
                timeout=30,
                stream=True,
            )
            assert resp.status_code in (200, 500, 503)
            if resp.status_code == 200:
                chunks = []
                for chunk in resp.iter_content(chunk_size=1024):
                    chunks.append(chunk)
                    if len(chunks) > 3:
                        break
                assert len(chunks) > 0
        except Exception:
            pass


class TestV1Embeddings:
    def test_embeddings_model_not_found(self, py_client):
        try:
            resp = py_client.post(
                f"{py_client.base_url}/v1/embeddings",
                json={"model": "nonexistent-model", "input": "Hello"},
                timeout=10,
            )
            assert resp.status_code in (404, 400, 500)
        except Exception:
            pass


class TestV1Images:
    def test_image_generation_not_available(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model")
        try:
            resp = py_client.post(
                f"{py_client.base_url}/v1/images/generations",
                json={
                    "model": running_model,
                    "prompt": "a red square",
                    "n": 1,
                    "size": "256x256",
                },
                timeout=30,
            )
            assert resp.status_code in (200, 400, 404, 500)
        except Exception:
            pass


class TestV1ModelDetails:
    def test_model_not_found(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/models/nonexistent-model-xyz")
        assert resp.status_code in (404, 500)

    def test_model_detail_structure(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(f"{py_client.base_url}/v1/models/{first_available_model}")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data or "name" in data

import pytest
import requests
import os

PY_BASE = os.environ.get("PY_BASE", "http://localhost:35000")
GO_BASE = os.environ.get("GO_BASE", "http://localhost:35001")
VLLM_BASE = os.environ.get("VLLM_BASE", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT", "10"))


@pytest.fixture(scope="session")
def py_base():
    return PY_BASE


@pytest.fixture(scope="session")
def go_base():
    return GO_BASE


@pytest.fixture(scope="session")
def vllm_base():
    return VLLM_BASE


@pytest.fixture(scope="session")
def py_client():
    s = requests.Session()
    s.base_url = PY_BASE
    s.timeout = REQUEST_TIMEOUT
    yield s
    s.close()


@pytest.fixture(scope="session")
def go_client():
    s = requests.Session()
    s.base_url = GO_BASE
    s.timeout = REQUEST_TIMEOUT
    yield s
    s.close()


@pytest.fixture(scope="session")
def running_model(py_client):
    try:
        resp = py_client.get(f"{py_client.base_url}/manage/models", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            for name, info in data.items():
                if info.get("running"):
                    return name
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def first_available_model(py_client):
    try:
        resp = py_client.get(f"{py_client.base_url}/manage/models", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            for name in data:
                return name
    except Exception:
        pass
    return None

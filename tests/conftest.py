import os
import sys
import time
import json

GO_BASE = os.environ.get("GO_BASE", "http://localhost:35001")
PY_BASE = os.environ.get("PY_BASE", "http://localhost:35000")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen2-7B-Instruct")

def pytest_addoption(parser):
    parser.addoption("--go-base", default=GO_BASE)
    parser.addoption("--py-base", default=PY_BASE)
    parser.addoption("--model-name", default=MODEL_NAME)

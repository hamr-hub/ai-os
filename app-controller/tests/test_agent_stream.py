import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes.agent import _stream_agent_completion


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "tool-1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{\"query\":\"hi\"}"},
                            }
                        ],
                    }
                }
            ]
        }


@pytest.mark.asyncio
async def test_stream_agent_completion_emits_tool_calls_end(monkeypatch):
    fake_client = SimpleNamespace(
        post=AsyncMock(return_value=DummyResponse()),
    )

    async def _fake_stream(*args, **kwargs):
        if False:
            yield None

    monkeypatch.setattr("routes.agent.httpx.AsyncClient", lambda *args, **kwargs: fake_client)
    fake_client.stream = _fake_stream

    executor = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(success=True, result={"ok": True}, error=None))
    )

    events = []
    async for chunk in _stream_agent_completion(
        backend_url="http://localhost:35000",
        model_name="demo",
        messages=[],
        tools=[],
        executor=executor,
        max_iterations=1,
        auto_confirm=False,
    ):
        events.append(chunk)

    joined = "".join(events)
    assert '"type": "tool_calls_start"' in joined
    assert '"type": "tool_result"' in joined
    assert '"type": "tool_calls_end"' in joined

from __future__ import annotations

import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

app_module = importlib.import_module("ai4ms.api.app")


class _ProbeGateway:
    async def generate(self, _system_prompt: str, _user_prompt: str):
        return SimpleNamespace(
            model="deepseek-v4-pro",
            usage={
                "input_tokens": 8,
                "output_tokens": 2,
                "total_tokens": 10,
                "call_count": 1,
            },
        )


def test_inference_probe_performs_live_gateway_call_without_exposing_key(tmp_path, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "OpenAICompatibleGateway",
        lambda **_kwargs: _ProbeGateway(),
    )
    client = TestClient(app_module.create_app(tmp_path))

    response = client.post("/api/v1/meta/inference/probe", json={})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "configured": True,
        "model": "deepseek-v4-pro",
        "usage": {
            "input_tokens": 8,
            "output_tokens": 2,
            "total_tokens": 10,
            "call_count": 1,
        },
    }
    assert "api_key" not in response.text.lower()

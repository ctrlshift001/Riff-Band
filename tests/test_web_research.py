from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from ai4ms.connectors import DataCommonsConnector, MCPConnectorError
from ai4ms.inference.gateway import InferenceResponse
from ai4ms.search import WebResearchService
from ai4ms.services.stage_chat import StageChatService


class _FakeWebSearch:
    async def __call__(self, query: str, k: int = 6):
        del k
        records = [
            {
                "title": "National AI statistics",
                "snippet": f"Official statistics matched {query}",
                "url": "https://stats.gov.cn/ai",
                "provider": "serper",
                "rank": 1,
            },
            {
                "title": "AI adoption overview",
                "snippet": "A research overview.",
                "url": "https://example.org/overview",
                "provider": "ddgs",
                "rank": 2,
            },
        ]
        return {
            "success": True,
            "backend": "serper+ddgs",
            "output": json.dumps(records),
            "source_runs": [
                {
                    "provider": "serper",
                    "success": True,
                    "record_count": 2,
                    "error": "",
                }
            ],
        }


def test_search_probe_requires_a_successful_serper_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")
    service = WebResearchService(
        tmp_path / "projects",
        web_search_factory=_FakeWebSearch,
    )

    result = asyncio.run(service.probe_search())

    assert result == {
        "status": "ok",
        "configured": True,
        "provider": "serper",
        "record_count": 2,
        "backend": "serper+ddgs",
    }
    assert "key" not in json.dumps(result).lower()


class _FakeLiteratureBroker:
    async def search(self, queries, backends, **kwargs):
        del backends, kwargs
        return SimpleNamespace(
            papers=[
                {
                    "paper_id": "paper_test",
                    "title": "AI Adoption and Firm Innovation",
                    "authors": ["Researcher"],
                    "year": 2025,
                    "abstract": "The study evaluates AI adoption and innovation.",
                    "source_urls": ["https://doi.org/10.1234/example"],
                    "backends": ["openalex", "crossref"],
                }
            ],
            source_runs=[
                {
                    "backend": "openalex",
                    "query": queries[0],
                    "success": True,
                    "record_count": 1,
                    "error": "",
                }
            ],
        )


class _FakePageReader:
    max_chars = 12_000

    async def read(self, url: str):
        return {
            "success": True,
            "url": url,
            "title": "",
            "text": f"Readable page evidence from {url}",
        }


class _UnconfiguredDataCommons:
    def status(self):
        return {"configured": False, "reason": "test connector has no key"}


def test_web_research_deduplicates_ranks_and_persists_snapshot(tmp_path):
    service = WebResearchService(
        tmp_path / "projects",
        web_search_factory=_FakeWebSearch,
        literature_broker=_FakeLiteratureBroker(),
        page_reader=_FakePageReader(),
        data_commons=_UnconfiguredDataCommons(),
    )

    result = asyncio.run(
        service.research(
            "project_a",
            "problem",
            "请搜索 AI 采用与企业创新的最新研究",
            "on",
        )
    )

    assert result["searched"] is True
    assert result["status"] == "complete"
    assert len(result["queries"]) == 2
    assert len(result["citations"]) == 3
    assert result["citations"][0]["source_type"] in {"official", "academic"}
    assert len({item["url"] for item in result["citations"]}) == 3
    snapshot = tmp_path / "projects" / "project_a" / result["snapshot_path"]
    assert snapshot.is_file()
    assert json.loads(snapshot.read_text(encoding="utf-8"))["search_id"] == result["search_id"]


class _FakeMCPClient:
    calls = []

    def __init__(self, url, *, headers, timeout_seconds):
        self.url = url
        self.headers = headers
        self.timeout_seconds = timeout_seconds

    async def list_tools(self):
        return [
            {
                "name": "search_indicators",
                "description": "Search indicators",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "queries": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["queries"],
                },
            },
            {
                "name": "write_data",
                "description": "Must not be exposed",
                "input_schema": {},
            },
        ]

    async def call_tool(self, name, arguments):
        self.__class__.calls.append((name, arguments, self.headers))
        return {
            "is_error": False,
            "text": "Population indicator",
            "content": [],
            "structured_content": None,
        }


def test_datacommons_connector_uses_schema_and_read_only_allowlist():
    _FakeMCPClient.calls.clear()
    connector = DataCommonsConnector(
        api_key="test-key",
        client_factory=_FakeMCPClient,
    )

    result = asyncio.run(connector.search_indicators("中国人口指标"))

    assert result["tool_name"] == "search_indicators"
    assert _FakeMCPClient.calls[0][1] == {"queries": ["中国人口指标"]}
    assert _FakeMCPClient.calls[0][2] == {"X-API-Key": "test-key"}
    with pytest.raises(MCPConnectorError):
        asyncio.run(connector.call_tool("write_data", {}))


class _FakeResearch:
    def __init__(self):
        self.calls = []

    async def research(self, project_id, stage_key, query, mode):
        self.calls.append((project_id, stage_key, query, mode))
        citation = {
            "citation_id": "1",
            "title": "Official source",
            "url": "https://example.gov/source",
            "domain": "example.gov",
            "snippet": "Verified external evidence",
            "excerpt": "Verified external evidence",
            "provider": "test",
            "source_type": "official",
            "is_official": True,
            "paper_id": "",
            "retrieved_at": "2026-07-26T00:00:00+00:00",
        }
        return {
            "search_id": "web_test",
            "status": "complete",
            "mode": mode,
            "searched": True,
            "searched_at": "2026-07-26T00:00:00+00:00",
            "queries": [query],
            "citations": [citation],
            "source_runs": [],
            "snapshot_path": "artifacts/search/web_test.json",
        }

    @staticmethod
    def prompt_context(trace):
        citation = trace["citations"][0]
        return f"[1] {citation['title']}\nURL: {citation['url']}"


class _FakeGateway:
    def __init__(self):
        self.calls = []

    async def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return InferenceResponse(
            text="根据官方来源，当前证据需要继续核验。[1]",
            model="test-model",
            usage={"total_tokens": 20},
        )


def test_stage_chat_persists_search_trace_and_citations(tmp_path):
    research = _FakeResearch()
    gateway = _FakeGateway()
    chat = StageChatService(
        tmp_path / "projects",
        gateway_factory=lambda: gateway,
        research_service=research,
    )
    client = TestClient(create_app(tmp_path, stage_chat=chat))
    project = client.post(
        "/api/v1/projects",
        json={"title": "AI 采用研究", "initial_idea": "研究 AI 采用的企业影响"},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['project_id']}/stages/problem/chat",
        json={"message": "查找官方证据", "search_mode": "on"},
    )

    assert response.status_code == 200
    assistant = response.json()["assistant_message"]
    assert assistant["search"]["search_id"] == "web_test"
    assert assistant["citations"][0]["citation_id"] == "1"
    assert "[1] Official source" in gateway.calls[0][1]
    history = client.get(
        f"/api/v1/projects/{project['project_id']}/stages/problem/chat"
    ).json()["items"]
    assert history[-1]["citations"] == assistant["citations"]


class _FakeDataCommonsAPI:
    def status(self):
        return {
            "connector_id": "datacommons",
            "configured": True,
            "read_only": True,
        }

    async def list_tools(self):
        return [{"name": "search_indicators"}]

    async def search_indicators(self, query):
        return {"connector_id": "datacommons", "query": query}

    async def call_tool(self, tool_name, arguments):
        return {"connector_id": "datacommons", "tool_name": tool_name, "arguments": arguments}


class _FakeResearchProbe:
    async def probe_search(self):
        return {
            "status": "ok",
            "configured": True,
            "provider": "serper",
            "record_count": 3,
            "backend": "serper",
        }


def test_search_probe_api_does_not_expose_credentials(tmp_path):
    client = TestClient(
        create_app(tmp_path, research_service=_FakeResearchProbe())
    )

    response = client.post("/api/v1/meta/search/probe", json={})

    assert response.status_code == 200
    assert response.json()["provider"] == "serper"
    assert "api_key" not in response.text.lower()


def test_connector_api_exposes_status_tools_and_query(tmp_path):
    client = TestClient(
        create_app(tmp_path, data_commons=_FakeDataCommonsAPI())
    )

    connectors = client.get("/api/v1/connectors")
    tools = client.get("/api/v1/connectors/datacommons/tools")
    query = client.post(
        "/api/v1/connectors/datacommons/query",
        json={"query": "GDP growth", "tool_name": "search_indicators"},
    )

    assert connectors.status_code == 200
    assert connectors.json()["items"][0]["configured"] is True
    assert tools.json()["items"] == [{"name": "search_indicators"}]
    assert query.json()["query"] == "GDP growth"

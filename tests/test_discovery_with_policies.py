from __future__ import annotations

from typing import Any

from fastmcp import Client

from mcp_elicitation_proxy.config import AppConfig
from mcp_elicitation_proxy.middleware import ElicitationMiddleware
from mcp_elicitation_proxy.pipeline import ElicitationPipeline
from mcp_elicitation_proxy.policies.base import InspectionResult
from mcp_elicitation_proxy.server import build_server
from tests.conftest import UPSTREAM_TOOL_DESCRIPTION, _tool_schema


class _RecordingPolicy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        self.calls.append(tool_name)
        return InspectionResult.ok()


async def test_discovery_is_preserved_with_policies_enabled(
    upstream_server_script,
) -> None:
    config = AppConfig.model_validate(
        {
            "upstream": {"url": str(upstream_server_script)},
            "proxy": {"name": "test-discovery-policy-proxy"},
            "tools": {"search_docs": {"required": ["scope"]}},
        }
    )
    server = build_server(config)
    recording_policy = _RecordingPolicy()
    server.add_middleware(ElicitationMiddleware(ElicitationPipeline([recording_policy])))

    async with Client(server) as client:
        tools = await client.list_tools()

    tool_names = {tool.name for tool in tools}
    assert tool_names == {"search_docs"}
    assert "call_upstream_tool" not in tool_names
    assert "call_tool" not in tool_names
    assert "proxy_call" not in tool_names

    search_docs_tool = tools[0]
    assert search_docs_tool.name == "search_docs"
    assert search_docs_tool.description == UPSTREAM_TOOL_DESCRIPTION

    schema = _tool_schema(search_docs_tool)
    assert set(schema["properties"]) == {"query", "project"}
    assert schema.get("required") == ["query", "project"]
    assert "scope" not in schema["properties"]
    assert "scope" not in schema.get("required", [])
    assert recording_policy.calls == []

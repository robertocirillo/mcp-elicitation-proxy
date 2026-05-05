from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import mcp.types as mt
from fastmcp import Client

from mcp_elicitation_proxy.config import AppConfig
from mcp_elicitation_proxy.middleware import ElicitationMiddleware
from mcp_elicitation_proxy.pipeline import ElicitationPipeline
from mcp_elicitation_proxy.policies.base import InspectionResult
from mcp_elicitation_proxy.server import build_server
from tests.conftest import _call_result_data, _tool_schema


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


def _write_first_slice_upstream(script_path: Path, calls_path: Path) -> None:
    script_path.write_text(
        dedent(
            f'''
            import json
            from pathlib import Path

            from fastmcp import FastMCP

            mcp = FastMCP("FirstSliceUpstream")
            CALLS_PATH = Path({str(calls_path)!r})


            def _record(tool: str, arguments: dict) -> None:
                with CALLS_PATH.open("a", encoding="utf-8") as calls_file:
                    calls_file.write(json.dumps({{"tool": tool, "arguments": arguments}}) + "\\n")


            @mcp.tool
            def search_docs(query: str, project: str) -> dict:
                """Search project documentation."""
                arguments = {{"query": query, "project": project}}
                _record("search_docs", arguments)
                return {{
                    "query": query,
                    "project": project,
                    "results": [f"{{project}}: {{query}}"],
                }}


            @mcp.tool
            def save_secret(name: str, api_key: str) -> dict:
                """Save an API key for a named integration."""
                arguments = {{"name": name, "api_key": api_key}}
                _record("save_secret", arguments)
                return {{"name": name, "saved": True}}


            if __name__ == "__main__":
                mcp.run()
            '''
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _first_slice_config(script_path: Path, *, elicitation_enabled: bool = True) -> AppConfig:
    return AppConfig.model_validate(
        {
            "upstream": {"url": str(script_path)},
            "proxy": {"name": "first-slice-hardening-proxy"},
            "elicitation": {
                "enabled": elicitation_enabled,
                "fallback_on_unsupported": "structured_error",
            },
            "policies": {
                "schema_required": {"enabled": True},
                "sensitive_required": {"enabled": True},
            },
            "tools": {
                "search_docs": {
                    "required": ["query", "project"],
                    "elicit": {
                        "message": "Which project should I search?",
                        "fields": {
                            "project": {
                                "type": "string",
                                "description": "Project or scope to search",
                            }
                        },
                    },
                },
                "save_secret": {
                    "required": ["name", "api_key"],
                },
            },
        }
    )


def _calls(calls_path: Path) -> list[dict[str, Any]]:
    if not calls_path.exists():
        return []
    return [
        json.loads(line)
        for line in calls_path.read_text(encoding="utf-8").splitlines()
        if line
    ]


async def test_complete_input_forwards_once_without_elicitation(tmp_path: Path) -> None:
    calls_path = tmp_path / "calls.jsonl"
    script_path = tmp_path / "first_slice_upstream.py"
    _write_first_slice_upstream(script_path, calls_path)
    server = build_server(_first_slice_config(script_path))
    elicitation_requests: list[mt.ElicitRequestParams] = []

    async def elicitation_handler(
        message: str,
        response_type: type[Any] | None,
        params: mt.ElicitRequestParams,
        context: object,
    ) -> dict[str, Any]:
        elicitation_requests.append(params)
        return {"project": "should-not-be-used"}

    async with Client(server, elicitation_handler=elicitation_handler) as client:
        result = await client.call_tool(
            "search_docs",
            {"query": "release notes", "project": "docs"},
        )

    assert _call_result_data(result) == {
        "query": "release notes",
        "project": "docs",
        "results": ["docs: release notes"],
    }
    assert elicitation_requests == []
    assert _calls(calls_path) == [
        {
            "tool": "search_docs",
            "arguments": {"query": "release notes", "project": "docs"},
        }
    ]


async def test_missing_non_sensitive_field_accepts_elicitation_and_forwards_once(
    tmp_path: Path,
) -> None:
    calls_path = tmp_path / "calls.jsonl"
    script_path = tmp_path / "first_slice_upstream.py"
    _write_first_slice_upstream(script_path, calls_path)
    server = build_server(_first_slice_config(script_path))
    elicitation_requests: list[mt.ElicitRequestParams] = []

    async def elicitation_handler(
        message: str,
        response_type: type[Any] | None,
        params: mt.ElicitRequestParams,
        context: object,
    ) -> dict[str, Any]:
        elicitation_requests.append(params)
        assert message == "Which project should I search?"
        assert response_type is not None
        return {"project": "platform"}

    async with Client(server, elicitation_handler=elicitation_handler) as client:
        result = await client.call_tool("search_docs", {"query": "release notes"})

    assert _call_result_data(result) == {
        "query": "release notes",
        "project": "platform",
        "results": ["platform: release notes"],
    }
    assert len(elicitation_requests) == 1
    requested_schema = elicitation_requests[0].requestedSchema
    assert set(requested_schema["properties"]) == {"project"}
    assert requested_schema["properties"]["project"]["description"] == (
        "Project or scope to search"
    )
    assert _calls(calls_path) == [
        {
            "tool": "search_docs",
            "arguments": {"query": "release notes", "project": "platform"},
        }
    ]


async def test_missing_non_sensitive_field_with_elicitation_disabled_blocks_upstream(
    tmp_path: Path,
) -> None:
    calls_path = tmp_path / "calls.jsonl"
    script_path = tmp_path / "first_slice_upstream.py"
    _write_first_slice_upstream(script_path, calls_path)
    server = build_server(_first_slice_config(script_path, elicitation_enabled=False))
    elicitation_requests: list[mt.ElicitRequestParams] = []

    async def elicitation_handler(
        message: str,
        response_type: type[Any] | None,
        params: mt.ElicitRequestParams,
        context: object,
    ) -> dict[str, Any]:
        elicitation_requests.append(params)
        return {"project": "should-not-be-used"}

    async with Client(server, elicitation_handler=elicitation_handler) as client:
        result = await client.call_tool("search_docs", {"query": "release notes"})

    payload = _call_result_data(result)
    assert payload["error"] == "elicitation_required"
    assert payload["tool"] == "search_docs"
    assert payload["status"] == "needs_elicitation"
    assert payload["reason"] == "elicitation_disabled"
    assert payload["missing_or_ambiguous"] == ["project"]
    assert payload["message"]
    assert elicitation_requests == []
    assert _calls(calls_path) == []


async def test_missing_sensitive_required_field_blocks_elicitation_and_upstream(
    tmp_path: Path,
) -> None:
    calls_path = tmp_path / "calls.jsonl"
    script_path = tmp_path / "first_slice_upstream.py"
    _write_first_slice_upstream(script_path, calls_path)
    server = build_server(_first_slice_config(script_path))
    elicitation_requests: list[mt.ElicitRequestParams] = []

    async def elicitation_handler(
        message: str,
        response_type: type[Any] | None,
        params: mt.ElicitRequestParams,
        context: object,
    ) -> dict[str, Any]:
        elicitation_requests.append(params)
        return {"api_key": "should-not-be-used"}

    async with Client(server, elicitation_handler=elicitation_handler) as client:
        result = await client.call_tool("save_secret", {"name": "github"})

    payload = _call_result_data(result)
    assert payload["error"] == "tool_call_blocked"
    assert payload["tool"] == "save_secret"
    assert payload["status"] == "reject"
    assert payload["reason"] == "sensitive_required_field"
    assert payload["missing_or_ambiguous"] == ["api_key"]
    assert elicitation_requests == []
    assert _calls(calls_path) == []


async def test_discovery_remains_upstream_native_with_call_policies_enabled(
    tmp_path: Path,
) -> None:
    calls_path = tmp_path / "calls.jsonl"
    script_path = tmp_path / "first_slice_upstream.py"
    _write_first_slice_upstream(script_path, calls_path)
    server = build_server(_first_slice_config(script_path))
    recording_policy = _RecordingPolicy()
    server.add_middleware(ElicitationMiddleware(ElicitationPipeline([recording_policy])))

    async with Client(server) as client:
        tools = await client.list_tools()

    tool_names = {tool.name for tool in tools}
    assert tool_names == {"search_docs", "save_secret"}
    assert "call_upstream_tool" not in tool_names
    assert "call_tool" not in tool_names
    assert "proxy_call" not in tool_names

    tools_by_name = {tool.name: tool for tool in tools}
    search_docs = tools_by_name["search_docs"]
    save_secret = tools_by_name["save_secret"]
    assert search_docs.description == "Search project documentation."
    assert save_secret.description == "Save an API key for a named integration."

    search_schema = _tool_schema(search_docs)
    assert set(search_schema["properties"]) == {"query", "project"}
    assert search_schema.get("required") == ["query", "project"]

    secret_schema = _tool_schema(save_secret)
    assert set(secret_schema["properties"]) == {"name", "api_key"}
    assert secret_schema.get("required") == ["name", "api_key"]

    assert recording_policy.calls == []
    assert _calls(calls_path) == []

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from fastmcp import Client

from mcp_elicitation_proxy.config import AppConfig, ProxyConfig, UpstreamConfig
from mcp_elicitation_proxy.server import build_server


UPSTREAM_TOOL_DESCRIPTION = "Search project documentation."


def _write_upstream_server(path: Path) -> None:
    path.write_text(
        dedent(
            '''
            from fastmcp import FastMCP

            mcp = FastMCP("UpstreamDocs")


            @mcp.tool
            def search_docs(query: str, project: str) -> dict:
                """Search project documentation."""
                return {
                    "query": query,
                    "project": project,
                    "results": [
                        f"{project}: {query}",
                        f"{project}: exact-match",
                    ],
                }


            if __name__ == "__main__":
                mcp.run()
            '''
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _tool_schema(tool: object) -> dict:
    schema = getattr(tool, "inputSchema", None)
    if schema is not None:
        return schema
    schema = getattr(tool, "input_schema", None)
    if schema is not None:
        return schema
    raise AssertionError(f"tool schema not found on {tool!r}")


def _call_result_data(result: object) -> dict:
    data = getattr(result, "data", None)
    if data is not None:
        return data

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None) or []
    if content and hasattr(content[0], "text"):
        return json.loads(content[0].text)

    raise AssertionError(f"unable to extract structured tool result from {result!r}")


@pytest.fixture
def upstream_server_script(tmp_path: Path) -> Path:
    script_path = tmp_path / "upstream_server.py"
    _write_upstream_server(script_path)
    return script_path


@pytest.fixture
def app_config(upstream_server_script: Path) -> AppConfig:
    return AppConfig(
        upstream=UpstreamConfig(url=str(upstream_server_script)),
        proxy=ProxyConfig(name="test-elicitation-proxy"),
    )


@pytest.fixture
def proxy_server(app_config: AppConfig):
    return build_server(app_config)


@pytest.fixture
async def proxy_client(proxy_server):
    async with Client(proxy_server) as client:
        yield client

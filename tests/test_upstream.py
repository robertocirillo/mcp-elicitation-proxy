from __future__ import annotations

import sys
from pathlib import Path

from fastmcp import Client

from mcp_elicitation_proxy.config import AppConfig, ProxyConfig, UpstreamConfig
from mcp_elicitation_proxy.server import build_server
from mcp_elicitation_proxy import upstream as upstream_module


def test_create_upstream_proxy_passes_url_target(
    monkeypatch,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    sentinel = object()
    config = AppConfig(
        upstream=UpstreamConfig(url="http://localhost:8001/mcp"),
        proxy=ProxyConfig(name="test-proxy"),
    )

    def fake_create_proxy(target: object, **settings: object) -> object:
        calls.append((target, settings))
        return sentinel

    monkeypatch.setattr(upstream_module, "create_proxy", fake_create_proxy)

    assert upstream_module.create_upstream_proxy(config) is sentinel
    assert calls == [("http://localhost:8001/mcp", {"name": "test-proxy"})]


def test_create_upstream_proxy_builds_command_config(
    monkeypatch,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    sentinel = object()
    config = AppConfig(
        upstream=UpstreamConfig(command="npx", args=["-y", "server"]),
        proxy=ProxyConfig(name="test-proxy"),
    )

    def fake_create_proxy(target: object, **settings: object) -> object:
        calls.append((target, settings))
        return sentinel

    monkeypatch.setattr(upstream_module, "create_proxy", fake_create_proxy)

    assert upstream_module.create_upstream_proxy(config) is sentinel
    assert calls == [
        (
            {
                "mcpServers": {
                    "upstream": {
                        "command": "npx",
                        "args": ["-y", "server"],
                    }
                }
            },
            {"name": "test-proxy"},
        )
    ]


def test_create_upstream_proxy_includes_command_env(
    monkeypatch,
) -> None:
    calls: list[object] = []
    config = AppConfig(
        upstream=UpstreamConfig(
            command="uvx",
            args=["some-mcp-server"],
            env={"SOME_KEY": "some-value"},
        )
    )

    def fake_create_proxy(target: object, **settings: object) -> object:
        calls.append(target)
        return object()

    monkeypatch.setattr(upstream_module, "create_proxy", fake_create_proxy)

    upstream_module.create_upstream_proxy(config)

    assert calls == [
        {
            "mcpServers": {
                "upstream": {
                    "command": "uvx",
                    "args": ["some-mcp-server"],
                    "env": {"SOME_KEY": "some-value"},
                }
            }
        }
    ]


async def test_command_config_preserves_upstream_tool_names(
    upstream_server_script: Path,
) -> None:
    proxy = build_server(
        AppConfig(
            upstream=UpstreamConfig(
                command=sys.executable,
                args=[str(upstream_server_script)],
            ),
            proxy=ProxyConfig(name="command-config-proxy"),
        )
    )

    async with Client(proxy) as client:
        tools = await client.list_tools()

    tool_names = {tool.name for tool in tools}
    assert tool_names == {"search_docs"}
    assert "upstream_search_docs" not in tool_names


def test_fastmcp_as_proxy_is_not_used_in_source() -> None:
    source_root = Path("src")
    references = [
        path
        for path in source_root.rglob("*.py")
        if "FastMCP.as_proxy" in path.read_text(encoding="utf-8")
        or ".as_proxy(" in path.read_text(encoding="utf-8")
    ]

    assert references == []


def test_no_generic_call_upstream_tool_in_source() -> None:
    source_root = Path("src")
    references = [
        path
        for path in source_root.rglob("*.py")
        if "call_upstream_tool" in path.read_text(encoding="utf-8")
    ]

    assert references == []

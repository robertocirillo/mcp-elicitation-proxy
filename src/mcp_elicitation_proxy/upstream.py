from __future__ import annotations

from typing import Any, Callable

from .config import AppConfig


def _resolve_create_proxy() -> Callable[..., Any]:
    try:
        from fastmcp.server import create_proxy
    except ImportError:
        from fastmcp import FastMCP

        # FastMCP documents `create_proxy()` as the current API. This fallback
        # keeps compatibility with older installations where `as_proxy()` exists.
        return FastMCP.as_proxy

    return create_proxy


def create_upstream_proxy(config: AppConfig) -> Any:
    create_proxy = _resolve_create_proxy()
    return create_proxy(config.upstream.url, name=config.proxy.name)

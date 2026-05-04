# mcp-elicitation-proxy

`mcp-elicitation-proxy` is a standalone Python MCP proxy built on FastMCP.

Its core architectural rule is strict: upstream discovery stays native. The proxy must preserve upstream `tools/list` output instead of replacing it with a synthetic wrapper such as `call_upstream_tool`.

In this first slice the project provides:

- an installable `src/` package;
- YAML configuration loading;
- a thin server factory around FastMCP native proxying;
- placeholders for elicitation middleware, policies, and request building;
- tests that verify real discovery and tool-call forwarding through the proxy.

## Architecture

- Upstream discovery is delegated to FastMCP native proxying via `fastmcp.server.create_proxy(...)`.
- No local generic tool is registered.
- No manual redefinition of upstream tool schemas is performed.
- Elicitation middleware is intentionally deferred to later tasks.

FastMCP's current recommended API is `fastmcp.server.create_proxy(...)`, so this project uses that directly.

## Setup

```bash
uv sync
```

## Test

```bash
uv run pytest
```

Optional lint:

```bash
uv run ruff check .
```

## Configuration

Example `config.yaml`:

```yaml
upstream:
  url: "http://localhost:8001/mcp"

proxy:
  name: "mcp-elicitation-proxy"

elicitation:
  enabled: true
  fallback_on_unsupported: "structured_error"
```

## Run

```bash
uv run mcp-elicitation-proxy --config config.yaml
```

You can also provide the config path via `MCP_ELICITATION_PROXY_CONFIG`.

## Status

The elicitation middleware is not implemented yet. This slice only establishes the proxy skeleton, policy interfaces, structured error payloads, and test harness needed for the next tasks.

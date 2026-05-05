# mcp-elicitation-proxy

`mcp-elicitation-proxy` is a standalone Python MCP proxy built on FastMCP.

Its core architectural rule is strict: upstream discovery stays native. The proxy must preserve upstream `tools/list` output instead of replacing it with a synthetic wrapper such as `call_upstream_tool`.

In this first slice the project provides:

- an installable `src/` package;
- YAML configuration loading;
- a thin server factory around FastMCP native proxying;
- elicitation middleware, policies, and request building for missing required fields;
- a guard that blocks form-mode elicitation for required fields that look sensitive;
- tests that verify real discovery and tool-call forwarding through the proxy.

## Architecture

- Upstream discovery is delegated to FastMCP native proxying via `fastmcp.server.create_proxy(...)`.
- No local generic tool is registered.
- No manual redefinition of upstream tool schemas is performed.
- Elicitation logic lives in middleware/policies and does not replace native discovery or forwarding.

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

The proxy performs real form-mode elicitation for non-sensitive missing required fields. Required fields that appear to be credentials or secrets are blocked with a structured `tool_call_blocked` result instead of being elicited.

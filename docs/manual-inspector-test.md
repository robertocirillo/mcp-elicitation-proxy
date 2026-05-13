# Manual Inspector Smoke Test

This smoke test validates `mcp-elicitation-proxy` with MCP Inspector as the
client and the official `@modelcontextprotocol/server-everything` package as
the upstream server.

It covers command-based upstream startup, native upstream tool discovery,
forwarding, elicitation for missing required fields, sensitive-required
blocking, and `upstream.env` propagation.

## Prerequisites

- `uv`
- Node/npm/npx

Optional local checks before the manual test:

```bash
uv run pytest -q
uv run ruff check .
node --version
npx --version
```

## Start Inspector

Use the checked-in config at
[examples/manual-everything.config.yaml](../examples/manual-everything.config.yaml):

```bash
npx @modelcontextprotocol/inspector -- uv run mcp-elicitation-proxy --config examples/manual-everything.config.yaml
```

The `--` separator keeps Inspector arguments separate from proxy arguments.

## Expected Checks

Discovery:

- `echo` is visible as an upstream tool.
- `call_upstream_tool` is not present.
- tool names are not prefixed with `upstream_`.

Forwarding:

```json
{ "message": "hello from mcp-elicitation-proxy v0.1.0" }
```

Calling `echo` with complete input should return the upstream echo response.

Elicitation:

Call `echo` without `message`. The proxy should discover that `message` is
required by the upstream schema and send an elicitation request using the custom
copy from `examples/manual-everything.config.yaml`.

If the elicited value is:

```text
completed through elicitation
```

the final result should be the upstream echo response for that value.

Sensitive required-field guard:

Temporarily add `message` as a sensitive marker:

```yaml
policies:
  sensitive_required:
    enabled: true
    sensitive_name_markers:
      - message
```

Calling `echo` without `message` should be blocked with
`reason: "sensitive_required_field"` and should not show an elicitation form.
Calling `echo` with an explicit complete `message` should still be forwarded.

Environment propagation:

`examples/manual-everything.config.yaml` sets:

```yaml
upstream:
  env:
    MCP_ELICITATION_PROXY_MANUAL_TEST: "env-ok"
```

Use the environment-related tool exposed by `server-everything` to verify that
the upstream process can see
`MCP_ELICITATION_PROXY_MANUAL_TEST=env-ok`.

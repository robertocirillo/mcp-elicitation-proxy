# mcp-elicitation-proxy

`mcp-elicitation-proxy` is a standalone Python MCP proxy built on FastMCP. It
preserves native upstream tool discovery while adding tool-call middleware for
required-field elicitation and sensitive required-field blocking.

The core architectural rule is strict: upstream discovery stays native. The
proxy must preserve upstream `tools/list` output instead of replacing it with a
synthetic wrapper such as `call_upstream_tool`.

## Setup

```bash
uv sync
```

Run tests:

```bash
uv run pytest -q
```

Optional lint:

```bash
uv run ruff check .
```

Build artifacts can be produced with `uv build`. Local outputs under `dist/`
are not intended to be committed.

## Configuration

Example `config.yaml` with an HTTP upstream:

```yaml
proxy:
  name: "mcp-elicitation-proxy"

upstream:
  url: "http://localhost:8001/mcp"

elicitation:
  enabled: true
  fallback_on_unsupported: "structured_error"

policies:
  schema_required:
    enabled: true
  sensitive_required:
    enabled: true

tools:
  search_docs:
    required:
      - query
      - project
    elicit:
      message: "Provide the missing search details."
      fields:
        project:
          type: "string"
          description: "Project or scope to search."
```

Example `config.yaml` with a command-based upstream:

```yaml
proxy:
  name: "mcp-elicitation-proxy"

upstream:
  command: "npx"
  args:
    - -y
    - "@modelcontextprotocol/server-everything"
```

`upstream.url` and `upstream.command` are mutually exclusive. Exactly one must
be configured. `upstream.args` defaults to an empty list and is valid only with
`upstream.command`. Command-based upstreams may also provide string environment
variables with `upstream.env`.

Run the proxy:

```bash
uv run mcp-elicitation-proxy --config config.yaml
```

You can also provide the config path via `MCP_ELICITATION_PROXY_CONFIG`.

## MCP Client Configuration

When configuring an MCP client, use `mcp-elicitation-proxy` as the package and
CLI command. The local MCP client server alias can be shorter; the recommended
alias is `elicitation-proxy`.

```json
{
  "mcpServers": {
    "elicitation-proxy": {
      "command": "uvx",
      "args": [
        "mcp-elicitation-proxy",
        "--config",
        "/path/to/config.yaml"
      ]
    }
  }
}
```

In this example, `elicitation-proxy` is only the client-local server alias.
`mcp-elicitation-proxy` remains the PyPI package name and CLI command. These
names do not need to match. If desired, the proxy's own MCP server name can also
be set separately in YAML:

```yaml
proxy:
  name: "elicitation-proxy"
```

## Discovery Invariants

- Upstream tools remain visible in native `tools/list`.
- The proxy does not register a generic `call_upstream_tool`.
- Tool names are not prefixed with values such as `upstream_`.
- Tool names, descriptions, and input schemas remain the upstream values unless
  an explicit future discovery feature changes that contract.

The upstream server is delegated to FastMCP native proxying via
`fastmcp.server.create_proxy(...)`.

## Required Fields And Elicitation

`schema_required` uses native upstream JSON Schema `required` fields.
Per-tool `tools.<tool_name>.required` entries are added at runtime for
`tools/call` validation only. Schema-required fields keep their original order,
then configured fields are appended without duplicates.

When `elicitation.enabled` is `true`, missing non-sensitive required fields may
be requested with the client's MCP elicitation capability and merged into the
original arguments before forwarding upstream. If elicitation is disabled,
unsupported, declined, cancelled, or fails, the proxy returns a structured
result instead of calling the upstream tool.

The `sensitive_required` policy runs before normal required-field elicitation.
If a missing required field appears to be a credential or secret, the proxy
blocks form-mode elicitation and returns a structured `tool_call_blocked`
result. Complete explicit input is still forwarded.

`ambiguous_if` and `confirm_if` settings are parsed for forward-compatible
configuration, but advanced ambiguity, confirmation, and LLM-based policies are
not implemented in `v0.1.0`.

## Manual Smoke Test With MCP Inspector

A repeatable manual test is available with MCP Inspector and the official
`@modelcontextprotocol/server-everything` reference server.

```bash
npx @modelcontextprotocol/inspector -- uv run mcp-elicitation-proxy --config examples/manual-everything.config.yaml
```

This test verifies command-based upstream startup, native upstream tool
discovery, forwarding, elicitation for missing required fields,
sensitive-required blocking, and `upstream.env` propagation.

Expected high-level checks:

- `echo` is visible as an upstream tool;
- `call_upstream_tool` is not present;
- tool names are not prefixed with `upstream_`;
- calling `echo` with a complete `message` is forwarded;
- calling `echo` without `message` triggers elicitation;
- configured elicitation copy from `examples/manual-everything.config.yaml` is
  used;
- marking a missing required field as sensitive blocks elicitation;
- the configured environment variable is visible to the upstream environment
  tool.

See [docs/manual-inspector-test.md](docs/manual-inspector-test.md) for details.

## Status

`v0.1.0` is the first public-ready baseline. It includes a single-upstream
FastMCP proxy, native discovery preservation, required-field elicitation,
sensitive required-field blocking, command-based upstream startup, YAML
configuration, and automated coverage for the main proxy invariants.

# mcp-elicitation-proxy

`mcp-elicitation-proxy` is a standalone Python MCP proxy built on FastMCP.

Its core architectural rule is strict: upstream discovery stays native. The proxy must preserve upstream `tools/list` output instead of replacing it with a synthetic wrapper such as `call_upstream_tool`.

In this first slice the project provides:

- an installable `src/` package;
- YAML configuration loading;
- a thin server factory around FastMCP native proxying;
- elicitation middleware, policies, and request building for missing required fields;
- a guard that blocks form-mode elicitation for required fields that look sensitive;
- declarative policy toggles and per-tool required fields;
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
uv run pytest -q
```

Optional lint:

```bash
uv run ruff check .
```

## Build

```bash
uv build
```

Build artifacts are local release outputs under `dist/` and are not intended to
be committed.

## Configuration

Example `config.yaml` with an HTTP upstream:

```yaml
upstream:
  url: "http://localhost:8001/mcp"

proxy:
  name: "mcp-elicitation-proxy"

elicitation:
  enabled: true
  fallback_on_unsupported: "structured_error"

policies:
  schema_required:
    enabled: true

  sensitive_required:
    enabled: true
    sensitive_name_markers:
      - password
      - secret
      - token
      - api_key
      - access_token
      - private_key
      - cvv
    sensitive_schema_markers:
      - password
      - secret
      - token
      - credential
      - private key

tools:
  search_docs:
    required:
      - query
      - project
    ambiguous_if:
      query_min_length: 5
      generic_terms:
        - documento
        - file
        - roba
    elicit:
      message: "La ricerca è ambigua. Specifica query e progetto."
      fields:
        query:
          type: string
          description: "Query completa da usare per la ricerca"
        project:
          type: string
          description: "Progetto o scope in cui cercare"

  delete_item:
    required:
      - item_id
    confirm_if:
      always: true
    elicit:
      message: "Confermi di voler eliminare questo elemento?"
```

Example `config.yaml` with a command-based upstream:

```yaml
upstream:
  command: "npx"
  args:
    - -y
    - "@modelcontextprotocol/server-everything"

proxy:
  name: "mcp-elicitation-proxy"
```

`upstream.url` and `upstream.command` are mutually exclusive. Exactly one must
be configured. `upstream.args` defaults to an empty list and is valid only with
`upstream.command`. Command-based upstreams may also provide string environment
variables:

```yaml
upstream:
  command: "uvx"
  args:
    - "some-mcp-server"
  env:
    SOME_KEY: "some-value"
```

Both upstream forms are passed to FastMCP `create_proxy(...)`. Discovery remains
native: the proxy delegates upstream `tools/list` and does not register a
generic forwarding tool.

`schema_required` uses native upstream JSON Schema `required` fields. Per-tool
`tools.<tool_name>.required` fields are added at runtime for `tools/call`
validation only: schema required fields keep their original order, then
configured fields are appended without duplicates.

The proxy does not modify `tools/list`. Tool name, description, and input schema
remain the upstream values unless an explicit future discovery feature changes
that contract.

`elicitation.enabled` controls whether the middleware may call the client's
MCP elicitation capability:

- `enabled: true` means missing non-sensitive required fields are requested with
  `ctx.elicit(...)`, then merged into the original arguments before forwarding
  upstream.
- `enabled: false` means the middleware never calls `ctx.elicit(...)`. If input
  is incomplete, it returns a structured result and does not call the upstream
  tool.

Only one unsupported-client fallback is implemented in this slice:
`fallback_on_unsupported: "structured_error"`. If the client does not support
elicitation, declines, cancels, or elicitation fails, the proxy returns a
structured result similar to:

```json
{
  "error": "elicitation_required",
  "tool": "search_docs",
  "status": "needs_elicitation",
  "reason": "elicitation_unsupported",
  "missing_or_ambiguous": ["project"],
  "message": "Input incompleto. Richiama il tool specificando i campi mancanti."
}
```

Clients or models that receive this result should call the same tool again with
complete input.

`tools.<tool_name>.elicit.message` customizes the prompt sent to the client for
that tool. `tools.<tool_name>.elicit.fields` customizes primitive flat field
metadata used in the elicitation form:

```yaml
tools:
  search_docs:
    elicit:
      message: "In quale progetto devo cercare?"
      fields:
        project:
          type: string
          description: "Progetto o scope in cui cercare"
```

Only fields present in the active `needs_elicitation` issues are included in the
elicitation request. Extra configured field metadata does not alter discovery or
the upstream schema.

Policy order is:

1. `sensitive_required`
2. `schema_required`

This blocks missing or empty sensitive required fields before normal required
field elicitation can request them.

`ambiguous_if` and `confirm_if` settings are parsed for forward-compatible
configuration, but advanced ambiguity, confirmation, and LLM-based policies are
not implemented in this slice.

Structured rejection reason behavior: if all reject issues have the same
`reason`, the error payload keeps that reason. If future reject policies produce
different reasons in one result, the payload reason can become
`policy_rejected`.

TODO: sensitive marker matching is intentionally conservative and may produce
false positives. A future version can add more precise word-boundary matching or
a configurable allowlist.

## Run

```bash
uv run mcp-elicitation-proxy --config config.yaml
```

You can also provide the config path via `MCP_ELICITATION_PROXY_CONFIG`.

### Manual functional test with MCP Inspector and server-everything

This manual test validates `mcp-elicitation-proxy` with the official MCP
Inspector as the client and the official reference `server-everything` package
as the upstream server:

```text
MCP Inspector
  -> mcp-elicitation-proxy
  -> npx -y @modelcontextprotocol/server-everything
```

It uses `examples/manual-everything.config.yaml`, which configures a
command-based upstream, an upstream environment variable, elicitation, and a
custom elicitation message for the upstream `echo` tool.

Prerequisites and optional local checks:

You need `uv` and Node/npm/npx available locally. The test and lint commands
below are optional local checkout checks before running the manual test.

```bash
uv run pytest -q
uv run ruff check .
node --version
npx --version
```

Start the manual test through Inspector:

```bash
npx @modelcontextprotocol/inspector -- uv run mcp-elicitation-proxy --config examples/manual-everything.config.yaml
```

The `--` separator keeps Inspector arguments separate from proxy arguments. If
it is omitted, `--config` may be interpreted by Inspector instead of by
`mcp-elicitation-proxy`.

After Inspector connects, the upstream tools exposed by `server-everything`
should be visible through the proxy. Expected discovery checks:

- `echo` is present;
- `call_upstream_tool` is absent;
- names are not prefixed, so tools such as `upstream_echo` or `upstream_add`
  should not appear.

These checks validate that upstream discovery stays delegated to FastMCP
`create_proxy(...)` and is not replaced by a generic forwarding tool.

Call `echo` with complete input:

```json
{
  "message": "hello from mcp-elicitation-proxy v0.1.0"
}
```

The expected result is equivalent to:

```text
Echo: "hello from mcp-elicitation-proxy v0.1.0"
```

Call `echo` without `message`. The proxy should dynamically discover that
`message` is required by the upstream schema and send an elicitation request.
With `examples/manual-everything.config.yaml`, the expected custom message is:

```text
To complete the proxy test, provide the message to send to the echo tool.
```

The request schema should contain the configured `message` field description:

```text
Text that the echo tool should repeat in its response.
```

Inspector may show the elicitation request inline in the tool-call flow rather
than automatically switching to a dedicated Elicitation tab. If the elicited
value is:

```text
completed through elicitation
```

the final result should be equivalent to:

```text
Echo: completed through elicitation
```

To test the sensitive required-field guard, temporarily mark `message` as
sensitive in the config:

```yaml
policies:
  sensitive_required:
    enabled: true
    sensitive_name_markers:
      - message

tools:
  echo:
    elicit:
      message: "This message should NOT appear when message is treated as sensitive."
      fields:
        message:
          type: "string"
          description: "This field is marked as sensitive for the manual test."
```

Calling `echo` without `message` should not show an elicitation request. The
expected structured result is:

```json
{
  "error": "tool_call_blocked",
  "tool": "echo",
  "status": "reject",
  "reason": "sensitive_required_field",
  "missing_or_ambiguous": [
    "message"
  ],
  "message": "Tool call blocked because form-mode elicitation cannot request sensitive required field 'message'."
}
```

The same guard must still allow explicit complete input:

```json
{
  "message": "sensitive guard allows explicit complete input"
}
```

Expected result:

```text
Echo: sensitive guard allows explicit complete input
```

To test the disabled-elicitation fallback, temporarily set:

```yaml
elicitation:
  enabled: false
  fallback_on_unsupported: "structured_error"
```

Calling `echo` without `message` should return:

```json
{
  "error": "elicitation_required",
  "tool": "echo",
  "status": "needs_elicitation",
  "reason": "elicitation_disabled",
  "missing_or_ambiguous": [
    "message"
  ],
  "message": "Input incompleto. Richiama il tool specificando i campi mancanti."
}
```

`examples/manual-everything.config.yaml` also passes an environment variable to
the upstream process:

```yaml
upstream:
  env:
    MCP_ELICITATION_PROXY_MANUAL_TEST: "env-ok"
```

In the manual test, use the environment or print-env tool exposed by
`server-everything` to verify that the upstream process can see:

```json
"MCP_ELICITATION_PROXY_MANUAL_TEST": "env-ok"
```

## First slice milestone status

The first slice is complete for:

- starting a standalone FastMCP proxy server;
- configuring a single upstream server;
- preserving native upstream tool discovery;
- applying middleware only on tool calls;
- enforcing required-field policies from upstream schema and config;
- blocking required fields that look sensitive before elicitation;
- eliciting missing non-sensitive required fields when the client supports it;
- forwarding the completed call upstream after accepted elicitation;
- returning structured errors when elicitation is unavailable, disabled,
  declined, cancelled, or fails;
- automated tests for discovery, forwarding, elicitation behavior, config, and
  structured error payload stability.

Explicitly out of scope for this slice:

- multi-upstream routing;
- UI;
- LLM-based policies;
- complex auth;
- rate limiting;
- persistence;
- advanced observability;
- real confirmation policy behavior;
- advanced ambiguity policy behavior.

## Status

The proxy performs real form-mode elicitation for non-sensitive missing required
fields when enabled. Required fields that appear to be credentials or secrets are
blocked with a structured `tool_call_blocked` result instead of being elicited.

This `0.1.0` baseline is intended as an internal/preliminary release. No package
license is declared yet; choose one before publishing outside internal channels.

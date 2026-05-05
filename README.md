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

`schema_required` uses native upstream JSON Schema `required` fields. Per-tool
`tools.<tool_name>.required` fields are added at runtime for `tools/call`
validation only: schema required fields keep their original order, then
configured fields are appended without duplicates.

The proxy does not modify `tools/list`. Tool name, description, and input schema
remain the upstream values unless an explicit future discovery feature changes
that contract.

Policy order is:

1. `sensitive_required`
2. `schema_required`

This blocks missing or empty sensitive required fields before normal required
field elicitation can request them.

`ambiguous_if`, `confirm_if`, and detailed `elicit` settings are parsed for
forward-compatible configuration, but advanced ambiguity, confirmation, and
LLM-based policies are not implemented in this slice.

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

## Status

The proxy performs real form-mode elicitation for non-sensitive missing required fields. Required fields that appear to be credentials or secrets are blocked with a structured `tool_call_blocked` result instead of being elicited.

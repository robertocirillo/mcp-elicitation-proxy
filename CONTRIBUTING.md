# Contributing

This project uses `uv` for local development.

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

Keep pull requests small and focused. Do not introduce new dependencies without
a clear motivation and maintainer agreement.

Preserve the proxy and discovery invariants:

- no generic `call_upstream_tool`;
- `tools/list` reflects upstream tools;
- no `upstream_` tool-name prefixes;
- upstream proxying uses `fastmcp.server.create_proxy(...)`;
- `FastMCP.as_proxy` stays absent;
- `server.py` stays thin.

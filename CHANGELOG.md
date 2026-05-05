# Changelog

## 0.1.0 - 2026-05-05

### Added

- First end-to-end FastMCP proxy slice.
- Native upstream tool discovery preservation.
- Tool-call middleware for required-field inspection.
- Configurable required fields from upstream schema and YAML tool policy.
- Elicitation flow for missing non-sensitive required fields.
- Structured fallback errors for disabled, unsupported, declined, cancelled, and failed elicitation.
- Sensitive required field guard that blocks elicitation for likely secrets.
- YAML configuration for upstream, proxy, elicitation, and policies.
- End-to-end and payload stability tests.

### Not included

- Multi-upstream routing.
- Advanced ambiguity policy.
- Destructive-action confirmation policy.
- LLM-based policies.
- Auth, rate limiting, persistence, and advanced observability.

### Notes

- This is an internal/preliminary release baseline.
- No package license is declared yet; choose one before publishing outside internal channels.

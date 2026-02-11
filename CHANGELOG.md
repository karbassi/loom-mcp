# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-02-10

### Changed

- Restructure to `src/` layout (`src/loom_mcp/server.py`, `src/loom_mcp/client.py`)
- Move tests to `tests/` directory
- Add hatchling build-system for proper packaging
- Resolve `.env`/`auth.json` paths by walking up to `pyproject.toml`
- Lower `requires-python` from 3.14 to 3.11
- Remove `.python-version` (redundant with `requires-python`)
- Simplify README auth docs, drop parent repo references
- Rename package to `loom-mcp` with console script entry point
- Switch to `@lifespan` decorator
- Add `read`/`write` tags and `timeout=30.0` to all tools
- Use `uvx` entry point in `fastmcp.json`

## [0.1.0] - 2026-02-08

### Added

- FastMCP server exposing 58 tools (29 read, 29 write) for Loom's internal GraphQL API
- Async Python client using httpx with concurrency limiter (5 concurrent requests)
- Auth via `LOOM_COOKIE` env var, `LOOM_AUTH_FILE` path, or `auth.json`
- Auto-load `.env` file for auth config
- Tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`) on all tools
- Input ID validation via `_id()`/`_ids()` helpers to reject injection-style inputs
- `LoomAPIError` and `ToolError` for actionable error messages (401, 403, connection errors)
- Lifespan-managed httpx client with proper cleanup
- 31 tests covering tool registration, annotations, ID validation, happy paths, and error paths
- `fastmcp.json` for FastMCP run support
- Ruff T20 lint rule to ban `print()` in stdio server code

# Project Instructions

## Testing

```sh
uv run --with pytest pytest tests/ -v
```

## Releasing

- Tag versions with annotated tags: `git tag -a v1.2.3 -m "v1.2.3"`
- Do NOT create GitHub releases — tags + CHANGELOG.md is sufficient
- Bump version in both `pyproject.toml` and `src/loom_mcp/server.py`

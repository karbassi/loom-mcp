# Contributing

Thanks for your interest in contributing to mcp-loom!

## Getting started

```sh
git clone git@github.com:karbassi/mcp-loom.git
cd loom-mcp
uv sync
```

## Running tests

```sh
uv run --with pytest --with anyio pytest tests/ -q
```

## Linting and formatting

```sh
uv run --with ruff ruff check src tests
uv run --with ruff ruff format src tests
```

## Submitting changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Ensure tests pass and code is formatted
4. Open a pull request

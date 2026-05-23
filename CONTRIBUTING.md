# Contributing

1. `uv sync --dev`
2. `uv run ruff check src tests && uv run ruff format src tests`
3. `uv run pytest`
4. Open a PR against `main`

Regenerate third-party notices after dependency changes:

```bash
uv run pip-licenses --format=markdown --with-license-file --output-file=THIRD_PARTY_NOTICES.md
```

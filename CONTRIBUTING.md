# Contributing

## Setup

Requires **Python 3.11+**.

```bash
python3.11 -m pip install -e ".[dev]"
cp config/leagues.example.json config/leagues.json   # optional for local scraping
```

## Checks

```bash
python3.11 -m ruff check src tests
python3.11 -m ruff format --check src tests
python3.11 -m pytest
```

Tests use `config/leagues.example.json` by default (see `tests/conftest.py`). No live ImagineSports credentials are required for pytest.

## Pull requests

Open a PR against `main`. CI runs ruff + pytest on push.

Regenerate third-party notices after dependency changes:

```bash
pip-licenses --format=markdown --with-license-file --output-file=THIRD_PARTY_NOTICES.md
```

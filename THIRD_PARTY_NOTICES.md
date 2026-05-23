# Third-Party Notices

This project depends on open-source packages. Run the following after dependency changes:

```bash
pip install pip-licenses
pip-licenses --format=markdown --with-license-file --output-file=THIRD_PARTY_NOTICES.md
```

## Direct runtime dependencies (declared)

| Package | License |
|---------|---------|
| mcp | MIT |
| requests | Apache-2.0 |
| beautifulsoup4 | MIT |
| lxml | BSD-3-Clause |
| pydantic | MIT |

See `pyproject.toml` for pinned versions. CI generates a CycloneDX SBOM artifact on each run.

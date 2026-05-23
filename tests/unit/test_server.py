"""Smoke tests for MCP server module."""

from __future__ import annotations


def test_mcp_server_imports() -> None:
    from dmb_mcp.server import mcp

    assert mcp.name == "dmb"

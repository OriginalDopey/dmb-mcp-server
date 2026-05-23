"""Shared scraper constants derived from settings."""

from __future__ import annotations

from dmb_mcp.settings import Settings, get_settings

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def bind_settings(settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    return {
        "BASE_URL": s.base_url,
        "COOKIE_PATH": s.session_path,
        "REQUEST_DELAY": s.request_delay,
        "REQUEST_TIMEOUT": s.request_timeout,
        "USER_AGENT": USER_AGENT,
    }

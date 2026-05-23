"""HTTP session for ImagineSports scraping."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from dmb_mcp.scraper.constants import USER_AGENT
from dmb_mcp.settings import Settings


def _load_session_class(settings: Settings) -> type:
    body_path = Path(__file__).with_name("_session_body.py")
    namespace: dict[str, Any] = {
        "requests": requests,
        "BeautifulSoup": BeautifulSoup,
        "time": time,
        "quote": quote,
        "Path": Path,
        "USER_AGENT": USER_AGENT,
        "COOKIE_PATH": settings.session_path,
        "REQUEST_DELAY": settings.request_delay,
        "REQUEST_TIMEOUT": settings.request_timeout,
        "BASE_URL": settings.base_url,
    }
    exec(body_path.read_text(), namespace)
    return namespace["ISSession"]


class ISSession:
    """Session with configurable cookie path and rate limits."""

    def __init__(self, cookie: str | None = None, settings: Settings | None = None):
        self._settings = settings or Settings.from_env()
        session_cls = _load_session_class(self._settings)
        self._inner = session_cls(cookie=cookie)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def save_cookie(self, cookie_str: str) -> None:
        path = self._settings.session_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cookie_str.strip())
        path.chmod(0o600)
        self._inner._set_cookie(cookie_str)

    def fetch_psimstats_popup(self, player_url: str, *, public: bool = True):
        safe = (player_url or "").replace(" ", "_")
        encoded = quote(safe, safe="_")
        if public:
            url = (
                f"{self._settings.base_url}/bball/draft/psimstats/popup"
                f"?player_url={encoded}&Catalog=Career&year=&curTeam=&leaguetype=all&mode=public"
            )
        else:
            url = (
                f"{self._settings.base_url}/bball/draft/psimstats/popup"
                f"?player_url={encoded}&Catalog=Career&year="
            )
        return self._inner.get_soup(url)

    def auth_status(self) -> dict[str, str | bool]:
        url = f"{self._settings.base_url}/bball/league/standings?curTeam=TEST"
        _resp, err = self._inner.get(url)
        if err == "AUTH_REQUIRED":
            return {"valid": False, "message": "Session cookie missing or expired"}
        if err:
            return {"valid": False, "message": str(err)}
        return {"valid": True, "message": "Session cookie accepted by ImagineSports"}

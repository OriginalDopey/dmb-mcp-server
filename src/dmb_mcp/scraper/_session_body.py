class ISSession:
    """Manages HTTP requests to imaginesports.com with rate limiting."""

    def __init__(self, cookie=None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.last_request_time = 0
        self._soup_cache = {}

        # Load cookie
        if cookie:
            self._set_cookie(cookie)
        elif COOKIE_PATH.exists():
            saved = COOKIE_PATH.read_text().strip()
            if saved:
                self._set_cookie(saved)

    def reset_cache(self):
        """Clear the per-URL soup cache (call between league refreshes)."""
        self._soup_cache.clear()

    def _set_cookie(self, cookie_str):
        """Set session cookie. Accepts raw cookie header or just the value."""
        cookie_str = cookie_str.strip()
        if "=" in cookie_str and not cookie_str.startswith("session="):
            # Full cookie header: parse all cookies
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    name, val = part.split("=", 1)
                    self.session.cookies.set(name.strip(), val.strip())
        else:
            # Just a session value or session=value
            if cookie_str.startswith("session="):
                cookie_str = cookie_str[8:]
            self.session.cookies.set("session", cookie_str)

    def save_cookie(self, cookie_str):
        """Save cookie to disk for future use."""
        COOKIE_PATH.write_text(cookie_str.strip())
        COOKIE_PATH.chmod(0o600)
        self._set_cookie(cookie_str)
        print(f"Session cookie saved to {COOKIE_PATH}")

    def get(self, url, **kwargs):
        """GET with rate limiting and error handling."""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        try:
            resp = self.session.get(url, **kwargs)
            self.last_request_time = time.time()

            if resp.status_code == 200:
                # Check for login redirect (IS redirects to /reg/public/login)
                if "/login" in resp.url.lower() and "/login" not in url.lower():
                    return None, "AUTH_REQUIRED"
                # Check for archived/bad team errors
                if "Bad teamID" in resp.text or "has been archived" in resp.text:
                    return None, "TEAM_ARCHIVED"
                return resp, None
            elif resp.status_code in (301, 302):
                location = resp.headers.get("Location", "")
                if "login" in location.lower():
                    return None, "AUTH_REQUIRED"
                return None, f"REDIRECT to {location}"
            elif resp.status_code == 403:
                return None, "AUTH_REQUIRED"
            else:
                return None, f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            return None, str(e)

    # URLs containing any of these substrings are guaranteed-once during a
    # refresh (e.g. the cutoff_game_id walk through standings) so we skip
    # caching them to keep memory bounded.
    _CACHE_SKIP_NEEDLES = ("cutoff_game_id=",)

    def _should_cache(self, url):
        return not any(n in url for n in self._CACHE_SKIP_NEEDLES)

    def get_soup(self, url):
        """GET and parse HTML, with per-URL memoization for the lifetime
        of one refresh. Reset between leagues via reset_cache()."""
        cached = self._soup_cache.get(url)
        if cached is not None:
            return cached, None
        resp, err = self.get(url)
        if err:
            return None, err
        try:
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            soup = BeautifulSoup(resp.text, "html.parser")
        if self._should_cache(url):
            self._soup_cache[url] = soup
        return soup, None

    def fetch_psimstats_popup(self, player_url):
        """
        Fetch the Details (psimstats) popup for one player.
        Returns (soup, error). Requires auth if league is private.
        """
        from urllib.parse import quote

        # IS expects player_url like Boileryard_Clarke (underscore)
        safe = (player_url or "").replace(" ", "_")
        encoded = quote(safe, safe="_")
        url = f"{BASE_URL}/bball/draft/psimstats/popup?player_url={encoded}&Catalog=Career&year="
        return self.get_soup(url)

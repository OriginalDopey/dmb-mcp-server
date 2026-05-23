class LeagueScraper:
    """Scrape all data for one IS league."""

    def __init__(self, db: Database, session: ISSession):
        self.db = db
        self.session = session

    def _url(self, path, **params):
        """Build a full IS URL."""
        qs = urlencode(params)
        return f"{BASE_URL}{path}?{qs}" if qs else f"{BASE_URL}{path}"

    def discover_teams(self, entry_team_id):
        """
        Discover all teams in a league starting from one team ID.
        Uses the league batting page (same approach as VBA SetupPages).
        Returns (league_id, teams_list) or (None, error_message).
        """
        url = self._url("/bball/league/batting", curTeam=entry_team_id)
        print(f"  Discovering teams via {url}")
        soup, err = self.session.get_soup(url)
        if err:
            return None, [], f"Failed to load league page: {err}"

        teams = parse_teams_from_league_page(soup)
        league_id = parse_league_id_from_page(soup) or entry_team_id

        if not teams:
            # Try league pitching page as fallback
            url2 = self._url("/bball/league/pitching", curTeam=entry_team_id)
            print(f"  Retrying via pitching page: {url2}")
            soup2, err2 = self.session.get_soup(url2)
            if not err2:
                teams = parse_teams_from_league_page(soup2)

        if not teams:
            return league_id, [], "No teams found — page may require login"

        # Deduplicate (data0 + data1 may overlap)
        seen = set()
        unique_teams = []
        for t in teams:
            if t["team_id"] not in seen:
                seen.add(t["team_id"])
                unique_teams.append(t)

        return league_id, unique_teams, None

    @staticmethod
    def _base_progress(step, total, detail, log_fn):
        """Baseball-themed progress: rounding 1st → 2nd → 3rd → Home."""
        if total <= 0:
            return
        pct = min(100, round(100 * step / total))
        if pct < 25:
            base = "1st"
        elif pct < 50:
            base = "2nd"
        elif pct < 75:
            base = "3rd"
        elif pct < 100:
            base = "Home"
        else:
            base = "HOME!"
        log_fn(f"  [ Rounding {base:4} ] {pct:3}% ({step}/{total}) — {detail}")

    def scrape_league(self, entry_team_id, verbose=True, direct_teams=None, league_name=None):
        """
        Full league scrape: discover teams, then pull ALL available data
        for every team, plus standings, rules, and team info.

        Each unique URL is fetched at most once per call thanks to the
        ISSession soup cache, which is reset on entry.

        Collects:
          - League-level: standings, standings_history, league_rules, team_info
          - Per-team: batter_ratings, pitcher_ratings, fielder_ratings,
                      batting_stats, pitching_stats, rosters,
                      transactions, fielding_stats

        Args:
            entry_team_id: A team ID from the league (used for URL context)
            direct_teams: Optional list of {"team_id": ..., "name": ...}
                         dicts — bypasses league page discovery (useful
                         when league pages need auth but ratings don't)
            league_name: Optional league name for the database
        """
        self.session.reset_cache()
        start_time = time.time()
        log = lambda msg: print(msg) if verbose else None

        log(f"\n{'=' * 60}")
        log(f"  SCRAPING LEAGUE (entry: {entry_team_id})")
        log(f"{'=' * 60}")

        # Step 1: Discover teams (or use direct list)
        if direct_teams:
            league_id = entry_team_id
            teams = direct_teams
            log(f"  Using {len(teams)} directly provided team IDs")
        else:
            league_id, teams, err = self.discover_teams(entry_team_id)
            if err:
                if "AUTH_REQUIRED" in str(err):
                    log("  League page requires login.")
                    log("  Options:")
                    log("    1. Save your IS session cookie:")
                    log("       python3 is_league_scraper.py auth --cookie 'your_cookie'")
                    log("    2. Provide team IDs directly:")
                    log(
                        f"       python3 is_league_scraper.py scrape "
                        f"--team-id {entry_team_id} "
                        f"--team-ids ID1 ID2 ID3 ..."
                    )
                else:
                    log(f"  ERROR: {err}")
                self.db.log_scrape(league_id or entry_team_id, "discover", status=f"error: {err}")
                self.db.commit()
                return False

        log(f"  Found {len(teams)} teams (league: {league_id})")

        # Store league + teams
        self.db.upsert_league(
            league_id, name=league_name, num_teams=len(teams), entry_team_id=entry_team_id
        )
        for t in teams:
            self.db.upsert_team(t["team_id"], league_id, name=t["name"])
            log(f"    {t['name']} ({t['team_id'][:12]}...)")
        self.db.commit()

        total_records = 0
        # Baseball progress: 3 league-level pages + 8 pages per team (fixed count)
        num_teams = len(teams)
        total_steps = 3 + 8 * num_teams
        current_step = 0

        # ── Step 2: League-level scrapes ─────────────────────────────

        # Standings (current snapshot + append to history)
        standings = self._scrape_standings(entry_team_id, league_id, teams)
        current_step += 1
        self._base_progress(current_step, total_steps, "Standings", log)
        if standings:
            n = self.db.clear_and_insert("standings", league_id, standings)
            total_records += n
            log(f"    {n} standing records (current snapshot)")

            # Also append to standings_history (time-series)
            history_rows = []
            for s in standings:
                h = dict(s)
                h["snapshot_at"] = h.pop("scraped_at")
                # Remove 'id' if present (auto-increment)
                h.pop("id", None)
                history_rows.append(h)
            nh = self.db.append_standings_history(history_rows)
            total_records += nh
            log(f"    {nh} standings history records (appended)")
        self.db.commit()

        # League rules
        log("\n  Scraping league rules...")
        rules = self._scrape_league_rules(entry_team_id, league_id)
        if rules:
            self.db.upsert_league_rules(league_id, rules)
            total_records += len(rules)
            log(f"    {len(rules)} rules/settings")
            # Update league name from rules if we found one
            if "league_name" in rules and not league_name:
                self.db.upsert_league(league_id, name=rules["league_name"])
        self.db.commit()
        current_step += 1
        self._base_progress(current_step, total_steps, "League rules", log)

        # Team info (parks, balances, owners from scouting page)
        log("\n  Scraping team info (parks, owners)...")
        n_info = self._scrape_team_info(entry_team_id, league_id, teams)
        total_records += n_info
        log(f"    {n_info} teams with park/owner info")
        self.db.commit()
        current_step += 1
        self._base_progress(current_step, total_steps, "Team info (parks, owners)", log)

        # ── Step 3: Per-team scraping ────────────────────────────────
        outs = 0
        for i, team in enumerate(teams, 1):
            tid = team["team_id"]
            tname = team["name"]
            log(f"\n  [{i}/{len(teams)}] {tname}")

            def do_step(label, scrape_fn, table, is_roster=False):
                nonlocal total_records, current_step, outs
                try:
                    data = scrape_fn(tid, entry_team_id, league_id)
                    if data:
                        n = self.db.replace_team_data(table, tid, data)
                        total_records += n
                        if is_roster:
                            log(
                                f"    {label}: {n} players "
                                f"(${sum(r.get('salary_num', 0) for r in data):,} total)"
                            )
                        else:
                            log(f"    {label}: {n} records")
                    current_step += 1
                    self._base_progress(
                        current_step, total_steps, f"Team {i}/{num_teams}: {tname} — {label}", log
                    )
                except Exception as e:
                    if verbose:
                        print(f"    You're out! {label} — {e}")
                    outs += 1
                    current_step += 1
                    self._base_progress(
                        current_step,
                        total_steps,
                        f"Team {i}/{num_teams}: {tname} — {label} (out)",
                        log,
                    )

            do_step("batter ratings", self._scrape_batter_ratings, "batter_ratings")
            do_step("pitcher ratings", self._scrape_pitcher_ratings, "pitcher_ratings")
            do_step("fielder ratings", self._scrape_fielder_ratings, "fielder_ratings")
            do_step("batting stats", self._scrape_batting_stats, "batting_stats")
            do_step("pitching stats", self._scrape_pitching_stats, "pitching_stats")
            do_step("roster", self._scrape_roster, "rosters", is_roster=True)
            # Fetch Details (psimstats) popup per player for projected stats/splits
            try:
                n_psim = self._scrape_team_psimstats(tid, entry_team_id, league_id, verbose=verbose)
                if n_psim and verbose:
                    log(f"    psimstats: {n_psim} players updated")
            except Exception as e:
                if verbose:
                    print(f"    psimstats (skipped): {e}")
            do_step("transactions", self._scrape_transactions, "transactions")
            do_step("fielding stats", self._scrape_fielding_stats, "fielding_stats")
            self.db.commit()

        # ── Step 4: Finalise ─────────────────────────────────────────
        current_step = total_steps
        self._base_progress(current_step, total_steps, "HOME!", log)
        duration = time.time() - start_time
        self.db.update_league_scraped(league_id)
        self.db.log_scrape(
            league_id,
            "full_scrape",
            teams_found=len(teams),
            records=total_records,
            duration_s=round(duration, 1),
        )
        self.db.commit()

        log(f"\n{'=' * 60}")
        log(f"  Safe at home! {len(teams)} teams, {total_records} records in {duration:.1f}s")
        if outs:
            log(f"  You're out: {outs} error(s) — check log above.")
        log(f"  Database: {self.db.db_path}")
        log(f"{'=' * 60}\n")
        return True

    # ── Per-page scrapers ──────────────────────────────────────────

    def _scrape_standings(self, entry_team_id, league_id, teams):
        url = self._url("/bball/league/standings", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Standings error: {err}")
            return []

        records = parse_standings(soup, league_id)

        # Resolve team_ids by matching team names
        team_name_map = {t["name"].lower().strip(): t["team_id"] for t in teams}
        for rec in records:
            tname = rec.pop("_team_name", "").lower().strip()
            rec["team_id"] = team_name_map.get(tname, "")
            # Fuzzy match if exact fails
            if not rec["team_id"]:
                for stored_name, stored_id in team_name_map.items():
                    if tname in stored_name or stored_name in tname:
                        rec["team_id"] = stored_id
                        break

        return records

    def _scrape_batter_ratings(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/batter_ratings", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Batter ratings error: {err}")
            return []
        return parse_batter_ratings(soup, team_id, league_id)

    def _scrape_pitcher_ratings(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/pitcher_ratings", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Pitcher ratings error: {err}")
            return []
        return parse_pitcher_ratings(soup, team_id, league_id)

    def _scrape_fielder_ratings(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/fielder_ratings", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Fielder ratings error: {err}")
            return []
        return parse_fielder_ratings(soup, team_id, league_id)

    def _scrape_batting_stats(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/batting", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Batting stats error: {err}")
            return []
        return parse_batting_stats(soup, team_id, league_id)

    def _scrape_pitching_stats(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/pitching", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Pitching stats error: {err}")
            return []
        return parse_pitching_stats(soup, team_id, league_id)

    def _scrape_roster(self, team_id, entry_team_id, league_id):
        """Fetch the roster page once and persist both roster rows and finance.

        The roster header carries Total Value, Cash Balance, and (when the
        league has loans and the team is owned by the viewer) Max Loan. We
        scrape it as a side effect so we never refetch the page just for
        finance data.
        """
        url = self._url("/bball/team/roster", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Roster error: {err}")
            return []
        records = parse_roster(soup, team_id, league_id)
        finance = parse_finance_from_text(soup)
        roster_salary = sum(r.get("salary_num", 0) or 0 for r in records)
        if roster_salary:
            finance.setdefault("roster_salary_num", roster_salary)
            finance.setdefault("total_value_num", roster_salary)
        if finance:
            try:
                self.db.update_team_finance(team_id, league_id, finance)
            except Exception as exc:
                print(f"    Finance update skipped ({team_id[:8]}…): {exc}")
        return records

    def _scrape_team_psimstats(self, team_id, entry_team_id, league_id, verbose=True):
        """
        For each roster player with player_url, fetch Details popup and upsert
        player_psimstats. Call after roster is in DB. Returns count of players updated.
        """
        log = lambda msg: print(msg) if verbose else None
        rows = self.db.execute(
            "SELECT player_url FROM rosters WHERE team_id = ? AND COALESCE(player_url,'') != ''",
            [team_id],
        ).fetchall()
        count = 0
        for row in rows:
            player_url = (row[0] or "").strip()
            if not player_url:
                continue
            soup, err = self.session.fetch_psimstats_popup(player_url)
            if err:
                continue
            data = parse_psimstats_popup(soup)
            if data:
                self.db.upsert_player_psimstats(player_url, data)
                count += 1
        self.db.commit()
        return count

    def _scrape_transactions(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/transactions", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Transactions error: {err}")
            return []
        return parse_transactions(soup, team_id, league_id)

    def _scrape_fielding_stats(self, team_id, entry_team_id, league_id):
        url = self._url("/bball/team/fielding", teamID=team_id, curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Fielding stats error: {err}")
            return []
        return parse_fielding_stats(soup, team_id, league_id)

    # ── Game-by-game standings stepping ───────────────────────────

    def scrape_game_standings(self, entry_team_id, league_id, verbose=True):
        """
        Step backwards through standings using cutoff_game_id to build
        game-by-game history for ALL teams in a league.

        Smart caching: stops when it hits a game_id already in the DB.
        On first run, walks all the way to game 1.
        On subsequent runs, only fetches new games since last scrape.

        Data yield: 12 teams × 15+ columns per API call.
        """
        log = lambda msg: print(msg) if verbose else None

        max_existing = self.db.get_max_game_id(league_id)
        min_existing = self.db.get_min_game_id(league_id)
        existing_count = self.db.get_game_id_count(league_id)

        if max_existing:
            log(f"    Cache: {existing_count} snapshots (ids {min_existing}..{max_existing})")

        # ── Step A: Find the latest game_id ──────────────────────
        # Load the regular standings page (no cutoff_game_id).
        # It shows the current/final standings and has a Previous
        # link whose game_id lets us derive the latest game_id.
        url = self._url("/bball/league/standings", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            log(f"    Game standings error: {err}")
            return 0

        records, prev_gid, next_gid, date_label = parse_standings_full(soup, league_id)

        if not records:
            log("    No standings data on page")
            return 0

        # The regular page IS the final game. Previous points to
        # the second-to-last game. So latest = prev + 1.
        if prev_gid is not None:
            latest_gid = prev_gid + 1
        else:
            log("    No Previous link found — league may have only 1 game or isn't started")
            return 0

        log(f"    Latest game_id: {latest_gid} ({date_label})")

        # Already fully up-to-date?
        if max_existing and latest_gid <= max_existing:
            log(f"    Already up to date (latest={latest_gid}, have={max_existing})")
            return 0

        # ── Step B: Store the latest standings ───────────────────
        total_stored = 0
        total_pages = 0
        batch = []

        for r in records:
            r["game_id"] = latest_gid
            r["date_label"] = date_label
            batch.append(r)
        total_pages += 1

        # ── Step C: Walk backwards via Previous link ─────────────
        current_gid = prev_gid
        first_gid = latest_gid

        while current_gid is not None:
            # Smart stop: already have this game_id or earlier
            if max_existing and current_gid <= max_existing:
                log(f"    Hit cached data at game_id={current_gid}")
                break

            total_pages += 1
            if total_pages % 50 == 0:
                log(
                    f"    Progress: {total_pages} pages, "
                    f"game_id={current_gid}, "
                    f"{len(batch)} records buffered..."
                )

            url = self._url(
                "/bball/league/standings", curTeam=entry_team_id, cutoff_game_id=current_gid
            )
            soup, err = self.session.get_soup(url)
            if err:
                log(f"    Error at game_id={current_gid}: {err}")
                break

            recs, new_prev, _, dl = parse_standings_full(soup, league_id)

            for r in recs:
                r["game_id"] = current_gid
                r["date_label"] = dl
                batch.append(r)

            # Commit in batches (every ~300 records ≈ 25 pages)
            if len(batch) >= 300:
                n = self.db.insert_game_standings_batch(batch)
                total_stored += n
                self.db.commit()
                batch = []

            # No Previous link → we've reached the first game
            if new_prev is None:
                first_gid = current_gid
                break

            current_gid = new_prev

        # Final batch
        if batch:
            n = self.db.insert_game_standings_batch(batch)
            total_stored += n
            self.db.commit()

        log(
            f"    Stored {total_stored} records "
            f"({total_pages} pages, "
            f"ids {first_gid}..{latest_gid})"
        )
        return total_stored

    # ── Smart refresh (weekly run) ─────────────────────────────────

    def refresh_league(self, entry_team_id, verbose=True):
        """
        Smart weekly refresh for a single league.

        Fetches ALL data needed for the analysis dashboard:
          - Current standings (always refresh)
          - Game-by-game standings history (smart: only new game_ids)
          - Batting/pitching/fielding stats (always refresh — change weekly)
          - Rosters & transactions (always refresh)
          - Ratings (skip if already have — don't change mid-season)
          - League rules & team info (skip if already have — static)

        One run fills every DB table the dashboard needs.
        """
        start_time = time.time()
        log = lambda msg: print(msg) if verbose else None

        # ── Discover league + teams ──────────────────────────────
        league_id, teams, err = self.discover_teams(entry_team_id)
        if err:
            log(f"  ERROR: {err}")
            return False

        log(f"\n  League: {league_id[:20]}... ({len(teams)} teams)")

        self.db.upsert_league(league_id, num_teams=len(teams), entry_team_id=entry_team_id)
        for t in teams:
            self.db.upsert_team(t["team_id"], league_id, name=t["name"])
        self.db.commit()

        total = 0
        calls_saved = 0

        # ── 1. Current standings (always) ────────────────────────
        log("  [1/7] Current standings...")
        standings = self._scrape_standings(entry_team_id, league_id, teams)
        if standings:
            n = self.db.clear_and_insert("standings", league_id, standings)
            total += n
            # Append to history
            history = []
            for s in standings:
                h = dict(s)
                h["snapshot_at"] = h.pop("scraped_at")
                h.pop("id", None)
                history.append(h)
            self.db.append_standings_history(history)
            log(f"    {n} teams")
        self.db.commit()

        # ── 2. Game-by-game standings (smart cache) ──────────────
        log("  [2/7] Game-by-game standings...")
        n = self.scrape_game_standings(entry_team_id, league_id, verbose=verbose)
        total += n

        # ── 3. League rules (skip if cached) ─────────────────────
        if not self.db.has_static_data(league_id, "league_rules"):
            log("  [3/7] League rules...")
            rules = self._scrape_league_rules(entry_team_id, league_id)
            if rules:
                self.db.upsert_league_rules(league_id, rules)
                total += len(rules)
                log(f"    {len(rules)} rules")
        else:
            calls_saved += 1
            log("  [3/7] League rules: cached")

        # ── 4. Team info (skip if cached) ────────────────────────
        if not self.db.has_static_data(league_id, "team_info"):
            log("  [4/7] Team info (parks, owners)...")
            n = self._scrape_team_info(entry_team_id, league_id, teams)
            total += n
            log(f"    {n} teams")
        else:
            calls_saved += 1
            log("  [4/7] Team info: cached")
        self.db.commit()

        # ── 5-7. Per-team data ───────────────────────────────────
        has_ratings = self.db.has_static_data(league_id, "batter_ratings")
        if has_ratings:
            calls_saved += len(teams) * 3
            log(f"  [5/7] Ratings: cached ({len(teams)} teams × 3)")

        for i, team in enumerate(teams, 1):
            tid = team["team_id"]
            tname = team["name"]
            parts = []

            # Ratings: static, skip if present
            if not has_ratings:
                for fn, tbl, lbl in [
                    (self._scrape_batter_ratings, "batter_ratings", "bat"),
                    (self._scrape_pitcher_ratings, "pitcher_ratings", "pit"),
                    (self._scrape_fielder_ratings, "fielder_ratings", "fld"),
                ]:
                    data = fn(tid, entry_team_id, league_id)
                    if data:
                        n = self.db.replace_team_data(tbl, tid, data)
                        total += n
                        parts.append(f"{lbl}={n}")

            # Stats: always refresh (change weekly)
            for fn, tbl, lbl in [
                (self._scrape_batting_stats, "batting_stats", "bst"),
                (self._scrape_pitching_stats, "pitching_stats", "pst"),
                (self._scrape_fielding_stats, "fielding_stats", "fst"),
            ]:
                data = fn(tid, entry_team_id, league_id)
                if data:
                    n = self.db.replace_team_data(tbl, tid, data)
                    total += n
                    parts.append(f"{lbl}={n}")

            # Roster + transactions: always refresh
            roster = self._scrape_roster(tid, entry_team_id, league_id)
            if roster:
                n = self.db.replace_team_data("rosters", tid, roster)
                total += n
                parts.append(f"ros={n}")

            txns = self._scrape_transactions(tid, entry_team_id, league_id)
            if txns:
                n = self.db.replace_team_data("transactions", tid, txns)
                total += n
                parts.append(f"txn={n}")

            self.db.commit()
            log(f"  [{i}/{len(teams)}] {tname}: {', '.join(parts)}")

        # ── Done ─────────────────────────────────────────────────
        duration = time.time() - start_time
        self.db.update_league_scraped(league_id)
        self.db.log_scrape(
            league_id,
            "refresh",
            teams_found=len(teams),
            records=total,
            duration_s=round(duration, 1),
        )
        self.db.commit()

        log(
            f"\n  Done: {total:,} records in {duration:.0f}s"
            f" ({calls_saved} API calls saved by caching)"
        )
        return True

    def _resolve_owner_team_canonical_id(self, entry_team_id, teams):
        """
        curTeam in URLs is not always the same token as team_id in league tables.
        Resolve to the canonical team_id used in game_standings / teams.

        Prefer the league batting row whose links include this curTeam (session
        context for the owner's team). daily_recap link order is unreliable.
        """
        for t in teams:
            if t["team_id"] == entry_team_id:
                return entry_team_id
        known = {t["team_id"] for t in teams}
        name_map = {t["name"].strip().lower(): t["team_id"] for t in teams}
        url = self._url("/bball/league/batting", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if not err and soup:
            needle = f"curTeam={entry_team_id}"
            for row in soup.find_all("tr", class_=lambda c: c and ("data0" in c or "data1" in c)):
                row_links = row.find_all("a", href=True)
                if not any(needle in (a.get("href") or "") for a in row_links):
                    continue
                for link in row_links:
                    href = link.get("href") or ""
                    if href.startswith("/"):
                        href = f"{BASE_URL}{href}"
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    tid = (qs.get("teamID") or [None])[0]
                    if tid and tid in known:
                        return tid
                for link in row_links:
                    tname = link.get_text(strip=True).lower()
                    if tname in name_map:
                        return name_map[tname]
        # Fallback: daily_recap (first teamID link that appears in this league)
        url = self._url("/bball/team/daily_recap", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err or not soup:
            return entry_team_id
        candidates = []
        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            if "teamID=" not in href:
                continue
            if href.startswith("/"):
                href = f"{BASE_URL}{href}"
            parsed = urlparse(href)
            tid = (parse_qs(parsed.query).get("teamID") or [None])[0]
            if tid and tid not in candidates:
                candidates.append(tid)
        for tid in candidates:
            if tid in known:
                return tid
        return candidates[0] if candidates else entry_team_id

    def refresh_league_tracker_only(self, entry_team_id, verbose=True):
        """
        Minimal refresh for the Season Tracker: standings, game-by-game
        standings, scouting metadata, roster (with finance side-effect),
        and batting/pitching/fielding stats. Skips ratings, transactions,
        league rules, and player psimstats popups.

        Each unique URL is fetched at most once per call: the per-URL soup
        cache on ISSession dedupes overlap between _scrape_standings and
        scrape_game_standings.
        """
        start_time = time.time()
        log = lambda msg: print(msg) if verbose else None
        self.session.reset_cache()

        league_id, teams, err = self.discover_teams(entry_team_id)
        if err:
            log(f"  ERROR: {err}")
            return False

        owner_team_id = self._resolve_owner_team_canonical_id(entry_team_id, teams)

        log(f"\n  League: {league_id[:20]}... ({len(teams)} teams)")
        self.db.upsert_league(
            league_id,
            num_teams=len(teams),
            entry_team_id=entry_team_id,
            owner_team_id=owner_team_id,
        )
        for t in teams:
            self.db.upsert_team(t["team_id"], league_id, name=t["name"])
        self.db.commit()

        total = 0

        # 1. Current standings
        log("  [1/4] Current standings...")
        standings = self._scrape_standings(entry_team_id, league_id, teams)
        if standings:
            n = self.db.clear_and_insert("standings", league_id, standings)
            total += n
            history = []
            for s in standings:
                h = dict(s)
                h["snapshot_at"] = h.pop("scraped_at")
                h.pop("id", None)
                history.append(h)
            self.db.append_standings_history(history)
            log(f"    {n} teams")
        self.db.commit()

        # 2. Game-by-game standings (incremental)
        log("  [2/4] Game-by-game standings...")
        n = self.scrape_game_standings(entry_team_id, league_id, verbose=verbose)
        total += n

        # 3. Public scouting metadata (parks, owners, divisions for all 12 teams in 1 call)
        log("  [3/4] Team metadata (scouting page)...")
        n_info = self._scrape_team_info(entry_team_id, league_id, teams)
        total += n_info
        log(f"    scouting metadata: {n_info} teams")
        self.db.commit()

        # 4. Per-team pages: roster (also captures finance) + batting/pitching/fielding
        log("  [4/4] Roster + batting/pitching/fielding stats...")
        for i, team in enumerate(teams, 1):
            tid = team["team_id"]
            tname = team["name"]
            parts = []
            roster = self._scrape_roster(tid, entry_team_id, league_id)
            if roster:
                n = self.db.replace_team_data("rosters", tid, roster)
                total += n
                parts.append(f"rost={n}")
            for fn, tbl, lbl in [
                (self._scrape_batting_stats, "batting_stats", "bst"),
                (self._scrape_pitching_stats, "pitching_stats", "pst"),
                (self._scrape_fielding_stats, "fielding_stats", "fst"),
            ]:
                data = fn(tid, entry_team_id, league_id)
                if data:
                    n = self.db.replace_team_data(tbl, tid, data)
                    total += n
                    parts.append(f"{lbl}={n}")
            self.db.commit()
            log(f"    [{i}/{len(teams)}] {tname}: {', '.join(parts)}")

        duration = time.time() - start_time
        self.db.update_league_scraped(league_id)
        self.db.log_scrape(
            league_id,
            "tracker_refresh",
            teams_found=len(teams),
            records=total,
            duration_s=round(duration, 1),
        )
        self.db.commit()
        log(f"\n  Done: {total:,} records in {duration:.0f}s")
        return True

    # ── Internal page scrapers ─────────────────────────────────────

    def _scrape_league_rules(self, entry_team_id, league_id):
        url = self._url("/bball/league/rules", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    League rules error: {err}")
            return {}
        return parse_league_rules(soup, league_id)

    def _scrape_team_info(self, entry_team_id, league_id, teams):
        """Scrape team info (parks, balances, owners) from scouting page."""
        url = self._url("/bball/league/scouting", curTeam=entry_team_id)
        soup, err = self.session.get_soup(url)
        if err:
            print(f"    Team info error: {err}")
            return 0

        info_list = parse_team_info_from_scouting(soup, league_id)
        if not info_list:
            return 0

        # Match info to team_ids by team name
        team_name_map = {t["name"].lower().strip(): t["team_id"] for t in teams}
        stored = 0
        for info in info_list:
            tname = info["team_name"].lower().strip()
            tid = team_name_map.get(tname, "")
            # Fuzzy match
            if not tid:
                for stored_name, stored_id in team_name_map.items():
                    if tname in stored_name or stored_name in tname:
                        tid = stored_id
                        break
            if tid:
                self.db.upsert_team_info(tid, league_id, info)
                stored += 1

        return stored


# ═══════════════════════════════════════════════════════════════════════
#  TOURNAMENT TRACKER
# ═══════════════════════════════════════════════════════════════════════

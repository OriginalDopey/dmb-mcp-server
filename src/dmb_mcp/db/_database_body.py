class Database:
    """SQLite database manager for IS scouting data."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        # Migration: add player_url to rosters if missing (for psimstats links)
        try:
            cur = self.conn.execute("PRAGMA table_info(rosters)")
            cols = [row[1] for row in cur.fetchall()]
            if "player_url" not in cols:
                self.conn.execute("ALTER TABLE rosters ADD COLUMN player_url TEXT")
        except Exception:
            pass
        try:
            cur = self.conn.execute("PRAGMA table_info(leagues)")
            lcols = [row[1] for row in cur.fetchall()]
            if "owner_team_id" not in lcols:
                self.conn.execute("ALTER TABLE leagues ADD COLUMN owner_team_id TEXT")
        except Exception:
            pass
        try:
            cur = self.conn.execute("PRAGMA table_info(team_info)")
            icols = [row[1] for row in cur.fetchall()]
            finance_cols = {
                "balance_num": "INTEGER",
                "roster_salary_num": "INTEGER",
                "total_value_num": "INTEGER",
                "upcoming_payment_total_num": "INTEGER",
                "max_loan_num": "INTEGER",
            }
            for col, typ in finance_cols.items():
                if col not in icols:
                    self.conn.execute(f"ALTER TABLE team_info ADD COLUMN {col} {typ}")
        except Exception:
            pass
        self.conn.commit()

    def execute(self, sql, params=None):
        return self.conn.execute(sql, params or [])

    def executemany(self, sql, params_list):
        return self.conn.executemany(sql, params_list)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ── League operations ──────────────────────────────────────────

    def upsert_league(
        self, league_id, name=None, num_teams=None, era=None, entry_team_id=None, owner_team_id=None
    ):
        self.execute(
            """
            INSERT INTO leagues (league_id, name, num_teams, era, entry_team_id, owner_team_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(league_id) DO UPDATE SET
                name = COALESCE(excluded.name, leagues.name),
                num_teams = COALESCE(excluded.num_teams, leagues.num_teams),
                era = COALESCE(excluded.era, leagues.era),
                entry_team_id = COALESCE(excluded.entry_team_id, leagues.entry_team_id),
                owner_team_id = COALESCE(excluded.owner_team_id, leagues.owner_team_id)
        """,
            [league_id, name, num_teams, era, entry_team_id, owner_team_id],
        )

    def update_league_scraped(self, league_id):
        now = datetime.now(timezone.utc).isoformat()
        self.execute("UPDATE leagues SET last_scraped = ? WHERE league_id = ?", [now, league_id])

    def get_league(self, league_id):
        return self.execute("SELECT * FROM leagues WHERE league_id = ?", [league_id]).fetchone()

    def get_all_leagues(self):
        return self.execute("SELECT * FROM leagues ORDER BY name").fetchall()

    # ── Team operations ────────────────────────────────────────────

    def upsert_team(self, team_id, league_id, name=None, owner=None, division=None):
        self.execute(
            """
            INSERT INTO teams (team_id, league_id, name, owner, division)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                league_id = COALESCE(excluded.league_id, teams.league_id),
                name = COALESCE(excluded.name, teams.name),
                owner = COALESCE(excluded.owner, teams.owner),
                division = COALESCE(excluded.division, teams.division)
        """,
            [team_id, league_id, name, owner, division],
        )

    def get_teams_for_league(self, league_id):
        return self.execute(
            "SELECT * FROM teams WHERE league_id = ? ORDER BY name", [league_id]
        ).fetchall()

    # ── Bulk data insert (ratings, stats, standings) ───────────────

    def clear_and_insert(self, table, league_id, rows):
        """Replace all rows for a league in a table (fresh snapshot)."""
        self.execute(f"DELETE FROM {table} WHERE league_id = ?", [league_id])
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        self.executemany(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        return len(rows)

    def get_table_data(self, table, league_id):
        return self.execute(
            f"SELECT * FROM {table} WHERE league_id = ? ORDER BY id", [league_id]
        ).fetchall()

    # ── Tournament operations ──────────────────────────────────────

    def add_tournament_league(
        self, tournament_name, round_name, entry_team_id, league_id=None, league_name=None
    ):
        now = datetime.now(timezone.utc).isoformat()
        self.execute(
            """
            INSERT OR REPLACE INTO tournaments
                (name, round, league_id, entry_team_id, league_name, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            [tournament_name, round_name, league_id, entry_team_id, league_name, now],
        )

    def get_tournament_leagues(self, tournament_name, round_name=None):
        if round_name:
            return self.execute(
                "SELECT * FROM tournaments WHERE name = ? AND round = ?",
                [tournament_name, round_name],
            ).fetchall()
        return self.execute(
            "SELECT * FROM tournaments WHERE name = ? ORDER BY round", [tournament_name]
        ).fetchall()

    def get_tournaments(self):
        return self.execute(
            "SELECT DISTINCT name, round FROM tournaments ORDER BY name, round"
        ).fetchall()

    # ── Scrape log ─────────────────────────────────────────────────

    def log_scrape(self, league_id, action, teams_found=0, records=0, duration_s=0, status="ok"):
        now = datetime.now(timezone.utc).isoformat()
        self.execute(
            """
            INSERT INTO scrape_log
                (league_id, action, teams_found, records, scraped_at,
                 duration_s, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            [league_id, action, teams_found, records, now, duration_s, status],
        )

    # ── Roster / Transaction / Team-info operations ────────────────

    def insert_rows(self, table, rows):
        """Insert rows into a table (generic). Returns count inserted."""
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        self.executemany(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows],
        )
        return len(rows)

    def replace_team_data(self, table, team_id, rows):
        """Delete existing rows for a team, then insert new rows."""
        self.execute(f"DELETE FROM {table} WHERE team_id = ?", [team_id])
        return self.insert_rows(table, rows)

    def upsert_league_rules(self, league_id, rules_dict):
        """Upsert league rules as key/value pairs."""
        now = datetime.now(timezone.utc).isoformat()
        for key, val in rules_dict.items():
            self.execute(
                """
                INSERT INTO league_rules (league_id, scraped_at, rule_key, rule_value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(league_id, rule_key) DO UPDATE SET
                    rule_value = excluded.rule_value,
                    scraped_at = excluded.scraped_at
            """,
                [league_id, now, key, val],
            )

    def upsert_team_info(self, team_id, league_id, info):
        """Upsert team info (park, abbreviation, balance, owner, finance)."""
        now = datetime.now(timezone.utc).isoformat()
        self.execute(
            """
            INSERT INTO team_info
                (team_id, league_id, scraped_at, abbreviation, balance,
                 balance_num, roster_salary_num, total_value_num,
                 upcoming_payment_total_num, max_loan_num,
                 park, owner, division)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, league_id) DO UPDATE SET
                abbreviation = excluded.abbreviation,
                balance = excluded.balance,
                balance_num = COALESCE(excluded.balance_num, team_info.balance_num),
                roster_salary_num = COALESCE(excluded.roster_salary_num, team_info.roster_salary_num),
                total_value_num = COALESCE(excluded.total_value_num, team_info.total_value_num),
                upcoming_payment_total_num = COALESCE(excluded.upcoming_payment_total_num, team_info.upcoming_payment_total_num),
                max_loan_num = COALESCE(excluded.max_loan_num, team_info.max_loan_num),
                park = excluded.park,
                owner = excluded.owner,
                division = excluded.division,
                scraped_at = excluded.scraped_at
        """,
            [
                team_id,
                league_id,
                now,
                info.get("abbreviation", ""),
                info.get("balance", ""),
                info.get("balance_num"),
                info.get("roster_salary_num"),
                info.get("total_value_num"),
                info.get("upcoming_payment_total_num"),
                info.get("max_loan_num"),
                info.get("park", ""),
                info.get("owner", ""),
                info.get("division", ""),
            ],
        )

    def update_team_finance(self, team_id, league_id, finance):
        """Best-effort update for finance fields discovered outside scouting."""
        if not finance:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        self.execute(
            """
            INSERT INTO team_info
                (team_id, league_id, scraped_at, balance, balance_num,
                 roster_salary_num, total_value_num,
                 upcoming_payment_total_num, max_loan_num)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, league_id) DO UPDATE SET
                scraped_at = excluded.scraped_at,
                balance = COALESCE(excluded.balance, team_info.balance),
                balance_num = COALESCE(excluded.balance_num, team_info.balance_num),
                roster_salary_num = COALESCE(excluded.roster_salary_num, team_info.roster_salary_num),
                total_value_num = COALESCE(excluded.total_value_num, team_info.total_value_num),
                upcoming_payment_total_num = COALESCE(excluded.upcoming_payment_total_num, team_info.upcoming_payment_total_num),
                max_loan_num = COALESCE(excluded.max_loan_num, team_info.max_loan_num)
        """,
            [
                team_id,
                league_id,
                now,
                finance.get("balance"),
                finance.get("balance_num"),
                finance.get("roster_salary_num"),
                finance.get("total_value_num"),
                finance.get("upcoming_payment_total_num"),
                finance.get("max_loan_num"),
            ],
        )
        return 1

    def append_standings_history(self, rows):
        """Append a standings snapshot (never overwrites)."""
        return self.insert_rows("standings_history", rows)

    def upsert_player_psimstats(self, player_url, data):
        """Upsert one row in player_psimstats (projected stats from Details popup)."""
        now = datetime.now(timezone.utc).isoformat()
        self.execute(
            """
            INSERT INTO player_psimstats
                (player_url, scraped_at, obp, rc, rc600, ba, slg,
                 vs_lhp_obp, vs_lhp_rc, vs_rhp_obp, vs_rhp_rc, raw_stats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_url) DO UPDATE SET
                scraped_at = excluded.scraped_at,
                obp = excluded.obp,
                rc = excluded.rc,
                rc600 = excluded.rc600,
                ba = excluded.ba,
                slg = excluded.slg,
                vs_lhp_obp = excluded.vs_lhp_obp,
                vs_lhp_rc = excluded.vs_lhp_rc,
                vs_rhp_obp = excluded.vs_rhp_obp,
                vs_rhp_rc = excluded.vs_rhp_rc,
                raw_stats = excluded.raw_stats
        """,
            [
                player_url,
                now,
                data.get("obp"),
                data.get("rc"),
                data.get("rc600"),
                data.get("ba"),
                data.get("slg"),
                data.get("vs_lhp_obp"),
                data.get("vs_lhp_rc"),
                data.get("vs_rhp_obp"),
                data.get("vs_rhp_rc"),
                data.get("raw_stats"),
            ],
        )

    # ── Game standings operations ──────────────────────────────────

    def get_max_game_id(self, league_id):
        """Get the highest game_id stored for a league."""
        row = self.execute(
            "SELECT MAX(game_id) as mx FROM game_standings WHERE league_id = ?", [league_id]
        ).fetchone()
        return row["mx"] if row and row["mx"] else None

    def get_min_game_id(self, league_id):
        """Get the lowest game_id stored for a league."""
        row = self.execute(
            "SELECT MIN(game_id) as mn FROM game_standings WHERE league_id = ?", [league_id]
        ).fetchone()
        return row["mn"] if row and row["mn"] else None

    def get_game_id_count(self, league_id):
        """Count distinct game_ids stored for a league."""
        row = self.execute(
            "SELECT COUNT(DISTINCT game_id) as c FROM game_standings WHERE league_id = ?",
            [league_id],
        ).fetchone()
        return row["c"] if row else 0

    def insert_game_standings_batch(self, rows):
        """Insert game standings, silently skipping duplicates.
        Uses INSERT OR IGNORE to skip any (team_id, league_id, game_id)
        that already exists."""
        if not rows:
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT OR IGNORE INTO game_standings ({col_names}) VALUES ({placeholders})"
        before = self.execute("SELECT COUNT(*) as c FROM game_standings").fetchone()["c"]
        self.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        after = self.execute("SELECT COUNT(*) as c FROM game_standings").fetchone()["c"]
        return after - before

    def has_static_data(self, league_id, table):
        """Check if we already have data for a league in a given table."""
        row = self.execute(
            f"SELECT COUNT(*) as c FROM {table} WHERE league_id = ?", [league_id]
        ).fetchone()
        return row["c"] > 0 if row else False

    # ── Summary queries ────────────────────────────────────────────

    def league_summary(self, league_id):
        """Return a dict summarising what's stored for a league."""
        tables = [
            "batter_ratings",
            "pitcher_ratings",
            "fielder_ratings",
            "batting_stats",
            "pitching_stats",
            "standings",
            "rosters",
            "transactions",
            "team_info",
            "fielding_stats",
            "standings_history",
            "game_standings",
        ]
        summary = {}
        for t in tables:
            row = self.execute(
                f"SELECT COUNT(*) as cnt FROM {t} WHERE league_id = ?", [league_id]
            ).fetchone()
            summary[t] = row["cnt"] if row else 0
        return summary

"""Read-only query helpers over SQLite."""

from __future__ import annotations

from typing import Any

from dmb_mcp.db.database import Database
from dmb_mcp.models import RosterPlayer, StandingsRow, TeamFinance


class Repository:
    def __init__(self, db: Database):
        self.db = db

    def standings(self, league_id: str) -> list[StandingsRow]:
        rows = self.db.execute(
            """
            SELECT s.*, COALESCE(t.name, '') AS team_name
            FROM standings s
            LEFT JOIN teams t ON t.team_id = s.team_id
            WHERE s.league_id = ?
            ORDER BY s.pct DESC, s.w DESC
            """,
            [league_id],
        ).fetchall()
        out: list[StandingsRow] = []
        for row in rows:
            out.append(
                StandingsRow(
                    team_id=row["team_id"] or "",
                    team_name=row["team_name"] or "",
                    division=row["division"] or "",
                    wins=row["w"] or 0,
                    losses=row["l"] or 0,
                    pct=row["pct"] or 0.0,
                    gb=row["gb"] or "",
                    rs=row["rs"] or 0,
                    ra=row["ra"] or 0,
                    streak=row["streak"] or "",
                    l10=row["l10"] or "",
                    vs_lhp=row["vs_lhp"] or "",
                    vs_rhp=row["vs_rhp"] or "",
                )
            )
        return out

    def roster(self, team_id: str) -> list[RosterPlayer]:
        rows = self.db.execute(
            "SELECT * FROM rosters WHERE team_id = ? ORDER BY section, player",
            [team_id],
        ).fetchall()
        return [RosterPlayer.model_validate(dict(row)) for row in rows]

    def financials(self, team_id: str) -> TeamFinance | None:
        row = self.db.execute(
            "SELECT * FROM team_info WHERE team_id = ? ORDER BY scraped_at DESC LIMIT 1",
            [team_id],
        ).fetchone()
        if not row:
            return None
        return TeamFinance(
            team_id=team_id,
            balance=row["balance"] or "",
            balance_num=row["balance_num"],
            roster_salary_num=row["roster_salary_num"],
            max_loan_num=row["max_loan_num"],
            park=row["park"] or "",
        )

    def league_rules(self, league_id: str) -> dict[str, str]:
        rows = self.db.execute(
            "SELECT rule_key, rule_value FROM league_rules WHERE league_id = ? ORDER BY rule_key",
            [league_id],
        ).fetchall()
        return {row["rule_key"]: row["rule_value"] for row in rows}

    def transactions(self, league_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT tx_date, tx_text, tx_type, player, salary, team_id
            FROM transactions
            WHERE league_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            [league_id, limit],
        ).fetchall()
        return [dict(row) for row in rows]

    def player_psimstats(self, player_name: str) -> dict[str, Any] | None:
        slug = player_name.replace(" ", "_")
        row = self.db.execute(
            """
            SELECT * FROM player_psimstats
            WHERE player_url LIKE ? OR player_url LIKE ?
            LIMIT 1
            """,
            [f"%{slug}%", f"%{player_name}%"],
        ).fetchone()
        return dict(row) if row else None

    def leaderboards(self, league_id: str, board_type: str = "batting") -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT category, rank, player, team_abbr, value
            FROM league_leaderboards
            WHERE league_id = ? AND board_type = ?
            ORDER BY category, rank
            """,
            [league_id, board_type.lower()],
        ).fetchall()
        return [dict(r) for r in rows]

    def fielding_leaders(self, league_id: str, position: str | None = None) -> list[dict[str, Any]]:
        if position:
            rows = self.db.execute(
                """
                SELECT position, rank, player, team_abbr, gp, inn, avg, po, a, e, rf
                FROM fielding_leaders
                WHERE league_id = ? AND position = ?
                ORDER BY rank
                """,
                [league_id, position.upper()],
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT position, rank, player, team_abbr, gp, inn, avg, po, a, e, rf
                FROM fielding_leaders
                WHERE league_id = ?
                ORDER BY position, rank
                """,
                [league_id],
            ).fetchall()
        return [dict(r) for r in rows]

    def team_vs_team(self, league_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT team_name, opp_abbr, record
            FROM team_vs_team
            WHERE league_id = ?
            ORDER BY team_name, opp_abbr
            """,
            [league_id],
        ).fetchall()
        return [dict(r) for r in rows]

    def league_transactions(self, league_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT team_name, tx_text, tx_date
            FROM league_transactions
            WHERE league_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            [league_id, limit],
        ).fetchall()
        return [dict(r) for r in rows]

    def injuries(self, team_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT section, player, positions, salary, out_for, cause, detail, scraped_at
            FROM injuries
            WHERE team_id = ?
            ORDER BY id DESC
            """,
            [team_id],
        ).fetchall()
        return [dict(r) for r in rows]

    def batting_splits(self, team_id: str, split_type: str | None = None) -> list[dict[str, Any]]:
        if split_type:
            rows = self.db.execute(
                "SELECT * FROM batting_splits WHERE team_id = ? AND split_type = ? ORDER BY player",
                [team_id, split_type],
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM batting_splits WHERE team_id = ? ORDER BY split_type, player",
                [team_id],
            ).fetchall()
        return [dict(r) for r in rows]

    def pitching_splits(self, team_id: str, split_type: str | None = None) -> list[dict[str, Any]]:
        if split_type:
            rows = self.db.execute(
                """
                SELECT * FROM pitching_splits
                WHERE team_id = ? AND split_type = ?
                ORDER BY player
                """,
                [team_id, split_type],
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM pitching_splits WHERE team_id = ? ORDER BY split_type, player",
                [team_id],
            ).fetchall()
        return [dict(r) for r in rows]

    def league_summary_text(self, league_id: str) -> str:
        standings = self.standings(league_id)
        lines = [f"Standings ({len(standings)} teams):"]
        for row in standings[:12]:
            lines.append(
                f"  {row.team_name or row.team_id[:8]}: {row.wins}-{row.losses} "
                f"({row.pct:.3f}) RS {row.rs} RA {row.ra} {row.streak}"
            )
        txns = self.transactions(league_id, limit=5)
        if txns:
            lines.append("Recent transactions:")
            for tx in txns:
                lines.append(f"  {tx.get('tx_date', '')}: {tx.get('tx_text', '')[:120]}")
        return "\n".join(lines)

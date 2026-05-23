"""Pydantic models for MCP structured output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthResult(BaseModel):
    valid: bool
    message: str


class ScrapeResult(BaseModel):
    ok: bool
    entry_team_id: str
    mode: str
    league_id: str | None = None
    league_name: str | None = None
    duration_s: float = 0.0
    message: str = ""


class StandingsRow(BaseModel):
    team_id: str = ""
    team_name: str = ""
    division: str = ""
    wins: int = 0
    losses: int = 0
    pct: float = 0.0
    gb: str = ""
    rs: int = 0
    ra: int = 0
    streak: str = ""
    last_10: str = Field(default="", alias="l10")
    vs_lhp: str = ""
    vs_rhp: str = ""

    model_config = {"populate_by_name": True}


class RosterPlayer(BaseModel):
    player: str
    position: str = ""
    section: str = ""
    salary: str = ""
    salary_num: int | None = None
    ba: str | None = None
    obp: str | None = None
    slg: str | None = None
    rc: str | None = None
    era: str | None = None
    ip: str | None = None


class TeamFinance(BaseModel):
    team_id: str
    balance: str = ""
    balance_num: int | None = None
    roster_salary_num: int | None = None
    max_loan_num: int | None = None
    park: str = ""


class LeagueEntry(BaseModel):
    entry_team_id: str
    display: str
    my_team_name: str
    key: str = ""
    active: bool = True

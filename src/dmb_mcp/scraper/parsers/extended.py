"""Parsers for extended ImagineSports pages (Phase 2)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup

FIELDING_POSITIONS: dict[str, str] = {
    "0": "P",
    "1": "C",
    "2": "1B",
    "3": "2B",
    "4": "3B",
    "5": "SS",
    "6": "LF",
    "7": "CF",
    "8": "RF",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_player_team(cell: str) -> tuple[str, str]:
    """Parse 'Vaughn, Greg(CRL)' -> ('Vaughn, Greg', 'CRL')."""
    text = cell.strip()
    match = re.search(r"\(([^)]+)\)\s*$", text)
    if match:
        abbr = match.group(1)
        player = text[: match.start()].strip()
        return player, abbr
    return text, ""


def _col_get(
    col_map: list[str],
    row: list[str],
    name: str,
    *,
    aliases: list[str] | None = None,
    default: str = "",
) -> str:
    for n in [name, *(aliases or [])]:
        try:
            idx = col_map.index(n.lower())
            return row[idx] if idx < len(row) else default
        except ValueError:
            pass
    return default


def parse_leaderboards(
    soup: BeautifulSoup, league_id: str, board_type: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    for table in soup.find_all("table", class_="stat_table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        category = rows[0].get_text(strip=True)
        if not category:
            continue
        rank = 0
        for tr in rows[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 2:
                continue
            rank += 1
            player, abbr = _parse_player_team(cells[0])
            records.append(
                {
                    "league_id": league_id,
                    "board_type": board_type,
                    "category": category,
                    "rank": rank,
                    "player": player,
                    "team_abbr": abbr,
                    "value": cells[-1],
                    "scraped_at": now,
                }
            )
    return records


def parse_fielding_leaders(
    soup: BeautifulSoup, league_id: str, position: str
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    table = soup.find("table", class_="stat_table")
    if not table:
        return records
    col_map: list[str] | None = None
    rank = 0
    for tr in table.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not row:
            continue
        lower = [c.lower() for c in row]
        if "player" in lower:
            col_map = lower
            continue
        if col_map is None or not row[0] or row[0].lower().startswith("team"):
            continue

        player, abbr = _parse_player_team(_col_get(col_map, row, "player", default=row[0]))
        rank += 1
        records.append(
            {
                "league_id": league_id,
                "position": position,
                "rank": rank,
                "player": player,
                "team_abbr": abbr or _col_get(col_map, row, "team"),
                "gp": _col_get(col_map, row, "gp"),
                "inn": _col_get(col_map, row, "inn"),
                "avg": _col_get(col_map, row, "avg.", aliases=["avg"]),
                "po": _col_get(col_map, row, "po"),
                "a": _col_get(col_map, row, "a"),
                "e": _col_get(col_map, row, "e"),
                "tc": _col_get(col_map, row, "tc"),
                "dp": _col_get(col_map, row, "dp"),
                "rf": _col_get(col_map, row, "rf"),
                "scraped_at": now,
            }
        )
    return records


def parse_team_vs_team(soup: BeautifulSoup, league_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    table = soup.find("table", class_="stat_table")
    if not table:
        return records
    rows = table.find_all("tr")
    if len(rows) < 2:
        return records
    header = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
    abbrs = header[1:]
    for tr in rows[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        team_name = cells[0]
        for opp_abbr, record in zip(abbrs, cells[1:], strict=False):
            if not opp_abbr or record in ("-", ""):
                continue
            records.append(
                {
                    "league_id": league_id,
                    "team_name": team_name,
                    "team_abbr": "",
                    "opp_abbr": opp_abbr,
                    "record": record,
                    "scraped_at": now,
                }
            )
    return records


def parse_league_transactions(soup: BeautifulSoup, league_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    for tr in soup.find_all("tr", class_=lambda c: c and ("data0" in c or "data1" in c)):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 3:
            continue
        records.append(
            {
                "league_id": league_id,
                "team_name": cells[0],
                "tx_text": cells[1],
                "tx_date": cells[2],
                "scraped_at": now,
            }
        )
    return records


def parse_trade_view(soup: BeautifulSoup, league_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    for tr in soup.find_all("tr", class_=lambda c: c and ("data0" in c or "data1" in c)):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 2:
            continue
        records.append(
            {
                "league_id": league_id,
                "status": cells[0] if len(cells) > 3 else "",
                "proposing_team": cells[0],
                "detail_text": " | ".join(cells[1:]),
                "scraped_at": now,
            }
        )
    return records


def parse_injuries(soup: BeautifulSoup, team_id: str, league_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    for table in soup.find_all("table", class_="stat_table"):
        title_row = table.find("tr")
        section = title_row.get_text(strip=True) if title_row else "unknown"
        col_map: list[str] | None = None
        for tr in table.find_all("tr"):
            row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not row:
                continue
            lower = [c.lower() for c in row]
            if "player" in lower and "date" in lower:
                col_map = lower
                continue
            if col_map is None:
                if len(row) == 1 and "no " in row[0].lower():
                    continue
                if (
                    section.lower().startswith("player injury")
                    and len(row) == 1
                    and row[0].lower() in ("player injury status",)
                ):
                    continue
                if (
                    section.lower().startswith("player injury")
                    and len(row) >= 1
                    and "no players" not in row[0].lower()
                ):
                    records.append(
                        {
                            "team_id": team_id,
                            "league_id": league_id,
                            "scraped_at": now,
                            "section": section,
                            "player": row[0],
                            "positions": "",
                            "salary": "",
                            "out_for": "",
                            "cause": "",
                            "detail": row[0],
                        }
                    )
                continue

            player = _col_get(col_map, row, "player", default=row[0] if row else "")
            if not player or "no injuries" in player.lower():
                continue
            records.append(
                {
                    "team_id": team_id,
                    "league_id": league_id,
                    "scraped_at": now,
                    "section": section,
                    "player": player,
                    "positions": _col_get(col_map, row, "position(s)", aliases=["position"]),
                    "salary": _col_get(col_map, row, "salary"),
                    "out_for": _col_get(col_map, row, "out for"),
                    "cause": _col_get(col_map, row, "injury cause", aliases=["cause"]),
                    "detail": " | ".join(row),
                }
            )
    return records


def parse_batting_splits(
    soup: BeautifulSoup, team_id: str, league_id: str, split_type: str
) -> list[dict[str, Any]]:
    return _parse_split_table(soup, team_id, league_id, split_type, "batting")


def parse_pitching_splits(
    soup: BeautifulSoup, team_id: str, league_id: str, split_type: str
) -> list[dict[str, Any]]:
    return _parse_split_table(soup, team_id, league_id, split_type, "pitching")


def _parse_split_table(
    soup: BeautifulSoup,
    team_id: str,
    league_id: str,
    split_type: str,
    kind: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    table = soup.find("table", class_="stat_table")
    if not table:
        return records
    col_map: list[str] | None = None
    for tr in table.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not row:
            continue
        lower = [c.lower() for c in row]
        if "player" in lower:
            col_map = lower
            continue
        if col_map is None or not row[0] or row[0].lower().startswith("team"):
            continue
        stats = {col_map[i]: row[i] for i in range(min(len(col_map), len(row)))}
        base = {
            "team_id": team_id,
            "league_id": league_id,
            "split_type": split_type,
            "scraped_at": now,
            "player": stats.get("player", row[0]),
            "stats_json": json.dumps(stats),
        }
        if kind == "batting":
            base.update(
                {
                    "ab": stats.get("ab", ""),
                    "h": stats.get("h", ""),
                    "doubles": stats.get("2b", ""),
                    "triples": stats.get("3b", ""),
                    "hr": stats.get("hr", ""),
                    "rbi": stats.get("rbi", ""),
                    "ba": stats.get("ba", ""),
                    "obp": stats.get("obp", ""),
                    "slg": stats.get("slg", ""),
                }
            )
        else:
            base.update(
                {
                    "w": stats.get("w", ""),
                    "l": stats.get("l", ""),
                    "era": stats.get("era", ""),
                    "ip": stats.get("ip", ""),
                    "sv": stats.get("sv", ""),
                    "k": stats.get("k", ""),
                    "bb": stats.get("bb", ""),
                }
            )
        records.append(base)
    return records


def parse_park_reference(soup: BeautifulSoup) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        header_cells = rows[1].find_all(["td", "th"])
        headers = [c.get_text(strip=True) for c in header_cells]
        if not headers or headers[0].lower() != "park":
            continue
        for tr in rows[2:]:
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or not cells[0]:
                continue
            park_name = re.sub(r"View Image$", "", cells[0]).strip()
            dim_count = max(0, len(headers) - 8)
            dim_headers = headers[5 : 5 + dim_count]
            dim_cells = cells[5 : 5 + dim_count]
            dimensions = dict(zip(dim_headers, dim_cells, strict=False))
            lhb_headers = headers[5 + dim_count : 5 + dim_count + 5]
            lhb_cells = cells[5 + dim_count : 5 + dim_count + 5]
            lhb = dict(zip(lhb_headers, lhb_cells, strict=False))
            rhb_headers = headers[5 + dim_count + 5 :]
            rhb_cells = cells[5 + dim_count + 5 :]
            rhb = dict(zip(rhb_headers, rhb_cells, strict=False))
            records.append(
                {
                    "park_name": park_name,
                    "scraped_at": now,
                    "years": cells[1] if len(cells) > 1 else "",
                    "city": cells[2] if len(cells) > 2 else "",
                    "surface": cells[3] if len(cells) > 3 else "",
                    "cover": cells[4] if len(cells) > 4 else "",
                    "dimensions_json": json.dumps(dimensions),
                    "factors_lhb_json": json.dumps(lhb),
                    "factors_rhb_json": json.dumps(rhb),
                }
            )
    return records


def parse_record_boards(soup: BeautifulSoup, board_key: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    now = _now()
    table = soup.find("table", class_="stat_table")
    if not table:
        return records
    col_map: list[str] | None = None
    stat_name = board_key
    rank = 0
    for tr in table.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not row:
            continue
        lower = [c.lower() for c in row]
        if len(row) == 1 and row[0] and "player" not in lower:
            stat_name = row[0]
            continue
        if "player" in lower or "name" in lower:
            col_map = lower
            continue
        if col_map is None or not row[0]:
            continue
        rank += 1
        value = row[-1] if len(row) > 1 else ""
        team_league = row[2] if len(row) > 2 else ""
        records.append(
            {
                "board_key": board_key,
                "stat_name": stat_name,
                "rank": rank,
                "player": row[0],
                "team_league": team_league,
                "value": value,
                "scraped_at": now,
            }
        )
    return records

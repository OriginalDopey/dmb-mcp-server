def parse_teams_from_league_page(soup):
    """
    Parse team names and IDs from the league batting or pitching page.
    Ported from VBA SetupPages() / GetPitchers() in Module6/Module1.

    Teams are in <tr> elements with class 'data0' or 'data1'.
    Each row has a link to the team page containing the teamID parameter.
    """
    teams = []
    for css_class in ["data0", "data1"]:
        for row in soup.find_all("tr", class_=css_class):
            links = row.find_all("a")
            for link in links:
                href = link.get("href", "")
                if "teamID=" in href or "curTeam=" in href:
                    # Extract team ID from URL
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)
                    team_id = params.get("teamID", params.get("curTeam", [None]))[0]
                    team_name = link.get_text(strip=True)
                    if team_id and team_name:
                        teams.append(
                            {
                                "team_id": team_id,
                                "name": team_name,
                            }
                        )
                    break  # first link in row is the team link
    return teams


def parse_league_id_from_page(soup):
    """Try to extract the league public ID from page links or scripts."""
    # Look for league links with a recognizable pattern
    for script in soup.find_all("script"):
        text = script.string or ""
        # Look for curTeam assignment
        match = re.search(r"curTeam\s*=\s*['\"]([A-Za-z0-9]+)['\"]", text)
        if match:
            return match.group(1)
    return None


def _find_stat_table(soup, table_index=None, header_keywords=None):
    """
    Find the main data table on an IS page.

    IS pages use class='stat_table' for data tables. Ratings pages
    typically have one main stat_table with player data.

    Args:
        soup: BeautifulSoup parsed page
        table_index: fallback table index (from VBA: often 6)
        header_keywords: list of column header strings to match
            e.g. ["Name", "Position", "Bats"] for batter ratings
    """
    # Method 1: stat_table class with header matching
    stat_tables = soup.find_all("table", class_="stat_table")
    if stat_tables and header_keywords:
        for st in stat_tables:
            rows = st.find_all("tr")
            if len(rows) < 3:
                continue
            # Check first couple rows for header keywords
            for row in rows[:3]:
                cells = [td.get_text(strip=True).lower() for td in row.find_all(["td", "th"])]
                cell_text = " ".join(cells)
                matches = sum(1 for kw in header_keywords if kw.lower() in cell_text)
                if matches >= 2:  # at least 2 keyword matches
                    return st

    # Method 2: stat_table class, pick largest
    if stat_tables:
        best = max(stat_tables, key=lambda t: len(t.find_all("tr")))
        # Early-season pitching pages can be header + one pitcher + totals (3 rows).
        if len(best.find_all("tr")) >= 3:
            return best

    # Method 3: any table with header matching
    if header_keywords:
        for t in soup.find_all("table"):
            rows = t.find_all("tr")
            if len(rows) < 3:
                continue
            for row in rows[:3]:
                cells = [td.get_text(strip=True).lower() for td in row.find_all(["td", "th"])]
                cell_text = " ".join(cells)
                matches = sum(1 for kw in header_keywords if kw.lower() in cell_text)
                if matches >= 2:
                    return t

    # Method 4: table by index (VBA fallback)
    if table_index is not None:
        all_tables = soup.find_all("table")
        if table_index < len(all_tables):
            return all_tables[table_index]

    return None


def _money_to_int(value):
    """Convert IS money strings like '$3,741,200' to integer dollars."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    neg = text.startswith("(") and text.endswith(")")
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    amount = int(digits)
    return -amount if neg or text.startswith("-") else amount


def _money_text(amount):
    return f"${amount:,}" if amount is not None else ""


def _parse_table_rows(table):
    """Parse all rows from an HTML table into a list of lists of strings."""
    rows = []
    for tr in table.find_all("tr"):
        cells = []
        for td in tr.find_all(["td", "th"]):
            cells.append(td.get_text(strip=True))
        if any(c for c in cells):  # skip fully empty rows
            rows.append(cells)
    return rows


def _extract_player_url_from_row(tr):
    """
    Extract player_url from a roster table row (for psimstats Details link).
    Looks for href or onclick containing psimstats/popup and player_url=.
    Returns e.g. 'Boileryard_Clarke' or '' if not found.
    """
    for tag in tr.find_all(["a", "span", "td"]):
        href = tag.get("href") or ""
        onclick = tag.get("onclick") or ""
        combined = href + " " + onclick
        if "psimstats/popup" in combined and "player_url=" in combined:
            m = re.search(r"player_url=([^&'\"]+)", combined)
            if m:
                return (m.group(1).strip() or "").replace("%5F", "_")
    return ""


def parse_batter_ratings(soup, team_id, league_id):
    """
    Parse batter ratings page.
    Ported from VBA HTML_Batting_Table_To_Excel() in Module7.

    Expected columns: Name, Position, Bats, BuntSac, BuntHit, Run,
                      Steal, Jump, [gap], Injury
    """
    now = datetime.now(timezone.utc).isoformat()
    # IS batter ratings page header: Name, Position, Bats, Sac, Hit, Run, Stl, Jmp, Injury
    table = _find_stat_table(soup, header_keywords=["Name", "Position", "Bats", "Sac", "Run"])
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []
    col_map = None

    for row in rows:
        if not row or len(row) < 5:
            continue

        lower_row = [c.lower().strip() for c in row]

        # Detect header row (IS uses: Name, Position, Bats, Sac, Hit, Run, Stl, Jmp, Injury)
        if "name" in lower_row or "player" in lower_row:
            col_map = lower_row
            continue

        if col_map is None:
            continue

        # Skip empty/total rows
        if not row[0] or row[0].lower().startswith("team"):
            continue

        def _col(name, aliases=None, default=""):
            """Find column value by header name with aliases."""
            names = [name] + (aliases or [])
            for n in names:
                if n.lower() in col_map:
                    idx = col_map.index(n.lower())
                    return row[idx] if idx < len(row) else default
            return default

        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "player": _col("name", ["player"]),
            "position": _col("position", ["pos"]),
            "bats": _col("bats", ["bat"]),
            "bunt_sac": _col("sac", ["buntsac", "bunt sac"]),
            "bunt_hit": _col("hit", ["bunthit", "bunt hit"]),
            "run": _col("run"),
            "steal": _col("stl", ["steal"]),
            "jump": _col("jmp", ["jump"]),
            "injury": _col("injury", ["inj"]),
        }

        # Fallback: if col_map doesn't match, use positional
        if not record["player"] and len(row) >= 5:
            record["player"] = row[0]
            record["position"] = row[1]
            record["bats"] = row[2]
            record["bunt_sac"] = row[3]
            record["bunt_hit"] = row[4] if len(row) > 4 else ""
            record["run"] = row[5] if len(row) > 5 else ""
            record["steal"] = row[6] if len(row) > 6 else ""
            record["jump"] = row[7] if len(row) > 7 else ""
            record["injury"] = row[-1] if len(row) > 8 else ""

        if record["player"] and record["player"].lower() not in ("name", "player"):
            records.append(record)

    return records


def parse_pitcher_ratings(soup, team_id, league_id):
    """
    Parse pitcher ratings page.
    Ported from VBA HTML_Pitching_Table_To_Excel() in Module11.

    Expected columns: Name, Position, Throws, SPDur, RPDur, Hold,
                      WP, BK, GB%, Injury
    (VBA skips columns 3-7 which are in-season stats — we keep ratings only)
    """
    now = datetime.now(timezone.utc).isoformat()
    # IS pitcher ratings header: Name, Position, Throws, SDur, RDur, Hold, WP, BK, GB%, Injury
    table = _find_stat_table(soup, header_keywords=["Name", "Position", "Throws", "SDur", "Hold"])
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []
    col_map = None

    for row in rows:
        if not row or len(row) < 5:
            continue

        lower_row = [c.lower().strip() for c in row]
        if "name" in lower_row or "player" in lower_row:
            col_map = lower_row
            continue
        if col_map is None:
            continue
        if not row[0] or row[0].lower().startswith("team"):
            continue

        def _col(name, aliases=None, default=""):
            names = [name] + (aliases or [])
            for n in names:
                if n.lower() in col_map:
                    idx = col_map.index(n.lower())
                    return row[idx] if idx < len(row) else default
            return default

        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "player": _col("name", ["player"]),
            "position": _col("position", ["pos"]),
            "throws": _col("throws", ["throw"]),
            "sp_dur": _col("sdur", ["spdur", "sp dur", "sp_dur"]),
            "rp_dur": _col("rdur", ["rpdur", "rp dur", "rp_dur"]),
            "hold": _col("hold", ["hld"]),
            "wp": _col("wp"),
            "bk": _col("bk"),
            "gb_pct": _col("gb%", ["gb", "gbpct"]),
            "injury": _col("injury", ["inj"]),
        }

        # Positional fallback
        if not record["player"] and len(row) >= 5:
            record["player"] = row[0]
            record["position"] = row[1]
            record["throws"] = row[2]
            record["sp_dur"] = row[3]
            record["rp_dur"] = row[4] if len(row) > 4 else ""
            record["hold"] = row[5] if len(row) > 5 else ""
            record["wp"] = row[6] if len(row) > 6 else ""
            record["bk"] = row[7] if len(row) > 7 else ""
            record["gb_pct"] = row[8] if len(row) > 8 else ""
            record["injury"] = row[-1] if len(row) > 9 else ""

        # Default RPDur for SPs without one (per IS rules: default Vg)
        if record["sp_dur"] and not record["rp_dur"]:
            record["rp_dur"] = "Vg"

        if record["player"] and record["player"].lower() not in ("name", "player"):
            records.append(record)

    return records


def parse_fielder_ratings(soup, team_id, league_id):
    """
    Parse fielder ratings page.
    Ported from VBA HTML_Fielding_Table_To_Excel() in Module10.

    Expected columns: Name, Primary Pos, P, C, 1B, 2B, 3B, SS, LF, CF,
                      RF, OF, C(throw), PB
    """
    now = datetime.now(timezone.utc).isoformat()
    # IS fielder ratings header: Name, Primary Pos, P, C, 1B, 2B, 3B, SS, LF, CF, RF, OF, C(throw), PB
    table = _find_stat_table(soup, header_keywords=["Name", "Primary Pos", "1B", "SS", "CF"])
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []
    header_found = False

    for row in rows:
        if not row or len(row) < 5:
            continue

        lower_row = [c.lower().strip() for c in row]
        if "name" in lower_row or "primary pos" in lower_row:
            header_found = True
            continue
        if not header_found:
            continue
        if not row[0] or row[0].lower().startswith("team"):
            continue

        # Fielder ratings are always positional (fixed column order)
        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "player": row[0] if len(row) > 0 else "",
            "primary_pos": row[1] if len(row) > 1 else "",
            "fld_p": row[2] if len(row) > 2 else "",
            "fld_c": row[3] if len(row) > 3 else "",
            "fld_1b": row[4] if len(row) > 4 else "",
            "fld_2b": row[5] if len(row) > 5 else "",
            "fld_3b": row[6] if len(row) > 6 else "",
            "fld_ss": row[7] if len(row) > 7 else "",
            "fld_lf": row[8] if len(row) > 8 else "",
            "fld_cf": row[9] if len(row) > 9 else "",
            "fld_rf": row[10] if len(row) > 10 else "",
            "fld_of": row[11] if len(row) > 11 else "",
            "throw_c": row[12] if len(row) > 12 else "",
            "pb_c": row[13] if len(row) > 13 else "",
        }
        if record["player"] and record["player"].lower() not in ("name", "player"):
            records.append(record)

    return records


def parse_standings(soup, league_id):
    """
    Parse league standings page.

    The standings page has multiple divisions, each with a header row.
    Columns: Team, W-L, %, GB, HM, AW, Div, Xtra, 1-Run, L10,
             vsLHP, vsRHP, RS, RA, Streak, Magic #
    """
    now = datetime.now(timezone.utc).isoformat()
    records = []
    current_division = ""
    col_map = None

    table = _find_stat_table(soup, header_keywords=["Team", "W-L", "Streak", "RS", "RA"])
    if not table:
        return []

    rows = _parse_table_rows(table)

    for row in rows:
        if not row:
            continue

        # Division header (single cell spanning whole row) — check BEFORE
        # the len(row)<2 filter so single-cell rows aren't skipped
        _div_keywords = [
            "division",
            "east",
            "central",
            "west",
            "north",
            "south",
            "american league",
            "national league",
        ]
        if len(row) <= 2 and row[0] and any(kw in row[0].lower() for kw in _div_keywords):
            current_division = row[0].strip()
            col_map = None  # reset for next header row
            continue

        if len(row) < 2:
            continue

        lower_row = [c.lower().strip() for c in row]

        # Column header row
        if "team" in lower_row and ("w-l" in lower_row or "%" in lower_row):
            col_map = lower_row
            continue

        if col_map is None or not row[0]:
            continue

        # Must have W-L format in second column
        if len(row) < 3 or "-" not in str(row[1]):
            continue

        def _col(name, aliases=None, default=""):
            names = [name] + (aliases or [])
            for n in names:
                if n.lower() in col_map:
                    idx = col_map.index(n.lower())
                    return row[idx] if idx < len(row) else default
            return default

        wl = row[1].split("-")
        w = int(wl[0].strip()) if wl[0].strip().isdigit() else 0
        l_val = int(wl[1].strip()) if len(wl) > 1 and wl[1].strip().isdigit() else 0

        try:
            pct_str = _col("%", ["pct"])
            pct = float(pct_str) if pct_str else 0.0
        except (ValueError, IndexError):
            pct = 0.0

        rs_str = _col("rs", ["runs scored"])
        ra_str = _col("ra", ["runs allowed"])

        # Clean team name (remove playoff clinch markers like "x-", "y-", "z-")
        team_name_raw = row[0].strip()

        record = {
            "team_id": "",
            "league_id": league_id,
            "scraped_at": now,
            "division": current_division,
            "w": w,
            "l": l_val,
            "pct": pct,
            "gb": _col("gb"),
            "home": _col("hm", ["home"]),
            "away": _col("aw", ["away"]),
            "one_run": _col("1-run", ["one_run"]),
            "l10": _col("l10"),
            "vs_lhp": _col("vslhp", ["vs lhp"]),
            "vs_rhp": _col("vsrhp", ["vs rhp"]),
            "rs": int(rs_str) if rs_str and rs_str.isdigit() else 0,
            "ra": int(ra_str) if ra_str and ra_str.isdigit() else 0,
            "streak": _col("streak"),
            "_team_name": team_name_raw,
        }
        records.append(record)

    return records


def parse_standings_full(soup, league_id):
    """
    Parse standings page with team_ids extracted directly from links,
    plus Previous/Next game_id navigation and date label.

    Returns (records, prev_game_id, next_game_id, date_label).
    """
    now = datetime.now(timezone.utc).isoformat()

    # ── Extract Previous/Next game_ids from nav links ────────────
    prev_gid = next_gid = None
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "Previous" in text and "cutoff_game_id=" in href:
            m = re.search(r"cutoff_game_id=(\d+)", href)
            if m:
                prev_gid = int(m.group(1))
        elif "Next" in text and "cutoff_game_id=" in href:
            m = re.search(r"cutoff_game_id=(\d+)", href)
            if m:
                next_gid = int(m.group(1))

    # ── Date label (e.g. "Sat February 14, 3:00 PM") ────────────
    date_label = ""
    page_text = soup.get_text(" ", strip=True)
    m = re.search(
        r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+"
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+"
        r"\d+,?\s+\d+:\d+\s+[AP]M)",
        page_text,
    )
    if m:
        date_label = m.group(1).strip()

    # ── Parse standings table ────────────────────────────────────
    table = _find_stat_table(soup, header_keywords=["Team", "W-L", "RS", "RA"])
    if not table:
        return [], prev_gid, next_gid, date_label

    records = []
    current_division = ""
    col_map = None

    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row = [td.get_text(strip=True) for td in cells]
        if not row:
            continue

        # Division header — check before len filter
        _div_kw = [
            "division",
            "east",
            "central",
            "west",
            "north",
            "south",
            "american league",
            "national league",
        ]
        if len(row) <= 2 and row[0] and any(kw in row[0].lower() for kw in _div_kw):
            current_division = row[0].strip()
            col_map = None
            continue

        if len(row) < 2:
            continue

        lower_row = [c.lower().strip() for c in row]

        # Column header row
        if "team" in lower_row and ("w-l" in lower_row or "%" in lower_row):
            col_map = lower_row
            continue

        if col_map is None or not row[0]:
            continue
        if len(row) < 3 or "-" not in str(row[1]):
            continue

        # Extract team_id from the roster link in the first cell
        team_id = ""
        link = cells[0].find("a", href=True)
        if link:
            href = link.get("href", "")
            m = re.search(r"teamID=([A-Za-z0-9]+)", href)
            if m:
                team_id = m.group(1)

        # Parse W-L
        wl = row[1].split("-")
        w = int(wl[0].strip()) if wl[0].strip().isdigit() else 0
        l_val = int(wl[1].strip()) if len(wl) > 1 and wl[1].strip().isdigit() else 0

        def _col(name, aliases=None, default=""):
            names = [name] + (aliases or [])
            for n in names:
                if n.lower() in col_map:
                    idx = col_map.index(n.lower())
                    return row[idx] if idx < len(row) else default
            return default

        try:
            pct = float(_col("%", ["pct"]))
        except (ValueError, TypeError):
            pct = 0.0

        rs_str = _col("rs")
        ra_str = _col("ra")

        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "division": current_division,
            "team_name": row[0].strip(),
            "w": w,
            "l": l_val,
            "pct": pct,
            "gb": _col("gb"),
            "home": _col("hm", ["home"]),
            "away": _col("aw", ["away"]),
            "div_record": _col("div"),
            "xtra": _col("xtra"),
            "one_run": _col("1-run"),
            "l10": _col("l10"),
            "vs_lhp": _col("vslhp", ["vs lhp"]),
            "vs_rhp": _col("vsrhp", ["vs rhp"]),
            "rs": int(rs_str) if rs_str and rs_str.isdigit() else 0,
            "ra": int(ra_str) if ra_str and ra_str.isdigit() else 0,
            "streak": _col("streak"),
            "magic": _col("magic #", ["magic"]),
        }
        records.append(record)

    return records, prev_gid, next_gid, date_label


def _expand_batting_colmap(table, col_map):
    """Expand col_map when IS batting page hides columns behind 'More..'.

    The IS batting page shows a subset of columns by default and hides
    the rest behind a 'More..' toggle.  The hidden column *headers* are
    nested inside the last visible <td>, so _parse_table_rows concatenates
    them into one string.  However, the data rows contain separate <td>
    elements for every column (visible + hidden).

    We detect this mismatch and rebuild col_map from the actual <th>/<td>
    elements in the header <tr>.
    """
    if not col_map or not col_map[-1].startswith("more.."):
        return col_map

    # Walk the actual header <tr> elements to extract individual headers
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        texts = [c.get_text(strip=True).lower() for c in cells]
        if "player" not in texts and "name" not in texts:
            continue
        # Found the header row — now extract each header individually,
        # walking into nested elements if a cell contains sub-headers
        expanded = []
        for td in cells:
            # Check if this cell has nested stat-header children
            children = td.find_all(["td", "th", "span", "a", "div"])
            inner_texts = [
                ch.get_text(strip=True).lower() for ch in children if ch.get_text(strip=True)
            ]
            # If the cell's direct text starts with "more" and it has
            # grandchildren, try to harvest individual headers
            cell_text = td.get_text(strip=True).lower()
            if cell_text.startswith("more") and inner_texts:
                # Skip the "more.." link text itself
                for t in inner_texts:
                    t = t.strip()
                    if t and not t.startswith("more") and len(t) <= 10:
                        expanded.append(t)
            else:
                expanded.append(cell_text)
        if len(expanded) > len(col_map):
            print(f"  [batting] expanded col_map ({len(expanded)} cols): {expanded}")
            return expanded
        break

    # Fallback: known IS batting extended columns in standard order
    _KNOWN_MORE = [
        "rc600",
        "tb",
        "gw rbi",
        "sh",
        "sf",
        "hbp",
        "ibb",
        "gdp",
        "ops",
        "sec",
        "iso",
        "bb",
        "k",
        "pa",
    ]
    base = col_map[:-1]  # drop the "more.." entry
    extended = base + _KNOWN_MORE
    print(f"  [batting] using known extended col_map ({len(extended)} cols)")
    return extended


def parse_batting_stats(soup, team_id, league_id):
    """Parse team batting stats page into records."""
    now = datetime.now(timezone.utc).isoformat()
    table = _find_stat_table(soup)
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []
    col_map = None
    logged_first_data = False

    for row in rows:
        if not row or len(row) < 5:
            continue

        # Detect header row
        lower_row = [c.lower() for c in row]
        if "player" in lower_row or "name" in lower_row:
            col_map = lower_row
            print(f"  [batting] raw col_map ({len(col_map)} cols): {col_map}")
            col_map = _expand_batting_colmap(table, col_map)
            continue

        if col_map is None:
            continue

        # Skip totals
        if row[0].lower().startswith("team") or row[0].lower().startswith("total") or row[0] == "":
            continue

        if not logged_first_data:
            print(f"  [batting] first data row: {len(row)} cells")
            logged_first_data = True

        def _get(name, aliases=None, default=""):
            for n in [name] + (aliases or []):
                try:
                    idx = col_map.index(n)
                    return row[idx] if idx < len(row) else default
                except ValueError:
                    pass
            return default

        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "player": _get("player", ["name"]),
            "position": _get("pos", ["position"]),
            "salary": _get("salary", ["sal"]),
            "g": _get("g", ["gp"]),
            "ab": _get("ab"),
            "r": _get("r", ["runs"]),
            "h": _get("h", ["hits"]),
            "doubles": _get("2b", ["doubles"]),
            "triples": _get("3b", ["triples"]),
            "hr": _get("hr", ["home runs"]),
            "rbi": _get("rbi"),
            "bb": _get("bb", ["walks", "base on balls"]),
            "k": _get("k", ["so", "strikeouts"]),
            "sb": _get("sb", ["stolen bases"]),
            "cs": _get("cs", ["caught stealing"]),
            "ba": _get("ba", ["avg", "batting avg"]),
            "obp": _get("obp", ["on base pct"]),
            "slg": _get("slg", ["slugging"]),
            "rc": _get("rc", ["rc/g"]),
        }
        if record["player"]:
            records.append(record)

    return records


def parse_pitching_stats(soup, team_id, league_id):
    """Parse team pitching stats page into records."""
    now = datetime.now(timezone.utc).isoformat()
    table = _find_stat_table(soup)
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []
    col_map = None

    for row in rows:
        if not row or len(row) < 5:
            continue

        lower_row = [c.lower() for c in row]
        if "player" in lower_row or "name" in lower_row:
            col_map = lower_row
            print(f"  [pitching] col_map: {col_map}")
            continue

        if col_map is None:
            continue

        if row[0].lower().startswith("team") or row[0].lower().startswith("total") or row[0] == "":
            continue

        def _get(name, aliases=None, default=""):
            for n in [name] + (aliases or []):
                try:
                    idx = col_map.index(n)
                    return row[idx] if idx < len(row) else default
                except ValueError:
                    pass
            return default

        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "player": _get("player", ["name"]),
            "position": _get("pos", ["position"]),
            "salary": _get("salary", ["sal"]),
            "w": _get("w", ["wins"]),
            "l": _get("l", ["losses"]),
            "era": _get("era"),
            "g": _get("g", ["gp"]),
            "gs": _get("gs"),
            "cg": _get("cg"),
            "sv": _get("sv", ["saves"]),
            "bs": _get("bs", ["blown saves", "blown"]),
            "svop": _get("svop", ["save opp", "save opportunities", "svo"]),
            "ip": _get("ip"),
            "h": _get("h", ["hits"]),
            "r": _get("r", ["runs"]),
            "er": _get("er"),
            "hr": _get("hr"),
            "bb": _get("bb", ["walks", "base on balls"]),
            "k": _get("k", ["so", "strikeouts"]),
            "whip": _get("whip"),
        }
        if record["player"]:
            records.append(record)

    return records


def parse_roster(soup, team_id, league_id):
    """
    Parse team roster page (/bball/team/roster).

    Three stat_tables:
      Table 0: Position players — POS, Player, Salary, BA, OBP, SLG, R, HR, RBI, RC, Stats
      Table 1: Pitchers — POS, Player, Salary, IP, W, L, ERA, Sv, K, BB, Stats
      Table 2: IR — POS, Player, Salary, Games On IR, Stats

    Extracts player_url from each row's Details link (psimstats popup) when present.
    """
    now = datetime.now(timezone.utc).isoformat()
    tables = soup.find_all("table", class_="stat_table")
    records = []

    section_map = {0: "batter", 1: "pitcher", 2: "ir"}

    for idx, table in enumerate(tables):
        section = section_map.get(idx, "unknown")
        col_map = None

        for tr in table.find_all("tr"):
            row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not row or len(row) < 3:
                continue

            lower_row = [c.lower().strip() for c in row]

            # Header row
            if "player" in lower_row or "pos" in lower_row:
                col_map = lower_row
                continue

            if col_map is None:
                continue

            # Skip totals/empty
            if row[0].lower().startswith("total") or not row[0]:
                continue

            def _col(name, aliases=None, default=""):
                names = [name] + (aliases or [])
                for n in names:
                    if n.lower() in col_map:
                        i = col_map.index(n.lower())
                        return row[i] if i < len(row) else default
                return default

            # Parse salary to integer
            salary_raw = _col("salary")
            salary_num = 0
            if salary_raw:
                digits = re.sub(r"[^\d]", "", salary_raw)
                salary_num = int(digits) if digits else 0

            record = {
                "team_id": team_id,
                "league_id": league_id,
                "scraped_at": now,
                "section": section,
                "position": _col("pos", ["position"]),
                "player": _col("player"),
                "salary": salary_raw,
                "salary_num": salary_num,
                "player_url": _extract_player_url_from_row(tr),
                # Batter cols
                "ba": _col("ba") if section == "batter" else "",
                "obp": _col("obp") if section == "batter" else "",
                "slg": _col("slg") if section == "batter" else "",
                "r": _col("r") if section == "batter" else "",
                "hr": _col("hr") if section == "batter" else "",
                "rbi": _col("rbi") if section == "batter" else "",
                "rc": _col("rc") if section == "batter" else "",
                # Pitcher cols
                "ip": _col("ip") if section == "pitcher" else "",
                "w": _col("w") if section == "pitcher" else "",
                "l": _col("l") if section == "pitcher" else "",
                "era": _col("era") if section == "pitcher" else "",
                "sv": _col("sv") if section == "pitcher" else "",
                "k": _col("k") if section == "pitcher" else "",
                "bb": _col("bb") if section == "pitcher" else "",
                # IR cols
                "games_on_ir": _col("games on ir") if section == "ir" else "",
            }

            if record["player"]:
                records.append(record)

    return records


def parse_psimstats_popup(soup):
    """
    Parse the psimstats Details popup HTML for projected stats and splits.
    Returns a dict with keys: obp, rc, rc600, ba, slg, vs_lhp_obp, vs_lhp_rc,
    vs_rhp_obp, vs_rhp_rc, raw_stats (optional JSON). Missing values are omitted.
    If the page is login or has no stat table, returns {}.
    """
    out = {}
    tables = soup.find_all("table", class_="stat_table")
    for table in tables:
        rows = _parse_table_rows(table)
        if not rows or len(rows) < 2:
            continue
        lower_row0 = [c.lower().strip() for c in rows[0]]
        # Look for OBP/RC-style header
        if "obp" not in lower_row0 and "rc" not in lower_row0:
            continue
        col_map = lower_row0
        # First data row (skip header)
        for row in rows[1:]:
            if not row or len(row) < 2:
                continue
            if row[0].lower().startswith("total") or not row[0]:
                continue

            def _col(name, aliases=None):
                names = [name] + (aliases or [])
                for n in names:
                    if n in col_map:
                        i = col_map.index(n)
                        return row[i].strip() if i < len(row) else ""
                return ""

            obp = _col("obp")
            rc = _col("rc")
            if obp:
                out["obp"] = obp
            if rc:
                out["rc"] = rc
            rc600 = _col("rc600") or _col("rc/600")
            if rc600:
                out["rc600"] = rc600
            ba = _col("ba")
            if ba:
                out["ba"] = ba
            slg = _col("slg")
            if slg:
                out["slg"] = slg
            # Only use first matching data row for main stats
            break
        if out:
            break

    # Look for vs LHP / vs RHP sections (often in links or separate tables)
    for table in soup.find_all("table", class_="stat_table"):
        rows = _parse_table_rows(table)
        for i, row in enumerate(rows):
            if not row:
                continue
            row_lower = " ".join(c.lower() for c in row)
            if "vs" in row_lower and ("lhp" in row_lower or "rhp" in row_lower):
                col_map = [c.lower().strip() for c in row]
                if i + 1 < len(rows):
                    data_row = rows[i + 1]

                    def _v(name):
                        if name in col_map:
                            j = col_map.index(name)
                            return data_row[j].strip() if j < len(data_row) else ""
                        return ""

                    if "lhp" in row_lower or "vs. l" in row_lower:
                        out["vs_lhp_obp"] = _v("obp") or out.get("vs_lhp_obp")
                        out["vs_lhp_rc"] = _v("rc") or out.get("vs_lhp_rc")
                    if "rhp" in row_lower or "vs. r" in row_lower:
                        out["vs_rhp_obp"] = _v("obp") or out.get("vs_rhp_obp")
                        out["vs_rhp_rc"] = _v("rc") or out.get("vs_rhp_rc")
                break

    return out


def parse_transactions(soup, team_id, league_id):
    """
    Parse team transactions page (/bball/team/transactions).

    Uses lined_table class. Columns: Transaction, Date
    Transaction types:
      - "X was activated"
      - "X was deactivated"
      - "X was signed (salary $N)"
      - "X was released (refund $N)"
      - "Took a loan of $N"
      - Trades
    """
    now = datetime.now(timezone.utc).isoformat()
    table = soup.find("table", class_="lined_table")
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []

    for row in rows:
        if not row or len(row) < 2:
            continue

        tx_text = row[0].strip()
        tx_date = row[1].strip()

        # Skip header row
        if tx_text.lower() == "transaction":
            continue

        # Classify transaction type and extract player/salary
        tx_type = "other"
        player = ""
        salary = ""

        if "was activated" in tx_text:
            tx_type = "activated"
            player = tx_text.split(" was activated")[0].strip()
        elif "was deactivated" in tx_text:
            tx_type = "deactivated"
            player = tx_text.split(" was deactivated")[0].strip()
        elif "was signed" in tx_text:
            tx_type = "signed"
            player = tx_text.split(" was signed")[0].strip()
            sal_match = re.search(r"salary\s*\$([0-9,]+)", tx_text, re.I)
            if sal_match:
                salary = "$" + sal_match.group(1)
        elif "was released" in tx_text:
            tx_type = "released"
            player = tx_text.split(" was released")[0].strip()
            ref_match = re.search(r"refund\s*\$([0-9,]+)", tx_text, re.I)
            if ref_match:
                salary = "$" + ref_match.group(1)
        elif "loan" in tx_text.lower():
            tx_type = "loan"
            sal_match = re.search(r"\$([0-9,]+)", tx_text)
            if sal_match:
                salary = "$" + sal_match.group(1)
        elif "trade" in tx_text.lower() or "traded" in tx_text.lower():
            tx_type = "trade"
            player = tx_text

        record = {
            "team_id": team_id,
            "league_id": league_id,
            "scraped_at": now,
            "tx_date": tx_date,
            "tx_text": tx_text,
            "tx_type": tx_type,
            "player": player,
            "salary": salary,
        }
        records.append(record)

    return records


def parse_league_rules(soup, league_id):
    """
    Parse league rules page (/bball/league/rules).

    The rules table has single-cell rows in format "Key:Value".
    Also extracts league name, teams count, commissioner from row 0.
    """
    table = _find_stat_table(soup)
    if not table:
        return {}

    rows = _parse_table_rows(table)
    rules = {}

    if rows:
        # Row 0 has league name, team count, commissioner
        first_cells = rows[0]
        if first_cells:
            for cell in first_cells:
                if "Teams:" in cell:
                    rules["teams_count"] = cell.split("Teams:")[-1].strip()
                elif "Commissioner:" in cell:
                    rules["commissioner"] = cell.split("Commissioner:")[-1].strip()
                elif cell and ":" not in cell:
                    rules["league_name"] = cell.strip()

    # Single-cell rows are "Key:Value"
    for row in rows[1:]:
        if not row:
            continue
        # Skip rows that are just repeats of multi-cell layout
        for cell in row:
            cell = cell.strip()
            if ":" in cell and len(cell) < 200:
                key, _, val = cell.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val and key not in rules:
                    # Clean up whitespace in values
                    val = re.sub(r"\s+", " ", val).strip()
                    rules[key] = val

    return rules


def parse_team_info_from_scouting(soup, league_id):
    """
    Parse team info from the scouting page (/bball/league/scouting).

    The scouting page has a stat_table with division headers and
    rows: Team, Abbr., Balance, Park, Owner
    """
    now = datetime.now(timezone.utc).isoformat()
    table = _find_stat_table(soup, header_keywords=["Team", "Abbr", "Park", "Owner"])
    if not table:
        return []

    rows = _parse_table_rows(table)
    records = []
    current_division = ""
    col_map = None

    for row in rows:
        if not row:
            continue

        lower_row = [c.lower().strip() for c in row]

        # Division header (single cell like "East Division")
        _div_kw2 = [
            "division",
            "east",
            "central",
            "west",
            "north",
            "south",
            "american league",
            "national league",
        ]
        if len(row) <= 2 and any(kw in row[0].lower() for kw in _div_kw2):
            current_division = row[0].strip()
            col_map = None
            continue

        # Column header
        if "team" in lower_row and ("abbr" in lower_row or "abbr." in lower_row):
            col_map = lower_row
            continue

        if col_map is None or not row[0]:
            continue

        def _col(name, aliases=None, default=""):
            names = [name] + (aliases or [])
            for n in names:
                for i, c in enumerate(col_map):
                    if n.lower() in c:
                        return row[i] if i < len(row) else default
            return default

        # Parse owner - remove PH/phone suffix
        owner_raw = _col("owner")
        owner = re.sub(r"\s*\{[^}]*\}\s*PH\s*$", "", owner_raw).strip()
        owner = re.sub(r"\s*PH\s*$", "", owner).strip()

        record = {
            "team_name": _col("team"),
            "abbreviation": _col("abbr", ["abbr."]),
            "balance": _col("balance"),
            "balance_num": _money_to_int(_col("balance")),
            "park": _col("park"),
            "owner": owner,
            "division": current_division,
        }

        if record["team_name"]:
            records.append(record)

    return records


def parse_finance_from_text(soup):
    """Extract Total Value, Cash Balance, Max Loan, Upcoming Payments when present.

    Works for any IS page that prints these labels in the header text — the
    roster page exposes Total Value / Cash Balance / Max Loan inline, while
    front-office pages add Upcoming Scheduled Payment Total when authenticated.
    """
    finance = {}
    label_map = {
        "total_value_num": ["total value"],
        "balance_num": ["cash balance", "current cash balance", "balance"],
        "upcoming_payment_total_num": [
            "upcoming scheduled payment total",
            "scheduled payment total",
            "upcoming scheduled payments",
        ],
        "max_loan_num": ["max loan", "maximum loan", "maximum advance"],
    }

    flat = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    for key, labels in label_map.items():
        for label in labels:
            pattern = re.compile(
                re.escape(label) + r"\s*:?\s*\(?\s*(\$-?[0-9,]+)\s*\)?",
                re.I,
            )
            match = pattern.search(flat)
            if match:
                finance[key] = _money_to_int(match.group(1))
                break

    if "balance_num" in finance:
        finance["balance"] = _money_text(finance["balance_num"])
    return finance


def parse_fielding_stats(soup, team_id, league_id):
    """
    Parse team fielding page (/bball/team/fielding).

    Has 9 stat_tables, one per position:
      Pitcher, Catcher, 1B, 2B, 3B, SS, LF, CF, RF
    Each has columns: [Position], GP, Inn, Avg., PO, A, E, TC, DP, RF (PB for catchers)
    """
    now = datetime.now(timezone.utc).isoformat()
    tables = soup.find_all("table", class_="stat_table")
    records = []

    # Position names in table headers
    pos_names = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
    pos_full = {
        "pitcher": "P",
        "catcher": "C",
        "first base": "1B",
        "second base": "2B",
        "third base": "3B",
        "shortstop": "SS",
        "left field": "LF",
        "center field": "CF",
        "right field": "RF",
    }

    for idx, table in enumerate(tables):
        rows = _parse_table_rows(table)
        if not rows:
            continue

        # Determine position from first cell of header row
        header = rows[0]
        position = pos_names[idx] if idx < len(pos_names) else "?"

        # Try to match position from header text
        for cell in header:
            for full_name, abbr in pos_full.items():
                if full_name in cell.lower():
                    position = abbr
                    break

        col_map = None
        for row in rows:
            if not row or len(row) < 3:
                continue

            lower_row = [c.lower().strip() for c in row]

            # Detect header (has GP and Inn)
            if "gp" in lower_row and "inn" in lower_row:
                col_map = lower_row
                continue

            if col_map is None:
                continue

            # Skip totals
            if not row[0] or row[0].lower().startswith("team"):
                continue

            def _col(name, aliases=None, default=""):
                names = [name] + (aliases or [])
                for n in names:
                    if n.lower() in col_map:
                        i = col_map.index(n.lower())
                        return row[i] if i < len(row) else default
                return default

            record = {
                "team_id": team_id,
                "league_id": league_id,
                "scraped_at": now,
                "position": position,
                "player": row[0],
                "gp": _col("gp"),
                "inn": _col("inn"),
                "avg": _col("avg", ["avg."]),
                "po": _col("po"),
                "a": _col("a"),
                "e": _col("e"),
                "tc": _col("tc"),
                "dp": _col("dp"),
                "rf": _col("rf"),
                "pb": _col("pb") if position == "C" else "",
                "sb": _col("sb", ["sb allowed", "stolen bases"]) if position == "C" else "",
                "cs": _col("cs", ["cs", "caught stealing"]) if position == "C" else "",
            }

            if record["player"]:
                records.append(record)

    return records


# ═══════════════════════════════════════════════════════════════════════
#  SCRAPER — Orchestrates the page fetches and parsing
# ═══════════════════════════════════════════════════════════════════════

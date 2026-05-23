CREATE TABLE IF NOT EXISTS leagues (
    league_id       TEXT PRIMARY KEY,
    name            TEXT,
    num_teams       INTEGER,
    era             TEXT,
    entry_team_id   TEXT,
    last_scraped    TEXT
);

CREATE TABLE IF NOT EXISTS teams (
    team_id     TEXT PRIMARY KEY,
    league_id   TEXT,
    name        TEXT,
    owner       TEXT,
    division    TEXT,
    FOREIGN KEY (league_id) REFERENCES leagues(league_id)
);

CREATE TABLE IF NOT EXISTS standings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    division    TEXT,
    w           INTEGER,
    l           INTEGER,
    pct         REAL,
    gb          TEXT,
    home        TEXT,
    away        TEXT,
    one_run     TEXT,
    l10         TEXT,
    vs_lhp      TEXT,
    vs_rhp      TEXT,
    rs          INTEGER,
    ra          INTEGER,
    streak      TEXT,
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS batter_ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    player      TEXT,
    position    TEXT,
    bats        TEXT,
    bunt_sac    TEXT,
    bunt_hit    TEXT,
    run         TEXT,
    steal       TEXT,
    jump        TEXT,
    injury      TEXT
);

CREATE TABLE IF NOT EXISTS pitcher_ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    player      TEXT,
    position    TEXT,
    throws      TEXT,
    sp_dur      TEXT,
    rp_dur      TEXT,
    hold        TEXT,
    wp          TEXT,
    bk          TEXT,
    gb_pct      TEXT,
    injury      TEXT
);

CREATE TABLE IF NOT EXISTS fielder_ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    player      TEXT,
    primary_pos TEXT,
    fld_p       TEXT,
    fld_c       TEXT,
    fld_1b      TEXT,
    fld_2b      TEXT,
    fld_3b      TEXT,
    fld_ss      TEXT,
    fld_lf      TEXT,
    fld_cf      TEXT,
    fld_rf      TEXT,
    fld_of      TEXT,
    throw_c     TEXT,
    pb_c        TEXT
);

CREATE TABLE IF NOT EXISTS batting_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    player      TEXT,
    position    TEXT,
    salary      TEXT,
    g           TEXT,
    ab          TEXT,
    r           TEXT,
    h           TEXT,
    doubles     TEXT,
    triples     TEXT,
    hr          TEXT,
    rbi         TEXT,
    bb          TEXT,
    k           TEXT,
    sb          TEXT,
    cs          TEXT,
    ba          TEXT,
    obp         TEXT,
    slg         TEXT,
    rc          TEXT
);

CREATE TABLE IF NOT EXISTS pitching_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    player      TEXT,
    position    TEXT,
    salary      TEXT,
    w           TEXT,
    l           TEXT,
    era         TEXT,
    g           TEXT,
    gs          TEXT,
    cg          TEXT,
    sv          TEXT,
    bs          TEXT,
    svop        TEXT,
    ip          TEXT,
    h           TEXT,
    r           TEXT,
    er          TEXT,
    hr          TEXT,
    bb          TEXT,
    k           TEXT,
    whip        TEXT
);

CREATE TABLE IF NOT EXISTS tournaments (
    name        TEXT,
    round       TEXT,
    league_id   TEXT,
    entry_team_id TEXT,
    league_name TEXT,
    added_at    TEXT,
    PRIMARY KEY (name, round, entry_team_id)
);

CREATE TABLE IF NOT EXISTS standings_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    snapshot_at TEXT,
    division    TEXT,
    w           INTEGER,
    l           INTEGER,
    pct         REAL,
    gb          TEXT,
    home        TEXT,
    away        TEXT,
    one_run     TEXT,
    l10         TEXT,
    vs_lhp      TEXT,
    vs_rhp      TEXT,
    rs          INTEGER,
    ra          INTEGER,
    streak      TEXT,
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS rosters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    section     TEXT,       -- 'batter', 'pitcher', 'ir'
    position    TEXT,
    player      TEXT,
    salary      TEXT,
    salary_num  INTEGER,    -- salary as integer (cents removed)
    -- batter cols (NULL for pitchers/IR)
    ba          TEXT,
    obp         TEXT,
    slg         TEXT,
    r           TEXT,
    hr          TEXT,
    rbi         TEXT,
    rc          TEXT,
    -- pitcher cols (NULL for batters/IR)
    ip          TEXT,
    w           TEXT,
    l           TEXT,
    era         TEXT,
    sv          TEXT,
    k           TEXT,
    bb          TEXT,
    -- IR cols
    games_on_ir TEXT,
    player_url  TEXT,       -- e.g. Boileryard_Clarke for psimstats popup
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    tx_date     TEXT,       -- raw date string from IS
    tx_text     TEXT,       -- full transaction text
    tx_type     TEXT,       -- 'activated','deactivated','signed','released','loan','trade','other'
    player      TEXT,       -- player name (parsed)
    salary      TEXT,       -- salary if signing/release (parsed)
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS league_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT,
    scraped_at  TEXT,
    rule_key    TEXT,
    rule_value  TEXT,
    UNIQUE(league_id, rule_key)
);

CREATE TABLE IF NOT EXISTS team_info (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    abbreviation TEXT,
    balance     TEXT,
    balance_num INTEGER,
    roster_salary_num INTEGER,
    total_value_num INTEGER,
    upcoming_payment_total_num INTEGER,
    max_loan_num INTEGER,
    park        TEXT,
    owner       TEXT,
    division    TEXT,
    UNIQUE(team_id, league_id)
);

CREATE TABLE IF NOT EXISTS fielding_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT,
    league_id   TEXT,
    scraped_at  TEXT,
    position    TEXT,       -- 'P','C','1B','2B','3B','SS','LF','CF','RF'
    player      TEXT,
    gp          TEXT,
    inn         TEXT,
    avg         TEXT,
    po          TEXT,
    a           TEXT,
    e           TEXT,
    tc          TEXT,
    dp          TEXT,
    rf          TEXT,       -- range factor (or PB for catchers)
    pb          TEXT,       -- passed balls (catchers only)
    sb          TEXT,       -- stolen bases allowed (catchers / team)
    cs          TEXT,       -- caught stealing (catchers / team)
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS game_standings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT NOT NULL,
    league_id   TEXT NOT NULL,
    game_id     INTEGER NOT NULL,
    date_label  TEXT,
    division    TEXT,
    team_name   TEXT,
    w           INTEGER,
    l           INTEGER,
    pct         REAL,
    gb          TEXT,
    home        TEXT,
    away        TEXT,
    div_record  TEXT,
    xtra        TEXT,
    one_run     TEXT,
    l10         TEXT,
    vs_lhp      TEXT,
    vs_rhp      TEXT,
    rs          INTEGER,
    ra          INTEGER,
    streak      TEXT,
    magic       TEXT,
    scraped_at  TEXT,
    UNIQUE(team_id, league_id, game_id)
);

CREATE TABLE IF NOT EXISTS player_psimstats (
    player_url   TEXT PRIMARY KEY,
    scraped_at   TEXT,
    obp         TEXT,
    rc          TEXT,
    rc600       TEXT,
    ba          TEXT,
    slg         TEXT,
    vs_lhp_obp  TEXT,
    vs_lhp_rc   TEXT,
    vs_rhp_obp  TEXT,
    vs_rhp_rc   TEXT,
    raw_stats   TEXT   -- JSON or key=value for extra stats/splits
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT,
    action      TEXT,
    teams_found INTEGER,
    records     INTEGER,
    scraped_at  TEXT,
    duration_s  REAL,
    status      TEXT
);

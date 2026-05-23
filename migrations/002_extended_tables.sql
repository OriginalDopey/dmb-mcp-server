CREATE TABLE IF NOT EXISTS league_leaderboards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT NOT NULL,
    board_type  TEXT NOT NULL,
    category    TEXT NOT NULL,
    rank        INTEGER,
    player      TEXT,
    team_abbr   TEXT,
    value       TEXT,
    scraped_at  TEXT
);

CREATE TABLE IF NOT EXISTS fielding_leaders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT NOT NULL,
    position    TEXT NOT NULL,
    rank        INTEGER,
    player      TEXT,
    team_abbr   TEXT,
    gp          TEXT,
    inn         TEXT,
    avg         TEXT,
    po          TEXT,
    a           TEXT,
    e           TEXT,
    tc          TEXT,
    dp          TEXT,
    rf          TEXT,
    scraped_at  TEXT
);

CREATE TABLE IF NOT EXISTS team_vs_team (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT NOT NULL,
    team_name   TEXT,
    team_abbr   TEXT,
    opp_abbr    TEXT NOT NULL,
    record      TEXT,
    scraped_at  TEXT,
    UNIQUE(league_id, team_abbr, opp_abbr)
);

CREATE TABLE IF NOT EXISTS league_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT NOT NULL,
    team_name   TEXT,
    tx_text     TEXT,
    tx_date     TEXT,
    scraped_at  TEXT
);

CREATE TABLE IF NOT EXISTS trade_view (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id   TEXT NOT NULL,
    status      TEXT,
    proposing_team TEXT,
    detail_text TEXT,
    scraped_at  TEXT
);

CREATE TABLE IF NOT EXISTS batting_splits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT NOT NULL,
    league_id   TEXT NOT NULL,
    split_type  TEXT NOT NULL,
    scraped_at  TEXT,
    player      TEXT,
    ab          TEXT,
    h           TEXT,
    doubles     TEXT,
    triples     TEXT,
    hr          TEXT,
    rbi         TEXT,
    ba          TEXT,
    obp         TEXT,
    slg         TEXT,
    stats_json  TEXT
);

CREATE TABLE IF NOT EXISTS pitching_splits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT NOT NULL,
    league_id   TEXT NOT NULL,
    split_type  TEXT NOT NULL,
    scraped_at  TEXT,
    player      TEXT,
    w           TEXT,
    l           TEXT,
    era         TEXT,
    ip          TEXT,
    sv          TEXT,
    k           TEXT,
    bb          TEXT,
    stats_json  TEXT
);

CREATE TABLE IF NOT EXISTS injuries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT NOT NULL,
    league_id   TEXT NOT NULL,
    scraped_at  TEXT,
    section     TEXT,
    player      TEXT,
    positions   TEXT,
    salary      TEXT,
    out_for     TEXT,
    cause       TEXT,
    detail      TEXT
);

CREATE TABLE IF NOT EXISTS park_reference (
    park_name   TEXT PRIMARY KEY,
    scraped_at  TEXT,
    years       TEXT,
    city        TEXT,
    surface     TEXT,
    cover       TEXT,
    dimensions_json TEXT,
    factors_lhb_json TEXT,
    factors_rhb_json TEXT
);

CREATE TABLE IF NOT EXISTS record_boards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    board_key   TEXT NOT NULL,
    stat_name   TEXT NOT NULL,
    rank        INTEGER,
    player      TEXT,
    team_league TEXT,
    value       TEXT,
    scraped_at  TEXT
);

CREATE TABLE IF NOT EXISTS reference_cache (
    cache_key   TEXT PRIMARY KEY,
    scraped_at  TEXT,
    expires_at  TEXT,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_leaderboards_league ON league_leaderboards(league_id, board_type);
CREATE INDEX IF NOT EXISTS idx_fielding_leaders_league ON fielding_leaders(league_id, position);
CREATE INDEX IF NOT EXISTS idx_team_vs_team_league ON team_vs_team(league_id);
CREATE INDEX IF NOT EXISTS idx_league_tx_league ON league_transactions(league_id);
CREATE INDEX IF NOT EXISTS idx_injuries_team ON injuries(team_id);
CREATE INDEX IF NOT EXISTS idx_batting_splits_team ON batting_splits(team_id, split_type);
CREATE INDEX IF NOT EXISTS idx_pitching_splits_team ON pitching_splits(team_id, split_type);

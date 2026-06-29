CREATE TABLE IF NOT EXISTS competitions (
    id          TEXT PRIMARY KEY,   -- football-data.org code: PL, WC, CL …
    name        TEXT NOT NULL,
    code        TEXT NOT NULL,
    country     TEXT,
    season      INTEGER
);

CREATE TABLE IF NOT EXISTS teams (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    short_name  TEXT,
    tla         TEXT                -- three-letter abbreviation: ARS, MCI, BRA
);

CREATE TABLE IF NOT EXISTS matches (
    id              TEXT PRIMARY KEY,
    competition     TEXT    NOT NULL,
    season          INTEGER,
    matchday        INTEGER,
    status          TEXT    NOT NULL,   -- SCHEDULED | IN_PLAY | PAUSED | FINISHED …
    utc_date        TEXT    NOT NULL,   -- ISO 8601
    home_team_id    TEXT    NOT NULL,
    away_team_id    TEXT    NOT NULL,
    home_score      INTEGER,
    away_score      INTEGER,
    ht_home         INTEGER,            -- half-time scores
    ht_away         INTEGER,
    minute          INTEGER,            -- live match minute
    stage           TEXT,               -- GROUP_STAGE | ROUND_OF_16 | FINAL …
    group_name      TEXT,               -- Group A/B … (World Cup) — not 'group': reserved word
    updated_at      TEXT,
    FOREIGN KEY (competition)   REFERENCES competitions(id),
    FOREIGN KEY (home_team_id)  REFERENCES teams(id),
    FOREIGN KEY (away_team_id)  REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS standings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    competition     TEXT    NOT NULL,
    season          INTEGER NOT NULL,
    stage           TEXT,
    group_name      TEXT,
    team_id         TEXT    NOT NULL,
    position        INTEGER NOT NULL,
    played          INTEGER NOT NULL DEFAULT 0,
    won             INTEGER NOT NULL DEFAULT 0,
    drawn           INTEGER NOT NULL DEFAULT 0,
    lost            INTEGER NOT NULL DEFAULT 0,
    goals_for       INTEGER NOT NULL DEFAULT 0,
    goals_against   INTEGER NOT NULL DEFAULT 0,
    goal_diff       INTEGER NOT NULL DEFAULT 0,
    points          INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT,
    -- upsert key: one row per team per competition per season per group
    UNIQUE (competition, season, stage, group_name, team_id),
    FOREIGN KEY (team_id)       REFERENCES teams(id),
    FOREIGN KEY (competition)   REFERENCES competitions(id)
);

CREATE TABLE IF NOT EXISTS scorers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    competition     TEXT    NOT NULL,
    season          INTEGER NOT NULL,
    player_name     TEXT    NOT NULL,
    team_id         TEXT,
    goals           INTEGER NOT NULL DEFAULT 0,
    assists         INTEGER NOT NULL DEFAULT 0,
    penalties       INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT,
    UNIQUE (competition, season, player_name),
    FOREIGN KEY (team_id)       REFERENCES teams(id),
    FOREIGN KEY (competition)   REFERENCES competitions(id)
);
 
-- ── indexes ───────────────────────────────────────────────────────────────
-- designed around the SQL stats agent's most common query patterns
 
CREATE INDEX IF NOT EXISTS idx_matches_competition_season
    ON matches(competition, season);
 
CREATE INDEX IF NOT EXISTS idx_matches_status
    ON matches(status);
 
CREATE INDEX IF NOT EXISTS idx_matches_home_team
    ON matches(home_team_id);
 
CREATE INDEX IF NOT EXISTS idx_matches_away_team
    ON matches(away_team_id);
 
CREATE INDEX IF NOT EXISTS idx_matches_utc_date
    ON matches(utc_date);
 
CREATE INDEX IF NOT EXISTS idx_standings_competition_season
    ON standings(competition, season);
 
CREATE INDEX IF NOT EXISTS idx_scorers_goals
    ON scorers(competition, season, goals DESC);

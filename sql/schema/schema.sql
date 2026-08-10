-- ============================================================================
-- IPL Auction Market Efficiency Analysis -- star schema
-- Milestone 3
-- ============================================================================
-- Grain notes:
--   fact_deliveries : one row per ball bowled (legal or not)
--   fact_wickets    : one row per dismissal (a ball can produce 2)
--   dim_player is a role-playing dimension -- fact_deliveries joins it three
--   times (striker_id, non_striker_id, bowler_id). In Power BI this needs
--   either three duplicated dim_player tables or one table with inactive
--   relationships activated per-visual via USERELATIONSHIP. Decision recorded
--   in docs/PROJECT_SPEC.md section 10.
-- ============================================================================

DROP TABLE IF EXISTS fact_wickets CASCADE;
DROP TABLE IF EXISTS fact_deliveries CASCADE;
DROP TABLE IF EXISTS dim_match CASCADE;
DROP TABLE IF EXISTS dim_season CASCADE;
DROP TABLE IF EXISTS dim_player CASCADE;
DROP TABLE IF EXISTS dim_venue CASCADE;
DROP TABLE IF EXISTS dim_team CASCADE;

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------

CREATE TABLE dim_team (
    team_id     SERIAL PRIMARY KEY,
    team_name   VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE dim_venue (
    venue_id    SERIAL PRIMARY KEY,
    venue_name  VARCHAR(200) UNIQUE NOT NULL  -- canonical, post rename-mapping
);

CREATE TABLE dim_player (
    player_id   VARCHAR(20) PRIMARY KEY,   -- Cricsheet registry id (hex string)
    player_name VARCHAR(150) NOT NULL      -- most frequent name spelling seen for this id
);

CREATE TABLE dim_season (
    season      SMALLINT PRIMARY KEY,
    match_count SMALLINT NOT NULL
);

CREATE TABLE dim_match (
    match_id    VARCHAR(20) PRIMARY KEY,   -- Cricsheet match id
    season      SMALLINT NOT NULL REFERENCES dim_season(season),
    match_date  DATE,
    venue_id    INT REFERENCES dim_venue(venue_id),
    team1_id    INT REFERENCES dim_team(team_id),
    team2_id    INT REFERENCES dim_team(team_id),
    match_type  VARCHAR(20)
);

-- ---------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------

CREATE TABLE fact_deliveries (
    delivery_id      BIGSERIAL PRIMARY KEY,
    match_id         VARCHAR(20) NOT NULL REFERENCES dim_match(match_id),
    season           SMALLINT NOT NULL REFERENCES dim_season(season),
    innings_number   SMALLINT NOT NULL,
    is_super_over    BOOLEAN NOT NULL,
    batting_team_id  INT REFERENCES dim_team(team_id),
    bowling_team_id  INT REFERENCES dim_team(team_id),
    over_number      SMALLINT NOT NULL,
    delivery_index   SMALLINT NOT NULL,     -- position within the over, includes illegal balls
    striker_id       VARCHAR(20) REFERENCES dim_player(player_id),
    non_striker_id   VARCHAR(20) REFERENCES dim_player(player_id),
    bowler_id        VARCHAR(20) REFERENCES dim_player(player_id),
    runs_batter      SMALLINT NOT NULL,
    runs_extras      SMALLINT NOT NULL,
    runs_total       SMALLINT NOT NULL,
    extras_wides     SMALLINT NOT NULL DEFAULT 0,
    extras_noballs   SMALLINT NOT NULL DEFAULT 0,
    extras_byes      SMALLINT NOT NULL DEFAULT 0,
    extras_legbyes   SMALLINT NOT NULL DEFAULT 0,
    extras_penalty   SMALLINT NOT NULL DEFAULT 0,
    is_legal_ball    BOOLEAN NOT NULL,
    wicket_count     SMALLINT NOT NULL DEFAULT 0,
    UNIQUE (match_id, innings_number, over_number, delivery_index)
);

CREATE TABLE fact_wickets (
    wicket_id        BIGSERIAL PRIMARY KEY,
    match_id         VARCHAR(20) NOT NULL,
    season           SMALLINT NOT NULL REFERENCES dim_season(season),
    innings_number   SMALLINT NOT NULL,
    is_super_over    BOOLEAN NOT NULL,
    over_number      SMALLINT NOT NULL,
    delivery_index   SMALLINT NOT NULL,
    player_out_id    VARCHAR(20) REFERENCES dim_player(player_id),
    kind             VARCHAR(30) NOT NULL,
    bowler_credited  BOOLEAN NOT NULL,
    bowler_id        VARCHAR(20) REFERENCES dim_player(player_id),
    fielder_names    TEXT,
    FOREIGN KEY (match_id, innings_number, over_number, delivery_index)
        REFERENCES fact_deliveries (match_id, innings_number, over_number, delivery_index)
);

-- ---------------------------------------------------------------------------
-- Indexes -- Milestone 5's phase-wise aggregations filter/group on these
-- ---------------------------------------------------------------------------

CREATE INDEX idx_deliveries_striker ON fact_deliveries(striker_id);
CREATE INDEX idx_deliveries_bowler  ON fact_deliveries(bowler_id);
CREATE INDEX idx_deliveries_season  ON fact_deliveries(season);
CREATE INDEX idx_deliveries_match   ON fact_deliveries(match_id);
CREATE INDEX idx_wickets_player_out ON fact_wickets(player_out_id);
CREATE INDEX idx_wickets_bowler     ON fact_wickets(bowler_id);

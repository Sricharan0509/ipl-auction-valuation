"""
load_to_postgres.py
====================
MILESTONE 3 -- Load fact_deliveries.csv / fact_wickets.csv into the
PostgreSQL star schema defined in sql/schema/schema.sql.

WHAT THIS DOES
--------------
1. Reads the two CSVs from Milestone 2.
2. Derives every dimension table (dim_team, dim_venue, dim_player,
   dim_season, dim_match) from the CSV contents -- there is no separate
   dimension source, the CSVs contain everything needed.
3. Maps fact rows onto the generated surrogate keys.
4. Truncates and reloads everything, so re-running this script after a fresh
   parse is always safe -- consistent with "everything in processed/ is
   reproducible" from CLAUDE.md.

WHY DIMENSIONS ARE BUILT HERE, NOT IN THE PARSER
--------------------------------------------------
The parser's job is one match file -> rows. Deduplicating players/teams/
venues into one canonical row each is a set operation over the WHOLE
dataset, which only makes sense once all matches are combined -- i.e. here.

VENUE CONSOLIDATION
--------------------
Checked against the 2022-2026 data directly: 19 distinct venue strings, and
exactly one real duplicate -- Punjab Kings' new home ground appears as both
"...Mullanpur" and "...New Chandigarh". Everything else in this window is
already a distinct, fully-qualified ground name (unlike the pre-2022 data,
which has far messier duplicates -- out of scope since it's outside the
analysis window). Extend VENUE_RENAMES if a future refresh adds more overlap.

HOW TO RUN
----------
    python src/ingestion/load_to_postgres.py

Requires: a running PostgreSQL server, sql/schema/schema.sql already applied,
and a .env file with DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD.
"""

import os
from pathlib import Path
from collections import Counter

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DELIVERIES_CSV = PROCESSED_DIR / "fact_deliveries.csv"
WICKETS_CSV = PROCESSED_DIR / "fact_wickets.csv"

VENUE_RENAMES = {
    "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur":
        "Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh",
}

UNKNOWN_PLAYER_ID = "UNKNOWN"
UNKNOWN_PLAYER_NAME = "Unknown / unregistered player"


def get_engine():
    """
    Built via URL.create() rather than an f-string -- passwords containing
    reserved URL characters (@, :, /, etc.) silently break a hand-built
    connection string. URL.create() percent-encodes each component so any
    password value is safe.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
    )
    return create_engine(url)


def reset_tables(engine):
    """Truncate in one CASCADE statement so re-running this script is always safe."""
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE TABLE fact_wickets, fact_deliveries, dim_match, "
            "dim_season, dim_player, dim_venue, dim_team RESTART IDENTITY CASCADE;"
        ))


def load_csvs():
    deliveries = pd.read_csv(DELIVERIES_CSV, dtype={"match_id": str})
    wickets = pd.read_csv(WICKETS_CSV, dtype={"match_id": str})
    return deliveries, wickets


def build_dim_team(deliveries):
    names = pd.concat([deliveries["batting_team"], deliveries["bowling_team"]]).dropna().unique()
    dim_team = pd.DataFrame({"team_name": sorted(names)})
    dim_team.insert(0, "team_id", range(1, len(dim_team) + 1))
    return dim_team


def build_dim_venue(deliveries):
    raw_venues = deliveries["venue"].dropna().unique()
    canonical = sorted({VENUE_RENAMES.get(v, v) for v in raw_venues})
    dim_venue = pd.DataFrame({"venue_name": canonical})
    dim_venue.insert(0, "venue_id", range(1, len(dim_venue) + 1))
    return dim_venue


def build_dim_player(deliveries, wickets):
    """
    One row per player_id. Canonical name = the most common name string seen
    for that id, since the same id occasionally shows minor spelling
    variation across matches (initials, punctuation).
    """
    name_counts = {}

    def tally(id_col, name_col, df):
        for pid, name in zip(df[id_col], df[name_col]):
            if pd.isna(pid) or pd.isna(name):
                continue
            name_counts.setdefault(pid, Counter())[name] += 1

    tally("striker_id", "striker_name", deliveries)
    tally("non_striker_id", "non_striker_name", deliveries)
    tally("bowler_id", "bowler_name", deliveries)
    tally("player_out_id", "player_out_name", wickets)
    tally("bowler_id", "bowler_name", wickets)

    rows = [
        {"player_id": pid, "player_name": counter.most_common(1)[0][0]}
        for pid, counter in name_counts.items()
    ]
    rows.append({"player_id": UNKNOWN_PLAYER_ID, "player_name": UNKNOWN_PLAYER_NAME})
    return pd.DataFrame(rows)


def build_dim_season(deliveries):
    match_counts = deliveries.groupby("season")["match_id"].nunique()
    return pd.DataFrame({
        "season": match_counts.index,
        "match_count": match_counts.values,
    })


def build_dim_match(deliveries):
    """
    One row per match_id. team1/team2 are just the two distinct teams seen
    in that match's deliveries -- order isn't meaningful, there's no "home
    team" concept in a neutral-venue T20 league.
    """
    rows = []
    for match_id, g in deliveries.groupby("match_id"):
        teams = sorted(set(g["batting_team"]) | set(g["bowling_team"]))
        venue_raw = g["venue"].iloc[0]
        rows.append({
            "match_id": match_id,
            "season": g["season"].iloc[0],
            "match_date": g["match_date"].iloc[0],
            "venue_name": VENUE_RENAMES.get(venue_raw, venue_raw),
            "match_type": g["match_type"].iloc[0],
            "team1_name": teams[0] if len(teams) > 0 else None,
            "team2_name": teams[1] if len(teams) > 1 else None,
        })
    return pd.DataFrame(rows)


def main():
    print("Loading CSVs...")
    deliveries, wickets = load_csvs()
    print(f"  fact_deliveries.csv: {len(deliveries):,} rows")
    print(f"  fact_wickets.csv:    {len(wickets):,} rows")

    print("\nBuilding dimensions...")
    dim_team = build_dim_team(deliveries)
    dim_venue = build_dim_venue(deliveries)
    dim_player = build_dim_player(deliveries, wickets)
    dim_season = build_dim_season(deliveries)
    dim_match = build_dim_match(deliveries)

    print(f"  dim_team:   {len(dim_team)}")
    print(f"  dim_venue:  {len(dim_venue)}")
    print(f"  dim_player: {len(dim_player)}")
    print(f"  dim_season: {len(dim_season)}")
    print(f"  dim_match:  {len(dim_match)}")

    team_id_map = dict(zip(dim_team["team_name"], dim_team["team_id"]))
    venue_id_map = dict(zip(dim_venue["venue_name"], dim_venue["venue_id"]))

    dim_match["venue_id"] = dim_match["venue_name"].map(venue_id_map)
    dim_match["team1_id"] = dim_match["team1_name"].map(team_id_map)
    dim_match["team2_id"] = dim_match["team2_name"].map(team_id_map)
    dim_match = dim_match.drop(columns=["venue_name", "team1_name", "team2_name"])

    # Orphan check -- any player id referenced in facts but missing from
    # dim_player would violate the FK. Should be zero given the registry
    # coverage confirmed in Milestone 2's audit, but verify, don't assume.
    known_ids = set(dim_player["player_id"])
    for col in ["striker_id", "non_striker_id", "bowler_id"]:
        deliveries[col] = deliveries[col].fillna(UNKNOWN_PLAYER_ID)
        missing = set(deliveries[col]) - known_ids
        if missing:
            print(f"  WARNING: {len(missing)} unmapped ids in {col}, mapped to UNKNOWN")
            deliveries.loc[~deliveries[col].isin(known_ids), col] = UNKNOWN_PLAYER_ID

    wickets["player_out_id"] = wickets["player_out_id"].fillna(UNKNOWN_PLAYER_ID)
    wickets["bowler_id"] = wickets["bowler_id"].fillna(UNKNOWN_PLAYER_ID)

    print("\nMapping fact tables onto surrogate keys...")
    fact_deliveries = deliveries.copy()
    fact_deliveries["batting_team_id"] = fact_deliveries["batting_team"].map(team_id_map)
    fact_deliveries["bowling_team_id"] = fact_deliveries["bowling_team"].map(team_id_map)
    fact_deliveries = fact_deliveries.rename(columns={"over": "over_number"})
    fact_deliveries = fact_deliveries[[
        "match_id", "season", "innings_number", "is_super_over",
        "batting_team_id", "bowling_team_id", "over_number", "delivery_index",
        "striker_id", "non_striker_id", "bowler_id",
        "runs_batter", "runs_extras", "runs_total",
        "extras_wides", "extras_noballs", "extras_byes", "extras_legbyes", "extras_penalty",
        "is_legal_ball", "wicket_count",
    ]]

    fact_wickets = wickets.rename(columns={"over": "over_number"})
    fact_wickets = fact_wickets[[
        "match_id", "season", "innings_number", "is_super_over",
        "over_number", "delivery_index", "player_out_id", "kind",
        "bowler_credited", "bowler_id", "fielder_names",
    ]]

    print("\nConnecting to PostgreSQL...")
    engine = get_engine()

    print("Truncating existing tables...")
    reset_tables(engine)

    print("Loading dimensions...")
    dim_team.to_sql("dim_team", engine, if_exists="append", index=False)
    dim_venue.to_sql("dim_venue", engine, if_exists="append", index=False)
    dim_player.to_sql("dim_player", engine, if_exists="append", index=False)
    dim_season.to_sql("dim_season", engine, if_exists="append", index=False)
    dim_match.to_sql("dim_match", engine, if_exists="append", index=False)

    print("Loading facts...")
    fact_deliveries.to_sql("fact_deliveries", engine, if_exists="append", index=False, chunksize=5000)
    fact_wickets.to_sql("fact_wickets", engine, if_exists="append", index=False, chunksize=5000)

    print("\nDone. Row counts loaded:")
    print(f"  dim_team:        {len(dim_team)}")
    print(f"  dim_venue:       {len(dim_venue)}")
    print(f"  dim_player:      {len(dim_player)}")
    print(f"  dim_season:      {len(dim_season)}")
    print(f"  dim_match:       {len(dim_match)}")
    print(f"  fact_deliveries: {len(fact_deliveries)}")
    print(f"  fact_wickets:    {len(fact_wickets)}")


if __name__ == "__main__":
    main()

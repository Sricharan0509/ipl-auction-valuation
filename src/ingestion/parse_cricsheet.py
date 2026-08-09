"""
parse_cricsheet.py
===================
MILESTONE 2, STEP 2 — Parse raw Cricsheet JSON into two relational tables.

OUTPUT
------
data/processed/fact_deliveries.csv
    Grain: one row per ball bowled (legal or not).
data/processed/fact_wickets.csv
    Grain: one row per dismissal.

WHY TWO TABLES, NOT ONE
------------------------
A single delivery can produce two dismissals (e.g. a run out off a wide, or
"obstructing the field" alongside a run out attempt). Cramming wicket detail
into fact_deliveries as flat columns would either lose the second dismissal or
break the one-row-per-ball grain. Splitting them keeps fact_deliveries at a
clean grain and fact_wickets exhaustive.

SCOPE
-----
Only seasons 2022-2026 are written to the output tables (PROJECT_SPEC.md
analysis window). Older raw JSONs are still read from data/raw/ but filtered
out here, not deleted -- keep them for potential future use.

CORRECTNESS RULES APPLIED (see CLAUDE.md for the full list)
-------------------------------------------------------------
1. Wides/no-balls are NOT legal balls -> not a ball faced. Runs still charge
   the bowler.
2. Byes/legbyes ARE legal balls (faced) but credit neither batter nor bowler
   for runs -- Cricsheet's runs.batter field already excludes them, so no
   special-casing needed there.
3. Bowler wicket credit is restricted to a fixed set of dismissal kinds.
4. extras and wickets are optional keys -- always .get().
5. wickets is a list -- iterate it, don't assume length 1.
6. Super overs are innings index 3+ -- flagged, not excluded here (exclusion
   happens in the metrics query, milestone 5), so the raw signal isn't lost.
7. Retained-player / price logic doesn't touch this script at all.
8. Overs are zero-indexed in Cricsheet's schema -- verify against
   docs/data_notes.md from the explorer script before trusting phase logic
   built on top of this table later.

HOW TO RUN
----------
    python src/ingestion/parse_cricsheet.py

Expects Cricsheet JSONs in data/raw/. Requires pandas.
"""

import json
import re
from pathlib import Path
from collections import Counter

import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DELIVERIES_OUT = PROCESSED_DIR / "fact_deliveries.csv"
WICKETS_OUT = PROCESSED_DIR / "fact_wickets.csv"

ANALYSIS_WINDOW = set(range(2022, 2027))  # PROJECT_SPEC.md: 2022-2026

# Franchise renames -- consolidate under the CURRENT name so a player's
# history reads as one franchise, not three. Extend if data_notes.md surfaces
# a variant not listed here.
TEAM_RENAMES = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}

# Bowler wicket credit -- CLAUDE.md rule 3.
BOWLER_CREDITED_KINDS = {
    "bowled", "caught", "lbw", "stumped", "hit wicket", "caught and bowled",
}
BOWLER_NOT_CREDITED_KINDS = {
    "run out", "retired hurt", "retired out", "retired not out",
    "obstructing the field", "handled the ball", "timed out",
}
KNOWN_WICKET_KINDS = BOWLER_CREDITED_KINDS | BOWLER_NOT_CREDITED_KINDS


def normalize_team(name):
    return TEAM_RENAMES.get(name, name)


def normalize_season(season_raw):
    """
    '2020/21' -> 2020, '2021' -> 2021, 2021 -> 2021.
    IPL seasons are named by their starting year -- take the first 4-digit
    number found. Returns None if nothing parses, so callers can skip
    cleanly instead of crashing on a malformed value.
    """
    match = re.search(r"\d{4}", str(season_raw))
    return int(match.group()) if match else None


def find_match_files():
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"{RAW_DIR} does not exist. Run Milestone 1's data download first.")
    files = sorted(f for f in RAW_DIR.glob("*.json") if f.stem.isdigit())
    if not files:
        raise FileNotFoundError(f"No match JSONs found in {RAW_DIR}.")
    return files


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def other_team(teams, batting_team):
    """teams is always a 2-element list in IPL matches -- return whichever isn't batting."""
    others = [t for t in teams if t != batting_team]
    return others[0] if others else None


def parse_match(path, delivery_rows, wicket_rows, unknown_kinds, stats):
    data = load_json(path)
    info = data.get("info", {})
    match_id = path.stem

    season = normalize_season(info.get("season"))
    if season not in ANALYSIS_WINDOW:
        stats["skipped_out_of_window"] += 1
        return

    dates = info.get("dates", [])
    match_date = dates[0] if dates else None
    venue = info.get("venue")
    match_type = info.get("match_type")
    teams = info.get("teams", [])
    registry = info.get("registry", {}).get("people", {})

    for innings_idx, inn in enumerate(data.get("innings", []), start=1):
        is_super_over = innings_idx > 2
        batting_team = normalize_team(inn.get("team"))
        bowling_team = normalize_team(other_team(teams, inn.get("team")))

        for over in inn.get("overs", []):
            over_num = over.get("over")

            for delivery_idx, d in enumerate(over.get("deliveries", []), start=1):
                striker = d.get("batter")
                non_striker = d.get("non_striker")
                bowler = d.get("bowler")

                runs = d.get("runs", {})
                extras = d.get("extras", {})

                extras_wides = extras.get("wides", 0)
                extras_noballs = extras.get("noballs", 0)
                extras_byes = extras.get("byes", 0)
                extras_legbyes = extras.get("legbyes", 0)
                extras_penalty = extras.get("penalty", 0)

                is_legal_ball = extras_wides == 0 and extras_noballs == 0

                wickets = d.get("wickets", [])

                delivery_rows.append({
                    "match_id": match_id,
                    "season": season,
                    "match_date": match_date,
                    "venue": venue,
                    "match_type": match_type,
                    "innings_number": innings_idx,
                    "is_super_over": is_super_over,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "over": over_num,
                    "delivery_index": delivery_idx,
                    "striker_name": striker,
                    "striker_id": registry.get(striker),
                    "non_striker_name": non_striker,
                    "non_striker_id": registry.get(non_striker),
                    "bowler_name": bowler,
                    "bowler_id": registry.get(bowler),
                    "runs_batter": runs.get("batter", 0),
                    "runs_extras": runs.get("extras", 0),
                    "runs_total": runs.get("total", 0),
                    "extras_wides": extras_wides,
                    "extras_noballs": extras_noballs,
                    "extras_byes": extras_byes,
                    "extras_legbyes": extras_legbyes,
                    "extras_penalty": extras_penalty,
                    "is_legal_ball": is_legal_ball,
                    "wicket_count": len(wickets),
                })

                for w in wickets:
                    kind = w.get("kind", "unknown")
                    if kind not in KNOWN_WICKET_KINDS:
                        unknown_kinds[kind] += 1

                    player_out = w.get("player_out")
                    fielders = w.get("fielders", [])
                    fielder_names = ";".join(
                        f.get("name", "") for f in fielders if isinstance(f, dict)
                    )

                    wicket_rows.append({
                        "match_id": match_id,
                        "season": season,
                        "innings_number": innings_idx,
                        "is_super_over": is_super_over,
                        "over": over_num,
                        "delivery_index": delivery_idx,
                        "player_out_name": player_out,
                        "player_out_id": registry.get(player_out),
                        "kind": kind,
                        "bowler_credited": kind in BOWLER_CREDITED_KINDS,
                        "bowler_name": bowler,
                        "bowler_id": registry.get(bowler),
                        "fielder_names": fielder_names,
                    })

    stats["matches_parsed"] += 1


def main():
    files = find_match_files()
    print(f"Found {len(files)} raw match files.")

    delivery_rows = []
    wicket_rows = []
    unknown_kinds = Counter()
    parse_failures = []
    stats = Counter()

    for i, path in enumerate(files, start=1):
        try:
            parse_match(path, delivery_rows, wicket_rows, unknown_kinds, stats)
        except Exception as e:
            parse_failures.append((path.name, str(e)))

        if i % 200 == 0:
            print(f"  ...{i}/{len(files)} files scanned")

    print(f"\nMatches in analysis window (2022-2026) parsed: {stats['matches_parsed']}")
    print(f"Matches skipped (outside window):               {stats['skipped_out_of_window']}")
    print(f"Parse failures:                                  {len(parse_failures)}")
    if parse_failures:
        print("Failed files (first 10):")
        for name, err in parse_failures[:10]:
            print(f"  {name}: {err}")

    if unknown_kinds:
        print("\nWARNING -- wicket kinds not in the known credited/not-credited sets:")
        for kind, count in unknown_kinds.most_common():
            print(f"  {kind!r}: {count} occurrences -- defaulted to bowler_credited=False")
        print("Add these to BOWLER_CREDITED_KINDS or BOWLER_NOT_CREDITED_KINDS and re-run.")

    deliveries_df = pd.DataFrame(delivery_rows)
    wickets_df = pd.DataFrame(wicket_rows)

    print(f"\nfact_deliveries: {len(deliveries_df):,} rows")
    print(f"fact_wickets:    {len(wickets_df):,} rows")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    deliveries_df.to_csv(DELIVERIES_OUT, index=False, encoding="utf-8")
    wickets_df.to_csv(WICKETS_OUT, index=False, encoding="utf-8")

    print(f"\nWritten to:\n  {DELIVERIES_OUT}\n  {WICKETS_OUT}")


if __name__ == "__main__":
    main()

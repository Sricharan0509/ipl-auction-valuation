"""
explore_cricsheet_json.py
=========================
MILESTONE 2, STEP 1 — Understand the raw data before writing the parser.

WHAT THIS DOES
--------------
1. Finds every match JSON in data/raw/
2. Prints the full structure of ONE file so you can see the shape
3. Audits ALL files for which fields exist, how often, and what values they take
4. Writes everything to docs/data_notes.md so you have a permanent reference

WHY THIS EXISTS
---------------
Cricsheet JSON has OPTIONAL fields. A delivery has "extras" only if there were
extras. It has "wickets" only if a wicket fell. If you write a parser assuming
every field is always present, it crashes on file 400 of 1000. This script tells
you exactly which fields are optional BEFORE you write the parser.

HOW TO RUN
----------
    python src/ingestion/explore_cricsheet_json.py

Expects Cricsheet JSONs in data/raw/. Writes docs/data_notes.md.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
# Path(__file__) is this file's location. .parents[2] climbs two folders up
# (ingestion -> src -> project root). This makes the script work no matter
# which directory you run it from — a small thing that prevents a lot of pain.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUT_FILE = DOCS_DIR / "data_notes.md"

# Set to None to audit every file. Set to a number to sample during testing —
# auditing 1000+ files takes a minute, and you often just want a quick look.
SAMPLE_LIMIT = None

# We collect output lines in a list and write once at the end, rather than
# opening the file repeatedly. Cheaper and keeps the writing logic in one place.
report = []


def out(text=""):
    """Print to console AND capture for the markdown report."""
    print(text)
    report.append(text)


# ---------------------------------------------------------------------------
# STEP 0 — Find the files
# ---------------------------------------------------------------------------
def find_match_files():
    """
    Return a sorted list of .json files in data/raw/.

    Cricsheet's zip also contains README.txt and sometimes a non-match JSON,
    so we filter to numeric filenames — Cricsheet names match files by their
    match ID (e.g. 1234567.json).
    """
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"{RAW_DIR} does not exist. Download the IPL JSON zip from "
            f"cricsheet.org/downloads/ and extract it there."
        )

    files = sorted(
        f for f in RAW_DIR.glob("*.json") if f.stem.isdigit()
    )

    if not files:
        raise FileNotFoundError(
            f"No match JSONs found in {RAW_DIR}. Check the zip extracted correctly."
        )

    return files


def load_json(path):
    """Load one JSON file. encoding='utf-8' matters — player names contain accents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# STEP 1 — Inspect ONE file in full
# ---------------------------------------------------------------------------
def inspect_single_file(path):
    """Print the complete structure of one match so you can see the shape."""
    data = load_json(path)

    out(f"\n{'=' * 70}")
    out(f"# 1. SINGLE FILE INSPECTION — {path.name}")
    out(f"{'=' * 70}")

    out(f"\n## Top-level keys\n")
    out(f"    {list(data.keys())}")
    out("\nCricsheet files always have three: meta, info, innings.")
    out("  meta   = data format version and creation date (rarely useful)")
    out("  info   = match-level context (teams, venue, date, players, registry)")
    out("  innings = the actual ball-by-ball data — this is where the value is")

    # --- meta ---
    out(f"\n## meta\n")
    out("```json")
    out(json.dumps(data.get("meta", {}), indent=2))
    out("```")

    # --- info ---
    info = data.get("info", {})
    out(f"\n## info — keys present\n")
    for key in sorted(info.keys()):
        value = info[key]
        # Show the type and a short preview so the printout stays readable
        if isinstance(value, dict):
            preview = f"dict with keys {list(value.keys())[:6]}"
        elif isinstance(value, list):
            preview = f"list[{len(value)}] e.g. {value[:2]}"
        else:
            preview = repr(value)
        out(f"    {key:20} -> {preview}")

    # The registry is the single most important thing in info.
    # It maps display names to STABLE player IDs. Names change spelling across
    # sources ("V Kohli" vs "Virat Kohli"); IDs never do. Every join in this
    # project should use the ID, not the name.
    registry = info.get("registry", {}).get("people", {})
    out(f"\n## registry.people — {len(registry)} players in this match\n")
    for name, pid in list(registry.items())[:5]:
        out(f"    {name:25} -> {pid}")
    out("\n    ^ USE THESE IDs FOR ALL JOINS. Never join on player name.")

    # --- innings ---
    innings = data.get("innings", [])
    out(f"\n## innings — {len(innings)} innings in this match\n")
    out("Structure: innings -> overs -> deliveries")
    out("  Note: a match can have 1 innings (rain), 2 (normal), or more (super over).")

    if innings:
        first = innings[0]
        out(f"\n  First innings keys: {list(first.keys())}")
        out(f"  Batting team: {first.get('team')}")

        overs = first.get("overs", [])
        out(f"  Overs in this innings: {len(overs)}")

        if overs:
            first_over = overs[0]
            # IMPORTANT: check whether Cricsheet numbers overs from 0 or 1.
            # The value printed below is the raw value — verify it yourself.
            out(f"\n  First over object keys: {list(first_over.keys())}")
            out(f"  Raw 'over' value of the FIRST over: {first_over.get('over')}")
            out("  ^ If this is 0, overs are ZERO-INDEXED. Your phase logic must")
            out("    account for that: powerplay = over 0-5, not 1-6.")

            out(f"\n## Every delivery in the first over\n")
            for i, d in enumerate(first_over.get("deliveries", []), start=1):
                out(f"  --- delivery {i} ---")
                out(json.dumps(d, indent=4))

    out("\n## Full raw structure of the first innings (truncated)\n")
    out("```json")
    truncated = json.dumps(innings[0], indent=2)[:2000] if innings else "{}"
    out(truncated + "\n... (truncated)")
    out("```")


# ---------------------------------------------------------------------------
# STEP 2 — Audit ALL files for field presence and value ranges
# ---------------------------------------------------------------------------
def audit_all_files(files):
    """
    Walk every match and count how often each field appears.

    This is the part that saves you from parser crashes. Any field appearing in
    fewer than 100% of records is OPTIONAL and needs a .get() with a default.
    """
    out(f"\n\n{'=' * 70}")
    out(f"# 2. FULL AUDIT — {len(files)} files")
    out(f"{'=' * 70}")

    info_keys = Counter()
    delivery_keys = Counter()
    extras_types = Counter()
    wicket_kinds = Counter()
    seasons = Counter()
    innings_counts = Counter()
    venues = Counter()
    teams = Counter()
    balls_per_over_values = Counter()
    match_types = Counter()

    total_deliveries = 0
    total_matches = 0
    files_with_super_over = 0
    files_missing_registry = []
    parse_failures = []

    # Track the maximum over number seen, to confirm indexing
    max_over_seen = -1
    min_over_seen = 999

    for path in files:
        try:
            data = load_json(path)
        except Exception as e:
            # Never let one corrupt file kill the whole run. Log and continue.
            parse_failures.append((path.name, str(e)))
            continue

        total_matches += 1
        info = data.get("info", {})

        for k in info.keys():
            info_keys[k] += 1

        seasons[str(info.get("season"))] += 1
        venues[info.get("venue", "UNKNOWN")] += 1
        balls_per_over_values[info.get("balls_per_over")] += 1
        match_types[info.get("match_type")] += 1

        for t in info.get("teams", []):
            teams[t] += 1

        if not info.get("registry", {}).get("people"):
            files_missing_registry.append(path.name)

        innings = data.get("innings", [])
        innings_counts[len(innings)] += 1
        if len(innings) > 2:
            files_with_super_over += 1

        for inn in innings:
            for over in inn.get("overs", []):
                over_num = over.get("over")
                if isinstance(over_num, int):
                    max_over_seen = max(max_over_seen, over_num)
                    min_over_seen = min(min_over_seen, over_num)

                for d in over.get("deliveries", []):
                    total_deliveries += 1
                    for k in d.keys():
                        delivery_keys[k] += 1

                    # extras is a dict whose KEYS are the extra type
                    for etype in d.get("extras", {}).keys():
                        extras_types[etype] += 1

                    # wickets is a LIST — a single delivery can dismiss two
                    # players (e.g. run out + retired). Always iterate it.
                    for w in d.get("wickets", []):
                        wicket_kinds[w.get("kind", "UNKNOWN")] += 1

    # ---- Report ----
    out(f"\n## Totals\n")
    out(f"    Matches parsed:      {total_matches}")
    out(f"    Total deliveries:    {total_deliveries:,}")
    out(f"    Parse failures:      {len(parse_failures)}")

    if parse_failures:
        out("\n    Failed files:")
        for name, err in parse_failures[:10]:
            out(f"      {name}: {err}")

    out(f"\n## Over indexing\n")
    out(f"    Lowest 'over' value seen:  {min_over_seen}")
    out(f"    Highest 'over' value seen: {max_over_seen}")
    if min_over_seen == 0:
        out("    => ZERO-INDEXED. Powerplay = over 0-5. Death = over 15-19.")
    else:
        out("    => ONE-INDEXED. Powerplay = over 1-6. Death = over 16-20.")

    out(f"\n## info fields — presence across {total_matches} matches\n")
    out(f"    {'field':<22} {'count':>8}  {'%':>7}   status")
    for k, c in info_keys.most_common():
        pct = 100 * c / total_matches
        status = "always" if c == total_matches else "OPTIONAL"
        out(f"    {k:<22} {c:>8}  {pct:6.1f}%   {status}")

    out(f"\n## delivery fields — presence across {total_deliveries:,} deliveries\n")
    out(f"    {'field':<22} {'count':>10}  {'%':>7}   status")
    for k, c in delivery_keys.most_common():
        pct = 100 * c / total_deliveries
        status = "always" if c == total_deliveries else "OPTIONAL"
        out(f"    {k:<22} {c:>10}  {pct:6.1f}%   {status}")
    out("\n    ^ Any field marked OPTIONAL must be read with .get(), never d['field'].")

    out(f"\n## extras types found\n")
    for k, c in extras_types.most_common():
        out(f"    {k:<15} {c:>10,}")
    out("""
    CRITICAL PARSING RULE:
      wides   -> NOT a legal ball. Does NOT count as a ball faced by the batter.
                 Runs DO count against the bowler.
      noballs -> NOT a legal ball. Does NOT count as a ball faced.
                 Runs DO count against the bowler.
      byes    -> IS a legal ball (counts as ball faced), but runs are NOT
                 credited to the batter AND are NOT charged to the bowler.
      legbyes -> Same as byes.
      penalty -> Rare. Not attributable to either player.

    Get this wrong and every strike rate and economy rate in the project is wrong.""")

    out(f"\n## wicket kinds found\n")
    for k, c in wicket_kinds.most_common():
        out(f"    {k:<25} {c:>8,}")
    out("""
    BOWLER CREDIT RULE:
      Credited to bowler:     bowled, caught, lbw, stumped, hit wicket,
                              caught and bowled
      NOT credited to bowler: run out, retired hurt, retired out,
                              obstructing the field, handled the ball,
                              timed out
    A wicket falling is not the same as the bowler taking a wicket.""")

    out(f"\n## innings count per match\n")
    for k, c in sorted(innings_counts.items()):
        label = {1: "(rain-affected / abandoned)", 2: "(normal)"}.get(k, "(SUPER OVER)")
        out(f"    {k} innings: {c:>5} matches  {label}")
    out(f"\n    Matches with a super over: {files_with_super_over}")
    out("    DECISION NEEDED: exclude super overs from player metrics. They are")
    out("    a different competitive context and distort strike rates. Document it.")

    out(f"\n## seasons\n")
    for k, c in sorted(seasons.items()):
        out(f"    {k:<12} {c:>5} matches")
    out("\n    NOTE: season values may be '2020/21' style for split-year seasons.")
    out("    You will need to normalise these to a single year for joining to")
    out("    auction data. Decide the rule and document it.")

    out(f"\n## balls_per_over values\n")
    for k, c in balls_per_over_values.most_common():
        out(f"    {k}: {c} matches")

    out(f"\n## match_type values\n")
    for k, c in match_types.most_common():
        out(f"    {k}: {c} matches")

    out(f"\n## teams (watch for franchise renames)\n")
    for k, c in teams.most_common():
        out(f"    {k:<35} {c:>5}")
    out("""
    RENAMES TO HANDLE:
      Delhi Daredevils        -> Delhi Capitals
      Kings XI Punjab         -> Punjab Kings
      Royal Challengers Bangalore -> Royal Challengers Bengaluru
      Rising Pune Supergiant / Supergiants (both spellings exist)
    Build a dim_team mapping table so these consolidate correctly.""")

    out(f"\n## venues — {len(venues)} distinct\n")
    for k, c in venues.most_common(15):
        out(f"    {k:<50} {c:>4}")
    out("""
    NOTE: the same ground can appear under multiple names (with and without
    city suffix, sponsor names). Check for near-duplicates and build a
    venue mapping table.""")

    if files_missing_registry:
        out(f"\n## WARNING — {len(files_missing_registry)} files have no registry")
        for f in files_missing_registry[:10]:
            out(f"    {f}")
        out("    These need name-based fallback matching.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    files = find_match_files()

    if SAMPLE_LIMIT:
        files = files[:SAMPLE_LIMIT]

    out("# Cricsheet Data Notes")
    out(f"\nAuto-generated by `explore_cricsheet_json.py`")
    out(f"Source directory: `{RAW_DIR}`")
    out(f"Files found: {len(files)}")

    inspect_single_file(files[0])
    audit_all_files(files)

    out(f"\n\n{'=' * 70}")
    out("# 3. DECISIONS TO RECORD")
    out(f"{'=' * 70}")
    out("""
Fill these in as you make them. They are the questions interviewers ask.

| Decision | Choice | Reasoning |
|---|---|---|
| Over indexing | | |
| Super over handling | | |
| Season normalisation rule | | |
| Wides/no-balls in balls faced | | |
| Byes/legbyes attribution | | |
| Bowler wicket credit rule | | |
| Franchise rename consolidation | | |
| Venue name consolidation | | |
| Analysis window (seasons) | | |
""")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n\nWritten to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
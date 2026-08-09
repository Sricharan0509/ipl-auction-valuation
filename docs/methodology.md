# Methodology Log

## Milestone 1 — Environment & repo scaffold

- Repo structure follows the layout fixed in CLAUDE.md: data/{raw,external,processed},
  src/{ingestion,transformation}, sql/{schema,analysis}, dashboard/, docs/.
- data/raw/ and data/processed/ are gitignored — raw data is re-downloaded from
  Cricsheet, processed outputs are reproducible by re-running the pipeline scripts.
  Neither belongs in version control.
- Python 3.11+ in a local venv (venv/), not a global install or conda env, so the
  environment is fully reproducible from requirements.txt.
- Cricsheet IPL JSON pulled from https://cricsheet.org/downloads/ipl_json.zip
  (full history, filtered to the 2021-2025 analysis window at parse time in
  Milestone 2). People register from https://cricsheet.org/register/people.csv
  for player-ID reconciliation.


## Milestone 2 — JSON parsing → fact_deliveries / fact_wickets

- Parsed 367 matches (2022-2026 window) from 1,243 total raw JSONs into two
  CSVs: fact_deliveries.csv (87,690 rows, one row per ball) and
  fact_wickets.csv (4,466 rows, one row per dismissal).
- Split wickets into a separate table rather than flattening onto
  fact_deliveries, because a single ball can produce two dismissals (e.g. a
  run out off a wide) and flat columns would either lose the second dismissal
  or break the one-row-per-ball grain.
- 0 parse failures, 0 unrecognised wicket kinds against the real data —
  the bowler-credit rule set (CLAUDE.md rule 3) is exhaustive for this window.
- Both CSVs are gitignored (data/processed/) — reproducible by re-running
  src/ingestion/parse_cricsheet.py against data/raw/.

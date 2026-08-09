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

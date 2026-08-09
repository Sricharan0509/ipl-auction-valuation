# CLAUDE.md

Project: **IPL Auction Market Efficiency Analysis** — a portfolio Data Analyst
project analysing Cricsheet ball-by-ball data against IPL auction prices.

Full spec: @docs/PROJECT_SPEC.md

Environment: **Windows + PowerShell**. VS Code. All commands must be PowerShell.

---

## Operating mode

The user runs everything themselves. You output; they execute.

- **Never write, create, or edit a file.** No file-writing or editing tools.
- **Never run anything.** No terminal execution, no git, no scripts.
- **Reading files in the repo is allowed and encouraged** — read existing code,
  data samples, and configs before answering. Read yes, write never.
- The user pastes back output and errors. React to what they actually paste.

---

## Tool selection — THE MOST IMPORTANT RULE

Match the tool to the job. Getting this wrong is the main failure mode.

| Task | Use |
|---|---|
| Create folders | PowerShell `mkdir` |
| Create/append short text files (< ~25 lines) | PowerShell here-string |
| Delete, move, rename, list files | PowerShell |
| venv, pip, git, environment | PowerShell |
| Inspect a file quickly | PowerShell `Get-Content` |
| **Parsing, transforming, analysing data** | **Python script** |

**Never write a Python script to create folders or files.** Never write a Python
script for anything the shell does natively. Python is for data work only.

If a task is filesystem or environment setup, the answer is a PowerShell command
block — not a `.py` file.

---

## Output formats

### PowerShell commands

```powershell
mkdir data\raw
mkdir data\external
```

Rules:
- One command per line. **No `&&`** — it fails in PowerShell 5.1. Use separate
  lines or `;`.
- Windows backslash paths.
- `mkdir` creates intermediate folders automatically.
- No `touch` — use `New-Item -ItemType File -Path name.txt`.

### Short text files — PowerShell here-string

```powershell
@'
venv/
__pycache__/
.env
data/raw/
'@ | Set-Content -Path .gitignore -Encoding utf8
```

The closing `'@` **must be at column 0** with no indentation, or PowerShell
errors. Mention this the first time you use one.

### Python scripts

State the path, then the complete file:

`src/ingestion/parse_cricsheet.py`
```python
[complete file]
```

Then one line: `Run: python src\ingestion\parse_cricsheet.py`

Rules:
- Complete files only — imports, config, error handling, `main()`. Never
  fragments, never `# TODO`, never "add this function to your existing file".
- Explanations go in docstrings and inline comments, at the point each decision
  is made. Not prose in chat instead of code.
- On any error, output the **full corrected file** again. Never a diff, never
  "change line 42".
- The user creates the file in VS Code and pastes the code in. Do not wrap long
  scripts in a here-string.

---

## Pace

Give the **entire milestone in one response** — every command and every script,
in execution order. Do not drip-feed across turns. Do not stop to ask if the
user is ready.

---

## Never

- Tell the user to write code themselves or attempt it first
- Quiz the user or set exercises as a precondition for help
- Withhold code to make a teaching point
- Add features beyond the scope below
- Open with theory paragraphs before the commands or code

---

## Scope: FINAL

**Out:** ML valuation models, regression, SHAP, clustering, LLM API calls, Monte
Carlo simulation, Power BI Copilot, live pipelines, cloud warehousing.

**In:** JSON→relational parsing, PostgreSQL star schema, phase-wise performance
metrics, value-per-crore analysis, franchise spend efficiency, Power BI dashboard
using native Q&A visual + Smart Narrative.

Analysis is **descriptive, not predictive**. Do not suggest expanding.

---

## Stack

Python 3.11+ · PostgreSQL 15+ · Power BI Desktop · Git · PowerShell
Packages: pandas, numpy, sqlalchemy, psycopg2-binary, python-dotenv, matplotlib,
seaborn, thefuzz, jupyter

All local, all free.

**PowerShell gotchas to flag when relevant:**
- venv activation is `.\venv\Scripts\Activate.ps1`
- If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

---

## Non-negotiable correctness rules

These silently corrupt every downstream number. Check them in any parsing or
metric code.

1. **Wides and no-balls are NOT balls faced** by the batter. Runs DO count
   against the bowler.
2. **Byes and legbyes ARE legal balls** (count as faced) but runs go to neither
   batter nor bowler.
3. **Bowler wicket credit:** bowled, caught, lbw, stumped, hit wicket, caught and
   bowled → credited. Run out, retired, obstructing the field → NOT credited.
4. **`extras` and `wickets` are optional keys** on a delivery. Always `.get()`.
5. **`wickets` is a list** — one delivery can dismiss two players. Iterate it.
6. **Super overs** appear as a 3rd+ innings. Exclude from player metrics.
7. **Retained players are NOT market prices** — negotiated, not bid. Exclude from
   any price-vs-performance comparison.
8. **Cricsheet numbers overs from 0.** Confirm before writing phase logic.

---

## Repo layout

```
data\raw\            Cricsheet JSONs (gitignored)
data\external\       auction_prices.csv, people.csv, name_overrides.csv
data\processed\      outputs for Power BI (gitignored)
src\ingestion\       explore_cricsheet_json.py, parse_cricsheet.py
src\transformation\  build_metrics.py
sql\schema\          DDL
sql\analysis\        analysis queries
dashboard\           ipl_auction.pbix
docs\                PROJECT_SPEC.md, data_notes.md, data_dictionary.md, methodology.md
```

Raw data is immutable. Everything in `processed\` must be reproducible by
re-running a script.

---

## After every milestone

Output in chat for the user to apply:

1. Updated status table + decisions log rows for `docs\PROJECT_SPEC.md`
2. Lines to append to `docs\methodology.md` — decisions made and why
3. A `git add` / `git commit` command with a descriptive message

# IPL Auction Market Efficiency Analysis — Project Spec

Referenced by `CLAUDE.md`. Behavioural rules live there; this file is the
analytical detail.

---

## 1. Business goal

IPL franchises spend crores at auction driven by reputation, recent highlights,
nationality, and bidding psychology rather than measured contribution.

**Central question:** Which players deliver on-field value relative to what
franchises paid, and are certain player types systematically overpaid?

**Framing:** In a hard salary-cap league, every crore overspent is a crore
unavailable for squad depth. Misvaluation is directly competitive.

**Deliverable:** an auction-preparation decision tool, not a stats dashboard.

**Primary persona:** Auction Strategy Lead building a target list. Every
dashboard element must serve someone preparing for an auction.

---

## 2. Business questions

Every visual and every analysis must map to one of these.

### Market behaviour
1. Which performance metrics correlate most with auction price?
2. Do Indian players command a premium over overseas players of equivalent output?
3. Do capped players command a premium over uncapped?
4. Does the market overweight the most recent season vs multi-season consistency?
5. Do batters get paid more than bowlers for equivalent impact?
6. Has price-per-unit-of-performance inflated across auction cycles?
7. Do mega auctions price differently from mini auctions?

### Player value
8. Which players delivered the highest value per crore?
9. Which delivered the lowest?
10. Do best/worst value buys cluster by role, nationality, or age?
11. Which franchises have the best and worst auction track record?
12. Does higher auction spend correlate with better league finish?
13. How much does availability (matches played) erode value per crore?

### Performance
14. How does output differ across powerplay / middle / death?
15. Which batters genuinely accelerate at the death vs only accumulate?
16. Which bowlers hold economy under pressure at the death?
17. How does performance vary by venue and opposition?
18. Which players are volatile vs consistent across innings?
19. Who is most effective in the powerplay specifically?
20. What is the league-average scoring pattern by over, and who beats it?

### Recommendation
21. Which five players should a franchise target next auction, and why?

---

## 3. Metric definitions

### Phases

| Phase     | Overs (1-indexed) | Overs (0-indexed) |
| --------- | ----------------- | ----------------- |
| Powerplay | 1–6               | 0–5               |
| Middle    | 7–15              | 6–14              |
| Death     | 16–20             | 15–19             |

Cricsheet numbers overs from 0 — confirm via the explorer script before writing
phase logic, then use the correct column.

### Batting

| Metric               | Formula                                              |
| -------------------- | ---------------------------------------------------- |
| Strike Rate          | (runs / balls faced) × 100                           |
| **True Strike Rate** | player SR − league avg SR *in same phase and season* |
| Boundary %           | (4s + 6s) / balls faced                              |
| Dot Ball %           | dots / balls faced                                   |
| Runs Above Expected  | actual runs − (balls faced × league phase run rate)  |
| Consistency          | std dev of per-innings True SR                       |

**True Strike Rate is the most important metric in the project.** Raw SR
unfairly rewards death specialists and punishes powerplay batters, making
cross-role comparison meaningless.

### Bowling

| Metric                    | Formula                                                     |
| ------------------------- | ----------------------------------------------------------- |
| Economy                   | runs conceded / overs bowled                                |
| **True Economy**          | league phase avg economy − player economy (positive = good) |
| Wickets per innings       | wickets credited / innings bowled                           |
| Dot Ball %                | dots / balls bowled                                         |
| Runs Saved Above Expected | (balls bowled × league phase run rate) − runs conceded      |

### Valuation

| Metric                | Definition                              |
| --------------------- | --------------------------------------- |
| Auction Price         | ₹ crore, actual paid                    |
| Normalised Price      | price as % of that season's total purse |
| Value per Crore       | total impact runs / price in crore      |
| Cost per Match Played | price / matches actually played         |

Normalised price is required for any cross-season comparison — purses inflate.

### Qualification thresholds

- Batters: minimum **150 balls faced** in the analysis window
- Bowlers: minimum **200 balls bowled** in the analysis window
- Below threshold: flag as `insufficient_sample`, do not silently drop

---

## 4. Data sources

### Cricsheet (free)
- cricsheet.org/downloads/ → Indian Premier League → JSON zip → `data/raw/`
- People register (player ID ↔ name) → `data/external/people.csv`
- Format spec: cricsheet.org/format/json/
- Structure: `meta` → `info` → `innings` → `overs` → `deliveries`
- **Analysis window: IPL 2021–2025.** Keep older files, filter at parse time.

### Auction prices (compiled manually)
`data/external/auction_prices.csv` with columns:
season, player_name, cricsheet_player_id, franchise, price_crore,
acquisition_type (auction/retained/RTM/replacement), capped_flag, nationality,
primary_role, age_at_auction

---

## 5. Known data traps

Beyond the correctness rules in CLAUDE.md:

| Trap                    | Handling                                                                                                                                                              |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Franchise renames       | Delhi Daredevils→Delhi Capitals, Kings XI Punjab→Punjab Kings, RCB Bangalore→Bengaluru, Pune Supergiant/Supergiants. Build `dim_team` mapping.                        |
| Venue name variants     | Same ground under multiple names. Build a venue mapping table.                                                                                                        |
| Season format           | May be "2020/21". Normalise to a single year.                                                                                                                         |
| Name reconciliation     | Cricsheet "V Kohli" vs auction "Virat Kohli". Use registry IDs first; `thefuzz` + `data/external/name_overrides.csv` for the rest. Keep overrides in version control. |
| Mid-season replacements | Distort per-season records. Flag them.                                                                                                                                |
| Small samples           | A bowler with 12 balls gives absurd economy. Hence thresholds.                                                                                                        |

---

## 6. Data model — star schema

**Facts**
- `fact_deliveries` — grain: one ball bowled
- `fact_player_season` — grain: player × season
- `fact_auction` — grain: player × auction event

**Dimensions**
- `dim_player`, `dim_match`, `dim_venue`, `dim_team`, `dim_season`

**Role-playing dimension:** `fact_deliveries` joins `dim_player` twice (batter
and bowler). In Power BI use an inactive relationship with `USERELATIONSHIP`, or
a duplicated dimension. Record the choice in the decisions log.

---

## 7. Milestones

| #   | Milestone                                       | Output                   | Est.  | Status |
| --- | ----------------------------------------------- | ------------------------ | ----- | ------ |
| 1   | Environment, repo scaffold, data download       | Working repo + raw JSONs | 0.5 d | Done   |
| 2   | JSON exploration + parser → `fact_deliveries`   | Delivery-level table     | 2 d   |        |
| 3   | PostgreSQL schema + load script                 | Queryable database       | 1 d   |        |
| 4   | Auction data + name reconciliation              | `fact_auction` joined    | 1 d   |        |
| 5   | Phase-wise metrics SQL → `fact_player_season`   | Metrics table            | 2 d   |        |
| 6   | EDA + insight write-up                          | Findings doc             | 1 d   |        |
| 7   | Power BI build + Q&A/Smart Narrative            | 3-page report            | 3 d   |        |
| 8   | Publish, README, resume bullets, interview prep | Public link + docs       | 1 d   |        |

---

## 8. Dashboard plan

**Page 1 — Executive Summary**
KPI cards (total auction spend, best value buy, worst value buy, spend-to-finish
correlation), spend vs performance scatter, Smart Narrative panel.

**Page 2 — Player Explorer**
Filterable profile: phase-wise batting and bowling, True SR and True Economy vs
league, value per crore, venue and matchup breakdown.

**Page 3 — Auction Board**
Ranked value-per-crore table, franchise spend efficiency, role and nationality
premium analysis, Q&A visual.

**Q&A visual note:** answer quality depends on clean table/column/measure names
plus synonyms defined in the Q&A setup pane. Budget time for this. Do not use
Copilot — it requires paid Fabric capacity.

---

## 9. Insight standard

Never describe a chart. Every insight answers:
1. What happened?
2. Why did it happen?
3. Why does it matter commercially?
4. What should the franchise do next?

Every insight ends with an actionable recommendation containing a number.

---

## 10. Decisions log

Update this after every milestone.

| Decision                        | Choice    | Reasoning                            |
| ------------------------------- | --------- | ------------------------------------ |
| Over indexing                   |           |                                      |
| Super over handling             |           |                                      |
| Season normalisation            |           |                                      |
| Wides/no-balls in balls faced   |           |                                      |
| Byes/legbyes attribution        |           |                                      |
| Bowler wicket credit            |           |                                      |
| Franchise rename consolidation  |           |                                      |
| Venue consolidation             |           |                                      |
| Role-playing dimension approach |           |                                      |
| Analysis window                 | 2021–2025 | Recent, comparable market conditions |
| Batting threshold               | 150 balls |                                      |
| Bowling threshold               | 200 balls |                                      |

---

## 11. Success criteria

- A stranger can clone the repo and reproduce every number
- Every metric defined in `data_dictionary.md`
- Every decision documented here with reasoning
- Dashboard publicly viewable via link
- Headline finding stateable in one sentence containing a number

---

## 12. End deliverables

1. Public GitHub repo, clean structure, recruiter-readable README
2. Published, publicly linkable Power BI report
3. `data_dictionary.md` and `methodology.md`
4. ATS-friendly title, 3–5 quantified resume bullets, business impact statement
5. 30–50 interview questions with answers covering SQL, data modelling, dashboard
   design, trade-offs, challenges faced, and future enhancements (including the
   v2 valuation model)

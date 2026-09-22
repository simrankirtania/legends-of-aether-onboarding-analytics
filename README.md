# Mobile Game Onboarding & Retention Optimization

**Product analytics case study using generated mobile-game telemetry to identify onboarding friction, analyze player retention, and recommend a testable product improvement.**

> **Note:** This project uses player telemetry generated for a fictional game (*Legends of Aether*), created for portfolio purposes. It does not use proprietary data from EA or any other company, and does not claim to represent any real game's internal metrics. The workflow, schema, and analysis approach are built to generalize to any live-service mobile game.

---

## Business Problem

Free-to-play mobile games lose the majority of their economic value in the first week after install. A player who never gets through onboarding never reaches the game's core loop — and is gone before the studio has a real chance to earn their engagement. This project walks through a Product Manager's investigation into that problem: where new players in *Legends of Aether* drop off, which early behaviors predict who comes back, which player segments are most at risk, and what the Product team should build and test next.

## Key Questions

1. Where do new players drop off?
2. Which onboarding behaviors are associated with retention?
3. Which player segments are most at risk?
4. What product problem could explain the behavior?
5. What should the PM team test to improve retention?

## Tech Stack

- **SQLite** — player, event, and session storage; funnel/retention SQL
- **Python (pandas, NumPy)** — data generation, segmentation, correlation analysis
- **HTML/CSS/Plotly.js** — the final interactive report

## Project Structure

```
mobile-game-onboarding-analytics/
├── data/                          players.csv, player_events.csv, sessions.csv
├── database/
│   └── game_analytics.sqlite      the SQLite database (3 tables, indexed)
├── sql/
│   └── queries.sql                documented funnel/retention SQL
├── src/
│   ├── generate_data.py           generates 50,000 players + behavioral telemetry
│   ├── analyze.py                 SQL + pandas analysis → output/dashboard_data.json
│   └── dashboard_template.html    HTML/CSS/JS report shell (data-driven, reusable)
├── output/
│   ├── dashboard_data.json        all computed analysis results
│   └── player_analytics_report.html   the final interactive report
├── PROJECT_SUMMARY.md             2-page summary of the project and its workflow
├── README.md
└── requirements.txt
```

To reproduce: `python3 src/generate_data.py` (builds the database) → `python3 src/analyze.py` (writes `output/dashboard_data.json`) → inject that JSON into `src/dashboard_template.html` in place of `__DASHBOARD_DATA__` to regenerate `output/player_analytics_report.html`.

## Data Model

**`players`** — `player_id, install_date, country, device_type, acquisition_channel, age_group`
**`player_events`** — `event_id, player_id, event_timestamp, event_date, event_name, level, session_id, event_value` (18 event types: install → tutorial steps → first battle → rewards/upgrades → daily missions → shop/purchase → social/live events)
**`sessions`** — `session_id, player_id, session_start, session_end, session_duration, sessions_number`

Dataset scale: **50,000 players · 663,019 events · 116,854 sessions**, generated with behavioral relationships baked in (players who complete onboarding milestones and return sooner have systematically higher engagement and retention, with realistic noise — not a deterministic rule) so the analysis surfaces genuine, investigable patterns rather than a trivially obvious signal.

## KPI Dictionary

| Category | KPI | Definition |
|---|---|---|
| Acquisition | New Players | Unique players who installed |
| Onboarding | Tutorial Completion Rate | Tutorial completers ÷ tutorial starters |
| First Value | First Battle Completion Rate | Players completing first battle ÷ players reaching first battle |
| Retention | D1 Retention | Players active on install date + 1 day ÷ all players |
| Retention | D7 Retention | Players active on install date + 7 days ÷ players with ≥7 days of history |
| Engagement | Avg. Sessions per Player | Total sessions ÷ unique players |
| Progression | Level 3 Reach Rate | Players reaching level 3 ÷ new players |
| Churn | Early Churn (portfolio definition) | Installs with no meaningful gameplay activity after Day 1 — a simplified definition for this project, not an industry standard |

## Key Findings

1. **Reaching the first battle predicts retention more strongly than finishing the tutorial.** Players who complete their first battle show a **37.5-point** gap in D7 retention vs. those who don't (61.7% vs. 24.2%) — a larger gap than tutorial completion alone (52.2% vs. 22.6%, a 29.6-point gap).
2. **The steepest single funnel drop is inside the tutorial itself**: only 34.1% of players who start the tutorial finish it (45,086 → 15,374 players).
3. **Sustained early engagement, not any one milestone, is the strongest overall correlate of D7 retention** — active days in the first two weeks (r = 0.60) and session count (r = 0.57) outrank any single onboarding event.
4. Segment comparison shows the "Highly Engaged" cohort (tutorial + first battle complete, 3+ sessions — 13% of players) reaches 81% D7 retention, while "Casual" players (1–2 sessions — 60% of players) reach just 11%.

*(All figures are computed live from the dataset in `output/dashboard_data.json` — see the report for the full, current numbers.)*

## Product Opportunity

The largest onboarding risk sits between tutorial completion and first meaningful gameplay, not in the tutorial's mechanics alone. Players who reach their first successful battle retain far better than those who merely finish a scripted tutorial — suggesting the tutorial itself may be necessary but not sufficient, and that **time-to-first-win** is the more important lever.

## Recommendation: Accelerate the First Gameplay Moment

Shorten the path from install to a player's first real win:

**Current:** Install → long multi-step tutorial → character setup → first battle → reward
**Proposed:** Install → short interactive tutorial → immediate first battle → reward → progression preview

This is proposed as a **hypothesis to test**, not a guaranteed fix.

## Proposed A/B Test

| | |
|---|---|
| Hypothesis | Reducing onboarding friction and moving the first meaningful gameplay interaction earlier will increase D7 retention |
| Audience | New players |
| Control | Existing onboarding |
| Variant | Simplified onboarding, earlier first battle, immediate reward |
| Primary KPI | D7 retention |
| Secondary KPIs | D1 retention, tutorial completion rate, first-battle completion rate, average sessions per player, Level 3 reach rate |
| Guardrails | Tutorial abandonment, session crash rate, negative feedback, notification opt-out rate |
| Test duration | 7–14 days |
| Decision rule | Ship only if the variant beats control on the primary KPI with statistical *and* practical significance, with no guardrail regression |

No experiment has actually been run — this is a proposed design, not a claimed result.

## Reusing This Project for Another Game or Company

Everything here is deliberately generic:

- The **schema** (players / events / sessions) matches how nearly every mobile game or app logs telemetry — swap in real event names and it drops in unchanged.
- The **SQL and pandas logic** in `analyze.py` reference event names and column names as constants at the top of relevant sections, so retargeting to a different game's event taxonomy is a find-and-replace exercise, not a rewrite.
- The **HTML report is entirely data-driven** — it reads `output/dashboard_data.json` and renders every number, chart, and segment card from it. Point it at a different `dashboard_data.json` (from a different game, or a different time period of the same game) and the report updates automatically, with no HTML edits required.
- The **funnel → retention → segmentation → correlation → recommendation → experiment** workflow is the standard shape of a growth/onboarding analysis at any live-service company (mobile games, subscription apps, SaaS trials) — only the event names change.

## What This Project Deliberately Avoids

- No generic BI-style dashboard — built for a Product Management audience, not a BI Analyst one
- No machine learning for its own sake — correlation and cohort comparison are more interpretable and more appropriate here than a black-box model
- No claims about real EA or industry data — everything is fictional and clearly labeled as such
- No causal claims — correlations are reported as correlations, with the A/B test proposed as the way to establish causation

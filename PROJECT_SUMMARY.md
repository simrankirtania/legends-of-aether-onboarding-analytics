# Project Summary: Mobile Game Onboarding & Retention Optimization

## What this project does

This project walks through the work of a Product Manager partnering with an analytics team at a mobile game studio. Starting from raw player telemetry, it answers a single business question — *where are new players dropping out during onboarding, and what should the product team do about it* — and carries that answer all the way through to a specific, testable recommendation.

It is built around a fictional free-to-play mobile RPG, **Legends of Aether**, with a generated population of 50,000 players, 663,000+ behavioral events, and 117,000+ play sessions. The behavior in the dataset is not random: players who complete onboarding milestones and stay engaged early are systematically more likely to return, with enough noise layered in that the patterns have to be *found*, not assumed. That is what makes the analysis feel like a genuine investigation rather than a demonstration of a foregone conclusion.

The deliverable is a single interactive HTML report — styled like a game studio's own product dashboard rather than a generic BI tool — that walks a reader from the raw funnel, through retention and segmentation analysis, to a concrete product recommendation and a proposed A/B test to validate it.

## The workflow

The project follows the same five-stage arc a Product team would use to turn data into a decision:

**1. Generate realistic telemetry.**
A Python script (`generate_data.py`) builds three tables that mirror how virtually any mobile game logs data — a `players` table (install date, country, device, acquisition channel, age group), a `player_events` table (18 event types spanning install, tutorial, first battle, rewards, progression, daily missions, monetization, and social/live features), and a `sessions` table. Each player is assigned a hidden "quality" score influenced by acquisition channel, device, and age group, which probabilistically drives their entire journey — tutorial completion, first-battle success, session frequency, and Day-1/Day-7 return. This produces a dataset where onboarding behavior and retention are genuinely correlated, the way they would be in a real game, without hand-scripting the answer.

**2. Analyze with SQL.**
The data is loaded into a SQLite database with three indexed tables. A documented set of SQL queries (`sql/queries.sql`) answers the foundational questions: total players, tutorial and first-battle completion rates, sessions and active days per player, and D1/D7 retention — including retention broken out by whether a player completed the tutorial. These queries are the same shape an analyst would hand a PM in any onboarding review, and they run directly against the `.sqlite` file with no dependency on the rest of the project.

**3. Go deeper with Python.**
A second script (`analyze.py`) builds a player-level feature table in pandas — joining onboarding flags, session aggregates, progression, and monetization — and layers on the analysis SQL alone can't easily express: five overlapping player segments (Highly Engaged, Early Drop-Off, Gameplay Drop-Off, Casual, Returning), a progression drop-off curve across character levels, and a correlation analysis that ranks ten early behaviors — from tutorial completion to active days to session count — by how strongly each one tracks with Day-7 retention. Every number in the final report, from the executive-summary KPIs down to each segment card, is computed here and written to a single JSON file.

**4. Turn the numbers into a product story.**
The analysis surfaces a specific, non-obvious insight: completing the tutorial matters, but completing a player's *first battle* matters more. Players who finish their first battle return at a 37.5-percentage-point higher Day-7 rate than those who don't — a larger gap than tutorial completion alone produces. Combined with the funnel data (only about a third of players who start the tutorial finish it), the project builds a specific product hypothesis: the tutorial isn't just too long, it's too disconnected from the moment that actually earns a player's return — their first real win.

**5. Propose (not fabricate) an experiment.**
Rather than claiming the fix works, the project proposes a concrete A/B test: shorten the tutorial, move the first battle earlier, and deliver the reward immediately after — with D7 retention as the primary KPI, D1 retention and completion rates as secondary KPIs, and abandonment/crash/feedback metrics as guardrails. The report is explicit throughout that these are correlations and a proposed test, not proof of causation or a claimed result — a distinction that matters both scientifically and professionally.

## How this can help a company in this industry

The core value of this project isn't the specific numbers about a fictional game — it's the **reusable analytical pipeline** behind them, which generalizes to any company that ships a product with an onboarding funnel and wants players, users, or customers to come back:

- **Mobile and PC game studios** can point the same schema and SQL at their real event logs to run this exact funnel → retention → segmentation → recommendation workflow on live data, with no restructuring — only the event names change.
- **Any subscription or freemium app** (fitness, productivity, fintech, EdTech) faces the identical shape of problem: users install, some fraction complete onboarding, and only a subset return a week later. The same D1/D7 retention logic, segment definitions, and correlation approach apply directly.
- **Growth and marketing teams** get a ready template for evaluating acquisition channel quality (the dataset already breaks retention out by channel and device), which is often the first question leadership asks when retention looks weak.
- **The report itself is a reusable artifact, not a one-off document.** Because it renders entirely from a JSON data file rather than hardcoded numbers, a team can regenerate it for a new cohort, a new game, or a re-run after shipping the recommended change — without touching the HTML.

Most importantly, the project models a habit of mind that's valuable in any data-driven product organization: resisting the pull to report a metric ("D7 retention is 24%") and instead building toward a decision ("players who reach their first win retain dramatically better than those who don't — here's what we should test to see if we can get more of them there faster"). That distinction, between analysis and product judgment, is the actual skill a Growth or Player Marketing PM role is hiring for.

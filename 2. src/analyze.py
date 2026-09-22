"""
Legends of Aether — Onboarding & Retention Analysis
======================================================
Reads database/game_analytics.sqlite, runs the SQL analysis (see sql/queries.sql),
builds player-level behavioral features in pandas, and writes a single JSON
payload (output/dashboard_data.json) that the HTML report renders.

Sections (mirrors the brief):
  02 Data loading            06 SQL analysis           10 Behavioral analysis
  03 Data quality checks     07 Player funnel          11 Key findings
  04 SQLite connection       08 Retention analysis      12 Product opportunities
  05 Cohort/day-7 window     09 Player segmentation     13 A/B test proposal
"""

import json
import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "/home/claude/project/database/game_analytics.sqlite"
OUT_JSON = "/home/claude/project/output/dashboard_data.json"
TODAY = pd.Timestamp("2026-09-22")

# ---------------------------------------------------------------------------
# 02-04. Load data / connect to SQLite
# ---------------------------------------------------------------------------
conn = sqlite3.connect(DB_PATH)
players = pd.read_sql("SELECT * FROM players", conn, parse_dates=["install_date"])
events = pd.read_sql("SELECT * FROM player_events", conn, parse_dates=["event_date"])
sessions = pd.read_sql("SELECT * FROM sessions", conn, parse_dates=["session_start", "session_end"])
conn.close()

# ---------------------------------------------------------------------------
# 03. Data quality checks
# ---------------------------------------------------------------------------
dq = {
    "players_rows": int(len(players)),
    "events_rows": int(len(events)),
    "sessions_rows": int(len(sessions)),
    "duplicate_player_ids": int(players.player_id.duplicated().sum()),
    "null_install_dates": int(players.install_date.isna().sum()),
    "orphan_events": int(events[~events.player_id.isin(players.player_id)].shape[0]),
    "orphan_sessions": int(sessions[~sessions.player_id.isin(players.player_id)].shape[0]),
}

# ---------------------------------------------------------------------------
# 06-07. SQL-equivalent funnel (run natively here for reuse in pandas)
# ---------------------------------------------------------------------------
funnel_steps = [
    ("Installs", "app_install"),
    ("Tutorial Started", "tutorial_start"),
    ("Tutorial Completed", "tutorial_complete"),
    ("First Battle", "first_battle"),
    ("First Battle Completed", "battle_complete"),
    ("Reward Claimed", "reward_claimed"),
]
funnel = []
for label, ev in funnel_steps:
    n = events.loc[events.event_name == ev, "player_id"].nunique()
    funnel.append({"stage": label, "players": int(n)})

level_events = events[events.event_name == "level_up"].copy()
level3plus = level_events[level_events.level.fillna(0) >= 3].player_id.nunique()
funnel.append({"stage": "Level 3 Reach", "players": int(level3plus)})

# ---------------------------------------------------------------------------
# Player-level behavioral feature table
# ---------------------------------------------------------------------------
def has_event(name):
    return set(events.loc[events.event_name == name, "player_id"])

flags = pd.DataFrame({"player_id": players.player_id})
event_flags = ["tutorial_start", "tutorial_complete", "first_battle", "battle_complete",
               "reward_claimed", "character_upgrade", "daily_mission_start",
               "daily_mission_complete", "shop_visit", "purchase",
               "social_feature_used", "event_joined"]
for ev in event_flags:
    s = has_event(ev)
    flags[ev] = flags.player_id.isin(s)

max_level = level_events.groupby("player_id")["level"].max().rename("max_level")
flags = flags.merge(max_level, on="player_id", how="left")
flags["max_level"] = flags["max_level"].fillna(1).astype(int)

sess_agg = sessions.groupby("player_id").agg(
    num_sessions=("session_id", "count"),
    avg_session_minutes=("session_duration", "mean"),
).reset_index()
sess_agg["active_days"] = sessions.assign(d=sessions.session_start.dt.date).groupby("player_id").d.nunique().values

df = players.merge(flags, on="player_id", how="left").merge(sess_agg, on="player_id", how="left")
df["num_sessions"] = df["num_sessions"].fillna(0).astype(int)
df["avg_session_minutes"] = df["avg_session_minutes"].fillna(0).round(2)
df["active_days"] = df["active_days"].fillna(0).astype(int)

purchase_val = events.loc[events.event_name == "purchase"].groupby("player_id").event_value.sum().rename("revenue")
df = df.merge(purchase_val, on="player_id", how="left")
df["revenue"] = df["revenue"].fillna(0.0)

# D1 / D7 retention flags derived from session activity vs. install_date
sess_dates = sessions.assign(day_offset=(sessions.session_start.dt.normalize()
                                          - sessions.merge(players[["player_id", "install_date"]],
                                                            on="player_id")["install_date"].dt.normalize()).dt.days)
d1_players = set(sess_dates.loc[sess_dates.day_offset == 1, "player_id"])
d7_players = set(sess_dates.loc[sess_dates.day_offset == 7, "player_id"])
df["d1_return"] = df.player_id.isin(d1_players)
df["days_since_install"] = (TODAY - df.install_date).dt.days
df["d7_eligible"] = df["days_since_install"] >= 7
df["d7_return"] = df.player_id.isin(d7_players) & df["d7_eligible"]

# ---------------------------------------------------------------------------
# 08. Retention analysis
# ---------------------------------------------------------------------------
d7_pool = df[df.d7_eligible]
retention_overall = {
    "d1_retention_pct": round(100 * df.d1_return.mean(), 2),
    "d7_retention_pct": round(100 * d7_pool.d7_return.mean(), 2),
    "d7_eligible_players": int(len(d7_pool)),
}

def retention_by(col, labels=None):
    g = d7_pool.groupby(col)
    out = []
    for key, sub in g:
        label = labels.get(key, str(key)) if labels else str(key)
        out.append({
            "cohort": label,
            "players": int(len(sub)),
            "d1_retention_pct": round(100 * sub.d1_return.mean(), 2),
            "d7_retention_pct": round(100 * sub.d7_return.mean(), 2),
        })
    return out

retention_by_tutorial = retention_by("tutorial_complete", {True: "Tutorial Completed", False: "Tutorial Not Completed"})
retention_by_battle = retention_by("battle_complete", {True: "First Battle Completed", False: "First Battle Not Completed"})
retention_by_channel = retention_by("acquisition_channel")
retention_by_device = retention_by("device_type")

# ---------------------------------------------------------------------------
# 09-10. Player segmentation (overlapping cohorts, per the brief) + behavior
# ---------------------------------------------------------------------------
seg_defs = {
    "Highly Engaged": (df.num_sessions >= 3) & df.tutorial_complete & df.battle_complete,
    "Early Drop-Off": df.tutorial_start & ~df.tutorial_complete,
    "Gameplay Drop-Off": df.tutorial_complete & ~df.battle_complete,
    "Casual (1-2 sessions)": df.num_sessions.between(1, 2),
    "Returning (D1 & D7)": df.d1_return & df.d7_return,
}
segments = []
for name, mask in seg_defs.items():
    sub = df[mask]
    sub7 = sub[sub.d7_eligible]
    segments.append({
        "segment": name,
        "players": int(len(sub)),
        "share_pct": round(100 * len(sub) / len(df), 2),
        "d1_retention_pct": round(100 * sub.d1_return.mean(), 2) if len(sub) else 0,
        "d7_retention_pct": round(100 * sub7.d7_return.mean(), 2) if len(sub7) else 0,
        "avg_session_minutes": round(sub.avg_session_minutes.mean(), 2) if len(sub) else 0,
        "avg_max_level": round(sub.max_level.mean(), 2) if len(sub) else 0,
        "social_use_pct": round(100 * sub.social_feature_used.mean(), 2) if len(sub) else 0,
    })

# Progression drop-off (levels 1-8)
progression = []
for lvl in range(1, 9):
    n = int((df.max_level >= lvl).sum())
    progression.append({"level": lvl, "players": n})

# Behavioral correlation with D7 retention (point-biserial / Pearson on 0-1 & counts)
corr_features = {
    "Tutorial Completed": "tutorial_complete",
    "First Battle Completed": "battle_complete",
    "Reward Claimed": "reward_claimed",
    "Character Upgrade": "character_upgrade",
    "Daily Mission Completed": "daily_mission_complete",
    "Social Feature Used": "social_feature_used",
    "Sessions (count)": "num_sessions",
    "Active Days": "active_days",
    "Max Level Reached": "max_level",
    "Avg Session Minutes": "avg_session_minutes",
}
correlations = []
for label, col in corr_features.items():
    x = d7_pool[col].astype(float)
    y = d7_pool["d7_return"].astype(float)
    if x.std() > 0:
        r = float(np.corrcoef(x, y)[0, 1])
    else:
        r = 0.0
    correlations.append({"feature": label, "correlation_with_d7": round(r, 3)})
correlations.sort(key=lambda r: -abs(r["correlation_with_d7"]))

# Sessions-per-player distribution (histogram buckets)
bins = [0, 1, 2, 3, 5, 8, 13, 1000]
bin_labels = ["1", "2", "3", "4-5", "6-8", "9-13", "14+"]
sess_hist = pd.cut(df.num_sessions.clip(lower=1), bins=bins, labels=bin_labels, right=True)
sess_dist = sess_hist.value_counts().reindex(bin_labels).fillna(0).astype(int)
sessions_distribution = [{"bucket": b, "players": int(sess_dist[b])} for b in bin_labels]

# Activity by day-since-install (day 0-14)
active_by_day = []
for day in range(0, 15):
    day_ts = sess_dates[sess_dates.day_offset == day]
    active_by_day.append({"day": day, "active_players": int(day_ts.player_id.nunique())})

# Country / channel acquisition mix
channel_mix = players.acquisition_channel.value_counts().reset_index()
channel_mix.columns = ["channel", "players"]
country_mix = players.country.value_counts().reset_index()
country_mix.columns = ["country", "players"]

# Monetization snapshot
monetization = {
    "payers": int((df.revenue > 0).sum()),
    "payer_rate_pct": round(100 * (df.revenue > 0).mean(), 3),
    "total_revenue": round(float(df.revenue.sum()), 2),
    "arppu": round(float(df.loc[df.revenue > 0, "revenue"].mean()), 2) if (df.revenue > 0).any() else 0,
}

# ---------------------------------------------------------------------------
# KPI dictionary summary (headline numbers for the executive summary bar)
# ---------------------------------------------------------------------------
kpis = {
    "total_players": int(len(df)),
    "tutorial_completion_rate_pct": round(100 * funnel[2]["players"] / funnel[1]["players"], 2),
    "battle_completion_rate_pct": round(100 * funnel[4]["players"] / funnel[3]["players"], 2),
    "d1_retention_pct": retention_overall["d1_retention_pct"],
    "d7_retention_pct": retention_overall["d7_retention_pct"],
    "avg_sessions_per_player": round(df.num_sessions.mean(), 2),
}

# ---------------------------------------------------------------------------
# 11. Key findings (data-driven, computed from the numbers above)
# ---------------------------------------------------------------------------
tut_gap = retention_by_tutorial[0]["d7_retention_pct"] - retention_by_tutorial[1]["d7_retention_pct"] \
    if retention_by_tutorial[0]["cohort"] == "Tutorial Completed" else \
    retention_by_tutorial[1]["d7_retention_pct"] - retention_by_tutorial[0]["d7_retention_pct"]
battle_gap = next(r for r in retention_by_battle if r["cohort"] == "First Battle Completed")["d7_retention_pct"] - \
             next(r for r in retention_by_battle if r["cohort"] == "First Battle Not Completed")["d7_retention_pct"]

biggest_drop = None
prev = None
for stage in funnel:
    if prev:
        drop = prev["players"] - stage["players"]
        drop_pct = round(100 * drop / prev["players"], 1)
        if biggest_drop is None or drop_pct > biggest_drop["drop_pct"]:
            biggest_drop = {"from": prev["stage"], "to": stage["stage"], "drop_pct": drop_pct}
    prev = stage

key_findings = {
    "biggest_funnel_drop": biggest_drop,
    "tutorial_retention_gap_pts": round(tut_gap, 1),
    "battle_retention_gap_pts": round(battle_gap, 1),
    "top_correlate_with_d7": correlations[0],
}

# ---------------------------------------------------------------------------
# Assemble output payload
# ---------------------------------------------------------------------------
payload = {
    "generated_at": str(TODAY.date()),
    "data_quality": dq,
    "kpis": kpis,
    "funnel": funnel,
    "retention_overall": retention_overall,
    "retention_by_tutorial": retention_by_tutorial,
    "retention_by_battle": retention_by_battle,
    "retention_by_channel": retention_by_channel,
    "retention_by_device": retention_by_device,
    "segments": segments,
    "progression": progression,
    "correlations": correlations,
    "sessions_distribution": sessions_distribution,
    "active_by_day": active_by_day,
    "channel_mix": channel_mix.to_dict("records"),
    "country_mix": country_mix.to_dict("records"),
    "monetization": monetization,
    "key_findings": key_findings,
}

with open(OUT_JSON, "w") as f:
    json.dump(payload, f, indent=2, default=str)

print("Analysis complete.")
print(json.dumps(kpis, indent=2))
print(json.dumps(key_findings, indent=2))
print(f"\nWrote {OUT_JSON}")

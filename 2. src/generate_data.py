"""
Legends of Aether - Player Telemetry Generator
==========================================================
Generates a portfolio-scale (fictional) mobile game dataset with realistic
behavioral relationships between onboarding, engagement and retention, and
loads it into a SQLite database (database/game_analytics.sqlite).

Note: This is fictional data generated for portfolio purposes. It does not use
proprietary data from any company and does not claim to represent any real
game's internal metrics.
"""

import csv
import random
import sqlite3
import uuid
from datetime import datetime, timedelta

import numpy as np

random.seed(42)
np.random.seed(42)

N_PLAYERS = 50000
INSTALL_START = datetime(2026, 6, 1)
INSTALL_END = datetime(2026, 8, 20)      # leaves >30 days of runway to "today" (treated as 2026-09-22)
TODAY = datetime(2026, 9, 22)

OUT_DIR = "/home/claude/project/data"
DB_PATH = "/home/claude/project/database/game_analytics.sqlite"

# ---------------------------------------------------------------------------
# Reference distributions
# ---------------------------------------------------------------------------
COUNTRIES = ["India", "USA", "UK", "Brazil", "Germany", "Canada",
             "Australia", "Philippines", "Indonesia", "Mexico"]
COUNTRY_W = [0.22, 0.16, 0.08, 0.10, 0.06, 0.05, 0.05, 0.09, 0.10, 0.09]

DEVICES = ["Android", "iOS"]
DEVICE_W = [0.66, 0.34]

CHANNELS = ["Organic", "Paid Social", "Search", "Influencer", "Cross-Promo"]
CHANNEL_W = [0.32, 0.28, 0.16, 0.12, 0.12]
# quality bonus per channel (organic/influencer users tend to be higher-intent)
CHANNEL_BONUS = {"Organic": 0.10, "Paid Social": -0.10, "Search": 0.02,
                  "Influencer": 0.08, "Cross-Promo": -0.03}

AGE_GROUPS = ["13-17", "18-24", "25-34", "35-44", "45+"]
AGE_W = [0.10, 0.32, 0.30, 0.18, 0.10]
AGE_BONUS = {"13-17": -0.03, "18-24": 0.05, "25-34": 0.06, "35-44": 0.0, "45+": -0.05}

DEVICE_BONUS = {"iOS": 0.05, "Android": 0.0}


def clip01(x):
    return float(np.clip(x, 0.02, 0.98))


def gen_players(n):
    install_offsets = np.random.randint(0, (INSTALL_END - INSTALL_START).days + 1, size=n)
    countries = np.random.choice(COUNTRIES, size=n, p=COUNTRY_W)
    devices = np.random.choice(DEVICES, size=n, p=DEVICE_W)
    channels = np.random.choice(CHANNELS, size=n, p=CHANNEL_W)
    ages = np.random.choice(AGE_GROUPS, size=n, p=AGE_W)

    players = []
    quality = np.zeros(n)
    for i in range(n):
        base = np.random.normal(0.5, 0.16)
        q = base + CHANNEL_BONUS[channels[i]] + AGE_BONUS[ages[i]] + DEVICE_BONUS[devices[i]]
        quality[i] = clip01(q)
        install_date = INSTALL_START + timedelta(days=int(install_offsets[i]))
        players.append({
            "player_id": f"P{i+1:06d}",
            "install_date": install_date.strftime("%Y-%m-%d"),
            "country": countries[i],
            "device_type": devices[i],
            "acquisition_channel": channels[i],
            "age_group": ages[i],
        })
    return players, quality, install_offsets


def bern(p):
    return random.random() < p


def gen_events_and_sessions(players, quality, install_offsets):
    events = []
    sessions = []
    event_id = 0
    session_id_ctr = 0

    for idx, p in enumerate(players):
        q = quality[idx]
        pid = p["player_id"]
        install_dt = datetime.strptime(p["install_date"], "%Y-%m-%d")
        days_since_install = (TODAY - install_dt).days

        def add_event(name, ts, level=None, session_id=None, value=None):
            nonlocal event_id
            event_id += 1
            events.append({
                "event_id": event_id,
                "player_id": pid,
                "event_timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "event_date": ts.strftime("%Y-%m-%d"),
                "event_name": name,
                "level": level if level is not None else "",
                "session_id": session_id if session_id is not None else "",
                "event_value": value if value is not None else "",
            })

        def new_session(day_offset, seq_no, minutes):
            nonlocal session_id_ctr
            session_id_ctr += 1
            sid = f"S{session_id_ctr:07d}"
            start = install_dt + timedelta(days=day_offset,
                                            hours=random.uniform(7, 22),
                                            minutes=random.uniform(0, 59))
            end = start + timedelta(minutes=minutes)
            sessions.append({
                "session_id": sid,
                "player_id": pid,
                "session_start": start.strftime("%Y-%m-%d %H:%M:%S"),
                "session_end": end.strftime("%Y-%m-%d %H:%M:%S"),
                "session_duration": round(minutes, 2),
                "sessions_number": seq_no,
            })
            return sid, start, end

        # ---- Day 0: install + onboarding funnel -------------------------
        seq = 1
        dur0 = max(1.0, np.random.normal(6 + 10 * q, 4))
        sid0, s0_start, s0_end = new_session(0, seq, dur0)
        t = s0_start
        add_event("app_install", t, session_id=sid0)
        add_event("session_start", t, session_id=sid0)

        tutorial_complete = False
        first_battle_complete = False
        reward_claimed = False

        if bern(0.90):
            t += timedelta(minutes=0.5)
            add_event("tutorial_start", t, session_id=sid0)
            if bern(0.95):
                t += timedelta(minutes=1)
                add_event("tutorial_step_1", t, session_id=sid0)
                if bern(0.55 + 0.35 * q):
                    t += timedelta(minutes=1.5)
                    add_event("tutorial_step_2", t, session_id=sid0)
                    if bern(0.45 + 0.45 * q):
                        t += timedelta(minutes=1.5)
                        add_event("tutorial_step_3", t, session_id=sid0)
                        if bern(0.35 + 0.55 * q):
                            t += timedelta(minutes=1)
                            add_event("tutorial_complete", t, session_id=sid0)
                            tutorial_complete = True

        if tutorial_complete and bern(0.85 + 0.10 * q):
            t += timedelta(minutes=1)
            add_event("first_battle", t, level=1, session_id=sid0)
            if bern(0.40 + 0.50 * q):
                t += timedelta(minutes=3)
                add_event("battle_complete", t, level=1, session_id=sid0)
                first_battle_complete = True
                if bern(0.90):
                    t += timedelta(minutes=0.5)
                    add_event("reward_claimed", t, level=1, session_id=sid0)
                    reward_claimed = True
                    if bern(0.45 + 0.35 * q):
                        t += timedelta(minutes=1)
                        add_event("character_upgrade", t, session_id=sid0)
                        t += timedelta(minutes=0.5)
                        add_event("level_up", t, level=2, session_id=sid0)

        add_event("session_end", s0_end, session_id=sid0)

        # ---- Retention: D1 / D7 -------------------------------------
        d1_prob = clip01(0.15 + 0.45 * q + 0.12 * tutorial_complete + 0.15 * first_battle_complete)
        d1_return = days_since_install >= 1 and bern(d1_prob)

        d7_prob = clip01(0.03 + 0.30 * q + 0.10 * tutorial_complete + 0.22 * first_battle_complete
                          + 0.10 * d1_return)
        d7_return = days_since_install >= 7 and bern(d7_prob)

        # ---- Subsequent days: activity, progression, engagement -----
        max_level = 2 if not first_battle_complete else int(np.random.poisson(2 + 6 * q)) + 2
        current_level = 2 if first_battle_complete else 1
        active_days = {0}
        if d1_return:
            active_days.add(1)

        # decaying daily activity probability out to day 21 (or install age, whichever smaller)
        horizon = min(10, days_since_install)
        decay_prob = clip01(0.03 + 0.15 * q)
        for day in range(2, horizon + 1):
            if day == 7:
                if d7_return:
                    active_days.add(day)
                continue
            p_active = decay_prob * (0.85 ** day)
            if bern(p_active):
                active_days.add(day)

        for day in sorted(active_days):
            if day == 0:
                continue
            seq += 1
            n_sess_today = 1 if bern(0.85) else 2
            for _ in range(n_sess_today):
                dur = max(1.0, np.random.normal(5 + 12 * q, 5))
                sid, s_start, s_end = new_session(day, seq, dur)
                t = s_start
                add_event("session_start", t, session_id=sid)

                if current_level < max_level and bern(0.5 + 0.3 * q):
                    current_level += 1
                    t += timedelta(minutes=1)
                    add_event("level_up", t, level=current_level, session_id=sid)

                if bern(0.55 + 0.25 * q):
                    t += timedelta(minutes=1)
                    add_event("daily_mission_start", t, session_id=sid)
                    if bern(0.5 + 0.4 * q):
                        t += timedelta(minutes=2)
                        add_event("daily_mission_complete", t, session_id=sid)

                if bern(0.20 + 0.30 * q):
                    t += timedelta(minutes=0.5)
                    add_event("shop_visit", t, session_id=sid)
                    if bern(0.05 + 0.20 * q):
                        t += timedelta(minutes=0.5)
                        value = round(random.choice([0.99, 1.99, 4.99, 9.99, 19.99, 49.99]), 2)
                        add_event("purchase", t, session_id=sid, value=value)

                if bern(0.10 + 0.30 * q):
                    t += timedelta(minutes=0.5)
                    add_event("social_feature_used", t, session_id=sid)

                if bern(0.05 + 0.20 * q):
                    t += timedelta(minutes=0.5)
                    add_event("event_joined", t, session_id=sid)

                add_event("session_end", s_end, session_id=sid)
                seq += 0  # seq already incremented per session below

        p["tutorial_complete"] = tutorial_complete
        p["first_battle_complete"] = first_battle_complete
        p["d1_return"] = d1_return
        p["d7_return"] = d7_return
        p["max_level"] = current_level

    return events, sessions


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_sqlite(players, events, sessions):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS player_events;
        DROP TABLE IF EXISTS sessions;

        CREATE TABLE players (
            player_id TEXT PRIMARY KEY,
            install_date TEXT,
            country TEXT,
            device_type TEXT,
            acquisition_channel TEXT,
            age_group TEXT
        );

        CREATE TABLE player_events (
            event_id INTEGER PRIMARY KEY,
            player_id TEXT,
            event_timestamp TEXT,
            event_date TEXT,
            event_name TEXT,
            level INTEGER,
            session_id TEXT,
            event_value REAL
        );

        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            player_id TEXT,
            session_start TEXT,
            session_end TEXT,
            session_duration REAL,
            sessions_number INTEGER
        );
    """)

    cur.executemany(
        "INSERT INTO players VALUES (:player_id, :install_date, :country, :device_type, "
        ":acquisition_channel, :age_group)",
        players
    )
    cur.executemany(
        "INSERT INTO player_events VALUES (:event_id, :player_id, :event_timestamp, :event_date, "
        ":event_name, :level, :session_id, :event_value)",
        [{**e, "level": e["level"] or None, "event_value": e["event_value"] or None} for e in events]
    )
    cur.executemany(
        "INSERT INTO sessions VALUES (:session_id, :player_id, :session_start, :session_end, "
        ":session_duration, :sessions_number)",
        sessions
    )

    cur.executescript("""
        CREATE INDEX idx_events_player ON player_events(player_id);
        CREATE INDEX idx_events_name ON player_events(event_name);
        CREATE INDEX idx_sessions_player ON sessions(player_id);
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print(f"Generating {N_PLAYERS} players...")
    players, quality, install_offsets = gen_players(N_PLAYERS)

    print("Generating events and sessions (onboarding funnel, retention, engagement)...")
    events, sessions = gen_events_and_sessions(players, quality, install_offsets)

    print(f"  players:       {len(players):,}")
    print(f"  player_events: {len(events):,}")
    print(f"  sessions:      {len(sessions):,}")

    print("Writing CSVs...")
    write_csv(f"{OUT_DIR}/players.csv", players,
              ["player_id", "install_date", "country", "device_type", "acquisition_channel", "age_group"])
    write_csv(f"{OUT_DIR}/player_events.csv", events,
              ["event_id", "player_id", "event_timestamp", "event_date", "event_name", "level", "session_id", "event_value"])
    write_csv(f"{OUT_DIR}/sessions.csv", sessions,
              ["session_id", "player_id", "session_start", "session_end", "session_duration", "sessions_number"])

    print("Building SQLite database...")
    build_sqlite(players, events, sessions)
    print(f"Done. Database at {DB_PATH}")

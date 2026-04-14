import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "bot_data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            last_name   TEXT,
            first_seen  TEXT,
            last_seen   TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            username    TEXT,
            full_name   TEXT,
            action      TEXT,
            detail      TEXT,
            timestamp   TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_activity(user, action, detail=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = user.username or ""
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username   = excluded.username,
            first_name = excluded.first_name,
            last_name  = excluded.last_name,
            last_seen  = excluded.last_seen
    """, (user.id, username, first_name, last_name, now, now))
    c.execute("""
        INSERT INTO activities (user_id, username, full_name, action, detail, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user.id, username, full_name, action, detail, now))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_actions = c.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    conn.close()
    return total_users, total_actions


def get_recent_activities(limit=50):
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute("""
        SELECT username, full_name, action, detail, timestamp
        FROM activities ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_users():
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute("""
        SELECT user_id, username, first_name, last_name, first_seen, last_seen
        FROM users ORDER BY last_seen DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

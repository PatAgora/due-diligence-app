#!/usr/bin/env python3
"""
Create the SQLite DB and seed a login user for Scrutinise apps.

Usage:
  python init_auth_db.py --email admin@example.com --password "ChangeMe!2025" --name "Admin" --role admin
  python init_auth_db.py --db ./scrutinise_workflow.db
"""

import argparse
import sqlite3
from datetime import datetime
from typing import Optional
from werkzeug.security import generate_password_hash

DEFAULT_DB = "scrutinise_workflow.db"

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        name TEXT,
        team_lead TEXT,
        level INTEGER,
        created_at TEXT,
        last_active TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT,
        requested_ip TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,
]

DEFAULT_SETTINGS = {
    "rework_overdue_days": "5",
    "default_task_limit": "50",
    "password_expiry_days": "90",
}

def upsert_settings(conn: sqlite3.Connection, settings: dict) -> None:
    cur = conn.cursor()
    for k, v in settings.items():
        cur.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (k, v))
    conn.commit()

def seed_user(conn: sqlite3.Connection,
              email: str,
              password: str,
              name: str,
              role: str,
              team_lead: Optional[str],
              level: Optional[int]) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (email,))
    row = cur.fetchone()
    if row:
        print(f"✔ User already exists: {email} (id={row[0]}) – skipping insert")
        return row[0]

    pw_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)
    now_iso = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT INTO users (email, password_hash, role, name, team_lead, level, created_at, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (email.strip().lower(), pw_hash, role.strip().lower(), name, team_lead, level, now_iso, now_iso))
    conn.commit()
    user_id = cur.lastrowid
    print(f"✔ Created user: {email} (id={user_id}, role={role})")
    return user_id

def main():
    ap = argparse.ArgumentParser(description="Initialize Scrutinise auth DB and seed a login user.")
    ap.add_argument("--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    ap.add_argument("--email", default="admin@example.com", help="Seed user email")
    ap.add_argument("--password", default="ChangeMe!2025", help="Seed user password")
    ap.add_argument("--name", default="Admin", help="Seed user name")
    ap.add_argument("--role", default="admin", help="Seed user role (e.g., admin, reviewer_1, sme)")
    ap.add_argument("--team-lead", dest="team_lead", default=None, help="Optional team lead name")
    ap.add_argument("--level", type=int, default=None, help="Optional level (e.g., 1/2/3)")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()

        upsert_settings(conn, DEFAULT_SETTINGS)

        seed_user(
            conn,
            email=args.email,
            password=args.password,
            name=args.name,
            role=args.role,
            team_lead=args.team_lead,
            level=args.level
        )
        print("✅ Database initialization complete.")
        print(f"   DB file: {args.db}")
        print(f"   Login with: {args.email} / {args.password}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
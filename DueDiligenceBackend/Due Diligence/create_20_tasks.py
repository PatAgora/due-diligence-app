"""
Utility script to create 20 dummy review tasks for CUST021 / CUST022
with randomised customer information fields.

Run from the `Due Diligence` directory:
    python create_20_tasks.py
"""

import random
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATHS = [
    "scrutinise_workflow.db",
    "database.db",
]


def find_db() -> Path:
    for p in DB_PATHS:
        path = Path(p)
        if path.exists():
            return path
    raise SystemExit("No SQLite DB found (tried: " + ", ".join(DB_PATHS) + ")")


FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Edward",
    "Fiona", "George", "Hannah", "Ian", "Julia",
]

LAST_NAMES = [
    "Smith", "Jones", "Brown", "Taylor", "Wilson",
    "Clark", "Johnson", "Walker", "Roberts", "Thompson",
]

OCCUPATIONS = [
    "Engineer", "Teacher", "Accountant", "Designer",
    "Consultant", "Analyst", "Manager", "Developer",
]

COUNTRIES = ["GB", "US", "DE", "FR", "NL"]
CITIES = ["London", "Manchester", "Bristol", "Leeds", "Birmingham"]


def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_email(name: str) -> str:
    base = name.lower().replace(" ", ".")
    domain = random.choice(["example.com", "mail.com", "demo.co.uk"])
    return f"{base}{random.randint(1,99)}@{domain}"


def random_phone() -> str:
    return "+44" + "".join(str(random.randint(0, 9)) for _ in range(10))


def random_address() -> str:
    return f"{random.randint(1, 200)} {random.choice(['High St', 'King St', 'Queen Rd', 'Station Rd'])}, {random.choice(CITIES)}"


def build_record_defaults(col) -> object:
    name = col["name"]
    coltype = (col["type"] or "").lower()

    # Explicit mappings for known/likely fields
    if name == "status":
        # New tasks should start as unassigned
        return "Unassigned"
    if name == "id":
        # Let SQLite auto-generate PK where applicable
        return None
    if name == "customer_id":
        # Filled later per-row
        return None
    if name == "task_id":
        # Filled later per-row
        return None
    if name == "assigned_to":
        # Start unassigned
        return None
    if "date" in name.lower():
        return None
    if "amount" in name.lower():
        return 0.0
    if "currency" in name.lower():
        return "GBP"
    if "country" in name.lower():
        return random.choice(COUNTRIES)
    if "city" in name.lower():
        return random.choice(CITIES)
    if "postcode" in name.lower() or "zip" in name.lower():
        return "AB1 2CD"
    if "phone" in name.lower() or "mobile" in name.lower():
        return random_phone()
    if "email" in name.lower():
        # Will be set from name later if possible
        return None
    if "name" in name.lower():
        return random_name()
    if "address" in name.lower():
        return random_address()
    if "occupation" in name.lower() or "job" in name.lower():
        return random.choice(OCCUPATIONS)
    if "qc_" in name.lower():
        # QC flags default to 0 / None
        if "outcome" in name.lower():
            return ""
        return 0
    if "sme_" in name.lower() or "sme" == name.lower():
        return None
    if "outreach" in name.lower():
        return None

    # Generic fallbacks based on type
    if "int" in coltype:
        return 0
    if "real" in coltype or "float" in coltype or "double" in coltype:
        return 0.0

    return None


def main():
    db_path = find_db()
    print(f"Using DB: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Introspect reviews table
    cur.execute("PRAGMA table_info(reviews)")
    cols = cur.fetchall()
    if not cols:
        raise SystemExit("Table 'reviews' not found in DB.")

    # Build per-column defaults
    defaults = {c["name"]: build_record_defaults(c) for c in cols}

    # Prepare list of NOT NULL columns without default value
    required_cols = [c["name"] for c in cols if c["notnull"] == 1 and c["dflt_value"] is None]

    # Determine current max numeric suffix for task_id pattern TASK-YYYYMMDD-XXX
    cur.execute("SELECT task_id FROM reviews WHERE task_id LIKE 'TASK-%'")
    existing_ids = [r["task_id"] for r in cur.fetchall() if r["task_id"]]
    max_suffix = 0
    today_str = datetime.today().strftime("%Y%m%d")
    for tid in existing_ids:
        try:
            parts = tid.split("-")
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                max_suffix = max(max_suffix, int(parts[2]))
        except Exception:
            continue

    to_insert = []
    cust_ids = ["CUST021", "CUST022"]

    for i in range(1, 21):
        seq = max_suffix + i
        task_id = f"TASK-{today_str}-{seq:03d}"
        customer_id = random.choice(cust_ids)

        # Start with defaults
        rec = dict(defaults)
        rec["task_id"] = task_id
        rec["customer_id"] = customer_id

        # Derive email from any name field if present
        name_field = None
        for k in rec.keys():
            if "name" in k.lower() and rec[k]:
                name_field = rec[k]
                break
        if name_field:
            for k in list(rec.keys()):
                if "email" in k.lower() and not rec[k]:
                    rec[k] = random_email(name_field)

        # Ensure all required columns have some value
        for col_name in required_cols:
            if rec.get(col_name) is None:
                # Best-effort generic defaults
                if "date" in col_name.lower():
                    rec[col_name] = None
                elif col_name == "id":
                    # Let SQLite auto-generate primary key
                    rec[col_name] = None
                elif "id" in col_name.lower():
                    rec[col_name] = ""
                else:
                    rec[col_name] = ""

        to_insert.append(rec)

    if not to_insert:
        print("Nothing to insert.")
        return

    # Build insert statement using all keys in rec
    col_names = list(to_insert[0].keys())
    # Quote column names to handle spaces / reserved words
    col_names_quoted = [f'"{c}"' for c in col_names]
    placeholders = ",".join(["?"] * len(col_names))
    sql = f"INSERT INTO reviews ({', '.join(col_names_quoted)}) VALUES ({placeholders})"

    rows = [tuple(rec[c] for c in col_names) for rec in to_insert]
    cur.executemany(sql, rows)
    conn.commit()

    print(f"Inserted {len(rows)} tasks:")
    for rec in to_insert:
        print(f"  {rec['task_id']} - {rec['customer_id']}")

    conn.close()


if __name__ == "__main__":
    main()



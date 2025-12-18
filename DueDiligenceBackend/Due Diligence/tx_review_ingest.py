"""
Transaction Review Data Ingestion Module
Handles CSV file uploads and transaction scoring for Transaction Review
"""
import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta, date
from collections import defaultdict
import statistics


def _excel_serial_to_date(n):
    """Convert Excel serial date to Python date"""
    origin = date(1899, 12, 30)
    try:
        n = int(float(n))
        if n <= 0:
            return None
        return origin + timedelta(days=n)
    except Exception:
        return None


def _coerce_date(val):
    """Robust date parsing from various formats"""
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None

    COMMON_FORMATS = [
        "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y",
        "%d-%m-%Y", "%Y/%m/%d",
    ]

    # 1) numeric → Excel serial
    try:
        if isinstance(val, (int, float)) or s.replace(".", "", 1).isdigit():
            d = _excel_serial_to_date(val)
            if d:
                return d
    except Exception:
        pass

    # 2) try explicit formats
    for fmt in COMMON_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass

    # 3) last resort: pandas to_datetime
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.notna(d):
            return d.date()
    except Exception:
        pass
    try:
        d = pd.to_datetime(s, dayfirst=False, errors="coerce")
        if pd.notna(d):
            return d.date()
    except Exception:
        pass

    return None


def _tx_cfg_get(conn, key, default=None, cast=str):
    """Get a Transaction Review config value from config_kv table"""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Ensure config_kv table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config_kv(
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    row = cur.execute("SELECT value FROM config_kv WHERE key=?", (key,)).fetchone()
    
    if not row or row["value"] is None:
        _tx_cfg_set(conn, key, default)
        return default
    
    raw = row["value"]
    try:
        if cast is float: return float(raw)
        if cast is int: return int(float(raw))
        if cast is bool: return raw in ("1", "true", "True", "yes", "on")
        if cast is list: return json.loads(raw) if raw else []
        return raw
    except Exception:
        return default


def _tx_cfg_set(conn, key, value):
    """Set a Transaction Review config value in config_kv table"""
    cur = conn.cursor()
    
    # Ensure config_kv table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config_kv(
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    if isinstance(value, list):
        val = json.dumps(value)
    elif isinstance(value, bool):
        val = "1" if value else "0"
    else:
        val = "" if value is None else str(value)
    
    cur.execute("""
        INSERT INTO config_kv(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
    """, (key, val))
    conn.commit()


def _tx_cfg_get_bool(conn, key, default=True):
    """Get boolean config value"""
    v = _tx_cfg_get(conn, key, None)
    if v is None:
        _tx_cfg_set(conn, key, default)
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


def _get_country_map(conn):
    """Get country risk data as a map"""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ref_country_risk(
            iso2 TEXT PRIMARY KEY,
            risk_level TEXT CHECK(risk_level IN ('LOW','MEDIUM','HIGH','HIGH_3RD','PROHIBITED')),
            score INTEGER NOT NULL,
            prohibited INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    rows = cur.execute("SELECT iso2, risk_level, score, prohibited FROM ref_country_risk").fetchall()
    return {r["iso2"]: dict(r) for r in rows}


def _get_expected_map(conn):
    """Get KYC expected monthly in/out as a map"""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kyc_profile(
            customer_id TEXT PRIMARY KEY,
            expected_monthly_in REAL,
            expected_monthly_out REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    rows = cur.execute("SELECT customer_id, expected_monthly_in, expected_monthly_out FROM kyc_profile").fetchall()
    return {
        r["customer_id"]: {
            "expected_monthly_in": float(r["expected_monthly_in"] or 0),
            "expected_monthly_out": float(r["expected_monthly_out"] or 0)
        }
        for r in rows
    }


def _risky_terms_enabled(conn):
    """Get list of enabled risky terms"""
    terms = _tx_cfg_get(conn, "cfg_risky_terms2", [], list)
    return [t.get("term") for t in terms if isinstance(t, dict) and t.get("enabled")]


def ingest_transactions_csv(conn, fobj):
    """
    Ingest transactions from CSV file
    Returns: (count_inserted, count_skipped_bad_dates)
    """
    # --- load & validate columns --------------------------------------------
    df = pd.read_csv(fobj)

    needed = {
        "id", "txn_date", "customer_id", "direction", "amount", "currency", "base_amount",
        "country_iso2", "payer_sort_code", "payee_sort_code", "channel", "narrative"
    }
    missing = needed - set(map(str, df.columns))
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    # --- txn_date robust parsing (no warnings, no mass failure) -------------
    df["txn_date"] = df["txn_date"].apply(_coerce_date)
    bad_dates = df["txn_date"].isna().sum()
    if bad_dates:
        # Drop rows with unparseable txn_date
        df = df[df["txn_date"].notna()]

    # --- normalize text-ish fields ------------------------------------------
    df["direction"] = df["direction"].astype(str).str.lower().str.strip()
    df["currency"] = df.get("currency", "GBP").fillna("GBP").astype(str).str.strip()

    # Normalize optional text fields (empty → None)
    for col in ["country_iso2", "payer_sort_code", "payee_sort_code", "channel", "narrative"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
            df[col] = df[col].str.strip()
            df[col] = df[col].replace({"": None, "nan": None, "None": None, "NULL": None})
        else:
            df[col] = None

    # ISO2 upper-case
    df["country_iso2"] = df["country_iso2"].apply(lambda x: (x or "").upper() or None)

    # channel lower-case
    df["channel"] = df["channel"].apply(lambda x: (x or "").lower() or None)

    # --- amounts: coerce, backfill, then fill (0.0) to satisfy NOT NULL -----
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["base_amount"] = pd.to_numeric(df["base_amount"], errors="coerce")

    mask_amt_na = df["amount"].isna() & df["base_amount"].notna()
    mask_base_na = df["base_amount"].isna() & df["amount"].notna()
    df.loc[mask_amt_na, "amount"] = df.loc[mask_amt_na, "base_amount"]
    df.loc[mask_base_na, "base_amount"] = df.loc[mask_base_na, "amount"]

    df["amount"] = df["amount"].fillna(0.0)
    df["base_amount"] = df["base_amount"].fillna(0.0)

    # --- ensure transactions table exists ----------------------------------
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id TEXT PRIMARY KEY,
            txn_date DATE NOT NULL,
            customer_id TEXT NOT NULL,
            direction TEXT CHECK(direction IN ('in','out')) NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'GBP',
            base_amount REAL NOT NULL,
            country_iso2 TEXT,
            payer_sort_code TEXT,
            payee_sort_code TEXT,
            channel TEXT,
            narrative TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # --- insert --------------------------------------------------------------
    recs = df.to_dict(orient="records")
    n_inserted = 0
    for r in recs:
        cur.execute(
            """INSERT OR REPLACE INTO transactions
               (id, txn_date, customer_id, direction, amount, currency, base_amount, country_iso2,
                payer_sort_code, payee_sort_code, channel, narrative)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(r["id"]),
                str(r["txn_date"]),  # now a real date
                str(r["customer_id"]),
                str(r["direction"]),
                float(r["amount"]),  # not null
                str(r.get("currency", "GBP")),
                float(r["base_amount"]),  # not null
                (str(r["country_iso2"]) if r.get("country_iso2") else None),
                (str(r["payer_sort_code"]) if r.get("payer_sort_code") else None),
                (str(r["payee_sort_code"]) if r.get("payee_sort_code") else None),
                (str(r["channel"]) if r.get("channel") else None),
                (str(r["narrative"]) if r.get("narrative") else None),
            )
        )
        n_inserted += 1

    conn.commit()
    
    # Score new transactions
    score_new_transactions(conn)

    return n_inserted, bad_dates


def score_new_transactions(conn):
    """
    Score transactions that don't have alerts yet
    Creates alerts based on configured rules
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Ensure alerts table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            severity TEXT CHECK(severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')) NOT NULL,
            reasons TEXT NOT NULL,
            rule_tags TEXT NOT NULL,
            config_version INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Ensure config_versions table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config_versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    country_map = _get_country_map(conn)
    expected_map = _get_expected_map(conn)

    # Params
    high_risk_min_amount = _tx_cfg_get(conn, "cfg_high_risk_min_amount", 0.0, float)
    median_mult = _tx_cfg_get(conn, "cfg_median_multiplier", 3.0, float)
    exp_out_factor = _tx_cfg_get(conn, "cfg_expected_out_factor", 1.2, float)
    exp_in_factor = _tx_cfg_get(conn, "cfg_expected_in_factor", 1.2, float)
    enabled_terms = _risky_terms_enabled(conn)
    sev_crit = _tx_cfg_get(conn, "cfg_sev_critical", 90, int)
    sev_high = _tx_cfg_get(conn, "cfg_sev_high", 70, int)
    sev_med = _tx_cfg_get(conn, "cfg_sev_medium", 50, int)
    sev_low = _tx_cfg_get(conn, "cfg_sev_low", 30, int)

    # Toggles
    on = {
        "prohibited_country": _tx_cfg_get_bool(conn, "cfg_rule_enabled_prohibited_country", True),
        "high_risk_corridor": _tx_cfg_get_bool(conn, "cfg_rule_enabled_high_risk_corridor", True),
        "median_outlier": _tx_cfg_get_bool(conn, "cfg_rule_enabled_median_outlier", True),
        "nlp_risky_terms": _tx_cfg_get_bool(conn, "cfg_rule_enabled_nlp_risky_terms", True),
        "expected_out": _tx_cfg_get_bool(conn, "cfg_rule_enabled_expected_out", True),
        "expected_in": _tx_cfg_get_bool(conn, "cfg_rule_enabled_expected_in", True),
        "cash_daily_breach": _tx_cfg_get_bool(conn, "cfg_rule_enabled_cash_daily_breach", True),
        "severity_mapping": _tx_cfg_get_bool(conn, "cfg_rule_enabled_severity_mapping", True),
    }

    # Medians
    cur.execute("SELECT customer_id, direction, base_amount FROM transactions")
    per_key = defaultdict(list)
    for r in cur.fetchall():
        per_key[(r["customer_id"], r["direction"])].append(r["base_amount"])
    cust_medians = {k: statistics.median(v) for k, v in per_key.items() if v}

    # Worklist - transactions without alerts
    txns = cur.execute("""
        SELECT t.* FROM transactions t
        LEFT JOIN alerts a ON a.txn_id = t.id
        WHERE a.id IS NULL
        ORDER BY t.txn_date ASC
    """).fetchall()

    for t in txns:
        reasons, tags, score = [], [], 0
        severity = "INFO"
        chan = (t["channel"] or "").lower()
        narrative = (t["narrative"] or "")

        d = date.fromisoformat(t["txn_date"])
        month_start = d.replace(day=1).isoformat()
        month_end = ((d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).isoformat()

        month_in_total = float(cur.execute(
            "SELECT SUM(base_amount) s FROM transactions WHERE customer_id=? AND direction='in' AND txn_date BETWEEN ? AND ?",
            (t["customer_id"], month_start, month_end)
        ).fetchone()["s"] or 0)

        month_out_total = float(cur.execute(
            "SELECT SUM(base_amount) s FROM transactions WHERE customer_id=? AND direction='out' AND txn_date BETWEEN ? AND ?",
            (t["customer_id"], month_start, month_end)
        ).fetchone()["s"] or 0)

        exp = expected_map.get(t["customer_id"], {"expected_monthly_in": 0, "expected_monthly_out": 0})
        expected_monthly_in = float(exp.get("expected_monthly_in") or 0)
        expected_monthly_out = float(exp.get("expected_monthly_out") or 0)
        med = float(cust_medians.get((t["customer_id"], t["direction"]), 0.0))

        # Prohibited
        c = country_map.get(t["country_iso2"] or "")
        if on["prohibited_country"] and c and c["prohibited"]:
            reasons.append(f"Prohibited country {t['country_iso2']}")
            tags.append("PROHIBITED_COUNTRY")
            score += 100

        # High-risk
        elif on["high_risk_corridor"] and c and (c["risk_level"] in ("HIGH_3RD", "HIGH")) and float(t["base_amount"]) >= high_risk_min_amount:
            reasons.append(f"High-risk corridor {t['country_iso2']} ({c['risk_level']})")
            tags.append("HIGH_RISK_COUNTRY")
            score += int(c["score"])

        # Cash daily breach (GLOBAL)
        cash_daily_limit = float(_tx_cfg_get(conn, "cfg_cash_daily_limit", 0.0, float))
        if on["cash_daily_breach"] and cash_daily_limit > 0 and (chan == "cash" or "cash" in narrative.lower()):
            d_total = float(cur.execute(
                "SELECT SUM(base_amount) AS s FROM transactions "
                "WHERE customer_id=? AND txn_date=? "
                "AND (lower(IFNULL(channel,''))='cash' OR instr(lower(IFNULL(narrative,'')),'cash')>0)",
                (t["customer_id"], t["txn_date"])
            ).fetchone()["s"] or 0)
            if d_total > cash_daily_limit:
                reasons.append(f"Cash daily limit breached (global £{cash_daily_limit:,.2f}; activity £{d_total:,.2f})")
                tags.append("CASH_DAILY_BREACH")
                score += 20

        # Median outlier
        if on["median_outlier"] and med > 0 and float(t["base_amount"]) > med * float(median_mult):
            reasons.append(f"Significant deviation (×{t['base_amount']/med:.1f})")
            tags.append("HISTORICAL_DEVIATION")
            score += 25

        # NLP risky terms (only enabled terms)
        if on["nlp_risky_terms"] and enabled_terms:
            low = narrative.lower()
            if any(term.lower() in low for term in enabled_terms):
                reasons.append("Narrative contains risky term(s)")
                tags.append("NLP_RISK")
                score += 10

        # Expected breaches
        if on["expected_out"] and t["direction"] == "out" and expected_monthly_out > 0:
            if month_out_total > expected_monthly_out * float(exp_out_factor):
                reasons.append(f"Outflows exceed expected (actual £{month_out_total:.2f})")
                tags.append("EXPECTED_BREACH_OUT")
                score += 20

        if on["expected_in"] and t["direction"] == "in" and expected_monthly_in > 0:
            if month_in_total > expected_monthly_in * float(exp_in_factor):
                reasons.append(f"Inflows exceed expected (actual £{month_in_total:.2f})")
                tags.append("EXPECTED_BREACH_IN")
                score += 15

        # Severity mapping
        if on["severity_mapping"]:
            if "PROHIBITED_COUNTRY" in tags or score >= sev_crit:
                severity = "CRITICAL"
            elif score >= sev_high:
                severity = "HIGH"
            elif score >= sev_med:
                severity = "MEDIUM"
            elif score >= sev_low:
                severity = "LOW"

        if reasons:
            # Get max config version ID
            config_version_row = cur.execute("SELECT MAX(id) as max_id FROM config_versions").fetchone()
            config_version = config_version_row["max_id"] if config_version_row and config_version_row["max_id"] else None
            
            cur.execute(
                """INSERT INTO alerts(txn_id, customer_id, score, severity, reasons, rule_tags, config_version)
                   VALUES(?,?,?,?,?,?,?)""",
                (t["id"], t["customer_id"], int(min(score, 100)), severity,
                 json.dumps(reasons), json.dumps(list(dict.fromkeys(tags))), config_version)
            )
    conn.commit()


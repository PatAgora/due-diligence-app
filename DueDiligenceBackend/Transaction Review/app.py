import os, sqlite3, csv, io, json
from datetime import datetime, date, timedelta
from collections import defaultdict
from datetime import date, timedelta
import ast
import math
import json
import re
from datetime import datetime
from typing import Optional

from flask import Flask, g, render_template, request, redirect, url_for, send_from_directory, flash, abort, jsonify

# Use shared database with Due Diligence module
# Path to shared database (scrutinise_workflow.db in Due Diligence folder)
DUE_DILIGENCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Due Diligence"))
DB_PATH = os.getenv("TX_DB") or os.path.join(DUE_DILIGENCE_DIR, "scrutinise_workflow.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY","devkey")

# ---------- Embedded schema (fallback if schema.sql not found) ----------
SCHEMA_SQL = r"""
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS config_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ref_country_risk(
  iso2 TEXT PRIMARY KEY,
  risk_level TEXT CHECK(risk_level IN ('LOW','MEDIUM','HIGH','HIGH_3RD','PROHIBITED')),
  score INTEGER NOT NULL,
  prohibited INTEGER DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ref_sort_codes(
  sort_code TEXT PRIMARY KEY,
  bank_name TEXT,
  branch TEXT,
  schemes TEXT,
  valid_from DATE,
  valid_to DATE
);

CREATE TABLE IF NOT EXISTS kyc_profile(
  customer_id TEXT PRIMARY KEY,
  expected_monthly_in REAL,
  expected_monthly_out REAL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_cash_limits(
  customer_id TEXT PRIMARY KEY,
  daily_limit REAL,
  weekly_limit REAL,
  monthly_limit REAL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

CREATE INDEX IF NOT EXISTS idx_tx_customer_date ON transactions(customer_id, txn_date);
CREATE INDEX IF NOT EXISTS idx_tx_country ON transactions(country_iso2);
CREATE INDEX IF NOT EXISTS idx_tx_direction ON transactions(direction);

CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  txn_id TEXT NOT NULL,
  customer_id TEXT NOT NULL,
  score INTEGER NOT NULL,
  severity TEXT CHECK(severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')) NOT NULL,
  reasons TEXT NOT NULL,
  rule_tags TEXT NOT NULL,
  config_version INTEGER REFERENCES config_versions(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_customer ON alerts(customer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity, created_at);
"""

# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def exec_script(path):
    db = get_db()
    try:
        with open(path, "r") as f:
            db.executescript(f.read())
    except FileNotFoundError:
        # Fallback to embedded schema
        db.executescript(SCHEMA_SQL)
    db.commit()

def ensure_config_kv_table():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS config_kv(
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()

# --- AI Rationale storage ----------------------------------------------------
def ensure_ai_rationale_table():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS ai_rationales (
          id INTEGER PRIMARY KEY,
          customer_id TEXT NOT NULL,
          period_from TEXT,
          period_to TEXT,
          nature_of_business TEXT,
          est_income REAL,
          est_expenditure REAL,
          rationale_text TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(customer_id, period_from, period_to)
        );
    """)
    db.commit()

def _load_rationale_row(customer_id: str, p_from: Optional[str], p_to: Optional[str]):
    db = get_db()
    return db.execute(
        "SELECT * FROM ai_rationales WHERE customer_id=? AND IFNULL(period_from,'')=IFNULL(?, '') AND IFNULL(period_to,'')=IFNULL(?, '')",
        (customer_id, p_from, p_to)
    ).fetchone()

def _upsert_rationale_row(customer_id: str, p_from: Optional[str], p_to: Optional[str],
                          nature_of_business: Optional[str], est_income: Optional[float],
                          est_expenditure: Optional[float], rationale_text: str):
    db = get_db()
    db.execute("""
        INSERT INTO ai_rationales(customer_id, period_from, period_to, nature_of_business,
                                  est_income, est_expenditure, rationale_text)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(customer_id, period_from, period_to) DO UPDATE SET
            nature_of_business=excluded.nature_of_business,
            est_income=excluded.est_income,
            est_expenditure=excluded.est_expenditure,
            rationale_text=excluded.rationale_text,
            updated_at=CURRENT_TIMESTAMP;
    """, (customer_id, p_from, p_to, nature_of_business, est_income, est_expenditure, rationale_text))
    db.commit()

def _format_date_pretty(date_str: str) -> str:
    """YYYY-MM-DD -> '18th July 2025'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    d = dt.day
    suffix = "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    return f"{d}{suffix} {dt.strftime('%B %Y')}"

def _latest_case_customer_id() -> Optional[str]:
    row = get_db().execute(
        "SELECT customer_id FROM ai_cases ORDER BY updated_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return row["customer_id"] if row else None

def _build_customer_friendly_sentence(country_name: str, items: list) -> str:
    """
    items: [{'date':'YYYY-MM-DD','direction':'IN'|'OUT','amount':float}]
    -> Our records show X received from <country> ... and Y sent to <country> ...
    """
    incoming = [i for i in items if i["direction"] == "IN"]
    outgoing = [i for i in items if i["direction"] == "OUT"]

    def describe(trans, preamble):
        parts = [f"£{t['amount']:,.2f} on {_format_date_pretty(t['date'])}" for t in trans]
        n = len(trans)
        return f"{n} transaction{'s' if n != 1 else ''} {preamble} {country_name} valued at " + ", ".join(parts)

    segments = []
    if incoming:
        segments.append(describe(incoming, "were received from"))
    if outgoing:
        segments.append(describe(outgoing, "were sent to"))

    if not segments:
        return ""

    return "Our records show " + " and ".join(segments) + ". Please can you confirm the reasons for these transactions?"

def upsert_cash_limits(customer_id: str, daily: float, weekly: float, monthly: float):
    db = get_db()
    db.execute(
        """INSERT INTO customer_cash_limits(customer_id, daily_limit, weekly_limit, monthly_limit)
           VALUES(?,?,?,?)
           ON CONFLICT(customer_id) DO UPDATE SET
             daily_limit=excluded.daily_limit,
             weekly_limit=excluded.weekly_limit,
             monthly_limit=excluded.monthly_limit,
             updated_at=CURRENT_TIMESTAMP
        """,
        (customer_id, daily, weekly, monthly)
    )
    db.commit()

def cfg_get(key, default=None, cast=str):
    """Get a config value, cast if possible; store default if missing."""
    ensure_config_kv_table()
    row = get_db().execute("SELECT value FROM config_kv WHERE key=?", (key,)).fetchone()
    if not row or row["value"] is None:
        cfg_set(key, default)
        return default
    raw = row["value"]
    try:
        if cast is float: return float(raw)
        if cast is int:   return int(float(raw))
        if cast is bool:  return raw in ("1", "true", "True", "yes", "on")
        if cast is list:  return json.loads(raw) if raw else []
        return raw
    except Exception:
        return default

# --- Country name utility (fallback map; uses ISO2 -> full name) ---
_COUNTRY_NAME_FALLBACK = {
    "GB":"United Kingdom","AE":"United Arab Emirates","TR":"Türkiye","RU":"Russia",
    "US":"United States","DE":"Germany","FR":"France","ES":"Spain","IT":"Italy",
    "NL":"Netherlands","CN":"China","HK":"Hong Kong","SG":"Singapore","IE":"Ireland"
}
def country_full_name(iso2: str) -> str:
    if not iso2:
        return ""
    iso2 = str(iso2).upper().strip()
    return _COUNTRY_NAME_FALLBACK.get(iso2, iso2)

def human_join(items):
    # Oxford-comma joining of short phrases
    items = [str(x) for x in items if str(x)]
    if not items: return ""
    if len(items) == 1: return items[0]
    if len(items) == 2: return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"

def make_narrative_from_txns(txns):
    """
    txns: list of {txn_id, txn_date, base_amount, country_iso2, direction}
    Returns concise sentence like:
      'two transactions to Russia valued at £1,234.00 on 2025-08-29 and £577.89 on 2025-09-11'
    Groups by country + direction; limits to 3 dates per group; rolls-up counts.
    """
    if not txns:
        return ""
    from collections import defaultdict
    buckets = defaultdict(list)  # (preposition, country) -> [text parts]
    # Normalize and sort by date
    norm = []
    for t in txns:
        norm.append({
            "date": str(t.get("txn_date","")),
            "amt": float(t.get("base_amount") or 0.0),
            "country": country_full_name(t.get("country_iso2")),
            "dir": (t.get("direction") or "").lower(),
        })
    norm.sort(key=lambda x: x["date"])

    for t in norm:
        prep = "to" if t["dir"] == "out" else "from"
        buckets[(prep, t["country"])].append(f"£{t['amt']:,.2f} on {t['date']}")

    parts = []
    for (prep, country), vals in buckets.items():
        n = len(vals)
        listed = human_join(vals[:3])
        extra = "" if n <= 3 else f" (and {n-3} more)"
        plural = "transaction" if n == 1 else "transactions"
        parts.append(f"{n} {plural} {prep} {country} valued at {listed}{extra}")
    return human_join(parts)

def cfg_set(key, value):
    """Upsert config value; lists -> JSON."""
    ensure_config_kv_table()
    if isinstance(value, list):
        val = json.dumps(value)
    elif isinstance(value, bool):
        val = "1" if value else "0"
    else:
        val = "" if value is None else str(value)
    db = get_db()
    db.execute("""
        INSERT INTO config_kv(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
    """, (key, val))
    db.commit()

def format_date_pretty(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day = dt.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    # Portable day formatting
    return f"{day}{suffix} {dt.strftime('%B %Y')}"

def build_customer_friendly_question(transactions, country_name):
    incoming = [t for t in transactions if t["direction"] == "IN"]
    outgoing = [t for t in transactions if t["direction"] == "OUT"]

    parts = []
    if incoming:
        inc_desc = ", ".join(
            f"£{t['amount']:.2f} on {format_date_pretty(t['date'])}"
            for t in incoming
        )
        parts.append(f"{len(incoming)} transaction{'s' if len(incoming)>1 else ''} were received from {country_name} valued at {inc_desc}")
    if outgoing:
        out_desc = ", ".join(
            f"£{t['amount']:.2f} on {format_date_pretty(t['date'])}"
            for t in outgoing
        )
        parts.append(f"{len(outgoing)} transaction{'s' if len(outgoing)>1 else ''} were sent to {country_name} valued at {out_desc}")

    sentence = " and ".join(parts)
    return f"Our records show {sentence}. Please can you confirm the reasons for these transactions?"

def ai_normalise_questions_llm(customer_id, fired_tags, source_alerts, base_questions, model=None, max_count=6):
    """
    Ask the LLM to merge/rephrase questions; preserve best-fit tag; attach sources.
    Falls back to base_questions on any error.
    """
    if not llm_enabled():
        return base_questions

    # build per-tag → txn_ids map from source_alerts
    per_tag_src = {}
    for r in source_alerts:
        per_tag_src.setdefault(r["tag"], [])
        if r["txn_id"] not in per_tag_src[r["tag"]]:
            per_tag_src[r["tag"]].append(r["txn_id"])

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = model or str(cfg_get("cfg_ai_model", "gpt-4o-mini"))

        lines = [
            f"Customer: {customer_id}",
            f"Alert tags observed: {', '.join(sorted(set(fired_tags or [])))}",
            "Example alerts (tag / sev / score / date / txn_id):"
        ]
        for r in source_alerts[:15]:
            lines.append(f"- {r['tag']} / {r['severity']} / {r['score']} / {r['txn_date']} / {r['txn_id']}")
        lines.append("\nExisting questions (pre-normalisation):")
        for q in base_questions:
            lines.append(f"- [{q['tag']}] {q['question']}")

        prompt = "\n".join(lines) + f"""
Please consolidate these into at most {max_count} clear, non-leading outreach questions for the customer.
Group overlaps; keep terminology neutral and regulator-friendly.
Return STRICT JSON array, each item exactly:
{{"tag":"<tag from observed set>","question":"<clean customer-facing question>","sources":["<txn_id>", "..."]}}
If you cannot determine per-question sources from context, use an empty array [].
"""

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a financial-crime analyst. Be concise, neutral, and non-leading."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)

        out, seen = [], set()
        for item in data:
            tag = (item.get("tag") or "").strip() or (fired_tags[0] if fired_tags else "NLP_RISK")
            q   = (item.get("question") or "").strip()
            src = item.get("sources") or []
            if not q:
                continue
            if not src and tag in per_tag_src:
                src = per_tag_src[tag][:5]
            key = (tag, q.lower())
            if key in seen: 
                continue
            seen.add(key)
            out.append({"tag": tag, "question": q, "sources": src})
        return out or base_questions

    except Exception:
        # fallback: dedupe base set; keep per-tag sources we already computed
        out, seen = [], set()
        for q in base_questions:
            key = (q["tag"], q["question"].lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({"tag": q["tag"], "question": q["question"], "sources": q.get("sources", [])})
        return out

def enrich_txn_details(txn_ids):
    """Return dict {txn_id: {txn_id, txn_date, base_amount, country_iso2, direction}}."""
    if not txn_ids:
        return {}
    db = get_db()
    qmarks = ",".join("?" for _ in txn_ids)
    rows = db.execute(f"""
        SELECT id AS txn_id, txn_date, base_amount, country_iso2, direction
        FROM transactions
        WHERE id IN ({qmarks})
    """, list(map(str, txn_ids))).fetchall()
    return {r["txn_id"]: dict(r) for r in rows}

def init_db():
    # Using shared database - ensure it exists
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Shared database not found at {DB_PATH}. Please ensure Due Diligence module is set up.")
    # Will use schema.sql if present; otherwise uses embedded SCHEMA_SQL
    # Note: Tables should already exist from migration, but this ensures schema is up to date
    exec_script(os.path.join(os.path.dirname(__file__), "schema.sql"))
    db = get_db()
    # Only insert init config_version if table is empty (idempotent)
    cur = db.execute("SELECT COUNT(*) c FROM config_versions")
    if cur.fetchone()["c"] == 0:
        db.execute("INSERT INTO config_versions(name) VALUES (?)", ("init",))
        db.commit()

ALLOWED_AST_NODES = {
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.Load, ast.Name, ast.Constant, ast.Call,
    ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod
}

import re

def _get_patterns(key: str, defaults: list) -> list:
     items = cfg_get(key, None, list)
     if items is None:
         # seed once
         seeded = [{"term": p, "enabled": True} for p in defaults]
         cfg_set(key, seeded)
         items = seeded
     return [i["term"] for i in items if isinstance(i, dict) and i.get("enabled")]

def _mitigant_patterns():
     defaults = [
         r"\binvoice\b", r"\bcontract\b", r"\bpurchase\s*order\b|\bPO\b",
         r"\bid\s*verified\b|\bKYC\b|\bscreened\b",
         r"\bshipping\b|\bbill of lading\b|\bBOL\b|\btracking\b",
         r"\bevidence\b|\bdocument(s)?\b|\bproof\b",
         r"\bbank transfer\b|\bwire\b|\bSWIFT\b|\bIBAN\b|\baudit trail\b",
     ]
     return _get_patterns("cfg_mitigant_patterns", defaults)

def _aggravant_patterns():
     defaults = [
         r"\bcash\b", r"\bcrypto\b|\busdt\b", r"\bgift\b", r"\bfamily\b|\bfriend\b",
         r"\bno doc(s)?\b|\bcannot provide\b|\bunknown\b|\bunaware\b",
         r"\bshell\b|\boffshore\b"
     ]
     return _get_patterns("cfg_aggravant_patterns", defaults)

def analyse_answer(text: str):
    """Return {'class': 'mitigating'|'aggravating'|'neutral'|'blank', 'hits': [...]}."""
    if not text or not text.strip():
        return {"class": "blank", "hits": []}
    t = text.lower()
    m_hits = [p for p in _mitigant_patterns() if re.search(p, t)]
    a_hits = [p for p in _aggravant_patterns() if re.search(p, t)]
    if a_hits and not m_hits:
        return {"class": "aggravating", "hits": a_hits}
    if m_hits and not a_hits:
        return {"class": "mitigating", "hits": m_hits}
    if m_hits and a_hits:
        # mixed; treat as neutral but note both
        return {"class": "neutral", "hits": m_hits + a_hits}
    return {"class": "neutral", "hits": []}

def cfg_get_bool(key, default=True):
    v = cfg_get(key, None)
    if v is None:
        cfg_set(key, default)
        return default
    return str(v).lower() in ("1","true","yes","on")

def llm_enabled():
    # Toggle + API key present
    return bool(os.getenv("OPENAI_API_KEY")) and bool(cfg_get("cfg_ai_use_llm", False))

def ai_suggest_questions_llm(customer_id, fired_tags, sample_alerts, base_questions, model=None):
    """Return up to a few extra questions from ChatGPT. Fails closed (returns [])."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = model or str(cfg_get("cfg_ai_model", "gpt-4o-mini"))

        # Compact context
        lines = [f"Customer: {customer_id}", "Alert tags (severity/score/date):"]
        for r in (sample_alerts or [])[:10]:
            lines.append(f"- {r['tag']} / {r['severity']} / {r['score']} / {r['txn_date']}")
        lines.append("Base questions we already plan to ask:")
        for q in base_questions:
            lines.append(f"- [{q['tag']}] {q['question']}")
        prompt = "\n".join(lines) + """
Please propose up to 3 additional concise, non-leading, regulator-friendly questions that clarify risk.
Return pure JSON array with objects of form: {"tag":"<best-fit tag>","question":"..."}.
"""

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a compliance analyst following AML/FCA best practice. Be concise and non-leading."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        import json
        txt = (resp.choices[0].message.content or "").strip()
        extras = json.loads(txt)
        out = []
        for e in extras:
            tag = (e.get("tag") or "").strip() or (fired_tags[0] if fired_tags else "NLP_RISK")
            q = (e.get("question") or "").strip()
            if q:
                out.append({"tag": tag, "question": q})
        return out
    except Exception:
        return []

def ai_question_bank():
    # One or more questions per tag; keep simple, non-leading, regulator-friendly phrasing.
    return {
        "PROHIBITED_COUNTRY": [
            "Please explain the purpose for sending funds to this location.",
            "Please can you provide details of the party you made the payment to, and confirm the nature of your relationship with them?"
        ],
        "HIGH_RISK_COUNTRY": [
            "What goods or services does this payment relate to?",
            "Can you confirm the nature of your relationship with this party?"
        ],
        "CASH_DAILY_BREACH": [
            "Why was cash used instead of electronic means for this amount?",
        ],
        "HISTORICAL_DEVIATION": [
            "This amount is higher than your usual activity. What is the reason for the increased activity?",
            "Is this a one-off or should we expect similar sized payments going forward?"
        ],
        "NLP_RISK": [
            "Please clarify the transaction narrative and provide supporting documentation (e.g., invoice/contract)."
        ],
        "EXPECTED_BREACH_OUT": [
            "Your monthly account outgoings exceed your declared expectations. What is the reason for the increase?",
            "Do we need to update your expected monthly outgoings moving forwards?"
        ],
        "EXPECTED_BREACH_IN": [
            "Your monthly account incomings exceed your declared expectations. What is the reason for the increase?",
            "Do we need to update your expected monthly incomings moving forwards?"
        ],
    }

def _severity_rank(sev: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}.get((sev or "").upper(), 0)

def build_ai_questions(customer_id, dfrom=None, dto=None, max_per_tag=5):
    """
    Returns:
      base_questions: [{"tag","question","sources":[txn_ids...]}]  (ONE per tag)
      fired_tags: list[str] in importance order
      preview_alerts: compact list of exemplar alerts for prompt
    """
    tagged = fetch_customer_alerts_with_tags(customer_id, dfrom, dto)
    if not tagged:
        return [], [], []

    from collections import defaultdict
    per_tag = defaultdict(list)
    for r in tagged:
        per_tag[r["tag"]].append(r)

    # order tags by worst severity → highest score → recency
    sev_rank = {"CRITICAL":1,"HIGH":2,"MEDIUM":3,"LOW":4,"INFO":5}
    fired = sorted(
        per_tag.keys(),
        key=lambda tg: (
            min(sev_rank.get(x["severity"], 5) for x in per_tag[tg]),
            -max(x["score"] or 0 for x in per_tag[tg]),
            max(x["txn_date"] for x in per_tag[tg]),
        )
    )

    # per-tag sources (txn_ids)
    per_tag_txn_ids = {tg: [x["txn_id"] for x in per_tag[tg][:max_per_tag]] for tg in per_tag}

    qbank = ai_question_bank()
    base = []

    # --- keep only ONE question per tag (the first template in qbank) ---
    for tg in fired:
        qs = qbank.get(tg, [])
        if not qs:
            continue
        q_text = qs[0].strip()  # choose the primary template for that tag
        base.append({
            "tag": tg,
            "question": q_text,
            "sources": per_tag_txn_ids.get(tg, [])
        })

    # compact exemplar alerts for prompt context
    preview = []
    for tg in fired:
        for r in per_tag[tg][:max_per_tag]:
            preview.append({
                "tag": tg, "severity": r["severity"], "score": r["score"],
                "txn_date": r["txn_date"], "txn_id": r["txn_id"]
            })
    return base, fired, preview

def ai_assess_responses(answer_rows, fired_tags):
    """
    Uses the *actual questions + answers* to build an explainable summary.
    Scoring:
      - Start from tag risk (same weights as before)
      - Per-answer: mitigating -6, aggravating +6, blank +2 (mild penalty)
    """
    # 1) Base from tags
    base = 0
    for t in set(fired_tags or []):
        if t == "PROHIBITED_COUNTRY": base += 70
        elif t == "HIGH_RISK_COUNTRY": base += 30
        elif t == "CASH_DAILY_BREACH": base += 15
        elif t == "HISTORICAL_DEVIATION": base += 20
        elif t == "NLP_RISK": base += 10
        elif t == "EXPECTED_BREACH_OUT": base += 15
        elif t == "EXPECTED_BREACH_IN": base += 10

    # 2) Question-by-question analysis
    bullets = []
    mitig_n = aggr_n = blank_n = 0
    for row in (answer_rows or []):
        q = (row.get("question") or "").strip()
        a = (row.get("answer") or "").strip()
        tag = row.get("tag") or "—"
        res = analyse_answer(a)

        # Adjust score
        if res["class"] == "mitigating":
            base -= 6; mitig_n += 1
            verdict = "Mitigating evidence noted"
        elif res["class"] == "aggravating":
            base += 6; aggr_n += 1
            verdict = "Aggravating indicator present"
        elif res["class"] == "blank":
            base += 2; blank_n += 1
            verdict = "No answer provided"
        else:
            verdict = "Neutral / requires review"

        bullets.append(f"- [{tag}] Q: {q} — {verdict}{'' if not a else f'; Answer: {a}'}")

    # 3) Clamp & map to band (re-using your severity thresholds)
    score = max(0, min(100, base))
    sev_crit = cfg_get("cfg_sev_critical", 90, int)
    sev_high = cfg_get("cfg_sev_high", 70, int)
    sev_med  = cfg_get("cfg_sev_medium", 50, int)
    sev_low  = cfg_get("cfg_sev_low", 30, int)

    if score >= sev_crit: band = "CRITICAL"
    elif score >= sev_high: band = "HIGH"
    elif score >= sev_med: band = "MEDIUM"
    elif score >= sev_low: band = "LOW"
    else: band = "INFO"

    # 4) Build a clean narrative summary that quotes the questions asked
    lines = []
    if fired_tags:
        lines.append(f"Triggered tags: {', '.join(sorted(set(fired_tags)))}.")
    if bullets:
        lines.append("Question & answer review:")
        lines.extend(bullets)
    # quick tallies
    if mitig_n or aggr_n or blank_n:
        tallies = []
        if mitig_n: tallies.append(f"{mitig_n} mitigating")
        if aggr_n: tallies.append(f"{aggr_n} aggravating")
        if blank_n: tallies.append(f"{blank_n} unanswered")
        lines.append(f"Answer quality: {', '.join(tallies)}.")
    lines.append(f"Calculated residual risk: {band} (score {score}).")

    return score, band, "\n".join(lines)

def _safe_eval(expr: str, names: dict) -> bool:
    """
    Very small, whitelisted expression evaluator for rule trigger conditions.
    Supports: and/or/not, comparisons, + - * / %, numeric/string constants,
    names from 'names', and calls to whitelisted helper functions below.
    """
    if not expr or not expr.strip():
        return False

    # Parse
    node = ast.parse(expr, mode="eval")

    # Validate node types
    for n in ast.walk(node):
        if type(n) not in ALLOWED_AST_NODES:
            raise ValueError(f"Disallowed expression element: {type(n).__name__}")
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            if n.func.id not in names:
                raise ValueError(f"Function '{n.func.id}' not allowed")

    # Evaluate
    code = compile(node, "<rule>", "eval")
    return bool(eval(code, {"__builtins__": {}}, names))

def load_rules_from_db():
    """Return list of dict rules from SQLite 'rules' table (if present)."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, category, rule, trigger_condition, score_impact, tags, outcome, description "
            "FROM rules ORDER BY category, rule"
        ).fetchall()
    except sqlite3.OperationalError:
        # 'rules' table not present yet
        return []

    out = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out

# Helper functions exposed to rule expressions -------------------------------

def in_high_risk(country_iso2: str) -> bool:
    cmap = get_country_map()
    c = cmap.get((country_iso2 or "").upper())
    return bool(c and (c["risk_level"] in ("HIGH", "HIGH_3RD") or int(c["prohibited"]) == 1))

def is_prohibited(country_iso2: str) -> bool:
    cmap = get_country_map()
    c = cmap.get((country_iso2 or "").upper())
    return bool(c and int(c["prohibited"]) == 1)

def contains(text: str, needle: str) -> bool:
    return (text or "").lower().find((needle or "").lower()) >= 0

def pct_over(actual: float, expected: float, factor: float = 1.0) -> bool:
    """Return True if actual > expected * factor."""
    try:
        return float(actual) > float(expected) * float(factor)
    except Exception:
        return False

def gt(x, y):  # handy for expressions
    try:
        return float(x) > float(y)
    except Exception:
        return False

def get_builtin_rules():
    """Return the hard-coded rules that are active in score_new_transactions(), as read-only metadata."""
    return [
        {
            "category": "Jurisdiction Risk",
            "rule": "Prohibited Country",
            "trigger_condition": "is_prohibited(txn.country_iso2)",
            "score_impact": "100",
            "tags": "PROHIBITED_COUNTRY",
            "outcome": "Critical",
            "description": "Flag any payment where the destination is on the prohibited list.",
        },
        {
            "category": "Jurisdiction Risk",
            "rule": "High-Risk Corridor",
            "trigger_condition": "in_high_risk(txn.country_iso2)",
            "score_impact": "Risk table score",
            "tags": "HIGH_RISK_COUNTRY",
            "outcome": "Escalate",
            "description": "Increase score for payments routed via high-risk or high-risk third countries.",
        },
        {
            "category": "Cash Activity",
            "rule": "Cash Daily Limit Breach",
            "trigger_condition": "txn.channel == 'cash' AND day_cash_total > configured daily_limit",
            "score_impact": "20",
            "tags": "CASH_DAILY_BREACH",
            "outcome": "Escalate",
            "description": "Alert when daily cash deposits/withdrawals exceed the set customer limit.",
        },
        {
            "category": "Behavioural Deviation",
            "rule": "Outlier vs Median",
            "trigger_condition": "txn.base_amount > 3 × median_amount (per customer + direction)",
            "score_impact": "25",
            "tags": "HISTORICAL_DEVIATION",
            "outcome": "Escalate",
            "description": "Flag unusually large transactions compared to customer’s typical behaviour.",
        },
        {
            "category": "Narrative Risk",
            "rule": "Risky Terms",
            "trigger_condition": "narrative contains any of: consultancy, gift, usdt, otc, crypto, cash, shell, hawala",
            "score_impact": "10",
            "tags": "NLP_RISK",
            "outcome": "Review",
            "description": "Flag transactions with sensitive wording in the narrative.",
        },
        {
            "category": "KYC Profile Breach",
            "rule": "Outflows > Expected",
            "trigger_condition": "month_out_total > expected_monthly_out × 1.2",
            "score_impact": "20",
            "tags": "EXPECTED_BREACH_OUT",
            "outcome": "Escalate",
            "description": "Monthly outflows exceed declared KYC expectations.",
        },
        {
            "category": "KYC Profile Breach",
            "rule": "Inflows > Expected",
            "trigger_condition": "month_in_total > expected_monthly_in × 1.2",
            "score_impact": "15",
            "tags": "EXPECTED_BREACH_IN",
            "outcome": "Review",
            "description": "Monthly inflows exceed declared KYC expectations.",
        },
        {
            "category": "Severity Mapping",
            "rule": "Score → Severity",
            "trigger_condition": "prohibited OR score≥90→Critical; 70–89→High; 50–69→Medium; 30–49→Low; else Info",
            "score_impact": "—",
            "tags": "—",
            "outcome": "Severity assignment",
            "description": "Maps composite score to severity band for alerting.",
        },
    ]

from datetime import date, timedelta

def _period_bounds(period: str):
    """
    Returns (start_date_str, end_date_str) or (None, None) for 'all'.
    Supported:
      all | 3m | 6m | 12m | ytd | month:YYYY-MM
    """
    today = date.today()
    if not period or period == "all":
        return None, None
    if period in {"3m","6m","12m"}:
        months = int(period[:-1])
        y = today.year
        m = today.month - months + 1
        while m <= 0:
            m += 12; y -= 1
        start = date(y, m, 1)
        end = today
        return start.isoformat(), end.isoformat()
    if period == "ytd":
        start = date(today.year, 1, 1)
        return start.isoformat(), today.isoformat()
    if period.startswith("month:"):
        ym = period.split(":",1)[1]
        y, m = map(int, ym.split("-"))
        start = date(y, m, 1)
        if m == 12:
            end = date(y+1, 1, 1) - timedelta(days=1)
        else:
            end = date(y, m+1, 1) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    return None, None

# ---------- Simple scoring / rules ----------
def get_country_map():
    db = get_db()
    rows = db.execute("SELECT iso2, risk_level, score, prohibited FROM ref_country_risk").fetchall()
    return {r["iso2"]: dict(r) for r in rows}

def get_expected_map():
    db = get_db()
    rows = db.execute("SELECT * FROM kyc_profile").fetchall()
    return {r["customer_id"]: dict(r) for r in rows}

def upsert_country(iso2, level, score, prohibited):
    db = get_db()
    db.execute(
        """INSERT INTO ref_country_risk(iso2, risk_level, score, prohibited)
           VALUES(?,?,?,?)
           ON CONFLICT(iso2) DO UPDATE SET risk_level=excluded.risk_level,
                                          score=excluded.score,
                                          prohibited=excluded.prohibited,
                                          updated_at=CURRENT_TIMESTAMP
        """,
        (iso2, level, score, prohibited)
    )
    db.commit()

def upsert_sort_codes(rows):
    db = get_db()
    for r in rows:
        db.execute(
            """INSERT INTO ref_sort_codes(sort_code, bank_name, branch, schemes, valid_from, valid_to)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(sort_code) DO UPDATE SET bank_name=excluded.bank_name,
                                                   branch=excluded.branch,
                                                   schemes=excluded.schemes,
                                                   valid_from=excluded.valid_from,
                                                   valid_to=excluded.valid_to
            """,
            (r.get("sort_code"), r.get("bank_name"), r.get("branch"),
             r.get("schemes"), r.get("valid_from"), r.get("valid_to"))
        )
    db.commit()

def load_csv_to_table(path, table):
    import pandas as pd
    df = pd.read_csv(path)
    db = get_db()
    count = 0
    if table == "ref_country_risk":
        for _,r in df.iterrows():
            upsert_country(str(r["iso2"]).strip(), str(r["risk_level"]).strip(),
                           int(r["score"]), int(r.get("prohibited",0)))
            count += 1
    elif table == "ref_sort_codes":
        recs = df.to_dict(orient="records")
        upsert_sort_codes(recs)
        count = len(recs)
    elif table == "kyc_profile":
        for _,r in df.iterrows():
            db.execute(
                """INSERT INTO kyc_profile(customer_id, expected_monthly_in, expected_monthly_out)
                   VALUES(?,?,?)
                   ON CONFLICT(customer_id) DO UPDATE SET expected_monthly_in=excluded.expected_monthly_in,
                                                         expected_monthly_out=excluded.expected_monthly_out,
                                                         updated_at=CURRENT_TIMESTAMP
                """,
                (str(r["customer_id"]), float(r["expected_monthly_in"]), float(r["expected_monthly_out"]))
            )
            count += 1
        db.commit()
    elif table == "customer_cash_limits":
        for _,r in df.iterrows():
            upsert_cash_limits(str(r["customer_id"]), float(r["daily_limit"]),
                               float(r["weekly_limit"]), float(r["monthly_limit"]))
            count += 1
    else:
        raise ValueError("Unsupported table for CSV load")
    return count

def ingest_transactions_csv(fobj):
    import pandas as pd
    from datetime import datetime, timedelta, date

    # --- helpers -------------------------------------------------------------
    def _excel_serial_to_date(n):
        # Excel's day 1 = 1899-12-31; but with the 1900-leap bug, pandas/Excel often use 1899-12-30
        # We’ll use 1899-12-30 which matches most CSV exports.
        origin = date(1899, 12, 30)
        try:
            n = int(float(n))
            if n <= 0:
                return None
            return origin + timedelta(days=n)
        except Exception:
            return None

    COMMON_FORMATS = [
        "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y",
        "%d-%m-%Y", "%Y/%m/%d",
    ]

    def _coerce_date(val):
        if val is None:
            return None
        s = str(val).strip()
        if s == "" or s.lower() in ("nan", "none", "null"):
            return None

        # 1) numeric → Excel serial
        try:
            # accept integers/floats or numeric-looking strings
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

        # 3) last resort: pandas to_datetime with dayfirst True then False
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

    # --- load & validate columns --------------------------------------------
    df = pd.read_csv(fobj)

    needed = {
        "id","txn_date","customer_id","direction","amount","currency","base_amount",
        "country_iso2","payer_sort_code","payee_sort_code","channel","narrative"
    }
    missing = needed - set(map(str, df.columns))
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    # --- txn_date robust parsing (no warnings, no mass failure) -------------
    df["txn_date"] = df["txn_date"].apply(_coerce_date)
    bad_dates = df["txn_date"].isna().sum()
    if bad_dates:
        # Drop rows with unparseable txn_date; we’ll report how many were skipped
        df = df[df["txn_date"].notna()]

    # --- normalize text-ish fields ------------------------------------------
    df["direction"] = df["direction"].astype(str).str.lower().str.strip()
    df["currency"]  = df.get("currency", "GBP").fillna("GBP").astype(str).str.strip()

    # Normalize optional text fields (empty → None)
    for col in ["country_iso2","payer_sort_code","payee_sort_code","channel","narrative"]:
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
    df["amount"]      = pd.to_numeric(df["amount"], errors="coerce")
    df["base_amount"] = pd.to_numeric(df["base_amount"], errors="coerce")

    mask_amt_na  = df["amount"].isna() & df["base_amount"].notna()
    mask_base_na = df["base_amount"].isna() & df["amount"].notna()
    df.loc[mask_amt_na,  "amount"]      = df.loc[mask_amt_na,  "base_amount"]
    df.loc[mask_base_na, "base_amount"] = df.loc[mask_base_na, "amount"]

    df["amount"]      = df["amount"].fillna(0.0)
    df["base_amount"] = df["base_amount"].fillna(0.0)

    # --- insert --------------------------------------------------------------
    recs = df.to_dict(orient="records")
    db = get_db()
    n_inserted = 0
    for r in recs:
        db.execute(
            """INSERT OR REPLACE INTO transactions
               (id, txn_date, customer_id, direction, amount, currency, base_amount, country_iso2,
                payer_sort_code, payee_sort_code, channel, narrative)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(r["id"]),
                str(r["txn_date"]),                 # now a real date
                str(r["customer_id"]),
                str(r["direction"]),
                float(r["amount"]),                 # not null
                str(r.get("currency","GBP")),
                float(r["base_amount"]),            # not null
                (str(r["country_iso2"]) if r.get("country_iso2") else None),
                (str(r["payer_sort_code"]) if r.get("payer_sort_code") else None),
                (str(r["payee_sort_code"]) if r.get("payee_sort_code") else None),
                (str(r["channel"]) if r.get("channel") else None),
                (str(r["narrative"]) if r.get("narrative") else None),
            )
        )
        n_inserted += 1

    db.commit()
    score_new_transactions()

    # Return count; the UI already flashes “Loaded N transactions”
    # If you want to surface skipped rows, you can also flash here, but
    # we’ll just print to console to avoid changing routes:
    if bad_dates:
        print(f"[ingest_transactions_csv] Skipped {bad_dates} row(s) with invalid txn_date.")

    return n_inserted

# ---------- Built-in rules (hard-coded) with configurable parameters ----------
def builtin_rules_catalog():
    return [
        {
            "key": "cash_daily_breach",
            "category": "Cash Activity",
            "rule": "Cash Daily Limit Breach",
            "trigger": "day_cash_total > cfg_cash_daily_limit (global)",
            "impact": "+20",
            "tags": "CASH_DAILY_BREACH",
            "outcome": "Escalate",
            "description": "Alert when daily cash deposits/withdrawals exceed the global cash limit.",
            "params": [ {"key":"cfg_cash_daily_limit","label":"Global cash daily limit","prefix":"£"} ],
        },
        {
            "key": "high_risk_corridor",
            "category": "Jurisdiction Risk",
            "rule": "High-Risk Corridor",
            "trigger": "in_high_risk(txn.country_iso2) AND txn.base_amount ≥ cfg_high_risk_min_amount",
            "impact": "risk table score",
            "tags": "HIGH_RISK_COUNTRY",
            "outcome": "Escalate",
            "description": "Increase score for transactions to high-risk or high-risk third countries if above the minimum amount.",
            "params": [ {"key":"cfg_high_risk_min_amount","label":"Min amount","prefix":"£"} ],
        },
        {
            "key": "median_outlier",
            "category": "Behavioural Deviation",
            "rule": "Outlier vs Median",
            "trigger": "txn.base_amount > (cfg_median_multiplier × median_amount)",
            "impact": "+25",
            "tags": "HISTORICAL_DEVIATION",
            "outcome": "Escalate",
            "description": "Flag unusually large transactions compared to customer’s typical behaviour.",
            "params": [ {"key":"cfg_median_multiplier","label":"Multiplier","suffix":"×"} ],
            "requires": "Historical median available",
        },
        {
            "key": "nlp_risky_terms",
            "category": "Narrative Risk",
            "rule": "Risky Terms",
            "trigger": "narrative contains any enabled keyword",
            "impact": "+10",
            "tags": "NLP_RISK",
            "outcome": "Review",
            "description": "Flag transactions with sensitive wording in the narrative.",
            "params": [ {"key":"cfg_risky_terms2","label":"Keywords","kind":"list"} ],
        },
        {
            "key": "expected_out",
            "category": "KYC Profile Breach",
            "rule": "Outflows > Expected",
            "trigger": "month_out_total > (cfg_expected_out_factor × expected_monthly_out)",
            "impact": "+20",
            "tags": "EXPECTED_BREACH_OUT",
            "outcome": "Escalate",
            "description": "Monthly outflows exceed declared KYC expectations.",
            "params": [ {"key":"cfg_expected_out_factor","label":"Multiplier","suffix":"×"} ],
            "requires": "KYC expected_monthly_out set",
        },
        {
            "key": "expected_in",
            "category": "KYC Profile Breach",
            "rule": "Inflows > Expected",
            "trigger": "month_in_total > (cfg_expected_in_factor × expected_monthly_in)",
            "impact": "+15",
            "tags": "EXPECTED_BREACH_IN",
            "outcome": "Review",
            "description": "Monthly inflows exceed declared KYC expectations.",
            "params": [ {"key":"cfg_expected_in_factor","label":"Multiplier","suffix":"×"} ],
            "requires": "KYC expected_monthly_in set",
        },
        {
            "key": "cash_daily_breach",
            "category": "Cash Activity",
            "rule": "Cash Daily Limit Breach",
            "trigger": "day_cash_total > per-customer daily_limit",
            "impact": "+20",
            "tags": "CASH_DAILY_BREACH",
            "outcome": "Escalate",
            "description": "Alert when daily cash deposits/withdrawals exceed the set customer limit.",
            "params": [],
            "requires": "Customer cash daily_limit set (optional)",
        },
        {
            "key": "severity_mapping",
            "category": "Severity Mapping",
            "rule": "Score → Severity",
            "trigger": "≥ cfg_sev_critical → Critical; ≥ cfg_sev_high → High; ≥ cfg_sev_medium → Medium; ≥ cfg_sev_low → Low; else Info",
            "impact": "—",
            "tags": "—",
            "outcome": "Severity assignment",
            "description": "Maps composite score to severity band for alerting.",
            "params": [
                {"key":"cfg_sev_critical","label":"Critical ≥"},
                {"key":"cfg_sev_high","label":"High ≥"},
                {"key":"cfg_sev_medium","label":"Medium ≥"},
                {"key":"cfg_sev_low","label":"Low ≥"},
            ],
        },
    ]

def ensure_ai_tables():
    """Create/patch AI tables (adds 'sources' column to ai_answers; rationale columns to ai_cases)."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS ai_cases (
          id INTEGER PRIMARY KEY,
          customer_id TEXT NOT NULL,
          period_from TEXT,
          period_to TEXT,
          assessment_risk TEXT,
          assessment_score INTEGER,
          assessment_summary TEXT,
          rationale_text TEXT,                -- NEW: persisted rationale
          rationale_generated_at TEXT,        -- NEW: when rationale was generated
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS ai_answers (
          id INTEGER PRIMARY KEY,
          case_id INTEGER NOT NULL,
          tag TEXT,
          question TEXT NOT NULL,
          answer TEXT,
          sources TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(case_id) REFERENCES ai_cases(id) ON DELETE CASCADE
        );
    """)
    # Add columns idempotently
    try:
        db.execute("ALTER TABLE ai_answers ADD COLUMN sources TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE ai_cases ADD COLUMN rationale_text TEXT;")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE ai_cases ADD COLUMN rationale_generated_at TEXT;")
    except sqlite3.OperationalError:
        pass
    db.commit()

def fetch_customer_alerts_with_tags(customer_id, dfrom=None, dto=None):
    """
    Rows shaped for AI: one row per (alert, tag).
    {alert_id, txn_id, txn_date, severity, score, tag}
    """
    db = get_db()
    wh, params = ["a.customer_id = ?"], [customer_id]
    if dfrom: wh.append("t.txn_date >= ?"); params.append(dfrom)
    if dto:   wh.append("t.txn_date <= ?"); params.append(dto)

    rows = db.execute(f"""
        SELECT a.id AS alert_id, a.txn_id, t.txn_date, a.severity, a.score, a.rule_tags
        FROM alerts a
        JOIN transactions t ON t.id = a.txn_id
        WHERE {" AND ".join(wh)}
        ORDER BY CASE a.severity
                   WHEN 'CRITICAL' THEN 1
                   WHEN 'HIGH' THEN 2
                   WHEN 'MEDIUM' THEN 3
                   WHEN 'LOW' THEN 4
                   ELSE 5
                 END, a.score DESC, t.txn_date DESC
    """, params).fetchall()

    out = []
    for r in rows:
        try:
            tags = json.loads(r["rule_tags"] or "[]")
        except Exception:
            tags = []
        for tag in tags:
            out.append({
                "alert_id": r["alert_id"],
                "txn_id": r["txn_id"],
                "txn_date": r["txn_date"],
                "severity": r["severity"],
                "score": r["score"],
                "tag": tag
            })
    return out

def ensure_default_parameters():
    """
    Seed all configurable parameters with sensible defaults (idempotent).
    Also migrates old cfg_risky_terms -> cfg_risky_terms2 (objects with enabled flag).
    """
    # Core thresholds / factors
    defaults = {
        "cfg_high_risk_min_amount": 0.0,     # £ threshold for high-risk corridor rule
        "cfg_median_multiplier": 3.0,        # × median for outlier rule
        "cfg_expected_out_factor": 1.2,      # × expected monthly outflows
        "cfg_expected_in_factor": 1.2,       # × expected monthly inflows
        "cfg_cash_daily_limit": 0.0,

        # Severity mapping thresholds
        "cfg_sev_critical": 90,
        "cfg_sev_high": 70,
        "cfg_sev_medium": 50,
        "cfg_sev_low": 30,

        # AI (LLM) integration toggles
        "cfg_ai_use_llm": False,             # off by default (local/heuristic only)
        "cfg_ai_model": "gpt-4o-mini",

        # Rule enable/disable toggles (all on by default)
        "cfg_rule_enabled_prohibited_country": True,
        "cfg_rule_enabled_high_risk_corridor": True,
        "cfg_rule_enabled_median_outlier": True,
        "cfg_rule_enabled_nlp_risky_terms": True,
        "cfg_rule_enabled_expected_out": True,
        "cfg_rule_enabled_expected_in": True,
        "cfg_rule_enabled_cash_daily_breach": True,
        "cfg_rule_enabled_severity_mapping": True,
    }

    # Write any missing defaults
    for k, v in defaults.items():
        if cfg_get(k, None) is None:
            cfg_set(k, v)

    # Legacy keyword list -> migrate to object list with enabled flags
    if cfg_get("cfg_risky_terms2", None) is None:
        base = cfg_get("cfg_risky_terms", None, list)
        if not base:
            base = ["consultancy", "gift", "usdt", "otc", "crypto", "cash", "shell", "hawala"]
            cfg_set("cfg_risky_terms", base)
        terms = [{"term": t, "enabled": True} for t in base]
        cfg_set("cfg_risky_terms2", terms)

def risky_terms_enabled():
    items = cfg_get("cfg_risky_terms2", [], list)
    return [i["term"] for i in items if isinstance(i, dict) and i.get("enabled")]

def score_new_transactions():
    import statistics
    db = get_db()
    country_map = get_country_map()
    expected_map = get_expected_map()

    # Params
    high_risk_min_amount = cfg_get("cfg_high_risk_min_amount", 0.0, float)
    median_mult = cfg_get("cfg_median_multiplier", 3.0, float)
    exp_out_factor = cfg_get("cfg_expected_out_factor", 1.2, float)
    exp_in_factor  = cfg_get("cfg_expected_in_factor", 1.2, float)
    enabled_terms  = risky_terms_enabled()  # NEW: only enabled
    sev_crit = cfg_get("cfg_sev_critical", 90, int)
    sev_high = cfg_get("cfg_sev_high", 70, int)
    sev_med  = cfg_get("cfg_sev_medium", 50, int)
    sev_low  = cfg_get("cfg_sev_low", 30, int)

    # Toggles
    on = {
        "prohibited_country": cfg_get_bool("cfg_rule_enabled_prohibited_country", True),
        "high_risk_corridor": cfg_get_bool("cfg_rule_enabled_high_risk_corridor", True),
        "median_outlier": cfg_get_bool("cfg_rule_enabled_median_outlier", True),
        "nlp_risky_terms": cfg_get_bool("cfg_rule_enabled_nlp_risky_terms", True),
        "expected_out": cfg_get_bool("cfg_rule_enabled_expected_out", True),
        "expected_in": cfg_get_bool("cfg_rule_enabled_expected_in", True),
        "cash_daily_breach": cfg_get_bool("cfg_rule_enabled_cash_daily_breach", True),
        "severity_mapping": cfg_get_bool("cfg_rule_enabled_severity_mapping", True),
    }

    # Medians
    cur = db.execute("SELECT customer_id, direction, base_amount FROM transactions")
    per_key = defaultdict(list)
    for r in cur.fetchall():
        per_key[(r["customer_id"], r["direction"])].append(r["base_amount"])
    cust_medians = {k: statistics.median(v) for k,v in per_key.items() if v}

    # Worklist
    txns = db.execute("""
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
        month_end = ((d.replace(day=28)+timedelta(days=4)).replace(day=1) - timedelta(days=1)).isoformat()

        month_in_total = float(db.execute(
            "SELECT SUM(base_amount) s FROM transactions WHERE customer_id=? AND direction='in' AND txn_date BETWEEN ? AND ?",
            (t["customer_id"], month_start, month_end)
        ).fetchone()["s"] or 0)

        month_out_total = float(db.execute(
            "SELECT SUM(base_amount) s FROM transactions WHERE customer_id=? AND direction='out' AND txn_date BETWEEN ? AND ?",
            (t["customer_id"], month_start, month_end)
        ).fetchone()["s"] or 0)

        exp = expected_map.get(t["customer_id"], {"expected_monthly_in":0, "expected_monthly_out":0})
        expected_monthly_in  = float(exp.get("expected_monthly_in") or 0)
        expected_monthly_out = float(exp.get("expected_monthly_out") or 0)
        med = float(cust_medians.get((t["customer_id"], t["direction"]), 0.0))

        # Prohibited
        c = country_map.get(t["country_iso2"] or "")
        if on["prohibited_country"] and c and c["prohibited"]:
            reasons.append(f"Prohibited country {t['country_iso2']}")
            tags.append("PROHIBITED_COUNTRY")
            score += 100

        # High-risk
        elif on["high_risk_corridor"] and c and (c["risk_level"] in ("HIGH_3RD","HIGH")) and float(t["base_amount"]) >= high_risk_min_amount:
            reasons.append(f"High-risk corridor {t['country_iso2']} ({c['risk_level']})")
            tags.append("HIGH_RISK_COUNTRY")
            score += int(c["score"])

        # Cash daily breach (GLOBAL)
        cash_daily_limit = float(cfg_get("cfg_cash_daily_limit", 0.0, float))
        if on["cash_daily_breach"] and cash_daily_limit > 0 and (chan == "cash" or "cash" in narrative.lower()):
            d_total = float(db.execute(
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
        if on["expected_out"] and t["direction"]=="out" and expected_monthly_out>0:
            if month_out_total > expected_monthly_out * float(exp_out_factor):
                reasons.append(f"Outflows exceed expected (actual £{month_out_total:.2f})")
                tags.append("EXPECTED_BREACH_OUT")
                score += 20

        if on["expected_in"] and t["direction"]=="in" and expected_monthly_in>0:
            if month_in_total > expected_monthly_in * float(exp_in_factor):
                reasons.append(f"Inflows exceed expected (actual £{month_in_total:.2f})")
                tags.append("EXPECTED_BREACH_IN")
                score += 15

        # Severity mapping (kept even if toggle is off; but we respect it for transparency)
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
            db.execute(
                """INSERT INTO alerts(txn_id, customer_id, score, severity, reasons, rule_tags, config_version)
                   VALUES(?,?,?,?,?,?, (SELECT MAX(id) FROM config_versions))""",
                (t["id"], t["customer_id"], int(min(score,100)), severity,
                 json.dumps(reasons), json.dumps(list(dict.fromkeys(tags))))
            )
    db.commit()

# ---------- Routes ----------
@app.route("/")
def dashboard():
    db = get_db()
    customer_id = request.args.get("customer_id", "").strip()

    # If no customer selected, render an empty state (no data shown)
    if not customer_id:
        months = []
        cur = date.today().replace(day=1)
        for _ in range(18):
            months.append(cur.strftime("%Y-%m"))
            if cur.month == 1:
                cur = cur.replace(year=cur.year-1, month=12)
            else:
                cur = cur.replace(month=cur.month-1)

        return render_template(
            "dashboard.html",
            kpis={"total_tx": 0, "total_alerts": 0, "alert_rate": 0, "critical": 0},
            tiles={
                "total_in": 0.0, "total_out": 0.0,
                "cash_in": 0.0, "cash_out": 0.0,
                "high_risk_volume": 0, "high_risk_total": 0.0
            },
            labels=[], values=[],
            top_countries=[],
            trend_labels=[], trend_in=[], trend_out=[],
            months=months,
            selected_period="12m",
            filter_meta=None,
            metrics={  # reviewer tiles – all zeros in empty state
                "avg_cash_deposits": 0.0,
                "avg_cash_withdrawals": 0.0,
                "avg_in": 0.0,
                "avg_out": 0.0,
                "max_in": 0.0,
                "max_out": 0.0,
                "overseas_value": 0.0,
                "overseas_pct": 0.0,
                "highrisk_value": 0.0,
                "highrisk_pct": 0.0,
            }
        )

    # --- Normal (filtered) dashboard below ---
    period = request.args.get("period", "12m")
    start, end = _period_bounds(period)

    # Predicates for transactions and alerts
    tx_where, tx_params = ["t.customer_id = ?"], [customer_id]
    a_where, a_params = ["a.customer_id = ?"], [customer_id]

    if start and end:
        tx_where.append("t.txn_date BETWEEN ? AND ?"); tx_params += [start, end]
        a_where.append("a.created_at BETWEEN ? AND ?"); a_params += [start + " 00:00:00", end + " 23:59:59"]

    tx_pred = "WHERE " + " AND ".join(tx_where)
    a_pred  = "WHERE " + " AND ".join(a_where)

    # KPIs
    total_tx = db.execute(f"SELECT COUNT(*) c FROM transactions t {tx_pred}", tx_params).fetchone()["c"]
    total_alerts = db.execute(f"SELECT COUNT(*) c FROM alerts a {a_pred}", a_params).fetchone()["c"]
    critical = db.execute(f"SELECT COUNT(*) c FROM alerts a {a_pred} AND a.severity='CRITICAL'", a_params).fetchone()["c"]

    kpis = {
        "total_tx": total_tx,
        "total_alerts": total_alerts,
        "alert_rate": (total_alerts / total_tx) if total_tx else 0,
        "critical": critical,
    }

    # Tiles: totals, cash in/out
    sums = db.execute(f"""
      SELECT
        SUM(CASE WHEN t.direction='in'  THEN t.base_amount ELSE 0 END)  AS total_in,
        SUM(CASE WHEN t.direction='out' THEN t.base_amount ELSE 0 END)  AS total_out
      FROM transactions t {tx_pred}
    """, tx_params).fetchone()
    total_in  = float(sums["total_in"]  or 0)
    total_out = float(sums["total_out"] or 0)
    total_value = total_in + total_out

    cash = db.execute(f"""
      SELECT
        SUM(CASE WHEN t.direction='in'
                   AND lower(IFNULL(t.channel,''))='cash'
                 THEN t.base_amount ELSE 0 END) AS cash_in,
        SUM(CASE WHEN t.direction='out'
                   AND lower(IFNULL(t.channel,''))='cash'
                 THEN t.base_amount ELSE 0 END) AS cash_out
      FROM transactions t {tx_pred}
    """, tx_params).fetchone()
    cash_in  = float(cash["cash_in"]  or 0)
    cash_out = float(cash["cash_out"] or 0)

    # High/High-3rd/Prohibited corridors — count AND total £
    hr = db.execute(f"""
      SELECT COUNT(*) AS cnt, SUM(t.base_amount) AS total
      FROM transactions t
      JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2, '')
      {tx_pred + (' AND ' if tx_pred else 'WHERE ')} r.risk_level IN ('HIGH','HIGH_3RD','PROHIBITED')
    """, tx_params).fetchone()
    high_risk_volume = int(hr["cnt"] or 0)
    high_risk_total  = float(hr["total"] or 0)

    tiles = {
        "total_in": total_in,
        "total_out": total_out,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "high_risk_volume": high_risk_volume,  # (you can ignore in template if you don't want to show the count)
        "high_risk_total": high_risk_total,
    }

    # Alerts over time — group by TRANSACTION DATE (t.txn_date)
    if start and end:
        aot_sql = """
          SELECT strftime('%Y-%m-%d', t.txn_date) d, COUNT(*) c
          FROM alerts a
          JOIN transactions t ON t.id = a.txn_id
          WHERE t.customer_id = ? AND t.txn_date BETWEEN ? AND ?
          GROUP BY d ORDER BY d
        """
        aot_params = [customer_id, start, end]
    else:
        aot_sql = """
          SELECT strftime('%Y-%m-%d', t.txn_date) d, COUNT(*) c
          FROM alerts a
          JOIN transactions t ON t.id = a.txn_id
          WHERE t.customer_id = ?
          GROUP BY d ORDER BY d
        """
        aot_params = [customer_id]
    rows = db.execute(aot_sql, aot_params).fetchall()
    labels = [r["d"] for r in rows]
    values = [int(r["c"]) for r in rows]

    # Top countries (alerts) — show full country names
    tc_rows = db.execute(f"""
      SELECT t.country_iso2, COUNT(*) cnt
      FROM alerts a
      JOIN transactions t ON t.id = a.txn_id
      {a_pred}
      GROUP BY t.country_iso2
      ORDER BY cnt DESC
      LIMIT 10
    """, a_params).fetchall()
    top_countries = [
        {"name": country_full_name(r["country_iso2"]), "cnt": int(r["cnt"] or 0)}
        for r in tc_rows
    ]

    # Monthly trend of money in/out
    trend_rows = db.execute(f"""
      SELECT strftime('%Y-%m', t.txn_date) ym,
             SUM(CASE WHEN t.direction='in'  THEN t.base_amount ELSE 0 END) AS in_sum,
             SUM(CASE WHEN t.direction='out' THEN t.base_amount ELSE 0 END) AS out_sum
      FROM transactions t {tx_pred}
      GROUP BY ym
      ORDER BY ym
    """, tx_params).fetchall()
    trend_labels = [r["ym"] for r in trend_rows]
    trend_in  = [float(r["in_sum"]  or 0) for r in trend_rows]
    trend_out = [float(r["out_sum"] or 0) for r in trend_rows]

    # Reviewer metrics (averages, highs, overseas, high-risk % etc.)
    m = db.execute(f"""
      SELECT
        AVG(CASE WHEN t.direction='in'  AND lower(IFNULL(t.channel,''))='cash' THEN t.base_amount END) AS avg_cash_in,
        AVG(CASE WHEN t.direction='out' AND lower(IFNULL(t.channel,''))='cash' THEN t.base_amount END) AS avg_cash_out,
        AVG(CASE WHEN t.direction='in'  THEN t.base_amount END) AS avg_in,
        AVG(CASE WHEN t.direction='out' THEN t.base_amount END) AS avg_out,
        MAX(CASE WHEN t.direction='in'  THEN t.base_amount END) AS max_in,
        MAX(CASE WHEN t.direction='out' THEN t.base_amount END) AS max_out,
        SUM(CASE WHEN IFNULL(t.country_iso2,'')<>'' AND UPPER(t.country_iso2)<>'GB' THEN t.base_amount ELSE 0 END) AS overseas_value,
        SUM(t.base_amount) AS total_value
      FROM transactions t {tx_pred}
    """, tx_params).fetchone()

    avg_cash_deposits     = float(m["avg_cash_in"]  or 0.0)
    avg_cash_withdrawals  = float(m["avg_cash_out"] or 0.0)
    avg_in                = float(m["avg_in"]       or 0.0)
    avg_out               = float(m["avg_out"]      or 0.0)
    max_in                = float(m["max_in"]       or 0.0)
    max_out               = float(m["max_out"]      or 0.0)
    overseas_value        = float(m["overseas_value"] or 0.0)
    total_val_from_query  = float(m["total_value"]  or 0.0)
    # Use the earlier computed total_value if present; else fall back
    denom_total = total_value if total_value > 0 else total_val_from_query
    overseas_pct = (overseas_value / denom_total * 100.0) if denom_total > 0 else 0.0

    hr_val_row = db.execute(f"""
      SELECT SUM(t.base_amount) AS v
      FROM transactions t
      JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2, '')
      {tx_pred + (' AND ' if tx_pred else 'WHERE ')} r.risk_level IN ('HIGH','HIGH_3RD','PROHIBITED')
    """, tx_params).fetchone()
    highrisk_value = float(hr_val_row["v"] or 0.0)
    highrisk_pct   = (highrisk_value / denom_total * 100.0) if denom_total > 0 else 0.0

    metrics = {
        "avg_cash_deposits": avg_cash_deposits,
        "avg_cash_withdrawals": avg_cash_withdrawals,
        "avg_in": avg_in,
        "avg_out": avg_out,
        "max_in": max_in,
        "max_out": max_out,
        "overseas_value": overseas_value,
        "overseas_pct": overseas_pct,
        "highrisk_value": highrisk_value,
        "highrisk_pct": highrisk_pct,
    }

    # Month options (last 18 months)
    months = []
    cur = date.today().replace(day=1)
    for _ in range(18):
        months.append(cur.strftime("%Y-%m"))
        if cur.month == 1:
            cur = cur.replace(year=cur.year-1, month=12)
        else:
            cur = cur.replace(month=cur.month-1)

    return render_template(
        "dashboard.html",
        kpis=kpis,
        labels=labels, values=values,
        top_countries=top_countries,
        tiles=tiles,
        trend_labels=trend_labels, trend_in=trend_in, trend_out=trend_out,
        months=months,
        selected_period=period,
        filter_meta={"customer_id": customer_id},
        metrics=metrics,
    )

@app.route("/upload", methods=["GET","POST"])
def upload():
    init_db()
    if request.method == "POST":
        cf, sf, tf = request.files.get("country_file"), request.files.get("sort_file"), request.files.get("tx_file")
        country_count = 0
        sort_count = 0
        tx_count = 0
        
        if cf and cf.filename: 
            country_count = load_csv_to_table(cf, "ref_country_risk")
        if sf and sf.filename: 
            sort_count = load_csv_to_table(sf, "ref_sort_codes")
        if tf and tf.filename: 
            tx_count = ingest_transactions_csv(tf)
        
        # Check if JSON response requested
        if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
            return jsonify({
                "status": "ok",
                "message": f"Loaded {tx_count} transactions, {country_count} countries, {sort_count} sort codes",
                "transactions": tx_count,
                "countries": country_count,
                "sort_codes": sort_count
            })
        
        flash(f"Loaded {tx_count} transactions")
        return redirect(url_for("upload"))
    return render_template("upload.html")

@app.route("/alerts")
def alerts():
    db = get_db()

    # Read filters
    sev  = (request.args.get("severity") or "").strip().upper()
    cust = (request.args.get("customer_id") or "").strip()
    tag  = (request.args.get("tag") or "").strip()  # NEW

    # Base query (severity / customer handled in SQL)
    where, params = [], []
    if sev:
        where.append("a.severity = ?"); params.append(sev)
    if cust:
        where.append("a.customer_id = ?"); params.append(cust)

    sql = f"""
      SELECT a.*, t.country_iso2, t.txn_date
        FROM alerts a
        LEFT JOIN transactions t ON t.id = a.txn_id
       {('WHERE ' + ' AND '.join(where)) if where else ''}
       ORDER BY t.txn_date DESC, a.created_at DESC
       LIMIT 500
    """
    rows = db.execute(sql, params).fetchall()

    # Build tag list (from the SQL-filtered set before applying 'tag')
    tag_set = set()
    for r in rows:
        try:
            for tg in json.loads(r["rule_tags"] or "[]"):
                if tg:
                    tag_set.add(str(tg))
        except Exception:
            pass
    available_tags = sorted(tag_set)

    # Apply tag filter in Python (robust even without SQLite JSON1)
    out = []
    for r in rows:
        d = dict(r)
        try:
            reasons_list = json.loads(d.get("reasons") or "[]")
        except Exception:
            reasons_list = [d.get("reasons")] if d.get("reasons") else []

        try:
            tags_list = json.loads(d.get("rule_tags") or "[]")
        except Exception:
            tags_list = []

        # If a tag is selected, keep only rows that include it
        if tag and tag not in tags_list:
            continue

        # Flatten for table display
        d["reasons"]   = ", ".join(x for x in reasons_list if x)
        d["rule_tags"] = ", ".join(tags_list)
        out.append(d)

    return render_template(
        "alerts.html",
        alerts=out,
        available_tags=available_tags,  # for the dropdown
    )

@app.route("/admin")
def admin():
    db = get_db()
    countries = db.execute("SELECT * FROM ref_country_risk ORDER BY iso2").fetchall()

    # Parameters shown/edited in the UI
    params = {
        "cfg_high_risk_min_amount": float(cfg_get("cfg_high_risk_min_amount", 0.0)),
        "cfg_median_multiplier":    float(cfg_get("cfg_median_multiplier", 3.0)),
        "cfg_expected_out_factor":  float(cfg_get("cfg_expected_out_factor", 1.2)),
        "cfg_expected_in_factor":   float(cfg_get("cfg_expected_in_factor", 1.2)),
        "cfg_sev_critical":         int(cfg_get("cfg_sev_critical", 90)),
        "cfg_sev_high":             int(cfg_get("cfg_sev_high", 70)),
        "cfg_sev_medium":           int(cfg_get("cfg_sev_medium", 50)),
        "cfg_sev_low":              int(cfg_get("cfg_sev_low", 30)),
        "cfg_ai_use_llm":           bool(cfg_get("cfg_ai_use_llm", False)),
        "cfg_ai_model":             str(cfg_get("cfg_ai_model", "gpt-4o-mini")),
        "cfg_risky_terms2":         cfg_get("cfg_risky_terms2", [], list),
        "cfg_cash_daily_limit":     float(cfg_get("cfg_cash_daily_limit", 0.0)),
    }

    # Rule toggles
    toggles = {
        "prohibited_country": bool(cfg_get("cfg_rule_enabled_prohibited_country", True)),
        "high_risk_corridor": bool(cfg_get("cfg_rule_enabled_high_risk_corridor", True)),
        "median_outlier":     bool(cfg_get("cfg_rule_enabled_median_outlier", True)),
        "nlp_risky_terms":    bool(cfg_get("cfg_rule_enabled_nlp_risky_terms", True)),
        "expected_out":       bool(cfg_get("cfg_rule_enabled_expected_out", True)),
        "expected_in":        bool(cfg_get("cfg_rule_enabled_expected_in", True)),
        "cash_daily_breach":  bool(cfg_get("cfg_rule_enabled_cash_daily_breach", True)),
        "severity_mapping":   bool(cfg_get("cfg_rule_enabled_severity_mapping", True)),
    }

    return render_template(
        "admin.html",
        countries=countries,
        params=params,
        toggles=toggles,
        builtin_rules=builtin_rules_catalog(),  # uses your catalog helper
    )

@app.post("/admin/country")
def admin_country():
    iso2 = request.form.get("iso2","").upper().strip()
    level = request.form.get("risk_level","MEDIUM").strip()
    score = int(request.form.get("score","0"))
    prohibited = 1 if request.form.get("prohibited") else 0
    if not iso2: 
        if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
            return jsonify({"status": "error", "message": "ISO2 code required"}), 400
        abort(400)
    upsert_country(iso2, level, score, prohibited)
    
    # Check if JSON response requested
    if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        return jsonify({"status": "ok", "message": f"Country {iso2} saved"})
    
    flash(f"Country {iso2} saved.")
    return redirect(url_for("admin"))

@app.post("/admin/rule-params")
def admin_rule_params():
    """Persist numeric parameters, severity thresholds, and AI toggles."""
    # Numbers / floats
    cfg_set("cfg_high_risk_min_amount", float(request.form.get("cfg_high_risk_min_amount") or 0))
    cfg_set("cfg_median_multiplier",    float(request.form.get("cfg_median_multiplier") or 3.0))
    cfg_set("cfg_expected_out_factor",  float(request.form.get("cfg_expected_out_factor") or 1.2))
    cfg_set("cfg_expected_in_factor",   float(request.form.get("cfg_expected_in_factor") or 1.2))
    cfg_set("cfg_cash_daily_limit",     float(request.form.get("cfg_cash_daily_limit") or 0))

    # Severities
    cfg_set("cfg_sev_critical", int(request.form.get("cfg_sev_critical") or 90))
    cfg_set("cfg_sev_high",     int(request.form.get("cfg_sev_high") or 70))
    cfg_set("cfg_sev_medium",   int(request.form.get("cfg_sev_medium") or 50))
    cfg_set("cfg_sev_low",      int(request.form.get("cfg_sev_low") or 30))

    # AI
    cfg_set("cfg_ai_use_llm", bool(request.form.get("cfg_ai_use_llm")))
    cfg_set("cfg_ai_model", (request.form.get("cfg_ai_model") or "gpt-4o-mini").strip())

    # Check if JSON response requested
    if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        return jsonify({"status": "ok", "message": "Rule parameters saved"})
    
    flash("Rule parameters saved.")
    return redirect(url_for("admin") + "#rule-params")

# --- helper to rewrite questions into natural sentences ---
def _enrich_questions_with_sentences(questions):
    """Take the structured question rows and rewrite into natural language sentences with country names, dates, amounts."""
    enriched = []
    for q in questions:
        if not q.get("sources"):
            enriched.append(q)
            continue

        # Example: "2025-09-11 OUT £577.89 (RU)"
        refs = []
        for s in q["sources"]:
            parts = []
            if s.get("date"): parts.append(s["date"])
            if s.get("direction"): parts.append(s["direction"])
            if s.get("amount"): parts.append(f"£{s['amount']}")
            if s.get("country"): parts.append(s["country_full"])  # assume you already map iso2->full
            if s.get("txn_id"): parts.append(f"Txn {s['txn_id']}")
            refs.append(" ".join(parts))

        # Collapse into a friendly sentence
        joined = "; ".join(refs)
        q["question"] = f"{q['question']} For reference: {joined}"
        enriched.append(q)

    return enriched


def _month_bounds_for(date_str: str):
    d = date.fromisoformat(date_str)
    start = d.replace(day=1)
    # end of month
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()

def _expected_vs_actual_month(customer_id: str, direction: str, any_date: str):
    """Return (expected_x, actual_y, ym_label) for the month containing any_date."""
    db = get_db()
    start, end = _month_bounds_for(any_date)
    # Actual month sum for that direction
    y = float(db.execute(
        "SELECT SUM(base_amount) s FROM transactions "
        "WHERE customer_id=? AND direction=? AND txn_date BETWEEN ? AND ?",
        (customer_id, direction.lower(), start, end)
    ).fetchone()["s"] or 0.0)
    # Expected from KYC profile
    kyc = db.execute(
        "SELECT expected_monthly_in, expected_monthly_out FROM kyc_profile WHERE customer_id=?",
        (customer_id,)
    ).fetchone()
    exp_in  = float(kyc["expected_monthly_in"]  or 0.0) if kyc else 0.0
    exp_out = float(kyc["expected_monthly_out"] or 0.0) if kyc else 0.0
    x = exp_in if direction.lower()=="in" else exp_out
    ym = start[:7]
    return x, y, ym

def _median_for_direction(customer_id: str, direction: str):
    """Return median amount for all txns for this customer+direction (0.0 if none)."""
    import statistics
    rows = get_db().execute(
        "SELECT base_amount FROM transactions WHERE customer_id=? AND direction=?",
        (customer_id, direction.lower())
    ).fetchall()
    vals = [float(r["base_amount"] or 0.0) for r in rows if r["base_amount"] is not None]
    if not vals:
        return 0.0
    try:
        return float(statistics.median(vals))
    except statistics.StatisticsError:
        return 0.0

def _risky_terms_used(narratives: list):
    """Return sorted unique risky terms that appear in the provided narratives."""
    terms = cfg_get("cfg_risky_terms2", [], list)
    needles = [t["term"] for t in terms if isinstance(t, dict) and t.get("enabled")]
    text = " ".join(narratives).lower()
    hits = sorted({w for w in needles if w.lower() in text})
    return hits

def _closing_prompt_for_base_question(base_q: str, tag: str) -> str:
    tag = (tag or "").upper()
    q = (base_q or "").lower()

    if tag == "CASH_DAILY_BREACH":
        return "Please explain the reason for the recent level of cash activity on your account."

    if tag == "HISTORICAL_DEVIATION":
        return "We’ve seen a spike compared to your typical activity. What is the reason, and should we expect similar amounts going forward?"

    if tag == "EXPECTED_BREACH_OUT":
        return "Your outgoings are higher than you previously told us to expect. What is the reason, and should we expect this level to continue?"

    if tag == "EXPECTED_BREACH_IN":
        return "Your incomings are higher than you previously told us to expect. What is the reason, and should we expect this level to continue?"

    if tag == "NLP_RISK" or "narrative" in q or "documentation" in q:
        return "Please clarify the purpose of the payment(s) and your relationship with the payer/payee, and share any supporting documents (e.g., invoices/contracts)."

    if "relationship" in q or "party you made the payment to" in q:
        return "Please tell us who the payment(s) were to and your relationship with the recipient(s)."

    if tag in ("PROHIBITED_COUNTRY", "HIGH_RISK_COUNTRY"):
        return "Please confirm the reasons for these transactions."

    return "Please provide further details."

def _question_sentence_for_row(row: dict) -> str:
    """
    Tag-aware, data-enriched outreach sentence builder.
    """
    tag = (row.get("tag") or "").upper()
    details = row.get("source_details") or []

    # If nothing to enrich, ensure we end with a question mark.
    if not details:
        base = (row.get("question") or "").strip()
        return base if base.endswith("?") else (base + "?") if base else ""

    # Normalise details we need
    norm = []
    for s in details:
        norm.append({
            "date": s["txn_date"],
            "amount": float(s.get("base_amount") or 0.0),
            "direction": "OUT" if (s.get("direction") or "").lower() == "out" else "IN",
            "country": country_full_name(s.get("country_iso2") or ""),
            "customer_id": s.get("customer_id"),
            "channel": (s.get("channel") or "").lower(),
            "narrative": s.get("narrative") or "",
        })
    norm.sort(key=lambda x: x["date"])

    def _fmt_date(d: str) -> str:
        dt = datetime.strptime(d, "%Y-%m-%d")
        day = dt.day
        suf = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{day}{suf} {dt.strftime('%B %Y')}"

    def _list_amount_dates(items):
        return ", ".join(f"£{i['amount']:,.2f} on {_fmt_date(i['date'])}" for i in items)

    closing = _closing_prompt_for_base_question(row.get("question"), tag)

    # ---- CASH_DAILY_BREACH (ignore country; focus on cash usage) ----
    if tag == "CASH_DAILY_BREACH":
        inc_cash = [i for i in norm if i["direction"] == "IN"  and i["channel"] == "cash"]
        out_cash = [i for i in norm if i["direction"] == "OUT" and i["channel"] == "cash"]
        # Fallback: if channel not present on source txns, treat all sources as cash (conservative)
        if not inc_cash and not out_cash:
            inc_cash = [i for i in norm if i["direction"] == "IN"]
            out_cash = [i for i in norm if i["direction"] == "OUT"]
        bits = []
        if inc_cash:
            bits.append(f"{len(inc_cash)} cash deposit{'s' if len(inc_cash)!=1 else ''} valued at {_list_amount_dates(inc_cash)}")
        if out_cash:
            bits.append(f"{len(out_cash)} cash withdrawal{'s' if len(out_cash)!=1 else ''} valued at {_list_amount_dates(out_cash)}")
        front = "Our records show " + " and ".join(bits) + "."
        s = f"{front} {closing}"
        return s if s.endswith("?") else s.rstrip('.') + "?"

    # ---- HISTORICAL_DEVIATION (spike vs median) ----
    if tag == "HISTORICAL_DEVIATION":
        # Use direction of the largest txn among sources
        spike = max(norm, key=lambda x: x["amount"])
        med = _median_for_direction(spike["customer_id"], spike["direction"])
        ratio = (spike["amount"] / med) if med > 0 else None
        ratio_txt = f" (≈×{ratio:.1f} your typical)" if ratio and ratio >= 1.2 else ""
        front = (f"Our records show a higher-than-usual transaction of £{spike['amount']:,.2f} "
                 f"on {_fmt_date(spike['date'])}{ratio_txt}.")
        s = f"{front} {closing}"
        return s if s.endswith("?") else s.rstrip('.') + "?"

    # ---- EXPECTED_BREACH_IN / OUT (expected X vs actual Y for that month) ----
    if tag in ("EXPECTED_BREACH_IN", "EXPECTED_BREACH_OUT"):
        # Pick the most recent source txn to anchor the month
        anchor = norm[-1]
        direction = anchor["direction"].lower()  # 'in' or 'out'
        x, y, ym = _expected_vs_actual_month(anchor["customer_id"], direction, anchor["date"])
        dir_word = "incomings" if direction == "in" else "outgoings"
        front = (f"Our records show your {dir_word} in {ym} totalled £{y:,.2f}, "
                 f"compared to your stated expectation of £{x:,.2f}.")
        s = f"{front} {closing}"
        return s if s.endswith("?") else s.rstrip('.') + "?"

    # ---- NLP_RISK (surface risky terms; ask for purpose + relationship) ----
    if tag == "NLP_RISK":
        hits = _risky_terms_used([i["narrative"] for i in norm if i["narrative"]])
        hit_txt = f" (keywords noted: {', '.join(hits)})" if hits else ""
        # Summarise sent/received without country to keep neutral
        inc = [i for i in norm if i["direction"] == "IN"]
        out = [i for i in norm if i["direction"] == "OUT"]
        bits = []
        if inc: bits.append(f"{len(inc)} transaction{'s' if len(inc)!=1 else ''} were received valued at {_list_amount_dates(inc)}")
        if out: bits.append(f"{len(out)} transaction{'s' if len(out)!=1 else ''} were sent valued at {_list_amount_dates(out)}")
        front = ("Our records show " + " and ".join(bits) + "." if bits else "We are reviewing recent activity.")
        s = f"{front} We’d like to understand these payments{hit_txt}. {closing}"
        return s if s.endswith("?") else s.rstrip('.') + "?"

    # ---- Jurisdictional (by country, sent/received) ----
    if tag in ("PROHIBITED_COUNTRY", "HIGH_RISK_COUNTRY"):
        by_country = {}
        for i in norm:
            by_country.setdefault(i["country"] or "Unknown country", []).append(i)
        parts = []
        for country, items in sorted(by_country.items(), key=lambda kv: kv[0]):
            inc = [x for x in items if x["direction"] == "IN"]
            out = [x for x in items if x["direction"] == "OUT"]
            segs = []
            if inc:
                segs.append(f"{len(inc)} transaction{'s' if len(inc)!=1 else ''} were received from {country} valued at {_list_amount_dates(inc)}")
            if out:
                segs.append(f"{len(out)} transaction{'s' if len(out)!=1 else ''} were sent to {country} valued at {_list_amount_dates(out)}")
            parts.append(" and ".join(segs))
        front = "Our records show " + " and ".join(parts) + "."
        s = f"{front} {closing}"
        return s if s.endswith("?") else s.rstrip('.') + "?"

    # ---- Neutral fallback (no country) ----
    inc = [i for i in norm if i["direction"] == "IN"]
    out = [i for i in norm if i["direction"] == "OUT"]
    bits = []
    if inc: bits.append(f"{len(inc)} transaction{'s' if len(inc)!=1 else ''} were received valued at {_list_amount_dates(inc)}")
    if out: bits.append(f"{len(out)} transaction{'s' if len(out)!=1 else ''} were sent valued at {_list_amount_dates(out)}")
    front = "Our records show " + " and ".join(bits) + "."
    s = f"{front} {closing}"
    return s if s.endswith("?") else s.rstrip('.') + "?"

# ---------- AI route (with outreach support) ----------

def _build_outreach_email(customer_id: str, rows: list) -> str:
    """
    Build a plain-text outreach email using the customer-friendly questions.
    """
    when = datetime.now().strftime("%d %B %Y")
    lines = []
    lines.append(f"Subject: Information request regarding recent account activity ({customer_id})")
    lines.append("")
    lines.append("Dear Customer,")
    lines.append("")
    lines.append(
        "We’re reviewing recent activity on your account and would be grateful if you could "
        "provide further information to help us complete our checks."
    )
    lines.append("")
    lines.append("Please respond to the questions below:")
    lines.append("")
    for i, r in enumerate(rows, start=1):
        q = (r.get("question_nice") or r.get("question") or "").strip()
        if q and not q.endswith("?"):
            q += "?"
        lines.append(f"{i}. {q}")
    lines.append("")
    lines.append("If you have any supporting documents (e.g., invoices or contracts), please include them.")
    lines.append("")
    lines.append("Kind regards,")
    lines.append("Compliance Team")
    lines.append(when)
    return "\n".join(lines)

# Remember the user's last customer in THIS browser session (not global)
def _remember_customer_for_session(customer_id: Optional[str]) -> None:
    try:
        from flask import session as _sess  # local import to avoid circulars
        if customer_id:
            _sess["last_customer_id"] = customer_id
    except Exception:
        pass


@app.route("/ai", methods=["GET", "POST"])
def ai_analysis():
    """
    AI Analysis workflow:
      - action=build    -> collect alerts -> (optional) LLM normalise -> save questions
      - action=save     -> persist answers
      - action=outreach -> generate outreach email text (shown on page)
    Renders customer-friendly sentences (country names, natural dates, sent/received) and
    keeps intent-specific closings to avoid apparent duplicates.

    NOTE: No global fallback to "last case" — we only use the per-session last customer.
    """
    ensure_ai_tables()

    cust   = request.values.get("customer_id")
    period = request.values.get("period", "3m")
    action = request.values.get("action")

    # remember the user’s current customer for this browser session
    _remember_customer_for_session(cust)

    # Resolve period bounds
    today = date.today()
    if period == "all":
        p_from, p_to = None, None
    elif period.endswith("m") and period[:-1].isdigit():
        months = int(period[:-1])
        start_month = (today.replace(day=1) - timedelta(days=months * 31)).replace(day=1)
        p_from, p_to = start_month.isoformat(), today.isoformat()
    else:
        p_from, p_to = None, None

    # If no customer provided, try session-scoped last_customer_id; else render empty state
    if not cust:
        last_cust = session.get("last_customer_id")
        if last_cust:
            return redirect(url_for("ai_analysis", customer_id=last_cust, period=period))

    db = get_db()
    params = {
        "cfg_ai_use_llm": bool(cfg_get("cfg_ai_use_llm", False)),
        "cfg_ai_model":   str(cfg_get("cfg_ai_model", "gpt-4o-mini")),
    }

    case_row = None
    answers  = []
    proposed = []
    used_llm = False
    outreach_text = None

    # -------- helpers to attach txn details + build customer-friendly text --------
    def _fetch_details_for_ids(txn_ids: list) -> dict:
        if not txn_ids:
            return {}
        qmarks = ",".join("?" * len(txn_ids))
        rows = get_db().execute(
            f"""SELECT id AS txn_id, txn_date, base_amount, country_iso2, direction,
                        customer_id, channel, narrative
                   FROM transactions
                  WHERE id IN ({qmarks})""",
            list(map(str, txn_ids)),
        ).fetchall()
        return {r["txn_id"]: dict(r) for r in rows}

    def _attach_and_enrich(rows):
        if not rows:
            return []
        # gather all ids
        all_ids = []
        for r in rows:
            src = r.get("sources")
            if isinstance(src, str) and src:
                all_ids.extend([x for x in src.split(",") if x])
            elif isinstance(src, list) and src:
                all_ids.extend(list(map(str, src)))
        details_map = _fetch_details_for_ids(list(dict.fromkeys(all_ids)))

        out = []
        for r in rows:
            if isinstance(r.get("sources"), str) and r["sources"]:
                ids = [x for x in r["sources"].split(",") if x]
            elif isinstance(r.get("sources"), list):
                ids = list(map(str, r["sources"]))
            else:
                ids = []
            r["source_details"] = [details_map[i] for i in ids if i in details_map]
            r["question_nice"] = _question_sentence_for_row(r)
            out.append(r)
        return out

    def _dedupe_by_sentence(rows):
        seen, out = set(), []
        for r in rows:
            key = (r.get("tag") or "", (r.get("question_nice") or r.get("question") or "").strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    # ------------------------------ Actions ------------------------------
    if cust:
        case_row = db.execute(
            "SELECT * FROM ai_cases WHERE customer_id=? ORDER BY updated_at DESC LIMIT 1",
            (cust,),
        ).fetchone()

        # -------- Prepare Questions --------
        if action == "build":
            base_questions, fired_tags, source_alerts = build_ai_questions(cust, p_from, p_to)

            if not case_row:
                db.execute(
                    "INSERT INTO ai_cases(customer_id, period_from, period_to) VALUES(?,?,?)",
                    (cust, p_from, p_to),
                )
                db.commit()
                case_row = db.execute(
                    "SELECT * FROM ai_cases WHERE customer_id=? ORDER BY id DESC LIMIT 1",
                    (cust,),
                ).fetchone()

            final_questions = list(base_questions)
            if llm_enabled():
                final_questions = ai_normalise_questions_llm(cust, fired_tags, source_alerts, base_questions)
                used_llm = True

            # Persist (overwrite) with sources (txn_ids)
            db.execute("DELETE FROM ai_answers WHERE case_id=?", (case_row["id"],))
            for q in final_questions:
                src = q.get("sources") or []
                db.execute(
                    "INSERT INTO ai_answers(case_id, tag, question, sources) VALUES(?,?,?,?)",
                    (
                        case_row["id"],
                        q.get("tag") or "",
                        q.get("question") or "",
                        ",".join(map(str, src)) if src else None,
                    ),
                )
            db.commit()

            flash(
                f"Prepared {len(final_questions)} question(s) based on {len(source_alerts)} alert(s) for {cust}."
                + (" (Normalised with AI.)" if used_llm else "")
            )
            return redirect(url_for("ai_analysis", customer_id=cust, period=period))

        # -------- Save Responses --------
        if action == "save":
            case_id = int(request.values.get("case_id"))
            for qid in request.values.getlist("qid"):
                ans = request.values.get(f"answer_{qid}", "")
                db.execute(
                    "UPDATE ai_answers SET answer=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (ans, qid),
                )
            db.execute("UPDATE ai_cases SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
            db.commit()
            flash("Responses saved.")
            return redirect(url_for("ai_analysis", customer_id=cust, period=period))

        # -------- Build Outreach Pack (generate email text) --------
        if action == "outreach" and case_row:
            rows = db.execute(
                "SELECT * FROM ai_answers WHERE case_id=? ORDER BY id",
                (case_row["id"],),
            ).fetchall()
            rows = _attach_and_enrich([dict(r) for r in rows]) if rows else []
            rows = _dedupe_by_sentence(rows)
            outreach_text = _build_outreach_email(cust, rows)
            # fall through to GET rendering with outreach_text displayed

        # -------- GET view (load answers or show preview if empty) --------
        if case_row and not outreach_text:
            answers = db.execute(
                "SELECT * FROM ai_answers WHERE case_id=? ORDER BY id",
                (case_row["id"],),
            ).fetchall()
            if not answers:
                proposed, _, _ = build_ai_questions(cust, p_from, p_to)

    # Attach & enrich for display
    answers_list  = _attach_and_enrich([dict(a) for a in answers]) if answers else []
    proposed_list = _attach_and_enrich([dict(p) for p in proposed]) if proposed else []

    # Guardrail: de-duplicate identical sentences per tag
    answers_list  = _dedupe_by_sentence(answers_list)
    proposed_list = _dedupe_by_sentence(proposed_list)

    case = dict(case_row) if case_row else None

    return render_template(
        "ai.html",
        customer_id=cust,
        period=period,
        period_from=p_from,
        period_to=p_to,
        case=case,
        answers=answers_list,
        proposed_questions=proposed_list,
        params=params,
        outreach_text=outreach_text,          # displayed when present
        country_full_name=country_full_name,  # available to Jinja if needed
    )

def format_outreach_responses(answers_rows):
    """Turn outreach answers into a narrative for the rationale."""
    if not answers_rows:
        return "Outreach questions have been prepared; responses are currently awaited."

    lines = []
    for r in answers_rows:
        ans = (r.get("answer") or "").strip()
        if not ans:
            continue
        # Tag context if available
        if r.get("tag"):
            lines.append(f"Regarding {r['tag'].replace('_',' ').title()}: {ans}")
        else:
            lines.append(f"Customer stated: {ans}")

    if not lines:
        return "Outreach questions prepared; responses currently awaited."
    return " ".join(lines)

def _months_in_period(p_from: Optional[str], p_to: Optional[str]) -> float:
    """Rough month count used for avg-per-month. Falls back to 1.0 if bounds missing/invalid."""
    try:
        if not p_from or not p_to:
            return 1.0
        d1 = date.fromisoformat(p_from)
        d2 = date.fromisoformat(p_to)
        days = max(1, (d2 - d1).days + 1)
        return max(1.0, days / 30.4375)
    except Exception:
        return 1.0

def _safe_pct(numer: float, denom: float) -> float:
    try:
        return (float(numer) / float(denom)) * 100.0 if float(denom) else 0.0
    except Exception:
        return 0.0

def _period_text(p_from: Optional[str] = None, p_to: Optional[str] = None) -> str:
    if not p_from and not p_to:
        return "the available period"
    if p_from and p_to:
        return f"{p_from} to {p_to}"
    if p_from and not p_to:
        return f"from {p_from}"
    if p_to and not p_from:
        return f"up to {p_to}"
    return "the selected period"

def _sector_alignment_score(nature_of_business: Optional[str], narratives: list[str]) -> tuple[float, list[str]]:
    """
    Very simple heuristic:
      - Tokenise 'nature_of_business' into keywords (>=4 chars), plus a small synonym set for common sectors.
      - Score % of narratives that contain at least one keyword.
    Returns (pct_aligned, hit_keywords_sorted)
    """
    if not nature_of_business:
        return 0.0, []
    base = nature_of_business.lower()

    # seed keywords from the nature text
    kw = {w for w in re.split(r"[^a-z0-9]+", base) if len(w) >= 4}

    # add tiny synonym hints for common sectors
    synonyms = {
        "restaurant": {"food", "catering", "kitchen", "takeaway", "diner"},
        "building": {"builder", "construction", "materials", "timber", "cement", "merchant", "trade"},
        "retail": {"shop", "store", "till", "pos", "receipt"},
        "consulting": {"consultancy", "professional", "advisory"},
        "transport": {"haulage", "logistics", "freight", "courier"},
    }
    for k, vals in synonyms.items():
        if k in base:
            kw |= vals

    kw = {k for k in kw if k}  # non-empty
    if not kw or not narratives:
        return 0.0, sorted(list(kw))

    aligned = 0
    hits = set()
    for n in narratives:
        low = (n or "").lower()
        if any(k in low for k in kw):
            aligned += 1
            # record which ones hit
            for k in kw:
                if k in low:
                    hits.add(k)

    pct = _safe_pct(aligned, len(narratives))
    return pct, sorted(list(hits))

from typing import Optional

def build_rationale_text(
    customer_id: str,
    p_from: Optional[str],
    p_to: Optional[str],
    nature_of_business: Optional[str],
    est_income: Optional[float],
    est_expenditure: Optional[float],
) -> str:
    m = _customer_metrics(customer_id, p_from, p_to)
    case, answers = _answers_summary(customer_id)

    def _period_text(pf: Optional[str], pt: Optional[str]) -> str:
        if pf and pt:
            return f"{pf} to {pt}"
        return "the period reviewed"

    period_txt = _period_text(p_from, p_to)

    # --- Outreach plausibility (kept but only used to shape tone if no tag-specific rewrite) ---
    n_answers = 0
    plaus_scores = []

    def _plausibility_score(ans: str, tag: str) -> int:
        if not ans:
            return 0
        a = ans.lower()
        score = 0
        # +detail
        if len(a) >= 80: score += 2
        if any(w in a for w in ["invoice", "payroll", "utilities", "supplier", "contract", "order", "shipment"]): score += 2
        if any(w in a for w in ["bank statement", "receipt", "evidence", "documentation", "proof"]): score += 2
        if any(w in a for w in ["gift", "loan", "family", "friend"]): score += 1
        if any(w in a for w in ["awaiting", "will provide", "checking", "confirming"]): score += 1
        # vagueness / hedging
        if any(w in a for w in ["don't know", "no idea", "can’t remember", "misc", "various"]): score -= 3
        if any(w in a for w in ["just because", "personal reasons"]): score -= 2
        if any(w in a for w in ["cash", "cash deposit"]) and tag.upper() != "CASH_DAILY_BREACH": score -= 1
        # light tag alignment
        t = (tag or "").upper()
        if t == "PROHIBITED_COUNTRY" and any(w in a for w in ["russia", "ru", "sanction", "export control"]):
            score += 1
        if t in ("HIGH_RISK_COUNTRY","HIGH_3RD") and any(w in a for w in ["third party", "intermediary", "agent"]):
            score += 1
        return score

    if answers:
        for r in answers:
            ans = (r.get("answer") or "").strip()
            if ans:
                n_answers += 1
                plaus_scores.append(_plausibility_score(ans, r.get("tag") or ""))

    if n_answers:
        avg_p = sum(plaus_scores) / max(1, len(plaus_scores))
        if avg_p >= 3:
            outreach_tone = "Customer explanations appear broadly plausible and evidence-led."
        elif avg_p >= 1:
            outreach_tone = "Customer explanations provide some relevant detail; further corroboration may be appropriate."
        else:
            outreach_tone = "Customer explanations lack sufficient detail and require clarification."
    else:
        outreach_tone = "Outreach questions prepared; responses currently awaited."

    # --- period months for averages (for estimate comparison) ---
    def _months_in_period() -> int:
        if m.get("period_months"):
            try:
                pm = int(m["period_months"])
                return pm if pm > 0 else 1
            except Exception:
                pass
        if p_from and p_to:
            try:
                d1 = date.fromisoformat(p_from)
                d2 = date.fromisoformat(p_to)
                days = max(1, (d2 - d1).days)
                return max(1, round(days / 30))
            except Exception:
                return 1
        return 1

    months = _months_in_period()

    def _line_for_estimate(avg_val: float, est_val: Optional[float], label: str) -> Optional[str]:
        if est_val is None or est_val <= 0:
            return None
        diff = avg_val - est_val
        pct = (diff / est_val) * 100.0
        abs_pct = abs(pct)
        if abs_pct <= 20:
            stance = "in line with"
        elif pct > 0:
            stance = "above"
        else:
            stance = "below"
        return (
            f"Average monthly {label} of £{avg_val:,.0f} is {stance} the estimate "
            f"(£{est_val:,.0f}{'' if stance=='in line with' else f', by {abs_pct:.0f}%'})."
        )

    avg_monthly_in  = (m.get("total_in") or 0.0)  / months
    avg_monthly_out = (m.get("total_out") or 0.0) / months

    income_line = _line_for_estimate(avg_monthly_in,  est_income,       "credits")
    spend_line  = _line_for_estimate(avg_monthly_out, est_expenditure,  "debits")

    # --- Friendly zero phrasing & composition helpers ---
    def _cash_phrase():
        ci, co = float(m.get("cash_in") or 0), float(m.get("cash_out") or 0)
        return "There has been no cash usage." if ci == 0 and co == 0 else \
               f"Cash activity: deposits £{ci:,.2f}, withdrawals £{co:,.2f}."

    def _overseas_phrase():
        ov = float(m.get("overseas") or 0)
        return "There have been no overseas transactions." if ov == 0 else \
               f"Overseas activity accounts for {float(m.get('overseas_pct') or 0):.1f}% of value (£{ov:,.2f})."

    def _hr_phrase():
        hr = float(m.get("hr_val") or 0)
        if hr == 0:
            return "No transactions were recorded through high-risk or prohibited corridors."
        return f"High-risk/high-risk-third/prohibited corridors account for {float(m.get('hr_pct') or 0):.1f}% of value (£{hr:,.2f})."

    cash_line = _cash_phrase()
    overseas_line = _overseas_phrase()
    hr_line = _hr_phrase()

    # --- Business alignment (keywords from nature_of_business vs narratives) ---
    def _alignment_phrase():
        nob = (nature_of_business or "").strip().lower()
        if not nob:
            return None
        stop = {"and","the","of","for","to","with","a","an","in","on","ltd","plc","inc","co"}
        kws = sorted({w.strip(",./-()") for w in nob.split() if len(w) >= 4 and w not in stop})
        if not kws:
            return None

        rows = get_db().execute(
            """
            SELECT narrative
              FROM transactions
             WHERE customer_id=? AND (? IS NULL OR txn_date>=?) AND (? IS NULL OR txn_date<=?)
             LIMIT 400
            """,
            (customer_id, p_from, p_from, p_to, p_to)
        ).fetchall()

        total = len(rows)
        if total == 0:
            return None

        hits = 0
        for r in rows:
            text = (r["narrative"] or "").lower()
            if any(k in text for k in kws):
                hits += 1

        ratio = hits / total
        eg = ", ".join(kws[:3])
        if ratio >= 0.5:
            return f"Most transactions (≈{ratio*100:.0f}%) reference terms consistent with the declared business (e.g., {eg})."
        if ratio >= 0.2:
            return f"A minority of transactions (≈{ratio*100:.0f}%) reference business-aligned terms (e.g., {eg}); the remainder appear generic."
        return "Transaction descriptions do not strongly indicate the declared business; consider corroborating with additional evidence."

    alignment_line = _alignment_phrase()

    # --- Alerts + Outreach: collapse into single, country-explicit sentence for PROHIBITED_COUNTRY ---
    def _prohibited_country_sentence() -> Optional[str]:
        # Find distinct countries linked to prohibited alerts in the period
        params = [customer_id]
        where = "a.customer_id=? AND json_extract(a.rule_tags, '$') IS NOT NULL AND a.rule_tags LIKE '%PROHIBITED_COUNTRY%'"
        if p_from and p_to:
            where += " AND t.txn_date BETWEEN ? AND ?"
            params += [p_from, p_to]
        rows = get_db().execute(
            f"""
            SELECT DISTINCT t.country_iso2
              FROM alerts a
              JOIN transactions t ON t.id = a.txn_id
             WHERE {where}
            """, params
        ).fetchall()
        countries = [country_full_name(r["country_iso2"]) for r in rows if r["country_iso2"]]
        countries_str = ", ".join(sorted(set(countries))) if countries else "a prohibited jurisdiction"

        # Choose the most relevant/first prohibited-country answer if present
        pc_answers = [r for r in (answers or []) if (r.get("tag") or "").upper() == "PROHIBITED_COUNTRY"]
        answer_txt = (pc_answers[0].get("answer") or "").strip() if pc_answers else ""

        # Documentation heuristic
        mentions_docs = any(w in (answer_txt or "").lower() for w in [
            "invoice","contract","agreement","evidence","documentation","proof","bank statement","receipt"
        ])

        if answer_txt:
            sentence = (
                f"Alerts show transactions to and from {countries_str}, which is a Prohibited Country. "
                f"The Customer has confirmed that {answer_txt.rstrip('.')}. "
                f"{'Supporting documentation has been referenced.' if mentions_docs else 'No supporting documentation has been provided.'}"
            )
        else:
            sentence = (
                f"Alerts show transactions to and from {countries_str}, which is a Prohibited Country. "
                "Customer outreach responses are awaited."
            )
        return sentence

    def _alerts_sentence() -> str:
        tags = dict(m.get("tag_counter") or {})
        if not tags:
            return "No alerts were noted in the review period."
        if "PROHIBITED_COUNTRY" in tags:
            return _prohibited_country_sentence() or "No alerts were noted in the review period."
        # fallback: name other tags cleanly
        tag_bits = [tg.replace("_", " ").title() for tg in sorted(tags.keys())]
        return "Alerts noted: " + ", ".join(tag_bits) + "."

    # --- Compose final text (single cohesive section; no duplicated blocks) ---
    lines = []
    if nature_of_business:
        lines.append(f"Nature of business: {nature_of_business.strip()}.")

    lines.append(
        "Analysis of account transactions over "
        f"{period_txt}. Credits total £{(m.get('total_in') or 0):,.2f} "
        f"(avg £{(m.get('avg_in') or 0):,.2f}; largest £{(m.get('max_in') or 0):,.2f}); "
        f"debits total £{(m.get('total_out') or 0):,.2f} "
        f"(avg £{(m.get('avg_out') or 0):,.2f}; largest £{(m.get('max_out') or 0):,.2f})."
    )

    # Cash/overseas/hr (use friendly zero phrasing and avoid duplicating numbers you asked to remove earlier)
    lines.append(cash_line)
    lines.append(overseas_line)
    if float(m.get("hr_val") or 0) > 0:
        lines.append(hr_line)

    if income_line: lines.append(income_line)
    if spend_line:  lines.append(spend_line)
    if alignment_line: lines.append(alignment_line)

    # Alerts (merged prohibited-country wording if applicable) + only add tone if we didn't already include a concrete sentence
    alerts_line = _alerts_sentence()
    lines.append(alerts_line)

    # If the alerts sentence already contains a concrete outreach statement (provided / awaited), we don't also add the generic tone
    if "Customer outreach responses are awaited." in alerts_line or "Supporting documentation has been referenced." in alerts_line or "No supporting documentation has been provided." in alerts_line:
        pass
    else:
        # keep a short tone line for non-prohibited tags or when no tag-specific sentence was formed
        lines.append(outreach_tone)

    # If truly no alerts, add the “no anomalies” wrap-up
    if not (m.get("tag_counter") or {}):
        lines.append("No material anomalies were identified in the period reviewed; activity appears consistent with the overall profile.")

    return "\n".join(lines)

from flask import session

from typing import Optional

@app.route("/ai-rationale", methods=["GET", "POST"])
def ai_rationale():
    ensure_ai_rationale_table()

    # Inputs
    customer_id = request.values.get("customer_id", "").strip() or None
    period = request.values.get("period", "3m")

    # Compute bounds (reuse your _period_bounds or equivalent)
    p_from, p_to = _period_bounds(period)

    # Defaults for template
    metrics = None
    answers_preview = []
    rationale_text = None
    nature_of_business = request.values.get("nature_of_business", "") or None
    est_income = request.values.get("est_income", "")
    est_expenditure = request.values.get("est_expenditure", "")
    action = request.values.get("action")

    # Coerce numbers safely
    def _to_float_or_none(s):
        try:
            return float(str(s).replace(",", "")) if s not in (None, "", "None") else None
        except Exception:
            return None
    est_income_num = _to_float_or_none(est_income)
    est_expenditure_num = _to_float_or_none(est_expenditure)

    # POST: generate + persist
    if request.method == "POST" and action == "generate" and customer_id:
        # Build metrics used in the page header tiles
        metrics = _customer_metrics(customer_id, p_from, p_to)  # you already have this helper
        # Build rationale text
        rationale_text = build_rationale_text(
            customer_id=customer_id,
            p_from=p_from,
            p_to=p_to,
            nature_of_business=nature_of_business,
            est_income=est_income_num,
            est_expenditure=est_expenditure_num,
        )
        # Save for this (customer, period)
        _upsert_rationale_row(
            customer_id=customer_id,
            p_from=p_from,
            p_to=p_to,
            nature_of_business=nature_of_business,
            est_income=est_income_num,
            est_expenditure=est_expenditure_num,
            rationale_text=rationale_text,
        )
        # Load short outreach preview, if you want to show the responses badge
        case, answers_preview = _answers_summary(customer_id)

        return render_template(
            "ai_rationale.html",
            customer_id=customer_id,
            period=period,
            metrics=metrics,
            nature_of_business=nature_of_business,
            est_income=est_income if est_income is not None else "",
            est_expenditure=est_expenditure if est_expenditure is not None else "",
            rationale_text=rationale_text,
            answers_preview=answers_preview,
        )

    # GET: load any saved rationale for this (customer, period)
    if request.method == "GET" and customer_id:
        metrics = _customer_metrics(customer_id, p_from, p_to)
        row = _load_rationale_row(customer_id, p_from, p_to)
        if row:
            rationale_text = row["rationale_text"]
            # Pre-fill inputs from saved row if user hasn't typed new values
            if not nature_of_business:
                nature_of_business = row["nature_of_business"]
            if est_income == "":
                est_income = ("" if row["est_income"] is None else str(int(row["est_income"])))
            if est_expenditure == "":
                est_expenditure = ("" if row["est_expenditure"] is None else str(int(row["est_expenditure"])))
        case, answers_preview = _answers_summary(customer_id)

    return render_template(
        "ai_rationale.html",
        customer_id=customer_id,
        period=period,
        metrics=metrics,
        nature_of_business=nature_of_business or "",
        est_income=est_income or "",
        est_expenditure=est_expenditure or "",
        rationale_text=rationale_text,
        answers_preview=answers_preview,
    )

@app.route("/explore")
def explore():
    db = get_db()
    customer_id = request.args.get("customer_id","").strip()
    direction = request.args.get("direction","").strip()
    channel = request.args.get("channel","").strip()
    risk_param = request.args.get("risk","").strip()   # e.g. "HIGH,HIGH_3RD,PROHIBITED" or "HIGH"
    date_from = request.args.get("date_from","").strip()
    date_to = request.args.get("date_to","").strip()
    export = request.args.get("export","") == "csv"

    where, params = [], []
    join_risk = False

    if customer_id:
        where.append("t.customer_id = ?"); params.append(customer_id)
    if direction in ("in","out"):
        where.append("t.direction = ?"); params.append(direction)
    if channel:
        where.append("lower(ifnull(t.channel,'')) = ?"); params.append(channel.lower())

    # --- NEW: flexible multi-risk filter ---
    valid_risks = {"LOW","MEDIUM","HIGH","HIGH_3RD","PROHIBITED"}
    risk_list = [r.strip().upper() for r in risk_param.split(",") if r.strip()]
    risk_list = [r for r in risk_list if r in valid_risks]
    if risk_list:
        join_risk = True
        placeholders = ",".join(["?"] * len(risk_list))
        where.append(f"r.risk_level IN ({placeholders})")
        params.extend(risk_list)

    if date_from:
        where.append("t.txn_date >= ?"); params.append(date_from)
    if date_to:
        where.append("t.txn_date <= ?"); params.append(date_to)

    join_clause = "JOIN ref_country_risk r ON r.iso2 = ifnull(t.country_iso2, '')" if join_risk else ""
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
      SELECT t.id, t.txn_date, t.customer_id, t.direction, t.base_amount, t.currency,
             t.country_iso2, t.channel, t.payer_sort_code, t.payee_sort_code, t.narrative
      FROM transactions t
      {join_clause}
      {where_clause}
      ORDER BY t.txn_date DESC, t.id DESC
      LIMIT 1000
    """

    rows = db.execute(sql, params).fetchall()
    recs = [dict(r) for r in rows]

    if export:
        from flask import Response
        import csv as _csv, io
        si = io.StringIO()
        fieldnames = recs[0].keys() if recs else [
            "id","txn_date","customer_id","direction","base_amount","currency",
            "country_iso2","channel","payer_sort_code","payee_sort_code","narrative"
        ]
        w = _csv.DictWriter(si, fieldnames=fieldnames)
        w.writeheader()
        for r in recs: w.writerow(r)
        return Response(
            si.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition":"attachment; filename=explore.csv"}
        )

    # distinct channels for dropdown
    ch_rows = db.execute("SELECT DISTINCT lower(ifnull(channel,'')) as ch FROM transactions ORDER BY ch").fetchall()
    channels = [r["ch"] for r in ch_rows if r["ch"]]

    return render_template("explore.html", rows=recs, channels=channels)

# ------- Rules table utilities (safe to add near other helpers) -------
def ensure_rules_table():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            rule TEXT,
            trigger_condition TEXT,
            score_impact TEXT,
            tags TEXT,
            outcome TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_rules_category_rule ON rules(category, rule);")
    db.commit()

def _normalize_rule_columns(df):
    # Accept flexible headers from Excel
    mapping = {}
    for c in df.columns:
        k = str(c).strip().lower()
        if k == "category": mapping[c] = "category"
        elif k in ("rule", "rule name", "name"): mapping[c] = "rule"
        elif k in ("trigger condition", "trigger", "condition"): mapping[c] = "trigger_condition"
        elif k in ("score impact", "impact", "score"): mapping[c] = "score_impact"
        elif k in ("tag(s)", "tags", "rule tags"): mapping[c] = "tags"
        elif k in ("escalation outcome", "outcome", "severity outcome"): mapping[c] = "outcome"
        elif k in ("description", "plain description", "explanation"): mapping[c] = "description"
        else:
            mapping[c] = c
    df = df.rename(columns=mapping)
    # ensure optional cols exist
    for col in ["trigger_condition","score_impact","tags","outcome","description"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    return df

# ------- Routes to edit/reload rules from Admin UI -------
@app.post("/admin/rules")
def admin_rules():
    """Save a single rule's editable fields (score_impact, outcome, description)."""
    ensure_rules_table()
    rid = request.form.get("save_rule")
    if not rid:
        flash("No rule id provided.")
        return redirect(url_for("admin"))

    score_impact = request.form.get(f"score_impact_{rid}", "").strip()
    outcome = request.form.get(f"outcome_{rid}", "").strip()
    description = request.form.get(f"description_{rid}", "").strip()

    db = get_db()
    db.execute("""
        UPDATE rules
           SET score_impact=?, outcome=?, description=?, updated_at=CURRENT_TIMESTAMP
         WHERE id=?
    """, (score_impact, outcome, description, rid))
    db.commit()
    flash(f"Rule {rid} saved.")
    return redirect(url_for("admin") + "#rules")

@app.post("/admin/rules-bulk")
def admin_rules_bulk():
    """
    Bulk actions:
      - action=reload: read uploaded .xlsx and upsert rules
      - action=wipe: delete all rules
    """
    ensure_rules_table()
    action = request.form.get("action", "").lower()
    db = get_db()

    if action == "wipe":
        db.execute("DELETE FROM rules;")
        db.commit()
        flash("All rules wiped.")
        return redirect(url_for("admin") + "#rules")

    if action == "reload":
        file = request.files.get("rules_file")
        if not file or not file.filename.lower().endswith((".xlsx", ".xls")):
            flash("Please upload an Excel file (.xlsx).")
            return redirect(url_for("admin") + "#rules")

        # Read Excel into DataFrame
        try:
            import pandas as pd
        except ImportError:
            flash("pandas is required to import Excel. Install with: pip install pandas openpyxl")
            return redirect(url_for("admin") + "#rules")

        try:
            df = pd.read_excel(file)
            df = _normalize_rule_columns(df)
        except Exception as e:
            flash(f"Failed to read Excel: {e}")
            return redirect(url_for("admin") + "#rules")

        # Upsert rows
        upsert_sql = """
            INSERT INTO rules (category, rule, trigger_condition, score_impact, tags, outcome, description, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(category, rule) DO UPDATE SET
                trigger_condition=excluded.trigger_condition,
                score_impact=excluded.score_impact,
                tags=excluded.tags,
                outcome=excluded.outcome,
                description=excluded.description,
                updated_at=CURRENT_TIMESTAMP;
        """

        recs = []
        for _, r in df.iterrows():
            category = str(r.get("category","")).strip()
            rule = str(r.get("rule","")).strip()
            if not category or not rule:
                continue
            recs.append((
                category,
                rule,
                str(r.get("trigger_condition","")).strip(),
                str(r.get("score_impact","")).strip(),
                str(r.get("tags","")).strip(),
                str(r.get("outcome","")).strip(),
                str(r.get("description","")).strip(),
            ))

        if not recs:
            flash("Excel contained no valid rule rows (need Category and Rule).")
            return redirect(url_for("admin") + "#rules")

        db.executemany(upsert_sql, recs)
        db.commit()
        flash(f"Reloaded {len(recs)} rule(s) from Excel.")
        return redirect(url_for("admin") + "#rules")

    # Unknown action
    flash("Unknown action.")
    return redirect(url_for("admin") + "#rules")

# ---------- AI Rationale storage ----------
def ensure_ai_rationale_table():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS ai_rationales(
          id INTEGER PRIMARY KEY,
          customer_id TEXT NOT NULL,
          period_from TEXT,
          period_to TEXT,
          nature_of_business TEXT,
          est_income REAL,
          est_expenditure REAL,
          rationale TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # convenience index
    db.execute("CREATE INDEX IF NOT EXISTS idx_ai_ration_cust ON ai_rationales(customer_id, updated_at DESC);")
    db.commit()


def _period_text(p_from, p_to):
    if not p_from and not p_to:
        return "all transactions in the feed"
    return f"{p_from} to {p_to}"

def _sum_q(sql, params):
    row = get_db().execute(sql, params).fetchone()
    return float(row["s"] or 0.0)

def _count_q(sql, params):
    row = get_db().execute(sql, params).fetchone()
    return int(row["c"] or 0)

def _customer_metrics(customer_id: str, p_from: Optional[str], p_to: Optional[str]):
    """
    Returns a dict of key figures for rationale text.
    """
    db = get_db()
    wh, params = ["customer_id=?"], [customer_id]
    if p_from: wh.append("txn_date>=?"); params.append(p_from)
    if p_to:   wh.append("txn_date<=?"); params.append(p_to)
    where = "WHERE " + " AND ".join(wh)

    total_in  = _sum_q(f"SELECT SUM(base_amount) s FROM transactions {where} AND direction='in'",  params)
    total_out = _sum_q(f"SELECT SUM(base_amount) s FROM transactions {where} AND direction='out'", params)
    n_in   = _count_q(f"SELECT COUNT(*) c FROM transactions {where} AND direction='in'",  params)
    n_out  = _count_q(f"SELECT COUNT(*) c FROM transactions {where} AND direction='out'", params)
    avg_in  = (total_in / n_in) if n_in else 0.0
    avg_out = (total_out / n_out) if n_out else 0.0

    # Largest in/out
    row = db.execute(f"""
        SELECT MAX(CASE WHEN direction='in'  THEN base_amount END) AS max_in,
               MAX(CASE WHEN direction='out' THEN base_amount END) AS max_out
        FROM transactions {where}
    """, params).fetchone()
    max_in  = float(row["max_in"]  or 0.0)
    max_out = float(row["max_out"] or 0.0)

    # Cash totals
    cash_in  = _sum_q(f"SELECT SUM(base_amount) s FROM transactions {where} AND direction='in'  AND lower(IFNULL(channel,''))='cash'",  params)
    cash_out = _sum_q(f"SELECT SUM(base_amount) s FROM transactions {where} AND direction='out' AND lower(IFNULL(channel,''))='cash'", params)

    # Overseas (anything not GB and not NULL)
    overseas = _sum_q(f"""
        SELECT SUM(base_amount) s
          FROM transactions
         {where} AND IFNULL(country_iso2,'')<>'' AND UPPER(country_iso2)!='GB'
    """, params)
    total_val = total_in + total_out
    overseas_pct = (overseas / total_val * 100.0) if total_val else 0.0

    # High-risk / prohibited
    hr_val = _sum_q(f"""
        SELECT SUM(t.base_amount) s
          FROM transactions t
          JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2,'')
         {where.replace('WHERE','WHERE t.')} AND r.risk_level IN ('HIGH','HIGH_3RD','PROHIBITED')
    """, params)
    hr_pct = (hr_val / total_val * 100.0) if total_val else 0.0

    # Alerts & tags present in period
    a_wh, a_params = ["a.customer_id=?"],[customer_id]
    if p_from and p_to:
        a_wh.append("t.txn_date BETWEEN ? AND ?"); a_params += [p_from, p_to]
    alerts = db.execute(f"""
        SELECT a.severity, a.rule_tags, t.txn_date, a.txn_id
          FROM alerts a
          JOIN transactions t ON t.id=a.txn_id
         WHERE {" AND ".join(a_wh)}
         ORDER BY t.txn_date
    """, a_params).fetchall()
    tag_counter = {}
    for r in alerts:
        tags = []
        try:
            tags = json.loads(r["rule_tags"] or "[]")
        except Exception:
            pass
        for tg in tags:
            tag_counter[tg] = tag_counter.get(tg, 0) + 1

    # KYC profile
    kyc = db.execute("SELECT expected_monthly_in, expected_monthly_out FROM kyc_profile WHERE customer_id=?", (customer_id,)).fetchone()
    exp_in  = float(kyc["expected_monthly_in"]  or 0.0) if kyc else 0.0
    exp_out = float(kyc["expected_monthly_out"] or 0.0) if kyc else 0.0

    return {
        "total_in": total_in, "total_out": total_out,
        "n_in": n_in, "n_out": n_out, "avg_in": avg_in, "avg_out": avg_out,
        "max_in": max_in, "max_out": max_out,
        "cash_in": cash_in, "cash_out": cash_out,
        "overseas": overseas, "overseas_pct": overseas_pct,
        "hr_val": hr_val, "hr_pct": hr_pct,
        "alerts": [dict(a) for a in alerts],
        "tag_counter": tag_counter,
        "expected_in": exp_in, "expected_out": exp_out,
    }


def _answers_summary(customer_id: str):
    """
    Pull latest AI case answers and summarise whether they’re answered.
    """
    db = get_db()
    case = db.execute(
        "SELECT * FROM ai_cases WHERE customer_id=? ORDER BY updated_at DESC LIMIT 1",
        (customer_id,)
    ).fetchone()
    if not case:
        return None, []

    rows = db.execute("SELECT * FROM ai_answers WHERE case_id=? ORDER BY id", (case["id"],)).fetchall()
    answered = [r for r in rows if (r["answer"] or "").strip()]
    return dict(case), [dict(r) for r in rows],

@app.post("/admin/rule-toggles")
def admin_rule_toggles():
    """Persist on/off switches for each built-in rule."""
    def flag(name): return bool(request.form.get(name))
    cfg_set("cfg_rule_enabled_prohibited_country", flag("enable_prohibited_country"))
    cfg_set("cfg_rule_enabled_high_risk_corridor", flag("enable_high_risk_corridor"))
    cfg_set("cfg_rule_enabled_median_outlier",     flag("enable_median_outlier"))
    cfg_set("cfg_rule_enabled_nlp_risky_terms",    flag("enable_nlp_risky_terms"))
    cfg_set("cfg_rule_enabled_expected_out",       flag("enable_expected_out"))
    cfg_set("cfg_rule_enabled_expected_in",        flag("enable_expected_in"))
    cfg_set("cfg_rule_enabled_cash_daily_breach",  flag("enable_cash_daily_breach"))
    cfg_set("cfg_rule_enabled_severity_mapping",   flag("enable_severity_mapping"))
    
    # Check if JSON response requested
    if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        return jsonify({"status": "ok", "message": "Rule toggles saved"})
    
    flash("Rule toggles saved.")
    return redirect(url_for("admin") + "#builtin-rules")

@app.post("/admin/keywords")
def admin_keywords():
    """Add / toggle / delete narrative risk keywords with enabled flags."""
    action = request.form.get("action")
    items = cfg_get("cfg_risky_terms2", [], list)
    message = ""
    success = True

    if action == "add":
        term = (request.form.get("new_term") or "").strip()
        if term and not any(t for t in items if (t.get("term") or "").lower() == term.lower()):
            items.append({"term": term, "enabled": True})
            cfg_set("cfg_risky_terms2", items)
            message = f"Added keyword: {term}"
        elif not term:
            message = "Keyword cannot be empty"
            success = False
        else:
            message = f"Keyword '{term}' already exists"
            success = False
    elif action == "toggle":
        term = request.form.get("term")
        found = False
        for t in items:
            if t.get("term") == term:
                t["enabled"] = not bool(t.get("enabled"))
                cfg_set("cfg_risky_terms2", items)
                message = f"Toggled keyword: {term}"
                found = True
                break
        if not found:
            message = f"Keyword '{term}' not found"
            success = False
    elif action == "delete":
        term = request.form.get("term")
        new_items = [t for t in items if t.get("term") != term]
        if len(new_items) < len(items):
            cfg_set("cfg_risky_terms2", new_items)
            message = f"Removed keyword: {term}"
        else:
            message = f"Keyword '{term}' not found"
            success = False
    else:
        message = "Unknown action."
        success = False

    # Check if JSON response requested
    if request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        if success:
            return jsonify({"status": "ok", "message": message})
        else:
            return jsonify({"status": "error", "message": message}), 400

    if message:
        flash(message)
    return redirect(url_for("admin") + "#keyword-library")

@app.post("/admin/wipe")
def admin_wipe():
    """Danger: wipe all transactional data (transactions, alerts, optional AI tables)."""
    confirm = (request.form.get("confirm") or "").strip().upper()
    if confirm != "WIPE":
        flash("Type WIPE to confirm deletion.", "error")
        return redirect(url_for("admin") + "#danger")

    db = get_db()
    # Count before delete
    n_tx = db.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"]
    n_alerts = db.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"]

    # Delete dependents first
    db.execute("DELETE FROM alerts;")
    db.execute("DELETE FROM transactions;")

    # Optional: clear AI working tables if you like
    try:
        db.execute("DELETE FROM ai_answers;")
        db.execute("DELETE FROM ai_cases;")
    except sqlite3.OperationalError:
        pass

    db.commit()
    try:
        db.execute("VACUUM;")
    except sqlite3.OperationalError:
        pass

    flash(f"Wiped {n_tx} transactions and {n_alerts} alerts. Any AI cases/answers were cleared.")
    return redirect(url_for("admin") + "#danger")

@app.route("/sample/<path:name>")
def download_sample(name):
    return send_from_directory(DATA_DIR, name, as_attachment=True)

# ============================================================================
# JSON API Endpoints for Admin/Operations Manager
# ============================================================================

@app.route("/api/admin/config", methods=["GET"])
def api_admin_config():
    """Get Transaction Review configuration as JSON"""
    db = get_db()
    countries = db.execute("SELECT * FROM ref_country_risk ORDER BY iso2").fetchall()
    
    params = {
        "cfg_high_risk_min_amount": float(cfg_get("cfg_high_risk_min_amount", 0.0)),
        "cfg_median_multiplier":    float(cfg_get("cfg_median_multiplier", 3.0)),
        "cfg_expected_out_factor":  float(cfg_get("cfg_expected_out_factor", 1.2)),
        "cfg_expected_in_factor":   float(cfg_get("cfg_expected_in_factor", 1.2)),
        "cfg_sev_critical":         int(cfg_get("cfg_sev_critical", 90)),
        "cfg_sev_high":             int(cfg_get("cfg_sev_high", 70)),
        "cfg_sev_medium":           int(cfg_get("cfg_sev_medium", 50)),
        "cfg_sev_low":              int(cfg_get("cfg_sev_low", 30)),
        "cfg_ai_use_llm":           bool(cfg_get("cfg_ai_use_llm", False)),
        "cfg_ai_model":             str(cfg_get("cfg_ai_model", "gpt-4o-mini")),
        "cfg_risky_terms2":         cfg_get("cfg_risky_terms2", [], list),
        "cfg_cash_daily_limit":     float(cfg_get("cfg_cash_daily_limit", 0.0)),
    }
    
    toggles = {
        "prohibited_country": bool(cfg_get("cfg_rule_enabled_prohibited_country", True)),
        "high_risk_corridor": bool(cfg_get("cfg_rule_enabled_high_risk_corridor", True)),
        "median_outlier":     bool(cfg_get("cfg_rule_enabled_median_outlier", True)),
        "nlp_risky_terms":    bool(cfg_get("cfg_rule_enabled_nlp_risky_terms", True)),
        "expected_out":       bool(cfg_get("cfg_rule_enabled_expected_out", True)),
        "expected_in":        bool(cfg_get("cfg_rule_enabled_expected_in", True)),
        "cash_daily_breach":  bool(cfg_get("cfg_rule_enabled_cash_daily_breach", True)),
        "severity_mapping":   bool(cfg_get("cfg_rule_enabled_severity_mapping", True)),
    }
    
    return jsonify({
        "status": "ok",
        "params": params,
        "toggles": toggles,
        "countries": [dict(c) for c in countries]
    })

@app.route("/api/admin/countries", methods=["GET"])
def api_admin_countries():
    """Get country risk data as JSON"""
    db = get_db()
    countries = db.execute("SELECT * FROM ref_country_risk ORDER BY iso2").fetchall()
    return jsonify({
        "status": "ok",
        "data": [dict(c) for c in countries]
    })

if __name__ == "__main__":
    # All DB init/seed must run inside the Flask app context
    with app.app_context():
        init_db()
        ensure_default_parameters()
        ensure_ai_tables()
        ensure_ai_rationale_table()
        db = get_db()
        if db.execute("SELECT COUNT(*) c FROM ref_country_risk").fetchone()["c"] == 0:
            load_csv_to_table(os.path.join(DATA_DIR, "ref_country_risk.csv"), "ref_country_risk")
        if db.execute("SELECT COUNT(*) c FROM ref_sort_codes").fetchone()["c"] == 0:
            load_csv_to_table(os.path.join(DATA_DIR, "ref_sort_codes.csv"), "ref_sort_codes")
        if db.execute("SELECT COUNT(*) c FROM kyc_profile").fetchone()["c"] == 0:
            load_csv_to_table(os.path.join(DATA_DIR, "kyc_profile.csv"), "kyc_profile")
        if db.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"] == 0:
            with open(os.path.join(DATA_DIR, "transactions_sample.csv"), "rb") as f:
                ingest_transactions_csv(f)

    app.run(debug=True, port=8085)
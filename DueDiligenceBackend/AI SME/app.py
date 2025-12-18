# app.py  (auth-enabled + feedback range filter + Jinja globals + login redirect)

from typing import Optional, List, Dict, Tuple
from fastapi import (
    FastAPI, UploadFile, File, Form, Request, Depends, HTTPException
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import (
    JSONResponse, PlainTextResponse, RedirectResponse, HTMLResponse
)
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND, HTTP_303_SEE_OTHER
from pathlib import Path
from datetime import datetime, timezone, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

import os
import json
import uuid
import re
import sqlite3

from dotenv import load_dotenv
# Load .env BEFORE importing modules that use environment variables
load_dotenv()

from rag import RAGPipeline
from settings import DATA_DIR, LLM_BACKEND 

# -----------------------------------------------------------------------------
# App + middleware
# -----------------------------------------------------------------------------
app = FastAPI(title="Local RAG Bot (AWS-ready)", docs_url=None, redoc_url=None)

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ✅ Jinja globals so existing Flask-style templates render fine
templates.env.globals.update(
    now=datetime.utcnow,                      # {{ now().year }}
    timedelta=timedelta,                      # if used
    csrf_token=lambda: "",                    # placeholder; no CSRF in FastAPI by default
    get_flashed_messages=lambda **kw: [],     # placeholder for Flask flashes
)

# CORS (relax as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessions (cookie)
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=False)

pipeline = RAGPipeline()

# -----------------------------------------------------------------------------
# Storage files
# -----------------------------------------------------------------------------
REFERRALS_PATH: Path = DATA_DIR / "referrals.jsonl"
FEEDBACK_PATH: Path = DATA_DIR / "feedback.jsonl"
CONFIG_PATH: Path = DATA_DIR / "config.json"
for p in [REFERRALS_PATH.parent, FEEDBACK_PATH.parent, CONFIG_PATH.parent]:
    p.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Config (bot name, auto-yes)
# -----------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "bot_name": "Assistant",
    "auto_yes_ms": 30000,
}

def load_config() -> Dict:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                out = DEFAULT_CONFIG.copy()
                out.update(cfg)
                return out
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

# -----------------------------------------------------------------------------
# SQLite helpers (auth)
# -----------------------------------------------------------------------------
# Use shared database with Due Diligence module
# Path to shared database (scrutinise_workflow.db in Due Diligence folder)
DUE_DILIGENCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Due Diligence"))
DB_PATH = os.environ.get("AUTH_DB_PATH") or os.path.join(DUE_DILIGENCE_DIR, "scrutinise_workflow.db")

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    with db_connect() as db:
        cur = db.execute("SELECT * FROM users WHERE lower(email)=lower(?) LIMIT 1", (email,))
        row = cur.fetchone()
    return row

def get_user_by_id(uid: int) -> Optional[sqlite3.Row]:
    with db_connect() as db:
        cur = db.execute("SELECT * FROM users WHERE id=? LIMIT 1", (uid,))
        row = cur.fetchone()
    return row

# -----------------------------------------------------------------------------
# Role guard dependency
# -----------------------------------------------------------------------------
def require_login(request: Request) -> sqlite3.Row:
    # First check FastAPI's own session (for direct access)
    uid = request.session.get("user_id")
    
    # If no FastAPI session, check for Flask-proxied user ID in header
    if not uid:
        flask_user_id = request.headers.get("X-User-Id")
        if flask_user_id:
            try:
                uid = int(flask_user_id)
            except (ValueError, TypeError):
                pass
    
    if not uid:
        # For HTML callers, signal redirect to /login (handled by exception handler below)
        if "text/html" in (request.headers.get("accept") or ""):
            raise HTTPException(status_code=HTTP_302_FOUND, detail="Redirect")
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = get_user_by_id(int(uid))
    if not user:
        if "text/html" in (request.headers.get("accept") or ""):
            raise HTTPException(status_code=HTTP_302_FOUND, detail="Redirect")
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_role(*roles: str):
    def _dep(request: Request, user: sqlite3.Row = Depends(require_login)) -> sqlite3.Row:
        role = (user["role"] or "").lower()
        # Normalize role names - allow "sme" to match "sme" or any "sme_*" variant
        normalized_roles = []
        for r in roles:
            normalized_roles.append(r.lower())
            # If role is "admin", also allow "sme" (SMEs have admin access to AI SME)
            if r.lower() == "admin":
                normalized_roles.append("sme")
        if not any(role == r or role.startswith(r + "_") for r in normalized_roles):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep

# -----------------------------------------------------------------------------
# Friendly redirect for unauthenticated HTML requests
# -----------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    wants_html = "text/html" in (request.headers.get("accept") or "")
    if wants_html and (exc.status_code in (HTTP_302_FOUND, 401)):
        # Send them to the login page
        return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)
    # JSON fallback
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

# -----------------------------------------------------------------------------
# Acronym normalizer for referral dedupe
# -----------------------------------------------------------------------------
ACRONYM_MAP = {
    r"\bsow\b": "source of wealth",
    r"\bsof\b": "source of funds",
    r"\bcdd\b": "customer due diligence",
    r"\bedd\b": "enhanced due diligence",
    r"\bpep\b": "politically exposed person",
    r"\bkyc\b": "know your customer",
    r"\bkyb\b": "know your business",
    r"\baml\b": "anti money laundering",
    r"\bmlro\b": "money laundering reporting officer",
}

def _norm_question(q: str) -> str:
    s = (q or "").strip().casefold()
    for pat, full in ACRONYM_MAP.items():
        s = re.sub(pat, full, s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\s,.;:!?'/()-]", "", s)
    return s.strip()

def _read_jsonl(path: Path) -> List[Dict]:
    items: List[Dict] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
    return items

def _write_jsonl(path: Path, items: List[Dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    tmp.replace(path)

# -----------------------------------------------------------------------------
# Login / Logout
# -----------------------------------------------------------------------------
@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    user = get_user_by_email(email.strip())
    if not user or not check_password_hash(user["password_hash"], password.strip()):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=401,
        )

    # set session
    request.session["user_id"] = int(user["id"])
    request.session["role"] = (user["role"] or "").lower()
    request.session["email"] = user["email"]
    request.session["name"] = user["name"] or user["email"]

    # ➜ send admins straight to the admin area
    target = "/admin" if request.session["role"] == "admin" or request.session["role"].startswith("admin") else "/"
    return RedirectResponse(url=target, status_code=HTTP_303_SEE_OTHER)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=HTTP_303_SEE_OTHER)

# -----------------------------------------------------------------------------
# UI routes (protected)
# -----------------------------------------------------------------------------
@app.get("/")
def index(request: Request, user: sqlite3.Row = Depends(require_login)):
    return templates.TemplateResponse("index.html", {"request": request, "user": dict(user)})

@app.get("/admin")
def admin(request: Request, user: sqlite3.Row = Depends(require_role("admin"))):
    return templates.TemplateResponse("admin.html", {"request": request, "user": dict(user)})

@app.get("/admin/referrals")
def referrals_page(request: Request, user: sqlite3.Row = Depends(require_role("admin"))):
    return templates.TemplateResponse("referrals.html", {"request": request, "user": dict(user)})

@app.get("/admin/feedback")
def feedback_page(request: Request, user: sqlite3.Row = Depends(require_role("admin"))):
    return templates.TemplateResponse("feedback.html", {"request": request, "user": dict(user)})

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health(request: Request):
    cfg = load_config()
    return {
        "status": "ok",
        "llm_backend": LLM_BACKEND,
        "bot_name": cfg.get("bot_name", DEFAULT_CONFIG["bot_name"]),
        "auto_yes_ms": int(cfg.get("auto_yes_ms", DEFAULT_CONFIG["auto_yes_ms"])),
        # Optional: who am I
        "user": {
            "id": request.session.get("user_id"),
            "email": request.session.get("email"),
            "role": request.session.get("role"),
        },
    }

# -----------------------------------------------------------------------------
# Config (admin)
# -----------------------------------------------------------------------------
@app.get("/config")
def get_config(user: sqlite3.Row = Depends(require_login)):
    cfg = load_config()
    return {
        "status": "ok",
        "data": {
            "bot_name": cfg.get("bot_name", DEFAULT_CONFIG["bot_name"]),
            "auto_yes_ms": int(cfg.get("auto_yes_ms", DEFAULT_CONFIG["auto_yes_ms"])),
        },
    }

@app.post("/admin/config")
def set_config(
    request: Request,
    bot_name: Optional[str] = Form(None),
    auto_yes_ms: Optional[int] = Form(None),
    user: sqlite3.Row = Depends(require_role("admin")),
):
    cfg = load_config()
    if bot_name is not None:
        bot_name = bot_name.strip()
        if not (1 <= len(bot_name) <= 48):
            return JSONResponse({"status": "error", "message": "bot_name must be 1..48 chars"}, status_code=400)
        cfg["bot_name"] = bot_name

    if auto_yes_ms is not None:
        try:
            v = int(auto_yes_ms)
        except Exception:
            return JSONResponse({"status": "error", "message": "auto_yes_ms must be an integer ms"}, status_code=400)
        v = max(5000, min(300000, v))  # clamp 5s..5min
        cfg["auto_yes_ms"] = v

    save_config(cfg)
    return {"status": "ok", "data": cfg}

# -----------------------------------------------------------------------------
# Upload / Query / Delete (any logged-in user)
# -----------------------------------------------------------------------------
@app.post("/upload")
async def upload_doc(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    user: sqlite3.Row = Depends(require_login),
):
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    dst = DATA_DIR / file.filename
    content = await file.read()
    dst.write_bytes(content)
    return pipeline.ingest_path(dst, title=title)

@app.post("/query")
async def query_bot(
    request: Request,
    q: str = Form(...),
    user: sqlite3.Row = Depends(require_login),
):
    try:
        result = pipeline.answer(q)
        return result
    except Exception as e:
        import traceback
        print(f"[API ERROR] Query failed: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "answer": f"Error processing query: {str(e)}",
                "hits": 0,
                "sources": [],
                "context_used": [],
                "error": True,
            }
        )

@app.post("/delete")
async def delete_doc(
    request: Request,
    doc_id: str = Form(...),
    user: sqlite3.Row = Depends(require_role("admin")),
):
    return pipeline.delete(doc_id)

# -----------------------------------------------------------------------------
# Admin: documents
# -----------------------------------------------------------------------------
@app.get("/admin/docs")
def admin_list_docs(user: sqlite3.Row = Depends(require_role("admin"))):
    data = pipeline.list_docs()
    return {"status": "ok", "data": data}

@app.get("/admin/docs/export")
def admin_export_docs(fmt: str = "json", user: sqlite3.Row = Depends(require_role("admin"))):
    data = pipeline.list_docs()
    if fmt.lower() == "csv":
        headers = ["doc_id", "title", "source", "sha256", "uploaded_at", "chunks"]
        lines = [",".join(headers)]

        def esc(v: str) -> str:
            s = "" if v is None else str(v)
            return '"' + s.replace('"', '""') + '"'

        for r in data:
            row = [esc(r.get(h, "")) for h in headers]
            lines.append(",".join(row))

        csv = "\n".join(lines)
        return PlainTextResponse(csv, media_type="text/csv")

    return JSONResponse({"status": "ok", "data": data})

# -----------------------------------------------------------------------------
# Referrals: create (dedupe) + list/export + update
# -----------------------------------------------------------------------------
@app.post("/referral")
async def raise_referral(
    request: Request,
    reason: str = Form(""),
    question: str = Form(""),
    answer: str = Form(""),
    task_id: Optional[str] = Form(None),
    user: sqlite3.Row = Depends(require_login),
):
    now_iso = datetime.now(timezone.utc).isoformat()
    norm = _norm_question(question)
    items = _read_jsonl(REFERRALS_PATH)

    match = None
    for r in items:
        if _norm_question(r.get("question", "")) == norm:
            match = r
            break

    if match:
        match["count"] = int(match.get("count") or 1) + 1
        match["last_ts"] = now_iso
        # backfill task_id if provided and missing
        if task_id and not match.get("task_id"):
            match["task_id"] = task_id
        inst = match.get("instances") or []
        inst.append({
            "ts": now_iso,
            "reason": reason,
            "answer": answer,
            "by": (user["email"] or ""),
        })
        match["instances"] = inst
        _write_jsonl(REFERRALS_PATH, items)
        return {"status": "ok", "message": "Referral updated (duplicate grouped)", "id": match.get("id")}
    else:
        item = {
            "id": str(uuid.uuid4()),
            "ts": now_iso,
            "last_ts": now_iso,
            "reason": reason,
            "question": question,
            "answer": answer,
            "status": "open",
            "closed_ts": None,
            "count": 1,
            "opened_by": (user["email"] or ""),
            "task_id": task_id or "",
            "instances": [
                {"ts": now_iso, "reason": reason, "answer": answer, "by": (user["email"] or "")}
            ],
        }
        with REFERRALS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return {"status": "ok", "message": "Referral logged", "id": item["id"]}

@app.get("/admin/referrals/data")
def referrals_data(status: Optional[str] = None, user: sqlite3.Row = Depends(require_role("admin"))):
    items = _read_jsonl(REFERRALS_PATH)
    if status in {"open", "closed"}:
        items = [r for r in items if (r.get("status") or "open") == status]
    def sort_key(r: Dict):
        return ((r.get("status") != "open"), -int(r.get("count") or 1), r.get("last_ts") or r.get("ts") or "")
    items.sort(key=sort_key)
    return {"status": "ok", "data": items}

@app.get("/admin/referrals/export")
def referrals_export(fmt: str = "json", status: Optional[str] = None, user: sqlite3.Row = Depends(require_role("admin"))):
    items = _read_jsonl(REFERRALS_PATH)
    if status in {"open", "closed"}:
        items = [r for r in items if (r.get("status") or "open") == status]
    def sort_key(r: Dict):
        return ((r.get("status") != "open"), -int(r.get("count") or 1), r.get("last_ts") or r.get("ts") or "")
    items.sort(key=sort_key)

    if fmt.lower() == "csv":
        headers = ["id", "ts", "last_ts", "status", "closed_ts", "count", "reason", "question", "answer", "opened_by"]
        lines = [",".join(headers)]

        def esc(v: str) -> str:
            s = "" if v is None else str(v)
            return '"' + s.replace('"', '""') + '"'

        for r in items:
            row = [esc(r.get(h, "")) for h in headers]
            lines.append(",".join(row))

        csv = "\n".join(lines)
        return PlainTextResponse(csv, media_type="text/csv")

    return JSONResponse({"status": "ok", "data": items})

# ---------- My Referrals (page + data) ----------
@app.get("/my_referrals")
def my_referrals_page(request: Request, user: sqlite3.Row = Depends(require_login)):
    return templates.TemplateResponse("my_referrals.html", {
        "request": request,
        "user": dict(user),
    })

@app.get("/my_referrals/data")
def my_referrals_data(user: sqlite3.Row = Depends(require_login)):
    email = (user["email"] or "").strip().lower()
    items = _read_jsonl(REFERRALS_PATH)

    # mine = referrals I opened, or where I added an instance
    mine = []
    for r in items:
        opened_by = (r.get("opened_by") or "").strip().lower()
        instances = r.get("instances") or []
        touched = opened_by == email or any((inst.get("by") or "").strip().lower() == email for inst in instances)
        if touched:
            mine.append(r)

    # sort newest activity first
    def _key(rec):
        return rec.get("last_ts") or rec.get("ts") or ""
    mine.sort(key=_key, reverse=True)

    # light payload for the UI
    out = []
    for r in mine:
        # Backward compatibility: if sme_response doesn't exist, check instances for sme_edit
        sme_response = r.get("sme_response", "")
        if not sme_response:
            instances = r.get("instances") or []
            for inst in reversed(instances):  # Check most recent first
                if inst.get("reason") == "(sme_edit)":
                    sme_response = inst.get("answer", "")
                    break
        
        out.append({
            "id": r.get("id", ""),
            "task_id": r.get("task_id", ""),
            "question": r.get("question", ""),
            "answer": r.get("answer", ""),  # Original chatbot response
            "sme_response": sme_response,  # SME's actual response
            "status": r.get("status", "open"),
            "count": int(r.get("count") or 1),
            "ts": r.get("ts", ""),
            "last_ts": r.get("last_ts", ""),
        })
    return {"status": "ok", "data": out}

@app.post("/admin/referrals/update")
async def referrals_update(
    id: str = Form(...),
    status: Optional[str] = Form(None),    # optional
    answer: Optional[str] = Form(None),    # inline editable answer (now saved as sme_response)
    user: sqlite3.Row = Depends(require_role("admin")),
):
    items = _read_jsonl(REFERRALS_PATH)
    now_iso = datetime.now(timezone.utc).isoformat()

    if status is not None:
        s = status.lower().strip()
        if s not in {"open", "closed"}:
            return JSONResponse({"status": "error", "message": "Invalid status"}, status_code=400)
        status = s

    found = False
    for r in items:
        if r.get("id") == id:
            if answer is not None:
                # Save SME response to sme_response field, keep original answer intact
                r["sme_response"] = answer
                r["last_ts"] = now_iso
                inst = r.get("instances") or []
                inst.append({"ts": now_iso, "reason": "(sme_edit)", "answer": answer, "by": user["email"]})
                r["instances"] = inst
            if status is not None:
                r["status"] = status
                if status == "closed":
                    r["closed_ts"] = r.get("closed_ts") or now_iso
                else:
                    r["closed_ts"] = None
            found = True
            break

    if not found:
        return JSONResponse({"status": "error", "message": "Referral not found"}, status_code=404)

    _write_jsonl(REFERRALS_PATH, items)
    return {"status": "ok", "message": "Referral updated"}

# -----------------------------------------------------------------------------
# Feedback capture (+ range filters for analytics)
# -----------------------------------------------------------------------------
@app.post("/feedback")
async def feedback(
    request: Request,
    q: str = Form(...),
    answer: str = Form(""),
    helpful: str = Form(...),
    session_id: str = Form(""),
    user: sqlite3.Row = Depends(require_login),
):
    """
    Records per-answer satisfaction.
    """
    try:
        item = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": q,
            "answer": answer,
            "helpful": helpful.lower() == "true",
            "session": session_id or "",
            "user": request.session.get("email") or "",
        }
        with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

def _apply_range(items: List[Dict], range_code: Optional[str]) -> List[Dict]:
    if not range_code:
        return items
    now = datetime.now(timezone.utc)
    if range_code == "7d":
        since = now - timedelta(days=7)
    elif range_code == "30d":
        since = now - timedelta(days=30)
    elif range_code == "90d":
        since = now - timedelta(days=90)
    else:
        return items
    out = []
    for r in items:
        ts = r.get("ts")
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= since:
                out.append(r)
        except Exception:
            pass
    return out

@app.get("/admin/feedback/data")
def feedback_data(range: Optional[str] = None, user: sqlite3.Row = Depends(require_role("admin"))):
    """
    Returns totals, daily trend, and recent last-50.
    """
    rows = _apply_range(_read_jsonl(FEEDBACK_PATH), range)
    yes = sum(1 for r in rows if r.get("helpful") is True)
    no  = sum(1 for r in rows if r.get("helpful") is False)
    rate = (yes / (yes + no)) if (yes + no) else 0.0

    by_day: Dict[str, Dict[str, int]] = {}
    for r in rows:
        ts = r.get("ts", "")
        key = ts[:10] if len(ts) >= 10 else "unknown"
        b = by_day.setdefault(key, {"yes": 0, "no": 0})
        if r.get("helpful") is True:
            b["yes"] += 1
        elif r.get("helpful") is False:
            b["no"] += 1

    trend = [
        {"date": d, "yes": v["yes"], "no": v["no"]}
        for d, v in sorted(by_day.items(), key=lambda kv: kv[0])
        if d != "unknown"
    ]

    return {
        "status": "ok",
        "totals": {"yes": yes, "no": no, "rate": round(rate, 3)},
        "by_day": trend,
        "recent": rows[-50:],
    }

@app.get("/admin/feedback/export")
def feedback_export(fmt: str = "json", range: Optional[str] = None, user: sqlite3.Row = Depends(require_role("admin"))):
    rows = _apply_range(_read_jsonl(FEEDBACK_PATH), range)

    if fmt.lower() == "csv":
        headers = ["ts", "helpful", "question", "answer", "session", "user"]
        lines = [",".join(headers)]

        def esc(v: str) -> str:
            s = "" if v is None else str(v)
            return '"' + s.replace('"', '""') + '"'

        for r in rows:
            line = ",".join([
                esc(r.get("ts", "")),
                esc("yes" if r.get("helpful") else "no"),
                esc(r.get("question", "")),
                esc(r.get("answer", "")),
                esc(r.get("session", "")),
                esc(r.get("user", "")),
            ])
            lines.append(line)

        csv = "\n".join(lines)
        return PlainTextResponse(csv, media_type="text/csv")

    return JSONResponse({"status": "ok", "data": rows})

# -----------------------------------------------------------------------------
# SME Resolutions (Admin)
# -----------------------------------------------------------------------------
@app.post("/admin/resolutions")
def add_resolution(
    question: str = Form(...),
    answer: str = Form(...),
    approved_by: str = Form("SME"),
    ticket_id: str = Form(""),
    user: sqlite3.Row = Depends(require_role("admin")),
):
    result = pipeline.add_resolution(
        question=question, answer=answer, approved_by=approved_by, ticket_id=ticket_id
    )
    print(f"[admin/resolutions] added qa_id={result.get('qa_id')} ticket_id={ticket_id}")
    return result

@app.get("/admin/resolutions")
def list_resolutions(user: sqlite3.Row = Depends(require_role("admin"))):
    try:
        batch = pipeline.store.qa_collection.get(  # type: ignore[attr-defined]
            where={}, include=["metadatas", "documents"], limit=100_000
        )
        metas_ll = batch.get("metadatas", []) or []
        docs_ll  = batch.get("documents", []) or []
        ids_ll   = batch.get("ids", []) or []

        metas: List[Dict] = []
        docs: List[str] = []
        ids: List[str] = []

        for row in metas_ll:
            if isinstance(row, list): metas.extend(row)
            elif isinstance(row, dict): metas.append(row)
        for row in docs_ll:
            if isinstance(row, list): docs.extend(row)
            elif isinstance(row, str): docs.append(row)
        for row in ids_ll:
            if isinstance(row, list): ids.extend(row)
            elif isinstance(row, str): ids.append(row)

        out = []
        for i, m in enumerate(metas):
            out.append({
                "qa_id": m.get("qa_id", ids[i] if i < len(ids) else ""),
                "title": m.get("title", ""),
                "approved": m.get("approved", True),
                "approved_by": m.get("approved_by", ""),
                "ticket_id": m.get("ticket_id", ""),
                "created_at": m.get("created_at", ""),
                "updated_at": m.get("updated_at", ""),
                "source": m.get("source", "SME resolution"),
                "answer_preview": (docs[i] if i < len(docs) else "")[:240],
            })

        out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return {"status": "ok", "data": out}
    except Exception as e:
        print("[admin/resolutions] list error:", e)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

# --------- Reviewers' "My referrals" (page) ----------
@app.get("/referrals/mine")
def referrals_mine_page(request: Request, user: sqlite3.Row = Depends(require_login)):
    # Any logged-in user can see their own
    return templates.TemplateResponse("my_referrals.html", {"request": request, "user": dict(user)})

# --------- Reviewers' "My referrals" (data) ----------
@app.get("/referrals/mine/data")
def referrals_mine_data(user: sqlite3.Row = Depends(require_login)):
    """
    Returns the open referrals created by the current user (or where they appear in instances).
    Sorted by last_ts desc.
    """
    me = (user["email"] or "").strip().lower()
    items = _read_jsonl(REFERRALS_PATH)

    def _by_me(rec: Dict) -> bool:
        opened = (rec.get("opened_by") or "").strip().lower() == me
        insts = rec.get("instances") or []
        touched = any((i.get("by") or "").strip().lower() == me for i in insts)
        return opened or touched

    open_mine = [r for r in items if (r.get("status") or "open") == "open" and _by_me(r)]

    open_mine.sort(key=lambda r: r.get("last_ts") or r.get("ts") or "", reverse=True)

    # Light payload
    out = [
        {
            "id": r.get("id"),
            "ts": r.get("ts"),
            "last_ts": r.get("last_ts"),
            "question": r.get("question", ""),
            "answer_preview": (r.get("answer", "") or "")[:180],
            "count": int(r.get("count") or 1),
        }
        for r in open_mine
    ]
    return {"status": "ok", "data": out}

@app.get("/admin/resolutions/export")
def export_resolutions(fmt: str = "json", user: sqlite3.Row = Depends(require_role("admin"))):
    try:
        batch = pipeline.store.qa_collection.get(  # type: ignore[attr-defined]
            where={}, include=["metadatas", "documents"], limit=100_000
        )
        metas_ll = batch.get("metadatas", []) or []
        docs_ll  = batch.get("documents", []) or []
        ids_ll   = batch.get("ids", []) or []

        metas: List[Dict] = []
        docs: List[str] = []
        ids: List[str] = []
        for row in metas_ll:
            if isinstance(row, list): metas.extend(row)
            elif isinstance(row, dict): metas.append(row)
        for row in docs_ll:
            if isinstance(row, list): docs.extend(row)
            elif isinstance(row, str): docs.append(row)
        for row in ids_ll:
            if isinstance(row, list): ids.extend(row)
            elif isinstance(row, str): ids.append(row)

        rows = []
        for i, m in enumerate(metas):
            rows.append({
                "qa_id": m.get("qa_id", ids[i] if i < len(ids) else ""),
                "title": m.get("title", ""),
                "approved": m.get("approved", True),
                "approved_by": m.get("approved_by", ""),
                "ticket_id": m.get("ticket_id", ""),
                "created_at": m.get("created_at", ""),
                "updated_at": m.get("updated_at", ""),
                "source": m.get("source", "SME resolution"),
                "answer": docs[i] if i < len(docs) else "",
            })

        if fmt.lower() == "csv":
            headers = ["qa_id", "title", "approved", "approved_by", "ticket_id",
                       "created_at", "updated_at", "source", "answer"]
            lines = [",".join(headers)]

            def esc(v: str) -> str:
                s = "" if v is None else str(v)
                return '"' + s.replace('"', '""') + '"'

            for r in rows:
                lines.append(",".join(esc(r.get(h, "")) for h in headers))

            csv = "\n".join(lines)
            return PlainTextResponse(csv, media_type="text/csv")

        return JSONResponse({"status": "ok", "data": rows})
    except Exception as e:
        print("[admin/resolutions/export] error:", e)
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
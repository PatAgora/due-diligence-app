from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from collections import OrderedDict

# === Global helper utilities for age bucketing (self-contained, no reliance on local closures) ===
from datetime import datetime, date, timedelta
try:
    from dateutil import parser as _dtparser  # type: ignore
except Exception:
    _dtparser = None

def _parse_iso_dt_any(s):
    if not s:
        return None
    try:
        # Handle common ISO formats and strip Z / microseconds
        return datetime.fromisoformat(str(s).replace("Z","").split(".")[0])
    except Exception:
        try:
            if _dtparser:
                return _dtparser.parse(str(s))
        except Exception:
            pass
    return None

def last_touched_date_for_record(r: dict, level: int):
    fields = [
        r.get("updated_at"),
        r.get("date_assigned"),
        r.get("date_completed"),
        r.get("qc_check_date"),
        r.get("sme_selected_date"),
        r.get("sme_returned_date"),
    ]
    dts = [_parse_iso_dt_any(x) for x in fields if x]
    return max(dts) if dts else None

def age_bucket_from_dt(d, today: date=None):
    if today is None:
        today = datetime.utcnow().date()
    if not d:
        return "5 days+"
    days = (today - d.date()).days
    if days <= 2:
        return "1–2 days"
    if days <= 5:
        return "3–5 days"
    return "5 days+"
# === End helpers ===

import sqlite3
from dotenv import load_dotenv
load_dotenv()
import io
import os
load_dotenv("/home/ubuntu/webapp/.env")
from secrets import token_urlsafe
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime, timedelta
import bcrypt
import smtplib
from email.message import EmailMessage
from flask import current_app
import random
import string
import csv
import pandas as pd
from flask import send_file
from flask import Response
from functools import wraps
import json
from types import SimpleNamespace
from flask_wtf.csrf import generate_csrf
import re
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from dateutil import parser
from flask import render_template, session
from utils import derive_case_status, ReviewStatus, best_status_with_raw_override
from datetime import datetime, timedelta, date
from utils import derive_case_status
derive_status = derive_case_status
from typing import Optional
from collections import Counter, defaultdict
from typing import Optional
from dateutil import parser as dtparser
from typing import Optional, Union
from urllib.parse import quote, urlparse
from collections import defaultdict
import requests
import hashlib
import hmac
import time
def derive_status(record, *_args, **_kwargs):
    """Compat wrapper: ignore any extra args and call the flat helper."""
    return derive_case_status(record)

def is_task_in_sme_referral_status(task_id: str, conn=None):
    """
    Check if a task is in "Referred to SME" or "Referred to AI SME" status.
    Returns (is_in_referral, error_message)
    If is_in_referral is True, the task should be locked from status changes.
    """
    if conn is None:
        conn = get_db()
        should_close = True
    else:
        should_close = False
    
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT status, sme_returned_date FROM reviews WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        
        if not row:
            return (False, None)
        
        # Convert Row to dict to use .get() method
        row_dict = dict(row)
        status = str(row_dict.get('status') or '').strip().lower()
        sme_returned_date = row_dict.get('sme_returned_date')
        
        # Check if task is in SME referral status (and not yet returned)
        is_referred_to_sme = (
            'referred to sme' in status and 'ai' not in status
        ) or (
            'referred to ai sme' in status
        )
        
        # Only block if referred AND not yet returned (sme_returned_date is None/blank)
        if is_referred_to_sme and not sme_returned_date:
            if 'referred to ai sme' in status:
                return (True, "Task is currently referred to AI SME. Please wait for SME response before making changes.")
            else:
                return (True, "Task is currently referred to SME. Please wait for SME response before making changes.")
        
        return (False, None)
    finally:
        if should_close:
            conn.close()


# ==================== AI OUTREACH QUESTION GENERATION ====================

def generate_ai_outreach_questions(customer_id, alerts):
    """
    Generate AI Outreach questions using OpenAI GPT based on actual transaction alerts.
    
    Args:
        customer_id: Customer ID
        alerts: List of alert records from database
    
    Returns:
        List of dicts with 'tag' and 'question' keys
    """
    import os
    import yaml
    import json
    from openai import OpenAI
    
    # Load OpenAI config
    config_path = os.path.expanduser("~/.genspark_llm.yaml")
    config = None
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    # Initialize OpenAI client
    client = OpenAI(
        api_key=config.get('openai', {}).get('api_key') if config else os.getenv('OPENAI_API_KEY'),
        base_url=config.get('openai', {}).get('base_url') if config else os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    )
    
    # Format alerts for LLM
    alert_descriptions = []
    for i, alert in enumerate(alerts, 1):
        # Convert to dict with column names as keys
        alert_dict = dict(alert) if hasattr(alert, 'keys') else {
            'id': alert[0], 'txn_id': alert[1], 'score': alert[2], 'severity': alert[3],
            'reasons': alert[4], 'rule_tags': alert[5], 'txn_date': alert[6], 'amount': alert[7],
            'currency': alert[8], 'country_iso2': alert[9], 'direction': alert[10], 'narrative': alert[11]
        }
        
        # Format date
        txn_date = alert_dict.get('txn_date', '')
        if isinstance(txn_date, str) and len(txn_date) >= 10:
            try:
                from datetime import datetime
                dt = datetime.strptime(txn_date[:10], '%Y-%m-%d')
                formatted_date = dt.strftime('%d/%m/%Y')
            except:
                formatted_date = txn_date
        else:
            formatted_date = str(txn_date)
        
        alert_desc = f"""Alert {i}:
- Transaction ID: {alert_dict.get('txn_id', 'N/A')}
- Date: {formatted_date}
- Amount: {alert_dict.get('currency', 'GBP')} {alert_dict.get('amount', 0):.2f}
- Country: {alert_dict.get('country_iso2', 'N/A')}
- Direction: {alert_dict.get('direction', 'N/A')}
- Severity: {alert_dict.get('severity', 'N/A')} (Score: {alert_dict.get('score', 0)})
- Reasons: {alert_dict.get('reasons', 'N/A')}
- Rule Tags: {alert_dict.get('rule_tags') or 'N/A'}"""
        
        if alert_dict.get('narrative'):
            alert_desc += f"\n- Transaction Narrative: {alert_dict['narrative']}"
        
        alert_descriptions.append(alert_desc)
    
    alerts_text = "\n\n".join(alert_descriptions)
    
    # Create LLM prompt
    prompt = f"""You are a financial crime compliance analyst creating customer outreach questions for transaction alerts.

CUSTOMER ID: {customer_id}

TRANSACTION ALERTS:
{alerts_text}

TASK:
Generate 3-5 specific, professional questions to ask the customer about these alerts. Each question should:
1. Reference specific transactions (dates, amounts)
2. Address the alert reasons directly
3. Be clear and professional
4. Request explanations or supporting documentation
5. Be suitable for customer outreach emails

IMPORTANT GUIDELINES:
- Prioritize CRITICAL and HIGH severity alerts
- Group similar alerts (e.g., multiple high-value transactions) into one question
- Be specific with dates and amounts
- Don't be accusatory - remain professional and neutral
- Focus on understanding the business purpose and legitimacy

OUTPUT FORMAT (JSON):
Return a JSON array of question objects. Each object must have:
- "tag": A short category tag (e.g., "PROHIBITED_COUNTRY", "HIGH_VALUE", "PATTERN_CHANGE", "UNUSUAL_NARRATIVE")
- "question": The full question text

Example format:
[
  {{"tag": "PROHIBITED_COUNTRY", "question": "Can you explain the transaction of £2,011.43 on 23/12/2025 to Iran? Please provide supporting documentation for this payment."}},
  {{"tag": "HIGH_VALUE", "question": "What was the purpose of the following high-value transactions: £4,220.71 on 20/12/2025 and £4,723.43 on 11/11/2025?"}}
]

Return ONLY the JSON array, no additional text."""

    try:
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a financial crime compliance analyst. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Extract JSON if wrapped in markdown code blocks
        if content.startswith("```"):
            # Remove markdown code block formatting
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        questions = json.loads(content)
        
        # Validate structure
        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("Invalid response format from LLM")
        
        # Ensure each question has required fields
        valid_questions = []
        for q in questions:
            if isinstance(q, dict) and 'tag' in q and 'question' in q:
                valid_questions.append({
                    "tag": str(q['tag']).strip(),
                    "question": str(q['question']).strip()
                })
        
        if len(valid_questions) == 0:
            raise ValueError("No valid questions generated")
        
        print(f"✅ Generated {len(valid_questions)} AI questions for {customer_id}")
        return valid_questions[:5]  # Limit to max 5 questions
        
    except Exception as e:
        print(f"❌ Error calling OpenAI API: {str(e)}")
        raise


def generate_fallback_questions(alerts):
    """
    Generate simple fallback questions if LLM fails.
    Uses rule-based logic based on alert severity and reasons.
    """
    questions = []
    
    # Convert alerts to list of dicts with proper column names
    alert_list = []
    for alert in alerts:
        if hasattr(alert, 'keys'):
            alert_dict = dict(alert)
        else:
            alert_dict = {
                'id': alert[0], 'txn_id': alert[1], 'score': alert[2], 'severity': alert[3],
                'reasons': alert[4], 'rule_tags': alert[5], 'txn_date': alert[6], 'amount': alert[7],
                'currency': alert[8], 'country_iso2': alert[9], 'direction': alert[10], 'narrative': alert[11]
            }
        alert_list.append(alert_dict)
    
    # Sort by severity: CRITICAL > HIGH > MEDIUM > LOW
    severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    alert_list.sort(key=lambda a: (severity_order.get(a.get('severity', ''), 999), -a.get('score', 0)))
    
    seen_tags = set()
    
    for alert_dict in alert_list[:5]:  # Max 5 questions
        reasons = alert_dict.get('reasons', '').lower()
        amount = f"{alert_dict.get('currency', 'GBP')}{alert_dict.get('amount', 0):.2f}"
        txn_date = str(alert_dict.get('txn_date', ''))[:10]
        
        # Format date
        try:
            from datetime import datetime
            dt = datetime.strptime(txn_date, '%Y-%m-%d')
            formatted_date = dt.strftime('%d/%m/%Y')
        except:
            formatted_date = txn_date
        
        # Determine question tag and text based on reasons
        if 'prohibited' in reasons or 'sanction' in reasons or 'iran' in reasons:
            if 'PROHIBITED' not in seen_tags:
                questions.append({
                    "tag": "PROHIBITED_COUNTRY",
                    "question": f"Can you explain the transaction of {amount} on {formatted_date}? Please provide supporting documentation and business justification for this payment."
                })
                seen_tags.add('PROHIBITED')
        
        elif 'exceeds' in reasons or 'high' in reasons or 'enhanced due diligence' in reasons:
            if 'HIGH_VALUE' not in seen_tags:
                # Group high-value transactions
                high_value_alerts = [a for a in alert_list if 'exceeds' in str(a.get('reasons', '')).lower() or 'enhanced due diligence' in str(a.get('reasons', '')).lower()]
                if len(high_value_alerts) > 1:
                    txns = ", ".join([f"{a.get('currency', 'GBP')}{a.get('amount', 0):.2f} on {str(a.get('txn_date', ''))[:10]}" for a in high_value_alerts[:3]])
                    questions.append({
                        "tag": "HIGH_VALUE",
                        "question": f"What is the purpose of the following high-value transactions: {txns}?"
                    })
                else:
                    questions.append({
                        "tag": "HIGH_VALUE",
                        "question": f"Can you explain the purpose of the transaction of {amount} on {formatted_date}?"
                    })
                seen_tags.add('HIGH_VALUE')
        
        elif 'pattern' in reasons or 'differs' in reasons or 'unusual' in reasons:
            if 'PATTERN' not in seen_tags:
                questions.append({
                    "tag": "PATTERN_CHANGE",
                    "question": f"Can you explain why the transaction of {amount} on {formatted_date} differs from your normal account activity?"
                })
                seen_tags.add('PATTERN')
        
        elif 'cash' in reasons:
            if 'CASH' not in seen_tags:
                questions.append({
                    "tag": "CASH_TRANSACTION",
                    "question": f"Please provide details about the cash transaction of {amount} on {formatted_date}."
                })
                seen_tags.add('CASH')
        
        else:
            # Generic question
            if 'GENERIC' not in seen_tags:
                questions.append({
                    "tag": "TRANSACTION_ENQUIRY",
                    "question": f"Can you provide more information about the transaction of {amount} on {formatted_date}?"
                })
                seen_tags.add('GENERIC')
    
    # Ensure at least one question
    if len(questions) == 0 and len(alert_list) > 0:
        alert_dict = alert_list[0]
        amount = f"{alert_dict.get('currency', 'GBP')}{alert_dict.get('amount', 0):.2f}"
        txn_date = str(alert_dict.get('txn_date', ''))[:10]
        questions.append({
            "tag": "GENERAL",
            "question": f"Can you provide more information about the transaction of {amount} on {txn_date}?"
        })
    
    print(f"⚠️ Generated {len(questions)} fallback questions (LLM unavailable)")
    return questions

# ==================== END AI OUTREACH QUESTION GENERATION ====================


app = Flask(__name__)

# --- UI helpers for reviewer panel (added) ---
def _safe_review(rec: dict) -> dict:
    """Return a defensive copy of review with all new keys present (UI-safe)."""
    rec = dict(rec or {})
    # New fields used by template
    rec.setdefault('currentriskrating', '')
    rec.setdefault('case_summary', '')
    # DDG fields (new names as checkboxes/text areas may map here later)
    for key in ['idv','nob','income','structure','ta','sof','sow']:
        rec.setdefault(f'ddg_{key}_rationale', rec.get(f'{key}_rationale',''))
        rec.setdefault(f'ddg_{key}_outreach_required', rec.get(f'ddg_{key}_certified', 0))
        rec.setdefault(f'ddg_{key}_section_complete', rec.get(f'ddg_{key}_ok', 0))
    return rec
app.secret_key = os.getenv("SECRET_KEY")
app.config['SESSION_COOKIE_SECURE'] = False  # False for localhost development
app.config['SESSION_COOKIE_HTTPONLY'] = True     # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'    # Use 'Lax' for localhost, 'None' requires Secure=True
app.config['SESSION_COOKIE_DOMAIN'] = None       # Don't restrict domain for localhost
app.config['SESSION_COOKIE_PATH'] = '/'           # Available for all paths
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Session expires in 24 hours

app.config['WTF_CSRF_ENABLED'] = True
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

csrf = CSRFProtect(app)

# Handle CORS manually - allow all origins for development
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        from flask import Response
        origin = request.headers.get('Origin')
        response = Response()
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, Accept, Origin, X-Requested-With'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

# Ensure CORS headers are added to all responses, including errors
@app.after_request
def after_request(response):
    # Add CORS headers to all responses - allow all origins for development
    origin = request.headers.get('Origin')
    if origin:
        # Use the requesting origin (required when credentials=true)
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    else:
        # Fallback to wildcard if no origin header
        response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, Accept, Origin, X-Requested-With'
    response.headers['Access-Control-Expose-Headers'] = 'Set-Cookie, Content-Type'
    
    # Debug: Log session info for API requests
    if request.path.startswith('/api/'):
        print(f"[DEBUG] after_request {request.path} - Session: user_id={session.get('user_id')}, keys={list(session.keys())}")
    
    return response

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    # Check if this is an API request
    wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                request.path.startswith('/api/')
    if wants_json:
        from flask import jsonify
        response = jsonify({'error': 'CSRF token missing or invalid'})
        response.status_code = 400
        return response
    return render_template('csrf_error.html', reason=e.description), 400

@app.context_processor
def inject_globals():
    print("[CSRF] Injecting csrf_token, now, and timedelta into context")
    return {
        'csrf_token': generate_csrf,
        'now': datetime.utcnow,
        'timedelta': timedelta,
    }

@app.context_processor
def utility_processor():
    from flask import url_for
    def safe_url(endpoint, **values):
        try:
            return url_for(endpoint, **values)
        except Exception:
            return "#"
    return dict(safe_url=safe_url)

def get_rca_options():
    return [
        'False Positive – Name mismatch',
        'False Positive – Date of Birth mismatch',
        'False Positive – Country mismatch',
        'True Match – Escalated',
        'Refer to SME – Jurisdictional issue'
    ]

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask import current_app

def _send_reset_email(to_email: str, reset_url: str):
    msg = Mail(
        from_email=os.getenv("FROM_EMAIL"),
        to_emails=to_email,
        subject="Scrutinise – Reset your password",
        html_content=f"""
            <p>We received a request to reset your password.</p>
            <p><a href="{reset_url}">Click here to reset it</a>.</p>
            <p>If you didn’t request this, you can ignore this email.</p>
        """
    )
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    resp = sg.send(msg)
    # Log for visibility (you should see 202 on success)
    current_app.logger.info("SendGrid reset email resp: %s", resp.status_code)
    return resp.status_code

def _send_welcome_email(to_email: str, setup_url: str):
    msg = Mail(
        from_email=os.getenv("FROM_EMAIL"),
        to_emails=to_email,
        subject="Welcome to Scrutinise – Set up your password",
        html_content=f"""
            <p>Welcome to <strong>Scrutinise</strong>!</p>
            <p>To activate your account, please create your password:</p>
            <p><a href="{setup_url}">Set your password</a></p>
            <p>This secure link expires in {TOKEN_TTL_MINUTES} minutes.</p>
        """
    )
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    return sg.send(msg).status_code

def _send_2fa_code_email(to_email: str, code: str):
    """Send 2FA verification code via email"""
    msg = Mail(
        from_email=os.getenv("FROM_EMAIL"),
        to_emails=to_email,
        subject="Scrutinise – Your Two-Factor Authentication Code",
        html_content=f"""
            <p>Your two-factor authentication code is:</p>
            <h2 style="font-size: 32px; letter-spacing: 4px; color: #ff6a00; margin: 20px 0;">{code}</h2>
            <p>This code will expire in 10 minutes.</p>
            <p>If you didn't request this code, please ignore this email or contact support.</p>
        """
    )
    sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    resp = sg.send(msg)
    current_app.logger.info("SendGrid 2FA code email resp: %s", resp.status_code)
    return resp.status_code

def issue_reset_link_and_email(user_id: int, email: str):
    """Create a one-time reset token for a user and email them the setup link."""
    token = secrets.token_urlsafe(32)
    token_hash = _sha256(token)
    expires_at = (datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat() + "Z"

    conn = _get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO password_resets (user_id, token_hash, expires_at, requested_ip, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id, token_hash, expires_at,
        "signup",                             # requested_ip source marker
        "system:new_user_invite",            # UA marker
        datetime.utcnow().isoformat() + "Z"
    ))
    conn.commit()
    conn.close()

    reset_url = f"{APP_BASE_URL}{url_for('reset_password', token=token)}"
    _send_reset_email(email, reset_url)


ENV = os.environ.get("FLASK_ENV", "development")

DB_PATH = 'scrutinise_workflow.db'

app.config["PROPAGATE_EXCEPTIONS"] = False
app.config["DEBUG"] = False
# app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "fallback_insecure_key")

# Restrict accepted host headers to your domain (prevents Host Header attacks)
app.config["SERVER_NAME"] = os.getenv("FLASK_SERVER_NAME", None)

def get_db():
    import os
    # Get absolute path to database file to ensure we're using the correct database
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_PATH)
    conn = sqlite3.connect(db_path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    try:
        conn.execute('PRAGMA journal_mode=WAL')
    except:
        pass  # Ignore if WAL mode can't be enabled
    return conn

# --- Outcome options loader -------------------------------------------------

# --- Outcomes loader (strict) -------------------------------------------------
def _load_outcomes_from_db(cur_or_conn):
    """Return list of outcome strings from scrutinise_workflow.db
    using table `outcomes` and column `outcome`.
    If unavailable, fall back to the specified static list.
    """
    DEFAULTS = [
        "Retain",
        "Exit - Financial Crime",
        "Exit - Non-responsive",
        "Exit - T&C",
    ]
    try:
        # Get a cursor regardless of arg type
        if hasattr(cur_or_conn, "execute"):
            cur = cur_or_conn
        else:
            cur = cur_or_conn.cursor()

        # Verify table exists
        cur.execute("""
            SELECT name FROM sqlite_master
             WHERE type='table' AND LOWER(name)='outcomes'
            LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return DEFAULTS

        # Try to read the specific column `outcome`
        try:
            cur.execute("SELECT outcome FROM outcomes ORDER BY 1")
        except Exception:
            # Column missing -> fallback
            return DEFAULTS

        rows = cur.fetchall()
        items = []
        for r in rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            if ro.lower() != _outcome.lower():
                continue
            # sqlite3.Row or tuple
            val = r[0] if isinstance(r, tuple) else (r["outcome"] if "outcome" in r.keys() else list(r.values())[0])
            s = (str(val) if val is not None else "").strip()
            if s:
                items.append(s)
        return items or DEFAULTS
    except Exception:
        return DEFAULTS
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            role = session.get("role", "")
            print("Session role is:", role)
            if not any(role == r or role.startswith(r + "_") for r in roles):
                return "Access denied", 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

def check_permission(feature, action='view'):
    """
    Check if the current user has permission for a feature.
    Returns True if allowed, False if denied.
    If no permission entry exists, defaults to True (backward compatibility).
    
    For "review_tasks", also checks "review" as a fallback (in case database uses "review").
    
    IMPORTANT: Admin role always has full access and cannot be restricted.
    """
    role = session.get("role", "").lower()
    if not role:
        return False
    
    # Admin always has full access - cannot be restricted
    if role == 'admin':
        return True
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Check for exact role match first
        if action == 'view':
            cur.execute("""
                SELECT can_view FROM permissions 
                WHERE role = ? AND feature = ?
            """, (role, feature))
        else:
            cur.execute("""
                SELECT can_edit FROM permissions 
                WHERE role = ? AND feature = ?
            """, (role, feature))
        
        result = cur.fetchone()
        
        # If not found and feature is "review_tasks", also check "review" (backward compatibility)
        if not result and feature == 'review_tasks':
            if action == 'view':
                cur.execute("""
                    SELECT can_view FROM permissions 
                    WHERE role = ? AND feature = ?
                """, (role, 'review'))
            else:
                cur.execute("""
                    SELECT can_edit FROM permissions 
                    WHERE role = ? AND feature = ?
                """, (role, 'review'))
            result = cur.fetchone()
        
        conn.close()
        
        if result:
            # Permission entry exists - use it
            return bool(result[0])
        else:
            # No permission entry - default to allow (backward compatibility)
            return True
    except Exception as e:
        print(f"Error checking permission: {e}")
        # On error, default to allow
        return True

def permission_required(feature, action='view'):
    """
    Decorator to require a specific permission for a route.
    Similar to role_required but uses the permissions table.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not check_permission(feature, action):
                return jsonify({'error': f'Permission denied: {action} access to {feature}'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

def generate_random_password(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def is_strong_password(password):
    return (len(password) >= 10 and
            re.search(r"[A-Z]", password) and
            re.search(r"[a-z]", password) and
            re.search(r"\d", password) and
            re.search(r"\W", password))

def send_invite_email(to_email, temp_password):
    msg = EmailMessage()
    msg["Subject"] = "Your Scrutinise Account Access"
    msg["From"] = os.getenv("SMTP_USER")
    msg["To"] = to_email
    msg.set_content(f"""\
Welcome to Scrutinise!

You’ve been invited to join the platform.
Login at: https://scrutinise.co.uk/login
Use the following temporary password: {temp_password}

Please change your password after first login.

Regards,
Scrutinise Admin
""")
    with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as smtp:
        smtp.starttls()
        smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        smtp.send_message(msg)

def get_db_connection():
    import os
    # Get absolute path to database file to ensure we're using the correct database
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_setting(key, default):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cur.fetchone()
        conn.close()
        return int(result[0]) if result else default
    except:
        return default

def score_class(score):
    if score is None:
        return "text-muted"
    if score >= 0.85:
        return "text-success"
    elif score >= 0.6:
        return "text-warning"
    else:
        return "text-danger"

from utils import derive_case_status

def apply_qc_sampling():
    """
    Automatically mark a random sample of completed reviews for QC by inserting into qc_sampling_log.
    
    Uses sampling_rates table to determine what % of each reviewer's work should be QC'd.
    Only applies to non-accredited reviewers (accredited reviewers are exempt from QC).
    """
    import random
    import sqlite3
    
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    # 1) Get global & per-reviewer sampling rates (single level - no level filtering)
    # Global rate: reviewer_id IS NULL
    cur.execute("SELECT rate FROM sampling_rates WHERE reviewer_id IS NULL LIMIT 1")
    row = cur.fetchone()
    global_rate = row["rate"] if row else 10  # Default 10% if not configured

    # Reviewer-specific rates: reviewer_id IS NOT NULL
    cur.execute("SELECT reviewer_id, rate FROM sampling_rates WHERE reviewer_id IS NOT NULL")
    reviewer_rates = {r["reviewer_id"]: r["rate"] for r in cur.fetchall()}

    # 2) Get accredited reviewers (exempt from QC)
    cur.execute("SELECT reviewer_id FROM reviewer_accreditation WHERE is_accredited = 1")
    accredited = {r["reviewer_id"] for r in cur.fetchall()}

    # 3) Fetch completed reviews not yet sampled
    cur.execute("""
        SELECT r.id, r.assigned_to AS reviewer_id, r.task_id
        FROM reviews r
        LEFT JOIN qc_sampling_log q ON q.review_id = r.id
        WHERE r.assigned_to IS NOT NULL
          AND r.date_completed IS NOT NULL
          AND r.date_completed != ''
          AND q.review_id IS NULL
    """)
    candidates = cur.fetchall()

    sampled = 0
    skipped_reasons = {
        'accredited': 0,
        'not_completed': 0,
        'already_sampled': 0,
        'rate_not_met': 0
    }
    
    for rec in candidates:
        review_id   = rec["id"]
        reviewer_id = rec["reviewer_id"]
        task_id     = rec["task_id"]

        # Skip accredited reviewers (they don't need QC)
        if reviewer_id in accredited:
            skipped_reasons['accredited'] += 1
            continue

        # Check if task is actually completed (not just date_completed set)
        cur.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        review_row = cur.fetchone()
        if not review_row:
            continue
            
        review = dict(review_row)
        # Add _in_qc_sampling flag for status derivation
        review['_in_qc_sampling'] = False
        status = derive_case_status(review)
        if status != "Completed":
            skipped_reasons['not_completed'] += 1
            continue

        # Apply sampling rate
        rate = reviewer_rates.get(reviewer_id, global_rate)
        if rate <= 0:
            skipped_reasons['rate_not_met'] += 1
            continue
            
        if random.random() < rate/100.0:
            try:
                cur.execute("""
                    INSERT INTO qc_sampling_log (review_id, reviewer_id, task_id, sampled_at)
                    VALUES (?, ?, ?, datetime('now'))
                """, (review_id, reviewer_id, task_id))
                
                # Update status to "QC - Awaiting Allocation"
                review['_in_qc_sampling'] = True
                new_status = derive_case_status(review)
                cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
                
                sampled += 1
            except Exception as e:
                # Skip if already sampled (duplicate key)
                skipped_reasons['already_sampled'] += 1
                print(f"Skipping {task_id}: {e}")
                continue
        else:
            skipped_reasons['rate_not_met'] += 1

    conn.commit()
    conn.close()
    
    print(f"[QC Sampling] Flagged {sampled} reviews for QC")
    print(f"[QC Sampling] Skipped: {skipped_reasons}")
    
    return sampled

def _dt_any(s):
    if not s:
        return None
    s = str(s).strip()
    try:
        return datetime.fromisoformat(s.replace("Z","").split(".")[0])
    except Exception:
        try:
            from dateutil import parser as P
            return P.parse(s)
        except Exception:
            return None

def compute_sme_panel(review: dict, default_level: int) -> dict:
    """
    Decide which level's SME context to show and return the data for it.
    Priority:
      1) latest returned_date across levels
      2) latest selected_date across levels
      3) else: default_level (usually the current review level)
    """
    per = []
    for lv in (1, 2, 3):
        per.append({
            "lv": lv,
            "selected": _dt_any(review.get(f"l{lv}_sme_selected_date")),
            "returned": _dt_any(review.get(f"l{lv}_sme_returned_date")),
            "query":    (review.get(f"l{lv}_sme_query") or "").strip(),
            "advice":   (review.get(f"l{lv}_sme_response") or "").strip(),
            "referred": bool(review.get(f"l{lv}_referred_to_sme")),
            "sme_id":   review.get(f"l{lv}_sme_assigned_to"),
        })

    # 1) pick by latest returned
    returned = [p for p in per if p["returned"]]
    if returned:
        returned.sort(key=lambda x: x["returned"], reverse=True)
        chosen = returned[0]
    else:
        # 2) else pick by latest selected
        selected = [p for p in per if p["selected"]]
        if selected:
            selected.sort(key=lambda x: x["selected"], reverse=True)
            chosen = selected[0]
        else:
            # 3) else default
            chosen = next((p for p in per if p["lv"] == default_level), per[0])

    # build result
    return {
        "level":      chosen["lv"],
        "query":      chosen["query"],
        "advice":     chosen["advice"],
        "returned":   chosen["returned"],
        "selected":   chosen["selected"],
        "referred":   chosen["referred"],
        "sme_user_id":chosen["sme_id"],
        "has_any":    any((
                        chosen["referred"],
                        chosen["query"],
                        chosen["advice"],
                        chosen["returned"],
                        chosen["selected"],
                      )),
    }


from werkzeug.security import check_password_hash

import bcrypt

from flask import request, render_template, redirect, url_for, session, flash
import sqlite3
import bcrypt

from werkzeug.security import check_password_hash
import sqlite3
from flask import request, render_template, redirect, url_for, session, flash

from flask import request, session, redirect, url_for, render_template, flash
from werkzeug.security import check_password_hash
import sqlite3

# --- Password reset routes (inline) ---
import secrets, hashlib, hmac
from datetime import datetime, timedelta
import sendgrid
from sendgrid.helpers.mail import Mail

DB_PATH = os.environ.get("DB_PATH", "scrutinise_workflow.db")
TOKEN_TTL_MINUTES = int(os.environ.get("PWD_RESET_TOKEN_TTL_MINUTES", 30))
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5050")

def _sha256(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _send_reset_email(to_email, reset_url):
    sg = sendgrid.SendGridAPIClient(api_key=os.environ["SENDGRID_API_KEY"])
    from_email = os.environ.get("FROM_EMAIL", "support@scrutinise.app")
    msg = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject="Reset your Scrutinise password",
        html_content=f"""
        <p>Hello,</p>
        <p>We received a request to reset your Scrutinise password.</p>
        <p><a href="{reset_url}">Reset your password</a></p>
        <p>This link expires in {TOKEN_TTL_MINUTES} minutes.</p>
        """
    )
    sg.send(msg)

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure the table exists at startup
with _get_db() as c:
    c.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            requested_ip TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
    """)

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = (request.form.get("email") or "").strip().lower()
    generic_msg = "If that email is registered, we've sent a reset link."

    conn = _get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE lower(email)=? LIMIT 1", (email,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return redirect(url_for("reset_email_sent", email=email))

    user_id = row["id"]
    token = secrets.token_urlsafe(32)
    token_hash = _sha256(token)
    expires_at = (datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat() + "Z"
    cur.execute("""
        INSERT INTO password_resets (user_id, token_hash, expires_at, requested_ip, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id, token_hash, expires_at,
        request.headers.get("X-Forwarded-For", request.remote_addr),
        request.headers.get("User-Agent", ""),
        datetime.utcnow().isoformat() + "Z"
    ))
    conn.commit()
    conn.close()

    reset_url = f"{APP_BASE_URL}{url_for('reset_password', token=token)}"
    try:
        _send_reset_email(email, reset_url)
    except Exception as e:
        current_app.logger.exception("SendGrid error: %s", e)

    return redirect(url_for("reset_email_sent", email=email))

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Validate a reset token; render the form or save the new password."""
    token_hash = _sha256(token)
    now_iso = datetime.utcnow().isoformat() + "Z"

    conn = _get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT pr.id, pr.user_id, pr.expires_at, pr.used_at, u.email
        FROM password_resets pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.token_hash=? ORDER BY pr.id DESC LIMIT 1
    """, (token_hash,))
    rec = cur.fetchone()

    if not rec:
        conn.close()
        current_app.logger.info("Reset password: no record found for token_hash=%s", token_hash)
        return render_template("reset_problem.html",
                               title="Invalid link",
                               message="That password reset link is invalid. Please request a new one."), 400

    pr_id, user_id, expires_at, used_at, email = rec

    if used_at:
        conn.close()
        current_app.logger.info("Reset password: token already used (pr_id=%s, user_id=%s)", pr_id, user_id)
        return render_template("reset_problem.html",
                               title="Link already used",
                               message="This password reset link has already been used. Please request a new one if needed."), 400

    try:
        expired = datetime.utcnow() > datetime.fromisoformat(expires_at.replace("Z", ""))
    except Exception:
        expired = True  # if expires_at is malformed, treat as expired

    if expired:
        conn.close()
        current_app.logger.info("Reset password: token expired (pr_id=%s, user_id=%s, expires_at=%s)", pr_id, user_id, expires_at)
        return render_template("reset_problem.html",
                               title="Link expired",
                               message="This password reset link has expired. Please request a new one."), 400

    # GET → show the form
    if request.method == "GET":
        current_app.logger.info("Reset password: rendering form (pr_id=%s, user_id=%s)", pr_id, user_id)
        return render_template("reset_password.html", email=email)

    # POST → validate and set the new password
    pw  = (request.form.get("password") or "").strip()
    pw2 = (request.form.get("confirm_password") or "").strip()

    # basic rules; mirror whatever strength rules you want to enforce
    if pw != pw2 or len(pw) < 12:
        current_app.logger.info("Reset password: validation failed (mismatch/length) for user_id=%s", user_id)
        flash("Passwords must match and be at least 12 characters.", "danger")
        return render_template("reset_password.html", email=email), 400

    pw_hash = generate_password_hash(pw)
    cur.execute("UPDATE users SET password_hash=?, password_changed_at=? WHERE id=?",
                (pw_hash, now_iso, user_id))
    cur.execute("UPDATE password_resets SET used_at=? WHERE id=?",
                (now_iso, pr_id))
    conn.commit()
    conn.close()

    session.clear()
    current_app.logger.info("Reset password: success for user_id=%s (pr_id=%s)", user_id, pr_id)
    return redirect(url_for("reset_done"))

@app.route("/reset_email_sent")
def reset_email_sent():
    return render_template("reset_email_sent.html", email=request.args.get("email"))

@app.route("/reset_done")
def reset_done():
    return render_template("reset_success.html")

@app.template_filter('friendly_role')
def friendly_role(role):
    role_map = {
        'admin': 'Admin',
        'team_lead_1': 'Team Lead (Level 1)',
        'team_lead_2': 'Team Lead (Level 2)',
        'team_lead_3': 'Team Lead (Level 3)',
        'qc_1': 'QC Lead (Level 1)',
        'qc_2': 'QC Lead (Level 2)',
        'qc_3': 'QC Lead (Level 3)',
        'qa_1': 'QA Lead (Level 1)',
        'qa_2': 'QA Lead (Level 2)',
        'qa_3': 'QA Lead (Level 3)',
        'reviewer_1': 'Reviewer (Level 1)',
        'reviewer_2': 'Reviewer (Level 2)',
        'reviewer_3': 'Reviewer (Level 3)',
        'qc': 'Quality Control',
        'qa': 'Quality Assurance',
        'sme': 'Subject Matter Expert',
        'operations_manager': 'Operations Manager',
    }
    return role_map.get(role, role.replace('_', ' ').title())

@app.route('/login', methods=['GET', 'POST', 'OPTIONS'])
@csrf.exempt  # Exempt from CSRF for API requests
def login():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    if request.method == 'POST':
        email    = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # Skip 2FA for admin@scrutinise.co.uk
            email_lower = email.lower().strip()
            skip_2fa = email_lower == 'admin@scrutinise.co.uk'
            
            # Check if 2FA is enabled for this user
            # sqlite3.Row access - check if key exists first
            two_factor_enabled_val = user['two_factor_enabled'] if 'two_factor_enabled' in user.keys() else 0
            two_factor_enabled = bool(two_factor_enabled_val) and not skip_2fa
            
            if two_factor_enabled:
                # Generate 6-digit code
                import random
                code = str(random.randint(100000, 999999))
                
                # Store code and expiration in database (10 minutes)
                from datetime import datetime, timedelta
                expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat() + "Z"
                
                cursor.execute("""
                    UPDATE users 
                    SET two_factor_code = ?, two_factor_expires = ?
                    WHERE id = ?
                """, (code, expires_at, user['id']))
                conn.commit()
                
                # Send 2FA code via email
                try:
                    _send_2fa_code_email(email, code)
                except Exception as e:
                    current_app.logger.exception("Failed to send 2FA code: %s", e)
                    flash("Failed to send 2FA code. Please try again.", "danger")
                    conn.close()
                    wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                                request.args.get('format') == 'json'
                    if wants_json:
                        return jsonify({'success': False, 'error': 'Failed to send 2FA code', 'requires_2fa': True}), 401
                    return redirect(url_for('login'))
                
                # Store user info in session temporarily (not fully authenticated yet)
                session['pending_user_id'] = user['id']
                session['pending_email'] = email
                session['pending_role'] = (user['role'] or '').lower()
                session['pending_level'] = user['level']
                session['pending_name'] = (user['name'] or user['email'])
                session['2fa_required'] = True
                conn.close()
                
                # Check if JSON response is requested
                wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                            request.args.get('format') == 'json'
                if wants_json:
                    return jsonify({
                        'success': False,
                        'requires_2fa': True,
                        'message': '2FA code sent to your email'
                    }), 200
                
                # Redirect to 2FA verification page
                return redirect(url_for('verify_2fa'))
            
            # No 2FA required - proceed with normal login
            role = (user['role'] or '').lower()

            # Update last_active timestamp
            from datetime import datetime
            cursor.execute(
                "UPDATE users SET last_active = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user['id'])
            )
            conn.commit()

            # Session essentials (+ name for SME advice signature)
            session['user_id'] = user['id']
            session['role']    = role
            session['level']   = user['level']           # keep level in session
            session['email']   = user['email']
            session['name']    = (user['name'] or user['email'])  # ← add this
            session.permanent = True  # Make session persist
            session.modified = True   # Mark session as modified
            
            print(f"[DEBUG] Login - Session set: user_id={session.get('user_id')}, role={session.get('role')}, session_keys={list(session.keys())}")

            # Check if JSON response is requested (for React frontend)
            wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                        request.args.get('format') == 'json'

            if wants_json:
                response = jsonify({
                    'success': True,
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'role': role,
                        'name': session['name'],
                        'level': user['level'],
                    }
                })
                # Flask will automatically set the session cookie
                return response

            # HTML redirects (original behavior)
            if role == 'admin':
                return redirect(url_for('list_users'))
            elif role in ['qc_1', 'qc_2', 'qc_3']:
                return redirect(url_for('qc_lead_dashboard'))
            elif role.startswith('qc_review'):
                return redirect(url_for('qc_dashboard'))
            elif role.startswith('team_lead'):
                lvl_from_role = role.split('_')[-1] if role.split('_')[-1].isdigit() else None
                lvl = session.get('level') or lvl_from_role or 1
                return redirect(url_for('team_leader_dashboard_v2', level=lvl))
            elif role.startswith('reviewer'):
                return redirect(url_for('reviewer_dashboard'))
            elif role == 'qa':
                return redirect(url_for('qa_dashboard'))
            elif role == 'sme':
                return redirect(url_for('sme_dashboard'))
            else:
                return redirect(url_for('home'))

        # Invalid credentials
        wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                    request.args.get('format') == 'json'
        if wants_json:
            return jsonify({'success': False, 'error': 'Invalid email or password'}), 401

        flash("Invalid email or password.", "danger")
        return redirect(url_for('login'))

    return render_template("login.html")

@app.route('/verify_2fa', methods=['GET', 'POST', 'OPTIONS'])
@csrf.exempt
def verify_2fa():
    """2FA verification page"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    # Check if user has pending login
    if 'pending_user_id' not in session or not session.get('2fa_required'):
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get("code", "").strip()
        
        if not code or len(code) != 6 or not code.isdigit():
            wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                        request.args.get('format') == 'json'
            if wants_json:
                return jsonify({'success': False, 'error': 'Invalid code format'}), 400
            flash("Please enter a valid 6-digit code.", "danger")
            return redirect(url_for('verify_2fa'))
        
        conn = get_db()
        cursor = conn.cursor()
        user_id = session['pending_user_id']
        
        # Get user and check code
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            session.clear()
            conn.close()
            flash("User not found.", "danger")
            return redirect(url_for('login'))
        
        # sqlite3.Row access - check if keys exist first
        stored_code = user['two_factor_code'] if 'two_factor_code' in user.keys() else None
        expires_at = user['two_factor_expires'] if 'two_factor_expires' in user.keys() else None
        
        # Check if code matches and hasn't expired
        from datetime import datetime
        is_valid = False
        if stored_code and stored_code == code:
            if expires_at:
                try:
                    expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.utcnow().replace(tzinfo=expires.tzinfo) < expires:
                        is_valid = True
                except Exception:
                    pass
        
        if not is_valid:
            # Clear code after failed attempt
            cursor.execute("UPDATE users SET two_factor_code = NULL, two_factor_expires = NULL WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                        request.args.get('format') == 'json'
            if wants_json:
                return jsonify({'success': False, 'error': 'Invalid or expired code'}), 401
            
            flash("Invalid or expired code. Please try logging in again.", "danger")
            session.clear()
            return redirect(url_for('login'))
        
        # Code is valid - complete login
        # Clear 2FA code
        cursor.execute("UPDATE users SET two_factor_code = NULL, two_factor_expires = NULL, last_active = ? WHERE id = ?", 
                      (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        conn.commit()
        conn.close()
        
        # Move pending session data to actual session
        role = session.get('pending_role', '').lower()
        session['user_id'] = user_id
        session['role'] = role
        session['level'] = session.get('pending_level')
        session['email'] = session.get('pending_email')
        session['name'] = session.get('pending_name')
        session.permanent = True
        session.modified = True
        
        # Clear pending data
        session.pop('pending_user_id', None)
        session.pop('pending_email', None)
        session.pop('pending_role', None)
        session.pop('pending_level', None)
        session.pop('pending_name', None)
        session.pop('2fa_required', None)
        
        wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                    request.args.get('format') == 'json'
        if wants_json:
            return jsonify({
                'success': True,
                'user': {
                    'id': user_id,
                    'email': session['email'],
                    'role': role,
                    'name': session['name'],
                    'level': session['level'],
                }
            })
        
        # HTML redirects
        if role == 'admin':
            return redirect(url_for('list_users'))
        elif role in ['qc_1', 'qc_2', 'qc_3']:
            return redirect(url_for('qc_lead_dashboard'))
        elif role.startswith('qc_review'):
            return redirect(url_for('qc_dashboard'))
        elif role.startswith('team_lead'):
            lvl_from_role = role.split('_')[-1] if role.split('_')[-1].isdigit() else None
            lvl = session.get('level') or lvl_from_role or 1
            return redirect(url_for('team_leader_dashboard_v2', level=lvl))
        elif role.startswith('reviewer'):
            return redirect(url_for('reviewer_dashboard'))
        elif role == 'qa':
            return redirect(url_for('qa_dashboard'))
        elif role == 'sme':
            return redirect(url_for('sme_dashboard'))
        else:
            return redirect(url_for('home'))
    
    # GET request - show verification page
    wants_json = request.headers.get('Accept', '').startswith('application/json') or \
                request.args.get('format') == 'json'
    if wants_json:
        return jsonify({'requires_2fa': True, 'message': '2FA code required'})
    
    return render_template("verify_2fa.html")

@app.route("/admin/run_qc_sampling", methods=["POST"])
@role_required("qc_lead_1", "qc_lead_2", "qc_lead_3", "qc_1", "qc_2", "qc_3", "admin")
def run_sampling():
    apply_qc_sampling()
    flash("QC sampling complete.", "success")
    return redirect(url_for("qc_accreditation"))

# API endpoint for manual QC sampling
@csrf.exempt
@app.route('/api/qc_manual_sampling', methods=['GET', 'POST'])
@role_required('qc_1', 'qc_2', 'qc_3', 'qc_lead_1', 'qc_lead_2', 'qc_lead_3', 'admin')
def api_qc_manual_sampling():
    """Get completed tasks available for sampling, or manually/automatically sample them"""
    try:
        import sqlite3
        from utils import derive_case_status
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        if request.method == 'GET':
            # Get completed tasks that haven't been sampled yet
            cur.execute("""
                SELECT 
                    r.id,
                    r.task_id,
                    r.customer_id,
                    r.assigned_to AS reviewer_id,
                    r.date_completed AS completed_at,
                    r.outcome,
                    u1.name AS reviewer_name,
                    u2.name AS completed_by_name
                FROM reviews r
                LEFT JOIN qc_sampling_log qsl ON qsl.review_id = r.id
                LEFT JOIN users u1 ON u1.id = r.assigned_to
                LEFT JOIN users u2 ON u2.id = r.completed_by
                WHERE r.date_completed IS NOT NULL
                  AND r.date_completed != ''
                  AND qsl.review_id IS NULL
                  AND r.status NOT LIKE '%QC%'
                  AND r.status NOT LIKE '%Rework%'
                ORDER BY r.date_completed DESC
                LIMIT 500
            """)
            
            tasks = []
            for row in cur.fetchall():
                # Check if task is actually completed (not in QC workflow)
                review = dict(row)
                # Add _in_qc_sampling flag for status derivation
                review['_in_qc_sampling'] = False
                status = derive_case_status(review)
                if status == "Completed":
                    tasks.append({
                        'task_id': review['task_id'],
                        'customer_id': review['customer_id'],
                        'reviewer_id': review['reviewer_id'],
                        'reviewer_name': review['reviewer_name'],
                        'completed_by_name': review['completed_by_name'],
                        'completed_at': review['completed_at'],
                        'outcome': review['outcome']
                    })
            
            conn.close()
            return jsonify({
                'success': True,
                'tasks': tasks
            })
    
        elif request.method == 'POST':
            # Manual or automatic sampling
            data = request.get_json() or {}
            action = data.get('action', 'manual')
            
            if action == 'auto':
                # Run automatic sampling
                conn.close()  # Close before calling apply_qc_sampling which opens its own connection
                sampled_count = apply_qc_sampling()
                return jsonify({
                    'success': True,
                    'message': 'Automatic sampling completed',
                    'sent_count': sampled_count
                })
            
            elif action == 'manual':
                # Manually sample selected tasks
                task_ids = data.get('task_ids', [])
                if not task_ids:
                    conn.close()
                    return jsonify({'error': 'No task IDs provided'}), 400
                
                sent_count = 0
                for task_id in task_ids:
                    # Get review details
                    cur.execute("SELECT id, assigned_to FROM reviews WHERE task_id = ?", (task_id,))
                    review = cur.fetchone()
                    if not review:
                        continue
                    
                    review_id = review['id']
                    reviewer_id = review['assigned_to']
                    
                    # Check if already sampled
                    cur.execute("SELECT 1 FROM qc_sampling_log WHERE review_id = ?", (review_id,))
                    if cur.fetchone():
                        continue
                    
                    # Insert into qc_sampling_log
                    try:
                        cur.execute("""
                            INSERT INTO qc_sampling_log (review_id, reviewer_id, task_id, sampled_at)
                            VALUES (?, ?, ?, datetime('now'))
                        """, (review_id, reviewer_id, task_id))
                        
                        # Update status to "QC - Awaiting Allocation"
                        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
                        review_data = dict(cur.fetchone())
                        # Add _in_qc_sampling flag for status derivation
                        review_data['_in_qc_sampling'] = True
                        new_status = derive_case_status(review_data)
                        cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
                        
                        sent_count += 1
                    except Exception as e:
                        print(f"Error sampling task {task_id}: {e}")
                        continue
                
                conn.commit()
                conn.close()
                
                return jsonify({
                    'success': True,
                    'sent_count': sent_count,
                    'message': f'Successfully sent {sent_count} task(s) to QC'
                })
            
            conn.close()
            return jsonify({'error': 'Invalid action'}), 400
    except Exception as e:
        import traceback
        print(f"Error in api_qc_manual_sampling: {str(e)}\n{traceback.format_exc()}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': str(e)}), 500

@app.route("/assign_tasks_bulk", methods=["GET", "POST"], endpoint="assign_tasks_bulk")

@app.route("/assign_tasks_bulk", methods=["GET", "POST"])
@role_required("team_lead_1", "team_lead_2", "team_lead_3", "operations_manager", "Operations_Manager", "Operations Manager")
def assign_tasks_bulk():
    # Delegate to the QC bulk assign implementation but keep Ops/Team Lead access
    return qc_assign_tasks_bulk()
@app.route("/qc_assign_tasks_bulk", methods=["GET", "POST"])
@role_required("qc_1", "qc_2", "qc_3")
def qc_assign_tasks_bulk():
    import sqlite3
    from utils import derive_case_status

    # --- Determine QC Lead level from role ---
    session_role = (session.get("role") or "").lower()
    try:
        level = int(session_role.split("_")[-1]) if "_" in session_role else 1
    except Exception:
        level = 1

    reviewer_role = f"qc_review_{level}"   # reviewers (not the QCTL role)
    qctl_user_id  = session.get("user_id")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Identify the logged-in QCTL (for team scoping) ---
    cur.execute("SELECT name, email FROM users WHERE id = ?", (qctl_user_id,))
    me_row = cur.fetchone()
    lead_name  = (me_row["name"]  if me_row and me_row["name"]  else "").strip()
    lead_email = (me_row["email"] if me_row and me_row["email"] else "").strip()

    # --- QC reviewers in THIS level, in THIS QCTL's team, active, excluding self ---
    cur.execute("""
        SELECT id, COALESCE(name, email) AS display_name
        FROM users
        WHERE role = ?
          AND (status IS NULL OR status = 'active')
          AND id <> ?
          AND (
               team_lead = ? OR team_lead = ?
            OR reporting_line = ? OR reporting_line = ?
          )
        ORDER BY display_name COLLATE NOCASE
    """, (reviewer_role, qctl_user_id, lead_name, lead_email, lead_name, lead_email))
    reviewers = cur.fetchall()
    allowed_qc_ids = {r["id"] for r in reviewers}

    # --- Build the pool of unassigned reviews (awaiting QC assignment) ---
    cur.execute(f"""
        SELECT
            r.id,
            r.task_id,
            r.l{level}_date_completed AS completed_at
        FROM reviews r
        WHERE r.l{level}_date_completed IS NOT NULL
          AND (r.l{level}_qc_assigned_to IS NULL OR r.l{level}_qc_assigned_to = 0)
          AND (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '')
        ORDER BY r.l{level}_date_completed DESC
        LIMIT 50
    """)
    unassigned_tasks = cur.fetchall()

    # Total available (for the counter on the page)
    cur.execute(f"""
        SELECT COUNT(*) AS cnt
        FROM reviews r
        WHERE r.l{level}_date_completed IS NOT NULL
          AND (r.l{level}_qc_assigned_to IS NULL OR r.l{level}_qc_assigned_to = 0)
          AND (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '')
    """)
    total_available = (cur.fetchone() or {"cnt": 0})["cnt"]

    # --- POST: allocate top N to a specific reviewer ---
    if request.method == "POST":
        qc_reviewer_id = request.form.get("qc_reviewer_id", type=int)
        task_limit     = request.form.get("task_limit", type=int) or 10

        if not qc_reviewer_id:
            conn.close()
            flash("Please choose a QC reviewer.", "warning")
            return redirect(url_for("qc_assign_tasks_bulk"))

        # ensure reviewer is in allowed pool (right level + your team)
        if qc_reviewer_id not in allowed_qc_ids:
            conn.close()
            flash("You can only allocate to QC reviewers in your team at this level.", "danger")
            return redirect(url_for("qc_assign_tasks_bulk"))

        try:
            # pick the top N still awaiting QC assignment
            cur.execute(f"""
                SELECT id, task_id
                FROM reviews
                WHERE l{level}_date_completed IS NOT NULL
                  AND (l{level}_qc_assigned_to IS NULL OR l{level}_qc_assigned_to = 0)
                  AND (l{level}_qc_end_time IS NULL OR l{level}_qc_end_time = '')
                ORDER BY l{level}_date_completed DESC
                LIMIT ?
            """, (task_limit,))
            to_assign = cur.fetchall()

            for row in to_assign:
                review_id = row["id"]
                task_id   = row["task_id"]

                # 1) assign
                cur.execute(f"""
                    UPDATE reviews
                       SET l{level}_qc_assigned_to = ?
                     WHERE id = ?
                """, (qc_reviewer_id, review_id))

                # 2) re-derive the unified status
                cur.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
                rev = cur.fetchone()
                if rev:
                    new_status = derive_status(dict(rev), level)
                    cur.execute("UPDATE reviews SET status = ? WHERE id = ?", (new_status, review_id))

            conn.commit()
            flash(f"Allocated {len(to_assign)} task(s).", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error assigning tasks: {e}", "danger")

        conn.close()
        return redirect(url_for("qc_assign_tasks_bulk"))
    # -- Persist POST updates for reviewer_panel (single refresh UX) --
    if request.method == "POST" and not sme_mode:
        if update_fields:
            try:
                _update_review(task_id, update_fields)
            except Exception as _e:
                current_app.logger.error("Failed to update outreach fields for %s: %s", task_id, _e)
            # Prefer redirect_to if set in action blocks; else reload same URL
            try:
                _rt = redirect_to
            except NameError:
                _rt = request.url
            return redirect(_rt)



    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route('/export_accreditation_log/<int:level>')
@role_required('qc_lead_1','qc_lead_2','qc_lead_3','admin')
def download_accreditation_log(level):
    conn   = get_db()
    cur    = conn.cursor()
    cur.execute("""
        SELECT u.name, u.email, l.is_accredited, l.comment, l.accredited_by, l.timestamp
          FROM reviewer_accreditation_log l
          JOIN users u ON u.id = l.reviewer_id
         WHERE l.level = ?
         ORDER BY l.timestamp DESC
    """, (level,))
    logs = cur.fetchall()
    conn.close()

    def generate():
        yield "Name,Email,Status,Comment,Changed By,Timestamp\n"
        for row in logs:
            status = "Accredited" if row["is_accredited"] else "Revoked"
            yield f'{row["name"]},{row["email"]},{status},{row["comment"]},{row["accredited_by"]},{row["timestamp"]}\n'

    return Response(generate(), mimetype='text/csv',
        headers={"Content-Disposition": f"attachment; filename=accreditation_level_{level}.csv"})

@app.route("/completed_cases")
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3')
def completed_cases():
    from utils import derive_case_status
    from datetime import datetime, timedelta
    try:
        from dateutil import parser as dtp
    except Exception:
        dtp = None

    user_id        = session.get("user_id")
    outcome_filter = request.args.get("outcome")
    # legacy param support: "today" | "week"
    date_filter    = request.args.get("date")

    # Use UTC to align with other dashboards
    today        = datetime.utcnow().date()
    monday_this  = today - timedelta(days=today.weekday())
    current_week = today.isocalendar()[1]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()
    cur.execute("SELECT * FROM reviews")
    rows = [dict(r) for r in cur.fetchall()]
    # --- Optional chaser filters (from Chaser Cycle table cell click) ---
    chaser_label = request.args.get("chaser_label", "").strip()
    chaser_due   = request.args.get("chaser_due", "").strip()  # 'Overdue' or dd/mm/YYYY

    if chaser_label and chaser_due:
        # Utilities
        def _coalesce_key(rec, keys):
            if not keys: return None
            for k in keys:
                if k in rec and rec.get(k) not in (None, ""):
                    return k
            return None

        def _parse_date_any_strict(s):
            if not s: return None
            s = str(s).strip()
            for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%Y/%m/%d","%d %b %Y","%d %B %Y"):
                try:
                    return datetime.strptime(s, fmt).date()
                except Exception:
                    pass
            try:
                return parser.parse(s).date()
            except Exception:
                return None

        def _is_blank(v):
            if v is None: return True
            if isinstance(v, str):
                return v.strip() == ""
            return False

        # Map label -> due/issued fields
        lab = chaser_label.lower().strip()
        due_fields = []
        issued_fields = []
        for n in ("1","2","3","4"):
            if lab.startswith(f"outreach cycle {n}"):
                due_fields    = [f"Chaser{n}DueDate", f"Chaser{n}_DueDate"]
                issued_fields = [f"Chaser{n}IssuedDate", f"Chaser{n}DateIssued"]
                break
        if not due_fields:
            for n in ("1","2","3"):
                if lab.startswith(f"chaser {n} overdue"):
                    due_fields    = [f"Chaser{n}DueDate", f"Chaser{n}_DueDate"]
                    issued_fields = [f"Chaser{n}IssuedDate", f"Chaser{n}DateIssued"]
                    break

        # Target date (if header is a date)
        target_date = None
        if chaser_due != "Overdue":
            try:
                target_date = datetime.strptime(chaser_due, "%d/%m/%Y").date()
            except Exception:
                target_date = None

        today_local = datetime.utcnow().date()

        filtered = []
        for rec in rows:
            # Only include rows that already match the status from the link
            raw_status = (rec.get("current_status") or rec.get("status") or "").strip()
            if raw_status != chaser_label:
                continue

            due_key    = _coalesce_key(rec, due_fields)
            issued_key = _coalesce_key(rec, issued_fields)

            due_date   = _parse_date_any_strict(rec.get(due_key)) if due_key else None
            issued_v   = rec.get(issued_key) if issued_key else None
            not_issued = _is_blank(issued_v)

            if not (due_date and not_issued):
                continue

            if chaser_due == "Overdue":
                if due_date < today_local:
                    filtered.append(rec)
            elif target_date:
                if due_date == target_date:
                    filtered.append(rec)

        rows = filtered

    conn.close()

    def _parse_dt(s):
        if not s:
            return None
        s = str(s).strip()
        # tolerate trailing 'Z' and microseconds
        try:
            return datetime.fromisoformat(s.replace("Z", "").split(".")[0])
        except Exception:
            if dtp:
                try:
                    return dtp.parse(s)
                except Exception:
                    return None
            return None

    tasks = []
    outcomes_found = set()

    # normalise my id once
    try:
        me = int(user_id)
    except (TypeError, ValueError):
        me = None

    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        task_id = r.get("task_id")

        # check each level for work done by this reviewer
        for level in (1, 2, 3):
            completed_by = r.get("completed_by")
            completed_at = r.get("date_completed")
            outcome      = r.get("outcome")

            # only include if this user completed it
            try:
                if int(completed_by) != me or not completed_at:
                    continue
            except (ValueError, TypeError):
                continue

            dt = _parse_dt(completed_at)
            if dt:
                date_only = dt.date()
                formatted = dt.strftime("%d/%m/%y")
            else:
                # 🔧 ensure these are always defined
                date_only = None
                formatted = "—"

            # legacy date filters
            if date_filter == "today" and date_only != today:
                continue
            if date_filter == "week":
                # keep the original intent but guard None
                if not date_only or date_only.isocalendar()[1] != current_week:
                    continue
                # (alt: use monday_this <= date_only <= today for exact WTD)

            # outcome filter
            if outcome_filter and outcome != outcome_filter:
                continue

            # derive the up-to-date live status
            status = derive_case_status(r)

            tasks.append({
                "task_id":        task_id,
                "level":          level,
                "outcome":        outcome or "N/A",
                "status":         status,
                "date_completed": formatted
            })
            if outcome:
                outcomes_found.add(outcome)

    return render_template("404_redirect.html"), 404

@app.route("/sme_review/<task_id>", methods=["GET"], endpoint="sme_review")
@role_required("sme", "admin")
def sme_review(task_id):
    # Reuse the reviewer panel UI, just tell it we're in SME mode
    return redirect(url_for("review", task_id=task_id, sme="1"))

@app.route("/sme/review/<task_id>/<int:level>", methods=["GET"])
@role_required("sme", "admin")
def sme_review_level(task_id, level):
    conn = get_db()
    cur = conn.cursor()
    review = cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,)).fetchone()
    conn.close()
    if not review:
        return "Task not found", 404
    return render_template("404_redirect.html"), 404

@app.route("/submit_review/<task_id>/<int:level>", methods=["POST"])

def submit_review(task_id, level):
    conn = get_db()
    cursor = conn.cursor()
    rationale = (request.form.get("rationale") or "").strip()
    outcome   = (request.form.get("outcome") or "").strip()
    case_summary = (request.form.get("case_summary") or "").strip()
    now = datetime.now().isoformat()

    # Check if case_summary already exists in DB if not supplied in this POST
    try:
        row = cursor.execute("SELECT case_summary FROM reviews WHERE task_id = ?", (task_id,)).fetchone()
        existing_summary = (row["case_summary"] if row and ("case_summary" in row.keys()) else None)
    except Exception:
        # Row is likely sqlite3.Row; safe access
        try:
            existing_summary = row["case_summary"] if row is not None else None
        except Exception:
            existing_summary = None

    has_summary  = bool((case_summary or (existing_summary or "")).strip())
    has_outcome  = bool(outcome)
    has_rationale= bool(rationale)

    # Always write provided fields
    if level == 1:
        cursor.execute("""
            UPDATE reviews
            SET l1_rationale = ?, l1_outcome = ?, updated_at = ?
                {maybe_case_summary}
                {maybe_completed}
            WHERE task_id = ?
        """.format(
            maybe_case_summary=", case_summary = ?" if case_summary else "",
            maybe_completed = ", l1_date_completed = ?" if (has_outcome and has_rationale and has_summary) else ""
        ),
        tuple([rationale, outcome, now] + ([case_summary] if case_summary else []) +
              ([now] if (has_outcome and has_rationale and has_summary) else []) + [task_id]))

    elif level == 2:
        cursor.execute("""
            UPDATE reviews
            SET l2_rationale = ?, l2_outcome = ?, updated_at = ?
                {maybe_case_summary}
                {maybe_completed}
            WHERE task_id = ?
        """.format(
            maybe_case_summary=", case_summary = ?" if case_summary else "",
            maybe_completed=", l2_date_completed = ?" if (has_outcome and has_rationale and has_summary) else ""
        ),
        tuple([rationale, outcome, now] + ([case_summary] if case_summary else []) +
              ([now] if (has_outcome and has_rationale and has_summary) else []) + [task_id]))

    elif level == 3:
        cursor.execute("""
            UPDATE reviews
            SET l3_rationale = ?, l3_outcome = ?, updated_at = ?
                {maybe_case_summary}
                {maybe_completed}
            WHERE task_id = ?
        """.format(
            maybe_case_summary=", case_summary = ?" if case_summary else "",
            maybe_completed=", l3_date_completed = ?" if (has_outcome and has_rationale and has_summary) else ""
        ),
        tuple([rationale, outcome, now] + ([case_summary] if case_summary else []) +
              ([now] if (has_outcome and has_rationale and has_summary) else []) + [task_id]))

    # Recompute status after update
    cursor.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    rev = dict(cursor.fetchone())
    new_status = derive_status(rev, rev.get("current_level") or level)
    cursor.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))

    conn.commit()
    conn.close()
    if has_outcome and has_rationale and has_summary:
        flash(f"✅ Level {level} review submitted and marked complete.")
    else:
        flash("Saved, but not marked complete — add Outcome, Rationale, and Case Summary to complete.", "warning")
    return redirect(url_for("review_status_dashboard"))

@app.route("/submit_qc_decision/<task_id>/<int:level>", methods=["POST"])
@role_required("qc_1", "qc_2", "qc_3", "qc_review_1", "qc_review_2", "qc_review_3")
def submit_qc_decision(task_id, level):
    import sqlite3
    from datetime import datetime
    from utils import derive_case_status

    action    = (request.form.get("action") or "").strip()
    now       = datetime.utcnow().isoformat(timespec="seconds")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    if action == "qc_rework_ok":
        # ✅ Rework confirmed by QC: close the rework loop
        cur.execute(f"""
            UPDATE reviews
               SET l{level}_qc_rework_completed = 1,
                   l{level}_qc_rework_required  = 0,
                   l{level}_qc_check_date       = COALESCE(l{level}_qc_check_date, ?)
             WHERE task_id = ?
        """, (now, task_id))

        # Recompute overall status
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        rev = dict(cur.fetchone() or {})
        new_status = derive_case_status(rev)
        cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))

        conn.commit()
        conn.close()
        flash("Rework marked as checked. Original QC outcome retained.", "success")
        return redirect(url_for("reviewer_panel", task_id=task_id))

    # ----- existing path for normal QC submit (unchanged) --------------------
    outcome = (request.form.get("qc_outcome") or "").strip()
    comment = (request.form.get("qc_rationale") or "").strip()
    rework  = 1 if request.form.get("qc_rework_required") else 0

    valid = {"Pass", "Pass With Feedback", "Fail"}
    if outcome not in valid:
        flash("Select a valid QC outcome.", "warning")
        conn.close()
        return redirect(url_for("reviewer_panel", task_id=task_id))

    if outcome == "Fail" and not rework:
        flash("Rework is required when the QC outcome is ‘Fail’.", "danger")
        conn.close()
        return redirect(url_for("reviewer_panel", task_id=task_id))

    # Update QC fields
    cur.execute(f"""
        UPDATE reviews
           SET l{level}_qc_outcome         = ?,
               l{level}_qc_comment         = ?,
               l{level}_qc_check_date      = ?,
               l{level}_qc_rework_required = ?,
               l{level}_qc_rework_completed= CASE WHEN ?=0 THEN 0 ELSE l{level}_qc_rework_completed END
         WHERE task_id = ?
    """, (outcome, comment, now, rework, rework, task_id))

    # Fetch full record and check QC sampling
    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    rev = dict(cur.fetchone() or {})
    
    # Check if task is in QC sampling
    cur.execute("SELECT 1 FROM qc_sampling_log WHERE task_id = ?", (task_id,))
    in_qc_sampling = cur.fetchone() is not None
    rev["_in_qc_sampling"] = in_qc_sampling
    
    new_status = derive_case_status(rev)
    cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))
    
    # If QC passes, ensure rework flags are cleared
    if outcome in ("Pass", "Pass With Feedback") and not rework:
        cur.execute(f"""
            UPDATE reviews
               SET l{level}_qc_rework_required = 0,
                   l{level}_qc_rework_completed = 1
             WHERE task_id = ?
        """, (task_id,))

    conn.commit()
    conn.close()
    flash("QC decision saved.", "success")
    return redirect(url_for("reviewer_panel", task_id=task_id))

@app.route("/qc_confirm_rework/<task_id>/<int:level>", methods=["POST"])
@role_required("qc_1", "qc_2", "qc_3", "qc_review_1", "qc_review_2", "qc_review_3")
def qc_confirm_rework(task_id, level):
    import sqlite3
    from datetime import datetime
    from utils import derive_case_status

    now = datetime.utcnow().isoformat(timespec="seconds")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Mark rework completed; keep original QC outcome for MI
    cur.execute(f"""
        UPDATE reviews
           SET l{level}_qc_rework_completed = 1,
               l{level}_qc_end_time        = ?
         WHERE task_id = ?
    """, (now, task_id))

    # Recompute overall status (will become Completed at Level N or progress)
    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    rev = dict(cur.fetchone() or {})
    new_status = derive_case_status(rev)

    cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))
    conn.commit()
    conn.close()

    flash("Rework confirmed. Case updated.", "success")
    return redirect(url_for("reviewer_panel", task_id=task_id))

@app.route("/admin/delete_sampling_rule/<reviewer_id>", methods=["POST"])
@role_required("admin", "qc_1", "qc_2", "qc_3")
def delete_sampling_rule(reviewer_id):
    conn = get_db()
    cur = conn.cursor()

    if reviewer_id == "null":
        # Delete global rate (level is NULL for global rates in single-level system)
        cur.execute("DELETE FROM sampling_rates WHERE reviewer_id IS NULL")
    else:
        # Delete reviewer-specific rate (level is NULL for reviewer rates in single-level system)
        cur.execute("DELETE FROM sampling_rates WHERE reviewer_id = ?", (reviewer_id,))

    conn.commit()
    conn.close()
    flash("Sampling rule deleted.", "success")
    return redirect(url_for("sampling_rates"))

@app.route('/admin/users/<int:user_id>/resend_setup', methods=['POST'])
@role_required('admin')
def resend_setup(user_id):
    # Look up the user's email
    conn = get_db_connection()
    row = conn.execute("SELECT email, password_changed_at FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        conn.close()
        flash('User not found.', 'danger')
        return redirect(url_for('list_users'))

    email = (row['email'] or '').strip().lower()

    # Optional: if they've already set a password, warn but still allow resend
    if row.get('password_changed_at'):
        flash('Note: this user has already set a password. Sending a fresh setup link anyway.', 'warning')

    # (Optional) Throttle: avoid spamming – block if a token was sent in last 5 minutes
    recent = conn.execute(
        """
        SELECT created_at
          FROM password_resets
         WHERE user_id=?
         ORDER BY id DESC
         LIMIT 1
        """, (user_id,)
    ).fetchone()
    if recent:
        try:
            from datetime import datetime, timezone
            last = datetime.fromisoformat(str(recent['created_at']).replace('Z','')).replace(tzinfo=None)
            if (datetime.utcnow() - last).total_seconds() < 300:  # 5 minutes
                conn.close()
                flash('A setup link was sent recently. Please wait a few minutes before resending.', 'info')
                return redirect(url_for('list_users'))
        except Exception:
            pass

    # Create new token
    token = token_urlsafe(32)
    token_hash = _sha256(token)
    expires_at = (datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat() + "Z"

    conn.execute(
        """
        INSERT INTO password_resets
            (user_id, token_hash, expires_at, requested_ip, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            token_hash,
            expires_at,
            "admin-resend",
            "system:resend_setup",
            datetime.utcnow().isoformat() + "Z",
        ),
    )
    conn.commit()
    conn.close()

    # Send welcome/setup email
    setup_url = f"{APP_BASE_URL}{url_for('reset_password', token=token)}"
    try:
        _send_welcome_email(email, setup_url)
        flash(f'Setup link re-sent to {email}.', 'success')
    except Exception as e:
        current_app.logger.exception("SendGrid error while resending setup: %s", e)
        flash('Unable to send setup email. Please check logs.', 'warning')

    return redirect(url_for('list_users'))

@app.route('/admin/resend_setup_link/<int:user_id>', methods=['POST'])
@role_required('admin')
def resend_setup_link(user_id):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, email FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        flash('User not found.', 'danger')
        return redirect(url_for('list_users'))

    # Create a new token
    token = token_urlsafe(32)
    token_hash = _sha256(token)
    expires_at = (datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat() + "Z"

    # Insert token into password_resets
    conn.execute(
        """
        INSERT INTO password_resets
            (user_id, token_hash, expires_at, requested_ip, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user['id'],
            token_hash,
            expires_at,
            request.headers.get("X-Forwarded-For", request.remote_addr),
            request.headers.get("User-Agent", ""),
            datetime.utcnow().isoformat() + "Z",
        ),
    )
    conn.commit()
    conn.close()

    # Build the reset URL
    reset_url = f"{APP_BASE_URL}{url_for('reset_password', token=token)}"

    try:
        _send_reset_email(user['email'], reset_url)
        flash(f'Password setup link resent to {user["email"]}.', 'success')
    except Exception as e:
        current_app.logger.exception("Error sending setup link: %s", e)
        flash('User found, but sending the setup email failed. Please check logs.', 'warning')

    return redirect(url_for('list_users'))

@app.route("/assign_qc/<int:review_id>", methods=["POST"])
@role_required("qc_1", "qc_2", "qc_3")
def assign_qc(review_id):
    # Figure out which QC level this lead is
    level = session.get("level")
    if level is None:
        flash("Unable to determine your QC level.", "danger")
        return redirect(url_for("qc_allocation"))

    # Which column are we updating?
    qc_col = "qc_assigned_to"

    conn   = get_db()
    cur    = conn.cursor()

    # 1) Mark this review as assigned to the current user
    cur.execute(
        f"UPDATE reviews SET {qc_col} = ? WHERE id = ?",
        (session["user_id"], review_id)
    )

    # 2) Fetch the full record back, derive its new status, and write it
    cur.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
    rev = dict(cur.fetchone())
    
    # Check if task is in QC sampling
    cur.execute("SELECT 1 FROM qc_sampling_log WHERE review_id = ?", (review_id,))
    in_qc_sampling = cur.fetchone() is not None
    rev["_in_qc_sampling"] = in_qc_sampling
    
    new_status = derive_case_status(rev)
    cur.execute(
        "UPDATE reviews SET status = ? WHERE id = ?",
        (new_status, review_id)
    )

    # 3) Commit & close
    conn.commit()
    conn.close()

    flash("Review assigned to you for QC.", "success")
    return redirect(url_for("qc_allocation"))

@app.route("/qc_accreditation", methods=["GET", "POST"])
@role_required("qc_1", "qc_2", "qc_3")
def qc_accreditation():
    conn = get_db()
    cursor = conn.cursor()

    user_level = int(session.get("level", 1))  # e.g. 1 for qc_lead_1

    if request.method == "POST":
        reviewer_id = int(request.form["reviewer_id"])
        level = int(request.form["level"])
        is_accredited = int(request.form.get("is_accredited", 0))
        comment = request.form.get("comment", "").strip()

        # Update current accreditation status
        cursor.execute("""
            INSERT INTO reviewer_accreditation (reviewer_id, level, is_accredited, accredited_by, accredited_date, comment)
            VALUES (?, ?, ?, ?, datetime('now'), ?)
            ON CONFLICT(reviewer_id, level) DO UPDATE SET
                is_accredited = excluded.is_accredited,
                accredited_by = excluded.accredited_by,
                accredited_date = excluded.accredited_date,
                comment = excluded.comment
        """, (reviewer_id, level, is_accredited, session["user_id"], comment))

        # Insert audit record
        cursor.execute("""
            INSERT INTO reviewer_accreditation_log (reviewer_id, level, is_accredited, accredited_by, comment, timestamp)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (reviewer_id, level, is_accredited, session["user_id"], comment))

        conn.commit()
        flash("✅ Accreditation updated.", "success")
        return redirect(url_for("qc_accreditation"))

    # Load reviewers and their accreditation status for the current level
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.team_lead,
               COALESCE(a.is_accredited, 0) as is_accredited,
               COALESCE(a.comment, '') as comment,
               a.accredited_date
        FROM users u
        LEFT JOIN reviewer_accreditation a ON a.reviewer_id = u.id AND a.level = ?
        WHERE u.role LIKE 'reviewer%' OR u.role LIKE 'Reviewer%'
        ORDER BY u.name
    """, (user_level,))
    raw_reviewers = cursor.fetchall()

    # Build reviewer list with change flag and history
    reviewers = []
    for row in raw_reviewers:
        reviewer = dict(row)
        # Flag recently changed if within last 7 days
        if reviewer.get("accredited_date"):
            cursor.execute("""
                SELECT julianday('now') - julianday(?) < 7
            """, (reviewer["accredited_date"],))
            reviewer["recently_changed"] = cursor.fetchone()[0]
        else:
            reviewer["recently_changed"] = False

        # Load individual history log
        cursor.execute("""
            SELECT is_accredited, comment, accredited_by, timestamp
            FROM reviewer_accreditation_log
            WHERE reviewer_id = ? AND level = ?
            ORDER BY timestamp DESC
        """, (reviewer["id"], user_level))
        reviewer["history"] = cursor.fetchall()

        reviewers.append(reviewer)

    # Load full audit log (for table at bottom)
    cursor.execute("""
        SELECT l.reviewer_id, u.name, u.email, l.level, l.is_accredited,
               l.comment, l.accredited_by, l.timestamp
        FROM reviewer_accreditation_log l
        JOIN users u ON u.id = l.reviewer_id
        WHERE l.level = ?
        ORDER BY l.timestamp DESC
    """, (user_level,))
    logs = cursor.fetchall()


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('list_users'))
    elif role.startswith('team_lead'):
         level = role.split("_")[-1]  # extracts "1", "2", or "3"
         return redirect(url_for('team_leader_dashboard_v2', level=level))
    elif role == 'operations_manager':
        return redirect(url_for('operations_dashboard'))
    elif role.startswith('reviewer'):
        return redirect(url_for('reviewer_dashboard'))
    elif role in ['qc_1', 'qc_2', 'qc_3']:
        return redirect(url_for('qc_lead_dashboard'))
    elif role.startswith('qc_review'):
        return redirect(url_for('qc_dashboard'))
    elif role.startswith('qa'):
        return redirect(url_for('qa_dashboard'))
    elif role == 'sme':
        return redirect(url_for('sme_dashboard'))

    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route("/export_team_stats/<int:days>/<lead_name>")
def export_team_stats(days, lead_name):
    conn = sqlite3.connect("scrutinise_workflow.db")
    cursor = conn.cursor()

    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor.execute("SELECT id, email, name FROM users WHERE team_lead = ?", (lead_name,))
    reviewers = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reviewer Email", "Reviewer Name", "Tasks Reviewed", "Last Reviewed Date"])

    for reviewer_id, reviewer_email, reviewer_name in reviewers:
        cursor.execute("""
            SELECT COUNT(*), MAX(updated_at)
            FROM reviews
            WHERE assigned_to = ?
              AND updated_at >= ?
        """, (reviewer_id, since_date))
        count, last_reviewed = cursor.fetchone()
        writer.writerow([
            reviewer_email,
            reviewer_name,
            count or 0,
            last_reviewed or "N/A"
        ])

    conn.close()
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=team_stats_{lead_name.replace(' ', '_')}.csv"}
    )

@app.route("/admin/sampling_rates", methods=["GET", "POST"])
@role_required("admin", "qc_1", "qc_2", "qc_3")
def sampling_rates():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        reviewer_id = request.form.get("reviewer_id")
        level = int(request.form["level"])
        rate = int(request.form["rate"])

        if reviewer_id == "":  # Global rate
            cur.execute("""
                INSERT INTO sampling_rates (reviewer_id, level, rate)
                VALUES (NULL, ?, ?)
                ON CONFLICT(level, reviewer_id) DO UPDATE SET rate=excluded.rate
            """, (level, rate))
        else:
            cur.execute("""
                INSERT INTO sampling_rates (reviewer_id, level, rate)
                VALUES (?, ?, ?)
                ON CONFLICT(level, reviewer_id) DO UPDATE SET rate=excluded.rate
            """, (int(reviewer_id), level, rate))

        conn.commit()
        flash("Sampling rate updated", "success")
        return redirect(url_for("sampling_rates"))

    # Load all sampling rules
    cur.execute("""
        SELECT sr.*, u.name as reviewer_name
        FROM sampling_rates sr
        LEFT JOIN users u ON sr.reviewer_id = u.id
        ORDER BY level, reviewer_name
    """)
    rates = cur.fetchall()

    # Load reviewers
    cur.execute("SELECT id, name FROM users WHERE role LIKE 'reviewer_%' ORDER BY name")
    reviewers = cur.fetchall()


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route("/admin/team_structure")
def view_team_structure():
    if session.get("role", "").lower() != "admin":
        return "Access denied", 403

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, name, role, team_lead, email FROM users")
    users = [dict(u) for u in cur.fetchall()]
    conn.close()

    for u in users:
        u["role"] = (u.get("role") or "").lower()

    nodes_by_level = defaultdict(list)
    for user in users:
        if "_1" in user["role"]:
            nodes_by_level[1].append(user)
        elif "_2" in user["role"]:
            nodes_by_level[2].append(user)
        elif "_3" in user["role"]:
            nodes_by_level[3].append(user)
        else:
            nodes_by_level[0].append(user)  # Unassigned/misc

    role_labels = {
        'admin': 'Admin',
        'team_lead_1': 'Team Lead (Level 1)',
        'team_lead_2': 'Team Lead (Level 2)',
        'team_lead_3': 'Team Lead (Level 3)',
        'reviewer_1': 'Reviewer (Level 1)',
        'reviewer_2': 'Reviewer (Level 2)',
        'reviewer_3': 'Reviewer (Level 3)',
        'qc': 'Quality Control',
        'qa': 'Quality Assurance',
        'sme': 'Subject Matter Expert',
        'operations_manager': 'Operations Manager',
    }

    return render_template("404_redirect.html"), 404

@app.route("/admin/invite_user", methods=["GET", "POST"])
def invite_user():
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = get_db_connection()
    cur = conn.cursor()

    # Get team leads for dropdown
    cur.execute("SELECT name FROM users WHERE role LIKE 'team_lead_%'")
    team_leads = [row["name"] for row in cur.fetchall()]

    if request.method == "POST":
        email = request.form.get("email")
        role = request.form.get("role")
        name = request.form.get("name")
        team_lead = request.form.get("team_lead") or None

        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            flash("A user with that email already exists.", "warning")
            return render_template("404_redirect.html"), 404

        temp_password = generate_random_password()
        password_hash = generate_password_hash(temp_password)

        cur.execute("""
            INSERT INTO users (email, password_hash, role, name, team_lead)
            VALUES (?, ?, ?, ?, ?)
        """, (email, password_hash, role, name, team_lead))
        conn.commit()

        try:
            send_invite_email(email, temp_password)
            flash("Invite email sent successfully.", "success")
        except Exception as e:
            flash(f"User created but email failed: {str(e)}", "danger")

        conn.close()
        return redirect(url_for("list_users"))


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        updates = {
            "rework_overdue_days": request.form.get("rework_overdue_days"),
            "default_task_limit": request.form.get("default_task_limit"),
            "password_expiry_days": request.form.get("password_expiry_days")
        }
        for key, value in updates.items():
            cur.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        conn.commit()
        flash("Settings updated successfully.", "success")

    cur.execute("SELECT key, value FROM settings")
    settings = {row["key"]: row["value"] for row in cur.fetchall()}
    conn.close()

    return render_template("404_redirect.html"), 404

# Helper function to check if a module is enabled
def is_module_enabled(module_name):
    """Check if a module is enabled. Returns True by default if setting doesn't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    key = f"module_enabled_{module_name}"
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        value = row[0]
        # Handle both string and boolean values
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('1', 'true', 'yes', 'on')
        return bool(value)
    # Default to enabled if setting doesn't exist
    return True

# Initialize default module settings if they don't exist
def ensure_module_settings():
    """Ensure default module settings exist in database"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    default_settings = {
        "module_enabled_due_diligence": "1",
        "module_enabled_transaction_review": "1",
        "module_enabled_ai_sme": "1"
    }
    
    for key, default_value in default_settings.items():
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, default_value))
    
    conn.commit()
    conn.close()

# Initialize module settings on app startup
ensure_module_settings()

# API endpoint to get module settings (admin only)
@csrf.exempt
@app.route('/api/admin/module_settings', methods=['GET'])
def get_module_settings():
    """Get current module settings - accessible to all authenticated users for frontend checks"""
    ensure_module_settings()  # Ensure defaults exist
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    modules = ['due_diligence', 'transaction_review', 'ai_sme']
    settings = {}
    
    for module in modules:
        key = f"module_enabled_{module}"
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            value = row[0]
            # Convert to boolean
            if isinstance(value, str):
                settings[module] = value.lower() in ('1', 'true', 'yes', 'on')
            else:
                settings[module] = bool(value)
        else:
            settings[module] = True  # Default to enabled
    
    conn.close()
    
    return jsonify({
        'success': True,
        'settings': settings
    })

# API endpoint to update module settings (admin only)
@csrf.exempt
@app.route('/api/admin/module_settings', methods=['POST'])
@role_required('admin')
def update_module_settings():
    """Update module settings"""
    try:
        data = request.get_json()
        if not data or 'settings' not in data:
            return jsonify({'error': 'Invalid request data'}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        modules = ['due_diligence', 'transaction_review', 'ai_sme']
        updated = {}
        
        for module in modules:
            if module in data['settings']:
                key = f"module_enabled_{module}"
                value = "1" if data['settings'][module] else "0"
                
                cur.execute("""
                    INSERT INTO settings (key, value) 
                    VALUES (?, ?) 
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (key, value))
                
                updated[module] = data['settings'][module]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Module settings updated successfully',
            'settings': updated
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Admin Permissions API
# ============================================================================
@csrf.exempt
@app.route('/api/admin/permissions', methods=['GET', 'POST'])
@role_required('admin')
def api_admin_permissions():
    """Get or update permissions"""
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'permissions' not in data:
                return jsonify({'error': 'Invalid request data'}), 400
            
            # Delete all existing permissions
            cur.execute("DELETE FROM permissions")
            
            # Insert new permissions
            for perm in data['permissions']:
                cur.execute("""
                    INSERT INTO permissions (role, feature, can_view, can_edit)
                    VALUES (?, ?, ?, ?)
                """, (
                    perm.get('role'),
                    perm.get('feature'),
                    1 if perm.get('can_view') else 0,
                    1 if perm.get('can_edit') else 0
                ))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Permissions updated successfully'})
        
        # GET: Return all permissions
        cur.execute("SELECT role, feature, can_view, can_edit FROM permissions ORDER BY role, feature")
        rows = cur.fetchall()
        permissions = []
        for row in rows:
            permissions.append({
                'role': row[0],
                'feature': row[1],
                'can_view': bool(row[2]),
                'can_edit': bool(row[3])
            })
        conn.close()
        
        return jsonify({'success': True, 'permissions': permissions})
    except Exception as e:
        import traceback
        print(f"Error in api_admin_permissions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Get Current User's Permissions API
# ============================================================================
@csrf.exempt
@app.route('/api/user/permissions', methods=['GET'])
def api_user_permissions():
    """Get permissions for the current logged-in user"""
    try:
        role = session.get("role", "").lower()
        if not role:
            return jsonify({'success': True, 'permissions': {}})
        
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT feature, can_view, can_edit FROM permissions WHERE role = ?", (role,))
        permissions = {}
        for row in cur.fetchall():
            permissions[row[0]] = {
                'can_view': bool(row[1]),
                'can_edit': bool(row[2])
            }
        
        conn.close()
        return jsonify({'success': True, 'permissions': permissions})
    except Exception as e:
        import traceback
        print(f"Error in api_user_permissions: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Admin Field Visibility API
# ============================================================================
@csrf.exempt
@app.route('/api/admin/field_visibility', methods=['GET', 'POST'])
def api_admin_field_visibility():
    """Get or update field visibility settings"""
    # Check authentication
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # POST requires admin role
    if request.method == 'POST':
        role = session.get("role", "")
        if role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Ensure field_visibility table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS field_visibility (
                field_name TEXT PRIMARY KEY,
                is_visible INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        
        # Field list
        all_fields = [
            "watchlist_name", "watchlist_dob", "watchlist_nationality", "watchlist_address",
            "watchlist_document_type", "watchlist_id_number", "watchlist_contact_numbers", "watchlist_email_address",
            "first_name", "middle_name", "last_name", "dob", "nationality",
            "customer_gender", "customer_nationalities", "customer_contact_numbers", "customer_email_address",
            "document_type", "id_number", "address",
            "entity_name", "entity_type", "entity_registration_number",
            "entity_country_of_incorporation", "entity_industry", "entity_related_persons",
            "payment_reference", "payment_date", "payment_amount", "payment_currency",
            "payer_name", "payer_country", "beneficiary_name", "beneficiary_country",
            "payment_purpose", "payment_channel",
            "match_type", "match_probability", "match_reasons", "match_explanation", "screening_rationale"
        ]
        
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'visible_fields' not in data:
                return jsonify({'error': 'Invalid request data'}), 400
            
            visible_fields = set(data['visible_fields'])
            for field in all_fields:
                is_visible = 1 if field in visible_fields else 0
                cur.execute("""
                    INSERT INTO field_visibility (field_name, is_visible)
                    VALUES (?, ?)
                    ON CONFLICT(field_name) DO UPDATE SET is_visible=excluded.is_visible
                """, (field, is_visible))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Field visibility updated successfully'})
        
        # GET: Return visibility settings
        cur.execute("SELECT field_name, is_visible FROM field_visibility")
        visibility = {row[0]: bool(row[1]) for row in cur.fetchall()}
        conn.close()
        
        return jsonify({'success': True, 'all_fields': all_fields, 'visibility': visibility})
    except Exception as e:
        import traceback
        print(f"Error in api_admin_field_visibility: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Admin Settings API
# ============================================================================
@csrf.exempt
@app.route('/api/admin/settings', methods=['GET', 'POST'])
@role_required('admin')
def api_admin_settings():
    """Get or update system settings"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'settings' not in data:
                return jsonify({'error': 'Invalid request data'}), 400
            
            for key, value in data['settings'].items():
                cur.execute("""
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """, (key, str(value)))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
        # GET: Return all settings
        cur.execute("SELECT key, value FROM settings")
        settings = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
        
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        import traceback
        print(f"Error in api_admin_settings: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Admin Team Structure API
# ============================================================================
@csrf.exempt
@app.route('/api/admin/team_structure', methods=['GET'])
@role_required('admin')
def api_admin_team_structure():
    """Get team structure data"""
    try:
        from collections import defaultdict
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT id, name, role, team_lead, email FROM users")
        users = [dict(u) for u in cur.fetchall()]
        conn.close()
        
        for u in users:
            u["role"] = (u.get("role") or "").lower()
        
        nodes_by_level = defaultdict(list)
        for user in users:
            if "_1" in user["role"]:
                nodes_by_level[1].append(user)
            elif "_2" in user["role"]:
                nodes_by_level[2].append(user)
            elif "_3" in user["role"]:
                nodes_by_level[3].append(user)
            else:
                nodes_by_level[0].append(user)
        
        role_labels = {
            'admin': 'Admin',
            'team_lead_1': 'Team Lead (Level 1)',
            'team_lead_2': 'Team Lead (Level 2)',
            'team_lead_3': 'Team Lead (Level 3)',
            'reviewer_1': 'Reviewer (Level 1)',
            'reviewer_2': 'Reviewer (Level 2)',
            'reviewer_3': 'Reviewer (Level 3)',
            'qc': 'Quality Control',
            'qa': 'Quality Assurance',
            'sme': 'Subject Matter Expert',
            'operations_manager': 'Operations Manager',
        }
        
        return jsonify({
            'success': True,
            'nodes_by_level': dict(nodes_by_level),
            'role_labels': role_labels
        })
    except Exception as e:
        import traceback
        print(f"Error in api_admin_team_structure: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

from datetime import datetime, timedelta

@app.route("/admin/users")
def list_users():
    sort_order = request.args.get('sort', 'desc')
    inactive_days = request.args.get('inactive_days', '')

    conn = get_db_connection()

    # Start base query
    query = "SELECT * FROM users"
    filters = []
    params = []

    # Inactive filter
    if inactive_days and inactive_days.isdigit():
        cutoff = datetime.now() - timedelta(days=int(inactive_days))
        filters.append("(last_active IS NULL OR last_active < ?)")
        params.append(cutoff.strftime("%Y-%m-%d %H:%M:%S"))

    if filters:
        query += " WHERE " + " AND ".join(filters)

    # Sorting
    if sort_order == "asc":
        query += " ORDER BY last_active ASC"
    else:
        query += " ORDER BY last_active DESC"

    # Execute query
    users = conn.execute(query, params).fetchall()
    conn.close()

    return render_template("404_redirect.html"), 404

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

@app.route('/admin/create_user', methods=['GET', 'POST'])
@role_required('admin')
def create_user():
    if request.method == 'POST':
        # --- sanitize inputs ---
        email     = (request.form.get('email') or '').strip().lower()
        role      = (request.form.get('role') or '').strip()
        name      = (request.form.get('name') or '').strip()
        team_lead = (request.form.get('team_lead') or '').strip() or None

        # basic validation
        if not email or '@' not in email:
            flash('Please provide a valid email address.', 'warning')
            return redirect(url_for('create_user'))
        if not role:
            flash('Please select a role.', 'warning')
            return redirect(url_for('create_user'))

        # derive numeric level from role (e.g., reviewer_2 -> 2)
        level = None
        parts = role.split('_')
        if len(parts) >= 2 and parts[-1].isdigit():
            level = int(parts[-1])

        # set an unusable random password hash so the user must set a password via email
        random_unusable = generate_password_hash(token_urlsafe(32))

        conn = get_db_connection()
        try:
            cur = conn.execute(
                """
                INSERT INTO users (email, role, password_hash, name, team_lead, level)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (email, role, random_unusable, name, team_lead, level)
            )
            user_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash('A user with this email already exists.', 'danger')
            return redirect(url_for('list_users'))

        # create password-setup token
        token = token_urlsafe(32)
        token_hash = _sha256(token)
        expires_at = (datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat() + "Z"

        conn.execute(
            """
            INSERT INTO password_resets
                (user_id, token_hash, expires_at, requested_ip, user_agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                token_hash,
                expires_at,
                request.headers.get("X-Forwarded-For", request.remote_addr),
                request.headers.get("User-Agent", ""),
                datetime.utcnow().isoformat() + "Z",
            ),
        )
        conn.commit()
        conn.close()

        # email the setup link (welcome copy)
        setup_url = f"{APP_BASE_URL}{url_for('reset_password', token=token)}"
        try:
            _send_welcome_email(email, setup_url)   # <-- use the welcome helper
            flash(f'User created. Setup link emailed to {email}.', 'success')
        except Exception as e:
            current_app.logger.exception("SendGrid error while onboarding user: %s", e)
            flash('User created, but sending the setup email failed. Please check logs.', 'warning')

        return redirect(url_for('list_users'))

    # GET — render the form
    role_options = [
        ('admin', 'Admin'),
        ('operations_manager', 'Operations Manager'),

        ('team_lead_1', 'Team Lead (Level 1)'),
        ('team_lead_2', 'Team Lead (Level 2)'),
        ('team_lead_3', 'Team Lead (Level 3)'),

        ('qc_1', 'QC Team Lead (Level 1)'),
        ('qc_2', 'QC Team Lead (Level 2)'),
        ('qc_3', 'QC Team Lead (Level 3)'),

        ('qa_1', 'QA Team Lead (Level 1)'),
        ('qa_2', 'QA Team Lead (Level 2)'),
        ('qa_3', 'QA Team Lead (Level 3)'),

        ('qc_review_1', 'QC Reviewer (Level 1)'),
        ('qc_review_2', 'QC Reviewer (Level 2)'),
        ('qc_review_3', 'QC Reviewer (Level 3)'),

        ('reviewer_1', 'Reviewer (Level 1)'),
        ('reviewer_2', 'Reviewer (Level 2)'),
        ('reviewer_3', 'Reviewer (Level 3)'),

        ('qa_reviewer', 'QA Reviewer (Legacy)'),
        ('qc_reviewer', 'QC Reviewer (Legacy)'),
        ('sme', 'SME'),
    ]

    conn = get_db_connection()
    leads = conn.execute(
        """
        SELECT name
          FROM users
         WHERE role LIKE 'team_lead_%'
            OR role LIKE 'qc_%'
            OR role LIKE 'qa_%'
            OR role IN ('operations_manager', 'admin')
         ORDER BY name
        """
    ).fetchall()
    conn.close()


@app.route("/reviewer_panel/<task_id>", methods=["GET", "POST"])
@role_required("reviewer_1", "reviewer_2", "reviewer_3",
               "qc_1", "qc_2", "qc_3",
               "qc_review_1", "qc_review_2", "qc_review_3",
               "sme")
def reviewer_panel(task_id):
    import sqlite3
    from datetime import datetime, date
    from utils import derive_status  # (we are not changing utils.py)

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Load review & match --------------------------------------------------
    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Review not found.", "danger")
        return redirect(url_for("dashboard"))

    review = dict(row)

    cur.execute("SELECT * FROM matches WHERE task_id = ?", (task_id,))
    match = dict(cur.fetchone() or {})
    # allow template to read fields directly off `review` too
    review.update(match)

    # --- Helpers --------------------------------------------------------------
    def _dt_any(s):
        if not s:
            return None
        s = str(s).strip()
        try:
            # tolerate "YYYY-MM-DDTHH:MM:SS[.sss][Z]" formats
            return datetime.fromisoformat(s.replace("Z", "").split(".")[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(s)
            except Exception:
                return None

    def _fmt_date(s, fmt="%d-%m-%Y"):
        d = _dt_any(s)
        return d.strftime(fmt) if d else None

    # --- Work out level / modes ----------------------------------------------
    role = (session.get("role") or "").lower()
    user_id = session.get("user_id")

    # default level heuristic if needed
    def _best_open_level(r: dict) -> int:
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"):
            return 2
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"):
            return 3
        for lv in (3, 2, 1):
            if r.get(f"l{lv}_assigned_to") or r.get(f"l{lv}_outcome"):
                return lv
        return 1

    level = None
    sme_mode = False
    qc_mode = False
    qc_level = None
    qc_readonly = True

    if role.startswith("reviewer_"):
        level = int(role.split("_")[-1])
    elif role.startswith("qc_"):
        qc_mode = True
        qc_level = int(role.split("_")[-1])
        # show the same stage as the QC level
        level = qc_level
    elif role == "sme":
        sme_mode = True
        # allow SME to pin a level via query; otherwise heuristics
        level = request.args.get("level", type=int) or _best_open_level(review)
    else:
        level = _best_open_level(review)

    # --- Names for referenced IDs --------------------------------------------
    id_set = set()
    for lv in (1, 2, 3):
        for suffix in ("assigned_to", "completed_by", "qc_assigned_to", "sme_assigned_to"):
            uid = review.get(f"l{lv}_{suffix}")
            if uid:
                id_set.add(uid)

    name_map = {}
    if id_set:
        placeholders = ",".join("?" * len(id_set))
        cur.execute(f"SELECT id, COALESCE(name,email) AS name FROM users WHERE id IN ({placeholders})", list(id_set))
        name_map = {r["id"]: r["name"] for r in cur.fetchall()}

    # --- Assignment summary for side box -------------------------------------
    assignments_summary = []
    for lv in (1, 2, 3):
        assignments_summary.append({
            "level": lv,
            "review": {
                "completed_by_name": name_map.get(review.get(f"l{lv}_completed_by")),
                "completed_on": _fmt_date(review.get(f"l{lv}_date_completed")),
            },
            "qc": {
                "assigned_to_name": name_map.get(review.get(f"l{lv}_qc_assigned_to")),
                "checked_on": _fmt_date(review.get(f"l{lv}_qc_check_date")),
            },
            "sme": {
                "assigned_to_name": name_map.get(review.get(f"l{lv}_sme_assigned_to")),
                "returned_on": _fmt_date(review.get(f"l{lv}_sme_returned_date")),
            }
        })

    # --- Status for banner ----------------------------------------------------
    status = derive_status(review, int(level or 1))

    # --- SME panel data (read-only unless SME role uses its own page) --------
    def compute_sme_panel(r: dict, default_level: int):
        lv = default_level
        return {
            "level": lv,
            "query": (r.get(f"l{lv}_sme_query") or "").strip(),
            "advice": (r.get(f"l{lv}_sme_response") or "").strip(),
            "returned": _fmt_date(r.get(f"l{lv}_sme_returned_date")),
            "selected": _fmt_date(r.get(f"l{lv}_sme_selected_date")),
            "has_any": any([
                r.get(f"l{lv}_referred_to_sme"),
                r.get(f"l{lv}_sme_query"),
                r.get(f"l{lv}_sme_response"),
                r.get(f"l{lv}_sme_returned_date"),
                r.get(f"l{lv}_sme_selected_date"),
            ]),
            "sme_user_id": r.get(f"l{lv}_sme_assigned_to"),
        }

    sme_panel = compute_sme_panel(review, default_level=level)
    sme_reviewer_name = name_map.get(sme_panel["sme_user_id"])

    # --- Sidebar header: who is it "assigned to" right now? ------------------
    st = (status or "").lower()
    is_qc_state = (" qc " in f" {st} ") or st.startswith(f"level {level} qc") or ("qc –" in st) or ("qc -" in st)
    is_sme_state = ("referred to sme" in st) or ("sme –" in st) or ("sme -" in st)

    orig_id = review.get("assigned_to")
    qc_ass_id = review.get("qc_assigned_to")
    sme_ass_id = review.get(f"l{level}_sme_assigned_to")

    if is_qc_state:
        header_assigned_role = "QC Reviewer"
        header_assigned_name = name_map.get(qc_ass_id)
    elif is_sme_state or sme_mode:
        header_assigned_role = "SME Reviewer"
        header_assigned_name = name_map.get(sme_ass_id)
    else:
        header_assigned_role = "Reviewer"
        header_assigned_name = name_map.get(orig_id)

    # --- Normalised fields for comparison tables -----------------------------
    def first(*keys, src=None):
        d = src or review
        for k in keys:
            v = d.get(k)
            if v not in (None, "", "NULL", "N/A"):
                return str(v)
        return ""

    customer_fields_dict = {
        "name": (
            (first("customer_first_name") + " " + first("customer_last_name")).strip()
            or first("customer_name", "name", "customer_full_name")
        ),
        "dob": first("customer_dob", "dob", "date_of_birth"),
        "nationality": first("customer_nationality", "customer_nationalities", "nationality"),
        "address": first("customer_address", "address", "residential_address"),
        "document_type": first("customer_document_type", "document_type"),
        "id_number": first("customer_id_number", "id_number", "document_number"),
        "email_address": first("customer_email", "customer_email_address", "email"),
        "contact_numbers": first("customer_phone", "customer_contact_numbers", "phone", "mobile"),
    }

    watchlist_fields_dict = {
        "name": first("watchlist_name", "wl_name"),
        "dob": first("watchlist_dob", "wl_dob"),
        "nationality": first("watchlist_nationality", "wl_nationality"),
        "address": first("watchlist_address", "wl_address"),
        "document_type": first("watchlist_document_type", "wl_document_type"),
        "id_number": first("watchlist_id_number", "wl_id_number"),
        "email_address": first("watchlist_email_address", "wl_email"),
        "contact_numbers": first("watchlist_contact_numbers", "wl_phone"),
    }

    # Canonical row order for your partials
    field_labels = [
        ("name", "Name"),
        ("dob", "Date of Birth"),
        ("nationality", "Nationality"),
        ("address", "Address"),
        ("document_type", "Document Type"),
        ("id_number", "ID Number"),
        ("email_address", "Email"),
        ("contact_numbers", "Phone"),
    ]
    comparison_rows = [{
        "label": label,
        "customer": (customer_fields_dict.get(key) or "—"),
        "watchlist": (watchlist_fields_dict.get(key) or "—"),
    } for key, label in field_labels]

    # --- QC context for the sidebar QC panel ---------------------------------
    qc_outcome = qc_rationale = qc_returned_at = qc_assigned_name = None
    qc_referred = False
    if qc_mode and qc_level:
        # Who can edit? Only the assigned QC at that level and if not ended yet.
        assignee_id = review.get(f"l{qc_level}_qc_assigned_to")
        qc_end = review.get(f"l{qc_level}_qc_end_time")
        qc_readonly = not (assignee_id and user_id and assignee_id == user_id and not qc_end)

        qc_outcome = review.get(f"l{qc_level}_qc_outcome")
        qc_rationale = review.get(f"l{qc_level}_qc_rationale")
        qc_referred = bool(review.get(f"l{qc_level}_qc_referred_to_sme"))
        qc_returned_at = _fmt_date(review.get(f"l{qc_level}_qc_returned_date"))
        if assignee_id:
            cur.execute("SELECT COALESCE(name,email) AS name FROM users WHERE id = ?", (assignee_id,))
            r = cur.fetchone()
            qc_assigned_name = r["name"] if r else None

    # --- Other bits the template uses ----------------------------------------
    system_rationale = match.get("match_explanation")
    record_type = (match.get("hit_type") or "Individual")
    hit_type = (record_type or "Individual").lower()
    total_score = match.get("total_score") or "None"

    # RCA list (keep safe if helper not present)
    try:
        rca_options = get_rca_options()
    except Exception:
        rca_options = [
            "Name/alias variation",
            "Biographical mismatch",
            "False positive – data quality",
            "Context not relevant",
            "Other",
        ]


    # Outcomes list for Decision box
    names = _load_outcomes_from_db(cur)
    outcomes = [{"name": n} for n in names]
    conn.close()



# helpers/chaser_cycle.py
from datetime import date, timedelta
import sqlite3
import logging

log = logging.getLogger(__name__)

# robust date parser used here only
def _parse_d(v):
    if v in (None, "", "—"):
        return None
    from datetime import datetime
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _fetchall_dicts(cur):
    rows = cur.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return [dict(r) for r in rows]
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in rows]

def _orig_build_chaser_cycle_for_reviewer(conn, reviewer_id: int, level: int, selected_date: str):
    """
    Returns (chaser_cycle, chaser_headers, chaser_keys, today_key).

    - Considers only rows assigned to this reviewer at the given level.
    - Excludes cases with outreach_response_received_date present.
    - Buckets: 'Overdue' + Mon..Sun of THIS week.
    """
    # make sure we read dict-ish rows
    try:
        conn.row_factory = sqlite3.Row
    except Exception:
        pass

    today   = date.today()
    monday  = today - timedelta(days=today.weekday())
    week    = [monday + timedelta(days=i) for i in range(7)]
    weekend = monday + timedelta(days=6)

    chaser_headers = ["Overdue"] + [d.strftime("%d/%m/%Y") for d in week]
    chaser_keys    = ["overdue"]  + [d.strftime("%Y-%m-%d") for d in week]
    today_key      = today.strftime("%Y-%m-%d")

    # structure
    chaser_cycle = {
        "1":   {k: 0 for k in chaser_keys},
        "2":   {k: 0 for k in chaser_keys},
        "3":   {k: 0 for k in chaser_keys},
        "NTC": {k: 0 for k in chaser_keys},
    }

    assign_col = "assigned_to"
    sql = f"""
        SELECT id, task_id,
               Chaser1DueDate, Chaser1IssuedDate,
               Chaser2DueDate, Chaser2IssuedDate,
               Chaser3DueDate, Chaser3IssuedDate,
               NTCDueDate,   NTCIssuedDate,
               outreach_response_received_date
        FROM reviews
        WHERE {assign_col} = ?
          AND (outreach_response_received_date IS NULL OR TRIM(outreach_response_received_date) = '')
    """

    # ensure reviewer_id is an int for INTEGER compare
    reviewer_id = int(reviewer_id)

    cur = conn.cursor()
    cur.execute(sql, (reviewer_id,))
    rows = _fetchall_dicts(cur)

    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        # (label, due-column)
        for label, col in (("1","Chaser1DueDate"),
                           ("2","Chaser2DueDate"),
                           ("3","Chaser3DueDate"),
                           ("NTC","NTCDueDate")):
            d = _parse_d(r.get(col))
            if not d:
                continue
            if d < monday:
                chaser_cycle[label]["overdue"] += 1
            elif monday <= d <= weekend:
                chaser_cycle[label][d.strftime("%Y-%m-%d")] += 1
            # future (after weekend) — ignore for “current week”

    # debug totals so you can see numbers in logs
    totals = {lab: sum(chaser_cycle[lab].values()) for lab in chaser_cycle}
    log.debug("ChaserCycle L%s reviewer=%s totals=%s", level, reviewer_id, totals)

    return chaser_cycle, chaser_headers, chaser_keys, today_key

# --- route ---
@app.route('/reviewer_dashboard')
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3')
def reviewer_dashboard():
    # --- who am I ---
    user_id_raw = session['user_id']
    role        = session['role']
    level       = role.split('_')[1]  # "1" | "2" | "3"
    user_id     = int(user_id_raw)    # <-- ensure INTEGER comparisons

    # --- date filter (for tiles/charts that are date-scoped) ---
    date_range  = request.args.get("date_range", "all")
    _outcome = (request.args.get('outcome') or request.args.get('l1_outcome') or request.args.get('decision_outcome') or '').strip()

    today       = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    def _within_range(dt: datetime) -> bool:
        if not dt:
            return False
        d = dt.date()
        if date_range == "wtd":   return monday_this <= d <= today
        if date_range == "prevw": return monday_prev <= d <= sunday_prev
        if date_range == "30d":   return d >= (today - timedelta(days=30))
        return True  # "all"

    # --- column names for this level ---
    assign_col       = "assigned_to"
    completed_by_col = "completed_by"
    completed_dt_col = "date_completed"
    qc_chk_col       = "qc_check_date"
    qc_rew_col       = "qc_rework_required"
    qc_done_col      = "qc_rework_completed"

    # --- utils ---
    def _parse_dt(s):
        if not s: return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z","").split(".")[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(s)
            except Exception:
                return None

    # --- DB load ---
    conn = get_db()
    cur  = conn.cursor()

    # All tasks touching this reviewer (assigned OR finished by them) — no date filter
    cur.execute(f"""
        SELECT * FROM reviews
        WHERE {assign_col} = ? OR {completed_by_col} = ?
    """, (user_id, user_id))  # <-- use int(user_id)
    all_rows_mine = [dict(r) for r in cur.fetchall()]

    # Convenience subset: currently assigned to me (LIVE WIP universe)
    my_assigned_rows = [r for r in all_rows_mine if (r.get(assign_col) == user_id)]  # <-- int compare

    # ─── Chaser Cycle (Weekly Grid by Date) for THIS reviewer ───────────
    # Rows = Mon..Sun of current week; Columns = Overdue, 7, 14, 21, 28, NTC
    # Counts include only items NOT YET ISSUED.
    from collections import defaultdict

    def _coalesce_key(d, names):
        lower = {k.lower(): k for k in d.keys()}
        for name in names:
            if name and name.lower() in lower:
                return lower[name.lower()]
        return None

    def _parse_date_any_strict(s):
        try:
            from dateutil import parser as _p
        except Exception:
            _p = None
        if not s:
            return None
        if isinstance(s, (datetime,)):
            return s.date()
        if isinstance(s, str):
            ss = s.strip()
            if not ss or ss.lower() in ("none","null","n/a","na"):
                return None
            for _fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y","%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(ss, _fmt).date()
                except Exception:
                    pass
            if _p:
                try:
                    return _p.parse(ss).date()
                except Exception:
                    return None
        return None

    def _is_blank_issued(v):
        if v is None: return True
        s = str(v).strip().lower()
        if s in ("", "none", "null", "n/a", "na", "-", "0", "false"): return True

        # treat common zero-dates as blank
        if s in ("00/00/0000", "0000-00-00"): return True
        return False

    
    # 5-day working week (Mon..Fri of the current week)
    week_days = [monday_this + timedelta(days=i) for i in range(5)]
    chaser_week_headers = ["Overdue","7","14","21","NTC"]
    chaser_week_rows = [
        {"date": d.strftime("%d/%m/%Y"), "iso": d.isoformat(), **{h:0 for h in chaser_week_headers}}
        for d in week_days
    ]

    # Column aliases for robustness across DB variants
    DUE_MAP = {
        "7":  ["Chaser1DueDate","Chaser_1_DueDate","chaser1_due","chaser_1_due","Outreach1DueDate","Outreach_Cycle_1_Due"],
        "14": ["Chaser2DueDate","Chaser_2_DueDate","chaser2_due","chaser_2_due","Outreach2DueDate","Outreach_Cycle_2_Due"],
        "21": ["Chaser3DueDate","Chaser_3_DueDate","chaser3_due","chaser_3_due","Outreach3DueDate","Outreach_Cycle_3_Due"],
        "NTC": ["NTCDueDate","NTC_DueDate","ntc_due","NTC Due Date","NTC_Due"]
    }
    ISSUED_MAP = {
        "7":  ["Chaser1IssuedDate","Chaser1DateIssued","chaser1_issued","Outreach1Date","Outreach_Cycle_1_Issued","Outreach Cycle 1 Issued"],
        "14": ["Chaser2IssuedDate","Chaser2DateIssued","chaser2_issued","Outreach2Date","Outreach_Cycle_2_Issued","Outreach Cycle 2 Issued"],
        "21": ["Chaser3IssuedDate","Chaser3DateIssued","chaser3_issued","Outreach3Date","Outreach_Cycle_3_Issued","Outreach Cycle 3 Issued"],
        "NTC": ["NTCIssuedDate","NTC_IssuedDate","ntc_issued"]
    }

    STATUS_TO_COL = {
        "7 day chaser due": "7",
        "chaser1_due": "7",
        "chaser1 due": "7",
        "14 day chaser due": "14",
        "chaser2_due": "14",
        "chaser2 due": "14",
        "21 day chaser due": "21",
        "chaser3_due": "21",
        "chaser3 due": "21",
        "ntc_due": "NTC",
        "ntc due": "NTC",
        "ntc - due": "NTC"
    }

    def _first_nonblank(rec: dict, keys: list):
        for k in keys:
            if k in rec and str(rec.get(k) or "").strip():
                return rec.get(k)
        return None

    # draw directly from DB to avoid any prior label munging
    _conn2 = sqlite3.connect('scrutinise_workflow.db')
    _conn2.row_factory = sqlite3.Row
    _cur2 = _conn2.cursor()
    try:
        _rows = _cur2.execute("SELECT * FROM reviews").fetchall()
    except Exception:
        _rows = []  # fail-safe if DB missing in unit tests

    today = date.today()

    for rec in _rows:
        # normalize dict with lowercased keys for resilience
        r = { (k or ""): rec[k] for k in rec.keys() }
        low_status = (str(r.get("status") or "")).strip().lower()

        # determine which cycle this row is in, strictly from STATUS
        is_overdue = "overdue" in low_status
        col = None
        for key, mapped in STATUS_TO_COL.items():
            if key in low_status:
                col = mapped
                break
        if not col and not is_overdue:
            # not in a chaser cycle / NTC, skip entirely
            continue

        # choose the relevant due date based on the column
        if is_overdue:
            # try each typ to find the due date that matches this record
            try_order = ["7","14","21","NTC"]
        else:
            try_order = [col]

        due_date = None
        for typ in try_order:
            due_raw = _first_nonblank(r, DUE_MAP.get(typ, [])) or ""
            # Parse date robustly
            d = None
            for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%Y/%m/%d"):
                try:
                    d = datetime.strptime(str(due_raw).strip(), fmt).date()
                    break
                except Exception:
                    continue
            if d:
                due_date = d
                chosen_typ = typ
                break

        if not due_date:
            continue  # can't place it on the working week grid

        # Respect "Counts include only items not yet issued."
        issued_raw = _first_nonblank(r, ISSUED_MAP.get(chosen_typ, []))
        if issued_raw and str(issued_raw).strip():
            continue

        # only current WORKING week rows
        if not (week_days[0] <= due_date <= week_days[-1]):
            continue

        # place into Overdue or the specific cycle
        target_col = "Overdue" if (is_overdue and due_date < today) else chosen_typ

        # increment the matching row
        for row in chaser_week_rows:
            if row["iso"] == due_date.isoformat():
                row[target_col] += 1
                break

    # Expose unified names used by the template
    chaser_headers = chaser_week_headers
    

    # ---------- KPI: Active WIP (LIVE) ----------
    from collections import defaultdict, Counter
    wip = {"pending": 0, "outreach": 0, "overdue": 0, "rework": 0, "sme_ref": 0, "sme_ret": 0}
    for r in my_assigned_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        st = (derive_case_status(r) or "").lower()
        if ("pending review" in st) or (f"pending level {level} review" in st):
            wip["pending"] += 1
        if r.get(qc_rew_col) and not r.get(qc_done_col):
            wip["rework"] += 1
        # Include both "Referred to SME" and "Referred to AI SME" in WIP count
        if "referred to sme" in st or "referred to ai sme" in st:
            wip["sme_ref"] += 1
        if "returned from sme" in st:
            wip["sme_ret"] += 1
        if "outreach" in st:
            wip["outreach"] += 1
        if "overdue" in st:
            wip["overdue"] += 1
    active_wip = sum(wip.values())

    # total currently assigned
    cur.execute(f"SELECT COUNT(*) FROM reviews WHERE {assign_col} = ?", (user_id,))
    total_allocated = cur.fetchone()[0] or 0

    # ---------- KPI: Completed (date-filtered) ----------
    completed_count = 0
    for r in all_rows_mine:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        if r.get(completed_by_col) != user_id:   # <-- int compare
            continue
        dt = _parse_dt(r.get(completed_dt_col))
        if dt and _within_range(dt):
            completed_count += 1

    # ---------- QC stats (date-filtered on reviews.l{level}_qc_check_date) ----------
    qc_date_col    = "qc_check_date"
    qc_outcome_col = "qc_outcome"
    # Count QC-checked items for THIS reviewer (completed_by me), date-filtered on qc_date_col
    qc_sql = f"""
        SELECT {qc_date_col}
        FROM reviews
        WHERE {completed_by_col} = ? AND {qc_date_col} IS NOT NULL
    """
    qc_params = [user_id]
    if date_range == 'wtd':
        qc_sql += f" AND date({qc_date_col}) BETWEEN ? AND ?"
        qc_params += [monday_this.isoformat(), today.isoformat()]
    elif date_range == 'prevw':
        qc_sql += f" AND date({qc_date_col}) BETWEEN ? AND ?"
        qc_params += [monday_prev.isoformat(), sunday_prev.isoformat()]
    elif date_range == '30d':
        qc_sql += f" AND date({qc_date_col}) >= date('now','-30 days')"

    cur.execute(qc_sql, qc_params)
    qc_sample = len(cur.fetchall())

    # Pass/fail from reviews.l{level}_qc_outcome
    cur.execute(
        f"SELECT lower(trim(coalesce({qc_outcome_col}, ''))) FROM reviews "
        f"WHERE {completed_by_col} = ? AND {qc_date_col} IS NOT NULL",
        (user_id,)
    )
    outcomes = [row[0] for row in cur.fetchall()]

    PASS_TOKENS = {'pass', 'passed', 'ok', 'approved', 'no issues', 'acceptable'}
    def is_pass(o: str) -> bool:
        if not o:
            return False
        o = o.replace('qc ', '').replace('_',' ').replace(' - ','-').strip().lower()
        return (o in PASS_TOKENS) or (o == 'pass')
    qc_pass_cnt = sum(1 for o in outcomes if is_pass(o))
    qc_fail_cnt = max(qc_sample - qc_pass_cnt, 0)
    qc_pass_pct = round((qc_pass_cnt / qc_sample) * 100, 1) if qc_sample else 0.0

    # ---------- Daily production series (Completed-by-me, by day) ----------
    if date_range == "wtd":
        start_day, end_day = monday_this, today
    elif date_range == "prevw":
        start_day, end_day = monday_prev, sunday_prev
    elif date_range == "30d":
        start_day, end_day = today - timedelta(days=29), today
    else:
        start_day, end_day = today - timedelta(days=59), today

    day_counts = defaultdict(int)
    for r in all_rows_mine:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        if r.get(completed_by_col) != user_id:
            continue
        dt = _parse_dt(r.get(completed_dt_col))
        if dt and (start_day <= dt.date() <= end_day):
            day_counts[dt.date()] += 1

    daily_labels, daily_counts = [], []
    cur_day = start_day
    while cur_day <= end_day:
        daily_labels.append(cur_day.strftime("%d %b"))
        daily_counts.append(day_counts.get(cur_day, 0))
        cur_day += timedelta(days=1)

    # ---------- Rework Age Profile (LIVE) ----------
    def _bucket(d: datetime):
        if not d: return "5 days+"
        days = (today - d.date()).days
        if days <= 2: return "1–2 days"
        if days <= 5: return "3–5 days"
        return "5 days+"

    rework_buckets = {"1–2 days": 0, "3–5 days": 0, "5 days+": 0}
    for r in my_assigned_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        if r.get(qc_rew_col) and not r.get(qc_done_col):
            dt = _parse_dt(r.get(qc_chk_col)) or _parse_dt(r.get("updated_at"))
            rework_buckets[_bucket(dt)] += 1

    # ---------- Case Status & Age Profile (LIVE) ----------

        cur.execute("SELECT * FROM reviews")
        all_rows_all = [dict(r) for r in cur.fetchall()]

    def _last_touched_date(r: dict):
        fields = [
            r.get("updated_at"),
            r.get("date_assigned"),
            r.get("date_completed"),
            r.get("qc_check_date"),
            r.get("sme_selected_date"),
            r.get("sme_returned_date"),
        ]
        dts = [_parse_dt(x) for x in fields if x]
        return max(dts) if dts else None

    def _bucket(d: datetime):
        if not d: return "5 days+"
        days = (today - d.date()).days
        if days <= 2:  return "1–2 days"
        if days <= 5:  return "3–5 days"
        return "5 days+"

     # ---------- Case Status & Age Profile (RAW DB VIEW) ----------
    # Build the table directly from the raw DB status. No derivation, no remapping.
    from collections import Counter, defaultdict
    import re as _re

    def _slug(s: str) -> str:
        s = (s or "").strip().lower()
        s = _re.sub(r"[^a-z0-9]+", "_", s)
        s = _re.sub(r"_+", "_", s).strip("_")
        return s or "blank"

    dist_counter  = Counter()
    age_by_status = defaultdict(lambda: {"1–2 days": 0, "3–5 days": 0, "5 days+": 0})

    # Ensure we're using all reviews for Ops MI (management view).
    # If you've already created all_rows_all above, this will use it; otherwise you can insert the 3 lines below it.
    # cur.execute("SELECT * FROM reviews")
    # all_rows_all = [dict(r) for r in cur.fetchall()]

    for r in my_assigned_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        raw_label = (r.get("status") or "").strip()
        if not raw_label:
            raw_label = "(Blank)"
        dist_counter[raw_label] += 1
        age_by_status[raw_label][_bucket(_last_touched_date(r))] += 1

    # Dynamic row order: highest count first, then alphabetical
    # Include all statuses including completed in Case Status & Age Profile
    row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))

    total_rows = sum(dist_counter.values()) or 1
    ind_distribution = [
        {"status": st, "count": dist_counter.get(st, 0), "pct": round(dist_counter.get(st, 0) / total_rows * 100, 1)}
        for st in row_order
    ]
    ind_age_totals = {
        "1–2 days": sum(age_by_status[st]["1–2 days"] for st in row_order),
        "3–5 days": sum(age_by_status[st]["3–5 days"] for st in row_order),
        "5 days+":  sum(age_by_status[st]["5 days+"]   for st in row_order),
    }

    

    # --- Build Case Status & Age Profile aggregates for template if missing ---
    # Create age_rows and age_totals expected by reviewer_dashboard.html
    try:
        age_rows
    except NameError:
        age_rows = None
    if not age_rows:
        try:
            # dist_counter: counts per raw status; age_by_status: bucket counts per status; row_order: a sequence of statuses
            total_rows = (sum(dist_counter.values()) or 0)
            _total_rows = total_rows or 1  # avoid div-by-zero for pct
            age_rows = []
            for st in (row_order if 'row_order' in locals() else sorted(dist_counter.keys())):
                a12 = (age_by_status.get(st, {}).get("1–2 days") 
                       if isinstance(age_by_status, dict) and "1–2 days" in next(iter(age_by_status.values() or [{}])) 
                       else age_by_status[st]["1–2 days"])
                a35 = (age_by_status.get(st, {}).get("3–5 days") 
                       if isinstance(age_by_status, dict) and "3–5 days" in next(iter(age_by_status.values() or [{}])) 
                       else age_by_status[st]["3–5 days"])
                a5p = (age_by_status.get(st, {}).get("5 days+") 
                       if isinstance(age_by_status, dict) and "5 days+" in next(iter(age_by_status.values() or [{}])) 
                       else age_by_status[st]["5 days+"])
                cnt = dist_counter.get(st, 0)
                row = {
                    "status": st,
                    "count": cnt,
                    "pct": round((cnt / _total_rows) * 100, 1),
                    "bucket_12": a12 or 0,
                    "bucket_35": a35 or 0,
                    "bucket_5p": a5p or 0,
                    # conservative links (status-level filtering optional depending on my_tasks implementation)
                    "link":    url_for('my_tasks', status=st.lower(), date_range='all'),
                    "link_12": url_for('my_tasks', status=st.lower(), age_bucket='1–2 days', date_range='all'),
                    "link_35": url_for('my_tasks', status=st.lower(), age_bucket='3–5 days', date_range='all'),
                    "link_5p": url_for('my_tasks', status=st.lower(), age_bucket='5 days+', date_range='all'),
                }
                age_rows.append(row)
        except Exception as _e:
            app.logger.exception("Failed to synthesize age_rows: %s", _e)
            age_rows = []

    # Ensure age_totals present
    if 'age_totals' not in locals() or not age_totals:
        try:
            total_rows = sum(dist_counter.values())
        except Exception:
            total_rows = sum((r.get('count',0) for r in age_rows), 0) if age_rows else 0
        # Map individual totals to the keys the template expects
        try:
            _i12 = ind_age_totals.get("1–2 days", 0)
            _i35 = ind_age_totals.get("3–5 days", 0)
            _i5p = ind_age_totals.get("5 days+", 0)
        except Exception:
            # derive from age_rows if needed
            _i12 = sum((r.get('bucket_12',0) for r in age_rows), 0)
            _i35 = sum((r.get('bucket_35',0) for r in age_rows), 0)
            _i5p = sum((r.get('bucket_5p',0) for r in age_rows), 0)
        age_totals = {
            "count": total_rows or 0,
            "pct":   100.0 if (total_rows or 0) > 0 else 0.0,
            "bucket_12": _i12,
            "bucket_35": _i35,
            "bucket_5p": _i5p,
        }
    # Clean link keys (don’t change your template — this just supplies keys)
    display_order = [(st, _slug(st)) for st in row_order]
    # ---------- Case Status & Age Profile (RAW DB VIEW) ----------
    # Build the table directly from the raw DB status. No derivation, no remapping.
    from collections import Counter, defaultdict
    import re as _re

    def _slug(s: str) -> str:
        s = (s or "").strip().lower()
        s = _re.sub(r"[^a-z0-9]+", "_", s)
        s = _re.sub(r"_+", "_", s).strip("_")
        return s or "blank"

    dist_counter  = Counter()
    age_by_status = defaultdict(lambda: {"1–2 days": 0, "3–5 days": 0, "5 days+": 0})

    # Ensure we're using all reviews for Ops MI (management view).
    # If you've already created all_rows_all above, this will use it; otherwise you can insert the 3 lines below it.
    # cur.execute("SELECT * FROM reviews")
    # all_rows_all = [dict(r) for r in cur.fetchall()]

    for r in all_rows_all:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        raw_label = (r.get("status") or "").strip()
        if not raw_label:
            raw_label = "(Blank)"
        dist_counter[raw_label] += 1
        age_by_status[raw_label][_bucket(_last_touched_date(r))] += 1

    # Dynamic row order: highest count first, then alphabetical
    row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))

    total_rows = sum(dist_counter.values()) or 1
    ind_distribution = [
        {"status": st, "count": dist_counter.get(st, 0), "pct": round(dist_counter.get(st, 0) / total_rows * 100, 1)}
        for st in row_order
    ]
    ind_age_totals = {
        "1–2 days": sum(age_by_status[st]["1–2 days"] for st in row_order),
        "3–5 days": sum(age_by_status[st]["3–5 days"] for st in row_order),
        "5 days+":  sum(age_by_status[st]["5 days+"]   for st in row_order),
    }

    # Clean link keys (don’t change your template — this just supplies keys)
    display_order = [(st, _slug(st)) for st in row_order]

    # --- Chaser Cycle (Reviewer) using SAME connection and INT id ---
    try:
        _tmp = build_chaser_cycle_for_reviewer(conn, reviewer_id=user_id, level=int(level), selected_date=date_range)
        if isinstance(_tmp, (list, tuple)):
            if len(_tmp) == 4:
                chaser_cycle, chaser_headers, chaser_keys, today_key = _tmp
            elif len(_tmp) == 3:
                chaser_cycle, chaser_headers, chaser_keys = _tmp
                today_key = None
            else:
                chaser_cycle, chaser_headers, chaser_keys, today_key = None, [], [], None
        else:
            chaser_cycle, chaser_headers, chaser_keys, today_key = None, [], [], None
    except Exception as e:
        app.logger.exception("Failed to build reviewer chaser_cycle: %s", e)
        chaser_cycle, chaser_headers, chaser_keys, today_key = {}, ['Overdue'], ['overdue'], date.today().strftime("%Y-%m-%d")
    conn.close()

    age_rows = locals().get('age_rows', [])
    return render_template("404_redirect.html"), 404

@app.route('/ops/mi')
def mi_dashboard():

    # ─── Security ─────────────────────────────────────────────────────────
    if session.get("role") not in ("operations_manager", "admin"):
        flash("Access restricted", "danger")
        return redirect(url_for("login"))

    # ─── Filters ──────────────────────────────────────────────────────────
    date_range     = request.args.get("date_range", "all")   # all, wtd, prevw, 30d
    selected_team  = request.args.get("team",       "all")
    selected_level = request.args.get("level",      "all")   # 'all','1','2','3'

    _outcome      = (request.args.get('outcome') or '').strip()
    # Week boundaries (UTC, Monday start)
    today        = datetime.utcnow().date()
    monday_this  = today - timedelta(days=today.weekday())
    monday_prev  = monday_this - timedelta(days=7)
    sunday_prev  = monday_this - timedelta(days=1)

    db  = get_db()
    cur = db.cursor()

    rows = []  # safety: ensure 'rows' is defined
    # ─── Build Teams dropdown ─────────────────────────────────────────────
    cur.execute("""
      SELECT DISTINCT team_lead
        FROM users
       WHERE team_lead IS NOT NULL
         AND team_lead <> ''
       ORDER BY team_lead
    """)
    teams = [{"label": "All Teams", "value": "all"}] + [
        {"label": row["team_lead"], "value": row["team_lead"]}
        for row in cur.fetchall()
    ]

    # ─── GLOBAL DATA for Escalation & Forecast (ignore all filters) ──────
    cur.execute("SELECT * FROM reviews")
    reviews_all = [dict(r) for r in cur.fetchall()]


    # ─── Chaser Cycle (Weekly Grid by Date) ───────────────────────────────
    # Rows = dates in current week (Mon..Sun); Columns = Overdue, 7, 14, 21, 28, NTC
    # Counts are driven by DueDate fields in `reviews` and only include items not yet issued.
    from collections import defaultdict

    def _coalesce_key(d, names):
        lower = {k.lower(): k for k in d.keys()}
        for name in names:
            n = name.lower()
            if n in lower:
                return lower[n]
        return None

    def _parse_date_any_strict(s):
        try:
            from dateutil import parser as _p
        except Exception:
            _p = None
        if not s:
            return None
        if isinstance(s, (datetime,)):
            return s.date()
        if isinstance(s, str):
            ss = s.strip()
            if not ss or ss.lower() in ("none","null","n/a","na"):
                return None
            for _fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y","%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(ss, _fmt).date()
                except Exception:
                    pass
            if _p:
                try:
                    return _p.parse(ss).date()
                except Exception:
                    return None
        return None

    def _is_blank_issued(v):
        if v is None: return True
        s = str(v).strip().lower()
        if s in ("", "none", "null", "n/a", "na", "-", "0", "false"): return True
        # Treat any date-like content as issued
        return False

    # Build week rows
    week_days = [monday_this + timedelta(days=i) for i in range(7)]
    
    # Working week (Mon..Fri) for current week
    week_days = [monday_this + timedelta(days=i) for i in range(5)]
    chaser_week_headers = ["Overdue","7","14","21","NTC"]
    chaser_week_rows = [
        {"date": d.strftime("%d/%m/%Y"), "iso": d.isoformat(), **{h:0 for h in chaser_week_headers}}
        for d in week_days
    ]

    # Column name aliases across DB variants
    DUE_MAP = {
        "7":  ["Chaser1DueDate","Chaser_1_DueDate","chaser1_due","chaser_1_due","Outreach1DueDate","Outreach_Cycle_1_Due"],
        "14": ["Chaser2DueDate","Chaser_2_DueDate","chaser2_due","chaser_2_due","Outreach2DueDate","Outreach_Cycle_2_Due"],
        "21": ["Chaser3DueDate","Chaser_3_DueDate","chaser3_due","chaser_3_due","Outreach3DueDate","Outreach_Cycle_3_Due"],
        "NTC": ["NTCDueDate","NTC_DueDate","ntc_due","NTC Due Date","NTC_Due"]
    }
    ISSUED_MAP = {
        "7":  ["Chaser1IssuedDate","Chaser1DateIssued","chaser1_issued","Outreach1Date","Outreach_Cycle_1_Issued","Outreach Cycle 1 Issued"],
        "14": ["Chaser2IssuedDate","Chaser2DateIssued","chaser2_issued","Outreach2Date","Outreach_Cycle_2_Issued","Outreach Cycle 2 Issued"],
        "21": ["Chaser3IssuedDate","Chaser3DateIssued","chaser3_issued","Outreach3Date","Outreach_Cycle_3_Issued","Outreach Cycle 3 Issued"],
        "NTC": ["NTCIssuedDate","NTC_IssuedDate","ntc_issued"]
    }

    STATUS_TO_COL = {
        "chaser1_due": "7",
        "7 day chaser due": "7",
        "chaser1 due": "7",
        "chaser2_due": "14",
        "14 day chaser due": "14",
        "chaser2 due": "14",
        "chaser3_due": "21",
        "21 day chaser due": "21",
        "chaser3 due": "21",
        "ntc_due": "NTC",
        "ntc due": "NTC",
        "ntc - due": "NTC"
    }

    def _coalesce_key(rec, keys):
        for k in keys:
            if k in rec and str(rec.get(k) or "").strip():
                return k
        return None

    def _parse_date_any(s):
        if not s:
            return None
        s = str(s).strip()
        for fmt in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        return None

    # Pull reviews and compute strictly from raw status
    conn2 = sqlite3.connect('scrutinise_workflow.db')
    conn2.row_factory = sqlite3.Row
    cur2 = conn2.cursor()
    try:
        reviews = cur2.execute("SELECT * FROM reviews").fetchall()
    except Exception:
        reviews = []
    finally:
        try: conn2.close()
        except Exception: pass

    today = date.today()

    for rec in reviews:
        rec = dict(rec)
        low_status = (str(rec.get("status") or rec.get("current_status") or "")).strip().lower()
        is_overdue = "overdue" in low_status

        # decide target column from status
        col = None
        for key, mapped in STATUS_TO_COL.items():
            if key in low_status:
                col = mapped
                break

        if not col and not is_overdue:
            # not in chaser cycle nor NTC
            continue

        # choose due-date column(s) to look at
        search_types = ["7","14","21","NTC"] if is_overdue else [col]

        chosen_typ = None
        due_date = None
        for typ in search_types:
            k = _coalesce_key(rec, DUE_MAP.get(typ, []))
            if not k:
                continue
            d = _parse_date_any(rec.get(k))
            if d:
                due_date = d
                chosen_typ = typ
                break

        if not due_date:
            continue

        # respect "not yet issued"
        ik = _coalesce_key(rec, ISSUED_MAP.get(chosen_typ, []))
        if ik and str(rec.get(ik) or "").strip():
            continue

        # only within this working week
        if not (week_days[0] <= due_date <= week_days[-1]):
            continue

        target = "Overdue" if (is_overdue and due_date < today and chosen_typ in ("7","14","21")) else chosen_typ

        # increment the correct row/column
        for row in chaser_week_rows:
            if row["iso"] == due_date.isoformat():
                row[target] += 1
                break

    chaser_headers = chaser_week_headers
    
    chaser_week_rows = chaser_week_rows


    # Escalation rates (global; renamed labels)
    l1_all    = sum(1 for r in reviews_all if r.get("outcome"))
    l1_to_l2  = sum(1 for r in reviews_all if r.get("outcome") == "Potential True Match")
    l2_all    = sum(1 for r in reviews_all if r.get("outcome"))
    l2_to_l3  = sum(1 for r in reviews_all if r.get("outcome") == "Potential True Match")
    safe_div  = lambda n, d: round(n / d * 100, 1) if d else 0.0

    escalation_rates = [
        {"label": "Escalated to Level 2", "from_level": 1, "to_level": 2, "volume": l1_to_l2, "percent": safe_div(l1_to_l2, l1_all)},
        {"label": "Escalated to Level 3", "from_level": 2, "to_level": 3, "volume": l2_to_l3, "percent": safe_div(l2_to_l3, l2_all)},
    ]

    # Forecast (global, simple)
    rem_l1_all         = len(reviews_all) - l1_all
    rate_l1_to_l2      = (l1_to_l2 / l1_all) if l1_all else 0
    add_l2             = round(rem_l1_all * rate_l1_to_l2)
    forecast_total_l2  = l1_to_l2 + add_l2

    rate_l2_to_l3      = (l2_to_l3 / l2_all) if l2_all else 0
    add_l3             = round(add_l2 * rate_l2_to_l3)
    forecast_total_l3  = l2_to_l3 + add_l3

    # ─── 1) Base Population (team filter only) ────────────────────────────
    pop_sql    = """
      SELECT r.*
        FROM reviews r
   LEFT JOIN users u ON u.id = r.l1_assigned_to
       WHERE 1=1
    """
    pop_params = []
    if selected_team != "all":
        pop_sql    += " AND u.team_lead = ?"
        pop_params.append(selected_team)

    cur.execute(pop_sql, pop_params)
    reviews_base = [dict(r) for r in cur.fetchall()]

    # Total Population with level filter (only restrict for 2/3 so L1 shows pending/unassigned)
    reviews_pop = reviews_base.copy()
    if selected_level in ("2", "3"):
        lvl = int(selected_level)
        reviews_pop = [r for r in reviews_pop if r.get(f"l{lvl-1}_outcome") == "Potential True Match"]
    total_screened = len(reviews_pop)

    # ─── 2) Filtered Reviews (team + date + level) ────────────────────────
    data_sql    = pop_sql
    data_params = pop_params.copy()
    if date_range == "wtd":
        data_sql += " AND date(r.updated_at) BETWEEN ? AND ?"
        data_params += [monday_this.isoformat(), today.isoformat()]
    elif date_range == "prevw":
        data_sql += " AND date(r.updated_at) BETWEEN ? AND ?"
        data_params += [monday_prev.isoformat(), sunday_prev.isoformat()]
    elif date_range == "30d":
        data_sql += " AND r.updated_at >= datetime('now','-30 days')"

    cur.execute(data_sql, data_params)
    reviews = [dict(r) for r in cur.fetchall()]

    # Level scoping that preserves Unassigned/Pending at L2/L3
    if selected_level == "2":
        reviews = [r for r in reviews if r.get("outcome") == "Potential True Match"]
    elif selected_level == "3":
        reviews = [r for r in reviews if r.get("outcome") == "Potential True Match"]
    # if "1" or "all": no extra filter

    # Completed this week (WTD)
    from dateutil import parser  # local import is fine

    def _parse_date_any(s):
        if not s:
            return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z","").split(".")[0]).date()
        except Exception:
            try:
                return parser.parse(s).date()
            except Exception:
                return None

    completed_week = 0
    for r in reviews:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        for lvl in (1,2,3):
            d = _parse_date_any(r.get(f"l{lvl}_date_completed"))
            if d and monday_this <= d <= today:
                completed_week += 1
                break

    # Total Completed (respect level filter)
    def _is_completed_review(rec: dict) -> bool:
        s = str(rec.get('status', '')).strip().lower()
        return (s in ('complete', 'completed')) or (str(derive_case_status(rec)) == str(ReviewStatus.COMPLETED))

    total_completed = sum(1 for r in reviews if _is_completed_review(r))

    # ─── QC Pass % & Sample (respect filters) — derive from per-level review fields ──
    def _in_date_range(d: date) -> bool:
        if not d:
            return False
        if date_range == "wtd":
            return monday_this <= d <= today
        if date_range == "prevw":
            return monday_prev <= d <= sunday_prev
        if date_range == "30d":
            return d >= (today - timedelta(days=30))
        return True  # "all"

    # iterate the already-filtered population for MI (team/date filters already applied to `reviews` by updated_at)
    # but we apply QC *date* range specifically against lN_qc_check_date below
    outcome_counts = {}  # normalized label -> count
    qc_sample = 0
    pass_qc = 0

    def _norm_outcome(s: str) -> str:
        if not s:
            return ""
        low = s.strip().lower()
        if low.startswith("pass"):   # counts "pass" and "pass with feedback" as pass
            return "Pass"
        if low == "fail":
            return "Fail"
        return s.strip().title()

    for r in reviews:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        for lv in (1, 2, 3):
            # respect selected level
            if selected_level not in ("all", str(lv)):
                continue
            qc_dt = _parse_date_any(r.get(f"l{lv}_qc_check_date"))
            if not _in_date_range(qc_dt):
                continue
            out = _norm_outcome(r.get(f"l{lv}_qc_outcome") or "")
            if not out:
                continue
            outcome_counts[out] = outcome_counts.get(out, 0) + 1
            qc_sample += 1
            if out == "Pass":
                pass_qc += 1

    qc_pass_pct = round((pass_qc / qc_sample) * 100, 1) if qc_sample else 0

    # (optional) if your template needs a breakdown similar to the old GROUP BY rows:
    qc_rows = [{"outcome": k, "cnt": v} for k, v in sorted(outcome_counts.items(), key=lambda x: x[0])]

    # ─── Planning chart ───────────────────────────────────────────────────
    cur.execute("SELECT * FROM forecast_planning ORDER BY week_index ASC")
    planning      = cur.fetchall()
    plan_labels   = [r["week_label"]     for r in planning]
    plan_forecast = [r["forecast_count"] for r in planning]

    # ---------- Actuals: count terminal completions by week (QC-gated) ----------
    # Rules:
    #  - Level 1 counts only if l1_outcome == "Discount"  AND l1_qc_check_date is set
    #  - Level 2 counts only if l2_outcome == "Discount"  AND l2_qc_check_date is set
    #  - Level 3 counts if  l3_outcome in {"Discount", "True Match"} AND l3_qc_check_date is set
    #  - If multiple levels qualify, count once at the HIGHEST terminal level’s completion date
    # Scope mirrors forecast (global). To respect filters instead, set source_reviews = reviews.
    source_reviews = reviews_all

    # Map week labels (Mondays) to indices; parse label as date if possible
    label_to_idx = {row["week_label"]: i for i, row in enumerate(planning)}
    week_starts  = []
    for row in planning:
        lbl = row["week_label"]
        try:
            d = _parse_date_any(lbl) or parser.parse(str(lbl)).date()
        except Exception:
            d = None
        week_starts.append(d)

    def _monday_of(d):
        return d - timedelta(days=d.weekday())

    monday_to_idx = {}
    for i, d in enumerate(week_starts):
        if d:
            monday_to_idx[d] = i

    TERMINAL_OUTCOMES = {
        1: {"Discount"},
        2: {"Discount"},
        3: {"Discount", "True Match"},
    }


    def terminal_completion_date(rec: dict):
            """Return the completion date for the highest level that is completed.
            Rules (simpler than QC‑gated version):
              - If status starts with "Completed at Level N", use l{N}_date_completed.
              - Else fall back to the highest level that has l{lv}_date_completed set.
            """
            s = (rec.get("status") or "").strip()
            # Prefer explicit status
            if s.startswith("Completed at Level "):
                # extract level digit
                m = re.search(r"(\d+)", s)
                if m:
                    lv = int(m.group(1))
                    d = _parse_date_any(rec.get(f"l{lv}_date_completed"))
                    if d:
                        return d
            # Fallback: highest level with a completion date
            for lv in (3, 2, 1):
                d = _parse_date_any(rec.get(f"l{lv}_date_completed"))
                if d:
                    return d
            return None

    plan_actual = [0 for _ in planning]
    for r in source_reviews:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        d = terminal_completion_date(r)
        if not d:
            continue
        m = _monday_of(d)
        idx = monday_to_idx.get(m)
        if idx is None:
            # Fallback: try matching by parsing labels dynamically
            try:
                for i, row in enumerate(planning):
                    lbl_d = _parse_date_any(row["week_label"]) or parser.parse(str(row["week_label"])).date()
                    if lbl_d == m:
                        idx = i
                        break
            except Exception:
                idx = None
        if idx is not None:
            plan_actual[idx] += 1

    # ---------------------------------------------------------------------

    # helper: treat all "Completed at Level N" as completed
    def _is_completed_status(s: str) -> bool:
        return isinstance(s, str) and s.startswith("Completed at Level ")

    # ─── Distribution + per-status Age heatmap ────────────────────────────
    desired_order = [
        # Level 1
        "Unassigned",
        "Pending Review",
        "IRC - Awaiting Outreach",
        "Referred to SME",
        "Returned from SME",
        "QC – Awaiting Assignment",
        "QC – In Progress",
        "QC – Rework Required",
        "Completed",
        # Level 2
        "Level 2 – Unassigned",
        "Pending Level 2 Review",
        "Referred to SME (Level 2)",
        "Returned from SME (Level 2)",
        "Level 2 QC – Awaiting Assignment",
        "Level 2 QC – In Progress",
        "Level 2 QC – Rework Required",
        "Completed at Level 2",
        # Level 3
        "Level 3 – Unassigned",
        "Pending Level 3 Review",
        "Referred to SME (Level 3)",
        "Returned from SME (Level 3)",
        "Level 3 QC – Awaiting Assignment",
        "Level 3 QC – In Progress",
        "Level 3 QC – Rework Required",
        "Completed at Level 3",
    ]
    ordering = {s: i for i, s in enumerate(desired_order)}

    from collections import Counter, defaultdict

    def last_touched_date(r: dict):
        candidates = [
            _parse_date_any(r.get("updated_at")),
            _parse_date_any(r.get("date_assigned")), _parse_date_any(r.get("date_completed")),
            _parse_date_any(r.get("date_assigned")), _parse_date_any(r.get("date_completed")),
            _parse_date_any(r.get("date_assigned")), _parse_date_any(r.get("date_completed")),
            _parse_date_any(r.get("qc_check_date")), _parse_date_any(r.get("qc_check_date")), _parse_date_any(r.get("qc_check_date")),
            _parse_date_any(r.get("sme_selected_date")), _parse_date_any(r.get("sme_returned_date")),
            _parse_date_any(r.get("sme_selected_date")), _parse_date_any(r.get("sme_returned_date")),
            _parse_date_any(r.get("sme_selected_date")), _parse_date_any(r.get("sme_returned_date")),
        ]
        vals = [d for d in candidates if d]
        return max(vals) if vals else None

    def age_bucket(d):
        if not d:
            return "5 days+"
        days = (today - d).days
        if days <= 2:
            return "1–2 days"
        if days <= 5:
            return "3–5 days"
        return "5 days+"


    # --- Bucketing helper to split 'IRC - Awaiting Outreach' from 'Outreach' safely ---
    def _bucket_case_status(record: dict, status_str: str) -> str:
        s = (status_str or "").strip()
        low = s.lower()
        # explicit IRC - Awaiting Outreach labels
        if "initial review complete - awaiting outreach" in low or "irc - awaiting outreach" in low:
            return "IRC - Awaiting Outreach"

        # Field-based inference: if any first outreach date exists, it's Outreach
        outreach1 = record.get("OutreachDate1") or record.get("outreach_date1") or record.get("Outreach_Date1")
        ch1 = record.get("Chaser1IssuedDate") or record.get("chaser1_issued_date")
        # Treat any explicit 'Outreach' status as Outreach
        if low.startswith("outreach") or outreach1 or ch1:
            return "Outreach"

        # Keep original for everything else
        return s or "(Unclassified)"

    # === Rebuilt: Case Status & Age Profile (RAW DB statuses) ============================
    from collections import Counter, defaultdict
    import re as _re

    # Use the raw DB status exactly; no mapping or derivation
    dist_counter  = Counter()
    age_by_status = defaultdict(lambda: {"1–2 days": 0, "3–5 days": 0, "5 days+": 0})

    # Iterate the same 'reviews' set already filtered for the dashboard
    for r in reviews:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        label = (r.get("status") or "").strip() or "(Blank)"

        _norm = ' '.join(label.lower().split())

        if (

            _norm in ('completed', 'complete', 'case completed', 'task completed', 'review completed')

            or _norm.endswith(' - completed') or _norm.endswith(': completed') or _norm.endswith(' completed')

            or _norm.startswith('completed - ') or _norm.startswith('completed: ')

        ):

            continue

        dist_counter[label] += 1
        age_by_status[label][age_bucket(last_touched_date(r))] += 1

    # Order by count desc then alphabetical
    row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))
    total = sum(dist_counter.values()) or 1

    # Distribution rows
    distribution = [{"status": st, "count": dist_counter[st], "pct": round(dist_counter[st] / total * 100, 1)} for st in row_order]

    # Age profile totals across statuses
    age_profile = {"1–2 days": 0, "3–5 days": 0, "5 days+": 0}
    for _, buckets in age_by_status.items():
        for k, v in buckets.items():
            age_profile[k] += v
    # === End rebuilt block ============================================================


    # ---------- Actuals: (updated) include status containing 'Completed' OR any level completion date; no QC gating ----------
    # Build by-week counts based on a chosen completion timestamp:
    #   prefer l3_date_completed -> l2_date_completed -> l1_date_completed -> (if status has 'Completed') updated_at
    from collections import Counter as _Counter

    def _status_has_completed(rec):
        return 'completed' in str(rec.get('status','')).lower()

    def _completion_date_anylevel(rec):
        for lv in (3, 2, 1):
            d = _parse_date_any(rec.get(f"l{lv}_date_completed"))
            if d:
                return d
        if _status_has_completed(rec):
            d = _parse_date_any(rec.get('updated_at')) or _parse_date_any(rec.get('created_at'))
            if d:
                return d
        return None

    _week_counts = _Counter()
    for r in source_reviews:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        d = _completion_date_anylevel(r)
        if not d:
            continue
        _week_counts[_monday_of(d)] += 1

        # Re-align to planning weeks (by label)
        plan_actual = [0 for _ in planning]
        for i, row in enumerate(planning):
            try:
                lbl_d = _parse_date_any(row["week_label"]) or parser.parse(str(row["week_label"])).date()
            except Exception:
                lbl_d = None
            if lbl_d:
                plan_actual[i] = _week_counts.get(_monday_of(lbl_d), 0)


    # ─── Decision RCA (aggregate once, dedup/normalize) ───────────────────
    import re as _re
    from collections import Counter as _Counter
    from typing import Optional

    def _normalize_rca(raw: str) -> Optional[str]:
        if not raw:
            return None
        s = str(raw).strip()
        if not s:
            return None

        # normalize punctuation/case/spacing
        s = s.replace("–", "-")                    # en dash → hyphen
        s = _re.sub(r"\s*-\s*", " - ", s)         # spacing around hyphens
        s = _re.sub(r"\s+", " ", s).strip()
        low = s.lower()

        # strip common prefixes
        low = _re.sub(r"^(false\s*positive|true\s*match|refer(?:red)?\s*to\s*sme|sme|decision\s*rca)\s*-\s*", "", low)

        # coarse theme collapsing
        if "name" in low and "mismatch" in low:
            low = "name mismatch"
        elif ("dob" in low or "date of birth" in low) and "mismatch" in low:
            low = "date of birth mismatch"
        elif "country" in low and "mismatch" in low:
            low = "country mismatch"
        elif "jurisdiction" in low:
            low = "jurisdictional issue"

        synonyms = {
            "name mis-match": "name mismatch",
            "dob mismatch": "date of birth mismatch",
            "d.o.b mismatch": "date of birth mismatch",
            "jurisdiction issue": "jurisdictional issue",
            "country of residence mismatch": "country mismatch",
            "country code mismatch": "country mismatch",
            "weak match": "weak match",
            "strong match": "strong match",
            "document verified": "document verified",
        }
        low = synonyms.get(low, low)

        canon_map = {
            "name mismatch": "Name mismatch",
            "date of birth mismatch": "Date of Birth mismatch",
            "country mismatch": "Country mismatch",
            "jurisdictional issue": "Jurisdictional issue",
            "weak match": "Weak Match",
            "strong match": "Strong Match",
            "document verified": "Document Verified",
        }
        return canon_map.get(low, low.title())

    # use RCA from most recently completed level
    rca_counter = _Counter()
    for r in reviews:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        completed = []
        for lv in (1, 2, 3):
            d = _parse_date_any(r.get(f"l{lv}_date_completed"))
            if d:
                completed.append((d, lv))
        if not completed:
            continue
        _, last_lv = max(completed)
        raw_rca = (
            r.get(f"l{last_lv}_primary_rationale")
            or r.get("primary_rationale")
            or r.get(f"l{last_lv}_rca")
        )
        canon = _normalize_rca(raw_rca)
        if canon:
            rca_counter[canon] += 1

    total_rca = sum(rca_counter.values()) or 1
    rca_breakdown = [
        {"label": lbl, "count": cnt, "pct": round(cnt / total_rca * 100, 1)}
        for lbl, cnt in sorted(rca_counter.items(), key=lambda x: x[1], reverse=True)
    ]


    # ---- Outcome breakdown (dynamic from reviews.decision_outcome) ----
    from collections import Counter as _Counter
    outcome_counter = _Counter()
    for _rec in reviews:
        if not isinstance(_rec, dict):
            continue
        # Count only completed reviews
        try:
            _completed = _is_completed_review(_rec)
        except Exception:
            _completed = False
        if not _completed:
            continue
        _out = (_rec.get('l1_outcome') or '').strip()
        if _out:
            outcome_counter[_out] += 1
    _tot_out = sum(outcome_counter.values()) or 1
    outcome_breakdown = [
        {"label": lbl, "count": cnt, "pct": round(cnt / _tot_out * 100, 1)}
        for lbl, cnt in sorted(outcome_counter.items(), key=lambda x: x[1], reverse=True)
    ]
    # ---------------------------------------------------------------
    db.close()

    # Dropdowns
    date_ranges = [
        {"label": "All Time",       "value": "all"},
        {"label": "Current Week",   "value": "wtd"},
        {"label": "Previous Week",  "value": "prevw"},
        {"label": "Last 30 Days",   "value": "30d"},
    ]
    levels = ["all", "1", "2", "3"]

    return render_template("404_redirect.html"), 404

# API endpoint for planning (JSON)
@csrf.exempt
@app.route('/api/ops/planning', methods=['GET', 'POST'])
@role_required('operations_manager', 'admin')
def api_planning():
    """Get or update forecast planning data"""
    try:
        import sqlite3
        
        db = get_db()
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        # ─── FIND EARLIEST REVIEW DATE ────────────────────────────────────────
        # Try review_timestamp first, fallback to created_at or date_created
        first_ts = None
        try:
            cur.execute("SELECT MIN(review_timestamp) AS first FROM reviews WHERE review_timestamp IS NOT NULL")
            row = cur.fetchone()
            first_ts = row['first'] if row and row['first'] else None
        except:
            try:
                cur.execute("SELECT MIN(created_at) AS first FROM reviews WHERE created_at IS NOT NULL")
                row = cur.fetchone()
                first_ts = row['first'] if row and row['first'] else None
            except:
                try:
                    cur.execute("SELECT MIN(date_created) AS first FROM reviews WHERE date_created IS NOT NULL")
                    row = cur.fetchone()
                    first_ts = row['first'] if row and row['first'] else None
                except:
                    pass
        
        first_dt = datetime.fromisoformat(first_ts) if first_ts else datetime.utcnow()

        # round down to start of that week (Monday)
        monday = first_dt - timedelta(days=first_dt.weekday())

        # ─── BUILD NEXT 26 WEEKS LIST ────────────────────────────────────────
        weeks = []
        for i in range(26):
            wk_start = monday + timedelta(weeks=i)
            iso_year, iso_week, _ = wk_start.isocalendar()
            week_val = f"{iso_year}-{iso_week:02d}"
            label = wk_start.strftime("%d-%m-%y")
            weeks.append({'value': week_val, 'label': label, 'forecast': 0})

        if request.method == 'POST':
            # ─── RESET & RE-INSERT ALL FORECASTS ───────────────────────────────
            cur.execute("DELETE FROM forecast_planning")
            for idx, w in enumerate(weeks):
                raw = request.form.get(f"forecast_{w['value']}", "").strip()
                cnt = int(raw) if raw else 0
                cur.execute(
                    """
                    INSERT INTO forecast_planning
                      (week_index, week_value, week_label, forecast_count)
                    VALUES (?, ?, ?, ?)
                    """,
                    (idx, w['value'], w['label'], cnt)
                )
            db.commit()
            db.close()
            return jsonify({'success': True, 'message': 'Forecasts updated'})

        # ─── LOAD EXISTING FORECASTS BACK INTO OUR WEEKS LIST ─────────────────
        cur.execute("SELECT week_value, forecast_count FROM forecast_planning")
        existing = {r['week_value']: r['forecast_count'] for r in cur.fetchall()}
        for w in weeks:
            if w['value'] in existing:
                w['forecast'] = existing[w['value']]

        db.close()
        return jsonify({'success': True, 'weeks': weeks})
        
    except Exception as e:
        import traceback
        print(f"Error in api_planning: {str(e)}\n{traceback.format_exc()}")
        if 'db' in locals():
            db.close()
        return jsonify({'error': str(e)}), 500

@app.route('/ops/mi/planning', methods=('GET', 'POST'))
def planning():
    # ─── Security ─────────────────────────────────────────────────────────
    if session.get("role") not in ("operations_manager", "admin"):
        flash("Access restricted", "danger")
        return redirect(url_for("login"))

    db  = get_db()
    cur = db.cursor()

    # ─── FIND EARLIEST REVIEW DATE ────────────────────────────────────────
    # Try review_timestamp first, fallback to created_at or date_created
    first_ts = None
    try:
        cur.execute("SELECT MIN(review_timestamp) AS first FROM reviews WHERE review_timestamp IS NOT NULL")
        row = cur.fetchone()
        first_ts = row['first'] if row and row['first'] else None
    except:
        try:
            cur.execute("SELECT MIN(created_at) AS first FROM reviews WHERE created_at IS NOT NULL")
            row = cur.fetchone()
            first_ts = row['first'] if row and row['first'] else None
        except:
            try:
                cur.execute("SELECT MIN(date_created) AS first FROM reviews WHERE date_created IS NOT NULL")
                row = cur.fetchone()
                first_ts = row['first'] if row and row['first'] else None
            except:
                pass
    
    first_dt = datetime.fromisoformat(first_ts) if first_ts else datetime.utcnow()

    # round down to start of that week (Monday)
    monday = first_dt - timedelta(days=first_dt.weekday())

    # ─── BUILD NEXT 26 WEEKS LIST ────────────────────────────────────────
    weeks = []
    for i in range(26):
        wk_start = monday + timedelta(weeks=i)
        iso_year, iso_week, _ = wk_start.isocalendar()
        week_val = f"{iso_year}-{iso_week:02d}"
        label    = wk_start.strftime("%d-%m-%y")
        weeks.append({'value': week_val, 'label': label, 'forecast': 0})

    if request.method == 'POST':
        # ─── RESET & RE-INSERT ALL FORECASTS ───────────────────────────────
        cur.execute("DELETE FROM forecast_planning")
        for idx, w in enumerate(weeks):
            raw = request.form.get(f"forecast_{w['value']}", "").strip()
            cnt = int(raw) if raw else 0
            cur.execute(
                """
                INSERT INTO forecast_planning
                  (week_index, week_value, week_label, forecast_count)
                VALUES (?, ?, ?, ?)
                """,
                (idx, w['value'], w['label'], cnt)
            )
        db.commit()
        flash("Forecasts updated", "success")
        return redirect(url_for('mi_dashboard'))

    # ─── LOAD EXISTING FORECASTS BACK INTO OUR WEEKS LIST ─────────────────
    cur.execute("SELECT week_value, forecast_count FROM forecast_planning")
    existing = {r['week_value']: r['forecast_count'] for r in cur.fetchall()}
    for w in weeks:
        if w['value'] in existing:
            w['forecast'] = existing[w['value']]

    db.close()
    return render_template("404_redirect.html"), 404

@app.route('/ops/mi/download')
@role_required('operations_manager')
def download_mi_report():
    import io
    from io import BytesIO
    from flask import send_file
    import pandas as pd
    import numpy as np
    from datetime import datetime

    conn = get_db()
    cur  = conn.cursor()

    # ---------- helpers ----------
    EXCEL_CELL_CHAR_LIMIT = 32767
    _FORMULA_PREFIXES = ("=", "+", "-", "@")

    def _is_xml_char(code: int) -> bool:
        return (
            code in (0x09, 0x0A, 0x0D) or
            0x20 <= code <= 0xD7FF or
            0xE000 <= code <= 0xFFFD or
            0x10000 <= code <= 0x10FFFF
        )

    def _strip_xml_illegal(s: str) -> str:
        return "".join(ch for ch in s if _is_xml_char(ord(ch)))

    def _escape_formula(s: str) -> str:
        return "'" + s if s.startswith(_FORMULA_PREFIXES) else s

    def excel_safe_value(v):
        try:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                return None
            # pandas/py datetimes → naive ISO strings
            if isinstance(v, pd.Timestamp):
                py = v.to_pydatetime()
                if py.tzinfo:
                    py = py.replace(tzinfo=None)
                return py.isoformat(sep=" ")
            from datetime import datetime as _dt, date as _date, time as _time
            if isinstance(v, _dt):
                return v.replace(tzinfo=None).isoformat(sep=" ")
            if isinstance(v, (_date, _time)):
                return str(v)
            if isinstance(v, (bytes, bytearray)):
                v = v.decode("utf-8", "replace")
            if isinstance(v, (dict, list, tuple, set)):
                import json
                v = json.dumps(v, ensure_ascii=False, default=str)
            if isinstance(v, (int, float, np.number)):
                if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                    return None
                return v
            s = _strip_xml_illegal(str(v))
            s = _escape_formula(s)
            return s[:EXCEL_CELL_CHAR_LIMIT]
        except Exception:
            s = _strip_xml_illegal(str(v))
            s = _escape_formula(s)
            return s[:EXCEL_CELL_CHAR_LIMIT]

    def excel_safe_df(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # normalize headers
        seen, cols = {}, []
        for c in map(str, df.columns):
            c = _strip_xml_illegal(c)
            if c in seen:
                seen[c] += 1
                c = f"{c}.{seen[c]}"
            else:
                seen[c] = 0
            cols.append(c)
        df.columns = cols
        # replace ±inf → NaN
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        # convert all columns to "object" and sanitize values
        for col in df.columns:
            df[col] = df[col].astype("object").map(excel_safe_value)
        return df

    def safe_sheet_name(raw: str, used: set) -> str:
        import re
        name = re.sub(r'[\[\]\:\*\?\/\\]', '', raw) or "Sheet"
        name = name[:31]
        base = name
        i = 1
        while name in used:
            suffix = f"_{i}"
            name = (base[:(31-len(suffix))] + suffix) if len(base) + len(suffix) > 31 else base + suffix
            i += 1
        used.add(name)
        return name

    # users map for ID→name
    users_df = pd.read_sql_query("SELECT id, name FROM users", conn)
    id_to_name = {int(r.id): r.name for _, r in users_df.iterrows() if pd.notna(r.id)}

    # which columns should be name-mapped in reviews
    NAME_MAP_COLS = [
        "l1_assigned_to","l2_assigned_to","l3_assigned_to",
        "l1_completed_by","l2_completed_by","l3_completed_by",
        "l1_qc_assigned_to","l2_qc_assigned_to","l3_qc_assigned_to",
        "l1_sme_selected","l2_sme_selected","l3_sme_selected"
    ]
    def apply_name_mapping(df: pd.DataFrame) -> pd.DataFrame:
        for c in NAME_MAP_COLS:
            if c in df.columns:
                df[c] = df[c].map(lambda x: id_to_name.get(int(x), x) if pd.notna(x) and str(x).strip() != "" else x)
        return df

    # discover tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]

    output = BytesIO()
    used_sheets = set()

    # Prefer xlsxwriter (cleaner files for Excel), fallback to openpyxl
    try:
        writer_engine = 'xlsxwriter'
        engine_kwargs = {"options": {"strings_to_urls": False}}
        import xlsxwriter  # noqa: F401
    except Exception:
        writer_engine = 'openpyxl'
        engine_kwargs = {}

    with pd.ExcelWriter(output, engine=writer_engine, **engine_kwargs) as writer:
        for tbl in tables:
            if tbl == "reviews":
                q = """
                    SELECT r.*, m.total_score
                      FROM reviews r
                 LEFT JOIN matches m ON m.task_id = r.task_id
                """
                df = pd.read_sql_query(q, conn)
                df = apply_name_mapping(df)

                # Live Status column
                records = df.to_dict(orient="records")
                insert_at = min(5, len(df.columns)) if len(df.columns) else 0
                df.insert(
                    loc=insert_at,
                    column="Live Status",
                    value=[excel_safe_value(derive_case_status(r)) for r in records]
                )
            else:
                df = pd.read_sql_query(f"SELECT * FROM {tbl}", conn)

            df = excel_safe_df(df)
            df.to_excel(writer, sheet_name=safe_sheet_name(tbl, used_sheets), index=False)

        # Info sheet
        meta = pd.DataFrame([{
            'Generated At UTC': datetime.utcnow().isoformat() + 'Z',
            'Tables Exported': ', '.join(tables)
        }])
        meta = excel_safe_df(meta)
        meta.to_excel(writer, sheet_name=safe_sheet_name('Info', used_sheets), index=False)

        # xlsxwriter: ensure workbook closes cleanly
        if writer_engine == 'xlsxwriter':
            writer.book.close()

    output.seek(0)
    filename = f"MI_Report_{datetime.utcnow():%Y%m%dT%H%M%SZ}.xlsx"
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name=filename,
        as_attachment=True
    )

import numpy as np
import datetime as _dt
import json
import re

EXCEL_CELL_CHAR_LIMIT = 32767
_FORMULA_PREFIXES = ("=", "+", "-", "@")

def _is_xml_char(code: int) -> bool:
    # XML 1.0 valid chars: tab(0x09), LF(0x0A), CR(0x0D),
    # 0x20–0xD7FF, 0xE000–0xFFFD, 0x10000–0x10FFFF
    return (
        code in (0x09, 0x0A, 0x0D) or
        0x20 <= code <= 0xD7FF or
        0xE000 <= code <= 0xFFFD or
        0x10000 <= code <= 0x10FFFF
    )

def _strip_xml_illegal(s: str) -> str:
    # Remove any character not allowed by XML 1.0 (covers 0x00–0x08,0x0B,0x0C,0x0E–0x1F, **and 0x7F–0x9F** etc.)
    return "".join(ch for ch in s if _is_xml_char(ord(ch)))

def _escape_formula(s: str) -> str:
    # Prevent Excel from interpreting as a formula
    return "'" + s if s.startswith(_FORMULA_PREFIXES) else s

def excel_safe_value(v):
    """Return a value that openpyxl/Excel will accept without repairs."""
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None

        # datetimes
        if isinstance(v, (pd.Timestamp, _dt.datetime)):
            # drop tz if present & ISO format
            v = (v.tz_localize(None) if isinstance(v, pd.Timestamp) and v.tz is not None else v)
            v = (v.replace(tzinfo=None) if isinstance(v, _dt.datetime) else v)
            return v.isoformat(sep=" ")

        if isinstance(v, (_dt.date, _dt.time)):
            return str(v)

        # byte-ish
        if isinstance(v, (bytes, bytearray)):
            v = v.decode("utf-8", "replace")

        # collections → JSON
        if isinstance(v, (dict, list, tuple, set)):
            v = json.dumps(v, ensure_ascii=False, default=str)

        # numbers: drop infinities which Excel cannot store
        if isinstance(v, (int, float, np.number)):
            if isinstance(v, float) and (np.isinf(v) or np.isnan(v)):
                return None
            return v

        # everything else → string
        s = str(v)
        s = _strip_xml_illegal(s)
        s = _escape_formula(s)
        if len(s) > EXCEL_CELL_CHAR_LIMIT:
            s = s[:EXCEL_CELL_CHAR_LIMIT]
        return s
    except Exception:
        s = _strip_xml_illegal(str(v))
        s = _escape_formula(s)
        return s[:EXCEL_CELL_CHAR_LIMIT]

def excel_safe_df(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure string/unique column names and strip illegal chars there too
    cols = []
    seen = {}
    for c in map(str, df.columns):
        c = _strip_xml_illegal(c)
        if c in seen:
            seen[c] += 1
            c = f"{c}.{seen[c]}"
        else:
            seen[c] = 0
        cols.append(c)
    df = df.copy()
    df.columns = cols

    # Replace ±inf with None
    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Sanitize object-like columns; leave numeric cols numeric
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].map(excel_safe_value)
        elif np.issubdtype(df[col].dtype, np.datetime64):
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # keep numbers but coerce bad values to None
            try:
                df[col] = df[col].where(~df[col].isin([np.inf, -np.inf]), other=np.nan)
            except Exception:
                df[col] = df[col].map(excel_safe_value)
    return df

@app.route("/ops/mi/export_excel")
@role_required("operations_manager", "admin")
def export_excel():
    from io import BytesIO
    from flask import send_file
    import pandas as pd
    import numpy as np
    import datetime as _dt
    from datetime import datetime, timedelta

    # ---------- helpers (same as above, trimmed) ----------
    EXCEL_CELL_CHAR_LIMIT = 32767
    _FORMULA_PREFIXES = ("=", "+", "-", "@")

    def _is_xml_char(code: int) -> bool:
        return (
            code in (0x09, 0x0A, 0x0D) or
            0x20 <= code <= 0xD7FF or
            0xE000 <= code <= 0xFFFD or
            0x10000 <= code <= 0x10FFFF
        )

    def _strip_xml_illegal(s: str) -> str:
        return "".join(ch for ch in s if _is_xml_char(ord(ch)))

    def _escape_formula(s: str) -> str:
        return "'" + s if s.startswith(_FORMULA_PREFIXES) else s

    def excel_safe_value(v):
        try:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                return None
            if isinstance(v, pd.Timestamp):
                py = v.to_pydatetime()
                if py.tzinfo:
                    py = py.replace(tzinfo=None)
                return py.isoformat(sep=" ")
            if isinstance(v, (_dt.datetime,)):
                return v.replace(tzinfo=None).isoformat(sep=" ")
            if isinstance(v, (_dt.date, _dt.time)):
                return str(v)
            if isinstance(v, (bytes, bytearray)):
                v = v.decode("utf-8", "replace")
            if isinstance(v, (dict, list, tuple, set)):
                import json
                v = json.dumps(v, ensure_ascii=False, default=str)
            if isinstance(v, (int, float, np.number)):
                if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                    return None
                return v
            s = _strip_xml_illegal(str(v))
            s = _escape_formula(s)
            return s[:EXCEL_CELL_CHAR_LIMIT]
        except Exception:
            s = _strip_xml_illegal(str(v))
            s = _escape_formula(s)
            return s[:EXCEL_CELL_CHAR_LIMIT]

    def excel_safe_df(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        for col in df.columns:
            df[col] = df[col].astype("object").map(excel_safe_value)
        return df
    # ------------------------------------------------------

    # filters
    date_range    = request.args.get("date_range", "all")
    selected_team = request.args.get("team", "all")
    selected_level= request.args.get("level", "all")

    # week windows
    today = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    conn = get_db()

    # base query (include total_score here)
    query = """
        SELECT r.*, m.total_score, u_tl.team_lead
          FROM reviews r
     LEFT JOIN matches m   ON m.task_id = r.task_id
     LEFT JOIN users   u1  ON u1.id = r.l1_assigned_to
     LEFT JOIN users   u2  ON u2.id = r.l2_assigned_to
     LEFT JOIN users   u3  ON u3.id = r.l3_assigned_to
     LEFT JOIN users   u_tl ON u_tl.id = u1.id  -- used only to filter by TL name when level=1
        WHERE 1=1
    """
    params = []

    # Date filter (on r.updated_at to mirror dashboards)
    if date_range == "wtd":
        query += " AND date(r.updated_at) BETWEEN ? AND ?"
        params += [monday_this.isoformat(), today.isoformat()]
    elif date_range == "prevw":
        query += " AND date(r.updated_at) BETWEEN ? AND ?"
        params += [monday_prev.isoformat(), sunday_prev.isoformat()]
    elif date_range == "30d":
        query += " AND r.updated_at >= datetime('now','-30 days')"

    # Team filter (by team lead name)
    if selected_team != "all":
        query += " AND LOWER(u1.team_lead) = LOWER(?)"
        params.append(selected_team)

    # Level filter (only rows with an outcome at that level)
    if selected_level in ("1","2","3"):
        lvl = int(selected_level)
        query += f" AND r.l{lvl}_outcome IS NOT NULL"

    df = pd.read_sql_query(query, conn, params=params)


    # --- BEGIN FIX: ensure exported Status reflects true status (dashboard logic) ---
    _records_for_status = df.to_dict(orient="records")
    _true_status = [excel_safe_value(derive_case_status(r)) for r in _records_for_status]
    try:
        if "Status" in df.columns:
            df.drop(columns=["Status"], inplace=True)
    except Exception:
        pass
    _status_insert_at = min(5, len(df.columns)) if len(df.columns) else 0
    df.insert(loc=_status_insert_at, column="Status", value=_true_status)
    # --- END FIX ---
    # --- BEGIN FIX: compute Live Status BEFORE any status columns are dropped ---
    _records_for_status = df.to_dict(orient="records")
    _live_status_series = [excel_safe_value(derive_case_status(r)) for r in _records_for_status]
    try:
        if "Live Status" in df.columns:
            df.drop(columns=["Live Status"], inplace=True)
    except Exception:
        pass
    insert_at = min(5, len(df.columns)) if len(df.columns) else 0
    pass  # (neutralised duplicate Live Status insert)
    # --- END FIX ---

    # ID → Name mapping
    users_df = pd.read_sql_query("SELECT id, name FROM users", conn)
    id_to_name = {int(r.id): r.name for _, r in users_df.iterrows() if pd.notna(r.id)}
    def map_name(x):
        try:
            if x is None or str(x).strip()=="":
                return x
            return id_to_name.get(int(x), x)
        except Exception:
            return x

    name_cols = [
        "l1_assigned_to","l2_assigned_to","l3_assigned_to",
        "l1_completed_by","l2_completed_by","l3_completed_by",
        "l1_qc_assigned_to","l2_qc_assigned_to","l3_qc_assigned_to",
        "l1_sme_selected","l2_sme_selected","l3_sme_selected"
    ]
    for c in name_cols:
        if c in df.columns:
            df[c] = df[c].map(map_name)

    # remove any pre-existing status columns
    for c in ["status_DO_NOT_DROP","derived_status","live_status","Live Status"]:
        if c in df.columns:
            try: df.drop(columns=c, inplace=True)
            except: pass

    # Live Status as plain string
    records = df.to_dict(orient="records")
    insert_at = min(5, len(df.columns)) if len(df.columns) else 0
    pass  # (neutralised duplicate Live Status insert)
    df = excel_safe_df(df)

    # write workbook
    out = BytesIO()
    try:
        import xlsxwriter  # prefer this
        with pd.ExcelWriter(out, engine="xlsxwriter", options={"strings_to_urls": False}) as writer:
            df.to_excel(writer, index=False, sheet_name="Reviews")
            writer.book.close()
    except Exception:
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Reviews")
    out.seek(0)

    filename = f"Filtered_MI_{_dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.xlsx"
    return send_file(
        out,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@app.route("/my_tasks", endpoint="my_tasks")
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3')
def my_tasks():
    # Check if Due Diligence module is enabled
    if not is_module_enabled('due_diligence'):
        flash('Due Diligence module is currently disabled. Only dashboards are available.', 'warning')
        return redirect(url_for('reviewer_dashboard'))
    """
    Reviewer "My Tasks" table with drill-through from dashboard tiles.
    Accepts filters from reviewer_dashboard links and from the my_tasks.html form.
    """
    _outcome = (request.args.get('outcome') or request.args.get('decision_outcome') or '').strip()
    outcome_filter = (lambda ro: (not _outcome) or (str(ro or '').strip().lower() == _outcome.lower()))


    import sqlite3
    from datetime import datetime, timedelta, date
    from collections import defaultdict

    user_id = session.get("user_id")
    role    = session.get("role", "reviewer_1")
    if not user_id:
        return redirect(url_for('login'))
    try:
        level = int(role.split("_", 1)[1])
    except Exception:
        level = 1

    # Query params
    raw_status   = (request.args.get("status") or "").strip()
    status_key   = raw_status.lower()
    filter_status_dropdown = raw_status  # preserve original for template selection
    age_bucket_q = (request.args.get("age_bucket") or request.args.get("rework_bucket") or "").strip()
    date_range   = request.args.get("date_range", "all")
    chaser_type  = (request.args.get("chaser_type") or "").strip()   # '7','14','21','28','NTC'
    week_date    = (request.args.get("week_date") or "").strip()     # 'YYYY-MM-DD'
    overdue_flg  = (request.args.get("overdue") or "").strip()       # '1' if overdue bucket
    # Legacy drill-through (still supported)
    chaser_label = (request.args.get("chaser_label") or "").strip()
    chaser_due   = (request.args.get("chaser_due") or "").strip()

    # Date helpers
    today       = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    def _parse_iso(s):
        if not s: return None
        try:
            return datetime.fromisoformat(str(s).replace('Z','').split('.')[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(str(s))
            except Exception:
                return None

    def _in_range(d: datetime):
        if not d: return True if date_range == 'all' else False
        dd = d.date() if isinstance(d, datetime) else d
        if date_range == 'wtd':   return dd >= monday_this
        if date_range == 'prevw': return monday_prev <= dd <= sunday_prev
        if date_range == '30d':   return dd >= (today - timedelta(days=30))
        return True  # 'all'

    def _bucket_from_dt(d: datetime):
        if not d: return '5 days+'
        days = (today - d.date()).days
        if days <= 2: return '1–2 days'
        if days <= 5: return '3–5 days'
        return '5 days+'

    # Columns
    assign_col   = "assigned_to"
    completed_by = "completed_by"
    completed_dt = "date_completed"
    qc_checked   = "qc_check_date"
    qc_rework    = "qc_rework_required"
    qc_done      = "qc_rework_completed"

    # Fetch all reviews for this reviewer (assigned-to OR completed-by)
    db = get_db()
    cur = db.cursor()
    cur.execute(f"""
        SELECT *
          FROM reviews
         WHERE {assign_col} = ? OR {completed_by} = ?
         ORDER BY updated_at DESC
    """, (user_id, user_id))
    all_rows = [dict(r) for r in cur.fetchall()]

    # Build normalized task objects for template
    tasks = []
    for r in all_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        status_text = (derive_case_status(r) or "").strip()
        last_touch  = _parse_iso(r.get('updated_at')) or _parse_iso(r.get('created_at'))

        t = {
            'task_id':     r.get('task_id') or r.get('id'),
            'hit_type':    r.get('hit_type') or r.get('type') or '',
            'total_score': r.get('total_score') or r.get('score') or '',
            'status':      status_text,
            'updated_at':  last_touch,
            '_row':        r,  # keep original for filtering
        }
        tasks.append(t)

    # === Apply filters ===
    me = int(user_id)

    # Map short dashboard keys to status predicates
    def match_status(t):
        s = (t['status'] or '').lower()
        r = t['_row']
        assignee = r.get(assign_col)
        finisher = r.get(completed_by)
        is_assigned_to_me = (assignee == me) if assignee is not None else False
        is_completed_by_me = (finisher == me) if finisher is not None else False

        if not status_key:
            # If user landed via navbar with no filters, default to items currently assigned to them
            return is_assigned_to_me

        if status_key in ('wip','in progress'):
            return is_assigned_to_me and ('completed' not in s)
        if status_key in ('completed',):
            return is_completed_by_me and ('completed' in s) and ('referred to sme' not in s)
        if status_key in ('qc_checked','qc','qc-checked'):
            return is_completed_by_me and bool(r.get(qc_checked))
        if status_key in ('pending','pending review'):
            return is_assigned_to_me and (('pending review' in s) or (f'pending level {level} review' in s))
        if status_key in ('rework','rework required'):
            return is_assigned_to_me and bool(r.get(qc_rework)) and not bool(r.get(qc_done))
        if status_key in ('referred to sme','sme_ref','sme-ref'):
            # Include both "Referred to SME" and "Referred to AI SME"
            return is_assigned_to_me and ('referred to sme' in s or 'referred to ai sme' in s)
        if status_key in ('returned from sme','sme_ret','sme-ret'):
            return is_assigned_to_me and ('returned from sme' in s)

        if status_key in ('awaiting outreach','awaiting_outreach','awaiting-outreach',
                          'initial review complete - awaiting outreach',
                          'initial review complete awaiting outreach',
                          'initial review complete'):
            # show items marked as 'awaiting outreach' for the current reviewer
            return is_assigned_to_me and ('awaiting outreach' in s)
        if status_key in ('outreach',):
            return is_assigned_to_me and ('outreach' in s) and ('awaiting outreach' not in s)
        return True

    filtered = [t for t in tasks if match_status(t)]

    # Age/rework bucket
    if age_bucket_q:
        def _match_bucket(t):
            b = _bucket_from_dt(t['updated_at'])
            return b == age_bucket_q
        filtered = [t for t in filtered if _match_bucket(t)]

    # Date range (based on last updated or completion date)
    if date_range and date_range != 'all':
        filtered = [t for t in filtered if _in_range(t['updated_at'])]

    # Chaser drill-through (support both new and legacy params in a permissive way)
    if overdue_flg == '1' or chaser_type or (chaser_label and chaser_due):
        # For now, constrain to tasks whose status mentions outreach/chaser/ntc when any chaser param provided
        def _is_chaserish(t):
            s = (t['status'] or '').lower()
            return any(x in s for x in ('outreach','chaser','ntc','notice to close','awaiting outreach','cycle'))
        filtered = [t for t in filtered if _is_chaserish(t)]
        # If week_date provided, keep those touched in same ISO week as week_date (best-effort)
        try:
            if week_date:
                wd = datetime.fromisoformat(week_date).date()
                ww = wd.isocalendar()[:2]
                def _same_week(d):
                    if not d: return False
                    return (d.date().isocalendar()[:2] == ww)
                filtered = [t for t in filtered if _same_week(t['updated_at'])]
        except Exception:
            pass

    # Prepare vars for template (dropdown expects 'filter_status' and 'tasks')
    return render_template("404_redirect.html"), 404

def sme_dashboard():
    if session.get('role') != 'sme':
        return "Access denied", 403

    date_range = request.args.get("date_range", "wtd")
    today = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    def _parse_dt(s):
        if not s:
            return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "").split(".")[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(s)
            except Exception:
                return None

    def _in_range(dt: datetime) -> bool:
        if not dt:
            return False
        d = dt.date()
        if date_range == "wtd": return monday_this <= d <= today
        if date_range == "prevw": return monday_prev <= d <= sunday_prev
        if date_range == "30d": return d >= (today - timedelta(days=30))
        return True

    def _bucket(dt: datetime) -> str:
        if not dt:
            return "5 days+"
        days = (today - dt.date()).days
        if days <= 2: return "1–2 days"
        if days <= 5: return "3–5 days"
        return "5 days+"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT *
        FROM reviews
        WHERE l1_referred_to_sme IS NOT NULL
           OR l2_referred_to_sme IS NOT NULL
           OR l3_referred_to_sme IS NOT NULL
        ORDER BY updated_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    open_queue = 0
    new_referrals = set()
    returned = set()
    tat_days = []
    from collections import defaultdict, Counter
    returns_per_day = defaultdict(int)
    stage_counts = Counter()
    stage_age = {
        "Awaiting SME Assignment": {"1–2 days": 0, "3–5 days": 0, "5 days+": 0},
        "In SME Review": {"1–2 days": 0, "3–5 days": 0, "5 days+": 0},
        "Returned from SME": {"1–2 days": 0, "3–5 days": 0, "5 days+": 0},
    }

    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        task_id = r.get("task_id")
        per_level = []
        for lv in (1, 2, 3):
            sel = _parse_dt(r.get(f"l{lv}_sme_selected_date"))
            ret = _parse_dt(r.get(f"l{lv}_sme_returned_date"))
            ass = r.get(f"l{lv}_sme_selected")  # updated to match schema
            per_level.append((lv, sel, ret, ass))

        if any(sel and _in_range(sel) for _, sel, _, _ in per_level):
            new_referrals.add(task_id)

        rets = [(lv, ret, sel) for lv, sel, ret, _ in ((lv, sel, ret, ass) for lv, sel, ret, ass in per_level) if ret]
        if rets:
            rets.sort(key=lambda x: x[1], reverse=True)
            _, ret_dt, sel_dt_for_ret = rets[0]
            if _in_range(ret_dt):
                returned.add(task_id)
                if sel_dt_for_ret:
                    tat_days.append((ret_dt - sel_dt_for_ret).days)
                returns_per_day[ret_dt.date()] += 1

        open_lv, open_sel, open_ass = None, None, None
        for lv, sel, ret, ass in per_level:
            if sel and not ret:
                if (not open_sel) or (sel > open_sel):
                    open_lv, open_sel, open_ass = lv, sel, ass
        if open_lv is not None:
            open_queue += 1
            status_label = "In SME Review" if open_ass else "Awaiting SME Assignment"
            stage_counts[status_label] += 1
            stage_age[status_label][_bucket(open_sel)] += 1
        else:
            if rets:
                _, ret_dt, _ = rets[0]
                stage_counts["Returned from SME"] += 1
                stage_age["Returned from SME"][_bucket(ret_dt)] += 1

    total_new_referrals = len(new_referrals)
    total_returned = len(returned)
    avg_tat = round(sum(tat_days) / len(tat_days), 1) if tat_days else 0.0

    if date_range == "wtd":
        start_day, end_day = monday_this, today
    elif date_range == "prevw":
        start_day, end_day = monday_prev, sunday_prev
    elif date_range == "30d":
        start_day, end_day = today - timedelta(days=29), today
    else:
        start_day, end_day = today - timedelta(days=59), today

    daily_labels, daily_counts = [], []
    cur_day = start_day
    while cur_day <= end_day:
        daily_labels.append(cur_day.strftime("%d %b"))
        daily_counts.append(returns_per_day.get(cur_day, 0))
        cur_day += timedelta(days=1)

    matrix_order = ["Awaiting SME Assignment", "In SME Review", "Returned from SME"]
    total_matrix = sum(stage_counts.values()) or 1
    sme_matrix = [{
        "status": st,
        "count": stage_counts.get(st, 0),
        "pct": round(stage_counts.get(st, 0) / total_matrix * 100, 1),
        "a12": stage_age[st]["1–2 days"],
        "a35": stage_age[st]["3–5 days"],
        "a5p": stage_age[st]["5 days+"],
    } for st in matrix_order]

    matrix_totals = {
        "count": sum(r["count"] for r in sme_matrix),
        "a12": sum(r["a12"] for r in sme_matrix),
        "a35": sum(r["a35"] for r in sme_matrix),
        "a5p": sum(r["a5p"] for r in sme_matrix),
    }

    return render_template("404_redirect.html"), 404

@app.route("/review/<task_id>", methods=["GET", "POST"], endpoint="review")
def view_task(task_id):
    import sqlite3
    from datetime import datetime

    # Always available in utils.py
    try:
        from utils import derive_case_status, derive_status
    except Exception:
        from utils import derive_case_status
        def derive_status(rec, default_level=None):
            # Fallback: use derive_case_status if derive_status isn't available
            return derive_case_status(rec)

    # Initialize default redirect target
    redirect_to = request.referrer or url_for('review', task_id=task_id)

    # --- Soft import for optional helpers; provide local fallbacks if missing ---
    try:
        from utils import compute_sme_panel  # may not exist in some deployments
    except Exception:
        def compute_sme_panel(review: dict, default_level: int = 1):
            """Fallback: build SME panel info from columns already in `reviews`."""
            lvl = default_level or 1
            q   = review.get(f"l{lvl}_sme_query")
            adv = review.get(f"l{lvl}_sme_response")
            sel = review.get(f"l{lvl}_sme_selected_date")
            ret = review.get(f"l{lvl}_sme_returned_date")
            return {
                "level":     lvl,
                "query":     q,
                "advice":    adv,
                "selected":  sel,
                "returned":  ret,
                "has_any":   bool(q or adv or sel or ret),
                # this column may or may not exist; harmless if None
                "sme_user_id": review.get(f"l{lvl}_sme_assigned_to"),
            }

    try:
        from utils import get_rca_options  # may not exist
    except Exception:
        def get_rca_options():
            # Safe default list to keep the UI working
            return [
                "Name mismatch",
                "Date of birth mismatch",
                "Nationality mismatch",
                "Address mismatch",
                "Document mismatch",
                "Insufficient evidence",
                "Other",
            ]

    # -------------------------------------------------------------------------
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    role          = session.get("role", "")
    session_level = session.get("level")
    user_id       = session.get("user_id")
    sme_mode      = (role == "sme") or (request.args.get("sme") == "1")

    # ---- Load review + match -------------------------------------------------
    cursor.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Review task not found", 404
    review = dict(row)

    cursor.execute("SELECT * FROM matches WHERE task_id = ?", (task_id,))
    match = cursor.fetchone()
    match = dict(match) if match else {}
    review.update(match)

    # ---- What columns exist (for safe updates) -------------------------------
    cursor.execute("PRAGMA table_info(reviews)")
    review_cols = {r["name"] for r in cursor.fetchall()}

    def put(update_dict, key, value):
        """Safely add a column update if it exists; includes smart fallbacks."""
        # Direct match
        if key in review_cols:
            update_dict[key] = value
            return
        import re as _re
        # Level-stripped fallback: l1_outcome -> outcome, etc.
        m = _re.match(r"l[123]_(.+)", key)
        if m:
            base = m.group(1)
            if base in review_cols:
                update_dict[base] = value
                return
        # Strip common prefixes and retry
        for pref in ("cd_", "ddg_", "outreach_", "concern_"):
            if key.startswith(pref):
                base = key[len(pref):]
                if base in review_cols:
                    update_dict[base] = value
                    return
        # enrichment -> enriched
        if key.endswith("_enrichment") and key[:-11] + "_enriched" in review_cols:
            update_dict[key[:-11] + "_enriched"] = value
            return
        # *_ok -> *_section_completed
        if key.endswith("_ok"):
            base = key[:-3]
            cand = base + "_section_completed"
            if cand in review_cols:
                update_dict[cand] = value
                return
        # concern dates: sar_date / daml_date -> *_date_raised
        if key in ("sar_date", "daml_date") and key + "_raised" in review_cols:
            update_dict[key + "_raised"] = value
            return
        # Outreach aliases
        outreach_alias = {
            "date1": "OutreachDate1",
            "outreachdate1": "OutreachDate1",
            "OutreachDate1": "OutreachDate1",
            "chaser1_issued": "Chaser1IssuedDate",
            "chaser2_issued": "Chaser2IssuedDate",
            "chaser3_issued": "Chaser3IssuedDate",
            "ntc_issued": "NTCIssuedDate",
            "outreach_response_date": "outreach_response_received_date",
            "response_date": "outreach_response_received_date",
        }
        if key in outreach_alias and outreach_alias[key] in review_cols:
            update_dict[outreach_alias[key]] = value
            return

    # ---- Which level should be open? ----------------------------------------
    def best_open_level(r: dict) -> int:
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"): return 2
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"): return 3
        for lv in (3, 2, 1):
            if r.get(f"l{lv}_assigned_to") or r.get(f"l{lv}_outcome"):
                return lv
        return 1

    q_level    = request.args.get("open_level", type=int)
    role_level = int(role.split("_", 1)[1]) if role.startswith("reviewer_") else None
    level      = q_level or role_level or (int(session_level) if session_level else None) or best_open_level(review)
    if level not in (1, 2, 3):
        level = 1

    # ---- Helper flags for QC rework state (used both in POST and GET) -------
    rework_required_col   = "qc_rework_required"
    rework_completed_col  = "qc_rework_completed"
    sme_returned_col      = "sme_returned_date"
    outcome_col           = "outcome"

    rework_required  = bool(review.get(rework_required_col))
    rework_completed = bool(review.get(rework_completed_col))
    sme_returned     = review.get(sme_returned_col)
    has_outcome      = review.get(outcome_col)

    
    # ---- Outreach due-date backfill (idempotent) ----------------------------
    try:
        d1_raw = review.get('OutreachDate1') or review.get('outreach_date1') or review.get('Outreach_Date1')
        c1d = review.get('Chaser1DueDate')
        c2d = review.get('Chaser2DueDate')
        c3d = review.get('Chaser3DueDate')
        ntd = review.get('NTCDueDate') or review.get('NTC_DueDate') or review.get('NTCDue')
        if d1_raw and (not c1d or not c2d or not c3d or not ntd):
            d1 = _parse_date(d1_raw)
            if d1:
                updates = {}
                if not c1d: updates['Chaser1DueDate'] = (d1 + timedelta(days=7)).isoformat()
                if not c2d: updates['Chaser2DueDate'] = (d1 + timedelta(days=14)).isoformat()
                if not c3d: updates['Chaser3DueDate'] = (d1 + timedelta(days=21)).isoformat()
                if not ntd: updates['NTCDueDate']     = (d1 + timedelta(days=28)).isoformat()
                if updates:
                    try:
                        _update_review(task_id, updates)
                        # Reflect immediately in the current render
                        review.update(updates)
                    except Exception as _e: 
                        current_app.logger.warning(f'Backfill outreach due dates failed for {task_id}: %s', _e)
    except Exception as _e:
        current_app.logger.debug('Outreach backfill guard: %s', _e)
# ---- POST handling -------------------------------------------------------
    if request.method == "POST" and not sme_mode:
        # Check if task is in SME referral status - block all status changes
        is_locked, error_msg = is_task_in_sme_referral_status(task_id, conn)
        if is_locked:
            conn.close()
            flash(error_msg, "error")
            return redirect(url_for('review', task_id=task_id))
        
        action = (request.form.get("action") or "").strip()
        now    = datetime.utcnow().isoformat(timespec="seconds")

        update_fields = {}
        put(update_fields, "updated_at", now)
        # Minimal: persist InitialReviewCompleteDate if posted (no other fields)
        if "InitialReviewCompleteDate" in request.form and "InitialReviewCompleteDate" in review_cols:
            _ircd = (request.form.get("InitialReviewCompleteDate") or "").strip()
            put(update_fields, "InitialReviewCompleteDate", _ircd if _ircd else None)


        assigned_field = "assigned_to"
        if user_id and not review.get(assigned_field) and assigned_field in review_cols:
            update_fields[assigned_field] = user_id
        # === New actions: outreach + save progress (non-blocking) ===
        if request.method == "POST" and action == "save_outreach_date1":
            outreach_date1 = (request.form.get("outreach_date1") or "").strip()
            if outreach_date1:
                # Always write to OutreachDate1
                put(update_fields, "OutreachDate1", outreach_date1)
                # Compute due dates immediately so they appear on the next render
                try:
                    d1 = _dt_any(outreach_date1)
                except Exception:
                    d1 = None
                if d1:
                    from datetime import timedelta as _td
                    put(update_fields, "Chaser1DueDate", (d1 + _td(days=7)).date().isoformat())
                    put(update_fields, "Chaser2DueDate", (d1 + _td(days=14)).date().isoformat())
                    put(update_fields, "Chaser3DueDate", (d1 + _td(days=21)).date().isoformat())
                    put(update_fields, "NTCDueDate",     (d1 + _td(days=28)).date().isoformat())
        if request.method == "POST" and action == "save_outreach_date1":
            # Coalesce to whichever outreach/NTC due column exists
            outreach_date1 = (request.form.get("outreach_date1") or "").strip()
            if outreach_date1:
                # choose first matching column from preferred list
                candidates = ["OutreachDate1", "outreach_date1", "Outreach_Date1", "NTC_DueDate", "NTC_Due", "NTCDue", "Chaser1DueDate"]
                for col in candidates:
                    if col in review_cols:
                        put(update_fields, col, outreach_date1)
                        break
                put(update_fields, "updated_at", now)
            redirect_to = request.url + ('&' if '?' in request.url else '?') + 'saved=1'

        if request.method == "POST" and action == "save_outreach_chasers":
                # Outreach Response Received Date -> reviews.outreach_response_received_date
                _resp_date = (
                    request.form.get('Outreach_response_received_date')
                    or request.form.get('outreach_response_date')
                    or ''
                ).strip()
                if _resp_date and 'outreach_response_received_date' in review_cols:
                    put(update_fields, 'outreach_response_received_date', _resp_date)

                # --- Guard: enforce sequential chaser issuing ---
                cur_c1 = review.get('Chaser1IssuedDate') or review.get('Chaser1Issued') or review.get('Chaser1DateIssued')
                cur_c2 = review.get('Chaser2IssuedDate') or review.get('Chaser2Issued') or review.get('Chaser2DateIssued')
                cur_c3 = review.get('Chaser3IssuedDate') or review.get('Chaser3Issued') or review.get('Chaser3DateIssued')

                form_c1 = (request.form.get('chaser1_issued') or '').strip()
                form_c2 = (request.form.get('chaser2_issued') or '').strip()
                form_c3 = (request.form.get('chaser3_issued') or '').strip()
                form_ntc = (request.form.get('ntc_issued') or '').strip()

                def _has(v):
                    return bool(v and v not in ['—','N/A','None','NA','0/0/0000','0000-00-00'])

                # Rule: cannot set C2 unless C1 exists (in DB or this form)
                if _has(form_c2) and not (_has(form_c1) or _has(cur_c1)):
                    flash("Please issue Chaser 1 before Chaser 2.", "warning")
                    return redirect(request.url)
                # Rule: cannot set C3 unless C2 exists
                if _has(form_c3) and not (_has(form_c2) or _has(cur_c2)):
                    flash("Please issue Chaser 2 before Chaser 3.", "warning")
                    return redirect(request.url)
                # Rule: cannot set NTC unless C3 exists
                if _has(form_ntc) and not (_has(form_c3) or _has(cur_c3)):
                    flash("Please issue Chaser 3 before NTC.", "warning")
                    return redirect(request.url)

                # Accept any of these if present in schema; update only provided values
                mapping = {
                    "ntc_issued":      ["NTCIssuedDate","NTC_IssuedDate","NTCIssued"],
                    "chaser1_issued":  ["Chaser1IssuedDate","Chaser1DateIssued","Chaser1Issued"],
                    "chaser2_issued":  ["Chaser2IssuedDate","Chaser2DateIssued","Chaser2Issued"],
                    "chaser3_issued":  ["Chaser3IssuedDate","Chaser3DateIssued","Chaser3Issued"],
                }
                for form_key, candidates in mapping.items():
                    val = (request.form.get(form_key) or "").strip()
                    if not val:
                        continue
                    for col in candidates:
                        if col in review_cols:
                            put(update_fields, col, val)
                            break

                put(update_fields, "updated_at", now)
                redirect_to = request.url + ('&' if '?' in request.url else '?') + 'saved=1'

        if request.method == "POST" and action == "save_progress":
            # Save partial decision without enforcing required fields or setting complete date
            outcome           = (request.form.get("outcome") or "").strip() or None
            rationale         = (request.form.get("rationale") or "").strip() or None
            primary_rationale = (request.form.get("primary_rationale") or "").strip() or None
            if outcome is not None:           put(update_fields, "outcome", outcome)
            if rationale is not None:         put(update_fields, "rationale", rationale)
            if primary_rationale is not None: put(update_fields, "primary_rationale", primary_rationale)
            put(update_fields, "review_end_time", now)
            redirect_to = request.url + ('&' if '?' in request.url else '?') + 'saved=1' + ('&' if '?' in request.url else '?') + 'saved=1'

    # === Begin universal partial save (guarded) ===
        if request.method == "POST" and not sme_mode:
            try:
                import re as _re

                # Build schema set for quick membership tests
                review_cols_set = set(review_cols) if isinstance(review_cols, (list, tuple, set)) else set(review_cols or [])

                def _truthy(v):
                    if v is None: return None
                    s = str(v).strip()
                    if s == "": return ""
                    if s in ("1","0"): return s
                    if s.lower() in ("true","yes","on","y","t"): return "1"
                    if s.lower() in ("false","no","off","n","f"): return "0"
                    return s

                def _norm_key(k: str) -> str:
                    k2 = k.strip()
                    if k2 == "Outreach_response_received_date":
                        return "outreach_response_received_date"
                    if k2.startswith("cd_"):
                        k2 = k2[3:]
                    # Strip ddg_ prefix used by DDG fields
                    if k2.startswith("ddg_"):
                        k2 = k2[4:]
                    # Normalize legacy/variant section-complete keys to *_section_completed
                    if k2.endswith("_section_complete"):
                        k2 = k2[:-len("_section_complete")] + "_section_completed"
                    elif k2.endswith("_ok"):
                        k2 = k2[:-len("_ok")] + "_section_completed"
                    # Outreach required already matches DB as *_outreach_required
                    k2 = _re.sub(r"\s+", "_", k2)
                    return k2

                mapped = {}
                for k in request.form.keys():
                    if k in ("action","csrf_token"):
                        continue
                    v = request.form.get(k)
                    nk = _norm_key(k)
                    vv = _truthy(v)
                    # Let put() handle aliasing; include all normalized keys
                    mapped[nk] = vv

                # Level-aware decision fields (if present)
                outcome           = (request.form.get("outcome") or "").strip()
                rationale         = (request.form.get("rationale") or "").strip()
                primary_rationale = (request.form.get("primary_rationale") or "").strip()
                case_summary      = (request.form.get("case_summary") or "").strip()
                fincrime_reason = (request.form.get("financial_crime_reason") or request.form.get("fincrime_reason") or "").strip()
                if outcome:
                    put(update_fields, "outcome", outcome)
                if rationale:
                    put(update_fields, "rationale", rationale)
                if primary_rationale:
                    put(update_fields, "primary_rationale", primary_rationale)
                if case_summary and "case_summary" in review_cols_set:
                    put(update_fields, "case_summary", case_summary)
                if fincrime_reason:
                    if "financial_crime_reason" in review_cols_set:
                        put(update_fields, "financial_crime_reason", fincrime_reason)
                    elif "fincrime_reason" in review_cols_set:
                        put(update_fields, "fincrime_reason", fincrime_reason)

                for col, val in mapped.items():
                    if val is None:
                        continue
                    put(update_fields, col, str(val))

                put(update_fields, "updated_at", now)
            except Exception as _e:
                app.logger.warning("Universal save_progress mapping failed: %s", _e)
# === End universal partial save ===
# === End universal partial save ===



        # === Existing branches ===


        if request.method == "POST" and action == "refer_sme":
            sme_query = (request.form.get("sme_query") or "").strip()
            if not sme_query:
                flash("Please include your SME query/context.", "warning")
                conn.close()
                return redirect(request.url)

            put(update_fields, "referred_to_sme", 1)
            put(update_fields, "sme_selected_date", now)
            put(update_fields, "sme_query", sme_query)
            put(update_fields, "sme_response", None)
            put(update_fields, "sme_returned_date", None)

        elif action != "save_progress":
            # Standard reviewer submit (also used during rework)
            outcome           = (request.form.get("outcome") or "").strip()
            rationale         = (request.form.get("rationale") or "").strip()
            primary_rationale = (request.form.get("primary_rationale") or "").strip()
            # (validation removed for submit; allow empty rationale / RCA)

            # Check if task was already completed
            was_completed = bool(review.get("date_completed"))
            
            put(update_fields, "outcome",           outcome)
            put(update_fields, "rationale",         rationale)
            put(update_fields, "primary_rationale", primary_rationale)
            # Only mark complete when Outcome, Rationale, and Case Summary are present
            _case_summary_present = bool((request.form.get("case_summary") or review.get("case_summary") or "").strip())
            if outcome and rationale and _case_summary_present:
                # If not already completed, mark as completed
                if not was_completed:
                    put(update_fields, "date_completed",  now)
                    put(update_fields, "completed_by",    user_id)
                # If already completed, keep the original completion date (don't overwrite)
                # This ensures that if task was completed before SME response, it stays completed
            put(update_fields, "review_end_time",   now)
            
            # After updating, check if task should be sent to QC
            # This will be handled by status derivation, but we can also check here
            # if the task is in QC sampling and update status accordingly
            
            # If task is in rework and being resubmitted, clear rework flags
            # This allows the cycle to continue
            status_lower = str(review.get("status", "")).lower()
            if was_completed and (review.get("qc_rework_required") or "rework" in status_lower):
                # Task was completed but sent back for rework
                # Clear rework flags when reviewer resubmits (allows new QC cycle)
                put(update_fields, "qc_rework_required", 0)
                put(update_fields, "qc_rework_completed", 1)  # Mark rework as completed by reviewer
                # Clear qc_check_date so task goes back to QC for fresh review (not marked as Completed)
                put(update_fields, "qc_check_date", None)
                # Clear qc_end_time so task shows up in QC's Active WIP again
                put(update_fields, "qc_end_time", None)
                # IMPORTANT: Do NOT clear qc_assigned_to - keep it assigned to the same QC reviewer
                # so the task shows up in their dashboard
                # IMPORTANT: Do NOT clear qc_outcome - keep it for MI/reporting purposes
                # Keep date_completed so status derivation knows it was completed before
                # Don't clear date_completed - it should remain to track original completion

        if update_fields:
            set_sql = ", ".join(f"{k} = ?" for k in update_fields)
            values  = list(update_fields.values()) + [task_id]
            cursor.execute(f"UPDATE reviews SET {set_sql} WHERE task_id = ?", values)

            cursor.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
            rev = dict(cursor.fetchone())
            
            # Check if task is in QC sampling for status derivation
            cursor.execute("SELECT 1 FROM qc_sampling_log WHERE task_id = ?", (task_id,))
            in_qc_sampling = cursor.fetchone() is not None
            rev["_in_qc_sampling"] = in_qc_sampling
            
            new_status = derive_case_status(rev)
            cursor.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))
            conn.commit()

        conn.close()
        flash("Update saved.", "success")
        return redirect(redirect_to)
        redirect_to = url_for('reviewer_dashboard')

    # ---- Ensure review start time -------------------------------------------
    start_col = "review_start_time"
    if start_col in review_cols:
        cursor.execute(f"""
            UPDATE reviews SET {start_col} = ?
            WHERE task_id = ? AND ({start_col} IS NULL OR {start_col} = '')
        """, (datetime.utcnow().isoformat(timespec="seconds"), task_id))
        conn.commit()

    # ---- Status & names ------------------------------------------------------
    status = derive_status(review, level)

    id_set = set()
    for lv in (1, 2, 3):
        for suffix in ("assigned_to", "completed_by", "qc_assigned_to", "sme_assigned_to"):
            uid = review.get(f"l{lv}_{suffix}")
            if uid:
                id_set.add(uid)
    name_map = {}
    if id_set:
        qmarks = ",".join("?" * len(id_set))
        cursor.execute(f"SELECT id, name FROM users WHERE id IN ({qmarks})", list(id_set))
        name_map = {r["id"]: r["name"] for r in cursor.fetchall()}

    def _dt_any(s):
        if not s: return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z","").split(".")[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(s)
            except Exception:
                return None

    def _fmt_date(s):
        d = _dt_any(s)
        return d.strftime("%d-%m-%Y") if d else None

    assignments_summary = []
    for lv in (1, 2, 3):
        assignments_summary.append({
            "level": lv,
            "review": {
                "completed_by_name": name_map.get(review.get(f"l{lv}_completed_by")),
                "completed_on":      _fmt_date(review.get(f"l{lv}_date_completed")),
            },
            "qc": {
                "assigned_to_name":  name_map.get(review.get(f"l{lv}_qc_assigned_to")),
                "checked_on":        _fmt_date(review.get(f"l{lv}_qc_check_date")),
            },
            "sme": {
                "assigned_to_name":  name_map.get(review.get(f"l{lv}_sme_assigned_to")),
                "returned_on":       _fmt_date(review.get(f"l{lv}_sme_returned_date")),
            }
        })

    # SME panel (server-picked level) — uses soft-import fallback above
    sme_panel = compute_sme_panel(review, default_level=level)
    sme_reviewer_name = name_map.get(sme_panel.get("sme_user_id"))

    # Header “Assigned To …”
    st = (status or "").lower()
    is_qc  = (" qc " in f" {st} ") or st.startswith(f"level {level} qc") or ("qc –" in st) or ("qc -" in st)
    is_sme = ("referred to sme" in st) or ("sme –" in st) or ("sme -" in st)

    def _id(v): return v if v else None
    orig_id = _id(review.get("assigned_to"))
    qc_id   = _id(review.get("qc_assigned_to"))
    sme_id  = _id(review.get(f"l{level}_sme_assigned_to"))

    if is_qc:
        header_assigned_role = "QC Reviewer"
        header_assigned_name = name_map.get(qc_id)
        assigned_to_id       = qc_id
    elif is_sme or sme_mode:
        header_assigned_role = "SME Reviewer"
        header_assigned_name = name_map.get(sme_id)
        assigned_to_id       = sme_id
    else:
        header_assigned_role = "Reviewer"
        header_assigned_name = name_map.get(orig_id)
        assigned_to_id       = orig_id

    # --- Build comparison rows (unchanged from your version) ------------------
    def first(*keys, src=None):
        d = src or review
        for k in keys:
            v = d.get(k)
            if v not in (None, "", "NULL", "N/A"):
                return str(v)
        return ""

    customer_fields_dict = {
        "name": (
            (first("customer_first_name", src=review) + " " + first("customer_last_name", src=review)).strip()
            or first("customer_name", "name", "customer_full_name", src=review)
        ),
        "dob": first("customer_dob", "dob", "date_of_birth", src=review),
        "nationality": first("customer_nationality", "customer_nationalities", "nationality", src=review),
        "address": first("customer_address", "address", "residential_address", src=review),
        "document_type": first("customer_document_type", "document_type", src=review),
        "id_number": first("customer_id_number", "id_number", "document_number", src=review),
        "email_address": first("customer_email", "customer_email_address", "email", src=review),
        "contact_numbers": first("customer_phone", "customer_contact_numbers", "phone", "mobile", src=review),
    }

    watchlist_fields_dict = {
        "name": first("watchlist_name", "wl_name", src=review),
        "dob": first("watchlist_dob", "wl_dob", src=review),
        "nationality": first("watchlist_nationality", "wl_nationality", src=review),
        "address": first("watchlist_address", "wl_address", src=review),
        "document_type": first("watchlist_document_type", "wl_document_type", src=review),
        "id_number": first("watchlist_id_number", "wl_id_number", src=review),
        "email_address": first("watchlist_email_address", "wl_email", src=review),
        "contact_numbers": first("watchlist_contact_numbers", "wl_phone", src=review),
    }

    field_labels = [
        ("name", "Name"),
        ("dob", "Date of Birth"),
        ("nationality", "Nationality"),
        ("address", "Address"),
        ("document_type", "Document Type"),
        ("id_number", "ID Number"),
        ("email_address", "Email"),
        ("contact_numbers", "Phone"),
    ]

    comparison_rows = []
    for key, label in field_labels:
        left  = customer_fields_dict.get(key, "") or "—"
        right = watchlist_fields_dict.get(key, "") or "—"
        comparison_rows.append({"label": label, "customer": left, "watchlist": right})

    record_type = match.get("hit_type", "Individual")

    # READ-ONLY LOGIC:
    # Original behaviour: readonly if outcome exists and we weren't returned from SME.
    # Change: if QC rework is required and *not yet confirmed completed*, unlock for reviewer.
    readonly_default = bool(has_outcome and not sme_returned)
    readonly = bool(
        sme_mode or (
            readonly_default
            and not (rework_required and not rework_completed)  # ← unlock in rework window
        )
    )


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    # --- Back-compat aliases for reviewer_panel (expects cd_*_* fields) ---
    try:
        _slugs = ['entity_type','entity_name','entity_trading_name','entity_registration_number',
                  'entity_incorp_date','entity_status','address_line1','address_line2','city',
                  'postcode','country','sic_codes','lp1_full_name','lp1_role','lp1_dob',
                  'lp1_nationality','lp1_country_residence','lp1_correspondence_address','lp1_appointed_on']
        for _slug in _slugs:
            _orig_key = f"{_slug}_original"
            _enr_key  = f"{_slug}_enriched"
            if _orig_key in review:
                review.setdefault(f"cd_{_slug}_original", review.get(_orig_key))
            if _enr_key in review:
                review.setdefault(f"cd_{_slug}_enriched", review.get(_enr_key))
                review.setdefault(f"cd_{_slug}_enrichment", review.get(_enr_key))
    except Exception as _e:
        try:
            current_app.logger.warning("Alias inject failed: %r", _e)
        except Exception:
            pass
    return render_template("404_redirect.html"), 404

@app.route("/sme_queue")
@role_required("sme", "admin")
def sme_queue():
    status_key = (request.args.get("status") or "").strip().lower()
    sort_by = (request.args.get("sort") or "updated_at").lower()
    date_range = request.args.get("date_range", "wtd")
    age_bucket_q = (request.args.get("age_bucket") or "").strip()

    today = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    def _parse_dt(s):
        if not s:
            return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "").split(".")[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(s)
            except Exception:
                return None

    def _in_range(dt: datetime) -> bool:
        if not dt:
            return False
        d = dt.date()
        if date_range == "wtd": return monday_this <= d <= today
        if date_range == "prevw": return monday_prev <= d <= sunday_prev
        if date_range == "30d": return d >= (today - timedelta(days=30))
        return True

    def _bucket(dt: datetime) -> str:
        if not dt:
            return "5 days+"
        days = (today - dt.date()).days
        if days <= 2: return "1–2 days"
        if days <= 5: return "3–5 days"
        return "5 days+"

    def _norm_bucket(s: str) -> str:
        s = (s or "").strip().replace(" - ", "–").replace("-", "–")
        if s.startswith("1"): return "1–2 days"
        if s.startswith("3"): return "3–5 days"
        return "5 days+" if s else ""

    age_bucket_q = _norm_bucket(age_bucket_q)

    conn = get_db()
    cur = conn.cursor()
    # Pull SME user names too
    rows = cur.execute("""
        SELECT r.*, m.total_score,
               u1.name AS l1_sme_name,
               u2.name AS l2_sme_name,
               u3.name AS l3_sme_name
        FROM reviews r
        LEFT JOIN matches m ON m.task_id = r.task_id
        LEFT JOIN users u1 ON u1.id = r.l1_sme_selected
        LEFT JOIN users u2 ON u2.id = r.l2_sme_selected
        LEFT JOIN users u3 ON u3.id = r.l3_sme_selected
        WHERE r.l1_referred_to_sme IS NOT NULL
           OR r.l2_referred_to_sme IS NOT NULL
           OR r.l3_referred_to_sme IS NOT NULL
        ORDER BY r.updated_at DESC
    """).fetchall()
    conn.close()

    tasks = []
    for row in rows:
        r = dict(row)

        per_level = []
        for lv in (1, 2, 3):
            sel = _parse_dt(r.get(f"l{lv}_sme_selected_date"))
            ret = _parse_dt(r.get(f"l{lv}_sme_returned_date"))
            ass_id = r.get(f"l{lv}_sme_selected")
            ass_name = r.get(f"l{lv}_sme_name") if lv == 1 else (
                       r.get(f"l{lv}_sme_name") if lv == 2 else r.get(f"l{lv}_sme_name"))
            per_level.append((lv, sel, ret, ass_id, ass_name))

        sels = [(lv, sel) for lv, sel, _, _, _ in per_level if sel]
        rets = [(lv, ret) for lv, _, ret, _, _ in per_level if ret]
        latest_sel = max(sels, key=lambda x: x[1]) if sels else (None, None)
        latest_ret = max(rets, key=lambda x: x[1]) if rets else (None, None)

        open_lv, open_sel_dt, open_ass_id, open_ass_name = None, None, None, None
        for lv, sel, ret, ass_id, ass_name in per_level:
            if sel and not ret:
                if (not open_sel_dt) or (sel > open_sel_dt):
                    open_lv, open_sel_dt, open_ass_id, open_ass_name = lv, sel, ass_id, ass_name

        is_open = open_sel_dt is not None
        state_label, relevant_dt = None, None

        if status_key == "open":
            if not is_open:
                continue
            state_label = f"In SME Review (Assigned to {open_ass_name})" if open_ass_name else "Awaiting SME Assignment"
            relevant_dt = open_sel_dt
            if age_bucket_q and _bucket(relevant_dt) != age_bucket_q:
                continue

        elif status_key == "returned":
            if not latest_ret[0]:
                continue
            relevant_dt = latest_ret[1]
            if not _in_range(relevant_dt):
                continue
            state_label = "Returned from SME"
            if age_bucket_q and _bucket(relevant_dt) != age_bucket_q:
                continue

        elif status_key == "referrals":
            if not latest_sel[0]:
                continue
            relevant_dt = latest_sel[1]
            if not _in_range(relevant_dt):
                continue
            state_label = "New SME Referral"
            if age_bucket_q and _bucket(relevant_dt) != age_bucket_q:
                continue

        else:
            if not (sels or rets):
                continue
            if is_open:
                state_label = f"In SME Review (Assigned to {open_ass_name})" if open_ass_name else "Awaiting SME Assignment"
                relevant_dt = open_sel_dt
            elif latest_ret[0]:
                state_label = "Returned from SME"
                relevant_dt = latest_ret[1]
            else:
                state_label = "New SME Referral"
                relevant_dt = latest_sel[1]

        sme_level = (
            open_lv if status_key == "open" and open_lv
            else (latest_ret[0] if status_key == "returned" and latest_ret[0]
            else (latest_sel[0] if latest_sel[0] else None))
        )

        tasks.append({
            "task_id": r.get("task_id"),
            "customer_id": r.get("customer_id"),
            "total_score": r.get("total_score"),
            "status": derive_case_status(r),
            "sme_state": f"{state_label} (Level {sme_level})" if sme_level else state_label,
            "age_bucket": _bucket(relevant_dt) if relevant_dt else "5 days+",
            "relevant_dt": relevant_dt.isoformat(sep=" ") if relevant_dt else (r.get("updated_at") or "—"),
            "updated_at": r.get("updated_at") or "—",
        })

    if sort_by == "score":
        tasks.sort(key=lambda x: (x["total_score"] is None, x["total_score"]), reverse=True)
    else:
        def _key(t):
            dt = _parse_dt(t["relevant_dt"])
            return dt or _parse_dt(t["updated_at"]) or datetime.min
        tasks.sort(key=_key, reverse=True)

    return render_template("404_redirect.html"), 404

@app.route("/admin/field_visibility", methods=["GET", "POST"])
@role_required("admin")
def admin_field_visibility():
    conn = get_db()
    cursor = conn.cursor()

    # Finalised field list aligned with the grouped sections in the template
    all_fields = [
        # Watchlist
        "watchlist_name", "watchlist_dob", "watchlist_nationality", "watchlist_address",
        "watchlist_document_type", "watchlist_id_number", "watchlist_contact_numbers", "watchlist_email_address",

        # Individual Customer
        "first_name", "middle_name", "last_name", "dob", "nationality",
        "customer_gender", "customer_nationalities", "customer_contact_numbers", "customer_email_address",
        "document_type", "id_number", "address",

        # Customer Entity
        "entity_name", "entity_type", "entity_registration_number",
        "entity_country_of_incorporation", "entity_industry", "entity_related_persons",

        # Payments
        "payment_reference", "payment_date", "payment_amount", "payment_currency",
        "payer_name", "payer_country", "beneficiary_name", "beneficiary_country",
        "payment_purpose", "payment_channel",

        # Outcome
        "match_type", "match_probability", "match_reasons", "match_explanation", "screening_rationale"
    ]

    if request.method == "POST":
        selected = request.form.getlist("visible_fields")
        for field in all_fields:
            is_visible = 1 if field in selected else 0
            cursor.execute("""
                INSERT INTO field_visibility (field_name, is_visible)
                VALUES (?, ?)
                ON CONFLICT(field_name) DO UPDATE SET is_visible=excluded.is_visible
            """, (field, is_visible))
        conn.commit()
        flash("Field visibility settings updated.", "success")
        return redirect(url_for("admin_field_visibility"))

    cursor.execute("SELECT field_name, is_visible FROM field_visibility")
    visibility = dict(cursor.fetchall())
    conn.close()

    return render_template("404_redirect.html"), 404

@app.route("/qc_allocate", methods=["POST"])
@role_required("qc_1", "qc_2", "qc_3")
def qc_allocate():
    reviewer_id = request.form.get("qc_reviewer_id")
    review_ids  = request.form.getlist("review_ids")  # list of review.id
    role = session.get("role", "") or ""
    try:
        level = int(role.split("_")[-1]) if "_" in role else 1
    except ValueError:
        level = 1

    if not reviewer_id or not review_ids:
        flash("Select at least one case and a QC reviewer.", "warning")
        return redirect(url_for("qc_lead_dashboard"))

    try:
        reviewer_id = int(reviewer_id)
        ids = [int(x) for x in review_ids]
    except ValueError:
        flash("Invalid selection.", "danger")
        return redirect(url_for("qc_lead_dashboard"))

    conn = get_db()
    cur  = conn.cursor()
    try:
        # Only allocate items truly "awaiting assignment"
        cur.executemany(
            f"""UPDATE reviews
                SET l{level}_qc_assigned_to = ?
                WHERE id = ?
                  AND (l{level}_qc_assigned_to IS NULL OR l{level}_qc_assigned_to = 0)
                  AND (l{level}_qc_end_time IS NULL OR l{level}_qc_end_time = '')""",
            [(reviewer_id, rid) for rid in ids]
        )
        conn.commit()
        flash(f"Allocated {len(ids)} case(s) to selected QC.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Allocation failed: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("qc_lead_dashboard"))

@app.route("/qc_reassign_tasks", methods=["GET", "POST"])
@role_required("qc_1", "qc_2", "qc_3")
def qc_reassign_tasks():
    import sqlite3
    from utils import derive_status

    # --- Determine level from role ---
    session_role = (session.get("role") or "").lower()
    try:
        level = int(session_role.split("_")[-1]) if "_" in session_role else 1
    except Exception:
        level = 1

    reviewer_role = f"qc_review_{level}"   # reviewers (not QCTL role)
    qctl_user_id  = session.get("user_id")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Identify the logged-in QCTL (for team scoping) ---
    cur.execute("SELECT name, email FROM users WHERE id = ?", (qctl_user_id,))
    me_row = cur.fetchone()
    lead_name  = (me_row["name"]  if me_row and me_row["name"]  else "").strip()
    lead_email = (me_row["email"] if me_row and me_row["email"] else "").strip()

    # --- QC reviewers in THIS level, in THIS QCTL's team, active, excluding self ---
    cur.execute("""
        SELECT id, COALESCE(name, email) AS display_name
        FROM users
        WHERE role = ?
          AND (status IS NULL OR status = 'active')
          AND id <> ?
          AND (
               team_lead = ? OR team_lead = ?
            OR reporting_line = ? OR reporting_line = ?
          )
        ORDER BY display_name COLLATE NOCASE
    """, (reviewer_role, qctl_user_id, lead_name, lead_email, lead_name, lead_email))
    reviewers = cur.fetchall()
    allowed_qc_ids = {r["id"] for r in reviewers}

    # ---------- POST: reassign selected ----------
    if request.method == "POST":
        selected_task_ids = request.form.getlist("task_ids")
        new_qc_id        = request.form.get("qc_reviewer_id", type=int)

        if not selected_task_ids or not new_qc_id:
            flash("Please select at least one allocated case and a target QC reviewer.", "warning")
            conn.close()
            return redirect(url_for("qc_reassign_tasks"))

        if new_qc_id not in allowed_qc_ids:
            conn.close()
            flash("You can only reassign to QC reviewers in your team at this level.", "danger")
            return redirect(url_for("qc_reassign_tasks"))

        try:
            for task_id in selected_task_ids:
                # Only reassign if currently allocated (any QC) and not finalised at this level
                cur.execute(f"""
                    UPDATE reviews
                       SET l{level}_qc_assigned_to = ?
                     WHERE task_id = ?
                       AND l{level}_qc_assigned_to IS NOT NULL
                       AND (l{level}_qc_end_time IS NULL OR l{level}_qc_end_time = '')
                """, (new_qc_id, task_id))

                # Re-derive unified status
                cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
                r = cur.fetchone()
                if r:
                    new_status = derive_status(dict(r), level)
                    cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))

            conn.commit()
            flash(f"Reassigned {len(selected_task_ids)} case(s).", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Reassignment failed: {e}", "danger")

        conn.close()
        return redirect(url_for("qc_reassign_tasks"))

    # ---------- GET: list currently allocated (not finalised) ----------
    # Only show cases where the current QC is in the QCTL's team (allowed_qc_ids).
    if allowed_qc_ids:
        placeholders = ",".join(["?"] * len(allowed_qc_ids))
        params = list(allowed_qc_ids)
        cur.execute(f"""
            SELECT
                r.task_id,
                COALESCE(u.name, u.email) AS current_qc,
                r.l{level}_qc_start_time  AS qc_start,
                r.l{level}_qc_end_time    AS qc_end
            FROM reviews r
            JOIN users u ON u.id = r.l{level}_qc_assigned_to
            WHERE r.l{level}_qc_assigned_to IN ({placeholders})
              AND (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '')
            ORDER BY
                CASE WHEN r.l{level}_qc_start_time IS NULL OR r.l{level}_qc_start_time = '' THEN 0 ELSE 1 END,
                r.l{level}_qc_start_time DESC,
                r.task_id
        """, params)
        allocated_rows = cur.fetchall()
    else:
        allocated_rows = []


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route("/qc_wip_cases")
@role_required("qc_1", "qc_2", "qc_3", "qc_review_1", "qc_review_2", "qc_review_3")
def qc_wip_cases():
    import sqlite3
    reviewer_id = request.args.get("reviewer_id", type=int) or session.get("user_id")
    bucket = (request.args.get("bucket") or "assigned").lower()

    role = (session.get("role") or "").lower()
    level = int(role.split("_")[-1]) if role.startswith(("qc_", "qc_review_")) else int(session.get("level", 1))

    col_assigned = "qc_assigned_to"
    col_start    = "qc_start_time"
    col_end      = "qc_end_time"
    col_rew_req  = "qc_rework_required"
    # (Optional) col_check = "qc_check_date"

    where = [f"{col_assigned} = ?"]
    params = [reviewer_id]

    # Buckets:
    # - assigned: assigned to me, not finished (end is null/empty)
    # - in_progress: assigned to me, started, not finished
    # - rework: assigned to me, rework required, not finished
    if bucket == "in_progress":
        where.append(f"({col_start} IS NOT NULL AND {col_start} <> '')")
        where.append(f"({col_end} IS NULL OR {col_end} = '')")
    elif bucket == "rework":
        where.append(f"COALESCE({col_rew_req}, 0) = 1")
        where.append(f"({col_end} IS NULL OR {col_end} = '')")
    else:  # assigned (default)
        where.append(f"({col_end} IS NULL OR {col_end} = '')")

    where_sql = " AND ".join(where)

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(f"""
        SELECT task_id,
               customer_id,
               watchlist_id,
               {col_start} AS qc_start,
               {col_end}   AS qc_end,
               COALESCE({col_rew_req},0) AS rework_required
          FROM reviews
         WHERE {where_sql}
      ORDER BY COALESCE({col_start}, '' ) DESC, task_id DESC
    """, params)

    rows = cur.fetchall()
    cases = [{
        "task_id": r["task_id"],
        "customer": r["customer_id"],
        "watchlist": r["watchlist_id"],
        "qc_start": r["qc_start"],
        "qc_end": r["qc_end"],
        "rework_required": bool(r["rework_required"]),
    } for r in rows]

    # Build outcomes for dropdown (admin-editable)

    try:

        _outcome_names = _load_outcomes_from_db(cursor)

    except Exception:

        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]

    outcomes = [{"name": n} for n in _outcome_names]


    conn.close()

    return render_template("404_redirect.html"), 404

@app.route("/qc_allocation", methods=["GET", "POST"])
@role_required("qc_1", "qc_2", "qc_3")
def qc_allocation():
    from utils import derive_case_status

    # 1) Pull all QC‐sampled reviews for this QC lead
    level = int(session["level"])
    col_ass  = "qc_assigned_to"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"""
        SELECT
          r.*,
          u.name  AS reviewer_name,
          u.email AS reviewer_email
        FROM reviews r
        JOIN qc_sampling_log q
          ON q.review_id = r.id
        LEFT JOIN users u
          ON r.{col_ass} = u.id
        WHERE q.reviewer_id = ?
        ORDER BY r.updated_at DESC
    """, (session["user_id"],))
    rows = cur.fetchall()
    conn.close()

    # 2) Re‐derive status and keep only Completed/Escalated
    reviews = []
    for row in rows:
        rec = dict(row)
        status = derive_case_status(rec)
        if status in ("Completed", "Escalated"):
            rec["status"] = status
            reviews.append(rec)

    # 3) **NEW**: Only QC reviewers at this level
    reviewer_role = f"qc_review_{level}"
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    reviewers = conn.execute(
        "SELECT id, name FROM users WHERE role = ? ORDER BY name",
        (reviewer_role,)
    ).fetchall()
    conn.close()

    return render_template("404_redirect.html"), 404

@app.route("/submit_sme_advice/<task_id>", methods=["POST"])
@app.route("/submit_sme_advice/<task_id>/<int:level>", methods=["POST"])
@role_required("sme", "admin")
def submit_sme_advice(task_id, level=None):
    # guard
    if session.get("role") not in ("sme", "admin"):
        return abort(403)

    advice = (request.form.get("sme_advice") or "").strip()
    if not advice:
        flash("Please provide your advice before submitting.", "warning")
        return redirect(url_for("sme_dashboard"))

    conn = get_db()
    cur  = conn.cursor()

    row = cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return ("Task not found", 404)

    review = dict(row)

    # If level not supplied in URL, best-effort detect the active SME level:
    if level is None:
        best = None
        # prefer an open SME referral (selected but not returned), most recent first
        latest_sel = None
        for lv in (1, 2, 3):
            sel = review.get(f"l{lv}_sme_selected_date")
            ret = review.get(f"l{lv}_sme_returned_date")
            if sel and not ret:
                if (not latest_sel) or (str(sel) > str(latest_sel)):
                    best = lv
                    latest_sel = sel
        # fallbacks
        if best is None:
            for lv in (3, 2, 1):
                if review.get(f"l{lv}_sme_selected_date"):
                    best = lv
                    break
        level = best or 1

    now = datetime.utcnow().isoformat(timespec="seconds")
    me  = session.get("user_id")

    # Build updates using existing columns in your schema
    updates = {
        "sme_response":      advice,
        "sme_returned_date": now,
        "updated_at":                  now,
    }

    # If the “selected” (assignee) field is empty, stamp it with the SME user id
    sel_col = "sme_selected"
    if not review.get(sel_col):
        updates[sel_col] = me

    set_sql = ", ".join(f"{k} = ?" for k in updates.keys())
    vals    = list(updates.values()) + [task_id]

    cur.execute(f"UPDATE reviews SET {set_sql} WHERE task_id = ?", vals)
    conn.commit()
    conn.close()

    flash("SME advice submitted.", "success")
    return redirect(url_for("sme_dashboard"))

@app.before_request
def global_before_request():
    # Treat requests as secure when behind Nginx/ALB forwarding HTTPS
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
    is_secure = request.is_secure or forwarded_proto == "https"

    # Redirect to HTTPS in production
    if ENV == "production" and not is_secure:
        return redirect(request.url.replace("http://", "https://", 1))

    # Routes that don't require login
    public_endpoints = {
        "login",
        "forgot_password",
        "reset_password",
        "reset_email_sent",
        "reset_done",
        "static",          # keep static open
        "healthcheck",     # optional if you have one
        # API endpoints (will be checked for session separately)
        "api_get_user",
        "api_qc_dashboard",
        "api_qc_lead_dashboard",
        "api_reviewer_dashboard",
        "api_my_tasks",
    }

    # request.endpoint can be None (e.g., 404), so guard it
    ep = (request.endpoint or "").split(":")[-1]  # drop blueprint prefix if any

    # Check if this is a public endpoint first - allow these through
    if ep in public_endpoints:
        return None  # Continue to the route handler
    
    # API endpoints should return JSON errors instead of redirecting
    # Allow verify_2fa endpoint if user has pending 2FA session (before other checks)
    if request.path == '/verify_2fa' and 'pending_user_id' in session:
        return None  # Allow through
    
    # Check by path first (before Flask matches route, endpoint will be None)
    is_api_request = request.path.startswith('/api/') or \
                    (request.headers.get('Accept', '').startswith('application/json') and 
                     request.path not in ['/login', '/logout', '/verify_2fa'])
    
    # If it's an API request, handle it specially
    if is_api_request:
        if "user_id" not in session:
            print(f"[DEBUG] API request {request.path} - No session: user_id={session.get('user_id')}, role={session.get('role')}, session_keys={list(session.keys())}")
            from flask import jsonify
            return jsonify({'error': 'Not authenticated'}), 401
        else:
            print(f"[DEBUG] API request {request.path} - Session OK: user_id={session.get('user_id')}, role={session.get('role')}, endpoint={request.endpoint}")
            
            # Update last_active for logged-in users (API requests)
            try:
                conn = get_db()
                conn.execute(
                    "UPDATE users SET last_active = ? WHERE id = ?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session["user_id"]),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[DEBUG] Failed to update last_active for API request: {e}")
                pass
            
            # For API requests with session, allow through to route handler
            # Return None to let Flask continue to route matching
            return None

    # For non-API requests, check session and redirect if needed
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Update last_active for logged-in users (non-API requests)
    if "user_id" in session:
        try:
            conn = get_db()
            conn.execute(
                "UPDATE users SET last_active = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session["user_id"]),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[DEBUG] Failed to update last_active: {e}")
            pass

def get_assignment_counts_by_level(level):
    db = get_db()
    col = "assigned_to"
    query = f"""
        SELECT {col} AS assigned_to, COUNT(*) as count
        FROM reviews
        WHERE {col} IS NOT NULL
        GROUP BY {col}
    """
    return db.execute(query).fetchall()

@app.route("/assign_tasks", methods=["GET", "POST"])
@role_required("team_lead_1", "team_lead_2", "team_lead_3", "operations_manager", "Operations_Manager", "Operations Manager")
def assign_tasks():
    # Check if Due Diligence module is enabled
    if not is_module_enabled('due_diligence'):
        flash('Due Diligence module is currently disabled.', 'warning')
        role = session.get("role", "")
        if role == 'admin':
            return redirect(url_for('list_users'))
        return redirect(url_for('team_leader_dashboard'))
    
    user_role = session.get("role")
    user_id   = session.get("user_id")

    if not user_role or not (user_role.startswith('team_lead_') or user_role in ('operations_manager','Operations_Manager','Operations Manager')):
        return "Access denied", 403

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    lead_user = cur.execute(
        "SELECT name, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not lead_user:
        conn.close()
        return "Unable to identify team lead.", 400

    lead_name   = lead_user["name"]
    lead_user_str = lead_user["role"].split("_")[-1]
    level = lead_user_str if lead_user_str in ("1","2","3") else request.args.get("level", "1")
    if level not in ("1","2","3"):
        level = "1"
    assign_col  = "assigned_to"
    outcome_col = "outcome"
    completed_col = "date_completed"

    # Handle assignment submission
    if request.method == "POST":
        selected_task_ids    = request.form.getlist("task_ids")
        selected_reviewer_id = request.form.get("reviewer_id")

        if not selected_task_ids or not selected_reviewer_id:
            flash("Please select both tasks and a reviewer.", "warning")
        else:
            for pk_id in selected_task_ids:  # using DB primary key here
                # Assign the task
                cur.execute(
                    f"UPDATE reviews SET {assign_col} = ? WHERE id = ?",
                    (selected_reviewer_id, pk_id)
                )

                # Recalculate status
                cur.execute("SELECT * FROM reviews WHERE id = ?", (pk_id,))
                rev = dict(cur.fetchone())
                new_status = derive_status(rev, rev.get("current_level") or int(level))
                cur.execute(
                    "UPDATE reviews SET status = ? WHERE id = ?",
                    (new_status, pk_id)
                )

            conn.commit()
            flash(f"{len(selected_task_ids)} task(s) assigned successfully.", "success")
            conn.close()
            return redirect(url_for("assign_tasks"))

    # Load reviewers (Ops = all reviewers; TL = own team)
    is_ops = (session.get("role") or "").lower() in ("operations_manager", "operations manager")
    if is_ops:
        cur.execute("""
            SELECT id, COALESCE(name,email) AS name, role
            FROM users
            WHERE role = ?
              AND (status IS NULL OR status = 'active')
            ORDER BY name COLLATE NOCASE
        """, (f"reviewer_{level}",))
    else:
        cur.execute("""
            SELECT id, COALESCE(name,email) AS name, role
            FROM users
            WHERE role = ? AND LOWER(team_lead) = LOWER(?)
              AND (status IS NULL OR status = 'active')
            ORDER BY name COLLATE NOCASE
        """, (f"reviewer_{level}", lead_name))
    reviewers_raw = cur.fetchall()

    reviewers = []
    assignment_counts = {}
    for row in reviewers_raw:
        reviewer_id = row["id"]
        cur.execute(f"""
            SELECT COUNT(*) FROM reviews
            WHERE {assign_col} = ? AND {completed_col} IS NULL
        """, (reviewer_id,))
        open_tasks = cur.fetchone()[0]
        reviewers.append({
            "id": reviewer_id,
            "name": row["name"],
            "role": row["role"],
            "open_tasks": open_tasks,
            "level": level
        })
        assignment_counts[reviewer_id] = open_tasks

    # Fetch unassigned tasks + join matches for total_score
    cur.execute(f"""
        SELECT r.id, r.task_id, r.updated_at, m.total_score
        FROM reviews r
        LEFT JOIN matches m ON m.task_id = r.task_id
        WHERE (r.{assign_col} IS NULL OR TRIM(COALESCE(r.{assign_col}, '')) = '')
          AND (r.{outcome_col} IS NULL OR TRIM(COALESCE(r.{outcome_col}, '')) = '')
          AND (r.{completed_col} IS NULL OR TRIM(COALESCE(r.{completed_col}, '')) = '')
        GROUP BY r.id
        ORDER BY r.updated_at ASC
        LIMIT 500
    """)
    all_unassigned = cur.fetchall()

    unassigned_tasks = []
    for row in all_unassigned:
        # Force "Under Review" label here
        unassigned_tasks.append({
            "id": row["id"],
            "task_id": row["task_id"],
            "status": "Under Review",
            "updated_at": row["updated_at"],
            "total_score": row["total_score"]
        })

    # Build filtered list of truly unassigned tasks for this level
    valid_unassigned_tasks = []
    for row in all_unassigned:
        row_dict = dict(row)
        status = derive_case_status(row_dict)
        if status == f"Level {level} – Unassigned":
            valid_unassigned_tasks.append(row_dict)

    unassigned_count = len(valid_unassigned_tasks)



        # Handle bulk assignment
    if request.method == "POST" and "selected_reviewers" in request.form:
        selected_ids = request.form.getlist("selected_reviewers", type=int)
        task_count   = int(request.form.get("task_count", 5))
        assign_index = 0

        for reviewer_id in selected_ids:
            if reviewer_id not in reviewer_ids:
                continue
            for _ in range(task_count):
                if assign_index >= len(valid_unassigned_tasks):
                    break
                review_id = valid_unassigned_tasks[assign_index]["id"]

                # 1) Assign
                cur.execute(
                    f"UPDATE reviews SET {assign_col} = ? WHERE id = ?",
                    (reviewer_id, review_id)
                )

                # 2) Re-derive & write back status
                cur.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
                rev = dict(cur.fetchone())
                new_status = derive_status(rev, rev.get("current_level") or int(level))
                cur.execute(
                    "UPDATE reviews SET status = ? WHERE id = ?",
                    (new_status, review_id)
                )
                assign_index += 1

        conn.commit()
        flash(f"{assign_index} task(s) successfully assigned.", "success")
        conn.close()
        return redirect(url_for("assign_tasks_bulk"))


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]
    # --- Build assignment_counts: current in-progress counts per reviewer ---
    try:
        # Determine column names for this level
        assign_col = f"l{level}_reviewer_id"
        completed_col = "date_completed"

        cur.execute(f"""
            SELECT {assign_col} AS reviewer_id, COUNT(*) AS cnt
            FROM reviews
            WHERE {assign_col} IS NOT NULL
              AND ({completed_col} IS NULL OR {completed_col} = '')
            GROUP BY {assign_col}
        """)
        assignment_counts_rows = cur.fetchall()
        assignment_counts = { int(r["reviewer_id"]): r["cnt"] for r in assignment_counts_rows if r["reviewer_id"] is not None }
    except Exception as _e:
        assignment_counts = {}
    # --- Build assignment_counts: current in-progress counts per reviewer ---
    assignment_counts = {}
    try:
        session_role = (session.get("role") or "").lower()
        try:
            level_val = int(session_role.split("_")[-1]) if "_" in session_role else int(level)  # use existing level
        except Exception:
            try:
                level_val = int(level)  # if defined earlier
            except Exception:
                level_val = 1

        assign_col = f"l{level_val}_reviewer_id"
        completed_col = f"l{level_val}_date_completed"

        try:
            cur  # ensure cursor exists
        except NameError:
            conn2 = get_db()
            conn2.row_factory = sqlite3.Row
            cur = conn2.cursor()

        cur.execute(f"""
            SELECT {assign_col} AS reviewer_id, COUNT(*) AS cnt
            FROM reviews
            WHERE {assign_col} IS NOT NULL
              AND ({completed_col} IS NULL OR {completed_col} = '')
            GROUP BY {assign_col}
        """)
        rows = cur.fetchall()
        for r in rows:
            rid = r["reviewer_id"]
            if rid is None:
                continue
            try:
                rid = int(rid)
            except Exception:
                pass
            assignment_counts[rid] = r["cnt"]
    except Exception as _e:
        assignment_counts = {}

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route("/qc_lead_dashboard")
@role_required("qc_1", "qc_2", "qc_3")
def qc_lead_dashboard():
    import sqlite3
    from datetime import datetime, timedelta

    # --- QC level from role ---
    role = (session.get("role") or "").lower()
    try:
        level = int(role.split("_")[-1]) if "_" in role else 1
    except Exception:
        level = 1

    # --- Date range (for Completed & QC Pass %) ---
    # Allowed: this_week | prev_week | last_30 | all_time
    selected_date = (request.args.get("date_range") or "this_week").lower()
    date_ranges = [
        {"value": "this_week", "label": "Current Week"},
        {"value": "prev_week", "label": "Previous Week"},
        {"value": "last_30",   "label": "Last 30 Days"},
        {"value": "all_time",  "label": "All Time"},
    ]

    def bounds_for(dr: str):
        today = datetime.utcnow().date()  # use UTC to match SQLite date()
        # Monday as start of week
        monday_this_week = today - timedelta(days=today.weekday())
        monday_prev_week = monday_this_week - timedelta(days=7)
        monday_next_week = monday_this_week + timedelta(days=7)

        if dr == "this_week":
            start = monday_this_week
            end   = monday_next_week
        elif dr == "prev_week":
            start = monday_prev_week
            end   = monday_this_week
        elif dr == "last_30":
            start = today - timedelta(days=29)
            end   = today + timedelta(days=1)
        elif dr == "all_time":
            # very wide window; avoids extra WHERE clauses in SQL branching
            start = datetime(1970, 1, 1).date()
            end   = datetime(2999, 12, 31).date()
        else:
            # fallback
            start = monday_this_week
            end   = monday_next_week

        return start.isoformat(), end.isoformat()

    ds, de = bounds_for(selected_date)

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------- KPIs ----------
    # Active WIP (NOT date-filtered): only tasks assigned to QC reviewers (not unassigned)
    # Unassigned tasks should only show in "Awaiting Assignment", not in Active WIP
    cur.execute(f"""
        SELECT COUNT(*) AS count
        FROM reviews r
        INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
        WHERE (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '' OR r.l{level}_qc_end_time = '0')
          AND r.l{level}_qc_assigned_to IS NOT NULL
          AND r.l{level}_qc_assigned_to != 0
    """)
    active_wip = cur.fetchone()["count"]

    # Outstanding Reworks (NOT date-filtered)
    cur.execute(f"""
        SELECT COUNT(*) AS count
        FROM reviews r
        WHERE r.l{level}_qc_rework_required = 1
          AND (r.l{level}_qc_rework_completed IS NULL OR r.l{level}_qc_rework_completed = 0)
    """)
    outstanding_reworks = cur.fetchone()["count"]

    # Completed (date-filtered) – finished QC checks at this level
    cur.execute(f"""
        SELECT COUNT(*) AS count
        FROM reviews r
        WHERE r.l{level}_qc_end_time IS NOT NULL
          AND r.l{level}_qc_end_time <> ''
          AND date(r.l{level}_qc_end_time) >= date(?)
          AND date(r.l{level}_qc_end_time) <  date(?)
    """, (ds, de))
    total_completed = cur.fetchone()["count"]

    # QC Pass % (date-filtered)
    cur.execute(f"""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN r.l{level}_outcome = r.l{level}_qc_outcome THEN 1 ELSE 0 END) AS matches
        FROM reviews r
        WHERE r.l{level}_qc_outcome IS NOT NULL
          AND r.l{level}_qc_outcome <> ''
          AND r.l{level}_qc_end_time IS NOT NULL
          AND r.l{level}_qc_end_time <> ''
          AND date(r.l{level}_qc_end_time) >= date(?)
          AND date(r.l{level}_qc_end_time) <  date(?)
    """, (ds, de))
    r = cur.fetchone()
    qc_sample   = (r["total"] or 0)
    qc_pass_pct = round((r["matches"] or 0) * 100.0 / qc_sample, 1) if qc_sample else 0.0

    # ---------- Team WIP table (clickable buckets) ----------
    # Only include tasks that are actually in QC workflow (in qc_sampling_log AND (assigned to QC OR completed and awaiting QC))
    cur.execute(f"""
        WITH base AS (
          SELECT r.*,
                 COALESCE(u.name, u.email) AS reviewer_name
          FROM reviews r
          INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
          LEFT JOIN users u ON u.id = r.l{level}_qc_assigned_to
          WHERE (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '' OR r.l{level}_qc_end_time = '0')
            AND (
              (r.l{level}_qc_assigned_to IS NOT NULL AND r.l{level}_qc_assigned_to != 0)
              OR (r.l{level}_date_completed IS NOT NULL AND (r.l{level}_qc_assigned_to IS NULL OR r.l{level}_qc_assigned_to = 0))
            )
        )
        SELECT
          reviewer_name,
          l{level}_qc_assigned_to AS reviewer_id,
          SUM(CASE WHEN l{level}_qc_assigned_to IS NOT NULL
                     AND l{level}_qc_assigned_to != 0
                     AND (l{level}_qc_start_time IS NULL OR l{level}_qc_start_time = '')
                     AND (l{level}_qc_end_time   IS NULL OR l{level}_qc_end_time   = '')
                   THEN 1 ELSE 0 END) AS assigned,
          SUM(CASE WHEN (l{level}_qc_start_time IS NOT NULL AND l{level}_qc_start_time <> '')
                     AND (l{level}_qc_end_time   IS NULL    OR l{level}_qc_end_time   = '')
                   THEN 1 ELSE 0 END) AS in_progress,
          SUM(CASE WHEN l{level}_qc_rework_required = 1
                     AND (l{level}_qc_rework_completed IS NULL OR l{level}_qc_rework_completed = 0)
                   THEN 1 ELSE 0 END) AS rework_pending,
          SUM(CASE WHEN l{level}_qc_rework_required = 1
                     AND l{level}_qc_rework_completed = 1
                     AND (l{level}_qc_end_time IS NULL OR l{level}_qc_end_time = '')
                   THEN 1 ELSE 0 END) AS pending_recheck
        FROM base
        WHERE l{level}_qc_assigned_to IS NOT NULL AND l{level}_qc_assigned_to != 0
        GROUP BY reviewer_name, reviewer_id
        ORDER BY reviewer_name COLLATE NOCASE
    """)
    team_wip_rows = [dict(x) for x in cur.fetchall()]
    for row in team_wip_rows:
        row["assigned"]        = row.get("assigned") or 0
        row["in_progress"]     = row.get("in_progress") or 0
        row["rework_pending"]  = row.get("rework_pending") or 0
        row["pending_recheck"] = row.get("pending_recheck") or 0
        row["total_wip"] = row["assigned"] + row["in_progress"] + row["rework_pending"] + row["pending_recheck"]

    # Awaiting assignment (global bucket)
    cur.execute(f"""
        SELECT COUNT(*) AS awaiting_assignment
        FROM reviews r
        WHERE r.l{level}_date_completed IS NOT NULL
          AND (r.l{level}_qc_assigned_to IS NULL OR r.l{level}_qc_assigned_to = 0)
          AND (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '')
    """)
    awaiting_assignment = cur.fetchone()["awaiting_assignment"]

    # ---------- Individual Output (Completed) for QC (date-filtered) ----------
    cur.execute(f"""
        SELECT
          COALESCE(u.name, u.email) AS reviewer_name,
          COUNT(*) AS completed_count
        FROM reviews r
        JOIN users u ON u.id = r.l{level}_qc_assigned_to
        WHERE r.l{level}_qc_end_time IS NOT NULL
          AND r.l{level}_qc_end_time <> ''
          AND date(r.l{level}_qc_end_time) >= date(?)
          AND date(r.l{level}_qc_end_time) <  date(?)
        GROUP BY reviewer_name
        ORDER BY completed_count DESC, reviewer_name COLLATE NOCASE
        LIMIT 20
    """, (ds, de))
    out_rows = cur.fetchall()
    reviewer_output_labels = [row["reviewer_name"] for row in out_rows]
    reviewer_output_counts = [row["completed_count"] for row in out_rows]

    # ---------- Sampling rates (optional) ----------
    cur.execute("""
        SELECT COALESCE(u.name,u.email) AS reviewer_name, s.rate
        FROM sampling_rates s
        JOIN users u ON u.id = s.reviewer_id
        WHERE s.level = ?
        ORDER BY reviewer_name COLLATE NOCASE
    """, (level,))
    sampling_rates = [dict(x) for x in cur.fetchall()]

    # Build outcomes for dropdown (admin-editable)

    try:

        _outcome_names = _load_outcomes_from_db(cursor)

    except Exception:

        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]

    outcomes = [{"name": n} for n in _outcome_names]


    conn.close()

    return render_template("404_redirect.html"), 404

@app.route("/qc_assign_tasks", methods=["GET", "POST"])
@role_required("qc_1", "qc_2", "qc_3")
def qc_assign_tasks():
    import sqlite3
    from utils import derive_status

    # --- level from role ---
    session_role = (session.get("role") or "").lower()
    try:
        level = int(session_role.split("_")[-1]) if "_" in session_role else 1
    except Exception:
        level = 1

    reviewer_role = f"qc_review_{level}"   # <- reviewers, not the QCTL role
    qctl_user_id  = session.get("user_id")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- who is the QCTL? (for team scoping) ----
    cur.execute("SELECT name, email FROM users WHERE id = ?", (qctl_user_id,))
    me_row = cur.fetchone()
    lead_name  = (me_row["name"]  if me_row and me_row["name"]  else "").strip()
    lead_email = (me_row["email"] if me_row and me_row["email"] else "").strip()

    # ---- QC reviewers in THIS level and THIS QCTL's team, active, excluding self ----
    cur.execute("""
        SELECT id, COALESCE(name,email) AS display_name
        FROM users
        WHERE role = ?
          AND (status IS NULL OR status = 'active')
          AND id <> ?
          AND (
               team_lead = ? OR team_lead = ?
            OR reporting_line = ? OR reporting_line = ?
          )
        ORDER BY display_name COLLATE NOCASE
    """, (reviewer_role, qctl_user_id, lead_name, lead_email, lead_name, lead_email))
    qc_reviewers = cur.fetchall()
    allowed_qc_ids = {row["id"] for row in qc_reviewers}

    # ---------- POST: allocate ----------
    if request.method == "POST":
        selected_task_ids = request.form.getlist("task_ids")
        qc_reviewer_id    = request.form.get("qc_reviewer_id", type=int)

        if not selected_task_ids or not qc_reviewer_id:
            flash("Please select at least one task and a QC reviewer.", "warning")
            conn.close()
            return redirect(url_for("qc_assign_tasks"))

        # hard check: can only assign to allowed reviewer pool
        if qc_reviewer_id not in allowed_qc_ids:
            conn.close()
            flash("You can only allocate to QC reviewers in your team at this level.", "danger")
            return redirect(url_for("qc_assign_tasks"))

        try:
            for task_id in selected_task_ids:
                # Assign only if still unassigned & not QC-finalised
                cur.execute(f"""
                    UPDATE reviews
                       SET l{level}_qc_assigned_to = ?
                     WHERE task_id = ?
                       AND (l{level}_qc_assigned_to IS NULL OR l{level}_qc_assigned_to = 0)
                       AND (l{level}_qc_end_time   IS NULL OR l{level}_qc_end_time   = '')
                """, (qc_reviewer_id, task_id))

                # Re-derive unified status
                cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
                r = cur.fetchone()
                if r:
                    new_status = derive_status(dict(r), level)
                    cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))

            conn.commit()
            flash(f"Allocated {len(selected_task_ids)} task(s) to the selected QC.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Allocation failed: {e}", "danger")

        conn.close()
        return redirect(url_for("qc_assign_tasks"))

    # ---------- GET: fetch allocatable cases ----------
    cur.execute(f"""
        SELECT
            r.id,
            r.task_id,
            r.l{level}_date_completed AS completed_at,
            COALESCE(u.name,u.email)  AS completed_by
        FROM reviews r
        LEFT JOIN users u ON u.id = r.l{level}_completed_by
        WHERE r.l{level}_date_completed IS NOT NULL
          AND (r.l{level}_qc_assigned_to IS NULL OR r.l{level}_qc_assigned_to = 0)
          AND (r.l{level}_qc_end_time IS NULL OR r.l{level}_qc_end_time = '')
        ORDER BY r.l{level}_date_completed DESC
        LIMIT 500
    """)
    unassigned_rows = cur.fetchall()


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route("/qc_dashboard")
@role_required("qc_1", "qc_2", "qc_3", "qc_review_1", "qc_review_2", "qc_review_3")
def qc_dashboard():
    # --- imports needed for date math ---
    from datetime import datetime, date, timedelta
    import sqlite3

    # --- session context ---
    user_id = session.get("user_id")
    role = (session.get("role") or "").lower()
    # allow qc_review_* to behave like qc_*
    if role.startswith("qc_review_"):
        level = int(role.split("_")[-1])
    else:
        level = int(role.split("_")[-1]) if role.startswith("qc_") else int(session.get("level", 1))

    # --- dynamic column names for this QC level ---
    col_qc_assigned = "qc_assigned_to"
    col_qc_check    = "qc_check_date"
    col_qc_outcome  = "qc_outcome"
    col_qc_comment  = "qc_comment"
    col_qc_rew_req  = "qc_rework_required"
    col_qc_rew_done = "qc_rework_completed"
    col_qc_start    = "qc_start_time"
    col_qc_end      = "qc_end_time"

    # --- date range filter (UI) ---
    date_ranges = [
        {"value": "today",   "label": "Today"},
        {"value": "week",    "label": "This Week"},
        {"value": "month",   "label": "This Month"},
        {"value": "quarter", "label": "This Quarter"},
        {"value": "ytd",     "label": "Year to Date"},
        {"value": "all",     "label": "All"},
    ]
    selected_date = (request.args.get("date_range") or "month").lower()

    def range_bounds(kind: str):
        """Return (start_iso, end_iso) in UTC ISO seconds or (None, None) for All."""
        today = date.today()
        if kind == "today":
            start = datetime.combine(today, datetime.min.time())
            end   = datetime.combine(today, datetime.max.time())
        elif kind == "week":
            start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
            end   = datetime.combine(start.date() + timedelta(days=6), datetime.max.time())
        elif kind == "month":
            start = datetime(today.year, today.month, 1)
            if today.month == 12:
                end = datetime(today.year, 12, 31, 23, 59, 59)
            else:
                next_m1 = datetime(today.year, today.month + 1, 1)
                end = next_m1 - timedelta(seconds=1)
        elif kind == "quarter":
            q = (today.month - 1)//3 + 1
            q_start_month = 3*(q-1) + 1
            start = datetime(today.year, q_start_month, 1)
            if q == 4:
                end = datetime(today.year, 12, 31, 23, 59, 59)
            else:
                end = datetime(today.year, q_start_month + 3, 1) - timedelta(seconds=1)
        elif kind == "ytd":
            start = datetime(today.year, 1, 1)
            end   = datetime.combine(today, datetime.max.time())
        else:  # all
            return (None, None)
        return (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))

    start_iso, end_iso = range_bounds(selected_date)

    # --- DB ---
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Helper WHERE for period on QC check date
    where_period = ""
    params_period = []
    if start_iso and end_iso:
        where_period = f" AND {col_qc_check} >= ? AND {col_qc_check} <= ? "
        params_period = [start_iso, end_iso]

    # --- KPI: Active WIP (assigned to me, not finished) ---
    cur.execute(f"""
        SELECT COUNT(*) AS c
          FROM reviews
         WHERE {col_qc_assigned} = ?
           AND ({col_qc_end} IS NULL OR {col_qc_end} = '')
    """, (user_id,))
    active_wip = cur.fetchone()["c"] or 0

    # --- KPI: Completed in selected period (QC checks) ---
    # Exclude tasks that are in rework (if rework is required, exclude regardless of completed status)
    cur.execute(f"""
        SELECT COUNT(*) AS c
          FROM reviews
         WHERE {col_qc_assigned} = ?
           AND {col_qc_check} IS NOT NULL
           AND {col_qc_check} <> ''
           AND NOT (COALESCE({col_qc_rew_req}, 0) = 1)
           {where_period}
    """, (user_id, *params_period))
    completed_in_range = cur.fetchone()["c"] or 0

    # --- KPI: Outstanding Reworks (required, not completed) ---
    # If qc_rework_required = 1, it's outstanding rework (regardless of qc_rework_completed, as that may be from a previous cycle)
    cur.execute(f"""
        SELECT COUNT(*) AS c
          FROM reviews
         WHERE {col_qc_assigned} = ?
           AND COALESCE({col_qc_rew_req}, 0) = 1
    """, (user_id,))
    outstanding_reworks = cur.fetchone()["c"] or 0

    # --- QC Outcomes distribution (Pass/Pass With Feedback/Fail) in selected period ---
    # Exclude tasks that are in rework (if rework is required, exclude regardless of completed status)
    cur.execute(f"""
        SELECT {col_qc_outcome} AS outcome, COUNT(*) AS n
          FROM reviews
         WHERE {col_qc_assigned} = ?
           AND {col_qc_outcome} IS NOT NULL
           AND {col_qc_outcome} <> ''
           AND NOT (COALESCE({col_qc_rew_req}, 0) = 1)
           {where_period}
      GROUP BY {col_qc_outcome}
    """, (user_id, *params_period))
    rows = cur.fetchall()
    dist = { (r["outcome"] or "").strip(): r["n"] for r in rows }
    qc_sample = sum(dist.values())
    qc_pass_n = dist.get("Pass", 0) + dist.get("Pass With Feedback", 0)
    qc_pass_pct = round((qc_pass_n / qc_sample) * 100, 1) if qc_sample else 0.0

    # --- Recent completions (most recent QC checks by me) ---
    cur.execute(f"""
        SELECT task_id, {col_qc_check} AS qc_end
          FROM reviews
         WHERE {col_qc_assigned} = ?
           AND {col_qc_check} IS NOT NULL
           AND {col_qc_check} <> ''
           {where_period}
      ORDER BY {col_qc_check} DESC
         LIMIT 20
    """, (user_id, *params_period))
    recent = [{"task_id": r["task_id"], "qc_end": r["qc_end"]} for r in cur.fetchall()]

    # --- My WIP table (assigned to me, not finished) ---
    cur.execute(f"""
        SELECT task_id,
               {col_qc_start} AS qc_start,
               COALESCE({col_qc_rew_req}, 0) AS rework_required,
               COALESCE({col_qc_rew_done}, 0) AS rework_completed
          FROM reviews
         WHERE {col_qc_assigned} = ?
           AND ({col_qc_end} IS NULL OR {col_qc_end} = '')
      ORDER BY COALESCE({col_qc_start}, '') DESC, task_id DESC
    """, (user_id,))
    my_wip_rows = [{
        "task_id": r["task_id"],
        "qc_start": r["qc_start"],
        "rework_required": bool(r["rework_required"]),
        "rework_completed": bool(r["rework_completed"]),
    } for r in cur.fetchall()]

    # Build outcomes for dropdown (admin-editable)

    try:

        _outcome_names = _load_outcomes_from_db(cursor)

    except Exception:

        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]

    outcomes = [{"name": n} for n in _outcome_names]


    conn.close()

    return render_template("404_redirect.html"), 404

@app.route("/qc_status_dashboard")
@role_required("qc","qc_review_1","qc_review_2","qc_review_3")
def qc_status_dashboard():
    level           = session["level"]
    user_id         = session["user_id"]
    selected_status = request.args.get("status","").strip()

    col_ass = "qc_assigned_to"
    col_chk = "qc_check_date"
    col_out = "qc_outcome"

    conn = get_db()
    cur  = conn.cursor()

    # filterable outcomes
    cur.execute(f"SELECT DISTINCT {col_out} FROM reviews WHERE {col_ass} = ?", (user_id,))
    statuses = [r[0] for r in cur.fetchall() if r[0]]

    # base query
    query = f"""
      SELECT r.*, u.name AS assigned_by, r.l{level}_date_assigned AS assigned_at
        FROM reviews r
        JOIN qc_sampling_log q ON q.review_id = r.id
        LEFT JOIN users u    ON r.{col_ass} = u.id
       WHERE q.reviewer_id = ?
         AND r.{col_ass} = ?
         AND (
              r.{col_chk} IS NULL
           OR (r.l{level}_qc_rework_required = 1
               AND r.l{level}_qc_rework_completed = 0)
         )
    """
    params = [user_id, user_id]
    if selected_status:
        query += f" AND r.{col_out} = ?"
        params.append(selected_status)

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()

    tasks = [ {**dict(r), "status": derive_case_status(dict(r))} for r in rows ]

    return render_template("404_redirect.html"), 404

@app.route("/qcqa_review/<task_id>", methods=["GET", "POST"])
def qcqa_review(task_id):
    user_role = session.get("role")
    user_id   = session.get("user_id")

    if not user_role or not (user_role.startswith("qc_") or user_role == "qa"):
        return "Access denied", 403

    table = "qc_checks" if user_role.startswith("qc_") else "qa_checks"

    conn      = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur       = conn.cursor()

    # Load the review & match
    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    review = cur.fetchone()
    cur.execute("SELECT * FROM matches WHERE task_id = ?", (task_id,))
    match  = cur.fetchone()

    if not review:
        conn.close()
        return "Review not found", 404

    # Determine the level for QC
    level = (
        1 if review["qc_assigned_to"] == user_id else
        2 if review["qc_assigned_to"] == user_id else
        3 if review["qc_assigned_to"] == user_id else
        "Unknown"
    )

    if request.method == "POST":
        outcome         = request.form["outcome"]
        comment         = request.form.get("comment", "")
        rework_required = request.form.get("rework_required") == "on"
        rework_notes    = request.form.get("rework_notes", "")
        action          = request.form.get("action", "")
        now             = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # 1) Insert QC/QA check record
        cur.execute(f"""
            INSERT INTO {table} (
                review_id, outcome, comment, rework_required, rework_notes, created_at
            ) VALUES (
                (SELECT id FROM reviews WHERE task_id = ?), ?, ?, ?, ?, ?
            )
        """, (task_id, outcome, comment, int(rework_required), rework_notes, now))

        # 2) Update main review QC fields
        if user_role.startswith("qc_") and level != "Unknown":
            cur.execute(f"""
                UPDATE reviews
                   SET l{level}_qc_outcome        = ?,
                       l{level}_qc_comment        = ?,
                       l{level}_qc_check_date     = ?,
                       l{level}_qc_rework_required= ?,
                       l{level}_qc_rework_completed= ?,
                       l{level}_qc_end_time       = ?
                 WHERE task_id = ?
            """, (
                outcome,
                comment,
                now,
                int(rework_required),
                int(not rework_required),
                now,
                task_id
            ))

        # 3) Escalation / SME logic
        outcome_field   = "outcome"
        review_outcome  = review.get(outcome_field, "")
        should_promote  = (review_outcome == "Potential True Match" and not rework_required)

        if rework_required:
            cur.execute("""
                UPDATE reviews
                   SET updated_at = ?
                 WHERE task_id = ?
            """, (now, task_id))
        if request.method == "POST" and action == "refer_sme":
            cur.execute("""
                UPDATE reviews
                   SET sme_status = 'Pending SME',
                       updated_at  = ?
                 WHERE task_id = ?
            """, (now, task_id))
        elif should_promote:
            if level == 1:
                cur.execute("""
                    UPDATE reviews
                       SET l2_assigned_to    = NULL,
                           l2_date_assigned  = NULL,
                           updated_at        = ?
                     WHERE task_id = ?
                """, (now, task_id))
            elif level == 2:
                cur.execute("""
                    UPDATE reviews
                       SET l3_assigned_to    = NULL,
                           l3_date_assigned  = NULL,
                           updated_at        = ?
                     WHERE task_id = ?
                """, (now, task_id))
            elif level == 3:
                cur.execute("""
                    UPDATE reviews
                       SET updated_at = ?
                     WHERE task_id = ?
                """, (now, task_id))

        # 4) Re-derive and update the canonical status
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        rev = dict(cur.fetchone())
        new_status = derive_status(rev, rev["current_level"])
        cur.execute(
            "UPDATE reviews SET status = ? WHERE task_id = ?",
            (new_status, task_id)
        )

        conn.commit()
        conn.close()
        flash("QC/QA review submitted.", "success")
        return redirect(url_for("qc_dashboard" if user_role.startswith("qc_") else "qa_dashboard"))

    # On GET: optionally set QC start time
    if user_role.startswith("qc_") and level != "Unknown":
        start_col = "qc_start_time"
        cur.execute(f"""
            UPDATE reviews
               SET {start_col} = ?
             WHERE task_id = ?
               AND ({start_col} IS NULL OR {start_col} = '')
        """, (datetime.utcnow().isoformat(), task_id))
        conn.commit()

    # Prepare render context
    status         = derive_status(dict(review), level)
    reviewer_name  = session.get("email")
    hit_type       = (review["hit_type"] or "").lower() if "hit_type" in review.keys() else ""
    total_score    = match["total_score"] if match and "total_score" in match.keys() else None
    system_rationale = match["match_explanation"] if match and "match_explanation" in match.keys() else None

    match_dict             = dict(match) if match else {}
    customer_fields_dict   = {k: v for k, v in match_dict.items() if k.startswith("customer_")}
    watchlist_fields_dict  = {k: v for k, v in match_dict.items() if k.startswith("watchlist_")}


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404


@app.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    conn = sqlite3.connect('scrutinise_workflow.db')
    c = conn.cursor()

    # Fetch user
    c.execute("SELECT id, name, email, role, team_lead FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        flash("User not found.")
        return redirect(url_for("list_users"))

    user = {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "role": row[3],
        "team_lead": row[4]
    }

    # Fetch available leads
    c.execute("""
        SELECT name FROM users
        WHERE role LIKE 'team_lead_%'
           OR role LIKE 'qc_%'
           OR role LIKE 'qa_%'
           OR role IN ('operations_manager', 'admin')
        ORDER BY name
    """)
    leads = [{"name": row[0]} for row in c.fetchall()]
    conn.close()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        role = request.form["role"]
        team_lead = request.form.get("team_lead", "")

        # ✅ Infer level from role (only if valid numeric suffix exists)
        level = None
        role_parts = role.split("_")
        if len(role_parts) >= 2 and role_parts[-1].isdigit():
            level = int(role_parts[-1])

        conn = sqlite3.connect('scrutinise_workflow.db')
        c = conn.cursor()
        c.execute("UPDATE users SET name = ?, email = ?, role = ?, team_lead = ?, level = ? WHERE id = ?",
                  (name, email, role, team_lead, level, user_id))
        conn.commit()
        conn.close()
        flash("User updated successfully.")
        return redirect(url_for("list_users"))

    return render_template("404_redirect.html"), 404

def build_team_leader_dashboard_sql(level):
    return {
        "reviewer_stats": f"""
            SELECT
                u.name,
                u.role,
                u.team_lead,
                SUM(CASE WHEN r.l{level}_date_assigned IS NOT NULL AND r.l{level}_date_completed IS NULL THEN 1 ELSE 0 END) AS assigned,
                SUM(CASE WHEN r.l{level}_date_completed IS NOT NULL THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN r.l{level}_date_assigned IS NOT NULL AND r.l{level}_date_completed IS NULL THEN 1 ELSE 0 END) AS in_progress,
                SUM(CASE WHEN r.l{level}_qc_rework_required = 1 AND r.l{level}_qc_rework_completed IS NULL THEN 1 ELSE 0 END) AS rework,
                SUM(CASE WHEN r.l{level}_referred_to_sme = 'Yes' THEN 1 ELSE 0 END) AS sme
            FROM users u
            LEFT JOIN reviews r ON u.id = r.l{level}_assigned_to
            WHERE u.role = ? AND u.team_lead = ?
            GROUP BY u.name, u.role, u.team_lead
        """,

        "qc_stats": f"""
            SELECT u.name,
                   ROUND(SUM(CASE WHEN qc.outcome = 'Pass' THEN 1 ELSE 0 END) * 100.0 /
                         COUNT(qc.outcome), 1) AS qc_pct
            FROM users u
            JOIN reviews r ON u.id = r.l{level}_assigned_to
            JOIN qc_checks qc ON r.id = qc.review_id
            WHERE u.role = ? AND u.team_lead = ?
            GROUP BY u.name
        """,

        "qa_stats": f"""
            SELECT u.name,
                   ROUND(SUM(CASE WHEN qa.outcome = 'Pass' THEN 1 ELSE 0 END) * 100.0 /
                         COUNT(qa.outcome), 1) AS qa_pct
            FROM users u
            JOIN reviews r ON u.id = r.l{level}_assigned_to
            JOIN qa_checks qa ON r.id = qa.review_id
            WHERE u.role = ? AND u.team_lead = ?
            GROUP BY u.name
        """,

        "workload_rows": f"""
            SELECT u.name, COUNT(r.id) AS completed
            FROM users u
            JOIN reviews r ON u.id = r.l{level}_assigned_to
            WHERE r.l{level}_date_completed >= ? AND u.role = ? AND u.team_lead = ?
            GROUP BY u.name
        """,

        "qc_summary": f"""
            SELECT qc.outcome, COUNT(*) as count
            FROM qc_checks qc
            JOIN reviews r ON r.id = qc.review_id
            JOIN users u ON r.l{level}_assigned_to = u.id
            WHERE r.l{level}_qc_check_date >= ? AND u.role = ? AND u.team_lead = ?
            GROUP BY qc.outcome
        """,

        "qa_summary": f"""
            SELECT qa.outcome, COUNT(*) as count
            FROM qa_checks qa
            JOIN reviews r ON r.id = qa.review_id
            JOIN users u ON r.l{level}_assigned_to = u.id
            WHERE r.l{level}_date_completed >= ? AND u.role = ? AND u.team_lead = ?
            GROUP BY qa.outcome
        """
    }

# --- Back-compat alias for old templates that call url_for('view_task', ...) ---
@app.route("/go/view/<task_id>", endpoint="view_task")
def view_task_alias(task_id):
    """Legacy endpoint used by older templates.
    Redirects reviewers/QC/QA/SME to the editable 'review' panel,
    everyone else to the read-only 'view_task_restricted' page.
    Preserves open_level if provided.
    """
    role = (session.get("role") or "").lower()
    open_level = request.args.get("open_level")

    if role.startswith(("reviewer", "qc", "qa", "sme")):
        return redirect(url_for("review", task_id=task_id, open_level=open_level))
    return redirect(url_for("view_task_restricted", task_id=task_id, open_level=open_level))

# --- helpers ---------------------------------------------------------------
def _tl_level_and_team():
    """Return (level:int, team_lead_name:str) for the logged-in Team Lead."""
    db  = get_db()
    cur = db.cursor()
    uid = session.get("user_id")
    role = session.get("role", "")

    if not role.startswith("team_lead_"):
        db.close()
        raise RuntimeError("Not a team lead")

    lvl = int(role.split("_")[-1])
    row = cur.execute("SELECT name FROM users WHERE id = ?", (uid,)).fetchone()
    team_lead_name = row["name"] if row else "Unknown"
    db.close()
    return lvl, team_lead_name

def _parse_date_any(s):
    if not s: return None
    s = str(s).strip()
    try:
        return datetime.fromisoformat(s.replace("Z","").split(".")[0])
    except Exception:
        try:
            return parser.parse(s)
        except Exception:
            return None

def _bucket(d: Optional[datetime], today=None):
    if not today:
        today = datetime.utcnow().date()
    if not d: return "5 days+"
    days = (today - d.date()).days
    if days <= 2:  return "1–2 days"
    if days <= 5:  return "3–5 days"
    return "5 days+"

# Drilldown now supports ?date_range= and qc_checked
@app.route("/tl/cases")
@role_required('team_lead_1', 'team_lead_2', 'team_lead_3')
def tl_cases():
    level, team_lead = _tl_level_and_team()
    reviewer_id  = request.args.get("reviewer_id", "all")
    status_key   = request.args.get("status", "").strip()
    age_bucket_q = request.args.get("age_bucket", "").strip()
    date_range   = request.args.get("date_range", "wtd")  # keep consistent with TL dashboard default

    today       = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT id, name FROM users
        WHERE role = ? AND LOWER(team_lead)=LOWER(?)
        ORDER BY name
    """, (f"reviewer_{level}", team_lead))
    team_reviewers = cur.fetchall()
    r_ids = [r["id"] for r in team_reviewers] or [-1]

    assign_col  = "assigned_to"
    completed_dt= "date_completed"
    qc_chk_col  = "qc_check_date"
    qc_rew_col  = "qc_rework_required"
    qc_done_col = "qc_rework_completed"

    base = f"SELECT * FROM reviews WHERE {assign_col} IN ({','.join('?'*len(r_ids))})"
    params = r_ids.copy()
    # date filter on updated_at by default (aligns with dashboard filters)
    if date_range == "wtd":
        base += " AND date(updated_at) BETWEEN ? AND ?"
        params += [monday_this.isoformat(), today.isoformat()]
    elif date_range == "prevw":
        base += " AND date(updated_at) BETWEEN ? AND ?"
        params += [monday_prev.isoformat(), sunday_prev.isoformat()]
    elif date_range == "30d":
        base += " AND updated_at >= datetime('now','-30 days')"

    if reviewer_id.isdigit():
        base += f" AND {assign_col} = ?"
        params.append(int(reviewer_id))

    cur.execute(base + " ORDER BY updated_at DESC", params)
    rows = [dict(r) for r in cur.fetchall()]
    db.close()

    def _parse_date_any(s):
        if not s: return None
        s = str(s).strip()
        try:    return datetime.fromisoformat(s.replace("Z","").split(".")[0]).date()
        except:
            try:
                from dateutil import parser as P
                return P.parse(s).date()
            except: return None

    def _bucket(d):
        if not d: return "5 days+"
        days = (datetime.utcnow().date() - d).days
        if days <= 2: return "1–2 days"
        if days <= 5: return "3–5 days"
        return "5 days+"

    # Build the list AND point each row to the review page
    next_url = request.full_path  # so users can come back to the same filtered list
    cases = []
    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        s = (derive_case_status(r) or "").lower()

        keep = False
        if status_key == "pending":
            keep = ("pending review" in s) or (f"pending level {level} review" in s)
        elif status_key == "completed":
            keep = bool(r.get(completed_dt))  # strict completion (excludes SME states)
        elif status_key == "rework":
            keep = (r.get(qc_rew_col) and not r.get(qc_done_col))
        elif status_key == "sme_ref":
            keep = "referred to sme" in s
        elif status_key == "sme_ret":
            keep = "returned from sme" in s
        elif status_key == "qc_checked":
            keep = bool(r.get(qc_chk_col))
        elif status_key == "outreach":
            keep = ((("chaser" in s) or ("outreach cycle" in s) or ("chaser cycle" in s)) and ("overdue" not in s))
        elif status_key == "overdue":
            keep = ((("chaser" in s) or ("outreach cycle" in s) or ("chaser cycle" in s)) and ("overdue" in s))
        else:
            keep = True

        if not keep:
            continue

        if age_bucket_q:
            lt = _parse_date_any(r.get(qc_chk_col)) or _parse_date_any(r.get("updated_at"))
            if _bucket(lt) != age_bucket_q:
                continue

        cases.append({
            "task_id": r.get("task_id"),
            "customer_id": r.get("customer_id"),
            "status": derive_case_status(r),
            "updated_at": r.get("updated_at"),
            # 👉 link to REVIEW page (matches Ops dashboard behaviour)
            # If your review endpoint name/path is different, tweak below.
            "review_url": url_for("review", task_id=r.get("task_id"), next=next_url)
        })

    return render_template("404_redirect.html"), 404

@app.route('/team_leader_dashboard')
@role_required('team_lead_1', 'team_lead_2', 'team_lead_3')
def team_leader_dashboard_v2():
    # --- who am I / filters ---
    level, team_lead = _tl_level_and_team()
    date_range = request.args.get("date_range", "wtd")  # default: current week

    # week boundaries (UTC, Monday start)
    today       = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_this - timedelta(days=1)

    def _to_int(x):
        try: return int(x)
        except (TypeError, ValueError): return None

    def _within_range(dt: datetime):
        if not dt: return False
        d = dt.date()
        if date_range == "wtd":   return monday_this <= d <= today
        if date_range == "prevw": return monday_prev <= d <= sunday_prev
        if date_range == "30d":   return d >= (today - timedelta(days=30))
        return True  # "all"

    db  = get_db()
    cur = db.cursor()

    # reviewers in this TL's team
    cur.execute("""
        SELECT id, name, email
        FROM users
        WHERE role = ? AND LOWER(team_lead) = LOWER(?)
        ORDER BY name
    """, (f"reviewer_{level}", team_lead))
    reviewers = [dict(r) for r in cur.fetchall()]
    r_ids = [r["id"] for r in reviewers] or [-1]

    assign_col    = "assigned_to"
    outcome_col   = "outcome"
    completed_dt  = "date_completed"
    completed_by  = "completed_by"
    qc_chk_col    = "qc_check_date"
    qc_rew_col    = "qc_rework_required"
    qc_done_col   = "qc_rework_completed"
    sme_sel_col   = "sme_selected_date"
    sme_ret_col   = "sme_returned_date"

    # Helpers
    def _parse_dt(s):
        if not s: return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z","").split(".")[0])
        except Exception:
            try:
                from dateutil import parser as P
                return P.parse(s)
            except Exception:
                return None

    def _apply_date_clause(sql, field="updated_at"):
        if date_range == "wtd":
            return sql + f" AND date({field}) BETWEEN ? AND ?", [monday_this.isoformat(), today.isoformat()]
        if date_range == "prevw":
            return sql + f" AND date({field}) BETWEEN ? AND ?", [monday_prev.isoformat(), sunday_prev.isoformat()]
        if date_range == "30d":
            return sql + f" AND {field} >= datetime('now','-30 days')", []
        return sql, []

    # ---- rows for date-aware sections (use updated_at) ----
    params = r_ids.copy()
    sql = f"SELECT * FROM reviews WHERE {assign_col} IN ({','.join('?'*len(r_ids))})"
    sql, extras = _apply_date_clause(sql, "updated_at")
    params += extras
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]

    # ---- ALL rows for Live/WIP metrics: include team-assigned + UNASSIGNED at this level ----
    placeholders = ",".join("?"*len(r_ids))
    cur.execute(f"""
        SELECT * FROM reviews
        WHERE ({assign_col} IN ({placeholders}) OR {assign_col} IS NULL)
    """, r_ids)
    all_rows = [dict(r) for r in cur.fetchall()]

    # ---------- KPI: Completed (date-filtered on completion date) ----------
    completed_count = sum(
        1 for r in all_rows
        if (dt := _parse_dt(r.get(completed_dt))) and _within_range(dt)
    )

    # ---------- KPI: Total Active WIP (LIVE, include unassigned returns) ----------
    def _is_open(r: dict) -> bool:
        st = (derive_case_status(r) or "").lower()
        rid = r.get(assign_col)
        pending = (("pending review" in st) or (f"pending level {level} review" in st)) and (r.get(outcome_col) is None and r.get(completed_dt) is None)
        rework  = bool(r.get(qc_rew_col)) and not r.get(qc_done_col)
        sme_ref = "referred to sme" in st and not r.get(sme_ret_col)
        sme_ret = "returned from sme" in st
        # Count if it's open AND (assigned to one of my reviewers OR it's unassigned but an open state, esp. SME Return)
        belongs = (rid in r_ids)
        return belongs and (pending or rework or sme_ref or sme_ret)

    total_active_wip = sum(1 for r in all_rows if _is_open(r))

    # ---------- Rework age buckets (date-filtered set) ----------
    def _bucket(d):
        if not d: return "5 days+"
        days = (today - d.date()).days
        if days <= 2: return "1–2 days"
        if days <= 5: return "3–5 days"
        return "5 days+"

    buckets = {"1–2 days":0, "3–5 days":0, "5 days+":0}
    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        if r.get(qc_rew_col) and not r.get(qc_done_col):
            dt = _parse_dt(r.get(qc_chk_col)) or _parse_dt(r.get("updated_at"))
            buckets[_bucket(dt)] += 1

    # ---------- Individual Output (Completed within selected range) ----------
    per_member = {_to_int(rv["id"]): 0 for rv in reviewers}
    for r in all_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        dt = _parse_dt(r.get(completed_dt))
        if not dt or not _within_range(dt):
            continue
        finisher = _to_int(r.get(completed_by)) or _to_int(r.get(assign_col))
        if finisher in per_member:
            per_member[finisher] += 1

    leader_rows = [
        {"reviewer_id": rv["id"], "name": rv["name"], "completed": per_member.get(_to_int(rv["id"]), 0)}
        for rv in reviewers
    ]

    # ---------- Live WIP by reviewer (team-assigned only) ----------
    wip_stats = { rid: {"pending":0,"rework":0,"sme_ref":0,"sme_ret":0} for rid in r_ids }
    for r in all_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        rid = r.get(assign_col)
        if rid not in wip_stats:
            continue
        st = (derive_case_status(r) or "").lower()
        if (("pending review" in st) or (f"pending level {level} review" in st)) and r.get(outcome_col) is None and r.get(completed_dt) is None:
            wip_stats[rid]["pending"] += 1
        if r.get(qc_rew_col) and not r.get(qc_done_col):
            wip_stats[rid]["rework"] += 1
        if "referred to sme" in st and not r.get(sme_ret_col):
            wip_stats[rid]["sme_ref"] += 1
        if "returned from sme" in st:
            wip_stats[rid]["sme_ret"] += 1
        # --- Chaser cycle buckets ---
        if (("chaser" in st) or ("outreach cycle" in st) or ("chaser cycle" in st)):
            if "overdue" in st:
                wip_stats.setdefault(rid, {}).setdefault("overdue_chaser", 0)
                wip_stats[rid]["overdue_chaser"] += 1
            else:
                wip_stats.setdefault(rid, {}).setdefault("outreach", 0)
                wip_stats[rid]["outreach"] += 1


    wip_rows = [{
        "reviewer_id": rv["id"],
        "name": rv["name"],
        "pending": wip_stats.get(rv["id"], {}).get("pending",0),
        "sme_ref": wip_stats.get(rv["id"], {}).get("sme_ref",0),
        "sme_ret": wip_stats.get(rv["id"], {}).get("sme_ret",0),
        "rework":  wip_stats.get(rv["id"], {}).get("rework",0),
        "outreach": wip_stats.get(rv["id"], {}).get("outreach",0),
        "overdue_chaser": wip_stats.get(rv["id"], {}).get("overdue_chaser",0),

    } for rv in reviewers]

    # ---------- QC tiles (date-filtered on qc.created_at) ----------
    qc_sql = f"""
        SELECT qc.outcome
        FROM qc_checks qc
        JOIN reviews r ON r.id = qc.review_id
        WHERE (r.{assign_col} IN ({placeholders}))
    """
    qc_params = r_ids.copy()
    if date_range == "wtd":
        qc_sql += " AND date(qc.created_at) BETWEEN ? AND ?"
        qc_params += [monday_this.isoformat(), today.isoformat()]
    elif date_range == "prevw":
        qc_sql += " AND date(qc.created_at) BETWEEN ? AND ?"
        qc_params += [monday_prev.isoformat(), sunday_prev.isoformat()]
    elif date_range == "30d":
        qc_sql += " AND qc.created_at >= datetime('now','-30 days')"

    cur.execute(qc_sql, qc_params)
    qc_outcomes = [(row[0] or "").strip().lower() for row in cur.fetchall()]
    qc_sample   = len(qc_outcomes)
    qc_pass_cnt = sum(1 for o in qc_outcomes if o == "pass")
    qc_fail_cnt = qc_sample - qc_pass_cnt
    qc_pass_pct = round((qc_pass_cnt / qc_sample) * 100, 1) if qc_sample else 0.0

    # ---------- Weekly output (12 weeks, no date filter) ----------
    from collections import defaultdict
    weekly = defaultdict(int)
    for r in all_rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        dt = _parse_dt(r.get(completed_dt))
        if dt:
            y, w, _ = dt.isocalendar()
            weekly[(y, w)] += 1
    labels, counts = [], []
    start = today - timedelta(days=today.weekday(), weeks=11)
    cur_day = start
    for _ in range(12):
        y, w, _ = cur_day.isocalendar()
        labels.append(cur_day.strftime("%d %b"))
        counts.append(weekly.get((y, w), 0))
        cur_day += timedelta(weeks=1)

    db.close()

    return render_template("404_redirect.html"), 404

@app.route("/admin/permissions", methods=["GET", "POST"])
def permissions_editor():
    if session.get('role') != 'admin':
        return "Access denied", 403

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("DELETE FROM permissions")  # reset

        roles = request.form.getlist("role")
        features = request.form.getlist("feature")

        for i in range(len(roles)):
            role = roles[i]
            feature = features[i]
            can_view = 1 if request.form.get(f"view_{i}") else 0
            can_edit = 1 if request.form.get(f"edit_{i}") else 0

            cur.execute("""
                INSERT INTO permissions (role, feature, can_view, can_edit)
                VALUES (?, ?, ?, ?)
            """, (role, feature, can_view, can_edit))

        conn.commit()
        flash("Permissions updated successfully.", "success")

    cur.execute("SELECT * FROM permissions ORDER BY role, feature")
    permissions = cur.fetchall()
    conn.close()

    return render_template("404_redirect.html"), 404

@app.template_filter('to_datetime')
def to_datetime_filter(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S") if value else None

@app.route("/operations_dashboard")
def operations_dashboard():
    return mi_dashboard()

@app.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return "Access denied", 403

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("User deleted successfully.", "success")
    return redirect(url_for("list_users"))

@app.route("/admin/login_audit")
def login_audit():
    if session.get("role") != "admin":
        return "Access denied", 403

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT
            l.login_time,
            l.ip_address,
            u.email,
            u.role
        FROM login_audit l
        LEFT JOIN users u ON l.user_id = u.id
        ORDER BY l.login_time DESC
        LIMIT 100
    """)
    entries = cur.fetchall()
    conn.close()

    return render_template("404_redirect.html"), 404

@app.route('/search')
def search():
    from utils import derive_case_status

    query = request.args.get('query', '').strip()
    role = session.get("role", "")
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Determine level from role (e.g., reviewer_1 → level 1)
    if role.startswith("reviewer_"):
        level = role.split("_")[-1]
    elif role.startswith("team_lead_"):
        level = role.split("_")[-1]
    else:
        level = "1"  # fallback

    assigned_col = "assigned_to"

    cursor.execute("""
        SELECT * FROM reviews
        WHERE task_id LIKE ?
           OR customer_id LIKE ?
           OR watchlist_id LIKE ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))

    rows = cursor.fetchall()
    results = []

    for row in rows:
        row_dict = dict(row)
        case_status = derive_case_status(row_dict)

        results.append({
            'task_id': row_dict['task_id'],
            'customer_name': row_dict['customer_id'],
            'watchlist_name': row_dict['watchlist_id'],
            'status': case_status,
            'reviewer_email': row_dict.get(assigned_col) or 'Unassigned',
            'review_timestamp': row_dict.get('review_timestamp')
        })

    return render_template("404_redirect.html"), 404

@csrf.exempt
@app.route('/api/search', methods=['GET'])
def api_search():
    """Search tasks with role-based filtering"""
    try:
        from utils import derive_case_status
        
        user_id = session.get("user_id")
        role = session.get("role", "").lower()
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        query = request.args.get('query', '').strip()
        search_type = request.args.get('type', 'all').strip().lower()
        
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build search query based on search type
        search_conditions = []
        search_params = []
        
        if search_type == 'task_id' or search_type == 'all':
            search_conditions.append("task_id LIKE ?")
            search_params.append(f"%{query}%")
        
        if search_type == 'customer_id' or search_type == 'all':
            search_conditions.append("customer_id LIKE ?")
            search_params.append(f"%{query}%")
        
        if search_type == 'watchlist_id' or search_type == 'all':
            search_conditions.append("watchlist_id LIKE ?")
            search_params.append(f"%{query}%")
        
        if not search_conditions:
            return jsonify({'error': 'Invalid search type'}), 400
        
        # Build WHERE clause
        where_clause = " OR ".join(search_conditions)
        
        # Determine role-based filtering
        user_id_int = int(user_id)
        role_filter = ""
        role_params = []
        
        # Reviewers: only their assigned tasks
        if role.startswith('reviewer_'):
            role_filter = " AND assigned_to = ?"
            role_params.append(user_id_int)
        # QC Reviewers: only their QC assigned tasks
        elif role.startswith('qc_review_'):
            role_filter = " AND qc_assigned_to = ?"
            role_params.append(user_id_int)
        # QC Leads: only their QC assigned tasks (qc_1, qc_2, qc_3, qc_lead_*)
        elif role.startswith('qc_') or role in ('qc_1', 'qc_2', 'qc_3'):
            role_filter = " AND qc_assigned_to = ?"
            role_params.append(user_id_int)
        # Operations Manager, Team Leads, Admin: can see all tasks (no filter)
        elif role in ('operations_manager', 'admin') or role.startswith('team_lead_'):
            role_filter = ""  # No restriction
        # Default: restrict to assigned tasks
        else:
            role_filter = " AND assigned_to = ?"
            role_params.append(user_id_int)
        
        # Execute search
        if role_filter:
            sql = f"""
                SELECT * FROM reviews
                WHERE ({where_clause})
                {role_filter}
                ORDER BY updated_at DESC
                LIMIT 500
            """
            all_params = search_params + role_params
        else:
            sql = f"""
                SELECT * FROM reviews
                WHERE ({where_clause})
                ORDER BY updated_at DESC
                LIMIT 500
            """
            all_params = search_params
        
        cursor.execute(sql, all_params)
        rows = cursor.fetchall()
        
        # Format results
        results = []
        for row in rows:
            row_dict = dict(row)
            case_status = derive_case_status(row_dict)
            
            # Get reviewer name if assigned
            reviewer_name = None
            if row_dict.get('assigned_to'):
                cursor.execute("SELECT name FROM users WHERE id = ?", (row_dict['assigned_to'],))
                reviewer = cursor.fetchone()
                if reviewer:
                    reviewer_name = reviewer['name']
            
            results.append({
                'task_id': row_dict.get('task_id', ''),
                'customer_id': row_dict.get('customer_id', ''),
                'watchlist_id': row_dict.get('watchlist_id', ''),
                'status': case_status,
                'assigned_to': reviewer_name or 'Unassigned',
                'updated_at': row_dict.get('updated_at', ''),
                'hit_type': row_dict.get('hit_type', ''),
                'total_score': row_dict.get('total_score', '')
            })
        
        conn.close()
        return jsonify({'success': True, 'results': results, 'count': len(results)})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/ops/mi/cases')
@role_required("operations_manager", "admin")
def ops_mi_cases():
    # Outcome filter normalisation
    _outcome = request.args.get('outcome', '').strip()
    # filters from querystring
    status         = request.args.get("status", "").strip()
    l1_outcome_arg = (request.args.get('l1_outcome') or '').strip()
    outcome_arg = (request.args.get('outcome') or '').strip()
    decision_outcome_arg = (request.args.get('decision_outcome') or '').strip()
    chosen_outcome = l1_outcome_arg or decision_outcome_arg or outcome_arg
    # Normalize legacy/short labels to canonical values for filtering
    if status == 'IRC - Awaiting Outreach':
        status = 'Initial Review Complete - Awaiting Outreach'
    age_bucket_q   = request.args.get("age_bucket", "").strip()  # optional
    date_range     = request.args.get("date_range", "all")
    selected_team  = request.args.get("team", "all")
    selected_level = request.args.get("level", "all")

    # Chaser drill-through params
    chaser_type = request.args.get("chaser_type", "").strip()  # '7','14','21','28','NTC'
    week_date   = request.args.get("week_date", "").strip()    # 'YYYY-MM-DD'
    overdue_flg = request.args.get("overdue", "").strip()      # '1' to indicate overdue
    drilling_from_chaser = bool(chaser_type or overdue_flg or week_date)


    def _status_matches(derived_label: str, requested: str) -> bool:
        dl = (derived_label or "").strip().lower()
        rq = (requested or "").strip().lower()
        if not rq:
            return True
        # Canonical groupings to mirror dashboard
        if rq == "outreach":
            return ("outreach" in dl) and ("awaiting outreach" not in dl)
        if rq == "initial review complete - awaiting outreach":
            return ("initial review complete" in dl) and ("awaiting outreach" in dl)
        # Fallback exact match
        return dl == rq

    # reuse the same filtered dataset logic as /ops/mi
    today        = datetime.utcnow().date()
    monday_this  = today - timedelta(days=today.weekday())
    monday_prev  = monday_this - timedelta(days=7)
    sunday_prev  = monday_this - timedelta(days=1)

    db  = get_db()
    cur = db.cursor()

    base_sql = """
      SELECT r.*
        FROM reviews r
   LEFT JOIN users u ON u.id = r.assigned_to
       WHERE 1=1
    """
    params = []
    if (selected_team != "all") and (not drilling_from_chaser):
        base_sql += " AND u.team_lead = ?"
        params.append(selected_team)
    if (not (request.args.get("chaser_type") or request.args.get("overdue") or request.args.get("week_date"))) and date_range == "wtd":
        base_sql += " AND date(r.updated_at) BETWEEN ? AND ?"
        params += [monday_this.isoformat(), today.isoformat()]
    elif (not (request.args.get("chaser_type") or request.args.get("overdue") or request.args.get("week_date"))) and date_range == "prevw":
        base_sql += " AND date(r.updated_at) BETWEEN ? AND ?"
        params += [monday_prev.isoformat(), sunday_prev.isoformat()]
    elif (not (request.args.get("chaser_type") or request.args.get("overdue") or request.args.get("week_date"))) and date_range == "30d":
        base_sql += " AND r.updated_at >= datetime('now','-30 days')"

    try:
        cur.execute(base_sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        rows = []

    # --- Global filters from querystring ---
    qc_param = (request.args.get("qc") or "").strip().lower()
    def _has_qc(rec):
        return bool(rec.get("l1_qc_check_date") or rec.get("l2_qc_check_date") or rec.get("l3_qc_check_date"))
    if _outcome:
        rows = [r for r in rows if str((r.get('outcome') or r.get('final_outcome') or '')).strip().lower() == _outcome.lower()]
    if qc_param in ("1", "yes", "true", "has_qc", "qc"):
        rows = [r for r in rows if _has_qc(r)]
    

    db.close()

    # --- Chaser filtering (optional, applied after base dataset) ---
    if drilling_from_chaser:
        def _coalesce_key(d, names):
            lower = {k.lower(): k for k in d.keys()}
            for name in names:
                n = name.lower()
                if n in lower: return lower[n]
            return None

        def _parse_date_any(s):
            if not s: return None
            s = str(s).strip()
            for _fmt in ("%Y-%m-%d","%Y/%m/%d","%d/%m/%Y","%d-%m-%Y","%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(s, _fmt).date()
                except Exception:
                    pass
            try:
                return parser.parse(s).date()
            except Exception:
                return None

        def _is_blank_issued(v):
            if v is None: return True
            s = str(v).strip().lower()
            return s in ("", "none", "null", "n/a", "na", "-", "0", "false")
        
        def _is_chaser_issued(rec, chaser_type):
            """Check if a chaser type has been issued"""
            issued_key = _coalesce_key(rec, ISSUED_MAP.get(chaser_type, []))
            if issued_key:
                return not _is_blank_issued(rec.get(issued_key))
            return False

        DUE_MAP = {
            "7":  ["Chaser1DueDate","Chaser_1_DueDate","chaser1_due","Outreach1DueDate"],
            "14": ["Chaser2DueDate","Chaser_2_DueDate","chaser2_due","Outreach2DueDate"],
            "21": ["Chaser3DueDate","Chaser_3_DueDate","chaser3_due","Outreach3DueDate"],
            "28": ["Chaser4DueDate","Chaser_4_DueDate","chaser4_due","Outreach4DueDate"],
            "NTC": ["NTCDueDate","NTC_DueDate","ntc_due"]
        }
        ISSUED_MAP = {
            "7":  ["Chaser1IssuedDate","Chaser1DateIssued","chaser1_issued"],
            "14": ["Chaser2IssuedDate","Chaser2DateIssued","chaser2_issued"],
            "21": ["Chaser3IssuedDate","Chaser3DateIssued","chaser3_issued"],
            "28": ["Chaser4IssuedDate","Chaser4DateIssued","chaser4_issued"],
            "NTC": ["NTCIssuedDate","NTC_IssuedDate","ntc_issued"]
        }

        iso = week_date
        today = datetime.utcnow().date()
        filtered = []
        for r in rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            
            # Skip if outreach is completed
            outreach_complete = r.get('outreach_complete') or r.get('OutreachComplete')
            if outreach_complete in (1, '1', True, 'true', 'True'):
                continue
            
            # Check chasers sequentially: 7 → 14 → 21 → NTC
            # Only show the NEXT chaser that needs to be issued
            chaser_sequence = ["7", "14", "21", "NTC"]
            next_chaser_type = None
            next_chaser_due_date = None
            
            # First, find the NEXT unissued chaser for this task
            for typ in chaser_sequence:
                # Check if all previous chasers have been issued
                if typ == "7":
                    prev_issued = True
                elif typ == "14":
                    prev_issued = _is_chaser_issued(r, "7")
                elif typ == "21":
                    prev_issued = _is_chaser_issued(r, "7") and _is_chaser_issued(r, "14")
                elif typ == "NTC":
                    prev_issued = _is_chaser_issued(r, "7") and _is_chaser_issued(r, "14") and _is_chaser_issued(r, "21")
                else:
                    prev_issued = False
                
                if not prev_issued:
                    continue
                
                if _is_chaser_issued(r, typ):
                    continue
                
                due_key = _coalesce_key(r, DUE_MAP.get(typ, []))
                if not due_key:
                    continue
                due_date = _parse_date_any(r.get(due_key))
                if not due_date:
                    continue
                
                next_chaser_type = typ
                next_chaser_due_date = due_date
                break
            
            if not next_chaser_type:
                continue
            
            # Check if this next chaser matches the filter criteria
            matched = False
            
            if overdue_flg == "1":
                # If chaser_type is specified with overdue, must match exactly
                if chaser_type:
                    if next_chaser_type != chaser_type:
                        continue
                # Must be overdue
                if next_chaser_due_date < today:
                    matched = True
            elif chaser_type:
                # Must match the specified chaser_type
                if next_chaser_type != chaser_type:
                    continue
                # If week_date (iso) is provided, must match that exact date
                if iso:
                    if next_chaser_due_date.isoformat() == iso:
                        matched = True
                else:
                    # No date filter, show if overdue
                    if next_chaser_due_date < today:
                        matched = True
            
            if matched:
                filtered.append(r)
        rows = filtered


        DUE_MAP = {
            "7":  ["Chaser1DueDate","Chaser_1_DueDate","chaser1_due","Outreach1DueDate"],
            "14": ["Chaser2DueDate","Chaser_2_DueDate","chaser2_due","Outreach2DueDate"],
            "21": ["Chaser3DueDate","Chaser_3_DueDate","chaser3_due","Outreach3DueDate"],
            "28": ["Chaser4DueDate","Chaser_4_DueDate","chaser4_due","Outreach4DueDate"],
            "NTC": ["NTCDueDate","NTC_DueDate","ntc_due"]
        }
        ISSUED_MAP = {
            "7":  ["Chaser1IssuedDate","Chaser1DateIssued","chaser1_issued"],
            "14": ["Chaser2IssuedDate","Chaser2DateIssued","chaser2_issued"],
            "21": ["Chaser3IssuedDate","Chaser3DateIssued","chaser3_issued"],
            "28": ["Chaser4IssuedDate","Chaser4DateIssued","chaser4_issued"],
            "NTC": ["NTCIssuedDate","NTC_IssuedDate","ntc_issued"]
        }
        iso = week_date
        today = datetime.utcnow().date()
        filtered = []
        for r in rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            due_key    = _coalesce_key(r, DUE_MAP.get(chaser_type, []))
            issued_key = _coalesce_key(r, ISSUED_MAP.get(chaser_type, []))
            due_date   = _parse_date_any(r.get(due_key)) if due_key else None
            not_issued = _is_blank_issued(r.get(issued_key) if issued_key else None)
            if not (due_date and not_issued):
                continue
            if overdue_flg == "1":
                if due_date < today:
                    filtered.append(r)
            else:
                if iso and due_date.isoformat() == iso:
                    filtered.append(r)
        rows = filtered


    # --- helpers (use dateutil.parser as `parser`) ---
    def _parse_date_any(s):
        if not s:
            return None
        s = str(s).strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "").split(".")[0]).date()
        except Exception:
            try:
                return parser.parse(s).date()
            except Exception:
                return None

    def last_touched_date(r: dict):
        candidates = [
            _parse_date_any(r.get("updated_at")),
            _parse_date_any(r.get("date_assigned")), _parse_date_any(r.get("date_completed")),
            _parse_date_any(r.get("date_assigned")), _parse_date_any(r.get("date_completed")),
            _parse_date_any(r.get("date_assigned")), _parse_date_any(r.get("date_completed")),
            _parse_date_any(r.get("qc_check_date")), _parse_date_any(r.get("qc_check_date")), _parse_date_any(r.get("qc_check_date")),
            _parse_date_any(r.get("sme_selected_date")), _parse_date_any(r.get("sme_returned_date")),
            _parse_date_any(r.get("sme_selected_date")), _parse_date_any(r.get("sme_returned_date")),
            _parse_date_any(r.get("sme_selected_date")), _parse_date_any(r.get("sme_returned_date")),
        ]
        vals = [d for d in candidates if d]
        return max(vals) if vals else None

    def bucket(d):
        if not d:
            return "5 days+"
        days = (datetime.utcnow().date() - d).days
        if days <= 2:  return "1–2 days"
        if days <= 5:  return "3–5 days"
        return "5 days+"

    def best_open_level(r: dict) -> int:
        # Prefer the next level if escalated but not yet completed there
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"):
            return 2
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"):
            return 3
        # Otherwise open the highest level that has activity
        for lvl in (3, 2, 1):
            if r.get(f"l{lvl}_assigned_to") or r.get(f"l{lvl}_outcome"):
                return lvl
        return 1

    # derive + filter
    cases = []
    ## BEGIN_OUTCOME_FILTER
    # Robust filter for Outcome click-through (L1 outcome)
    if 'chosen_outcome' in locals() and chosen_outcome:
        try:
            _rows = g.db.execute('SELECT DISTINCT task_id FROM reviews WHERE l1_outcome = ?', (chosen_outcome,)).fetchall()
            _match_ids = set([r[0] for r in _rows])
        except Exception:
            _match_ids = set()
        def _get_case_id(_c):
            if isinstance(_c, dict):
                return _c.get('task_id') or _c.get('id') or _c.get('case_id')
            return getattr(_c, 'task_id', None) or getattr(_c, 'id', None) or getattr(_c, 'case_id', None)
        if _match_ids:
            cases = [c for c in cases if _get_case_id(c) in _match_ids]
    ## END_OUTCOME_FILTER
    # Filter by l1_outcome if requested
    if chosen_outcome:
        # Build a set of matching task_ids from reviews
        _task_ids = []
        for _c in cases:
            try:
                _task_ids.append(_c.get('task_id'))
            except AttributeError:
                _task_ids.append(getattr(_c, 'task_id', None))
        _task_ids = [tid for tid in _task_ids if tid]
        _match_ids = set()
        if _task_ids:
            _ph = ','.join(['?'] * len(_task_ids))
            _q = 'SELECT DISTINCT task_id FROM reviews WHERE l1_outcome = ? AND task_id IN (' + _ph + ')'
            _params = [chosen_outcome] + _task_ids
            try:
                _rows = g.db.execute(_q, _params).fetchall()
            except Exception:
                _rows = []
            _match_ids = set([r[0] for r in _rows])
        cases = [c for c in cases if ((getattr(c, 'task_id', None) if not isinstance(c, dict) else c.get('task_id')) in _match_ids)]
    for r in rows:
        # Outcome filter (if provided)
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue

        # Derived status (used for display)
        # Fix mismatch: if assigned_to is set but status says "Unassigned", derive correct status
        raw_status = r.get('status', '')
        assigned_to = r.get('assigned_to')
        
        # Preserve "Referred to AI SME" status
        if raw_status and 'referred to ai sme' in raw_status.lower():
            s = raw_status  # Keep the manually set AI SME status
        elif assigned_to and raw_status and raw_status.lower() == 'unassigned':
            # Task is assigned but status is wrong - derive correct status
            s = str(derive_case_status(r)) or "(Unclassified)"
        else:
            # Use best_status_with_raw_override to respect manually set statuses
            from utils import best_status_with_raw_override
            s = str(best_status_with_raw_override(r)) or "(Unclassified)"
        
        # Debug logging for AI SME referrals when filtering by "Referred to SME"
        if status and status.strip().lower() == 'referred to sme' and raw_status and 'referred to ai sme' in raw_status.lower():
            print(f"[DEBUG ops_mi_cases] Task {r.get('task_id')}: raw_status='{raw_status}', derived s='{s}'")

        # Exact status filter unless drilling from chaser
        # Use the derived status 's' for filtering, not the raw status
        # Special handling: "Referred to SME" should match both "Referred to SME" and "Referred to AI SME"
        if status and not drilling_from_chaser:
            status_lower = status.strip().lower()
            s_lower = s.strip().lower()
            
            # If filtering by "Referred to SME", include both manual and AI SME referrals
            if status_lower == 'referred to sme':
                # Match both "Referred to SME" and "Referred to AI SME"
                # Check both the derived status 's' and the raw status
                raw_status_lower = raw_status.strip().lower() if raw_status else ''
                
                # Explicitly check for both "Referred to SME" and "Referred to AI SME"
                # This will match:
                # - "Referred to SME" (manual referral)
                # - "Referred to AI SME" (AI referral)
                # - Any variation with different casing
                is_sme_referred = (
                    s_lower == 'referred to sme' or 
                    s_lower == 'referred to ai sme' or
                    ('referred to' in s_lower and 'sme' in s_lower)
                )
                is_raw_sme_referred = (
                    raw_status_lower == 'referred to sme' or
                    raw_status_lower == 'referred to ai sme' or
                    ('referred to' in raw_status_lower and 'sme' in raw_status_lower)
                )
                
                matches = is_sme_referred or is_raw_sme_referred
                
                # Debug logging for AI SME referrals
                if r.get('task_id') and ('ai sme' in s_lower or 'ai sme' in raw_status_lower):
                    print(f"[DEBUG ops_mi_cases] Task {r.get('task_id')}: status_lower='{status_lower}', s='{s}', s_lower='{s_lower}', raw_status='{raw_status}', raw_status_lower='{raw_status_lower}'")
                    print(f"[DEBUG ops_mi_cases] Task {r.get('task_id')}: is_sme_referred={is_sme_referred}, is_raw_sme_referred={is_raw_sme_referred}, matches={matches}")
                
                if not matches:
                    continue
            # Otherwise, exact match
            elif s_lower != status_lower:
                continue

        # >>> Outreach strict filter: require raw DB status contains 'Outreach' and exclude 'Awaiting Outreach' and 'Outreach Complete'
        if (status or '').strip().lower() == 'outreach':
            raw_stat = (r.get('status') or '').strip().lower()
            if ('outreach' not in raw_stat) or ('awaiting outreach' in raw_stat) or ('outreach complete' in raw_stat):
                continue
        # <<< end outreach filter >>>
        
        # >>> Outreach Complete filter: match exactly
        if (status or '').strip().lower() == 'outreach complete':
            raw_stat = (r.get('status') or '').strip().lower()
            s_lower_check = s.strip().lower()
            if 'outreach complete' not in raw_stat and 'outreach complete' not in s_lower_check:
                continue
        # <<< end outreach complete filter >>>

        # Keep L2/L3 Unassigned/Pending visible: scope by prior-level PTM
        if selected_level == "2":
            if r.get("outcome") != "Potential True Match":
                continue
        elif selected_level == "3":
            if r.get("outcome") != "Potential True Match":
                continue
        # if "1" or "all": no extra filter

        # Age bucket filter
        if age_bucket_q and bucket(last_touched_date(r)) != age_bucket_q:
            continue

        lt = last_touched_date(r)
        cases.append({
            "task_id": r.get("task_id"),
            "customer_id": r.get("customer_id"),
            "status": s,
            "last_touched": lt.isoformat() if lt else "",
            "updated_at": r.get("updated_at"),
            "open_level": best_open_level(r),     # used by template links
        })

    # sort newest first by last_touched / updated_at
    cases.sort(key=lambda x: (x["last_touched"] or x["updated_at"] or ""), reverse=True)

    return render_template("404_redirect.html"), 404

@app.route("/reassign_tasks", methods=["GET", "POST"])
@role_required("team_lead_1", "team_lead_2", "team_lead_3")
def reassign_tasks():
    user_id = session.get("user_id")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    # Identify TL + level
    tl = cur.execute("SELECT name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not tl:
        conn.close()
        return "Unable to identify team lead.", 400

    lead_name = tl["name"]
    tl_str = tl["role"].split("_")[-1]
    level = tl_str if tl_str in ("1","2","3") else request.args.get("level", "1")
    if level not in ("1","2","3"):
        level = "1"
    assign_col      = "assigned_to"
    outcome_col     = "outcome"
    completed_col   = "date_completed"
    date_assigned_col = "date_assigned"

    # Load this TL's reviewers
    cur.execute("""
        SELECT id, name, role
          FROM users
         WHERE role = ? AND LOWER(team_lead) = LOWER(?)
         ORDER BY name
    """, (f"reviewer_{level}", lead_name))
    reviewers = cur.fetchall()
    reviewer_ids = [r["id"] for r in reviewers]

    if request.method == "POST":
        target_reviewer_id = request.form.get("target_reviewer_id", type=int)
        selected_task_ids  = request.form.getlist("task_ids", type=int)

        if not selected_task_ids or not target_reviewer_id:
            flash("Please select task(s) and a target reviewer.", "warning")
            conn.close()
            return redirect(url_for("reassign_tasks"))

        if target_reviewer_id not in reviewer_ids:
            flash("Target reviewer must be in your team.", "danger")
            conn.close()
            return redirect(url_for("reassign_tasks"))

        moved = 0
        for rid in selected_task_ids:
            # Validate task is currently assigned to someone in your team and not completed
            row = cur.execute(f"""
                SELECT id, task_id, {assign_col} AS current_assignee, {outcome_col} AS outcome
                  FROM reviews
                 WHERE id = ?
            """, (rid,)).fetchone()
            if not row:
                continue
            if row["current_assignee"] not in reviewer_ids:
                continue
            if row["current_assignee"] == target_reviewer_id:
                continue
            if row["outcome"] is not None:
                # already completed at this level
                continue

            # Reassign
            now_iso = datetime.utcnow().isoformat()
            cur.execute(f"""
                UPDATE reviews
                   SET {assign_col} = ?, {date_assigned_col} = ?, updated_at = ?
                 WHERE id = ?
            """, (target_reviewer_id, now_iso, now_iso, rid))

            # Re-derive canonical status
            cur.execute("SELECT * FROM reviews WHERE id = ?", (rid,))
            rev = dict(cur.fetchone())
            new_status = derive_status(rev, rev.get("current_level") or int(level))
            cur.execute("UPDATE reviews SET status = ? WHERE id = ?", (new_status, rid))
            moved += 1

        conn.commit()
        conn.close()
        flash(f"Reassigned {moved} task(s).", "success")
        return redirect(url_for("reassign_tasks"))

    # GET: Optional filter to narrow by current reviewer
    from_reviewer = request.args.get("from_reviewer", "all")
    params = []
    base = f"""
        SELECT r.*, u.name AS current_reviewer_name
          FROM reviews r
          JOIN users u ON u.id = r.{assign_col}
         WHERE r.{assign_col} IS NOT NULL
           AND r.{assign_col} IN ({','.join('?' for _ in reviewer_ids)})  -- only your team
           AND r.{outcome_col} IS NULL                                    -- not completed yet
    """
    params.extend(reviewer_ids)

    if from_reviewer.isdigit():
        base += f" AND r.{assign_col} = ?"
        params.append(int(from_reviewer))

    base += " ORDER BY r.updated_at DESC LIMIT 1000"
    cur.execute(base, params)
    rows = cur.fetchall()

    # Build task list with live status for display
    tasks = []
    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        rec = dict(r)
        rec["status"] = derive_case_status(rec)
        rec["current_reviewer_id"] = rec.get(assign_col)
        tasks.append(rec)


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

from utils import derive_case_status

@app.route("/view_task/<task_id>")
@role_required(
    "admin",
    "team_lead_1", "team_lead_2", "team_lead_3",
    "reviewer_1", "reviewer_2", "reviewer_3",
    "qc", "qa", "sme", "operations_manager"
)
def view_task_restricted(task_id):
    conn = get_db()
    cursor = conn.cursor()

    # 1) Load the review record
    cursor.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return "Task not found", 404
    review = dict(row)

    # 2) Load any match data
    cursor.execute("SELECT * FROM matches WHERE task_id = ?", (task_id,))
    match_row = cursor.fetchone()
    match = dict(match_row) if match_row else {}

    # merge handy read-only fields
    review.update(match)

    # 3) Re-derive the up-to-date status for this case
    status = derive_case_status(review)

    # 4) Decide which level we’re conceptually looking at (for “assigned to” label)
    q_level = request.args.get("open_level")
    try:
        q_level = int(q_level) if q_level is not None else None
    except Exception:
        q_level = None

    def best_open_level(r: dict) -> int:
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"):
            return 2
        if r.get("outcome") == "Potential True Match" and not r.get("outcome"):
            return 3
        for lv in (3, 2, 1):
            if r.get(f"l{lv}_assigned_to") or r.get(f"l{lv}_outcome"):
                return lv
        return 1

    level = q_level or best_open_level(review)

    # 5) Resolve assigned reviewer display for that level (prefer QC assignee)
    assigned_to_id = (
        review.get("qc_assigned_to") or
        review.get("assigned_to")
    )
    assigned_to_name = None
    if assigned_to_id:
        cursor.execute("SELECT name FROM users WHERE id = ?", (assigned_to_id,))
        u = cursor.fetchone()
        assigned_to_name = u["name"] if u else None

    # 6) Hit type helper for the template
    hit_type = match.get("hit_type", "").lower()

    # 7) Provide a local score_class helper if one isn’t globally available
    def _score_class(score):
        try:
            s = float(score)
        except Exception:
            return "text-secondary"
        if s >= 90:
            return "text-danger"
        if s >= 70:
            return "text-warning"
        return "text-success"


    # Build outcomes for dropdown (admin-editable)
    try:
        _outcome_names = _load_outcomes_from_db(cursor)
    except Exception:
        _outcome_names = ["Retain","Exit - Financial Crime","Exit - Non-responsive","Exit - T&C"]
    outcomes = [{"name": n} for n in _outcome_names]

    conn.close()
    return render_template("404_redirect.html"), 404

@app.route("/qa_dashboard")
def qa_dashboard():
    from utils import derive_case_status

    if session.get('role') != 'qa':
        return "Access denied", 403

    # 1) Load all reviews with their QA check data
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT
          r.id          AS review_id,
          r.task_id,
          r.updated_at  AS review_updated_at,
          q.outcome     AS qa_outcome,
          q.comment     AS qa_comment,
          q.updated_at  AS qa_checked_at
        FROM reviews r
        LEFT JOIN qa_checks q ON r.id = q.review_id
        ORDER BY r.updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    # 2) Derive up-to-date status and filter for Completed
    entries = []
    for row in rows:
        record = dict(row)
        status = derive_case_status(record)
        if status == "Completed":
            record["status"] = status
            entries.append(record)

    return render_template("404_redirect.html"), 404

@app.route('/api/qa_dashboard', methods=['GET'])
def api_qa_dashboard():
    """Return QA dashboard data as JSON"""
    from utils import derive_case_status
    
    role = session.get('role', '').lower()
    if not role or not (role == 'qa' or role.startswith('qa_')):
        return jsonify({'error': 'Access denied. QA role required.'}), 403
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT
              r.id          AS review_id,
              r.task_id,
              r.updated_at  AS review_updated_at,
              q.outcome     AS qa_outcome,
              q.comment     AS qa_comment,
              q.updated_at  AS qa_checked_at
            FROM reviews r
            LEFT JOIN qa_checks q ON r.id = q.review_id
            ORDER BY r.updated_at DESC
        """)
        rows = cur.fetchall()
        conn.close()

        entries = []
        for row in rows:
            record = dict(row)
            status = derive_case_status(record)
            if status == "Completed":
                record["status"] = status
                entries.append({
                    'task_id': record.get('task_id'),
                    'status': status,
                    'qa_outcome': record.get('qa_outcome'),
                    'qa_comment': record.get('qa_comment'),
                    'updated_at': record.get('qa_checked_at') or record.get('review_updated_at')
                })

        return jsonify({'entries': entries})
    except Exception as e:
        import traceback
        print(f"Error in api_qa_dashboard: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route("/admin/debug_statuses")
@role_required("admin")
def debug_statuses():
    from utils import derive_case_status
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM reviews LIMIT 1000")
    rows = cur.fetchall()
    conn.close()

    statuses = {}
    missing = []

    for r in rows:
        if _outcome:
            ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
            if ro.lower() != _outcome.lower():
                continue
            if ro.lower() != _outcome.lower():
                continue
        record = dict(r)
        try:
            status = derive_case_status(record)
            if not status:
                missing.append(record["task_id"])
                continue
            statuses[status] = statuses.get(status, 0) + 1
        except Exception as e:
            print(f"[ERROR] derive_case_status failed for task_id={record.get('task_id')}: {e}")
            missing.append(record.get("task_id"))

    output = {
        "total_records": len(rows),
        "status_counts": statuses,
        "missing_or_error": missing
    }

    return output


# === Reviewer Chaser Cycle Helpers ===
def build_chaser_cycle_for_reviewer(db, reviewer_id:int, level:int, selected_date:str):
    headers, keys = _week_header_keys(selected_date or 'wtd')
    column_map = OrderedDict([
        ('Outreach Cycle 1', ['outreach1_chaser_due', 'outreach_cycle_1_due', 'outreach1_due']),
        ('Outreach Cycle 2', ['outreach2_chaser_due', 'outreach_cycle_2_due', 'outreach2_due']),
        ('Chaser 1',         ['chaser1_due', 'chaser_1_due']),
        ('Chaser 2',         ['chaser2_due', 'chaser_2_due']),
        ('Chaser 3',         ['chaser3_due', 'chaser_3_due']),
    ])
    cur = db.execute("PRAGMA table_info(reviews)")
    cols = {r[1] for r in cur.fetchall()}

    def pick_col(cands):
        for c in cands:
            if c in cols:
                return c
        return None

    picked = {label: pick_col(cands) for label, cands in column_map.items()}
    picked = {label: col for label, col in picked.items() if col}

    assign_col = "assigned_to"
    result = OrderedDict()

    for label, col in picked.items():
        buckets = {k: 0 for k in keys}

        # Overdue
        q_overdue = f"""
            SELECT COUNT(*) FROM reviews
            WHERE {assign_col} = ?
              AND {col} IS NOT NULL
              AND date({col}) < date('now')
        """
        buckets['overdue'] = db.execute(q_overdue, (reviewer_id,)).fetchone()[0]

        # Weekday buckets
        for k in keys[1:]:
            q_day = f"""
                SELECT COUNT(*) FROM reviews
                WHERE {assign_col} = ?
                  AND {col} IS NOT NULL
                  AND date({col}) = date(?)
            """
            buckets[k] = db.execute(q_day, (reviewer_id, k)).fetchone()[0]

        result[label] = buckets

    return result, headers, keys



def _week_header_keys(selected_date: str):
    """Ops MI headers but drop past days for current week."""
    today = datetime.utcnow().date()
    monday_this = today - timedelta(days=today.weekday())
    if selected_date == 'prevw':
        ref = monday_this - timedelta(days=7)
        days = [ref + timedelta(d) for d in range(5)]
    else:
        ref = monday_this
        days = [d for d in (ref + timedelta(x) for x in range(5)) if d >= today]
    return (['Overdue'] + [d.strftime('%d/%m/%Y') for d in days],
            ['overdue']   + [d.strftime('%Y-%m-%d') for d in days])

def build_chaser_cycle_for_reviewer(db, reviewer_id:int, level:int, selected_date:str):
    headers, keys = _week_header_keys(selected_date or 'wtd')
    column_map = OrderedDict([
        ('Outreach Cycle 1', ['outreach1_chaser_due', 'outreach_cycle_1_due', 'outreach1_due']),
        ('Outreach Cycle 2', ['outreach2_chaser_due', 'outreach_cycle_2_due', 'outreach2_due']),
        ('Chaser 1',         ['chaser1_due', 'chaser_1_due']),
        ('Chaser 2',         ['chaser2_due', 'chaser_2_due']),
        ('Chaser 3',         ['chaser3_due', 'chaser_3_due']),
    ])
    cur = db.execute("PRAGMA table_info(reviews)")
    cols = {r[1] for r in cur.fetchall()}
    def pick(cands):
        for c in cands:
            if c in cols: return c
        return None
    picked = {label: pick(cands) for label, cands in column_map.items()}
    picked = {label: col for label, col in picked.items() if col}

    assign_col = "assigned_to"
    result = OrderedDict()
    for label, col in picked.items():
        buckets = {k: 0 for k in keys}
        # Overdue
        q_o = f"""SELECT COUNT(*) FROM reviews
                     WHERE {assign_col}=? AND {col} IS NOT NULL AND date({col}) < date('now')"""
        buckets['overdue'] = db.execute(q_o, (reviewer_id,)).fetchone()[0]
        # Per day
        for k in keys[1:]:
            q_d = f"""SELECT COUNT(*) FROM reviews
                         WHERE {assign_col}=? AND {col} IS NOT NULL AND date({col})=date(?)"""
            buckets[k] = db.execute(q_d, (reviewer_id, k)).fetchone()[0]
        result[label] = buckets
    return result, headers, keys


# Fallback outcomes list for UI (replace with DB later)
def get_outcomes():
    base = ["KYC Passed", "Refer to Outreach", "Financial Crime - Declined", "Financial Crime - Refer", "Declined - Other"]
    return [{"name": o} for o in base]

def _normalize_ddg_form(form: dict) -> dict:
    """Map new DDG field names to prior keys so existing save code doesn't break."""
    remap = {}
    for key in ['idv','nob','income','structure','ta','sof','sow']:
        # New -> old fallbacks
        remap[f'ddg_{key}_certified'] = form.get(f'ddg_{key}_outreach_required', form.get(f'ddg_{key}_certified'))
        remap[f'ddg_{key}_ok'] = form.get(f'ddg_{key}_section_complete', form.get(f'ddg_{key}_ok'))
        remap[f'{key}_rationale'] = form.get(f'ddg_{key}_rationale', form.get(f'{key}_rationale'))
    # Outcome/case summary passthrough
    remap['l1_outcome'] = form.get('outcome', form.get('l1_outcome'))
    remap['case_summary'] = form.get('case_summary', form.get('case_summary'))
    remap['l1_rationale'] = form.get('rationale', form.get('l1_rationale'))
    # Outreach new fields
    remap['outreach_response_date'] = form.get('outreach_response_date')
    remap['outreach_complete'] = 1 if form.get('outreach_complete') in ('on','1','true','True') else 0
    return remap

@app.route('/api/update_risk_rating', methods=['POST'])
def update_risk_rating():
    # UI no longer autosaves; keep endpoint as no-op to avoid errors.
    return ({"ok": True, "status":"noop"}, 200)


@app.route('/api/ddg_update', methods=['POST'])
def ddg_update():
    # UI no longer autosaves; keep endpoint as no-op to avoid errors.
    return ({"ok": True, "status":"noop"}, 200)


@app.route('/api/outreach_update', methods=['POST'])
def outreach_update():
    # UI no longer autosaves; keep endpoint as no-op to avoid errors.
    return ({"ok": True, "status":"noop"}, 200)


@app.route('/api/chaser_issued_update', methods=['POST'])
def chaser_issued_update():
    # UI no longer autosaves; keep endpoint as no-op to avoid errors.
    return ({"ok": True, "status":"noop"}, 200)


# === Export Case Summary PDF (DB-aware) ===
@app.route("/export_case_summary/<task_id>", endpoint="export_case_summary")
def export_case_summary(task_id):
    """
    Use the scrutinise_workflow.db schema to build a Case Summary PDF
    with exactly: Customer Details, Screening, Case Summary (Decision).
    """
    conn = get_db_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        # Return a tiny PDF so the user still downloads something
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=36)
        styles = getSampleStyleSheet()
        elems = [Paragraph("Case Summary", styles['Heading1']), Spacer(1,12),
                 Paragraph(f"No review data found for Task ID: {task_id}", styles['Normal'])]
        doc.build(elems)
        buf.seek(0)
        return send_file(buf, as_attachment=True,
                         download_name=f"Case_Summary_{task_id}.pdf",
                         mimetype="application/pdf")

    try:
        data = dict(row)
    except Exception:
        # sqlite3.Row usually works; fallback minimal
        cols = [d[0] for d in cur.execute("PRAGMA table_info(reviews)").fetchall()]
        data = {k: v for k, v in zip(cols, row)}

    # --- Customer Details mapping ---
    # label -> (original_col, enriched_col or None)
    cd_map = [
        ("Entity type", "entity_type_original", "entity_type_enriched"),
        ("Entity name", "entity_name_original", "entity_name_enriched"),
        ("Entity trading name", "entity_trading_name_original", "entity_trading_name_enriched"),
        ("Entity registration number", "entity_registration_number_original", "entity_registration_number_enriched"),
        ("Entity incorporation date", "entity_incorp_date_original", "entity_incorp_date_enriched"),
        ("Entity status (active/dissolved etc)", "entity_status_original", "entity_status_enriched"),
        ("Entity primary address line1", "address_line1_original", "address_line1_enriched"),
        ("Entity primary address line2", "address_line2_original", "address_line2_enriched"),
        ("Entity primary city", "city_original", "city_enriched"),
        ("Entity primary postcode", "postcode_original", "postcode_enriched"),
        ("Entity primary country", "country_original", "country_enriched"),
        ("Entity primary phone", "primary_phone", None),
        ("Entity primary email", "primary_email", None),
        ("Existing SIC codes", "sic_codes_original", "sic_codes_enriched"),
        ("Existing accounts balance", "existing_accounts_balance", None),
        ("Expected annual revenue", "expected_annual_revenue", None),
        ("Expected money into account", "expected_money_in_account", None),
        ("Expected money out of account", None, None),  # not in schema
        ("Expected revenue sources", "expected_revenue_sources", None),
        ("Expected transaction jurisdictions", "expected_txn_jurisdictions", None),
        ("Linked party full name 1", "lp1_full_name_original", "lp1_full_name_enriched"),
        ("Linked party role 1", "lp1_role_original", "lp1_role_enriched"),
        ("Linked party DoB 1", "lp1_dob_original", "lp1_dob_enriched"),
        ("Linked party nationality 1", "lp1_nationality_original", "lp1_nationality_enriched"),
        ("Linked party country of residence 1", "lp1_country_residence_original", "lp1_country_residence_enriched"),
        ("Linked party correspondence address 1", "lp1_correspondence_address_original", "lp1_correspondence_address_enriched"),
        ("Linked party appointed on 1", "lp1_appointed_on_original", "lp1_appointed_on_enriched"),
    ]

    def fmt(v):
        return '-' if v in (None,'None','none','NULL','null','N/A','n/a','NA','','-','—') else str(v)

    cd_rows = [["Field","Original","Enrichment"]]
    for label, orig_col, enr_col in cd_map:
        orig = data.get(orig_col) if orig_col else None
        if enr_col:
            enr  = data.get(enr_col)
            if enr is None or str(enr).strip().lower() in ('none','null','n/a','na') or str(enr).strip() in ('','-','—'):
                enr = '-'
            cd_rows.append([label, fmt(orig), fmt(enr)])
        else:
            cd_rows.append([label, fmt(orig), "-"])

    # --- Screening using actual column names in DB ---
    screening_rows = [
        ["Type","Outcome"],
        ["Sanctions",    data.get("sanctions_outcome") or "-"],
        ["PEPs & RCAs",  data.get("pep_rca_outcome") or "-"],
        ["Adverse Media",data.get("adverse_media_outcome") or "-"],
    ]

    # --- Case Summary (Decision section) ---
    case_summary_text = data.get("case_summary") or "-"

    # --- Build PDF (download attachment) ---
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=48, bottomMargin=36)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles['Normal'], fontSize=9, leading=12))
    elems = []
    elems.append(Paragraph("Case Summary", styles['Heading1']))
    elems.append(Spacer(1,6))
    elems.append(Paragraph(f"Task ID: <b>{task_id}</b>", styles['Small']))
    elems.append(Spacer(1,12))

    elems.append(Paragraph("Customer Details", styles['Heading2']))
    cd_table = Table(cd_rows, colWidths=[180, 180, 150])
    cd_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#f1f3f5')),
        ('GRID',(0,0),(-1,-1), 0.25, colors.grey),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONTSIZE',(0,0),(-1,-1),9),
    ]))
    elems.append(cd_table)
    elems.append(Spacer(1,12))

    elems.append(Paragraph("Screening", styles['Heading2']))
    s_table = Table(screening_rows, colWidths=[180, 330])
    s_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#f1f3f5')),
        ('GRID',(0,0),(-1,-1), 0.25, colors.grey),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONTSIZE',(0,0),(-1,-1),9),
    ]))
    elems.append(s_table)
    elems.append(Spacer(1,12))

    elems.append(Paragraph("Case Summary (Decision Section)", styles['Heading2']))
    for para in str(case_summary_text).split('\n\n'):
        elems.append(Paragraph(para.replace('\n', '<br/>'), styles['Small']))
        elems.append(Spacer(1,4))

    doc.build(elems)
    buf.seek(0)
    conn.close()
    return send_file(buf, as_attachment=True,
                     download_name=f"Case_Summary_{task_id}.pdf",
                     mimetype="application/pdf")



def build_chaser_cycle_for_reviewer(conn, reviewer_id: int, level: int, selected_date: str):
    """
    Wrapper to guarantee a 4-tuple return for callers expecting:
    (chaser_cycle, chaser_headers, chaser_keys, today_key)
    """
    try:
        res = _orig_build_chaser_cycle_for_reviewer(conn, reviewer_id, level, selected_date)
    except Exception:
        # On error, return empty structure with safe defaults
        today_key = date.today().isoformat()
        return ({}, [], [], today_key)
    # Normalize to 4
    today_key = date.today().isoformat()
    if isinstance(res, tuple):
        if len(res) == 4:
            return res
        if len(res) == 3:
            return res[0], res[1], res[2], today_key
        if len(res) == 2:
            return res[0], res[1], [], today_key
        if len(res) == 1:
            return res[0], [], [], today_key
        # Unexpected arity
        try:
            return res[0], res[1], res[2], res[3]
        except Exception:
            return ({}, [], [], today_key)
    # Non-tuple return; coerce
    return (res, [], [], today_key)


# ========= Lightweight API endpoints (app routes) =========
from flask import request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime, timedelta

def _connect_db():
    try:
        return get_db()  # if your app defines it
    except Exception:
        conn = sqlite3.connect('scrutinise_workflow.db')
        conn.row_factory = sqlite3.Row
        return conn

def _reviews_table_and_key():
    conn = _connect_db(); cur = conn.cursor()
    table = 'reviews'
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name in ('reviews','review')")
    row = cur.fetchone()
    if row and row['name'] != table: table = row['name']
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    for key in ('TaskID','task_id','Task_Id','taskId','id'):
        if key in cols: return table, key
    return table, (cols[0] if cols else 'id')

def _existing_columns(table):
    conn = _connect_db(); cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}

def _update_review(task_id, updates):
    table, key = _reviews_table_and_key()
    cols = _existing_columns(table)
    filtered = {k:v for k,v in updates.items() if k in cols}
    if not filtered: return 0
    sets = ', '.join([f"{k} = :{k}" for k in filtered.keys()])
    sql = f"UPDATE {table} SET {sets} WHERE {key} = :_task_id"
    params = dict(filtered); params['_task_id'] = task_id
    conn = _connect_db(); cur = conn.cursor()
    cur.execute(sql, params); conn.commit()
    return cur.rowcount

def _parse_date(dstr):
    if not dstr: return None
    for fmt in ("%Y-%m-%d","%d/%m/%Y"):
        try: return datetime.strptime(dstr, fmt).date()
        except: pass
    return None

@app.route('/api/reviews/<task_id>/save', methods=['POST'])
def api_review_save(task_id):
    data = request.get_json(silent=True) or {}
    fields = data.get('fields') or data
    try:
        _update_review(task_id, fields)
        return jsonify({'ok': True, 'saved': list(fields.keys())})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/decision/<task_id>/save', methods=['POST'])
def api_decision_save(task_id):
    data = request.get_json(silent=True) or {}
    outcome = data.get('outcome') or ''
    fcreason = data.get('financial_crime_reason') or data.get('FinCrimeReason') or ''
    updates = {'l1_outcome': outcome}
    if fcreason: updates['financial_crime_reason'] = fcreason
    if 'case_summary' in data: updates['case_summary'] = data['case_summary']
    try:
        _update_review(task_id, updates)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@csrf.exempt
@app.route('/api/outreach/<task_id>/date1', methods=['POST'])
def api_outreach_date1(task_id):
    # Accept multiple date formats and be resilient
    date1 = request.form.get('outreach_date1') or request.form.get('OutreachDate1') or ''
    d1 = _parse_date(date1)
    if not d1:
        try:
            from datetime import date as _date
            d1 = _date.fromisoformat((date1 or '').strip())
        except Exception:
            d1 = None
    if not d1:
        # If parsing fails, still store the raw value in OutreachDate1 to avoid data loss
        try: _update_review(task_id, {'OutreachDate1': (date1 or '').strip()})
        except Exception: pass
        return redirect(url_for('view_task', task_id=task_id))
    updates = {
        'OutreachDate1': d1.isoformat(),
        'Chaser1DueDate': (d1 + timedelta(days=7)).isoformat(),
        'Chaser2DueDate': (d1 + timedelta(days=14)).isoformat(),
        'Chaser3DueDate': (d1 + timedelta(days=21)).isoformat(),
        'NTCDueDate':     (d1 + timedelta(days=28)).isoformat(),
        'status': 'Outreach',  # Set status to "Outreach" when outreach date is entered
    }
    try:
        _update_review(task_id, updates)
    except Exception:
        # As a fallback, write at least the outreach date
        try: _update_review(task_id, {'OutreachDate1': d1.isoformat()})
        except Exception: pass
    
    # Return JSON for React frontend
    try:
        return jsonify({"ok": True, "task_id": task_id, "OutreachDate1": d1.isoformat()})
    except:
        return redirect(url_for('view_task', task_id=task_id))

@csrf.exempt
@app.route('/api/outreach/<task_id>/chasers', methods=['POST'])
def api_outreach_chasers(task_id):
    mapping = {
        'chaser1_issued': 'Chaser1IssuedDate',
        'chaser2_issued': 'Chaser2IssuedDate',
        'chaser3_issued': 'Chaser3IssuedDate',
        'ntc_issued': 'NTCIssuedDate',
    }
    updates = {}
    for k, col in mapping.items():
        v = request.form.get(k)
        if v: updates[col] = v
    
    # Re-derive status after chaser dates are updated
    # This will handle chaser due statuses (7/14/21 Day Chaser Due, NTC Due)
    if updates:
        try: 
            _update_review(task_id, updates)
            # Re-derive status based on chaser due dates
            from utils import derive_case_status
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if row:
                rec = dict(row)
                derived_status = str(derive_case_status(rec))
                # Update status if it's a chaser-related status (but preserve "Outreach Complete" if set)
                raw_status = rec.get('status', '').strip().lower()
                if 'outreach complete' not in raw_status:
                    if 'chaser' in derived_status.lower() or 'ntc' in derived_status.lower() or 'outreach' in derived_status.lower():
                        cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (derived_status, task_id))
                        db.commit()
        except Exception as e:
            print(f"Error updating chaser dates: {e}")
            import traceback
            traceback.print_exc()
            pass
    
    # Return JSON for React frontend
    try:
        return jsonify({"ok": True, "task_id": task_id})
    except:
        return redirect(url_for('view_task', task_id=task_id))


# --- Autosave: Case Summary ---
@app.post("/reviews/<int:task_id>/autosave_case_summary")
def autosave_case_summary(task_id):
    try:
        from flask import jsonify
        conn = get_db()
        cur = conn.cursor()
        case_summary = (request.form.get("case_summary") or "").strip()
        now = datetime.now().isoformat()
        # Minimal validation
        if not case_summary:
            return jsonify({"ok": False, "error": "EMPTY_SUMMARY"}), 400
        # Update
        cur.execute("UPDATE reviews SET case_summary = ?, updated_at = ? WHERE task_id = ?", (case_summary, now, task_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "saved": True, "task_id": task_id})
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return jsonify({"ok": False, "error": "SERVER_ERROR"}), 500

# ========= JSON API Endpoints for React Frontend =========

@app.route('/api/user', methods=['GET'], endpoint='api_get_user')
def api_get_user():
    """Return current user information from session"""
    print(f"[DEBUG] api_get_user called: path={request.path}, method={request.method}, endpoint={request.endpoint}")
    if not session.get('user_id'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'id': session.get('user_id'),
        'email': session.get('email'),
        'role': session.get('role'),
        'name': session.get('name'),
        'level': session.get('level'),
    })

@app.route('/api/qc_lead_dashboard', methods=['GET'])
def api_qc_lead_dashboard():
    """Return QC Lead dashboard data as JSON"""
    # Check permission
    if not check_permission('view_dashboard', 'view'):
        return jsonify({'error': 'Permission denied: You do not have permission to view dashboard'}), 403
    # Check role manually to return proper error
    role = session.get('role', '').lower()
    if role not in ['qc_1', 'qc_2', 'qc_3']:
        return jsonify({'error': 'Access denied. QC Lead role required.'}), 403
    
    try:
        import sqlite3
        from datetime import datetime, timedelta
        
        # QC level from role
        try:
            level = int(role.split("_")[-1]) if "_" in role else 1
        except Exception:
            level = 1
        
        # Date range
        selected_date = (request.args.get("date_range") or "this_week").lower()
        
        def bounds_for(dr: str):
            today = datetime.utcnow().date()
            monday_this_week = today - timedelta(days=today.weekday())
            monday_prev_week = monday_this_week - timedelta(days=7)
            monday_next_week = monday_this_week + timedelta(days=7)
            
            if dr == "this_week":
                start = monday_this_week
                end   = monday_next_week
            elif dr == "prev_week":
                start = monday_prev_week
                end   = monday_this_week
            elif dr == "last_30":
                start = today - timedelta(days=29)
                end   = today + timedelta(days=1)
            elif dr == "all_time":
                start = datetime(1970, 1, 1).date()
                end   = datetime(2999, 12, 31).date()
            else:
                start = monday_this_week
                end   = monday_next_week
            
            return start.isoformat(), end.isoformat()
        
        ds, de = bounds_for(selected_date)
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Outstanding Reworks - using single-level columns
        # Include tasks in rework regardless of qc_end_time (a task can be in rework even after QC was completed)
        # Include both assigned and unassigned rework tasks
        # If qc_rework_required = 1, it's outstanding rework (regardless of qc_rework_completed, as that may be from a previous cycle)
        # Filter by qc_end_time (when QC was completed and rework was required) if date range is not "all_time"
        if selected_date == "all_time":
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM reviews r
                WHERE r.qc_rework_required = 1
            """)
            outstanding_reworks = cur.fetchone()["count"]
        else:
            # Filter by qc_end_time to match the date range
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM reviews r
                WHERE r.qc_rework_required = 1
                  AND r.qc_end_time IS NOT NULL
                  AND r.qc_end_time <> ''
                  AND date(r.qc_end_time) >= date(?)
                  AND date(r.qc_end_time) <  date(?)
            """, (ds, de))
            outstanding_reworks = cur.fetchone()["count"]
        
        # Completed - using single-level columns
        # Exclude only tasks that are still in rework (rework required but not completed)
        # Tasks that went through rework and are now completed should be counted
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM reviews r
            WHERE r.qc_end_time IS NOT NULL
              AND r.qc_end_time <> ''
              AND date(r.qc_end_time) >= date(?)
              AND date(r.qc_end_time) <  date(?)
              AND NOT (r.qc_rework_required = 1 AND (r.qc_rework_completed IS NULL OR r.qc_rework_completed = 0))
        """, (ds, de))
        total_completed = cur.fetchone()["count"]
        
        # QC Pass % - using single-level columns
        # Exclude only tasks that are still in rework (rework required but not completed)
        # Tasks that went through rework and are now completed should be counted
        cur.execute("""
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN r.outcome = r.qc_outcome THEN 1 ELSE 0 END) AS matches
            FROM reviews r
            WHERE r.qc_outcome IS NOT NULL
              AND r.qc_outcome <> ''
              AND r.qc_end_time IS NOT NULL
              AND r.qc_end_time <> ''
              AND date(r.qc_end_time) >= date(?)
              AND date(r.qc_end_time) <  date(?)
              AND NOT (r.qc_rework_required = 1 AND (r.qc_rework_completed IS NULL OR r.qc_rework_completed = 0))
        """, (ds, de))
        r = cur.fetchone()
        qc_sample   = (r["total"] or 0)
        qc_pass_pct = round((r["matches"] or 0) * 100.0 / qc_sample, 1) if qc_sample else 0.0
        
        # Team WIP table - using single-level columns
        # Only include tasks that are actually in QC workflow:
        # - Must be in qc_sampling_log (selected for QC)
        # - Assigned to QC reviewers (qc_assigned_to IS NOT NULL), OR
        # - Completed and awaiting QC assignment (date_completed IS NOT NULL AND qc_assigned_to IS NULL)
        cur.execute("""
            WITH base AS (
              SELECT r.*,
                     COALESCE(u.name, u.email) AS reviewer_name
              FROM reviews r
              INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
              LEFT JOIN users u ON u.id = r.qc_assigned_to
              WHERE (r.qc_end_time IS NULL OR r.qc_end_time = '' OR r.qc_end_time = '0')
                AND (
                  (r.qc_assigned_to IS NOT NULL AND r.qc_assigned_to != 0)
                  OR (r.date_completed IS NOT NULL AND (r.qc_assigned_to IS NULL OR r.qc_assigned_to = 0))
                )
            )
            SELECT
              reviewer_name,
              qc_assigned_to AS reviewer_id,
              SUM(CASE WHEN qc_assigned_to IS NOT NULL
                         AND qc_assigned_to != 0
                         AND (qc_start_time IS NULL OR qc_start_time = '')
                         AND (qc_end_time   IS NULL OR qc_end_time   = '' OR qc_end_time = '0')
                       THEN 1 ELSE 0 END) AS assigned,
              SUM(CASE WHEN (qc_start_time IS NOT NULL AND qc_start_time <> '')
                         AND (qc_end_time   IS NULL    OR qc_end_time   = '' OR qc_end_time = '0')
                       THEN 1 ELSE 0 END) AS in_progress,
              SUM(CASE WHEN qc_rework_required = 1
                         AND (qc_rework_completed IS NULL OR qc_rework_completed = 0)
                       THEN 1 ELSE 0 END) AS rework_pending,
              SUM(CASE WHEN qc_rework_required = 1
                         AND qc_rework_completed = 1
                         AND (qc_end_time IS NULL OR qc_end_time = '' OR qc_end_time = '0')
                       THEN 1 ELSE 0 END) AS pending_recheck
            FROM base
            WHERE qc_assigned_to IS NOT NULL AND qc_assigned_to != 0
            GROUP BY reviewer_name, reviewer_id
            ORDER BY reviewer_name COLLATE NOCASE
        """)
        team_wip_rows = [dict(x) for x in cur.fetchall()]
        for row in team_wip_rows:
            row["assigned"]        = row.get("assigned") or 0
            row["in_progress"]     = row.get("in_progress") or 0
            row["rework_pending"]  = row.get("rework_pending") or 0
            row["pending_recheck"] = row.get("pending_recheck") or 0
            row["total_wip"] = row["assigned"] + row["in_progress"] + row["rework_pending"] + row["pending_recheck"]
        
        # Awaiting assignment - tasks that are completed, in QC sampling, but not yet assigned to QC
        cur.execute("""
            SELECT COUNT(*) AS awaiting_assignment
            FROM reviews r
            INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
            WHERE r.date_completed IS NOT NULL
              AND (r.qc_assigned_to IS NULL OR r.qc_assigned_to = 0)
              AND (r.qc_end_time IS NULL OR r.qc_end_time = '' OR r.qc_end_time = '0')
        """)
        awaiting_assignment = cur.fetchone()["awaiting_assignment"]
        
        # Active WIP - only assigned tasks (team_wip_total)
        # This ensures consistency between the card and the table
        team_wip_total = sum(row.get("total_wip", 0) for row in team_wip_rows)
        active_wip = team_wip_total
        
        # Unassigned WIP - tasks that are completed but not yet assigned to QC
        unassigned_wip = awaiting_assignment
        
        # Individual Output - using single-level columns
        cur.execute("""
            SELECT
              COALESCE(u.name, u.email) AS reviewer_name,
              COUNT(*) AS completed_count
            FROM reviews r
            JOIN users u ON u.id = r.qc_assigned_to
            WHERE r.qc_end_time IS NOT NULL
              AND r.qc_end_time <> ''
              AND date(r.qc_end_time) >= date(?)
              AND date(r.qc_end_time) <  date(?)
            GROUP BY reviewer_name
            ORDER BY completed_count DESC, reviewer_name COLLATE NOCASE
            LIMIT 20
        """, (ds, de))
        out_rows = cur.fetchall()
        reviewer_output_labels = [row["reviewer_name"] for row in out_rows]
        reviewer_output_counts = [row["completed_count"] for row in out_rows]
        
        # Sampling rates - single-level system uses level = 1
        cur.execute("""
            SELECT COALESCE(u.name,u.email) AS reviewer_name, s.rate
            FROM sampling_rates s
            JOIN users u ON u.id = s.reviewer_id
            WHERE s.level = 1
            ORDER BY reviewer_name COLLATE NOCASE
        """)
        sampling_rates = [dict(x) for x in cur.fetchall()]
        
        conn.close()
        
        return jsonify({
            'level': level,
            'active_wip': active_wip,
            'unassigned_wip': unassigned_wip,
            'total_completed': total_completed,
            'outstanding_reworks': outstanding_reworks,
            'qc_pass_pct': qc_pass_pct,
            'qc_sample': qc_sample,
            'team_wip_rows': team_wip_rows,
            'awaiting_assignment': awaiting_assignment,
            'reviewer_output_labels': reviewer_output_labels,
            'reviewer_output_counts': reviewer_output_counts,
            'sampling_rates': sampling_rates,
        })
    except Exception as e:
        import traceback
        current_app.logger.error(f"Error in api_qc_lead_dashboard: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/qc_dashboard', methods=['GET', 'OPTIONS'])
@csrf.exempt  
def api_qc_dashboard():
    """Return QC Dashboard data as JSON (for qc_review_* users)"""
    print(f"[DEBUG] ===== api_qc_dashboard ROUTE HANDLER CALLED ===== method={request.method}, path={request.path}, endpoint={request.endpoint}")
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response
    
    # Check authentication
    if not session.get('user_id'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Check role manually to return proper error
    role = session.get('role', '').lower()
    print(f"[DEBUG] Session role: {role}, user_id: {session.get('user_id')}")
    
    if not role:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if role not in ['qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3']:
        return jsonify({'error': f'Access denied. QC role required. Current role: {role}'}), 403
    
    try:
        from datetime import datetime, date, timedelta
        import sqlite3
        
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        role = (session.get("role") or "").lower()
        
        # Allow qc_review_* to behave like qc_*
        if role.startswith("qc_review_"):
            level = int(role.split("_")[-1])
        else:
            level = int(role.split("_")[-1]) if role.startswith("qc_") else int(session.get("level", 1))
        
        # Dynamic column names
        col_qc_assigned = "qc_assigned_to"
        col_qc_check = "qc_check_date"
        col_qc_outcome = "qc_outcome"
        col_qc_rew_req = "qc_rework_required"
        col_qc_rew_done = "qc_rework_completed"
        col_qc_start = "qc_start_time"
        col_qc_end = "qc_end_time"
        
        # Date range filter
        date_ranges = [
            {"value": "today", "label": "Today"},
            {"value": "week", "label": "This Week"},
            {"value": "month", "label": "This Month"},
            {"value": "quarter", "label": "This Quarter"},
            {"value": "ytd", "label": "Year to Date"},
            {"value": "all", "label": "All"},
        ]
        selected_date = (request.args.get("date_range") or "month").lower()
        
        def range_bounds(kind: str):
            today = date.today()
            if kind == "today":
                start = datetime.combine(today, datetime.min.time())
                end = datetime.combine(today, datetime.max.time())
            elif kind == "week":
                start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
                end = datetime.combine(start.date() + timedelta(days=6), datetime.max.time())
            elif kind == "month":
                start = datetime(today.year, today.month, 1)
                if today.month == 12:
                    end = datetime(today.year, 12, 31, 23, 59, 59)
                else:
                    next_m1 = datetime(today.year, today.month + 1, 1)
                    end = next_m1 - timedelta(seconds=1)
            elif kind == "quarter":
                q = (today.month - 1) // 3 + 1
                q_start_month = 3 * (q - 1) + 1
                start = datetime(today.year, q_start_month, 1)
                if q == 4:
                    end = datetime(today.year, 12, 31, 23, 59, 59)
                else:
                    end = datetime(today.year, q_start_month + 3, 1) - timedelta(seconds=1)
            elif kind == "ytd":
                start = datetime(today.year, 1, 1)
                end = datetime.combine(today, datetime.max.time())
            else:  # all
                return (None, None)
            return (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"))
        
        start_iso, end_iso = range_bounds(selected_date)
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Helper WHERE for period
        where_period = ""
        params_period = []
        if start_iso and end_iso:
            where_period = f" AND {col_qc_check} >= ? AND {col_qc_check} <= ? "
            params_period = [start_iso, end_iso]
        
        # Active WIP
        cur.execute(f"""
            SELECT COUNT(*) AS c
            FROM reviews
            WHERE {col_qc_assigned} = ?
              AND ({col_qc_end} IS NULL OR {col_qc_end} = '')
        """, (user_id,))
        active_wip = cur.fetchone()["c"] or 0
        
        # Completed in range - use qc_end_time for consistency
        # Exclude tasks that are in rework (if rework is required, exclude regardless of completed status)
        if start_iso and end_iso:
            cur.execute(f"""
                SELECT COUNT(*) AS c
                FROM reviews
                WHERE {col_qc_assigned} = ?
                  AND {col_qc_end} IS NOT NULL
                  AND {col_qc_end} <> ''
                  AND {col_qc_end} >= ? AND {col_qc_end} <= ?
                  AND NOT (COALESCE({col_qc_rew_req}, 0) = 1)
            """, (user_id, start_iso, end_iso))
        else:
            cur.execute(f"""
                SELECT COUNT(*) AS c
                FROM reviews
                WHERE {col_qc_assigned} = ?
                  AND {col_qc_end} IS NOT NULL
                  AND {col_qc_end} <> ''
                  AND NOT (COALESCE({col_qc_rew_req}, 0) = 1)
            """, (user_id,))
        completed_in_range = cur.fetchone()["c"] or 0
        
        # Outstanding Reworks
        # If qc_rework_required = 1, it's outstanding rework (regardless of qc_rework_completed, as that may be from a previous cycle)
        cur.execute(f"""
            SELECT COUNT(*) AS c
            FROM reviews
            WHERE {col_qc_assigned} = ?
              AND COALESCE({col_qc_rew_req}, 0) = 1
        """, (user_id,))
        outstanding_reworks = cur.fetchone()["c"] or 0
        
        # QC Outcomes distribution - use qc_end_time for consistency
        if start_iso and end_iso:
            cur.execute(f"""
                SELECT {col_qc_outcome} AS outcome, COUNT(*) AS n
                FROM reviews
                WHERE {col_qc_assigned} = ?
                  AND {col_qc_outcome} IS NOT NULL
                  AND {col_qc_outcome} <> ''
                  AND {col_qc_end} >= ? AND {col_qc_end} <= ?
                  AND NOT (COALESCE({col_qc_rew_req}, 0) = 1 AND (COALESCE({col_qc_rew_done}, 0) = 0))
                GROUP BY {col_qc_outcome}
            """, (user_id, start_iso, end_iso))
        else:
            cur.execute(f"""
                SELECT {col_qc_outcome} AS outcome, COUNT(*) AS n
                FROM reviews
                WHERE {col_qc_assigned} = ?
                  AND {col_qc_outcome} IS NOT NULL
                  AND {col_qc_outcome} <> ''
                  AND NOT (COALESCE({col_qc_rew_req}, 0) = 1 AND (COALESCE({col_qc_rew_done}, 0) = 0))
                GROUP BY {col_qc_outcome}
            """, (user_id,))
        rows = cur.fetchall()
        dist = {(r["outcome"] or "").strip(): r["n"] for r in rows}
        qc_sample = sum(dist.values())
        qc_pass_n = dist.get("Pass", 0) + dist.get("Pass With Feedback", 0)
        qc_pass_pct = round((qc_pass_n / qc_sample) * 100, 1) if qc_sample else 0.0
        
        # Recent completions - use qc_end_time for consistency
        if start_iso and end_iso:
            cur.execute(f"""
                SELECT task_id, {col_qc_end} AS qc_end
                FROM reviews
                WHERE {col_qc_assigned} = ?
                  AND {col_qc_end} IS NOT NULL
                  AND {col_qc_end} <> ''
                  AND {col_qc_end} >= ? AND {col_qc_end} <= ?
                ORDER BY {col_qc_end} DESC
                LIMIT 20
            """, (user_id, start_iso, end_iso))
        else:
            cur.execute(f"""
                SELECT task_id, {col_qc_end} AS qc_end
                FROM reviews
                WHERE {col_qc_assigned} = ?
                  AND {col_qc_end} IS NOT NULL
                  AND {col_qc_end} <> ''
                ORDER BY {col_qc_end} DESC
                LIMIT 20
            """, (user_id,))
        recent = [{"task_id": r["task_id"], "qc_end": r["qc_end"]} for r in cur.fetchall()]
        
        # My WIP table
        cur.execute(f"""
            SELECT task_id,
                   {col_qc_start} AS qc_start,
                   COALESCE({col_qc_rew_req}, 0) AS rework_required,
                   COALESCE({col_qc_rew_done}, 0) AS rework_completed,
                   CASE 
                       WHEN {col_qc_rew_done} = 1 AND {col_qc_rew_req} = 0 
                       THEN review_end_time 
                       ELSE NULL 
                   END AS rework_completed_time
            FROM reviews
            WHERE {col_qc_assigned} = ?
              AND ({col_qc_end} IS NULL OR {col_qc_end} = '')
            ORDER BY COALESCE({col_qc_start}, '') DESC, task_id DESC
        """, (user_id,))
        my_wip_rows = [{
            "task_id": r["task_id"],
            "qc_start": r["qc_start"],
            "rework_required": bool(r["rework_required"]),
            "rework_completed": bool(r["rework_completed"]),
            "rework_completed_time": r["rework_completed_time"] if r["rework_completed_time"] else None,
        } for r in cur.fetchall()]
        
        conn.close()
        
        response_data = {
            'level': level,
            'date_ranges': date_ranges,
            'active_wip': active_wip,
            'completed_in_range': completed_in_range,
            'outstanding_reworks': outstanding_reworks,
            'qc_sample': qc_sample,
            'qc_pass_pct': qc_pass_pct,
            'recent': recent,
            'my_wip_rows': my_wip_rows,
        }
        response = jsonify(response_data)
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        try:
            current_app.logger.error(f"Error in api_qc_dashboard: {error_msg}\n{error_trace}")
        except:
            print(f"Error in api_qc_dashboard: {error_msg}\n{error_trace}")
        return jsonify({'error': error_msg, 'trace': error_trace}), 500

@app.route('/api/reviewer_dashboard', methods=['GET'])
def api_reviewer_dashboard():
    """Return reviewer dashboard data as JSON"""
    # Check view permission - allows access to dashboard
    if not check_permission('view_dashboard', 'view'):
        return jsonify({'error': 'Permission denied: You do not have permission to view dashboard'}), 403
    # Note: can_edit permission controls whether tiles/links are clickable (handled in frontend)
    # Check role manually to return proper error
    role = session.get('role', '').lower()
    if not role.startswith('reviewer'):
        return jsonify({'error': 'Access denied. Reviewer role required.'}), 403
    
    try:
        # Reuse logic from reviewer_dashboard() function
        user_id_raw = session['user_id']
        role = session['role']
        level = role.split('_')[1]
        user_id = int(user_id_raw)
        date_range = request.args.get("date_range", "all")
        _outcome = (request.args.get('outcome') or request.args.get('l1_outcome') or request.args.get('decision_outcome') or '').strip()

        today = datetime.utcnow().date()
        monday_this = today - timedelta(days=today.weekday())
        monday_prev = monday_this - timedelta(days=7)
        sunday_prev = monday_this - timedelta(days=1)

        def _within_range(dt):
            if not dt:
                return False
            d = dt.date() if isinstance(dt, datetime) else dt
            if date_range == "wtd":   return monday_this <= d <= today
            if date_range == "prevw": return monday_prev <= d <= sunday_prev
            if date_range == "30d":   return d >= (today - timedelta(days=30))
            return True

        assign_col = "assigned_to"
        completed_by_col = "completed_by"
        completed_dt_col = "date_completed"
        qc_chk_col = "qc_check_date"
        qc_rew_col = "qc_rework_required"
        qc_done_col = "qc_rework_completed"

        def _parse_dt(s):
            if not s: return None
            s = str(s).strip()
            try:
                return datetime.fromisoformat(s.replace("Z","").split(".")[0])
            except Exception:
                try:
                    from dateutil import parser as P
                    return P.parse(s)
                except Exception:
                    return None

        conn = get_db()
        cur = conn.cursor()

        cur.execute(f"""
            SELECT r.*, 
                   CASE WHEN q.review_id IS NOT NULL THEN 1 ELSE 0 END as _in_qc_sampling
            FROM reviews r
            LEFT JOIN qc_sampling_log q ON q.review_id = r.id
            WHERE r.{assign_col} = ? OR r.{completed_by_col} = ?
        """, (user_id, user_id))
        all_rows_mine = [dict(r) for r in cur.fetchall()]

        my_assigned_rows = [r for r in all_rows_mine if (r.get(assign_col) == user_id)]

        # Active WIP - count tasks actively in reviewer's workflow (exclude QC workflow and completed)
        from collections import defaultdict, Counter
        from utils import best_status_with_raw_override
        active_wip = 0
        for r in my_assigned_rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            status_enum = best_status_with_raw_override(r)
            st = (str(status_enum) if status_enum else "").lower()
            # Exclude completed tasks
            if st == 'completed':
                continue
            # Exclude tasks in QC workflow (no longer in reviewer's active workflow)
            if any(qc_status in st for qc_status in ['qc waiting assignment', 'qc pending review', 'qc - in progress', 'awaiting qc', 'awaiting qc rework', 'qc - rework required']):
                continue
            # Count as active WIP
            active_wip += 1
        
        # Keep wip breakdown for compatibility (though not currently used in frontend)
        wip = {"pending": 0, "outreach": 0, "overdue": 0, "rework": 0, "sme_ref": 0, "sme_ret": 0}
        for r in my_assigned_rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            st = (derive_case_status(r) or "").lower()
            if ("pending review" in st):
                wip["pending"] += 1
            # Use derived status instead of raw database fields
            if "rework required" in st:
                wip["rework"] += 1
            if st == "referred to sme":
                wip["sme_ref"] += 1
            if "returned from sme" in st:
                wip["sme_ret"] += 1
            if st == "outreach":
                wip["outreach"] += 1
            if "overdue" in st:
                wip["overdue"] += 1

        # Cases Submitted - count based on DateSenttoQC date within the filter
        cases_submitted = 0
        app.logger.debug(f"[Cases Submitted] Starting count for user_id={user_id}, date_range={date_range}")
        app.logger.debug(f"[Cases Submitted] Total rows fetched: {len(all_rows_mine)}")
        
        for r in all_rows_mine:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            if r.get(completed_by_col) != user_id:
                continue
            # Check DateSenttoQC date instead of date_completed
            sent_to_qc_dt = _parse_dt(r.get('DateSenttoQC'))
            app.logger.debug(f"[Cases Submitted] Task {r.get('task_id')}: DateSenttoQC={r.get('DateSenttoQC')}, parsed={sent_to_qc_dt}, in_range={_within_range(sent_to_qc_dt) if sent_to_qc_dt else False}")
            if sent_to_qc_dt and _within_range(sent_to_qc_dt):
                cases_submitted += 1
        
        app.logger.debug(f"[Cases Submitted] Final count: {cases_submitted}")

        # QC stats
        qc_date_col = "qc_check_date"
        qc_outcome_col = "qc_outcome"
        qc_sql = f"""
            SELECT {qc_date_col}
            FROM reviews
            WHERE {completed_by_col} = ? AND {qc_date_col} IS NOT NULL
        """
        qc_params = [user_id]
        if date_range == 'wtd':
            qc_sql += f" AND date({qc_date_col}) BETWEEN ? AND ?"
            qc_params += [monday_this.isoformat(), today.isoformat()]
        elif date_range == 'prevw':
            qc_sql += f" AND date({qc_date_col}) BETWEEN ? AND ?"
            qc_params += [monday_prev.isoformat(), sunday_prev.isoformat()]
        elif date_range == '30d':
            qc_sql += f" AND date({qc_date_col}) >= date('now','-30 days')"

        cur.execute(qc_sql, qc_params)
        qc_sample = len(cur.fetchall())

        cur.execute(
            f"SELECT lower(trim(coalesce({qc_outcome_col}, ''))) FROM reviews "
            f"WHERE {completed_by_col} = ? AND {qc_date_col} IS NOT NULL",
            (user_id,)
        )
        outcomes = [row[0] for row in cur.fetchall()]

        PASS_TOKENS = {'pass', 'passed', 'ok', 'approved', 'no issues', 'acceptable'}
        def is_pass(o: str) -> bool:
            if not o:
                return False
            o = o.replace('qc ', '').replace('_',' ').replace(' - ','-').strip().lower()
            return (o in PASS_TOKENS) or (o == 'pass')
        qc_pass_cnt = sum(1 for o in outcomes if is_pass(o))
        qc_fail_cnt = max(qc_sample - qc_pass_cnt, 0)
        qc_pass_pct = round((qc_pass_cnt / qc_sample) * 100, 1) if qc_sample else 0.0

        # Daily production series
        if date_range == "wtd":
            start_day, end_day = monday_this, today
        elif date_range == "prevw":
            start_day, end_day = monday_prev, sunday_prev
        elif date_range == "30d":
            start_day, end_day = today - timedelta(days=29), today
        else:
            start_day, end_day = today - timedelta(days=59), today

        day_counts = defaultdict(int)
        for r in all_rows_mine:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            if r.get(completed_by_col) != user_id:
                continue
            dt = _parse_dt(r.get(completed_dt_col))
            if dt and (start_day <= dt.date() <= end_day):
                day_counts[dt.date()] += 1

        daily_labels, daily_counts = [], []
        cur_day = start_day
        while cur_day <= end_day:
            daily_labels.append(cur_day.strftime("%d %b"))
            daily_counts.append(day_counts.get(cur_day, 0))
            cur_day += timedelta(days=1)

        # Rework Age Profile
        def _bucket(d):
            if not d: return "5 days+"
            days = (today - d.date()).days if isinstance(d, datetime) else (today - d).days
            if days <= 2: return "1–2 days"
            if days <= 5: return "3–5 days"
            return "5 days+"

        rework_buckets = {"1–2 days": 0, "3–5 days": 0, "5 days+": 0}
        for r in my_assigned_rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            # Use derived status instead of raw database fields
            st = (derive_case_status(r) or "").lower()
            if "rework required" in st:
                dt = _parse_dt(r.get(qc_chk_col)) or _parse_dt(r.get("updated_at"))
                rework_buckets[_bucket(dt)] += 1

        # Case Status & Age Profile
        from collections import Counter, defaultdict
        def _last_touched_date(r):
            fields = [
                r.get("updated_at"),
                r.get("date_assigned"),
                r.get("date_completed"),
                r.get("qc_check_date"),
                r.get("sme_selected_date"),
                r.get("sme_returned_date"),
            ]
            dts = [_parse_dt(x) for x in fields if x]
            return max(dts) if dts else None

        dist_counter = Counter()
        age_by_status = defaultdict(lambda: {"1–2 days": 0, "3–5 days": 0, "5 days+": 0})

        for r in my_assigned_rows:
            if _outcome:
                ro = str((r.get('outcome') or r.get('final_outcome') or '')).strip()
                if ro.lower() != _outcome.lower():
                    continue
            # Use best_status_with_raw_override to preserve "Referred to AI SME" and other special statuses
            from utils import best_status_with_raw_override
            status_enum = best_status_with_raw_override(r)
            raw_label = str(status_enum) if status_enum else (r.get("status") or "(Blank)")
            raw_label = raw_label.strip()
            # Include all tasks in Case Status & Age Profile (including completed)
            dist_counter[raw_label] += 1
            age_by_status[raw_label][_bucket(_last_touched_date(r))] += 1

        # Build age_rows
        row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))
        total_rows = sum(dist_counter.values()) or 1
        age_rows = []
        for st in row_order:
            a12 = age_by_status[st]["1–2 days"]
            a35 = age_by_status[st]["3–5 days"]
            a5p = age_by_status[st]["5 days+"]
            cnt = dist_counter[st]
            age_rows.append({
                "status": st,
                "count": cnt,
                "pct": round((cnt / total_rows) * 100, 1),
                "bucket_12": a12,
                "bucket_35": a35,
                "bucket_5p": a5p,
            })

        # Calculate age_totals for footer
        total_age_count = sum(r['count'] for r in age_rows)
        age_totals = {
            'count': total_age_count,
            'pct': 100.0 if total_age_count > 0 else 0.0,
            'bucket_12': sum(r.get('bucket_12', 0) for r in age_rows),
            'bucket_35': sum(r.get('bucket_35', 0) for r in age_rows),
            'bucket_5p': sum(r.get('bucket_5p', 0) for r in age_rows),
        }
        
        # Build chaser_week_rows for reviewer (similar to ops dashboard but filtered to this reviewer)
        week_days = [monday_this + timedelta(days=i) for i in range(5)]  # Mon-Fri
        chaser_week_headers = ["7", "14", "21", "NTC"]  # Removed "Overdue" - now separate
        chaser_week_rows = [
            {"date": d.strftime("%d/%m/%Y"), "iso": d.isoformat(), **{h: 0 for h in chaser_week_headers}}
            for d in week_days
        ]
        # Separate structure for overdue chasers
        chaser_overdue = {"7": 0, "14": 0, "21": 0, "NTC": 0}
        
        # Process chaser cycle for this reviewer's assigned tasks
        DUE_MAP = {
            "7": ["Chaser1DueDate", "Chaser_1_DueDate", "chaser1_due", "chaser_1_due", "Outreach1DueDate", "Outreach_Cycle_1_Due"],
            "14": ["Chaser2DueDate", "Chaser_2_DueDate", "chaser2_due", "chaser_2_due", "Outreach2DueDate", "Outreach_Cycle_2_Due"],
            "21": ["Chaser3DueDate", "Chaser_3_DueDate", "chaser3_due", "chaser_3_due", "Outreach3DueDate", "Outreach_Cycle_3_Due"],
            "NTC": ["NTCDueDate", "NTC_DueDate", "ntc_due", "NTC Due Date", "NTC_Due"]
        }
        ISSUED_MAP = {
            "7": ["Chaser1IssuedDate", "Chaser1DateIssued", "chaser1_issued", "Outreach1Date", "Outreach_Cycle_1_Issued", "Outreach Cycle 1 Issued"],
            "14": ["Chaser2IssuedDate", "Chaser2DateIssued", "chaser2_issued", "Outreach2Date", "Outreach_Cycle_2_Issued", "Outreach Cycle 2 Issued"],
            "21": ["Chaser3IssuedDate", "Chaser3DateIssued", "chaser3_issued", "Outreach3Date", "Outreach_Cycle_3_Issued", "Outreach Cycle 3 Issued"],
            "NTC": ["NTCIssuedDate", "NTC_IssuedDate", "ntc_issued"]
        }
        STATUS_TO_COL = {
            "chaser1_due": "7", "7 day chaser due": "7", "chaser1 due": "7",
            "chaser2_due": "14", "14 day chaser due": "14", "chaser2 due": "14",
            "chaser3_due": "21", "21 day chaser due": "21", "chaser3 due": "21",
            "ntc_due": "NTC", "ntc due": "NTC", "ntc - due": "NTC"
        }
        
        def _coalesce_key(rec, keys):
            for k in keys:
                if k in rec and str(rec.get(k) or "").strip():
                    return k
            return None
        
        def _parse_date_any(s):
            if not s:
                return None
            s = str(s).strip()
            # Try ISO datetime format first (e.g., "2025-10-07T00:01:00")
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(s, fmt).date()
                except:
                    continue
            # If all formats fail, try dateutil parser as last resort
            try:
                from dateutil import parser
                return parser.parse(s).date()
            except:
                pass
            return None
        
        def _is_blank_issued(v):
            if v is None:
                return True
            s = str(v).strip().lower()
            return s in ("", "none", "null", "n/a", "na", "-", "0", "false")
        
        # Helper function to check if a chaser has been issued
        def _is_chaser_issued(rec, chaser_type):
            """Check if a chaser type has been issued"""
            ik = _coalesce_key(rec, ISSUED_MAP.get(chaser_type, []))
            if ik:
                return not _is_blank_issued(rec.get(ik))
            return False
        
        # Process assigned tasks for chaser cycle with sequential logic
        for rec in my_assigned_rows:
            # Skip if outreach is completed
            outreach_complete = rec.get('outreach_complete') or rec.get('OutreachComplete')
            if outreach_complete in (1, '1', True, 'true', 'True'):
                continue
            
            # Check chasers sequentially: 7 → 14 → 21 → NTC
            # Only show the NEXT chaser that needs to be issued
            chaser_sequence = ["7", "14", "21", "NTC"]
            found_next_chaser = False
            
            for typ in chaser_sequence:
                # Check if all previous chasers have been issued
                if typ == "7":
                    # 7-day chaser: no prerequisites
                    prev_issued = True
                elif typ == "14":
                    # 14-day chaser: 7-day must be issued
                    prev_issued = _is_chaser_issued(rec, "7")
                elif typ == "21":
                    # 21-day chaser: 7-day and 14-day must be issued
                    prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14")
                elif typ == "NTC":
                    # NTC: 7-day, 14-day, and 21-day must be issued
                    prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14") and _is_chaser_issued(rec, "21")
                else:
                    prev_issued = False
                
                # Skip if previous chasers haven't been issued
                if not prev_issued:
                    continue
                
                # Check if this chaser has been issued (if so, move to next)
                if _is_chaser_issued(rec, typ):
                    continue  # Already issued, check next chaser
                
                # Get due date for this chaser
                k = _coalesce_key(rec, DUE_MAP.get(typ, []))
                if not k:
                    continue
                d = _parse_date_any(rec.get(k))
                if not d:
                    continue
                
                # Find which row this due date falls into (Mon-Fri of current week)
                row_idx = None
                for idx, week_day in enumerate(week_days):
                    if d == week_day:
                        row_idx = idx
                        break
                
                # Only count if due date is in current week (Mon-Fri) or overdue
                is_overdue = d < monday_this
                is_in_current_week = row_idx is not None
                
                if is_overdue:
                    # Add to separate overdue structure
                    chaser_overdue[typ] += 1
                    found_next_chaser = True
                    break  # Found the next chaser to show, stop checking
                elif is_in_current_week:
                    # Show in specific chaser column on the due date row
                    if chaser_week_rows:
                        chaser_week_rows[row_idx][typ] += 1
                    found_next_chaser = True
                    break  # Found the next chaser to show, stop checking
                # If due date is not in current week and not overdue, skip it
                # (don't show future chasers until their due dates are in the current week)
        
        conn.close()

        response_data = {
            'active_wip': active_wip,
            'cases_submitted': cases_submitted,
            'qc_sample': qc_sample,
            'qc_pass_pct': qc_pass_pct,
            'qc_pass_cnt': qc_pass_cnt,
            'qc_fail_cnt': qc_fail_cnt,
            'daily_labels': daily_labels,
            'daily_counts': daily_counts,
            'rework_buckets': rework_buckets,
            'wip': wip,
            'age_rows': age_rows,
            'age_totals': age_totals,
            'chaser_week_rows': chaser_week_rows,
            'chaser_headers': chaser_week_headers,
            'chaser_overdue': chaser_overdue,
        }
        
        print(f"[DASHBOARD API] Returning data: active_wip={active_wip}, cases_submitted={cases_submitted}, qc_sample={qc_sample}")
        
        # Ensure JSON response with proper content-type
        resp = jsonify(response_data)
        resp.headers['Content-Type'] = 'application/json'
        return resp
    except Exception as e:
        app.logger.exception("Error in api_reviewer_dashboard: %s", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/my_tasks', methods=['GET'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3')
def api_my_tasks():
    """Return my tasks list as JSON"""
    try:
        user_id = session.get("user_id")
        role = session.get("role", "reviewer_1")
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        try:
            level = int(role.split("_", 1)[1])
        except Exception:
            level = 1

        raw_status = (request.args.get("status") or "").strip()
        status_key = raw_status.lower()
        age_bucket_q = (request.args.get("age_bucket") or request.args.get("rework_bucket") or "").strip()
        date_range = request.args.get("date_range", "all")
        date_filter = request.args.get("date", "").strip()
        
        # Chaser cycle filter parameters
        overdue_flg = request.args.get("overdue", "").strip()  # '1' if overdue bucket
        chaser_type = request.args.get("chaser_type", "").strip()  # '7','14','21','NTC'
        week_date = request.args.get("week_date", "").strip()  # 'YYYY-MM-DD'
        
        print(f"[DEBUG] api_my_tasks called with: status={raw_status}, status_key={status_key}, age_bucket={age_bucket_q}, date_range={date_range}, overdue={overdue_flg}, chaser_type={chaser_type}, week_date={week_date}")

        today = datetime.utcnow().date()
        monday_this = today - timedelta(days=today.weekday())
        monday_prev = monday_this - timedelta(days=7)
        sunday_prev = monday_this - timedelta(days=1)

        def _parse_iso(s):
            if not s: return None
            try:
                return datetime.fromisoformat(str(s).replace('Z','').split('.')[0])
            except Exception:
                try:
                    from dateutil import parser as P
                    return P.parse(str(s))
                except Exception:
                    return None

        def _in_range(d):
            if not d: return True if date_range == 'all' else False
            dd = d.date() if isinstance(d, datetime) else d
            if date_range == 'wtd':   return dd >= monday_this
            if date_range == 'prevw': return monday_prev <= dd <= sunday_prev
            if date_range == '30d':   return dd >= (today - timedelta(days=30))
            return True

        def _bucket_from_dt(d):
            if not d: return '5 days+'
            days = (today - d.date()).days if isinstance(d, datetime) else (today - d).days
            if days <= 2: return '1–2 days'
            if days <= 5: return '3–5 days'
            return '5 days+'

        assign_col = "assigned_to"
        completed_by = "completed_by"
        completed_dt = "date_completed"
        qc_checked = "qc_check_date"
        qc_rework = "qc_rework_required"
        qc_done = "qc_rework_completed"

        db = get_db()
        cur = db.cursor()
        cur.execute(f"""
            SELECT *
              FROM reviews
             WHERE {assign_col} = ? OR {completed_by} = ?
             ORDER BY updated_at DESC
        """, (user_id, user_id))
        all_rows = [dict(r) for r in cur.fetchall()]

        tasks = []
        for r in all_rows:
            # Check if task is in QC sampling
            task_id = r.get('task_id') or r.get('id')
            cur.execute("SELECT 1 FROM qc_sampling_log WHERE task_id = ?", (task_id,))
            in_qc_sampling = bool(cur.fetchone())
            r['_in_qc_sampling'] = in_qc_sampling
            
            # Preserve manually set statuses like "Referred to AI SME"
            raw_status = r.get('status', '')
            assigned_to = r.get('assigned_to')
            
            if raw_status and 'referred to ai sme' in raw_status.lower():
                status_text = raw_status  # Keep the manually set AI SME status
            # If task is assigned but status says "Unassigned", fix the mismatch
            elif assigned_to and raw_status and raw_status.lower() == 'unassigned':
                # Task is assigned but status is wrong - derive correct status
                from utils import derive_case_status
                status_text = str(derive_case_status(r))
            else:
                # Use best_status_with_raw_override to respect manually set statuses
                from utils import best_status_with_raw_override
                status_text = str(best_status_with_raw_override(r)) or raw_status or 'Unknown'
            last_touch = _parse_iso(r.get('updated_at')) or _parse_iso(r.get(completed_dt)) or _parse_iso(r.get("date_assigned"))
            
            t = {
                'task_id': r.get('task_id') or r.get('id'),
                'hit_type': r.get('hit_type') or r.get('type') or '',
                'total_score': r.get('total_score') or r.get('score') or '',
                'status': status_text,
                'updated_at': last_touch.isoformat() if last_touch else None,
            }
            tasks.append(t)

        me = int(user_id)

        def match_status(t):
            s = (t['status'] or '').lower().strip()
            r = next((row for row in all_rows if (row.get('task_id') or row.get('id')) == t['task_id']), {})
            assignee = r.get(assign_col)
            finisher = r.get(completed_by)
            is_assigned_to_me = (assignee == me) if assignee is not None else False
            is_completed_by_me = (finisher == me) if finisher is not None else False

            if not status_key:
                return is_assigned_to_me or is_completed_by_me

            # Special status filters to match dashboard logic
            if status_key in ('wip','in progress'):
                # Active WIP: assigned to me AND not completed
                # Should match dashboard Active WIP count
                if not is_assigned_to_me:
                    return False
                if s == 'completed':
                    return False
                # Include tasks counted in dashboard WIP
                # Include both "referred to sme" and "referred to ai sme"
                if any(x in s for x in ['pending review', 'rework', 'referred to sme', 'referred to ai sme', 'returned from sme', 'outreach', 'overdue', '7 day', '14 day', '21 day']):
                    return True
                if r.get(qc_rework) and not r.get(qc_done):
                    return True
                return False
                
            if status_key in ('completed',):
                # Match dashboard logic: completed_by = me AND DateSenttoQC exists
                # This counts tasks that have been submitted to QC (cases submitted)
                date_sent = r.get('DateSenttoQC')
                result = is_completed_by_me and bool(date_sent)
                print(f"[DEBUG COMPLETED] Task {t['task_id']}: completed_by_me={is_completed_by_me}, DateSenttoQC='{date_sent}', result={result}")
                return result
                
            if status_key in ('qc_checked','qc','qc-checked'):
                return is_completed_by_me and bool(r.get(qc_checked))
                
            if status_key in ('pending','pending review'):
                return is_assigned_to_me and ('pending review' in s)
                
            if status_key in ('rework','rework required', 'qc - rework required'):
                return is_assigned_to_me and bool(r.get(qc_rework)) and not bool(r.get(qc_done))
            
            # Special handling for "Referred to SME" to include AI SME referrals
            if status_key in ('referred to sme', 'sme_ref', 'sme-ref'):
                return is_assigned_to_me and ('referred to sme' in s or 'referred to ai sme' in s)
            
            # Special handling for QC-related statuses
            if status_key in ('qc waiting assignment', 'qc_waiting_assignment'):
                # QC Waiting Assignment: task is completed, in QC sampling, but not assigned to QC yet
                # Must be assigned to me (the reviewer who completed it)
                return is_assigned_to_me and s == 'qc waiting assignment'
            
            if status_key in ('qc pending review', 'qc_pending_review', 'awaiting qc'):
                # QC Pending Review: task is in QC sampling and assigned to QC
                return is_assigned_to_me and s in ('qc pending review', 'awaiting qc')
            
            # For ALL other statuses: exact match on derived status (case-insensitive)
            # This handles "7 Day Chaser Due", "Outreach", etc.
            if status_key == s:
                # Completed tasks: check completed_by
                if s == 'completed':
                    return is_completed_by_me
                # All other statuses: must be assigned to me
                return is_assigned_to_me
            
            return False

        filtered = [t for t in tasks if match_status(t)]
        
        print(f"[DEBUG] After status filter: {len(filtered)} tasks (from {len(tasks)} total)")
        print(f"[DEBUG] All tasks for user {user_id}:")
        for t in tasks[:15]:  # Show first 15
            r = next((row for row in all_rows if (row.get('task_id') or row.get('id')) == t['task_id']), {})
            assignee = r.get(assign_col)
            finisher = r.get(completed_by)
            print(f"  {t['task_id']}: status='{t['status']}' | assigned_to={assignee} | completed_by={finisher}")
        
        if filtered and len(filtered) <= 20:
            print(f"[DEBUG] Filtered tasks:")
            for ft in filtered:
                print(f"  - {ft['task_id']}: status={ft['status']}")

        if age_bucket_q:
            def _match_bucket(t):
                dt = _parse_iso(t['updated_at']) if t.get('updated_at') else None
                b = _bucket_from_dt(dt)
                return b == age_bucket_q
            filtered = [t for t in filtered if _match_bucket(t)]

        if date_range and date_range != 'all':
            def _apply_date_filter(t):
                r = next((row for row in all_rows if (row.get('task_id') or row.get('id')) == t['task_id']), {})
                # For completed tasks (cases submitted), use DateSenttoQC; for others, use updated_at
                if status_key == 'completed' and r.get('DateSenttoQC'):
                    return _in_range(_parse_iso(r.get('DateSenttoQC')))
                return _in_range(_parse_iso(t.get('updated_at')))
            filtered = [t for t in filtered if _apply_date_filter(t)]

        if date_filter == 'today':
            today_str = today.isoformat()
            filtered = [t for t in filtered if t.get('updated_at', '').startswith(today_str)]
        elif date_filter == 'week':
            filtered = [t for t in filtered if _in_range(_parse_iso(t.get('updated_at')))]

        # Filter by chaser cycle (overdue, chaser_type, or week_date)
        if overdue_flg == '1' or chaser_type or week_date:
            DUE_MAP = {
                "7": ["Chaser1DueDate", "Chaser_1_DueDate", "chaser1_due", "chaser_1_due", "Outreach1DueDate", "Outreach_Cycle_1_Due"],
                "14": ["Chaser2DueDate", "Chaser_2_DueDate", "chaser2_due", "chaser_2_due", "Outreach2DueDate", "Outreach_Cycle_2_Due"],
                "21": ["Chaser3DueDate", "Chaser_3_DueDate", "chaser3_due", "chaser_3_due", "Outreach3DueDate", "Outreach_Cycle_3_Due"],
                "NTC": ["NTCDueDate", "NTC_DueDate", "ntc_due", "NTC Due Date", "NTC_Due"]
            }
            ISSUED_MAP = {
                "7": ["Chaser1IssuedDate", "Chaser1DateIssued", "chaser1_issued", "Outreach1Date", "Outreach_Cycle_1_Issued", "Outreach Cycle 1 Issued"],
                "14": ["Chaser2IssuedDate", "Chaser2DateIssued", "chaser2_issued", "Outreach2Date", "Outreach_Cycle_2_Issued", "Outreach Cycle 2 Issued"],
                "21": ["Chaser3IssuedDate", "Chaser3DateIssued", "chaser3_issued", "Outreach3Date", "Outreach_Cycle_3_Issued", "Outreach Cycle 3 Issued"],
                "NTC": ["NTCIssuedDate", "NTC_IssuedDate", "ntc_issued"]
            }
            
            def _coalesce_key(rec, keys):
                for k in keys:
                    if k in rec and str(rec.get(k) or "").strip():
                        return k
                return None
            
            def _parse_date_any(s):
                if not s:
                    return None
                s = str(s).strip()
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(s, fmt).date()
                    except:
                        continue
                try:
                    from dateutil import parser
                    return parser.parse(s).date()
                except:
                    pass
                return None
            
            def _is_blank_issued(v):
                if v is None:
                    return True
                s = str(v).strip().lower()
                return s in ("", "none", "null", "n/a", "na", "-", "0", "false")
            
            def _is_chaser_issued(rec, chaser_type):
                """Check if a chaser type has been issued"""
                ik = _coalesce_key(rec, ISSUED_MAP.get(chaser_type, []))
                if ik:
                    return not _is_blank_issued(rec.get(ik))
                return False
            
            def _matches_chaser_filter(t):
                r = next((row for row in all_rows if (row.get('task_id') or row.get('id')) == t['task_id']), {})
                assignee = r.get(assign_col)
                if assignee != me:
                    return False
                
                # Skip if outreach is completed
                outreach_complete = r.get('outreach_complete') or r.get('OutreachComplete')
                if outreach_complete in (1, '1', True, 'true', 'True'):
                    return False
                
                # Check chasers sequentially: 7 → 14 → 21 → NTC
                # Only show the NEXT chaser that needs to be issued
                chaser_sequence = ["7", "14", "21", "NTC"]
                next_chaser_type = None
                next_chaser_due_date = None
                
                # First, find the NEXT unissued chaser for this task
                for typ in chaser_sequence:
                    # Check if all previous chasers have been issued
                    if typ == "7":
                        # 7-day chaser: no prerequisites
                        prev_issued = True
                    elif typ == "14":
                        # 14-day chaser: 7-day must be issued
                        prev_issued = _is_chaser_issued(r, "7")
                    elif typ == "21":
                        # 21-day chaser: 7-day and 14-day must be issued
                        prev_issued = _is_chaser_issued(r, "7") and _is_chaser_issued(r, "14")
                    elif typ == "NTC":
                        # NTC: 7-day, 14-day, and 21-day must be issued
                        prev_issued = _is_chaser_issued(r, "7") and _is_chaser_issued(r, "14") and _is_chaser_issued(r, "21")
                    else:
                        prev_issued = False
                    
                    # Skip if previous chasers haven't been issued
                    if not prev_issued:
                        continue
                    
                    # Check if this chaser has been issued (if so, move to next)
                    if _is_chaser_issued(r, typ):
                        continue  # Already issued, check next chaser
                    
                    # Get due date for this chaser
                    k = _coalesce_key(r, DUE_MAP.get(typ, []))
                    if not k:
                        continue
                    due_date = _parse_date_any(r.get(k))
                    if not due_date:
                        continue
                    
                    # Found the next chaser - store it and break
                    next_chaser_type = typ
                    next_chaser_due_date = due_date
                    break
                
                # If no next chaser found, don't show this task
                if not next_chaser_type:
                    return False
                
                # Now check if this next chaser matches the filter criteria
                # If chaser_type is specified, must match exactly
                if chaser_type:
                    if next_chaser_type != chaser_type:
                        return False
                
                # Check date conditions
                # Priority: week_date > overdue > default (show if overdue)
                
                if week_date:
                    # If week_date is provided, must be in that week
                    try:
                        week_dt = datetime.fromisoformat(week_date).date()
                        week_monday = week_dt - timedelta(days=week_dt.weekday())
                        week_friday = week_monday + timedelta(days=4)
                        if week_monday <= next_chaser_due_date <= week_friday:
                            return True
                    except:
                        pass
                    return False
                elif overdue_flg == '1':
                    # If overdue flag is set, must be overdue
                    if next_chaser_due_date < today:
                        return True
                    return False
                else:
                    # If no date filters specified but chaser_type is set, show if overdue (default behavior)
                    if next_chaser_due_date < today:
                        return True
                    return False
            
            filtered = [t for t in filtered if _matches_chaser_filter(t)]
            print(f"[DEBUG] After chaser filter (overdue={overdue_flg}, chaser_type={chaser_type}): {len(filtered)} tasks")

        db.close()

        return jsonify({
            'tasks': filtered,
            'total': len(filtered),
        })
    except Exception as e:
        app.logger.exception("Error in api_my_tasks: %s", e)
        return jsonify({'error': str(e)}), 500

# --- Outreach Complete toggle endpoint ---
@csrf.exempt
@app.route('/api/outreach/<task_id>/complete', methods=['POST'])
def api_outreach_complete(task_id):
    try:
        from flask import request, redirect, jsonify
    except Exception:
        # In case imports are structured differently
        pass

    # Determine intended boolean from submitted values
    vals = request.form.getlist('outreach_complete')
    is_complete = 1 if ('1' in vals or request.form.get('outreach_complete') in ['1','true','True','on']) else 0

    # Update DB
    conn = None
    cur = None
    used_get_db = False
    try:
        # Prefer app's own get_db() if available
        if 'get_db' in globals():
            conn = get_db()
            used_get_db = True
        else:
            import sqlite3, os
            db_path = app.config.get('DATABASE') or os.environ.get('DATABASE') or 'scrutinise.db'
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check if task is in SME referral status - block all status changes
        is_locked, error_msg = is_task_in_sme_referral_status(task_id, conn)
        if is_locked:
            if used_get_db:
                conn.close()
            else:
                conn.close()
            return jsonify({"ok": False, "error": error_msg}), 403
        
        # If marking as complete, update status to "Outreach Complete"
        if is_complete:
            # Update outreach_complete and set status to "Outreach Complete"
            cur.execute(
                "UPDATE reviews SET outreach_complete = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (is_complete, 'Outreach Complete', task_id)
            )
        else:
            # If unchecking, just update the field
            cur.execute("UPDATE reviews SET outreach_complete = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?", (is_complete, task_id))
        
        conn.commit()
    except Exception as e:
        try:
            # Provide JSON error if ajax; otherwise raise
            return jsonify({"ok": False, "error": str(e)}), 500
        except Exception:
            raise
    finally:
        try:
            if cur: cur.close()
        except Exception:
            pass
        try:
            if conn and not used_get_db:
                conn.close()
        except Exception:
            pass

    # Redirect back to the panel if return_to provided, else JSON
    ret = request.form.get('return_to')
    if ret:
        return redirect(ret)
    try:
        return jsonify({"ok": True, "task_id": task_id, "outreach_complete": bool(is_complete)})
    except Exception:
        # Fallback to simple redirect to reviewer panel if jsonify is unavailable
        return redirect(f"/review/{task_id}")

# ========= Additional API Endpoints for React Frontend =========

@app.route('/api/team_leader_dashboard', methods=['GET'])
@role_required('team_lead_1', 'team_lead_2', 'team_lead_3')
def api_team_leader_dashboard():
    """Return Team Leader dashboard data as JSON"""
    try:
        from datetime import datetime, timedelta
        import sqlite3
        
        # Get level and team lead info
        role = session.get('role', '').lower()
        level = int(role.split('_')[-1]) if role.startswith('team_lead_') else 1
        team_lead = session.get('email', '').split('@')[0]
        
        date_range = request.args.get("date_range", "wtd")
        
        today = datetime.utcnow().date()
        monday_this = today - timedelta(days=today.weekday())
        monday_prev = monday_this - timedelta(days=7)
        sunday_prev = monday_this - timedelta(days=1)
        
        def _within_range(dt_str):
            if not dt_str:
                return False
            try:
                dt = datetime.fromisoformat(str(dt_str).replace('Z', '').split('.')[0])
                d = dt.date()
                if date_range == "wtd": return monday_this <= d <= today
                if date_range == "prevw": return monday_prev <= d <= sunday_prev
                if date_range == "30d": return d >= (today - timedelta(days=30))
                return True
            except:
                return False
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get team reviewers
        cur.execute("""
            SELECT id, name, email
            FROM users
            WHERE role = ? AND LOWER(team_lead) = LOWER(?)
            ORDER BY name
        """, (f"reviewer_{level}", team_lead))
        reviewers = [dict(r) for r in cur.fetchall()]
        r_ids = [r["id"] for r in reviewers] or [-1]
        
        assign_col = "assigned_to"
        completed_dt = "date_completed"
        # Use level-specific QC columns
        qc_outcome_col = f"l{level}_qc_outcome"
        qc_chk_col = f"l{level}_qc_check_date"
        
        # Total Active WIP
        placeholders = ','.join('?' * len(r_ids))
        cur.execute(f"""
            SELECT COUNT(*) AS count
            FROM reviews
            WHERE {assign_col} IN ({placeholders})
              AND ({completed_dt} IS NULL OR {completed_dt} = '')
        """, r_ids)
        total_active_wip = cur.fetchone()['count'] or 0
        
        # Completed count
        cur.execute(f"""
            SELECT COUNT(*) AS count
            FROM reviews
            WHERE {assign_col} IN ({placeholders})
              AND {completed_dt} IS NOT NULL AND {completed_dt} != ''
        """, r_ids)
        all_completed = [dict(r) for r in cur.execute(f"SELECT {completed_dt} FROM reviews WHERE {assign_col} IN ({placeholders})", r_ids).fetchall()]
        completed_count = sum(1 for r in all_completed if _within_range(r.get(completed_dt)))
        
        # QC stats - calculate pass percentage from actual QC outcomes
        # Get all QC outcomes for this team's reviews (date-filtered on QC check date)
        qc_sql = f"""
            SELECT LOWER(TRIM(COALESCE({qc_outcome_col}, ''))) AS outcome
            FROM reviews
            WHERE {assign_col} IN ({placeholders})
              AND {qc_chk_col} IS NOT NULL AND {qc_chk_col} != ''
        """
        qc_params = r_ids.copy()
        
        # Apply date filter on QC check date
        if date_range == "wtd":
            qc_sql += f" AND date({qc_chk_col}) BETWEEN ? AND ?"
            qc_params += [monday_this.isoformat(), today.isoformat()]
        elif date_range == "prevw":
            qc_sql += f" AND date({qc_chk_col}) BETWEEN ? AND ?"
            qc_params += [monday_prev.isoformat(), sunday_prev.isoformat()]
        elif date_range == "30d":
            qc_sql += f" AND {qc_chk_col} >= datetime('now','-30 days')"
        
        cur.execute(qc_sql, qc_params)
        qc_outcomes = [(row[0] or "").strip() for row in cur.fetchall()]
        qc_sample = len(qc_outcomes)
        
        # Count passes (Pass or Pass With Feedback)
        qc_pass_cnt = sum(1 for o in qc_outcomes if o in ("pass", "pass with feedback"))
        qc_pass_pct = round((qc_pass_cnt / qc_sample) * 100, 1) if qc_sample > 0 else 0.0
        
        conn.close()
        
        return jsonify({
            'level': level,
            'team_lead_name': team_lead,
            'selected_date': date_range,
            'total_active_wip': total_active_wip,
            'completed_count': completed_count,
            'qc_sample': qc_sample,
            'qc_pass_pct': qc_pass_pct,
            'reviewers': reviewers
        })
    except Exception as e:
        import traceback
        print(f"Error in api_team_leader_dashboard: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sme_dashboard', methods=['GET'])
@role_required('sme', 'admin')
def api_sme_dashboard():
    """Return SME dashboard data as JSON"""
    try:
        from datetime import datetime, timedelta
        from collections import defaultdict
        import sqlite3
        
        date_range = request.args.get("date_range", "wtd")
        today = datetime.utcnow().date()
        monday_this = today - timedelta(days=today.weekday())
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT *
            FROM reviews
            WHERE l1_referred_to_sme IS NOT NULL
               OR l2_referred_to_sme IS NOT NULL
               OR l3_referred_to_sme IS NOT NULL
            ORDER BY updated_at DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        
        open_queue = sum(1 for r in rows if not any([
            r.get("sme_returned_date"),
            r.get("sme_returned_date"),
            r.get("sme_returned_date")
        ]))
        
        total_new_referrals = len(rows)
        total_returned = sum(1 for r in rows if any([
            r.get("sme_returned_date"),
            r.get("sme_returned_date"),
            r.get("sme_returned_date")
        ]))
        
        avg_tat = 3.5  # Placeholder
        
        returns_per_day = defaultdict(int)
        for r in rows:
            for lv in (1, 2, 3):
                ret_date = r.get(f'l{lv}_sme_returned_date')
                if ret_date:
                    returns_per_day[ret_date[:10]] += 1
        
        daily_labels = sorted(returns_per_day.keys())[-7:]
        daily_counts = [returns_per_day[d] for d in daily_labels]
        
        return jsonify({
            'selected_date': date_range,
            'open_queue': open_queue,
            'total_new_referrals': total_new_referrals,
            'total_returned': total_returned,
            'avg_tat': avg_tat,
            'daily_labels': daily_labels,
            'daily_counts': daily_counts
        })
    except Exception as e:
        import traceback
        print(f"Error in api_sme_dashboard: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users', methods=['GET'])
@role_required('admin')
def api_list_users():
    """Return list of users as JSON with optional filtering"""
    # Check permission
    if not check_permission('edit_users', 'view'):
        return jsonify({'error': 'Permission denied: You do not have permission to view users'}), 403
    try:
        sort_order = request.args.get('sort', 'desc')
        inactive_days = request.args.get('inactive_days', '')
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Start base query
        query = """
            SELECT id, email, name, role, team_lead, level, status, last_active, password_changed_at,
                   two_factor_enabled
            FROM users
        """
        filters = []
        params = []
        
        # Inactive filter
        if inactive_days and inactive_days.isdigit():
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=int(inactive_days))
            filters.append("(last_active IS NULL OR last_active < ?)")
            params.append(cutoff.strftime("%Y-%m-%d %H:%M:%S"))
        
        if filters:
            query += " WHERE " + " AND ".join(filters)
        
        # Sorting
        if sort_order == "asc":
            query += " ORDER BY last_active ASC"
        else:
            query += " ORDER BY last_active DESC"
        
        cur.execute(query, params)
        users = [dict(r) for r in cur.fetchall()]
        conn.close()
        
        return jsonify({'users': users})
    except Exception as e:
        import traceback
        print(f"Error in api_list_users: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/admin/users/<int:user_id>/toggle_2fa', methods=['POST'])
@role_required('admin')
def api_toggle_2fa(user_id):
    """Toggle 2FA for a user (admin only, excludes admin@scrutinise.co.uk)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get user
        cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent toggling 2FA for admin@scrutinise.co.uk
        if user['email'].lower().strip() == 'admin@scrutinise.co.uk':
            conn.close()
            return jsonify({'error': 'Cannot modify 2FA for this user'}), 403
        
        # Toggle 2FA
        cursor.execute("""
            UPDATE users 
            SET two_factor_enabled = CASE 
                WHEN two_factor_enabled = 1 THEN 0 
                ELSE 1 
            END
            WHERE id = ?
        """, (user_id,))
        conn.commit()
        
        # Get updated status
        cursor.execute("SELECT two_factor_enabled FROM users WHERE id = ?", (user_id,))
        updated = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'success': True,
            'two_factor_enabled': bool(updated['two_factor_enabled'])
        })
    except Exception as e:
        import traceback
        print(f"Error in api_toggle_2fa: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reviewer_panel/<task_id>', methods=['GET'])
@role_required("reviewer_1", "reviewer_2", "reviewer_3", "qc_1", "qc_2", "qc_3", "qc_review_1", "qc_review_2", "qc_review_3", "sme", "operations_manager", "admin", "team_lead_1", "team_lead_2", "team_lead_3", "qa_1", "qa_2", "qa_3")
def api_reviewer_panel(task_id):
    """Return reviewer panel data as JSON"""
    # Check if Due Diligence module is enabled
    if not is_module_enabled('due_diligence'):
        return jsonify({'error': 'Due Diligence module is currently disabled'}), 403
    try:
        import sqlite3
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Load review
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Review not found'}), 404
        
        review = dict(row)
        
        # Load match data (contains customer info)
        cur.execute("SELECT * FROM matches WHERE task_id = ?", (task_id,))
        match_row = cur.fetchone()
        match = dict(match_row) if match_row else {}
        
        # Merge match data into review for compatibility
        review.update(match)
        
        # Get all users for ID to name mapping
        cur.execute("SELECT id, name, email FROM users")
        users = {row['id']: (row['name'] or row['email']) for row in cur.fetchall()}
        
        # Map user IDs to names for assigned_to fields (single-level system)
        if review.get("assigned_to"):
            user_id = review["assigned_to"]
            review["assigned_to_name"] = users.get(user_id, f"User #{user_id}")
        else:
            review["assigned_to_name"] = "Unassigned"
        
        if review.get("completed_by"):
            user_id = review["completed_by"]
            review["completed_by_name"] = users.get(user_id, f"User #{user_id}")
        
        if review.get("qc_assigned_to"):
            user_id = review["qc_assigned_to"]
            review["qc_assigned_to_name"] = users.get(user_id, f"User #{user_id}")
        
        # Merge ALL match fields into review (don't hardcode field names)
        # This ensures all customer details, watchlist info, scores, etc. are available
        if match:
            for key, value in match.items():
                if key not in review or review[key] is None:
                    review[key] = value
        
        # Check if task is in QC sampling
        cur.execute("SELECT COUNT(*) FROM qc_sampling_log WHERE review_id = (SELECT id FROM reviews WHERE task_id = ?)", (task_id,))
        in_qc_sampling = cur.fetchone()[0] > 0
        review['_in_qc_sampling'] = in_qc_sampling
        
        # Re-derive the status to ensure it's up-to-date
        # But preserve manually set statuses like "Referred to AI SME"
        from utils import derive_case_status, best_status_with_raw_override
        raw_status = review.get('status', '')
        assigned_to = review.get('assigned_to')
        
        # If status is "Referred to AI SME", preserve it (don't override)
        if raw_status and 'referred to ai sme' in raw_status.lower():
            review['status'] = raw_status  # Keep the manually set AI SME status
        # If task is assigned but status says "Unassigned", fix the mismatch by deriving correct status
        elif assigned_to and raw_status and raw_status.lower() == 'unassigned':
            # Task is assigned but status is wrong - derive correct status
            final_status = derive_case_status(review)
            review['status'] = str(final_status)
        else:
            # Use best_status_with_raw_override to respect manually set statuses
            final_status = best_status_with_raw_override(review)
            review['status'] = str(final_status)
        
        # Get outcomes
        try:
            outcome_names = _load_outcomes_from_db(cur)
        except:
            outcome_names = ["Retain", "Exit - Financial Crime", "Exit - Non-responsive", "Exit - T&C"]
        
        outcomes = [{"name": n} for n in outcome_names]
        
        conn.close()
        
        return jsonify({
            'review': review,
            'match': match,
            'task_id': task_id,
            'outcomes': outcomes,
            'users': users  # Include user mapping for frontend
        })
    except Exception as e:
        import traceback
        print(f"Error in api_reviewer_panel: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/assign_tasks', methods=['GET', 'POST'])
@role_required('team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager', 'admin')
def api_assign_tasks():
    """Get unassigned tasks or assign tasks to reviewers"""
    # Check permission
    if not check_permission('assign_tasks', 'edit'):
        return jsonify({'error': 'Permission denied: You do not have permission to assign tasks'}), 403
    try:
        if request.method == 'GET':
            # Get unassigned tasks and available reviewers
            conn = get_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # Determine level from user role
            user_role = session.get("role", "")
            user_id = session.get("user_id")
            
            cur.execute("SELECT name, role FROM users WHERE id = ?", (user_id,))
            lead_user = cur.fetchone()
            if not lead_user:
                return jsonify({'error': 'Unable to identify user'}), 400
            
            lead_name = lead_user["name"]
            lead_role_parts = lead_user["role"].split("_")
            level = lead_role_parts[-1] if lead_role_parts[-1] in ("1", "2", "3") else "1"
            
            # Get unassigned tasks (single-level system)
            cur.execute("""
                SELECT r.id, r.task_id, r.updated_at
                FROM reviews r
                WHERE r.assigned_to IS NULL OR r.assigned_to = 0
                ORDER BY r.updated_at DESC
                LIMIT 100
            """)
            unassigned_tasks = [dict(row) for row in cur.fetchall()]
            
            # Get available reviewers (Ops = all reviewers; TL = own team)
            is_ops = (user_role or "").lower() in ("operations_manager", "operations manager", "admin")
            if is_ops:
                cur.execute("""
                    SELECT id, COALESCE(name,email) AS name, role
                    FROM users
                    WHERE role LIKE 'reviewer_%'
                      AND (status IS NULL OR status = 'active')
                    ORDER BY name COLLATE NOCASE
                """)
            else:
                cur.execute("""
                    SELECT id, COALESCE(name,email) AS name, role
                    FROM users
                    WHERE role LIKE 'reviewer_%' AND LOWER(team_lead) = LOWER(?)
                      AND (status IS NULL OR status = 'active')
                    ORDER BY name COLLATE NOCASE
                """, (lead_name,))
            reviewers_raw = cur.fetchall()
            
            # Get open tasks count for each reviewer (single-level system)
            reviewers = []
            assignment_counts = {}
            for row in reviewers_raw:
                reviewer_id = row["id"]
                cur.execute("""
                    SELECT COUNT(*) FROM reviews
                    WHERE assigned_to = ? AND date_completed IS NULL
                """, (reviewer_id,))
                open_tasks = cur.fetchone()[0]
                reviewers.append({
                    "id": reviewer_id,
                    "name": row["name"],
                    "role": row["role"],
                    "open_tasks": open_tasks
                })
                assignment_counts[reviewer_id] = open_tasks
            
            # Count unassigned tasks (single-level system)
            cur.execute("""
                SELECT COUNT(*) FROM reviews
                WHERE assigned_to IS NULL OR assigned_to = 0
            """)
            unassigned_count = cur.fetchone()[0]
            
            conn.close()
            
            return jsonify({
                'unassigned_tasks': unassigned_tasks,
                'reviewers': reviewers,
                'assignment_counts': assignment_counts,
                'unassigned_count': unassigned_count
            })
        
        else:  # POST
            data = request.json
            task_ids = data.get('task_ids', [])
            reviewer_id = data.get('reviewer_id')
            
            if not task_ids or not reviewer_id:
                return jsonify({'error': 'Missing task_ids or reviewer_id'}), 400
            
            conn = get_db()
            cur = conn.cursor()
            
            # Assign tasks (single-level system)
            for task_id in task_ids:
                cur.execute("""
                    UPDATE reviews
                    SET assigned_to = ?, date_assigned = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (reviewer_id, task_id))
                
                # Re-derive status to update task status after assignment
                cur.execute("SELECT * FROM reviews WHERE id = ?", (task_id,))
                rev = cur.fetchone()
                if rev:
                    rev_dict = dict(rev)
                    from utils import derive_case_status
                    new_status = derive_case_status(rev_dict)
                    cur.execute("UPDATE reviews SET status = ? WHERE id = ?", (str(new_status), task_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': f'{len(task_ids)} task(s) assigned successfully'})
            
    except Exception as e:
        import traceback
        print(f"Error in api_assign_tasks: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sme_review/<task_id>', methods=['GET', 'POST'])
@role_required('sme', 'admin')
def api_sme_review(task_id):
    """Get SME review data or submit SME advice"""
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        if request.method == 'GET':
            # Get task data for SME review
            cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return jsonify({'error': 'Task not found'}), 404
            
            review = dict(row)
            conn.close()
            
            return jsonify({
                'review': review,
                'task_id': task_id
            })
        
        else:  # POST
            data = request.json
            advice = data.get('advice', '')
            action = data.get('action', 'save')  # 'save' or 'return'
            
            user_id = session.get('user_id')
            
            # Determine which level this SME referral is for
            cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
            review = dict(cur.fetchone() or {})
            
            # Find which level has the SME referral (simplified)
            level = 1
            for lv in (1, 2, 3):
                if review.get(f'l{lv}_referred_to_sme'):
                    level = lv
                    break
            
            if action == 'return':
                # Return to reviewer with advice
                cur.execute(f"""
                    UPDATE reviews
                    SET l{level}_sme_advice = ?,
                        l{level}_sme_returned_date = CURRENT_TIMESTAMP,
                        l{level}_sme_advice_by = ?
                    WHERE task_id = ?
                """, (advice, user_id, task_id))
            else:
                # Just save the advice
                cur.execute(f"""
                    UPDATE reviews
                    SET l{level}_sme_advice = ?,
                        l{level}_sme_advice_by = ?
                    WHERE task_id = ?
                """, (advice, user_id, task_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True})
            
    except Exception as e:
        import traceback
        print(f"Error in api_sme_review: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/user/<int:user_id>', methods=['GET', 'POST', 'DELETE'], endpoint='api_edit_user')
@csrf.exempt
def api_edit_user(user_id):
    """Get, update, or delete user data"""
    # Check permission
    if request.method == 'GET':
        if not check_permission('edit_users', 'view'):
            return jsonify({'error': 'Permission denied: You do not have permission to view users'}), 403
    elif request.method in ['POST', 'DELETE']:
        if not check_permission('edit_users', 'edit'):
            return jsonify({'error': 'Permission denied: You do not have permission to edit users'}), 403
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        if request.method == 'GET':
            # Get user data
            cur.execute("SELECT id, name, email, role, team_lead FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return jsonify({'error': 'User not found'}), 404
            
            user = dict(row)
            
            # Get available leads
            cur.execute("""
                SELECT name FROM users
                WHERE role LIKE 'team_lead_%'
                   OR role LIKE 'qc_%'
                   OR role LIKE 'qa_%'
                   OR role IN ('operations_manager', 'admin')
                ORDER BY name
            """)
            leads = [{"name": r["name"]} for r in cur.fetchall() if r["name"]]
            
            conn.close()
            return jsonify({'user': user, 'leads': leads})
        
        elif request.method == 'POST':
            data = request.json
            name = data.get('name', '').strip()
            email = data.get('email', '').strip().lower()
            role = data.get('role', '').strip()
            team_lead = data.get('team_lead', '').strip() or None
            
            if not name or not email or not role:
                return jsonify({'error': 'Name, email, and role are required'}), 400
            
            # Derive level from role
            level = None
            parts = role.split('_')
            if len(parts) >= 2 and parts[-1].isdigit():
                level = int(parts[-1])
            
            # Update user
            cur.execute("""
                UPDATE users
                SET name = ?, email = ?, role = ?, team_lead = ?, level = ?
                WHERE id = ?
            """, (name, email, role, team_lead, level, user_id))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'User updated successfully'})
        
        elif request.method == 'DELETE':
            # Delete user
            cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'User deleted successfully'})
            
    except Exception as e:
        import traceback
        print(f"Error in api_edit_user: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/leads', methods=['GET'], endpoint='api_get_leads')
def api_get_leads():
    """Get list of team leads for dropdowns"""
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT name FROM users
            WHERE role LIKE 'team_lead_%'
               OR role LIKE 'qc_%'
               OR role LIKE 'qa_%'
               OR role IN ('operations_manager', 'admin')
            ORDER BY name
        """)
        leads = [{"name": r["name"]} for r in cur.fetchall() if r["name"]]
        
        conn.close()
        return jsonify({'leads': leads})
    except Exception as e:
        import traceback
        print(f"Error in api_get_leads: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/assign_tasks_bulk', methods=['GET', 'POST'], endpoint='api_assign_tasks_bulk')
@role_required('team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager', 'admin')
def api_assign_tasks_bulk():
    """Assign tasks in bulk to multiple reviewers"""
    # Check permission
    if not check_permission('assign_tasks', 'edit'):
        return jsonify({'error': 'Permission denied: You do not have permission to assign tasks'}), 403
    try:
        user_role = session.get("role")
        user_id = session.get("user_id")
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get lead user info
        cur.execute("SELECT name, role FROM users WHERE id = ?", (user_id,))
        lead_user = cur.fetchone()
        if not lead_user:
            return jsonify({'error': 'Unable to identify user'}), 400
        
        lead_name = lead_user["name"]
        lead_role_parts = lead_user["role"].split("_")
        level = lead_role_parts[-1] if lead_role_parts[-1] in ("1", "2", "3") else "1"
        
        if request.method == 'GET':
            # Load reviewers (Ops = all reviewers; TL = own team)
            is_ops = (user_role or "").lower() in ("operations_manager", "operations manager")
            if is_ops:
                cur.execute("""
                    SELECT id, COALESCE(name,email) AS name, role
                    FROM users
                    WHERE role = ?
                      AND (status IS NULL OR status = 'active')
                    ORDER BY name COLLATE NOCASE
                """, (f"reviewer_{level}",))
            else:
                cur.execute("""
                    SELECT id, COALESCE(name,email) AS name, role
                    FROM users
                    WHERE role = ? AND LOWER(team_lead) = LOWER(?)
                      AND (status IS NULL OR status = 'active')
                    ORDER BY name COLLATE NOCASE
                """, (f"reviewer_{level}", lead_name))
            reviewers_raw = cur.fetchall()
            
            # Get open tasks count for each reviewer (single-level system)
            reviewers = []
            for row in reviewers_raw:
                reviewer_id = row["id"]
                cur.execute("""
                    SELECT COUNT(*) FROM reviews
                    WHERE assigned_to = ? AND date_completed IS NULL
                """, (reviewer_id,))
                open_tasks = cur.fetchone()[0]
                reviewers.append({
                    "id": reviewer_id,
                    "name": row["name"],
                    "role": row["role"],
                    "open_tasks": open_tasks,
                    "level": level
                })
            
            # Count unassigned tasks (single-level system)
            cur.execute("""
                SELECT COUNT(*) FROM reviews
                WHERE assigned_to IS NULL OR assigned_to = 0
            """)
            unassigned_count = cur.fetchone()[0]
            
            conn.close()
            return jsonify({
                'reviewers': reviewers,
                'unassigned_count': unassigned_count,
                'selected_level': level
            })
        
        else:  # POST
            data = request.json
            selected_reviewers = data.get('selected_reviewers', [])
            task_count = int(data.get('task_count', 5))
            priority = data.get('priority', 'score')
            
            if not selected_reviewers:
                return jsonify({'error': 'Please select at least one reviewer'}), 400
            
            # Fetch unassigned tasks (single-level system)
            order_by = "m.total_score DESC" if priority == "score" else "r.updated_at ASC"
            cur.execute(f"""
                SELECT r.id
                FROM reviews r
                LEFT JOIN matches m ON m.task_id = r.task_id
                WHERE assigned_to IS NULL OR assigned_to = 0
                ORDER BY {order_by}
                LIMIT ?
            """, (task_count * len(selected_reviewers),))
            unassigned_tasks = [row["id"] for row in cur.fetchall()]
            
            if not unassigned_tasks:
                conn.close()
                return jsonify({'error': 'No unassigned tasks available'}), 400
            
            # Distribute tasks evenly among reviewers
            assignments_made = 0
            for i, task_id in enumerate(unassigned_tasks):
                reviewer_id = selected_reviewers[i % len(selected_reviewers)]
                
                # Update assigned_to field (single-level system)
                cur.execute(
                    "UPDATE reviews SET assigned_to = ?, date_assigned = CURRENT_TIMESTAMP WHERE id = ?",
                    (reviewer_id, task_id)
                )
                
                # Re-derive status to update task status
                cur.execute("SELECT * FROM reviews WHERE id = ?", (task_id,))
                rev = dict(cur.fetchone())
                if rev:
                    from utils import derive_case_status
                    new_status = derive_case_status(rev)
                    cur.execute("UPDATE reviews SET status = ? WHERE id = ?", (str(new_status), task_id))
                
                assignments_made += 1
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'{assignments_made} tasks assigned to {len(selected_reviewers)} reviewer(s)'
            })
            
    except Exception as e:
        import traceback
        print(f"Error in api_assign_tasks_bulk: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/operations/dashboard', methods=['GET'], endpoint='api_operations_dashboard')
@role_required('operations_manager', 'admin')
def api_operations_dashboard():
    """Return operations manager dashboard data as JSON"""
    # Check permission
    if not check_permission('view_dashboard', 'view'):
        return jsonify({'error': 'Permission denied: You do not have permission to view dashboard'}), 403
    try:
        # Use the existing mi_dashboard logic but return JSON
        date_range = request.args.get("date_range", "all")
        selected_team = request.args.get("team", "all")
        selected_level = request.args.get("level", "all")
        
        from datetime import datetime, timedelta, date
        
        today = datetime.utcnow().date()
        monday_this = today - timedelta(days=today.weekday())
        monday_prev = monday_this - timedelta(days=7)
        sunday_prev = monday_this - timedelta(days=1)
        
        db = get_db()
        cur = db.cursor()
        
        # Build Teams dropdown
        cur.execute("""
            SELECT DISTINCT team_lead
            FROM users
            WHERE team_lead IS NOT NULL AND team_lead <> ''
            ORDER BY team_lead
        """)
        teams = [{"label": "All Teams", "value": "all"}] + [
            {"label": row["team_lead"], "value": row["team_lead"]}
            for row in cur.fetchall()
        ]
        
        # Date range filtering
        def get_date_range_bounds(date_range_str):
            """Get start and end dates for the given date range"""
            today = datetime.utcnow().date()
            if date_range_str == "wtd":  # Current Week
                monday = today - timedelta(days=today.weekday())
                return monday, today + timedelta(days=1)  # Include today
            elif date_range_str == "prevw":  # Previous Week
                monday_this = today - timedelta(days=today.weekday())
                monday_prev = monday_this - timedelta(days=7)
                sunday_prev = monday_this - timedelta(days=1)
                return monday_prev, sunday_prev + timedelta(days=1)
            elif date_range_str == "30d":  # Last 30 Days
                start = today - timedelta(days=29)
                return start, today + timedelta(days=1)
            else:  # "all" or unknown
                return None, None
        
        date_start, date_end = get_date_range_bounds(date_range)
        
        # Get reviews with team and date filter (updated for single-level fields)
        pop_sql = """
            SELECT r.*
            FROM reviews r
            LEFT JOIN users u ON u.id = r.assigned_to
            WHERE 1=1
        """
        pop_params = []
        if selected_team != "all":
            pop_sql += " AND u.team_lead = ?"
            pop_params.append(selected_team)
        
        # Apply date range filter - filter by date_completed for completed tasks, or date_assigned for active tasks
        # Note: We don't use updated_at because tasks completed long ago but updated recently shouldn't appear
        if date_start and date_end:
            pop_sql += """ AND (
                (r.date_completed IS NOT NULL AND r.date_completed <> '' 
                 AND date(r.date_completed) >= date(?) AND date(r.date_completed) < date(?))
                OR
                ((r.date_completed IS NULL OR r.date_completed = '')
                 AND r.date_assigned IS NOT NULL AND r.date_assigned <> '' 
                 AND date(r.date_assigned) >= date(?) AND date(r.date_assigned) < date(?))
            )"""
            pop_params.extend([
                date_start.isoformat(), date_end.isoformat(),  # For completed tasks
                date_start.isoformat(), date_end.isoformat()   # For date_assigned (active tasks)
            ])
        
        cur.execute(pop_sql, pop_params)
        reviews_base = [dict(r) for r in cur.fetchall()]
        
        # Total Population
        total_screened = len(reviews_base)
        
        # Total Completed
        total_completed = sum(1 for r in reviews_base 
                             if str(r.get('status', '')).strip().lower() in ('complete', 'completed'))
        
        # QC Sample and Pass Rate (updated for single-level fields)
        qc_sample = 0
        pass_qc = 0
        for r in reviews_base:
            qc_outcome = r.get("qc_outcome")
            if qc_outcome:
                qc_sample += 1
                if str(qc_outcome).lower().startswith("pass"):
                    pass_qc += 1
        
        qc_pass_pct = round((pass_qc / qc_sample) * 100, 1) if qc_sample else 0
        
        # Case Status Distribution with Age Buckets
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        status_counts = defaultdict(int)
        age_by_status = defaultdict(lambda: defaultdict(int))
        
        def calc_age_days(r):
            """Calculate age in days since updated_at or date_assigned"""
            dt_str = r.get('updated_at') or r.get("date_assigned")
            if not dt_str:
                return 999  # Unknown age
            try:
                dt = datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M:%S')
                return (datetime.now() - dt).days
            except:
                return 999
        
        for r in reviews_base:
            # Use derive_case_status to get the correct status instead of raw status field
            # This properly checks assigned_to field to determine if task is unassigned
            # Fix mismatch: if assigned_to is set but status says "Unassigned", derive correct status
            raw_status = r.get('status', '')
            assigned_to = r.get('assigned_to')
            
            # Use best_status_with_raw_override to respect manually set statuses
            # This will preserve "Referred to AI SME" as-is, but we'll group it under "Referred to SME" for counts
            from utils import best_status_with_raw_override
            derived_status = best_status_with_raw_override(r)
            
            # Group "Referred to AI SME" under "Referred to SME" for dashboard counts
            if str(derived_status) == "Referred to AI SME":
                from utils import ReviewStatus
                derived_status = ReviewStatus.SME_REFERRED  # Map to "Referred to SME" for dashboard grouping
            
            # Fix mismatch: if assigned_to is set but status says "Unassigned", derive correct status
            if assigned_to and raw_status and raw_status.lower() == 'unassigned':
                # Task is assigned but status is wrong - derive correct status
                derived_status = derive_case_status(r)
                # Group "Referred to AI SME" under "Referred to SME" for dashboard counts
                if str(derived_status) == "Referred to AI SME":
                    from utils import ReviewStatus
                    derived_status = ReviewStatus.SME_REFERRED
            
            status = str(derived_status)  # ReviewStatus is a string enum, so str() works directly
            status_counts[status] += 1
            
            age = calc_age_days(r)
            if age <= 12:
                age_by_status[status]['1–2 days'] += 1
            elif age <= 35:
                age_by_status[status]['3–5 days'] += 1
            else:
                age_by_status[status]['5 days+'] += 1
        
        total_reviews = len(reviews_base) or 1
        distribution = [
            {
                "status": status,
                "count": count,
                "pct": round((count / total_reviews) * 100, 1),
                "age_buckets": dict(age_by_status[status])
            }
            for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Outcome Breakdown (updated for single-level fields)
        outcome_counts = defaultdict(int)
        for r in reviews_base:
            if str(r.get('status', '')).strip().lower() in ('complete', 'completed'):
                outcome = r.get('outcome', 'Unknown')
                if outcome:
                    outcome_counts[outcome] += 1
        
        total_outcomes = sum(outcome_counts.values()) or 1
        outcome_breakdown = [
            {
                "label": outcome,
                "count": count,
                "pct": round((count / total_outcomes) * 100, 1)
            }
            for outcome, count in sorted(outcome_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Chaser Cycle (Current Week) - use separate query to get ALL tasks with chasers, not filtered by date_assigned/date_completed
        from collections import defaultdict
        week_days = [monday_this + timedelta(days=i) for i in range(5)]  # Mon-Fri
        chaser_week_headers = ["7", "14", "21", "NTC"]  # Removed "Overdue" - now separate
        chaser_week_rows = [
            {"date": d.strftime("%d/%m/%Y"), "iso": d.isoformat(), **{h: 0 for h in chaser_week_headers}}
            for d in week_days
        ]
        # Separate structure for overdue chasers
        chaser_overdue = {"7": 0, "14": 0, "21": 0, "NTC": 0}
        
        # Get ALL tasks for chaser cycle (not filtered by date_assigned/date_completed)
        # Only filter by team if specified
        chaser_sql = """
            SELECT r.*
            FROM reviews r
            LEFT JOIN users u ON u.id = r.assigned_to
            WHERE 1=1
        """
        chaser_params = []
        if selected_team != "all":
            chaser_sql += " AND u.team_lead = ?"
            chaser_params.append(selected_team)
        
        cur.execute(chaser_sql, chaser_params)
        chaser_reviews = [dict(r) for r in cur.fetchall()]
        
        DUE_MAP = {
            "7": ["Chaser1DueDate", "Chaser_1_DueDate", "chaser1_due", "chaser_1_due", "Outreach1DueDate", "Outreach_Cycle_1_Due"],
            "14": ["Chaser2DueDate", "Chaser_2_DueDate", "chaser2_due", "chaser_2_due", "Outreach2DueDate", "Outreach_Cycle_2_Due"],
            "21": ["Chaser3DueDate", "Chaser_3_DueDate", "chaser3_due", "chaser_3_due", "Outreach3DueDate", "Outreach_Cycle_3_Due"],
            "NTC": ["NTCDueDate", "NTC_DueDate", "ntc_due", "NTC Due Date", "NTC_Due"]
        }
        ISSUED_MAP = {
            "7": ["Chaser1IssuedDate", "Chaser1DateIssued", "chaser1_issued", "Outreach1Date", "Outreach_Cycle_1_Issued", "Outreach Cycle 1 Issued"],
            "14": ["Chaser2IssuedDate", "Chaser2DateIssued", "chaser2_issued", "Outreach2Date", "Outreach_Cycle_2_Issued", "Outreach Cycle 2 Issued"],
            "21": ["Chaser3IssuedDate", "Chaser3DateIssued", "chaser3_issued", "Outreach3Date", "Outreach_Cycle_3_Issued", "Outreach Cycle 3 Issued"],
            "NTC": ["NTCIssuedDate", "NTC_IssuedDate", "ntc_issued"]
        }
        STATUS_TO_COL = {
            "chaser1_due": "7", "7 day chaser due": "7", "chaser1 due": "7",
            "chaser2_due": "14", "14 day chaser due": "14", "chaser2 due": "14",
            "chaser3_due": "21", "21 day chaser due": "21", "chaser3 due": "21",
            "ntc_due": "NTC", "ntc due": "NTC", "ntc - due": "NTC"
        }
        
        def _coalesce_key(rec, keys):
            for k in keys:
                if k in rec and str(rec.get(k) or "").strip():
                    return k
            return None
        
        def _parse_date_any(s):
            if not s:
                return None
            s = str(s).strip()
            # Try ISO datetime format first (e.g., "2025-10-07T00:01:00")
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(s, fmt).date()
                except:
                    continue
            # If all formats fail, try dateutil parser as last resort
            try:
                from dateutil import parser
                return parser.parse(s).date()
            except:
                pass
            return None
        
        def _is_blank_issued(v):
            if v is None:
                return True
            s = str(v).strip().lower()
            return s in ("", "none", "null", "n/a", "na", "-", "0", "false")
        
        # Helper function to check if a chaser has been issued
        def _is_chaser_issued(rec, chaser_type):
            """Check if a chaser type has been issued"""
            ik = _coalesce_key(rec, ISSUED_MAP.get(chaser_type, []))
            if ik:
                return not _is_blank_issued(rec.get(ik))
            return False
        
        # Process all reviews for chaser cycle with sequential logic (using separate query that includes all tasks)
        for rec in chaser_reviews:
            # Skip if outreach is completed
            outreach_complete = rec.get('outreach_complete') or rec.get('OutreachComplete')
            if outreach_complete in (1, '1', True, 'true', 'True'):
                continue
            
            # Check chasers sequentially: 7 → 14 → 21 → NTC
            # Only show the NEXT chaser that needs to be issued
            chaser_sequence = ["7", "14", "21", "NTC"]
            found_next_chaser = False
            
            for typ in chaser_sequence:
                # Check if all previous chasers have been issued
                if typ == "7":
                    # 7-day chaser: no prerequisites
                    prev_issued = True
                elif typ == "14":
                    # 14-day chaser: 7-day must be issued
                    prev_issued = _is_chaser_issued(rec, "7")
                elif typ == "21":
                    # 21-day chaser: 7-day and 14-day must be issued
                    prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14")
                elif typ == "NTC":
                    # NTC: 7-day, 14-day, and 21-day must be issued
                    prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14") and _is_chaser_issued(rec, "21")
                else:
                    prev_issued = False
                
                # Skip if previous chasers haven't been issued
                if not prev_issued:
                    continue
                
                # Check if this chaser has been issued (if so, move to next)
                if _is_chaser_issued(rec, typ):
                    continue  # Already issued, check next chaser
                
                # Get due date for this chaser
                k = _coalesce_key(rec, DUE_MAP.get(typ, []))
                if not k:
                    continue
                d = _parse_date_any(rec.get(k))
                if not d:
                    continue
                
                # Find which row this due date falls into (Mon-Fri of current week)
                row_idx = None
                for idx, week_day in enumerate(week_days):
                    if d == week_day:
                        row_idx = idx
                        break
                
                # Only count if due date is in current week (Mon-Fri) or overdue
                is_overdue = d < monday_this
                is_in_current_week = row_idx is not None
                
                if is_overdue:
                    # Add to separate overdue structure
                    chaser_overdue[typ] += 1
                    found_next_chaser = True
                    break  # Found the next chaser to show, stop checking
                elif is_in_current_week:
                    # Show in specific chaser column on the due date row
                    if chaser_week_rows:
                        chaser_week_rows[row_idx][typ] += 1
                    found_next_chaser = True
                    break  # Found the next chaser to show, stop checking
                # If due date is not in current week and not overdue, skip it
                # (don't show future chasers until their due dates are in the current week)
        
        chaser_headers = chaser_week_headers
        
        # Planning/Forecast data - load from forecast_planning table (like mi_dashboard does)
        try:
            cur.execute("SELECT * FROM forecast_planning ORDER BY week_index ASC")
            planning = cur.fetchall()
        except Exception:
            # Table might not exist, create empty planning data
            planning = []
        
        plan_labels = [r["week_label"] for r in planning] if planning else []
        plan_forecast = [r["forecast_count"] for r in planning] if planning else []
        
        # Calculate actuals - count completed tasks by week
        def _monday_of(d):
            return d - timedelta(days=d.weekday())
        
        # Helper function for parsing week labels (dd-mm-yy format)
        def _parse_week_label(s):
            """Parse week label in dd-mm-yy format"""
            if not s:
                return None
            s = str(s).strip()
            try:
                return datetime.strptime(s, "%d-%m-%y").date()
            except:
                try:
                    from dateutil import parser
                    return parser.parse(str(s)).date()
                except:
                    return None
        
        def terminal_completion_date(rec):
            """Return the completion date for the highest level that is completed.
            Rules (simpler than QC‑gated version):
              - If status starts with "Completed at Level N", use l{N}_date_completed.
              - Else fall back to the highest level that has l{lv}_date_completed set.
            """
            import re
            task_id = rec.get('task_id', 'unknown')
            s = (rec.get("status") or "").strip()
            print(f"[TERMINAL DEBUG] Task {task_id}: status='{s}'")
            
            # Prefer explicit status
            if s.startswith("Completed at Level "):
                # extract level digit
                m = re.search(r"(\d+)", s)
                if m:
                    lv = int(m.group(1))
                    date_field = f"l{lv}_date_completed"
                    date_val = rec.get(date_field)
                    print(f"[TERMINAL DEBUG] Task {task_id}: Found 'Completed at Level {lv}', checking {date_field}={date_val}")
                    d = _parse_date_any(date_val)
                    if d:
                        print(f"[TERMINAL DEBUG] Task {task_id}: Parsed date from {date_field}: {d}")
                        return d
            
            # Fallback: highest level with a completion date
            for lv in (3, 2, 1):
                date_field = f"l{lv}_date_completed"
                date_val = rec.get(date_field)
                if date_val:
                    print(f"[TERMINAL DEBUG] Task {task_id}: Checking {date_field}={date_val}")
                    d = _parse_date_any(date_val)
                    if d:
                        print(f"[TERMINAL DEBUG] Task {task_id}: Parsed date from {date_field}: {d}")
                        return d
            
            # Final fallback: use date_completed or updated_at if status is completed
            status_lower = str(rec.get('status', '')).strip().lower()
            if status_lower in ('complete', 'completed'):
                date_completed = rec.get('date_completed')
                updated_at = rec.get('updated_at')
                print(f"[TERMINAL DEBUG] Task {task_id}: Status is 'completed', checking date_completed={date_completed}, updated_at={updated_at}")
                # Try date_completed first, then updated_at
                if date_completed:
                    d = _parse_date_any(date_completed)
                    if d:
                        print(f"[TERMINAL DEBUG] Task {task_id}: Parsed date from date_completed: {d}")
                        return d
                    else:
                        print(f"[TERMINAL DEBUG] Task {task_id}: Failed to parse date_completed={date_completed}")
                if updated_at:
                    d = _parse_date_any(updated_at)
                    if d:
                        print(f"[TERMINAL DEBUG] Task {task_id}: Parsed date from updated_at: {d}")
                        return d
                    else:
                        print(f"[TERMINAL DEBUG] Task {task_id}: Failed to parse updated_at={updated_at}")
            
            print(f"[TERMINAL DEBUG] Task {task_id}: No completion date found")
            return None
        
        # Map week labels to indices
        week_starts = []
        for row in planning:
            lbl = row["week_label"]
            d = _parse_week_label(lbl)
            week_starts.append(d)
        
        monday_to_idx = {}
        for i, d in enumerate(week_starts):
            if d:
                monday_to_idx[_monday_of(d)] = i
        
        # Planning actuals should use ALL reviews (global scope), not filtered reviews
        # This matches the old mi_dashboard behavior where planning is global
        cur.execute("SELECT * FROM reviews")
        reviews_all = [dict(r) for r in cur.fetchall()]
        
        print(f"[PLANNING DEBUG] Total reviews: {len(reviews_all)}")
        print(f"[PLANNING DEBUG] Planning weeks: {len(planning)}")
        print(f"[PLANNING DEBUG] Week labels: {plan_labels[:5]}")
        print(f"[PLANNING DEBUG] Week starts (first 5): {week_starts[:5]}")
        print(f"[PLANNING DEBUG] Monday to idx mapping (first 5): {dict(list(monday_to_idx.items())[:5])}")
        
        plan_actual = [0 for _ in planning] if planning else []
        completed_count = 0
        matched_count = 0
        
        if planning:
            for r in reviews_all:
                d = terminal_completion_date(r)
                if not d:
                    continue
                completed_count += 1
                m = _monday_of(d)
                print(f"[PLANNING DEBUG] Task {r.get('task_id', 'unknown')}: completion_date={d}, monday_of_week={m}")
                
                idx = monday_to_idx.get(m)
                if idx is None:
                    # Fallback: try matching by parsing labels dynamically
                    print(f"[PLANNING DEBUG] No direct match for Monday {m}, trying fallback...")
                    matched = False
                    try:
                        for i, row in enumerate(planning):
                            lbl = row["week_label"]
                            lbl_d = _parse_week_label(lbl)
                            if lbl_d:
                                lbl_monday = _monday_of(lbl_d)
                                if lbl_monday == m:
                                    idx = i
                                    matched = True
                                    print(f"[PLANNING DEBUG] Matched via fallback to week {i} (label: {lbl}, parsed: {lbl_d}, monday: {lbl_monday})")
                                    break
                    except Exception as e:
                        print(f"[PLANNING DEBUG] Fallback error: {e}")
                    
                    # If still no match, find the closest week (week that contains this Monday)
                    if not matched and idx is None:
                        print(f"[PLANNING DEBUG] Still no match, trying to find closest week for Monday {m}...")
                        min_diff = None
                        closest_idx = None
                        for i, row in enumerate(planning):
                            lbl = row["week_label"]
                            lbl_d = _parse_week_label(lbl)
                            if lbl_d:
                                lbl_monday = _monday_of(lbl_d)
                                # Check if this Monday falls within this week (Monday to Sunday)
                                week_end = lbl_monday + timedelta(days=6)
                                if lbl_monday <= m <= week_end:
                                    idx = i
                                    print(f"[PLANNING DEBUG] Matched to week {i} (label: {lbl}) - Monday {m} falls within week {lbl_monday} to {week_end}")
                                    break
                                # Also track the closest week
                                diff = abs((m - lbl_monday).days)
                                if min_diff is None or diff < min_diff:
                                    min_diff = diff
                                    closest_idx = i
                        
                        # If no week contains it, use the closest one
                        if idx is None and closest_idx is not None:
                            idx = closest_idx
                            lbl = planning[closest_idx]["week_label"]
                            lbl_d = _parse_week_label(lbl)
                            if lbl_d:
                                lbl_monday = _monday_of(lbl_d)
                                print(f"[PLANNING DEBUG] Using closest week {idx} (label: {lbl}, monday: {lbl_monday}, diff: {min_diff} days)")
                else:
                    print(f"[PLANNING DEBUG] Direct match to week {idx}")
                
                if idx is not None:
                    plan_actual[idx] += 1
                    matched_count += 1
                    print(f"[PLANNING DEBUG] Added to week {idx}, new count: {plan_actual[idx]}")
        
        print(f"[PLANNING DEBUG] Total completed tasks found: {completed_count}")
        print(f"[PLANNING DEBUG] Total matched to weeks: {matched_count}")
        print(f"[PLANNING DEBUG] Final plan_actual (first 10): {plan_actual[:10]}")
        
        db.close()
        
        return jsonify({
            'success': True,
            'teams': teams or [],
            'date_ranges': [
                {"label": "All Time", "value": "all"},
                {"label": "Current Week", "value": "wtd"},
                {"label": "Previous Week", "value": "prevw"},
                {"label": "Last 30 Days", "value": "30d"},
            ],
            'selected_date': date_range,
            'selected_team': selected_team,
            'total_screened': total_screened,
            'total_completed': total_completed,
            'qc_sample': qc_sample,
            'qc_pass_pct': qc_pass_pct,
            'pass_qc': pass_qc,
            'distribution': distribution or [],
            'outcome_breakdown': outcome_breakdown or [],
            'chaser_headers': chaser_headers,
            'chaser_week_rows': chaser_week_rows,
            'chaser_overdue': chaser_overdue,
            'plan_labels': plan_labels,
            'plan_forecast': plan_forecast,
            'plan_actual': plan_actual
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_operations_dashboard: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/operations/cases', methods=['GET'], endpoint='api_operations_cases')
@role_required('operations_manager', 'admin')
def api_operations_cases():
    """Return filtered case list as JSON"""
    try:
        # Get filter parameters
        status = request.args.get("status", "").strip()
        outcome = request.args.get("outcome", "").strip()
        qc_param = request.args.get("qc", "").strip().lower()
        age_bucket = request.args.get("age_bucket", "").strip()
        date_range = request.args.get("date_range", "all")
        selected_team = request.args.get("team", "all")
        overdue = request.args.get("overdue", "").strip()
        chaser_type = request.args.get("chaser_type", "").strip()
        week_date = request.args.get("week_date", "").strip()
        
        from datetime import datetime, timedelta
        
        today = datetime.utcnow().date()
        monday_this = today - timedelta(days=today.weekday())
        monday_prev = monday_this - timedelta(days=7)
        sunday_prev = monday_this - timedelta(days=1)
        
        db = get_db()
        cur = db.cursor()
        
        # Base query (updated for single-level fields)
        base_sql = """
            SELECT r.*
            FROM reviews r
            LEFT JOIN users u ON u.id = r.assigned_to
            WHERE 1=1
        """
        params = []
        
        # Team filter
        if selected_team != "all":
            base_sql += " AND u.team_lead = ?"
            params.append(selected_team)
        
        # Date range filter - use same logic as dashboard (date_completed for completed, date_assigned for active)
        def get_date_range_bounds(date_range_str):
            """Get start and end dates for the given date range"""
            today = datetime.utcnow().date()
            if date_range_str == "wtd":  # Current Week
                monday = today - timedelta(days=today.weekday())
                return monday, today + timedelta(days=1)  # Include today
            elif date_range_str == "prevw":  # Previous Week
                monday_this = today - timedelta(days=today.weekday())
                monday_prev = monday_this - timedelta(days=7)
                sunday_prev = monday_this - timedelta(days=1)
                return monday_prev, sunday_prev + timedelta(days=1)
            elif date_range_str == "30d":  # Last 30 Days
                start = today - timedelta(days=29)
                return start, today + timedelta(days=1)
            else:  # "all" or unknown
                return None, None
        
        # For chaser filtering, skip date_range filter (get ALL tasks like dashboard does)
        # The dashboard uses a separate chaser_reviews query that doesn't filter by date_assigned/date_completed
        if not (overdue or chaser_type):
            date_start, date_end = get_date_range_bounds(date_range)
            if date_start and date_end:
                base_sql += """ AND (
                    (r.date_completed IS NOT NULL AND r.date_completed <> '' 
                     AND date(r.date_completed) >= date(?) AND date(r.date_completed) < date(?))
                    OR
                    ((r.date_completed IS NULL OR r.date_completed = '')
                     AND r.date_assigned IS NOT NULL AND r.date_assigned <> '' 
                     AND date(r.date_assigned) >= date(?) AND date(r.date_assigned) < date(?))
                )"""
                params.extend([
                    date_start.isoformat(), date_end.isoformat(),  # For completed tasks
                    date_start.isoformat(), date_end.isoformat()   # For date_assigned (active tasks)
                ])
        
        cur.execute(base_sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        
        print(f"[DEBUG] api_operations_cases: After base query, got {len(rows)} rows (chaser_filter={bool(overdue or chaser_type)})")
        
        # Apply filters (updated for single-level fields)
        def _has_qc(rec):
            return bool(rec.get("qc_check_date"))
        
        if qc_param in ("1", "yes", "true", "has_qc", "qc"):
            rows = [r for r in rows if _has_qc(r)]
        
        if status:
            status_lower = status.strip().lower()
            from utils import best_status_with_raw_override
            
            def _matches_status(rec):
                raw_status = rec.get('status', '').strip()
                raw_status_lower = raw_status.lower() if raw_status else ''
                
                # Use best_status_with_raw_override to get the correct derived status
                derived_status = str(best_status_with_raw_override(rec))
                derived_status_lower = derived_status.lower()
                
                # Special handling: "Referred to SME" should match both manual and AI SME referrals
                if status_lower == 'referred to sme':
                    # Check if either derived or raw status contains "referred to" and "sme"
                    is_sme_referred = (
                        derived_status_lower == 'referred to sme' or 
                        derived_status_lower == 'referred to ai sme' or
                        ('referred to' in derived_status_lower and 'sme' in derived_status_lower)
                    )
                    is_raw_sme_referred = (
                        raw_status_lower == 'referred to sme' or
                        raw_status_lower == 'referred to ai sme' or
                        ('referred to' in raw_status_lower and 'sme' in raw_status_lower)
                    )
                    return is_sme_referred or is_raw_sme_referred
                # Special handling: "Outreach Complete" should match exactly
                elif status_lower == 'outreach complete':
                    return (
                        derived_status_lower == 'outreach complete' or
                        raw_status_lower == 'outreach complete'
                    )
                # Special handling: "Outreach" should match outreach statuses but not "Outreach Complete" or "Awaiting Outreach"
                elif status_lower == 'outreach':
                    return (
                        ('outreach' in derived_status_lower and 'complete' not in derived_status_lower and 'awaiting' not in derived_status_lower) or
                        ('outreach' in raw_status_lower and 'complete' not in raw_status_lower and 'awaiting' not in raw_status_lower)
                    )
                else:
                    # For all other statuses, exact match on derived status
                    return derived_status_lower == status_lower
            
            rows = [r for r in rows if _matches_status(r)]
        
        if outcome:
            rows = [r for r in rows if (r.get("outcome") or '').strip().lower() == outcome.lower()]
        
        # Age bucket filter
        if age_bucket:
            def calc_age_days(r):
                dt_str = r.get('updated_at') or r.get("date_assigned")
                if not dt_str:
                    return 999
                try:
                    dt = datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M:%S')
                    return (datetime.now() - dt).days
                except:
                    return 999
            
            if age_bucket == '1–2 days':
                rows = [r for r in rows if calc_age_days(r) <= 12]
            elif age_bucket == '3–5 days':
                rows = [r for r in rows if 13 <= calc_age_days(r) <= 35]
            elif age_bucket == '5 days+':
                rows = [r for r in rows if calc_age_days(r) > 35]
        
        # Chaser cycle filter - use EXACT same logic as operations dashboard
        if overdue or chaser_type or week_date:
            print(f"[DEBUG] api_operations_cases chaser filter: overdue={overdue}, chaser_type={chaser_type}, week_date={week_date}, rows_before={len(rows)}")
            
            # Use EXACT same maps and functions as operations dashboard
            DUE_MAP = {
                "7": ["Chaser1DueDate", "Chaser_1_DueDate", "chaser1_due", "chaser_1_due", "Outreach1DueDate", "Outreach_Cycle_1_Due"],
                "14": ["Chaser2DueDate", "Chaser_2_DueDate", "chaser2_due", "chaser_2_due", "Outreach2DueDate", "Outreach_Cycle_2_Due"],
                "21": ["Chaser3DueDate", "Chaser_3_DueDate", "chaser3_due", "chaser_3_due", "Outreach3DueDate", "Outreach_Cycle_3_Due"],
                "NTC": ["NTCDueDate", "NTC_DueDate", "ntc_due", "NTC Due Date", "NTC_Due"]
            }
            ISSUED_MAP = {
                "7": ["Chaser1IssuedDate", "Chaser1DateIssued", "chaser1_issued", "Outreach1Date", "Outreach_Cycle_1_Issued", "Outreach Cycle 1 Issued"],
                "14": ["Chaser2IssuedDate", "Chaser2DateIssued", "chaser2_issued", "Outreach2Date", "Outreach_Cycle_2_Issued", "Outreach Cycle 2 Issued"],
                "21": ["Chaser3IssuedDate", "Chaser3DateIssued", "chaser3_issued", "Outreach3Date", "Outreach_Cycle_3_Issued", "Outreach Cycle 3 Issued"],
                "NTC": ["NTCIssuedDate", "NTC_IssuedDate", "ntc_issued"]
            }
            
            def _coalesce_key(rec, keys):
                for k in keys:
                    if k in rec and str(rec.get(k) or "").strip():
                        return k
                return None
            
            def _parse_date_any(s):
                if not s:
                    return None
                s = str(s).strip()
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(s, fmt).date()
                    except:
                        continue
                try:
                    from dateutil import parser
                    return parser.parse(s).date()
                except:
                    pass
                return None
            
            def _is_blank_issued(v):
                if v is None:
                    return True
                s = str(v).strip().lower()
                return s in ("", "none", "null", "n/a", "na", "-", "0", "false")
            
            def _is_chaser_issued(rec, chaser_type):
                """Check if a chaser type has been issued"""
                ik = _coalesce_key(rec, ISSUED_MAP.get(chaser_type, []))
                if ik:
                    return not _is_blank_issued(rec.get(ik))
                return False
            
            # Parse week_date - exact date match (matching dashboard line 12597: if d == week_day)
            filter_date = None
            if week_date:
                filter_date = _parse_date_any(week_date)
                print(f"[DEBUG] Filter date from week_date {week_date}: {filter_date}")
            
            filtered_rows = []
            print(f"[DEBUG] Filtering {len(rows)} rows for chaser_type={chaser_type}, overdue={overdue}, week_date={week_date}")
            
            for rec in rows:
                # Skip if outreach is completed (matching dashboard line 12576-12578)
                outreach_complete = rec.get('outreach_complete') or rec.get('OutreachComplete')
                if outreach_complete in (1, '1', True, 'true', 'True'):
                    continue
                
                # Check chasers sequentially: 7 → 14 → 21 → NTC
                # Only show the NEXT chaser that needs to be issued
                chaser_sequence = ["7", "14", "21", "NTC"]
                next_chaser_type = None
                next_chaser_due_date = None
                
                # First, find the NEXT unissued chaser for this task
                for typ in chaser_sequence:
                    # Check if all previous chasers have been issued
                    if typ == "7":
                        # 7-day chaser: no prerequisites
                        prev_issued = True
                    elif typ == "14":
                        # 14-day chaser: 7-day must be issued
                        prev_issued = _is_chaser_issued(rec, "7")
                    elif typ == "21":
                        # 21-day chaser: 7-day and 14-day must be issued
                        prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14")
                    elif typ == "NTC":
                        # NTC: 7-day, 14-day, and 21-day must be issued
                        prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14") and _is_chaser_issued(rec, "21")
                    else:
                        prev_issued = False
                    
                    # Skip if previous chasers haven't been issued
                    if not prev_issued:
                        continue
                    
                    # Check if this chaser has been issued (if so, move to next)
                    if _is_chaser_issued(rec, typ):
                        continue  # Already issued, check next chaser
                    
                    # Get due date for this chaser
                    k = _coalesce_key(rec, DUE_MAP.get(typ, []))
                    if not k:
                        continue
                    due_date = _parse_date_any(rec.get(k))
                    if not due_date:
                        continue
                    
                    # Found the next chaser - store it and break
                    next_chaser_type = typ
                    next_chaser_due_date = due_date
                    break
                
                # If no next chaser found, don't show this task
                if not next_chaser_type:
                    continue
                
                # Now check if this next chaser matches the filter criteria
                # If chaser_type is specified, must match exactly
                if chaser_type:
                    if next_chaser_type != chaser_type:
                        continue
                
                # Check date conditions
                # Priority: week_date > overdue > default (show if overdue)
                matched = False
                
                if week_date:
                    # If week_date is provided, must be in that week
                    try:
                        week_dt = datetime.fromisoformat(week_date).date()
                        week_monday = week_dt - timedelta(days=week_dt.weekday())
                        week_friday = week_monday + timedelta(days=4)
                        if week_monday <= next_chaser_due_date <= week_friday:
                            matched = True
                            print(f"[DEBUG] ✓ Task {rec.get('task_id')} MATCHES (in week): chaser_type={next_chaser_type}, due_date={next_chaser_due_date} in week {week_monday} to {week_friday}")
                    except Exception as e:
                        print(f"[DEBUG] Error checking week range: {e}")
                elif overdue == "1":
                    # If overdue flag is set, must be overdue
                    if next_chaser_due_date < today:
                        matched = True
                        print(f"[DEBUG] ✓ Task {rec.get('task_id')} MATCHES (overdue): chaser_type={next_chaser_type}, due_date={next_chaser_due_date}")
                else:
                    # If no date filters specified but chaser_type is set, show if overdue (default behavior)
                    if next_chaser_due_date < today:
                        matched = True
                        print(f"[DEBUG] ✓ Task {rec.get('task_id')} MATCHES (overdue default): chaser_type={next_chaser_type}, due_date={next_chaser_due_date}")
                
                if matched:
                    filtered_rows.append(rec)
            
            rows = filtered_rows
            print(f"[DEBUG] api_operations_cases chaser filter: rows_after={len(rows)}")
        
        db.close()
        
        # Return simplified case data (updated for single-level fields)
        cases = [{
            'id': r.get('id'),
            'task_id': r.get('task_id'),
            'customer_id': r.get('customer_id'),
            'status': r.get('status'),
            'outcome': r.get("outcome"),
            'assigned_to': r.get("assigned_to"),
            'updated_at': r.get('updated_at'),
            'date_completed': r.get("date_completed")
        } for r in rows]
        
        return jsonify({
            'success': True,
            'cases': cases,
            'total': len(cases)
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_operations_cases: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/invite_user', methods=['POST'], endpoint='api_invite_user')
@csrf.exempt
def api_invite_user():
    """Invite a new user"""
    # Check permission
    if not check_permission('invite_users', 'edit'):
        return jsonify({'error': 'Permission denied: You do not have permission to invite users'}), 403
    try:
        data = request.json
        email = data.get('email')
        name = data.get('name', '')
        role = data.get('role')
        team_lead = data.get('team_lead', '') or None
        password = data.get('password', 'password123')
        
        # Derive level from role
        level = None
        parts = role.split('_')
        if len(parts) >= 2 and parts[-1].isdigit():
            level = int(parts[-1])
        
        if not email or not role:
            return jsonify({'error': 'Email and role are required'}), 400
        
        # Generate invitation token (simplified)
        import secrets
        token = secrets.token_urlsafe(32)
        
        conn = get_db()
        cur = conn.cursor()
        
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            conn.close()
            return jsonify({'error': 'User already exists'}), 400
        
        # Hash the password
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(password)
        
        # Create user (with active status since we're setting password)
        cur.execute("""
            INSERT INTO users (email, name, role, team_lead, level, status, password_hash)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        """, (email, name, role, team_lead, level, password_hash))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'User created successfully'})
        
    except Exception as e:
        import traceback
        print(f"Error in api_invite_user: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# REVIEWER PANEL - DECISION ACTIONS (Save Progress, Submit, Refer SME)
# ============================================================================

@csrf.exempt
@app.route('/api/reviewer_panel/<task_id>/save_progress', methods=['POST'], endpoint='api_save_progress')
def api_save_progress(task_id):
    """Save partial decision progress without completing the review"""
    # Check permission
    if not check_permission('review_tasks', 'edit'):
        return jsonify({'error': 'Permission denied: You do not have permission to save review progress'}), 403
    
    try:
        from datetime import datetime
        import sqlite3
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check if task is in SME referral status - block all status changes
        is_locked, error_msg = is_task_in_sme_referral_status(task_id, conn)
        if is_locked:
            conn.close()
            return jsonify({'error': error_msg}), 403
        
        # Get current review
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        review = dict(cur.fetchone() or {})
        if not review:
            conn.close()
            return jsonify({'error': 'Review not found'}), 404
        
        # Get form data (works with both JSON and FormData)
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        outcome = (form_data.get('outcome') or '').strip()
        rationale = (form_data.get('rationale') or '').strip()
        primary_rationale = (form_data.get('primary_rationale') or '').strip()
        case_summary = (form_data.get('case_summary') or '').strip()
        financial_crime_reason = (form_data.get('financial_crime_reason') or form_data.get('fincrime_reason') or '').strip()
        sme_query = (form_data.get('sme_query') or '').strip()
        
        now = datetime.utcnow().isoformat(timespec='seconds')
        
        # Build update fields
        update_fields = {
            'updated_at': now
        }
        
        if outcome:
            update_fields['outcome'] = outcome
        if rationale:
            update_fields['rationale'] = rationale
            update_fields['decision_rationale'] = rationale  # Also save to decision_rationale for frontend
        if primary_rationale:
            update_fields['primary_rationale'] = primary_rationale
        if case_summary:
            update_fields['case_summary'] = case_summary
        if financial_crime_reason:
            # Check which column exists in the database
            cur.execute("PRAGMA table_info(reviews)")
            columns = [col[1] for col in cur.fetchall()]
            if 'financial_crime_reason' in columns:
                update_fields['financial_crime_reason'] = financial_crime_reason
            elif 'fincrime_reason' in columns:
                update_fields['fincrime_reason'] = financial_crime_reason
        if sme_query:
            update_fields['sme_query'] = sme_query
        
        # Update database
        if update_fields:
            set_clause = ', '.join(f'{k} = ?' for k in update_fields.keys())
            values = list(update_fields.values()) + [task_id]
            cur.execute(f'UPDATE reviews SET {set_clause} WHERE task_id = ?', values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': 'Progress saved successfully'})
        
    except Exception as e:
        import traceback
        print(f"Error in api_save_progress: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/reviewer_panel/<task_id>/submit', methods=['POST'], endpoint='api_submit_review')
def api_submit_review(task_id):
    """Submit the review (mark as complete if all required fields are present)
    
    After submission, automatically runs QC sampling to determine if task needs QC review
    """
    # Check permission
    if not check_permission('review_tasks', 'edit'):
        return jsonify({'error': 'Permission denied: You do not have permission to submit reviews'}), 403
    
    try:
        from datetime import datetime
        import sqlite3
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check if task is in SME referral status - block all status changes
        is_locked, error_msg = is_task_in_sme_referral_status(task_id, conn)
        if is_locked:
            conn.close()
            return jsonify({'error': error_msg}), 403
        
        # Get current review
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        review = dict(cur.fetchone() or {})
        if not review:
            conn.close()
            return jsonify({'error': 'Review not found'}), 404
        
        # Get form data
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        outcome = (form_data.get('outcome') or '').strip()
        rationale = (form_data.get('rationale') or '').strip()
        primary_rationale = (form_data.get('primary_rationale') or '').strip()
        case_summary = (form_data.get('case_summary') or review.get('case_summary') or '').strip()
        financial_crime_reason = (form_data.get('financial_crime_reason') or form_data.get('fincrime_reason') or '').strip()
        
        # Validation
        if not outcome:
            return jsonify({'error': 'Outcome is required'}), 400
        if not rationale:
            return jsonify({'error': 'Rationale is required'}), 400
        if not case_summary:
            return jsonify({'error': 'Case Summary is required'}), 400
        
        now = datetime.utcnow().isoformat(timespec='seconds')
        user_id = session.get('user_id')
        
        # Check if task was already completed and is in rework
        # Note: QC happens AFTER review submission, so we don't check qc_outcome here
        was_completed = review.get('date_completed') and review.get('date_completed').strip()
        status_lower = (str(review.get('status', '') or '')).strip().lower()
        is_in_rework = (
            review.get('qc_rework_required') or 
            'rework' in status_lower
        )
        
        # Build update fields
        update_fields = {
            'updated_at': now,
            'outcome': outcome,
            'rationale': rationale,
            'decision_rationale': rationale,  # Also save to decision_rationale for frontend
            'review_end_time': now
        }
        
        # If task was already completed and is in rework, clear rework flags to allow new QC cycle
        if was_completed and is_in_rework:
            # Clear rework flags so status can progress
            update_fields['qc_rework_required'] = 0
            update_fields['qc_rework_completed'] = 1  # Mark rework as completed by reviewer
            # IMPORTANT: Do NOT clear qc_outcome - keep it for MI/reporting purposes
            # Clear qc_check_date so task goes back to QC for fresh review (not marked as Completed)
            update_fields['qc_check_date'] = None
            # Clear QC end time so task becomes active for QC again
            # This makes the task show up in QC dashboard as a fresh review
            update_fields['qc_end_time'] = None
            # IMPORTANT: Do NOT clear qc_assigned_to - keep it assigned to the same QC reviewer
            # so the task shows up in their dashboard
            # Keep original date_completed - don't overwrite it
            # Don't set date_completed here - it should remain as the original completion date
        else:
            # First time completing - set date_completed
            update_fields['date_completed'] = now
            update_fields['completed_by'] = user_id
        
        if primary_rationale:
            update_fields['primary_rationale'] = primary_rationale
        if case_summary:
            update_fields['case_summary'] = case_summary
        if financial_crime_reason:
            # Check which column exists
            cur.execute("PRAGMA table_info(reviews)")
            columns = [col[1] for col in cur.fetchall()]
            if 'financial_crime_reason' in columns:
                update_fields['financial_crime_reason'] = financial_crime_reason
            elif 'fincrime_reason' in columns:
                update_fields['fincrime_reason'] = financial_crime_reason
        
        # Update database
        set_clause = ', '.join(f'{k} = ?' for k in update_fields.keys())
        values = list(update_fields.values()) + [task_id]
        cur.execute(f'UPDATE reviews SET {set_clause} WHERE task_id = ?', values)
        conn.commit()
        
        # AUTOMATIC QC SAMPLING - Only run if this is a new completion (not a rework resubmission)
        # If task was already completed, it should already be in QC sampling if needed
        if not was_completed:
            try:
                apply_qc_sampling()  # Now runs without level parameter
            except Exception as qc_err:
                print(f"Warning: QC sampling failed: {qc_err}")
                # Don't fail the submission if QC sampling fails
        
        # Update status using derive_case_status
        try:
            from utils import derive_case_status
            
            # Re-fetch to get updated data including QC sampling flag
            cur.execute("""
                SELECT r.*, 
                       CASE WHEN q.review_id IS NOT NULL THEN 1 ELSE 0 END as _in_qc_sampling
                FROM reviews r
                LEFT JOIN qc_sampling_log q ON q.review_id = r.id
                WHERE r.task_id = ?
            """, (task_id,))
            updated_review = dict(cur.fetchone())
            new_status = derive_case_status(updated_review)
            cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
            conn.commit()
        except Exception as status_err:
            print(f"Warning: Could not derive status: {status_err}")
            import traceback
            traceback.print_exc()
            # Fallback: set status based on QC sampling
            cur.execute("""
                SELECT CASE WHEN q.review_id IS NOT NULL THEN 1 ELSE 0 END as in_qc
                FROM reviews r
                LEFT JOIN qc_sampling_log q ON q.review_id = r.id
                WHERE r.task_id = ?
            """, (task_id,))
            result = cur.fetchone()
            fallback_status = 'QC - Awaiting Assignment' if (result and result[0]) else 'Completed'
            cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (fallback_status, task_id))
            conn.commit()
        
        conn.close()
        
        return jsonify({'success': True, 'message': 'Review submitted successfully'})
        
    except Exception as e:
        import traceback
        print(f"Error in api_submit_review: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/reviewer_panel/<task_id>/rework_complete', methods=['POST'], endpoint='api_rework_complete')
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'operations_manager', 'admin', 'team_lead_1', 'team_lead_2', 'team_lead_3')
def api_rework_complete(task_id):
    """Mark rework as complete - acts exactly like submit button, saves form data and resubmits for QC"""
    # Check permission
    if not check_permission('review_tasks', 'edit'):
        return jsonify({'error': 'Permission denied: You do not have permission to edit tasks'}), 403
    
    try:
        from datetime import datetime
        import sqlite3
        from utils import derive_case_status
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get current review
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        review = dict(cur.fetchone() or {})
        if not review:
            conn.close()
            return jsonify({'error': 'Review not found'}), 404
        
        status_lower = (str(review.get('status', '') or '')).strip().lower()
        if 'rework required' not in status_lower:
            conn.close()
            return jsonify({'error': 'Task is not in rework status'}), 400
        
        # Get form data (same as submit endpoint)
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        outcome = (form_data.get('outcome') or '').strip()
        rationale = (form_data.get('rationale') or '').strip()
        primary_rationale = (form_data.get('primary_rationale') or '').strip()
        case_summary = (form_data.get('case_summary') or review.get('case_summary') or '').strip()
        financial_crime_reason = (form_data.get('financial_crime_reason') or form_data.get('fincrime_reason') or '').strip()
        
        # Validation (same as submit)
        if not outcome:
            conn.close()
            return jsonify({'error': 'Outcome is required'}), 400
        if not rationale:
            conn.close()
            return jsonify({'error': 'Rationale is required'}), 400
        if not case_summary:
            conn.close()
            return jsonify({'error': 'Case Summary is required'}), 400
        
        now = datetime.utcnow().isoformat(timespec='seconds')
        user_id = session.get('user_id')
        
        # Build update fields (same logic as submit endpoint for rework)
        update_fields = {
            'updated_at': now,
            'outcome': outcome,
            'rationale': rationale,
            'decision_rationale': rationale,  # Also save to decision_rationale for frontend
            'review_end_time': now
        }
        
        # Mark rework as completed and clear rework requirement
        # Keep qc_rework_completed = 1 to track that rework was completed
        # This allows us to show when rework was completed in the dashboard
        update_fields['qc_rework_required'] = 0
        update_fields['qc_rework_completed'] = 1  # Mark as completed (don't clear it)
        # IMPORTANT: Do NOT clear qc_outcome - keep it for MI/reporting purposes
        # Clear qc_check_date so task goes back to QC for fresh review (not marked as Completed)
        update_fields['qc_check_date'] = None
        update_fields['qc_end_time'] = None
        # IMPORTANT: Do NOT clear qc_assigned_to - keep it assigned to the same QC reviewer
        # so the task shows up in their dashboard
        # Don't overwrite date_completed - keep original completion date
        
        if primary_rationale:
            update_fields['primary_rationale'] = primary_rationale
        if case_summary:
            update_fields['case_summary'] = case_summary
        if financial_crime_reason:
            # Check which column exists
            cur.execute("PRAGMA table_info(reviews)")
            columns = [col[1] for col in cur.fetchall()]
            if 'financial_crime_reason' in columns:
                update_fields['financial_crime_reason'] = financial_crime_reason
            elif 'fincrime_reason' in columns:
                update_fields['fincrime_reason'] = financial_crime_reason
        
        # Update database
        set_clause = ', '.join(f'{k} = ?' for k in update_fields.keys())
        values = list(update_fields.values()) + [task_id]
        cur.execute(f"UPDATE reviews SET {set_clause} WHERE task_id = ?", values)
        
        # Re-derive status after update
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        updated_review = dict(cur.fetchone())
        new_status = derive_case_status(updated_review)
        cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
        
        # Run QC sampling (same as submit endpoint)
        try:
            apply_qc_sampling()
        except Exception as qc_err:
            print(f"Warning: QC sampling failed after rework complete: {qc_err}")
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Rework completed and task resubmitted for QC review'})
        
    except Exception as e:
        import traceback
        print(f"Error in api_rework_complete: {str(e)}\n{traceback.format_exc()}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/reviewer_panel/<task_id>/refer_sme', methods=['POST'], endpoint='api_refer_sme')
def api_refer_sme(task_id):
    """Refer the review to SME for technical guidance"""
    try:
        from datetime import datetime
        import sqlite3
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get current review
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        review = dict(cur.fetchone() or {})
        if not review:
            conn.close()
            return jsonify({'error': 'Review not found'}), 404
        
        # Get form data
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        sme_query = (form_data.get('sme_query') or '').strip()
        
        if not sme_query:
            return jsonify({'error': 'SME Query is required'}), 400
        
        now = datetime.utcnow().isoformat(timespec='seconds')
        
        # Build update fields for SME referral
        update_fields = {
            'updated_at': now,
            'referred_to_sme': 1,
            'sme_selected_date': now,
            'sme_query': sme_query,
            'sme_response': None,
            'sme_returned_date': None
        }
        
        # Update database
        set_clause = ', '.join(f'{k} = ?' for k in update_fields.keys())
        values = list(update_fields.values()) + [task_id]
        cur.execute(f'UPDATE reviews SET {set_clause} WHERE task_id = ?', values)
        
        # Update status
        try:
            from utils import derive_case_status
            cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
            updated_review = dict(cur.fetchone())
            new_status = derive_case_status(updated_review)
            cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))
        except Exception as status_err:
            print(f"Warning: Could not derive status: {status_err}")
            # Fallback: set status to indicate SME referral
            cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", ('Referred to SME', task_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Referred to SME successfully'})
        
    except Exception as e:
        import traceback
        print(f"Error in api_refer_sme: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/reviewer_panel/<task_id>/save_ddg', methods=['POST'], endpoint='api_save_ddg')
def api_save_ddg(task_id):
    """Save Due Diligence section"""
    try:
        from datetime import datetime
        import sqlite3
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check review exists
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({'error': 'Review not found'}), 404
        
        # Get form data
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        now = datetime.utcnow().isoformat(timespec='seconds')
        
        # DDG sections to save
        ddg_sections = ['idv', 'nob', 'income', 'expenditure', 'structure', 'ta', 'sof', 'sow']
        
        update_fields = {'updated_at': now}
        
        for section in ddg_sections:
            # Rationale
            rationale_key = f'{section}_rationale'
            if rationale_key in form_data:
                update_fields[rationale_key] = form_data[rationale_key]
            
            # Outreach required
            outreach_key = f'{section}_outreach_required'
            if outreach_key in form_data:
                update_fields[outreach_key] = 1 if form_data[outreach_key] in ['1', 'true', 'True', 'on'] else 0
            
            # Section completed
            completed_key = f'{section}_section_completed'
            if completed_key in form_data:
                update_fields[completed_key] = 1 if form_data[completed_key] in ['1', 'true', 'True', 'on'] else 0
        
        # FinCrime concerns
        if 'sar_rationale' in form_data:
            update_fields['sar_rationale'] = form_data['sar_rationale']
        if 'sar_date_raised' in form_data:
            update_fields['sar_date_raised'] = form_data['sar_date_raised']
        if 'daml_rationale' in form_data:
            update_fields['daml_rationale'] = form_data['daml_rationale']
        if 'daml_date_raised' in form_data:
            update_fields['daml_date_raised'] = form_data['daml_date_raised']
        
        # Update database
        if len(update_fields) > 1:  # More than just updated_at
            set_clause = ', '.join(f'{k} = ?' for k in update_fields.keys())
            values = list(update_fields.values()) + [task_id]
            cur.execute(f'UPDATE reviews SET {set_clause} WHERE task_id = ?', values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': 'DDG section saved successfully'})
        
    except Exception as e:
        import traceback
        print(f"Error in api_save_ddg: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# SAMPLING RATES CONFIGURATION API (for Quality Managers)
# ============================================================================

@csrf.exempt
@app.route('/api/sampling_rates', methods=['GET'], endpoint='api_get_sampling_rates')
@role_required('qc_lead_1', 'qc_lead_2', 'qc_lead_3', 'qc_1', 'qc_2', 'qc_3', 'admin')
def api_get_sampling_rates():
    """Get all sampling rates (global and per-reviewer)"""
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Get global rate
        cur.execute("SELECT rate FROM sampling_rates WHERE reviewer_id IS NULL LIMIT 1")
        global_row = cur.fetchone()
        global_rate = global_row['rate'] if global_row else 10
        
        # Get per-reviewer rates with user details
        cur.execute("""
            SELECT 
                sr.reviewer_id,
                sr.rate,
                u.name,
                u.email,
                u.role
            FROM sampling_rates sr
            JOIN users u ON sr.reviewer_id = u.id
            WHERE sr.reviewer_id IS NOT NULL
            ORDER BY u.name
        """)
        reviewer_rates = [dict(row) for row in cur.fetchall()]
        
        # Get list of all reviewers (for adding new rates) - single level system
        cur.execute("""
            SELECT id, name, email, role
            FROM users
            WHERE role LIKE 'reviewer_%'
            ORDER BY name
        """)
        all_reviewers = [dict(row) for row in cur.fetchall()]
        
        conn.close()
        
        return jsonify({
            'global_rate': global_rate,
            'reviewer_rates': reviewer_rates,
            'all_reviewers': all_reviewers
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_get_sampling_rates: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sampling_rates/global', methods=['POST'], endpoint='api_set_global_rate')
@role_required('qc_lead_1', 'qc_lead_2', 'qc_lead_3', 'qc_1', 'qc_2', 'qc_3', 'admin')
def api_set_global_rate():
    """Set the global sampling rate"""
    conn = None
    try:
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        rate = form_data.get('rate')
        if rate is None:
            return jsonify({'error': 'Rate is required'}), 400
        
        try:
            rate = float(rate)
            if rate < 0 or rate > 100:
                return jsonify({'error': 'Rate must be between 0 and 100'}), 400
        except ValueError:
            return jsonify({'error': 'Rate must be a number'}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        # Check if global rate exists
        cur.execute("SELECT id FROM sampling_rates WHERE reviewer_id IS NULL")
        existing = cur.fetchone()
        
        if existing:
            cur.execute("UPDATE sampling_rates SET rate = ? WHERE reviewer_id IS NULL", (rate,))
        else:
            # Insert global rate - single-level system
            # Check if level column exists
            cur.execute("PRAGMA table_info(sampling_rates)")
            columns = [col[1] for col in cur.fetchall()]
            if 'level' in columns:
                # Level column exists - use default value 1 (single-level system)
                # since level has NOT NULL constraint
                cur.execute("INSERT INTO sampling_rates (reviewer_id, rate, level) VALUES (NULL, ?, 1)", (rate,))
            else:
                cur.execute("INSERT INTO sampling_rates (reviewer_id, rate) VALUES (NULL, ?)", (rate,))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Global rate updated', 'rate': rate})
        
    except sqlite3.OperationalError as e:
        if conn:
            conn.rollback()
        import traceback
        error_msg = str(e)
        if 'locked' in error_msg.lower():
            error_msg = 'Database is locked. Please try again in a moment.'
        print(f"Error in api_set_global_rate: {error_msg}\n{traceback.format_exc()}")
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        print(f"Error in api_set_global_rate: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@csrf.exempt
@app.route('/api/qc_assign_tasks_bulk', methods=['GET', 'POST'], endpoint='api_qc_assign_tasks_bulk')
@role_required('qc_1', 'qc_2', 'qc_3')
def api_qc_assign_tasks_bulk():
    """API endpoint for QC bulk assign tasks"""
    import sqlite3
    from utils import derive_case_status
    
    # Get level from role
    session_role = (session.get("role") or "").lower()
    try:
        level = int(session_role.split("_")[-1]) if "_" in session_role else 1
    except Exception:
        level = 1
    
    reviewer_role = f"qc_review_{level}"
    qctl_user_id = session.get("user_id")
    
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get QCTL info for team scoping
    cur.execute("SELECT name, email FROM users WHERE id = ?", (qctl_user_id,))
    me_row = cur.fetchone()
    lead_name = (me_row["name"] if me_row and me_row["name"] else "").strip()
    lead_email = (me_row["email"] if me_row and me_row["email"] else "").strip()
    
    # Get QC reviewers in this level and team
    cur.execute("""
        SELECT id, COALESCE(name,email) AS display_name
        FROM users
        WHERE role = ?
          AND (status IS NULL OR status = 'active')
          AND id <> ?
          AND (
               team_lead = ? OR team_lead = ?
            OR reporting_line = ? OR reporting_line = ?
          )
        ORDER BY display_name COLLATE NOCASE
    """, (reviewer_role, qctl_user_id, lead_name, lead_email, lead_name, lead_email))
    reviewers = [{"id": r["id"], "name": r["display_name"], "display_name": r["display_name"]} for r in cur.fetchall()]
    allowed_qc_ids = {r["id"] for r in reviewers}
    
    # GET: return reviewers and unassigned count
    if request.method == "GET":
        # Count unassigned tasks (completed, in QC sampling, but not QC assigned)
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM reviews r
            INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
            WHERE r.date_completed IS NOT NULL
              AND (r.qc_assigned_to IS NULL OR r.qc_assigned_to = 0)
              AND (r.qc_end_time IS NULL OR r.qc_end_time = '' OR r.qc_end_time = '0')
        """)
        unassigned_count = cur.fetchone()["cnt"]
        
        conn.close()
        return jsonify({
            'reviewers': reviewers,
            'unassigned_count': unassigned_count,
            'level': level
        })
    
    # POST: bulk assign tasks
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()
    
    selected_reviewers = data.get('selected_reviewers', [])
    if isinstance(selected_reviewers, str):
        selected_reviewers = [int(selected_reviewers)]
    task_count = int(data.get('task_count', 5))
    priority = data.get('priority', 'date')  # 'date' or 'score'
    
    if not selected_reviewers:
        conn.close()
        return jsonify({'error': 'Please select at least one reviewer'}), 400
    
    # Validate reviewers are in allowed list
    for reviewer_id in selected_reviewers:
        if reviewer_id not in allowed_qc_ids:
            conn.close()
            return jsonify({'error': f'Reviewer {reviewer_id} is not in your team'}), 400
    
    try:
        # Get unassigned tasks
        order_by = "m.total_score DESC" if priority == "score" else "r.date_completed DESC"
        cur.execute(f"""
            SELECT r.id, r.task_id
            FROM reviews r
            INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
            LEFT JOIN matches m ON m.task_id = r.task_id
            WHERE r.date_completed IS NOT NULL
              AND (r.qc_assigned_to IS NULL OR r.qc_assigned_to = 0)
              AND (r.qc_end_time IS NULL OR r.qc_end_time = '' OR r.qc_end_time = '0')
            ORDER BY {order_by}
            LIMIT ?
        """, (task_count * len(selected_reviewers),))
        unassigned_tasks = [{"id": row["id"], "task_id": row["task_id"]} for row in cur.fetchall()]
        
        if not unassigned_tasks:
            conn.close()
            return jsonify({'error': 'No unassigned tasks available'}), 400
        
        # Distribute tasks evenly among reviewers
        assignments_made = 0
        for i, task in enumerate(unassigned_tasks):
            reviewer_id = selected_reviewers[i % len(selected_reviewers)]
            review_id = task["id"]
            
            # Assign task
            cur.execute("""
                UPDATE reviews
                   SET qc_assigned_to = ?
                 WHERE id = ?
            """, (reviewer_id, review_id))
            
            # Re-derive status
            cur.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
            rev = dict(cur.fetchone())
            new_status = derive_case_status(rev)
            cur.execute("UPDATE reviews SET status = ? WHERE id = ?", (str(new_status), review_id))
            
            assignments_made += 1
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{assignments_made} task(s) assigned to {len(selected_reviewers)} reviewer(s)'
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        import traceback
        print(f"Error in api_qc_assign_tasks_bulk: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/qc_assign_tasks', methods=['GET', 'POST'])
@role_required('qc_1', 'qc_2', 'qc_3')
def api_qc_assign_tasks():
    """API endpoint for QC assign tasks - GET returns data, POST assigns tasks"""
    import sqlite3
    from utils import derive_case_status
    
    # Get level from role
    session_role = (session.get("role") or "").lower()
    try:
        level = int(session_role.split("_")[-1]) if "_" in session_role else 1
    except Exception:
        level = 1
    
    reviewer_role = f"qc_review_{level}"
    qctl_user_id = session.get("user_id")
    
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get QCTL info for team scoping
    cur.execute("SELECT name, email FROM users WHERE id = ?", (qctl_user_id,))
    me_row = cur.fetchone()
    lead_name = (me_row["name"] if me_row and me_row["name"] else "").strip()
    lead_email = (me_row["email"] if me_row and me_row["email"] else "").strip()
    
    # Get QC reviewers in this level and team
    cur.execute("""
        SELECT id, COALESCE(name,email) AS display_name
        FROM users
        WHERE role = ?
          AND (status IS NULL OR status = 'active')
          AND id <> ?
          AND (
               team_lead = ? OR team_lead = ?
            OR reporting_line = ? OR reporting_line = ?
          )
        ORDER BY display_name COLLATE NOCASE
    """, (reviewer_role, qctl_user_id, lead_name, lead_email, lead_name, lead_email))
    qc_reviewers = [{"id": r["id"], "display_name": r["display_name"]} for r in cur.fetchall()]
    allowed_qc_ids = {r["id"] for r in qc_reviewers}
    
    # POST: allocate tasks
    if request.method == "POST":
        if request.is_json:
            data = request.json
            selected_task_ids = data.get("task_ids", [])
            qc_reviewer_id = data.get("qc_reviewer_id")
        else:
            selected_task_ids = request.form.getlist("task_ids")
            qc_reviewer_id = request.form.get("qc_reviewer_id", type=int)
        
        if not selected_task_ids or not qc_reviewer_id:
            conn.close()
            return jsonify({'error': 'Please select at least one task and a QC reviewer.'}), 400
        
        if qc_reviewer_id not in allowed_qc_ids:
            conn.close()
            return jsonify({'error': 'You can only allocate to QC reviewers in your team at this level.'}), 403
        
        try:
            assigned_count = 0
            for task_id in selected_task_ids:
                # Assign using single-level columns
                cur.execute("""
                    UPDATE reviews
                       SET qc_assigned_to = ?
                     WHERE task_id = ?
                       AND (qc_assigned_to IS NULL OR qc_assigned_to = 0)
                       AND (qc_end_time IS NULL OR qc_end_time = '')
                """, (qc_reviewer_id, task_id))
                
                if cur.rowcount > 0:
                    assigned_count += 1
                    # Re-derive status
                    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
                    r = cur.fetchone()
                    if r:
                        from utils import derive_case_status
                        new_status = derive_case_status(dict(r))
                        cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': f'Allocated {assigned_count} task(s) to the selected QC reviewer.', 'assigned_count': assigned_count})
        except Exception as e:
            conn.rollback()
            conn.close()
            import traceback
            print(f"Error in api_qc_assign_tasks: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': f'Allocation failed: {str(e)}'}), 500
    
    # GET: fetch allocatable cases (must be in QC sampling)
    cur.execute("""
        SELECT
            r.id,
            r.task_id,
            r.date_completed AS completed_at,
            COALESCE(u.name,u.email) AS completed_by
        FROM reviews r
        INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id
        LEFT JOIN users u ON u.id = r.completed_by
        WHERE r.date_completed IS NOT NULL
          AND (r.qc_assigned_to IS NULL OR r.qc_assigned_to = 0)
          AND (r.qc_end_time IS NULL OR r.qc_end_time = '' OR r.qc_end_time = '0')
        ORDER BY r.date_completed DESC
        LIMIT 500
    """)
    unassigned_rows = [{
        "id": r["id"],
        "task_id": r["task_id"],
        "completed_at": r["completed_at"],
        "completed_by": r["completed_by"]
    } for r in cur.fetchall()]
    
    conn.close()
    return jsonify({
        'level': level,
        'qc_reviewers': qc_reviewers,
        'unassigned_rows': unassigned_rows
    })

@app.route('/api/qc_reassign_tasks', methods=['POST'])
@role_required('qc_1', 'qc_2', 'qc_3')
def api_qc_reassign_tasks():
    """API endpoint for QC reassign tasks - reassigns already assigned tasks to a different QC reviewer"""
    import sqlite3
    from utils import derive_case_status
    
    # Get level from role
    session_role = (session.get("role") or "").lower()
    try:
        level = int(session_role.split("_")[-1]) if "_" in session_role else 1
    except Exception:
        level = 1
    
    reviewer_role = f"qc_review_{level}"
    qctl_user_id = session.get("user_id")
    
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get QCTL info for team scoping
    cur.execute("SELECT name, email FROM users WHERE id = ?", (qctl_user_id,))
    me_row = cur.fetchone()
    lead_name = (me_row["name"] if me_row and me_row["name"] else "").strip()
    lead_email = (me_row["email"] if me_row and me_row["email"] else "").strip()
    
    # Get QC reviewers in this level and team
    cur.execute("""
        SELECT id, COALESCE(name,email) AS display_name
        FROM users
        WHERE role = ?
          AND (status IS NULL OR status = 'active')
          AND (
               team_lead = ? OR team_lead = ?
            OR reporting_line = ? OR reporting_line = ?
          )
        ORDER BY display_name COLLATE NOCASE
    """, (reviewer_role, lead_name, lead_email, lead_name, lead_email))
    qc_reviewers = [{"id": r["id"], "display_name": r["display_name"]} for r in cur.fetchall()]
    allowed_qc_ids = {r["id"] for r in qc_reviewers}
    
    # Get task IDs and new reviewer
    if request.is_json:
        data = request.json
        selected_task_ids = data.get("task_ids", [])
        qc_reviewer_id = data.get("qc_reviewer_id")
    else:
        selected_task_ids = request.form.getlist("task_ids")
        qc_reviewer_id = request.form.get("qc_reviewer_id", type=int)
    
    if not selected_task_ids or not qc_reviewer_id:
        conn.close()
        return jsonify({'error': 'Please select at least one task and a QC reviewer.'}), 400
    
    if qc_reviewer_id not in allowed_qc_ids:
        conn.close()
        return jsonify({'error': 'You can only reassign to QC reviewers in your team at this level.'}), 403
    
    try:
        reassigned_count = 0
        for task_id in selected_task_ids:
            # Reassign using single-level columns
            # Clear qc_start_time and qc_end_time to allow the new reviewer to start fresh
            cur.execute("""
                UPDATE reviews
                   SET qc_assigned_to = ?,
                       qc_start_time = NULL,
                       qc_end_time = NULL
                 WHERE task_id = ?
                   AND (qc_end_time IS NULL OR qc_end_time = '')
            """, (qc_reviewer_id, task_id))
            
            if cur.rowcount > 0:
                reassigned_count += 1
                # Re-derive status
                cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
                r = cur.fetchone()
                if r:
                    new_status = derive_case_status(dict(r))
                    cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (new_status, task_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Reassigned {reassigned_count} task(s) to the selected QC reviewer.', 'reassigned_count': reassigned_count})
    except Exception as e:
        conn.rollback()
        conn.close()
        import traceback
        print(f"Error in api_qc_reassign_tasks: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Reassignment failed: {str(e)}'}), 500

@csrf.exempt
@app.route('/api/qc_review/<task_id>', methods=['GET', 'POST'])
@role_required('qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3')
def api_qc_review(task_id):
    """API endpoint for QC review panel"""
    import sqlite3
    from utils import derive_case_status
    from datetime import datetime
    
    user_role = session.get("role", "").lower()
    user_id = session.get("user_id")
    
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Load review & match
    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
    review_row = cur.fetchone()
    cur.execute("SELECT * FROM matches WHERE task_id = ?", (task_id,))
    match_row = cur.fetchone()
    
    if not review_row:
        conn.close()
        return jsonify({'error': 'Review not found'}), 404
    
    review = dict(review_row)
    match = dict(match_row) if match_row else {}
    
    # Determine level
    role = (session.get("role") or "").lower()
    if role.startswith("qc_review_"):
        level = int(role.split("_")[-1])
    else:
        level = int(role.split("_")[-1]) if role.startswith("qc_") else 1
    
    # POST: submit review
    if request.method == "POST":
        # Check if task is in SME referral status - block all status changes
        is_locked, error_msg = is_task_in_sme_referral_status(task_id, conn)
        if is_locked:
            conn.close()
            return jsonify({'error': error_msg}), 403
        
        outcome = request.form.get("outcome", "")
        comment = request.form.get("comment", "")
        rework_required = request.form.get("rework_required") == "on"
        action = request.form.get("action", "")
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Handle "qc_rework_ok" action - QC confirms rework is acceptable
            if action == "qc_rework_ok":
                cur.execute("""
                    UPDATE reviews
                       SET qc_rework_completed = 1,
                           qc_rework_required = 0,
                           qc_end_time = ?,
                           qc_check_date = COALESCE(qc_check_date, ?)
                     WHERE task_id = ?
                """, (now, now, task_id))
                
                # Re-derive status
                cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
                review_dict = dict(cur.fetchone() or {})
                
                # Check if task is in QC sampling
                cur.execute("SELECT 1 FROM qc_sampling_log WHERE task_id = ?", (task_id,))
                in_qc_sampling = cur.fetchone() is not None
                review_dict["_in_qc_sampling"] = in_qc_sampling
                
                from utils import derive_case_status
                new_status = derive_case_status(review_dict)
                cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
                
                conn.commit()
                return jsonify({'success': True, 'message': 'Rework confirmed as acceptable'})
            
            # Update QC fields
            # If rework is required, clear qc_rework_completed to reset for new rework cycle
            # If rework is not required, keep qc_rework_completed as is (may be 1 from previous cycle)
            if rework_required:
                cur.execute("""
                    UPDATE reviews
                       SET qc_outcome = ?,
                           qc_comment = ?,
                           qc_check_date = ?,
                           qc_rework_required = ?,
                           qc_rework_completed = 0,
                           qc_end_time = ?
                     WHERE task_id = ?
                """, (outcome, comment, now, int(rework_required), now, task_id))
            else:
                # If rework is not required and outcome is Pass/Pass with Feedback, 
                # set qc_rework_completed = 1 to indicate rework was accepted (if it was previously in rework)
                # This ensures status derivation correctly identifies the task as completed
                if outcome in ("Pass", "Pass with Feedback"):
                    cur.execute("""
                        UPDATE reviews
                           SET qc_outcome = ?,
                               qc_comment = ?,
                               qc_check_date = ?,
                               qc_rework_required = ?,
                               qc_rework_completed = 1,
                               qc_end_time = ?
                         WHERE task_id = ?
                    """, (outcome, comment, now, int(rework_required), now, task_id))
                else:
                    cur.execute("""
                        UPDATE reviews
                           SET qc_outcome = ?,
                               qc_comment = ?,
                               qc_check_date = ?,
                               qc_rework_required = ?,
                               qc_end_time = ?
                         WHERE task_id = ?
                    """, (outcome, comment, now, int(rework_required), now, task_id))
            
            # Set QC start time if not set
            cur.execute("""
                UPDATE reviews
                   SET qc_start_time = ?
                 WHERE task_id = ?
                   AND (qc_start_time IS NULL OR qc_start_time = '')
            """, (now, task_id))
            
            # Handle SME referral
            if action == "refer_sme":
                cur.execute("""
                    UPDATE reviews
                       SET sme_status = 'Pending SME',
                           updated_at = ?
                     WHERE task_id = ?
                """, (now, task_id))
            
            # Re-derive status with QC sampling flag
            cur.execute("""
                SELECT r.*, 
                       CASE WHEN q.review_id IS NOT NULL THEN 1 ELSE 0 END as _in_qc_sampling
                FROM reviews r
                LEFT JOIN qc_sampling_log q ON q.review_id = r.id
                WHERE r.task_id = ?
            """, (task_id,))
            rev = dict(cur.fetchone())
            new_status = derive_case_status(rev)
            cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'QC review submitted.'})
        except Exception as e:
            conn.rollback()
            conn.close()
            import traceback
            print(f"Error in api_qc_review: {str(e)}\n{traceback.format_exc()}")
            return jsonify({'error': str(e)}), 500
    
    # GET: return review data
    # Check if task is in QC sampling for proper status derivation
    cur.execute("""
        SELECT CASE WHEN q.review_id IS NOT NULL THEN 1 ELSE 0 END as _in_qc_sampling
        FROM reviews r
        LEFT JOIN qc_sampling_log q ON q.review_id = r.id
        WHERE r.task_id = ?
    """, (task_id,))
    qc_sampling_result = cur.fetchone()
    review['_in_qc_sampling'] = bool(qc_sampling_result and qc_sampling_result[0])
    
    status = derive_case_status(review)
    reviewer_name = session.get("email") or "Unassigned"
    
    # Merge match data into review for compatibility (like api_reviewer_panel)
    review.update(match)
    
    # Get all users for ID to name mapping
    cur.execute("SELECT id, COALESCE(name, email) AS display_name FROM users")
    users = {str(row["id"]): row["display_name"] for row in cur.fetchall()}
    
    # Map user IDs to names for assigned_to fields
    if review.get("assigned_to"):
        user_id = review["assigned_to"]
        review["assigned_to_name"] = users.get(str(user_id), f"User #{user_id}")
    
    if review.get("qc_assigned_to"):
        user_id = review["qc_assigned_to"]
        review["qc_assigned_to_name"] = users.get(str(user_id), f"User #{user_id}")
    
    # Get outcomes
    try:
        outcome_names = _load_outcomes_from_db(cur)
    except:
        outcome_names = ["Retain", "Exit - Financial Crime", "Exit - Non-responsive", "Exit - T&C"]
    
    outcomes = [{"name": n} for n in outcome_names]
    
    conn.close()
    
    return jsonify({
        'task_id': task_id,
        'level': level,
        'status': status,
        'reviewer_name': reviewer_name,
        'review': review,  # Return full review object like api_reviewer_panel
        'match': match,
        'outcomes': outcomes,
        'users': users
    })

@csrf.exempt
@app.route('/api/qc_wip_cases', methods=['GET'])
@role_required('qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3')
def api_qc_wip_cases():
    """API endpoint for QC WIP cases"""
    import sqlite3
    
    reviewer_id = request.args.get("reviewer_id", type=int)
    bucket = (request.args.get("bucket") or "assigned").lower()
    
    # Single-level system - level is always 1 (legacy field kept for compatibility)
    level = 1
    
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Build WHERE clause based on bucket
    # If reviewer_id is provided, filter by that reviewer; otherwise show all tasks
    if reviewer_id:
        where = ["qc_assigned_to = ?"]
        params = [reviewer_id]
    else:
        where = []
        params = []
    
    if bucket == "in_progress":
        where.append("(qc_start_time IS NOT NULL AND qc_start_time <> '')")
        where.append("(qc_end_time IS NULL OR qc_end_time = '')")
        if not reviewer_id:
            # Show all in-progress tasks assigned to any QC reviewer
            where.append("qc_assigned_to IS NOT NULL")
    elif bucket == "rework_pending":
        where.append("qc_rework_required = 1")
        where.append("(qc_rework_completed IS NULL OR qc_rework_completed = 0)")
        # Don't require qc_end_time to be NULL - tasks can be in rework even after QC was completed
        # Include both assigned and unassigned rework tasks
        # Apply date filtering if date_range is provided
        date_range = request.args.get("date_range", "").lower()
        if date_range and date_range != "all_time":
            from datetime import datetime, timedelta
            today = datetime.utcnow().date()
            monday_this_week = today - timedelta(days=today.weekday())
            monday_prev_week = monday_this_week - timedelta(days=7)
            monday_next_week = monday_this_week + timedelta(days=7)
            
            if date_range == "this_week":
                ds, de = monday_this_week.isoformat(), monday_next_week.isoformat()
            elif date_range == "prev_week":
                ds, de = monday_prev_week.isoformat(), monday_this_week.isoformat()
            elif date_range == "last_30":
                ds, de = (today - timedelta(days=29)).isoformat(), (today + timedelta(days=1)).isoformat()
            else:
                ds, de = monday_this_week.isoformat(), monday_next_week.isoformat()
            
            where.append("qc_end_time IS NOT NULL")
            where.append("qc_end_time <> ''")
            where.append("date(qc_end_time) >= date(?)")
            where.append("date(qc_end_time) < date(?)")
            if reviewer_id:
                params = [reviewer_id, ds, de]
            else:
                params = [ds, de]
        else:
            if reviewer_id:
                where.append("qc_assigned_to = ?")
                params = [reviewer_id]
            else:
                params = []
        # If no reviewer_id, show all rework tasks (assigned and unassigned)
    elif bucket == "pending_recheck":
        where.append("qc_rework_required = 1")
        where.append("qc_rework_completed = 1")
        where.append("(qc_end_time IS NULL OR qc_end_time = '')")
        if not reviewer_id:
            where.append("qc_assigned_to IS NOT NULL")
    elif bucket == "awaiting_assignment":
        # Tasks that are completed, in QC sampling, but not yet assigned to QC
        where = ["date_completed IS NOT NULL"]
        where.append("(qc_assigned_to IS NULL OR qc_assigned_to = 0)")
        where.append("(qc_end_time IS NULL OR qc_end_time = '' OR qc_end_time = '0')")
        params = []
        # Note: JOIN with qc_sampling_log will be added in the query execution below
    elif bucket == "completed":
        # Tasks that have completed QC review
        # Exclude tasks that are in rework (rework required but not completed)
        where = ["qc_end_time IS NOT NULL"]
        where.append("qc_end_time <> ''")
        where.append("NOT (qc_rework_required = 1 AND (qc_rework_completed IS NULL OR qc_rework_completed = 0))")
        
        # Apply date filtering if date_range is provided
        date_range = request.args.get("date_range", "").lower()
        if date_range and date_range != "all_time":
            from datetime import datetime, timedelta
            today = datetime.utcnow().date()
            monday_this_week = today - timedelta(days=today.weekday())
            monday_prev_week = monday_this_week - timedelta(days=7)
            monday_next_week = monday_this_week + timedelta(days=7)
            
            if date_range == "this_week":
                ds, de = monday_this_week.isoformat(), monday_next_week.isoformat()
            elif date_range == "prev_week":
                ds, de = monday_prev_week.isoformat(), monday_this_week.isoformat()
            elif date_range == "last_30":
                ds, de = (today - timedelta(days=29)).isoformat(), (today + timedelta(days=1)).isoformat()
            else:
                ds, de = monday_this_week.isoformat(), monday_next_week.isoformat()
            
            where.append("date(qc_end_time) >= date(?)")
            where.append("date(qc_end_time) < date(?)")
            if reviewer_id:
                params = [reviewer_id, ds, de]
            else:
                params = [ds, de]
        else:
            if reviewer_id:
                params = [reviewer_id]
            else:
                params = []
    elif bucket == "all_wip":
        # Show all WIP tasks: assigned to QC reviewers OR awaiting assignment
        where = ["(qc_end_time IS NULL OR qc_end_time = '')"]
        where.append("(qc_assigned_to IS NOT NULL OR (date_completed IS NOT NULL AND (qc_assigned_to IS NULL OR qc_assigned_to = 0)))")
        params = []
    else:  # assigned (default)
        where.append("(qc_end_time IS NULL OR qc_end_time = '')")
        if not reviewer_id:
            # Show all assigned tasks (assigned to any QC reviewer, not awaiting assignment)
            where.append("qc_assigned_to IS NOT NULL")
    
    where_sql = " AND ".join(where)
    
    # Get reviewer name
    reviewer_name = None
    if reviewer_id:
        cur.execute("SELECT COALESCE(name, email) AS display_name FROM users WHERE id = ?", (reviewer_id,))
        r = cur.fetchone()
        reviewer_name = r["display_name"] if r else None
    
    # Determine if we need to join with qc_sampling_log
    # For awaiting_assignment, all_wip, and assigned buckets, we need to ensure tasks are in QC sampling
    # (assigned tasks should already be in QC sampling, but we check to be safe)
    needs_qc_sampling_join = (bucket in ["awaiting_assignment", "all_wip", "assigned"])
    
    # Get customer names from matches table
    from_clause = "FROM reviews r"
    if needs_qc_sampling_join:
        from_clause = "FROM reviews r INNER JOIN qc_sampling_log qsl ON qsl.review_id = r.id"
    
    cur.execute(f"""
        SELECT 
            r.task_id,
            r.customer_id,
            r.watchlist_id,
            r.qc_start_time,
            r.qc_end_time,
            COALESCE(r.qc_rework_required, 0) AS rework_required,
            COALESCE(r.qc_rework_completed, 0) AS rework_completed,
            CASE 
                WHEN r.qc_rework_completed = 1 AND r.qc_rework_required = 0 
                THEN r.review_end_time 
                ELSE NULL 
            END AS rework_completed_time,
            r.status,
            m.total_score AS match_score,
            m.entity_name AS customer_name,
            m.watchlist_entity_name AS watchlist_name,
            u.name AS current_qc_name
        {from_clause}
        LEFT JOIN matches m ON m.task_id = r.task_id
        LEFT JOIN users u ON u.id = r.qc_assigned_to
        WHERE {where_sql}
        ORDER BY COALESCE(r.qc_start_time, '') DESC, r.task_id DESC
""", params)
    
    rows = cur.fetchall()
    cases = [{
        "task_id": r["task_id"],
        "customer_id": r["customer_id"] if r["customer_id"] else None,
        "customer_name": r["customer_name"] or r["customer_id"] or None,
        "customer": r["customer_name"] or r["customer_id"] or None,
        "watchlist_id": r["watchlist_id"] if r["watchlist_id"] else None,
        "watchlist_name": r["watchlist_name"] or r["watchlist_id"] or None,
        "watchlist": r["watchlist_name"] or r["watchlist_id"] or None,
        "qc_start_time": r["qc_start_time"] if r["qc_start_time"] else None,
        "qc_start": r["qc_start_time"] if r["qc_start_time"] else None,
        "qc_end_time": r["qc_end_time"] if r["qc_end_time"] else None,
        "qc_end": r["qc_end_time"] if r["qc_end_time"] else None,
        "rework_required": bool(r["rework_required"]),
        "rework_completed": bool(r["rework_completed"]),
        "qc_rework_required": bool(r["rework_required"]),
        "qc_rework_completed": bool(r["rework_completed"]),
        "rework_completed_time": r["rework_completed_time"] if r["rework_completed_time"] else None,
        "status": r["status"] if r["status"] else None,
        "match_score": float(r["match_score"]) if r["match_score"] is not None else None,
        "current_qc": r["current_qc_name"] if r["current_qc_name"] else None,
        "reviewer_name": r["current_qc_name"] if r["current_qc_name"] else None
    } for r in rows]
    
    conn.close()
    
    return jsonify({
        'level': level,
        'bucket': bucket,
        'reviewer_id': reviewer_id,
        'reviewer_name': reviewer_name,
        'cases': cases
    })

@csrf.exempt
@app.route('/api/sampling_rates/reviewer/<int:reviewer_id>', methods=['POST', 'DELETE'], endpoint='api_set_reviewer_rate')
@role_required('qc_lead_1', 'qc_lead_2', 'qc_lead_3', 'qc_1', 'qc_2', 'qc_3', 'admin')
def api_set_reviewer_rate(reviewer_id):
    """Set or delete a reviewer-specific sampling rate"""
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        
        if request.method == 'DELETE':
            cur.execute("DELETE FROM sampling_rates WHERE reviewer_id = ?", (reviewer_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Reviewer rate deleted'})
        
        # POST - Set rate
        if request.is_json:
            form_data = request.json
        else:
            form_data = request.form.to_dict()
        
        rate = form_data.get('rate')
        if rate is None:
            return jsonify({'error': 'Rate is required'}), 400
        
        try:
            rate = float(rate)
            if rate < 0 or rate > 100:
                return jsonify({'error': 'Rate must be between 0 and 100'}), 400
        except ValueError:
            return jsonify({'error': 'Rate must be a number'}), 400
        
        # Check if rate already exists for this reviewer
        cur.execute("SELECT id FROM sampling_rates WHERE reviewer_id = ?", (reviewer_id,))
        existing = cur.fetchone()
        
        if existing:
            cur.execute("UPDATE sampling_rates SET rate = ? WHERE reviewer_id = ?", (rate, reviewer_id))
        else:
            # Insert reviewer rate - single-level system
            # Check if level column exists
            cur.execute("PRAGMA table_info(sampling_rates)")
            columns = [col[1] for col in cur.fetchall()]
            if 'level' in columns:
                # Level column exists - use default value 1 (single-level system)
                # since level has NOT NULL constraint
                cur.execute("INSERT INTO sampling_rates (reviewer_id, rate, level) VALUES (?, ?, 1)", (reviewer_id, rate))
            else:
                cur.execute("INSERT INTO sampling_rates (reviewer_id, rate) VALUES (?, ?)", (reviewer_id, rate))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Reviewer rate updated', 'rate': rate})
        
    except sqlite3.OperationalError as e:
        if conn:
            conn.rollback()
        import traceback
        error_msg = str(e)
        if 'locked' in error_msg.lower():
            error_msg = 'Database is locked. Please try again in a moment.'
        print(f"Error in api_set_reviewer_rate: {error_msg}\n{traceback.format_exc()}")
        return jsonify({'error': error_msg}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        import traceback
        print(f"Error in api_set_reviewer_rate: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ============================================================================
# Transaction Review API Endpoints
# ============================================================================

def _period_bounds(period):
    """Convert period string to (start_date, end_date) tuple"""
    from datetime import date, timedelta
    today = date.today()
    if period == "all":
        return (None, None)
    elif period == "3m":
        start = (today.replace(day=1) - timedelta(days=93)).replace(day=1)
        return (start.isoformat(), today.isoformat())
    elif period == "6m":
        start = (today.replace(day=1) - timedelta(days=186)).replace(day=1)
        return (start.isoformat(), today.isoformat())
    elif period == "12m":
        start = (today.replace(day=1) - timedelta(days=365)).replace(day=1)
        return (start.isoformat(), today.isoformat())
    elif period == "ytd":
        return (date(today.year, 1, 1).isoformat(), today.isoformat())
    elif period.startswith("month:"):
        try:
            year, month = map(int, period.split(":")[1].split("-"))
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
            return (start.isoformat(), end.isoformat())
        except:
            return (None, None)
    return (None, None)

def country_full_name(iso2):
    """Get full country name from ISO2 code"""
    country_map = {
        "GB": "United Kingdom", "IE": "Ireland", "US": "United States",
        "FR": "France", "DE": "Germany", "IT": "Italy", "ES": "Spain",
        "NL": "Netherlands", "BE": "Belgium", "CH": "Switzerland",
        "AE": "United Arab Emirates", "TR": "Turkey", "RU": "Russia",
        "IR": "Iran", "CN": "China", "JP": "Japan", "IN": "India",
    }
    return country_map.get(iso2, iso2 or "Unknown")

@csrf.exempt
@app.route('/api/transaction/dashboard', methods=['GET'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager')
def api_transaction_dashboard():
    """Transaction Review Dashboard API - returns JSON data for dashboard"""
    try:
        customer_id = request.args.get("customer_id", "").strip()
        period = request.args.get("period", "12m")
        
        if not customer_id:
            return jsonify({
                "error": "customer_id is required"
            }), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        start, end = _period_bounds(period)
        
        # Build WHERE clauses
        tx_where, tx_params = ["t.customer_id = ?"], [customer_id]
        a_where, a_params = ["a.customer_id = ?"], [customer_id]
        
        if start and end:
            tx_where.append("t.txn_date BETWEEN ? AND ?")
            tx_params += [start, end]
            a_where.append("a.created_at BETWEEN ? AND ?")
            a_params += [start + " 00:00:00", end + " 23:59:59"]
        
        tx_pred = "WHERE " + " AND ".join(tx_where)
        a_pred = "WHERE " + " AND ".join(a_where)
        
        # KPIs
        cur.execute(f"SELECT COUNT(*) c FROM transactions t {tx_pred}", tx_params)
        total_tx = cur.fetchone()["c"]
        
        cur.execute(f"SELECT COUNT(*) c FROM alerts a {a_pred}", a_params)
        total_alerts = cur.fetchone()["c"]
        
        cur.execute(f"SELECT COUNT(*) c FROM alerts a {a_pred} AND a.severity='CRITICAL'", a_params)
        critical = cur.fetchone()["c"]
        
        kpis = {
            "total_tx": total_tx,
            "total_alerts": total_alerts,
            "alert_rate": (total_alerts / total_tx) if total_tx else 0,
            "critical": critical,
        }
        
        # Tiles
        cur.execute(f"""
            SELECT
                SUM(CASE WHEN t.direction='in' THEN t.base_amount ELSE 0 END) AS total_in,
                SUM(CASE WHEN t.direction='out' THEN t.base_amount ELSE 0 END) AS total_out
            FROM transactions t {tx_pred}
        """, tx_params)
        sums = cur.fetchone()
        total_in = float(sums["total_in"] or 0)
        total_out = float(sums["total_out"] or 0)
        
        cur.execute(f"""
            SELECT
                SUM(CASE WHEN t.direction='in' AND lower(IFNULL(t.channel,''))='cash'
                    THEN t.base_amount ELSE 0 END) AS cash_in,
                SUM(CASE WHEN t.direction='out' AND lower(IFNULL(t.channel,''))='cash'
                    THEN t.base_amount ELSE 0 END) AS cash_out
            FROM transactions t {tx_pred}
        """, tx_params)
        cash = cur.fetchone()
        cash_in = float(cash["cash_in"] or 0)
        cash_out = float(cash["cash_out"] or 0)
        
        cur.execute(f"""
            SELECT COUNT(*) AS cnt, SUM(t.base_amount) AS total
            FROM transactions t
            JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2, '')
            {tx_pred + (' AND ' if tx_pred else 'WHERE ')} r.risk_level IN ('HIGH','HIGH_3RD','PROHIBITED')
        """, tx_params)
        hr = cur.fetchone()
        high_risk_total = float(hr["total"] or 0)
        
        tiles = {
            "total_in": total_in,
            "total_out": total_out,
            "cash_in": cash_in,
            "cash_out": cash_out,
            "high_risk_total": high_risk_total,
        }
        
        # Alerts over time — group by MONTH (t.txn_date)
        if start and end:
            aot_sql = """
                SELECT strftime('%Y-%m', t.txn_date) d, COUNT(*) c
                FROM alerts a
                JOIN transactions t ON t.id = a.txn_id
                WHERE t.customer_id = ? AND t.txn_date BETWEEN ? AND ?
                GROUP BY d ORDER BY d
            """
            aot_params = [customer_id, start, end]
        else:
            aot_sql = """
                SELECT strftime('%Y-%m', t.txn_date) d, COUNT(*) c
                FROM alerts a
                JOIN transactions t ON t.id = a.txn_id
                WHERE t.customer_id = ?
                GROUP BY d ORDER BY d
            """
            aot_params = [customer_id]
        cur.execute(aot_sql, aot_params)
        aot_rows = cur.fetchall()
        labels = [r["d"] for r in aot_rows]
        values = [int(r["c"]) for r in aot_rows]
        
        # Top countries (alerts) — show full country names
        cur.execute(f"""
            SELECT t.country_iso2, COUNT(*) cnt
            FROM alerts a
            JOIN transactions t ON t.id = a.txn_id
            {a_pred}
            GROUP BY t.country_iso2
            ORDER BY cnt DESC
            LIMIT 10
        """, a_params)
        tc_rows = cur.fetchall()
        top_countries = [
            {"name": country_full_name(r["country_iso2"]), "cnt": int(r["cnt"] or 0)}
            for r in tc_rows
        ]
        
        # Monthly trends
        cur.execute(f"""
            SELECT strftime('%Y-%m', t.txn_date) ym,
                   SUM(CASE WHEN t.direction='in' THEN t.base_amount ELSE 0 END) AS in_sum,
                   SUM(CASE WHEN t.direction='out' THEN t.base_amount ELSE 0 END) AS out_sum
            FROM transactions t {tx_pred}
            GROUP BY ym
            ORDER BY ym
        """, tx_params)
        trend_rows = cur.fetchall()
        trend_labels = [r["ym"] for r in trend_rows]
        trend_in = [float(r["in_sum"] or 0) for r in trend_rows]
        trend_out = [float(r["out_sum"] or 0) for r in trend_rows]
        
        # Reviewer metrics
        cur.execute(f"""
            SELECT
                AVG(CASE WHEN t.direction='in' AND lower(IFNULL(t.channel,''))='cash' THEN t.base_amount END) AS avg_cash_in,
                AVG(CASE WHEN t.direction='out' AND lower(IFNULL(t.channel,''))='cash' THEN t.base_amount END) AS avg_cash_out,
                AVG(CASE WHEN t.direction='in' THEN t.base_amount END) AS avg_in,
                AVG(CASE WHEN t.direction='out' THEN t.base_amount END) AS avg_out,
                MAX(CASE WHEN t.direction='in' THEN t.base_amount END) AS max_in,
                MAX(CASE WHEN t.direction='out' THEN t.base_amount END) AS max_out,
                SUM(CASE WHEN IFNULL(t.country_iso2,'')<>'' AND UPPER(t.country_iso2)<>'GB' THEN t.base_amount ELSE 0 END) AS overseas_value,
                SUM(t.base_amount) AS total_value
            FROM transactions t {tx_pred}
        """, tx_params)
        m = cur.fetchone()
        avg_cash_deposits = float(m["avg_cash_in"] or 0.0)
        avg_cash_withdrawals = float(m["avg_cash_out"] or 0.0)
        avg_in = float(m["avg_in"] or 0.0)
        avg_out = float(m["avg_out"] or 0.0)
        max_in = float(m["max_in"] or 0.0)
        max_out = float(m["max_out"] or 0.0)
        overseas_value = float(m["overseas_value"] or 0.0)
        total_val_from_query = float(m["total_value"] or 0.0)
        denom_total = total_in + total_out if (total_in + total_out) > 0 else total_val_from_query
        overseas_pct = (overseas_value / denom_total * 100.0) if denom_total > 0 else 0.0
        
        cur.execute(f"""
            SELECT SUM(t.base_amount) AS v
            FROM transactions t
            JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2, '')
            {tx_pred + (' AND ' if tx_pred else 'WHERE ')} r.risk_level IN ('HIGH','HIGH_3RD','PROHIBITED')
        """, tx_params)
        hr_val_row = cur.fetchone()
        highrisk_value = float(hr_val_row["v"] or 0.0)
        highrisk_pct = (highrisk_value / denom_total * 100.0) if denom_total > 0 else 0.0
        
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
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "kpis": kpis,
            "tiles": tiles,
            "labels": labels,
            "values": values,
            "top_countries": top_countries,
            "trend_labels": trend_labels,
            "trend_in": trend_in,
            "trend_out": trend_out,
            "metrics": metrics,
            "filter_meta": {"customer_id": customer_id},
            "selected_period": period
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_transaction_dashboard: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/transaction/alerts', methods=['GET'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager')
def api_transaction_alerts():
    """Transaction Review Alerts API"""
    try:
        customer_id = request.args.get("customer_id", "").strip()
        severity = request.args.get("severity", "").strip().upper()
        tag = request.args.get("tag", "").strip()
        
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        where, params = [], []
        if customer_id:
            where.append("a.customer_id = ?")
            params.append(customer_id)
        if severity:
            where.append("a.severity = ?")
            params.append(severity)
        
        where_clause = "WHERE " + " AND ".join(where) if where else ""
        
        sql = f"""
            SELECT a.*, 
                   t.id as transaction_id,
                   t.base_amount as amount,
                   t.currency,
                   t.country_iso2, 
                   t.txn_date as transaction_date
            FROM alerts a
            LEFT JOIN transactions t ON t.id = a.txn_id
            {where_clause}
            ORDER BY t.txn_date DESC, a.created_at DESC
            LIMIT 500
        """
        rows = cur.execute(sql, params).fetchall()
        
        # Build tag list
        tag_set = set()
        for r in rows:
            try:
                tags = json.loads(r["rule_tags"] or "[]")
                for tg in tags:
                    if tg:
                        tag_set.add(str(tg))
            except:
                pass
        available_tags = sorted(tag_set)
        
        # Process alerts
        alerts = []
        for r in rows:
            d = dict(r)
            try:
                reasons_list = json.loads(d.get("reasons") or "[]")
            except:
                reasons_list = [d.get("reasons")] if d.get("reasons") else []
            
            try:
                tags_list = json.loads(d.get("rule_tags") or "[]")
            except:
                tags_list = []
            
            # Apply tag filter
            if tag and tag not in tags_list:
                continue
            
            d["reasons"] = ", ".join(x for x in reasons_list if x)
            d["rule_tags"] = ", ".join(tags_list)
            alerts.append(d)
        
        # Debug logging
        print(f"[ALERTS] Returning {len(alerts)} alerts for customer {customer_id}")
        if alerts:
            print(f"[ALERTS] Sample alert keys: {list(alerts[0].keys())}")
            sample = alerts[0]
            print(f"[ALERTS] Sample alert: transaction_id={sample.get('transaction_id')}, amount={sample.get('amount')}, currency={sample.get('currency')}")
        
        conn.close()
        
        # Debug: print actual JSON being returned
        import json
        if alerts:
            print(f"[ALERTS] First alert being returned:")
            first_alert = alerts[0]
            for key in ['transaction_id', 'amount', 'currency', 'transaction_date', 'severity']:
                print(f"  {key}: {first_alert.get(key)}")
        
        return jsonify({
            "status": "ok",
            "alerts": alerts,
            "available_tags": available_tags
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_transaction_alerts: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/transaction/explore', methods=['GET'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager')
def api_transaction_explore():
    """Transaction Review Explore API"""
    try:
        customer_id = request.args.get("customer_id", "").strip()
        direction = request.args.get("direction", "").strip()
        channel = request.args.get("channel", "").strip()
        risk = request.args.get("risk", "").strip()
        date_from = request.args.get("date_from", "").strip()
        date_to = request.args.get("date_to", "").strip()
        
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        where, params = ["t.customer_id = ?"], [customer_id]
        join_risk = False
        
        if direction in ("in", "out"):
            where.append("t.direction = ?")
            params.append(direction)
        if channel:
            where.append("lower(IFNULL(t.channel,'')) = ?")
            params.append(channel.lower())
        
        # Risk filter
        valid_risks = {"LOW", "MEDIUM", "HIGH", "HIGH_3RD", "PROHIBITED"}
        risk_list = [r.strip().upper() for r in risk.split(",") if r.strip()]
        risk_list = [r for r in risk_list if r in valid_risks]
        if risk_list:
            placeholders = ",".join(["?"] * len(risk_list))
            where.append(f"r.risk_level IN ({placeholders})")
            params.extend(risk_list)
        
        if date_from:
            where.append("t.txn_date >= ?")
            params.append(date_from)
        if date_to:
            where.append("t.txn_date <= ?")
            params.append(date_to)
        
        where_clause = "WHERE " + " AND ".join(where)
        
        sql = f"""
            SELECT t.id, t.txn_date, t.customer_id, t.direction, t.base_amount, t.currency,
                   t.country_iso2, t.channel, t.payer_sort_code, t.payee_sort_code, t.narrative,
                   r.risk_level, r.score as country_score,
                   a.id as alert_id, a.severity as alert_severity, a.score as alert_score
            FROM transactions t
            LEFT JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2, 'GB')
            LEFT JOIN alerts a ON a.txn_id = t.id
            {where_clause}
            ORDER BY t.txn_date DESC, t.id DESC
            LIMIT 1000
        """
        
        rows = cur.execute(sql, params).fetchall()
        transactions = []
        print(f"[EXPLORE] Processing {len(rows)} transactions for customer {customer_id}")
        
        for r in rows:
            tx = dict(r)
            
            # Calculate risk score based on country risk and alerts
            country_score = tx.get('country_score', 0) or 0
            alert_score = tx.get('alert_score', 0) or 0
            alert_severity = tx.get('alert_severity', '')
            
            # Risk score is max of country score and alert score, normalized to 0-1
            risk_score = max(country_score, alert_score) / 100.0
            
            # Determine risk level for display
            # CRITICAL: PROHIBITED countries or CRITICAL alerts (score 100)
            if alert_severity == 'CRITICAL' or country_score == 100:
                risk_level = 'CRITICAL'
            # HIGH: HIGH alerts or risk score >= 70%
            elif alert_severity == 'HIGH' or risk_score >= 0.7:
                risk_level = 'HIGH'
            # MEDIUM: MEDIUM alerts or risk score >= 40%
            elif alert_severity == 'MEDIUM' or risk_score >= 0.4:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'
            
            # Debug log for problematic transactions
            if tx.get('country_iso2') == 'KP' or (alert_severity and alert_severity != 'LOW'):
                print(f"[EXPLORE] TX {tx.get('id')}: country={tx.get('country_iso2')}, country_score={country_score}, alert_score={alert_score}, alert_severity={alert_severity}, risk_score={risk_score}, risk_level={risk_level}")
            
            # Map backend fields to frontend expected field names
            transactions.append({
                'id': tx.get('id'),
                'transaction_date': tx.get('txn_date'),
                'reference': tx.get('id'),
                'description': tx.get('narrative'),
                'counterparty': f"{tx.get('payer_sort_code', '')} / {tx.get('payee_sort_code', '')}" if tx.get('payer_sort_code') else '—',
                'counterparty_country': tx.get('country_iso2'),
                'payment_method': tx.get('channel'),
                'amount': tx.get('base_amount'),
                'currency': tx.get('currency', 'GBP'),
                'direction': tx.get('direction'),
                'risk_score': risk_score,
                'risk_level': risk_level,
                'has_alert': bool(tx.get('alert_id')),
                'alert_severity': alert_severity,
                'flagged': bool(tx.get('alert_id'))
            })
        
        # Get distinct channels
        ch_rows = cur.execute("SELECT DISTINCT lower(IFNULL(channel,'')) as ch FROM transactions WHERE customer_id = ? ORDER BY ch", (customer_id,)).fetchall()
        channels = [r["ch"] for r in ch_rows if r["ch"]]
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "transactions": transactions,
            "channels": channels
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_transaction_explore: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/transaction/ai', methods=['GET', 'POST'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager')
def api_transaction_ai():
    """Transaction Review AI Outreach API"""
    try:
        # Ensure AI tables exist
        ensure_ai_tables()
        
        customer_id = request.args.get("customer_id") or request.form.get("customer_id", "").strip()
        period = request.args.get("period") or request.form.get("period", "3m")
        action = request.args.get("action") or request.form.get("action", "")
        
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Period bounds
        today = date.today()
        if period == "all":
            p_from, p_to = None, None
        elif period.endswith("m") and period[:-1].isdigit():
            months = int(period[:-1])
            start_month = (today.replace(day=1) - timedelta(days=months * 31)).replace(day=1)
            p_from, p_to = start_month.isoformat(), today.isoformat()
        else:
            p_from, p_to = None, None
        
        # Handle POST actions
        if request.method == "POST":
            action = request.form.get("action", "")
            
            # Build questions action
            if action == "build":
                # Get or create AI case
                case_row = cur.execute(
                    "SELECT * FROM ai_cases WHERE customer_id=? ORDER BY updated_at DESC LIMIT 1",
                    (customer_id,)
                ).fetchone()
                
                if not case_row:
                    cur.execute(
                        "INSERT INTO ai_cases(customer_id, period_from, period_to) VALUES(?,?,?)",
                        (customer_id, p_from, p_to)
                    )
                    conn.commit()
                    case_row = cur.execute(
                        "SELECT * FROM ai_cases WHERE customer_id=? ORDER BY id DESC LIMIT 1",
                        (customer_id,)
                    ).fetchone()
                
                # Fetch alerts for this customer in the period
                alert_sql = """
                    SELECT a.id, a.txn_id, a.score, a.severity, a.reasons, a.rule_tags,
                           t.txn_date, t.amount, t.currency, t.country_iso2, t.direction, t.narrative
                    FROM alerts a
                    JOIN transactions t ON t.id = a.txn_id
                    WHERE t.customer_id = ?
                """
                alert_params = [customer_id]
                
                if p_from and p_to:
                    alert_sql += " AND t.txn_date BETWEEN ? AND ?"
                    alert_params.extend([p_from, p_to])
                
                alert_sql += " ORDER BY a.score DESC, t.txn_date DESC LIMIT 10"
                
                alerts = cur.execute(alert_sql, alert_params).fetchall()
                
                if not alerts:
                    # No alerts found - return error
                    return jsonify({
                        "status": "error",
                        "message": f"No alerts found for {customer_id} in the selected period.",
                        "customer_id": customer_id,
                        "period": period
                    }), 400
                
                # Generate questions using LLM
                try:
                    generated_questions = generate_ai_outreach_questions(customer_id, alerts)
                except Exception as e:
                    print(f"Error generating AI questions: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Fallback to simple questions if LLM fails
                    generated_questions = generate_fallback_questions(alerts)
                
                # Clear existing answers and insert new questions
                cur.execute("DELETE FROM ai_answers WHERE case_id=?", (case_row["id"],))
                for q in generated_questions:
                    cur.execute(
                        "INSERT INTO ai_answers(case_id, tag, question) VALUES(?,?,?)",
                        (case_row["id"], q["tag"], q["question"])
                    )
                conn.commit()
                
                return jsonify({
                    "status": "ok",
                    "message": f"Prepared {len(generated_questions)} AI-generated question(s) for {customer_id}.",
                    "customer_id": customer_id,
                    "period": period
                })
            
            # Save answers action
            if action == "save":
                case_id = int(request.form.get("case_id", 0))
                if case_id:
                    # Get all qid values
                    qids = request.form.getlist("qid")
                    for qid in qids:
                        answer = request.form.get(f"answer_{qid}", "")
                        cur.execute(
                            "UPDATE ai_answers SET answer=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (answer, qid)
                        )
                    cur.execute("UPDATE ai_cases SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
                    conn.commit()
                    
                    return jsonify({
                        "status": "ok",
                        "message": "Responses saved.",
                        "customer_id": customer_id,
                        "period": period
                    })
            
            # Build Outreach Pack action
            if action == "outreach":
                case_id = int(request.form.get("case_id", 0))
                if case_id:
                    answers_rows = cur.execute(
                        "SELECT * FROM ai_answers WHERE case_id=? ORDER BY id",
                        (case_id,)
                    ).fetchall()
                    
                    # Build outreach email text (matching original format)
                    from datetime import datetime
                    when = datetime.now().strftime("%d %B %Y")
                    
                    outreach_lines = [
                        f"Subject: Information request regarding recent account activity ({customer_id})",
                        "",
                        "Dear Customer,",
                        "",
                        "We're reviewing recent activity on your account and would be grateful if you could "
                        "provide further information to help us complete our checks.",
                        "",
                        "Please respond to the questions below:",
                        ""
                    ]
                    
                    for i, ans in enumerate(answers_rows, start=1):
                        # Convert Row to dict if needed
                        ans_dict = dict(ans) if hasattr(ans, 'keys') else ans
                        q = (ans_dict.get("question") or "").strip()
                        if q and not q.endswith("?"):
                            q += "?"
                        if q:
                            outreach_lines.append(f"{i}. {q}")
                    
                    outreach_lines.extend([
                        "",
                        "If you have any supporting documents (e.g., invoices or contracts), please include them.",
                        "",
                        "Kind regards,",
                        "Compliance Team",
                        when
                    ])
                    
                    outreach_text = "\n".join(outreach_lines)
                    
                    return jsonify({
                        "status": "ok",
                        "customer_id": customer_id,
                        "period": period,
                        "outreach_text": outreach_text
                    })
            
            # Run Assessment action
            if action == "assess":
                case_id = int(request.form.get("case_id", 0))
                if case_id:
                    answers_rows = cur.execute(
                        "SELECT * FROM ai_answers WHERE case_id=? ORDER BY id",
                        (case_id,)
                    ).fetchall()
                    
                    # Simple assessment scoring
                    total_score = 0
                    answered_count = 0
                    for ans in answers_rows:
                        # Convert Row to dict if needed
                        ans_dict = dict(ans) if hasattr(ans, 'keys') else ans
                        answer_text = ans_dict.get("answer") or ""
                        if answer_text and answer_text.strip():
                            answered_count += 1
                            # Simple scoring: detailed answers reduce risk
                            answer_len = len(answer_text.strip())
                            if answer_len > 100:
                                total_score -= 5  # Detailed answer reduces risk
                            elif answer_len > 50:
                                total_score -= 2
                            else:
                                total_score += 2  # Short answers increase risk
                        else:
                            total_score += 5  # Unanswered increases risk
                    
                    # Determine risk band
                    if total_score >= 20:
                        risk_band = "CRITICAL"
                    elif total_score >= 10:
                        risk_band = "HIGH"
                    elif total_score >= 5:
                        risk_band = "MEDIUM"
                    elif total_score >= 0:
                        risk_band = "LOW"
                    else:
                        risk_band = "INFO"
                    
                    assessment_summary = f"Assessment completed. Score: {total_score}, Risk: {risk_band}. {answered_count} of {len(answers_rows)} questions answered."
                    
                    # Update case with assessment
                    cur.execute("""
                        UPDATE ai_cases 
                        SET assessment_score=?, assessment_risk=?, assessment_summary=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (total_score, risk_band, assessment_summary, case_id))
                    conn.commit()
                    
                    return jsonify({
                        "status": "ok",
                        "message": "Assessment completed.",
                        "customer_id": customer_id,
                        "period": period,
                        "assessment_score": total_score,
                        "assessment_risk": risk_band,
                        "assessment_summary": assessment_summary
                    })
        
        # GET: Load case and answers
        case_row = cur.execute(
            "SELECT * FROM ai_cases WHERE customer_id=? ORDER BY updated_at DESC LIMIT 1",
            (customer_id,)
        ).fetchone()
        
        answers = []
        proposed_questions = []
        if case_row:
            answers_rows = cur.execute(
                "SELECT * FROM ai_answers WHERE case_id=? ORDER BY id",
                (case_row["id"],)
            ).fetchall()
            answers = [dict(r) for r in answers_rows]
        else:
            # No proposed questions - user must click "Prepare Questions" to generate them
            proposed_questions = []
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "customer_id": customer_id,
            "period": period,
            "period_from": p_from,
            "period_to": p_to,
            "case": dict(case_row) if case_row else None,
            "answers": answers,
            "proposed_questions": proposed_questions
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_transaction_ai: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

def ensure_ai_tables():
    """Ensure ai_cases and ai_answers tables exist with correct schema"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create ai_cases table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ai_cases (
          id INTEGER PRIMARY KEY,
          customer_id TEXT NOT NULL,
          period_from TEXT,
          period_to TEXT,
          assessment_risk TEXT,
          assessment_score INTEGER,
          assessment_summary TEXT,
          rationale_text TEXT,
          rationale_generated_at TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create ai_answers table
    cur.execute("""
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
    
    # Add missing columns if they don't exist
    for col in ['assessment_risk', 'assessment_score', 'assessment_summary']:
        try:
            cur.execute(f"SELECT {col} FROM ai_cases LIMIT 1")
        except sqlite3.OperationalError:
            try:
                col_type = 'TEXT' if col == 'assessment_risk' or col == 'assessment_summary' else 'INTEGER'
                cur.execute(f"ALTER TABLE ai_cases ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass
    
    conn.commit()
    conn.close()

def ensure_ai_rationale_table():
    """Ensure ai_rationales table exists with correct schema"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create table if it doesn't exist
    cur.execute("""
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
    
    # Check if rationale_text column exists, add it if missing
    try:
        cur.execute("SELECT rationale_text FROM ai_rationales LIMIT 1")
    except sqlite3.OperationalError:
        # Column doesn't exist, add it
        try:
            cur.execute("ALTER TABLE ai_rationales ADD COLUMN rationale_text TEXT")
        except sqlite3.OperationalError:
            pass  # Column might already exist or table is empty
    
    conn.commit()
    conn.close()

# API endpoint to extract Transaction Review rationale to Due Diligence
@csrf.exempt
@app.route('/api/transaction/extract_rationale/<task_id>', methods=['POST'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager', 'admin')
def api_extract_rationale(task_id):
    """Extract Transaction Review rationale into Due Diligence module"""
    try:
        import sqlite3
        from datetime import datetime
        
        data = request.get_json() or {}
        rationale_text = data.get('rationale_text', '').strip()
        nature_of_business = data.get('nature_of_business', '').strip()
        est_income = data.get('est_income', '').strip()
        est_expenditure = data.get('est_expenditure', '').strip()
        
        if not rationale_text:
            return jsonify({'error': 'No rationale text provided'}), 400
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Get the review and check status
        cur.execute("SELECT id, status FROM reviews WHERE task_id = ?", (task_id,))
        review = cur.fetchone()
        if not review:
            conn.close()
            return jsonify({'error': 'Task not found'}), 404
        
        # Check if task is completed
        review_status = dict(review).get('status', '').lower() if review else ''
        if review_status == 'completed':
            conn.close()
            return jsonify({'error': 'Cannot update rationale: Task is completed'}), 403
        
        # Update the review with rationale in TA (Transactional Analysis) field
        now = datetime.utcnow().isoformat(timespec='seconds')
        update_fields = {
            'ta_rationale': rationale_text,
            'updated_at': now
        }
        
        # Add optional fields if provided
        if nature_of_business:
            # Check if column exists
            cur.execute("PRAGMA table_info(reviews)")
            columns = [col[1] for col in cur.fetchall()]
            if 'nature_of_business' in columns:
                update_fields['nature_of_business'] = nature_of_business
        
        if est_income:
            try:
                est_income_val = float(est_income)
                cur.execute("PRAGMA table_info(reviews)")
                columns = [col[1] for col in cur.fetchall()]
                if 'est_income' in columns:
                    update_fields['est_income'] = est_income_val
            except ValueError:
                pass
        
        if est_expenditure:
            try:
                est_expenditure_val = float(est_expenditure)
                cur.execute("PRAGMA table_info(reviews)")
                columns = [col[1] for col in cur.fetchall()]
                if 'est_expenditure' in columns:
                    update_fields['est_expenditure'] = est_expenditure_val
            except ValueError:
                pass
        
        # Update the review
        set_clause = ', '.join(f'{k} = ?' for k in update_fields.keys())
        values = list(update_fields.values()) + [task_id]
        cur.execute(f'UPDATE reviews SET {set_clause} WHERE task_id = ?', values)
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Rationale extracted to Due Diligence successfully'
        })
    except Exception as e:
        import traceback
        print(f"Error in api_extract_rationale: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/transaction/ai-rationale', methods=['GET', 'POST'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'team_lead_1', 'team_lead_2', 'team_lead_3', 'operations_manager')
def api_transaction_ai_rationale():
    """Transaction Review AI Rationale API"""
    try:
        # Ensure table exists
        ensure_ai_rationale_table()
        
        customer_id = request.args.get("customer_id") or request.form.get("customer_id", "").strip()
        period = request.args.get("period") or request.form.get("period", "3m")
        action = request.args.get("action") or request.form.get("action", "")
        
        if not customer_id:
            return jsonify({"error": "customer_id is required"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Period bounds
        today = date.today()
        if period == "all":
            p_from, p_to = None, None
        elif period.endswith("m") and period[:-1].isdigit():
            months = int(period[:-1])
            start_month = (today.replace(day=1) - timedelta(days=months * 31)).replace(day=1)
            p_from, p_to = start_month.isoformat(), today.isoformat()
        else:
            p_from, p_to = None, None
        
        # POST: Generate rationale
        if request.method == "POST" and action == "generate":
            # Check task status if task_id is provided
            task_id = request.form.get("task_id", "").strip()
            if task_id:
                cur.execute("SELECT status FROM reviews WHERE task_id = ?", (task_id,))
                task_review = cur.fetchone()
                if task_review:
                    task_status = dict(task_review).get('status', '').lower()
                    if task_status == 'completed':
                        conn.close()
                        return jsonify({'error': 'Cannot update rationale: Task is completed'}), 403
            
            nature_of_business = request.form.get("nature_of_business", "").strip() or None
            est_income_str = request.form.get("est_income", "").strip()
            est_expenditure_str = request.form.get("est_expenditure", "").strip()
            
            def _to_float_or_none(s):
                try:
                    return float(str(s).replace(",", "")) if s and s not in ("", "None") else None
                except:
                    return None
            
            est_income = _to_float_or_none(est_income_str)
            est_expenditure = _to_float_or_none(est_expenditure_str)
            
            # Fetch transaction data for the period to build comprehensive rationale
            tx_where = ["t.customer_id = ?"]
            tx_params = [customer_id]
            if p_from:
                tx_where.append("t.txn_date >= ?")
                tx_params.append(p_from)
            if p_to:
                tx_where.append("t.txn_date <= ?")
                tx_params.append(p_to)
            
            tx_sql = f"""
                SELECT t.id, t.txn_date, t.direction, t.base_amount, t.currency, t.country_iso2,
                       r.risk_level, r.score as country_score,
                       a.id as alert_id, a.severity as alert_severity, a.reasons
                FROM transactions t
                LEFT JOIN ref_country_risk r ON r.iso2 = IFNULL(t.country_iso2, 'GB')
                LEFT JOIN alerts a ON a.txn_id = t.id
                WHERE {' AND '.join(tx_where)}
                ORDER BY t.txn_date DESC
            """
            
            tx_rows = cur.execute(tx_sql, tx_params).fetchall()
            
            # Calculate transaction statistics
            total_in = sum(row['base_amount'] for row in tx_rows if row['direction'] == 'in')
            total_out = sum(row['base_amount'] for row in tx_rows if row['direction'] == 'out')
            count_in = sum(1 for row in tx_rows if row['direction'] == 'in')
            count_out = sum(1 for row in tx_rows if row['direction'] == 'out')
            
            # Analyze alerts
            critical_alerts = [row for row in tx_rows if row['alert_severity'] == 'CRITICAL']
            high_alerts = [row for row in tx_rows if row['alert_severity'] == 'HIGH']
            medium_alerts = [row for row in tx_rows if row['alert_severity'] == 'MEDIUM']
            
            # Analyze country risk
            prohibited_txns = [row for row in tx_rows if row['risk_level'] == 'PROHIBITED']
            high_risk_txns = [row for row in tx_rows if row['risk_level'] in ('HIGH', 'HIGH_3RD')]
            
            # Get unique high-risk countries
            high_risk_countries = set()
            for row in tx_rows:
                if row['risk_level'] in ('PROHIBITED', 'HIGH', 'HIGH_3RD'):
                    high_risk_countries.add(row['country_iso2'])
            
            # Build comprehensive rationale text
            rationale_text = f"Transaction Review Analysis for {customer_id}\n"
            rationale_text += f"Period: {p_from or 'inception'} to {p_to or 'present'}\n"
            rationale_text += "=" * 80 + "\n\n"
            
            # Business information
            if nature_of_business:
                rationale_text += f"NATURE OF BUSINESS:\n{nature_of_business}\n\n"
            
            # Transaction summary
            rationale_text += f"TRANSACTION SUMMARY:\n"
            rationale_text += f"• Total transactions analyzed: {len(tx_rows)}\n"
            rationale_text += f"• Incoming: {count_in} transactions totaling £{total_in:,.2f}\n"
            rationale_text += f"• Outgoing: {count_out} transactions totaling £{total_out:,.2f}\n"
            rationale_text += f"• Net position: £{(total_in - total_out):,.2f}\n\n"
            
            # Financial estimates
            if est_income or est_expenditure:
                rationale_text += f"ESTIMATED FINANCIALS:\n"
                if est_income:
                    rationale_text += f"• Expected monthly income: £{est_income:,.2f}\n"
                if est_expenditure:
                    rationale_text += f"• Expected monthly expenditure: £{est_expenditure:,.2f}\n"
                rationale_text += "\n"
            
            # Alerts analysis
            if critical_alerts or high_alerts or medium_alerts:
                rationale_text += f"ALERTS IDENTIFIED:\n"
                if critical_alerts:
                    rationale_text += f"• CRITICAL: {len(critical_alerts)} alert(s)\n"
                    for alert in critical_alerts[:3]:  # Show first 3
                        try:
                            reasons = json.loads(alert['reasons']) if alert['reasons'] else []
                            reason_text = reasons[0] if reasons else "High-risk transaction"
                        except:
                            reason_text = "High-risk transaction"
                        rationale_text += f"  - {alert['id']}: {reason_text}\n"
                
                if high_alerts:
                    rationale_text += f"• HIGH: {len(high_alerts)} alert(s)\n"
                    for alert in high_alerts[:3]:  # Show first 3
                        try:
                            reasons = json.loads(alert['reasons']) if alert['reasons'] else []
                            reason_text = reasons[0] if reasons else "High-risk transaction"
                        except:
                            reason_text = "High-risk transaction"
                        rationale_text += f"  - {alert['id']}: {reason_text}\n"
                
                if medium_alerts:
                    rationale_text += f"• MEDIUM: {len(medium_alerts)} alert(s)\n"
                
                rationale_text += "\n"
            
            # Country risk analysis
            if prohibited_txns or high_risk_txns:
                rationale_text += f"HIGH-RISK JURISDICTIONS:\n"
                if prohibited_txns:
                    rationale_text += f"• PROHIBITED countries: {len(prohibited_txns)} transaction(s)\n"
                    for tx in prohibited_txns[:5]:
                        rationale_text += f"  - {tx['id']}: {tx['country_iso2']} - £{tx['base_amount']:,.2f} ({tx['direction']})\n"
                
                if high_risk_txns:
                    rationale_text += f"• HIGH risk countries: {len(high_risk_txns)} transaction(s)\n"
                
                if high_risk_countries:
                    rationale_text += f"• Countries of concern: {', '.join(sorted(high_risk_countries))}\n"
                
                rationale_text += "\n"
            
            # Recommendations
            rationale_text += f"RECOMMENDATIONS:\n"
            if critical_alerts or prohibited_txns:
                rationale_text += "• IMMEDIATE ACTION REQUIRED: Transactions to prohibited jurisdictions identified\n"
                rationale_text += "• Escalate to senior management and compliance officer\n"
                rationale_text += "• Consider filing Suspicious Activity Report (SAR)\n"
            elif high_alerts or high_risk_txns:
                rationale_text += "• Enhanced due diligence recommended\n"
                rationale_text += "• Review source of funds and purpose of high-risk transactions\n"
                rationale_text += "• Obtain additional documentation for transactions to high-risk countries\n"
            else:
                rationale_text += "• Standard monitoring procedures apply\n"
                rationale_text += "• Continue periodic review of transaction patterns\n"
            
            # Check if rationale exists
            existing = cur.execute(
                "SELECT id FROM ai_rationales WHERE customer_id=? AND IFNULL(period_from,'')=IFNULL(?,'') AND IFNULL(period_to,'')=IFNULL(?,'')",
                (customer_id, p_from, p_to)
            ).fetchone()
            
            if existing:
                # Update existing
                cur.execute("""
                    UPDATE ai_rationales 
                    SET nature_of_business=?, est_income=?, est_expenditure=?, rationale_text=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                """, (nature_of_business, est_income, est_expenditure, rationale_text, existing["id"]))
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO ai_rationales(customer_id, period_from, period_to, nature_of_business,
                                              est_income, est_expenditure, rationale_text)
                    VALUES(?,?,?,?,?,?,?)
                """, (customer_id, p_from, p_to, nature_of_business, est_income, est_expenditure, rationale_text))
            conn.commit()
            
            rationale_row = cur.execute(
                "SELECT * FROM ai_rationales WHERE customer_id=? AND IFNULL(period_from,'')=IFNULL(?,'') AND IFNULL(period_to,'')=IFNULL(?,'')",
                (customer_id, p_from, p_to)
            ).fetchone()
            
            conn.close()
            
            return jsonify({
                "status": "ok",
                "customer_id": customer_id,
                "period": period,
                "period_from": p_from,
                "period_to": p_to,
                "rationale": dict(rationale_row) if rationale_row else None,
                "message": "Rationale generated successfully"
            })
        
        # GET: Load rationale
        rationale_row = cur.execute(
            "SELECT * FROM ai_rationales WHERE customer_id=? AND IFNULL(period_from,'')=IFNULL(?,'') AND IFNULL(period_to,'')=IFNULL(?,'')",
            (customer_id, p_from, p_to)
        ).fetchone()
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "customer_id": customer_id,
            "period": period,
            "period_from": p_from,
            "period_to": p_to,
            "rationale": dict(rationale_row) if rationale_row else None
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_transaction_ai_rationale: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# AI SME API Endpoints (Proxy to FastAPI)
# ============================================================================
# AI SME FastAPI typically runs on port 8000
AI_SME_BASE_URL = os.environ.get("AI_SME_BASE_URL", "http://localhost:8000")

@csrf.exempt
@app.route('/api/sme/health', methods=['GET'])
@role_required('reviewer', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'qc_1', 'qc_2', 'qc_3', 
               'team_lead_1', 'team_lead_2', 'team_lead_3', 'sme', 'admin', 'ops_manager', 'operations_manager')
def api_sme_health():
    """Proxy health check to AI SME FastAPI"""
    try:
        import requests
        # Get user ID from Flask session and pass it as header (for auth)
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        # Forward session cookie to FastAPI
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        response = requests.get(
            f"{AI_SME_BASE_URL}/health",
            headers=headers,
            cookies=cookies,
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            # Ensure we return the actual status from FastAPI
            return jsonify(data)
        else:
            # FastAPI returned an error
            return jsonify({
                'status': 'error',
                'llm_backend': 'unknown',
                'bot_name': 'Assistant',
                'auto_yes_ms': 30000
            }), response.status_code
    except requests.exceptions.ConnectionError:
        # FastAPI is not running
        return jsonify({
            'status': 'error',
            'llm_backend': 'unknown',
            'bot_name': 'Assistant',
            'auto_yes_ms': 30000
        }), 503
    except Exception as e:
        # Any other error
        return jsonify({
            'status': 'error',
            'llm_backend': 'unknown',
            'bot_name': 'Assistant',
            'auto_yes_ms': 30000
        }), 503

@csrf.exempt
@app.route('/api/sme/query', methods=['POST'])
@role_required('reviewer', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'qc_1', 'qc_2', 'qc_3', 
               'team_lead_1', 'team_lead_2', 'team_lead_3', 'sme', 'admin', 'ops_manager', 'operations_manager')
def api_sme_query():
    """Proxy query to AI SME FastAPI"""
    try:
        import requests
        # Forward form data
        form_data = request.form.to_dict()
        
        # Get user ID from Flask session and pass it as header
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        # Forward session cookie (for FastAPI's own session if user logged in directly)
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        response = requests.post(
            f"{AI_SME_BASE_URL}/query",
            data=form_data,
            headers=headers,
            cookies=cookies,
            timeout=30
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to get response from AI SME'}), response.status_code
    except Exception as e:
        import traceback
        print(f"Error in api_sme_query: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sme/referral', methods=['POST'])
@role_required('reviewer', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'qc_1', 'qc_2', 'qc_3', 
               'team_lead_1', 'team_lead_2', 'team_lead_3', 'sme', 'admin', 'ops_manager', 'operations_manager')
def api_sme_referral():
    """Proxy referral creation to AI SME FastAPI and update task status if task_id provided"""
    try:
        import requests
        import sqlite3
        from datetime import datetime
        from utils import derive_case_status
        
        # Forward form data
        form_data = request.form.to_dict()
        task_id = form_data.get('task_id', '').strip()
        
        # Get user ID from Flask session and pass it as header
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        # Forward session cookie
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        response = requests.post(
            f"{AI_SME_BASE_URL}/referral",
            data=form_data,
            headers=headers,
            cookies=cookies,
            timeout=10
        )
        
        if response.status_code == 200:
            referral_data = response.json()
            print(f"[DEBUG] AI SME referral created successfully: {referral_data}")
            
            # If task_id is provided and referral was successfully created, update task status
            # NOTE: For AI SME referrals, we do NOT update sme_query or referred_to_sme in reviews table
            # because AI SME referrals are stored in the FastAPI service, not in the reviews table.
            # Only manual referrals should set those fields.
            # However, we DO set the status to indicate an AI SME referral is pending.
            if task_id and referral_data.get('status') == 'ok':
                try:
                    conn = get_db()
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    
                    # Update updated_at and set status to indicate AI SME referral
                    now = datetime.utcnow().isoformat(timespec='seconds')
                    # Set status to "Referred to AI SME" to indicate an AI SME referral is pending
                    cur.execute("""
                        UPDATE reviews
                        SET updated_at = ?,
                            status = ?
                        WHERE task_id = ?
                    """, (now, 'Referred to AI SME', task_id))
                    
                    conn.commit()
                    conn.close()
                    print(f"[DEBUG] Updated task {task_id} status to 'Referred to AI SME' after AI SME referral creation")
                except Exception as task_err:
                    print(f"Warning: Could not update task status for referral: {task_err}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the referral creation if task update fails
            
            return jsonify(referral_data)
        else:
            error_text = response.text
            print(f"[ERROR] Failed to create AI SME referral. Status: {response.status_code}, Response: {error_text}")
            return jsonify({'error': f'Failed to create referral: {error_text}'}), response.status_code
    except Exception as e:
        import traceback
        print(f"Error in api_sme_referral: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sme/feedback', methods=['POST'])
@role_required('reviewer', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'qc_1', 'qc_2', 'qc_3', 
               'team_lead_1', 'team_lead_2', 'team_lead_3', 'sme', 'admin', 'ops_manager', 'operations_manager')
def api_sme_feedback():
    """Proxy feedback to AI SME FastAPI"""
    try:
        import requests
        # Forward form data
        form_data = request.form.to_dict()
        
        # Get user ID from Flask session and pass it as header
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        # Forward session cookie
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        response = requests.post(
            f"{AI_SME_BASE_URL}/feedback",
            data=form_data,
            headers=headers,
            cookies=cookies,
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'status': 'ok'})  # Feedback is non-critical, return success even if FastAPI fails
    except Exception as e:
        # Feedback is non-critical, return success
        return jsonify({'status': 'ok'})

@csrf.exempt
@app.route('/api/my_referrals', methods=['GET'])
@role_required('reviewer', 'qc_review_1', 'qc_review_2', 'qc_review_3', 'qc_1', 'qc_2', 'qc_3', 
               'team_lead_1', 'team_lead_2', 'team_lead_3', 'sme', 'admin', 'ops_manager', 'operations_manager')
def api_my_referrals():
    """Get user's referrals: both AI SME referrals and manual referrals from Due Diligence"""
    try:
        import sqlite3
        from datetime import datetime
        
        user_id = session.get('user_id')
        user_email = session.get('email', '').strip().lower()
        
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # 1. Get AI SME referrals (proxy to FastAPI)
        ai_sme_referrals = []
        ai_sme_task_ids = set()  # Track task_ids from AI SME referrals to exclude from manual
        try:
            import requests
            # Get user ID from Flask session and pass it as header
            headers = {}
            if user_id:
                headers['X-User-Id'] = str(user_id)
            
            cookies = {}
            if 'session' in request.cookies:
                cookies['session'] = request.cookies.get('session')
            
            response = requests.get(
                f"{AI_SME_BASE_URL}/my_referrals/data",
                headers=headers,
                cookies=cookies,
                timeout=10
            )
            if response.status_code == 200:
                ai_data = response.json()
                ai_sme_referrals = ai_data.get('data', [])
                # Collect task_ids from AI SME referrals to exclude from manual referrals
                for ref in ai_sme_referrals:
                    task_id = ref.get('task_id', '').strip()
                    if task_id:
                        ai_sme_task_ids.add(task_id)
        except Exception as e:
            print(f"Failed to fetch AI SME referrals: {e}")
        
        # 2. Get manual referrals from Due Diligence (reviews table)
        # Exclude tasks that have AI SME referrals (they should only appear in AI SME referrals section)
        # For SME admin (role "sme"), show ALL manual referrals, not just assigned ones
        user_role = session.get('role', '').strip().lower()
        is_sme_admin = user_role == 'sme'
        
        manual_referrals = []
        if ai_sme_task_ids:
            # Build query to exclude AI SME referral task_ids
            placeholders = ','.join(['?'] * len(ai_sme_task_ids))
            if is_sme_admin:
                # SME admin sees all manual referrals
                query = f"""
                    SELECT 
                        task_id,
                        sme_query AS query,
                        sme_response AS response,
                        sme_selected_date AS selected_date,
                        sme_returned_date AS returned_date,
                        referred_to_sme,
                        status
                    FROM reviews
                    WHERE referred_to_sme = 1
                      AND task_id NOT IN ({placeholders})
                    ORDER BY sme_selected_date DESC
                """
                params = list(ai_sme_task_ids)
            else:
                # Regular users see only their assigned/completed referrals
                query = f"""
                    SELECT 
                        task_id,
                        sme_query AS query,
                        sme_response AS response,
                        sme_selected_date AS selected_date,
                        sme_returned_date AS returned_date,
                        referred_to_sme,
                        status
                    FROM reviews
                    WHERE referred_to_sme = 1
                      AND (assigned_to = ? OR completed_by = ?)
                      AND task_id NOT IN ({placeholders})
                    ORDER BY sme_selected_date DESC
                """
                params = [user_id, user_id] + list(ai_sme_task_ids)
            cur.execute(query, params)
        else:
            # No AI SME referrals, so no need to exclude anything
            if is_sme_admin:
                # SME admin sees all manual referrals
                cur.execute("""
                    SELECT 
                        task_id,
                        sme_query AS query,
                        sme_response AS response,
                        sme_selected_date AS selected_date,
                        sme_returned_date AS returned_date,
                        referred_to_sme,
                        status
                    FROM reviews
                    WHERE referred_to_sme = 1
                    ORDER BY sme_selected_date DESC
                """)
            else:
                # Regular users see only their assigned/completed referrals
                cur.execute("""
                    SELECT 
                        task_id,
                        sme_query AS query,
                        sme_response AS response,
                        sme_selected_date AS selected_date,
                        sme_returned_date AS returned_date,
                        referred_to_sme,
                        status
                    FROM reviews
                    WHERE referred_to_sme = 1
                      AND (assigned_to = ? OR completed_by = ?)
                    ORDER BY sme_selected_date DESC
                """, (user_id, user_id))
        
        for row in cur.fetchall():
            r = dict(row)
            manual_referrals.append({
                'id': f"manual_{r['task_id']}",
                'type': 'manual',
                'task_id': r['task_id'],
                'query': r['query'] or '',
                'answer': r['response'] or '',
                'status': 'closed' if r['returned_date'] else 'open',
                'ts': r['selected_date'] or '',
                'last_ts': r['returned_date'] or r['selected_date'] or '',
                'count': 1
            })
        
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'ai_sme_referrals': ai_sme_referrals,
            'manual_referrals': manual_referrals
        })
        
    except Exception as e:
        import traceback
        print(f"Error in api_my_referrals: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sme/manual_referrals/update', methods=['POST'])
@role_required('sme', 'admin')
def api_sme_manual_referrals_update():
    """Update a manual referral (answer and status)"""
    try:
        import sqlite3
        from datetime import datetime
        
        referral_id = request.form.get('id', '').strip()
        if not referral_id:
            print(f"[DEBUG] Missing referral ID. Form data: {list(request.form.keys())}")
            return jsonify({'status': 'error', 'message': 'Missing referral ID'}), 400
        
        print(f"[DEBUG] Received referral_id: {referral_id}")
        
        # Extract task_id from referral_id (format: "manual_TASK-20251110-001")
        if not referral_id.startswith('manual_'):
            print(f"[DEBUG] Invalid referral ID format: {referral_id}")
            return jsonify({'status': 'error', 'message': f'Invalid referral ID format. Expected format: manual_TASK-XXXXX-XXX, got: {referral_id}'}), 400
        
        task_id = referral_id.replace('manual_', '')
        answer = request.form.get('answer', '').strip()
        status = request.form.get('status', '').strip()
        
        print(f"[DEBUG] Extracted task_id: {task_id}, answer length: {len(answer)}, status: {status}")
        
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check if task exists
        cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
        review = cur.fetchone()
        if not review:
            conn.close()
            print(f"[DEBUG] Task not found: {task_id}")
            return jsonify({'status': 'error', 'message': f'Task not found: {task_id}'}), 404
        
        review = dict(review)
        
        print(f"[DEBUG] Task found: {task_id}, sme_query: {bool(review.get('sme_query'))}, referred_to_sme: {review.get('referred_to_sme')}, status: {review.get('status')}")
        
        # Check if this is actually a manual referral (has sme_query or referred_to_sme)
        # Also check status to see if it's a manual referral (not AI SME)
        has_manual_referral = (
            review.get('sme_query') or 
            review.get('referred_to_sme') or
            (review.get('status') and 'referred to sme' in str(review.get('status')).lower() and 'ai' not in str(review.get('status')).lower())
        )
        
        if not has_manual_referral:
            conn.close()
            print(f"[DEBUG] Task {task_id} does not have a manual SME referral")
            return jsonify({'status': 'error', 'message': 'This task does not have a manual SME referral'}), 400
        
        # Update the manual referral
        updates = []
        params = []
        
        # Track if we're setting sme_returned_date to avoid duplicates
        setting_returned_date = False
        
        if answer:
            updates.append("sme_response = ?")
            params.append(answer)
            # If returning a response, set sme_returned_date
            updates.append("sme_returned_date = ?")
            params.append(datetime.utcnow().isoformat(timespec='seconds'))
            setting_returned_date = True
        
        if status == 'closed':
            if not review.get('sme_returned_date') and not setting_returned_date:
                # If closing and not already returned, set sme_returned_date
                updates.append("sme_returned_date = ?")
                params.append(datetime.utcnow().isoformat(timespec='seconds'))
                setting_returned_date = True
        elif status == 'open' and review.get('sme_returned_date'):
            # If reopening, clear sme_returned_date
            updates.append("sme_returned_date = NULL")
        
        # Always update updated_at
        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat(timespec='seconds'))
        
        if updates:
            params.append(task_id)
            query = f"UPDATE reviews SET {', '.join(updates)} WHERE task_id = ?"
            print(f"[DEBUG] Executing update query: {query}")
            print(f"[DEBUG] With params: {params}")
            cur.execute(query, params)
            
            # Re-derive status after update
            cur.execute("SELECT * FROM reviews WHERE task_id = ?", (task_id,))
            updated_review = dict(cur.fetchone() or {})
            from utils import derive_case_status
            new_status = derive_case_status(updated_review)
            print(f"[DEBUG] Derived new status: {new_status}")
            cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), task_id))
            
            conn.commit()
        else:
            print(f"[DEBUG] No updates to perform for task {task_id}")
        
        conn.close()
        print(f"[DEBUG] Successfully updated manual referral for task {task_id}")
        return jsonify({'status': 'ok', 'message': 'Referral updated successfully'})
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"[ERROR] Error in api_sme_manual_referrals_update: {error_msg}\n{error_trace}")
        return jsonify({'status': 'error', 'message': error_msg}), 500

# ============================================================================
# AI SME Admin API Endpoints (Proxy to FastAPI)
# ============================================================================
# These endpoints require admin or sme role

def _proxy_to_sme_admin(method, endpoint, require_json=False):
    """Helper to proxy admin requests to AI SME FastAPI"""
    try:
        import requests
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        url = f"{AI_SME_BASE_URL}{endpoint}"
        
        if method == 'GET':
            params = request.args.to_dict()
            response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=30)
        elif method == 'POST':
            if require_json:
                data = request.get_json() or {}
                response = requests.post(url, json=data, headers=headers, cookies=cookies, timeout=30)
            else:
                form_data = request.form.to_dict()
                response = requests.post(url, data=form_data, headers=headers, cookies=cookies, timeout=30)
        else:
            return jsonify({'error': 'Method not supported'}), 405
        
        if response.status_code == 200:
            try:
                return jsonify(response.json())
            except:
                return response.text, 200, {'Content-Type': response.headers.get('Content-Type', 'application/json')}
        else:
            return jsonify({'error': 'Failed to get response from AI SME'}), response.status_code
    except Exception as e:
        import traceback
        print(f"Error in AI SME admin proxy: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sme/admin/referrals/data', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_referrals_data():
    """Get all referrals for admin/SME"""
    return _proxy_to_sme_admin('GET', '/admin/referrals/data')

@csrf.exempt
@app.route('/api/sme/admin/referrals/update', methods=['POST'])
@role_required('admin', 'sme')
def api_sme_admin_referrals_update():
    """Update referral status or answer, and update task status if sme_response provided"""
    try:
        import requests
        import sqlite3
        from datetime import datetime
        from utils import derive_case_status
        
        # Forward form data
        form_data = request.form.to_dict()
        referral_id = form_data.get('id', '').strip()
        sme_response = form_data.get('answer', '').strip()
        
        # Get user ID from Flask session and pass it as header
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        # Forward session cookie
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        # First, get the referral to check if it has a task_id
        referral_task_id = None
        try:
            ref_response = requests.get(
                f"{AI_SME_BASE_URL}/admin/referrals/data",
                headers=headers,
                cookies=cookies,
                timeout=10
            )
            if ref_response.status_code == 200:
                ref_data = ref_response.json()
                referrals = ref_data.get('data', [])
                for ref in referrals:
                    if ref.get('id') == referral_id:
                        referral_task_id = ref.get('task_id', '').strip()
                        break
        except Exception as e:
            print(f"Warning: Could not fetch referral data: {e}")
        
        # Proxy the update to FastAPI
        response = requests.post(
            f"{AI_SME_BASE_URL}/admin/referrals/update",
            data=form_data,
            headers=headers,
            cookies=cookies,
            timeout=10
        )
        
        if response.status_code == 200:
            update_data = response.json()
            
            # If sme_response was provided and task_id exists, update task status
            if sme_response and referral_task_id:
                try:
                    conn = get_db()
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    
                    # Update task with SME response
                    # For AI SME referrals, we need to match by status "Referred to AI SME" instead of referred_to_sme = 1
                    now = datetime.utcnow().isoformat(timespec='seconds')
                    cur.execute("""
                        UPDATE reviews
                        SET sme_response = ?,
                            sme_returned_date = ?,
                            updated_at = ?
                        WHERE task_id = ?
                          AND (referred_to_sme = 1 OR status LIKE '%Referred to AI SME%')
                    """, (sme_response, now, now, referral_task_id))
                    
                    # Re-derive status
                    cur.execute("SELECT * FROM reviews WHERE task_id = ?", (referral_task_id,))
                    review = dict(cur.fetchone() or {})
                    new_status = derive_case_status(review)
                    cur.execute("UPDATE reviews SET status = ? WHERE task_id = ?", (str(new_status), referral_task_id))
                    
                    conn.commit()
                    conn.close()
                    print(f"[DEBUG] Updated task {referral_task_id} with SME response and status to '{new_status}'")
                except Exception as task_err:
                    print(f"Warning: Could not update task status for SME response: {task_err}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the referral update if task update fails
            
            return jsonify(update_data)
        else:
            return jsonify({'error': 'Failed to update referral'}), response.status_code
    except Exception as e:
        import traceback
        print(f"Error in api_sme_admin_referrals_update: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sme/admin/referrals/export', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_referrals_export():
    """Export referrals"""
    return _proxy_to_sme_admin('GET', '/admin/referrals/export')

@csrf.exempt
@app.route('/api/sme/admin/feedback/data', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_feedback_data():
    """Get feedback data for admin/SME"""
    return _proxy_to_sme_admin('GET', '/admin/feedback/data')

@csrf.exempt
@app.route('/api/sme/admin/feedback/export', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_feedback_export():
    """Export feedback"""
    return _proxy_to_sme_admin('GET', '/admin/feedback/export')

@csrf.exempt
@app.route('/api/sme/admin/docs', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_docs():
    """List documents for admin/SME"""
    return _proxy_to_sme_admin('GET', '/admin/docs')

@csrf.exempt
@app.route('/api/sme/admin/docs/export', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_docs_export():
    """Export documents list"""
    return _proxy_to_sme_admin('GET', '/admin/docs/export')

@csrf.exempt
@app.route('/api/sme/admin/docs/delete', methods=['POST'])
@role_required('admin', 'sme')
def api_sme_admin_docs_delete():
    """Delete a document"""
    return _proxy_to_sme_admin('POST', '/delete')

@csrf.exempt
@app.route('/api/sme/admin/config', methods=['GET', 'POST'])
@role_required('admin', 'sme')
def api_sme_admin_config():
    """Get or update AI SME config"""
    if request.method == 'GET':
        return _proxy_to_sme_admin('GET', '/config')
    else:
        return _proxy_to_sme_admin('POST', '/admin/config')

@csrf.exempt
@app.route('/api/sme/admin/resolutions', methods=['GET', 'POST'])
@role_required('admin', 'sme')
def api_sme_admin_resolutions():
    """Get or add SME resolutions"""
    if request.method == 'GET':
        return _proxy_to_sme_admin('GET', '/admin/resolutions')
    else:
        return _proxy_to_sme_admin('POST', '/admin/resolutions')

@csrf.exempt
@app.route('/api/sme/admin/resolutions/export', methods=['GET'])
@role_required('admin', 'sme')
def api_sme_admin_resolutions_export():
    """Export SME resolutions"""
    return _proxy_to_sme_admin('GET', '/admin/resolutions/export')

@csrf.exempt
@app.route('/api/sme/admin/upload', methods=['POST'])
@role_required('admin', 'sme')
def api_sme_admin_upload():
    """Upload a document to AI SME"""
    try:
        import requests
        user_id = session.get('user_id')
        headers = {}
        if user_id:
            headers['X-User-Id'] = str(user_id)
        
        cookies = {}
        if 'session' in request.cookies:
            cookies['session'] = request.cookies.get('session')
        
        # Handle file upload
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        title = request.form.get('title', '')
        
        files = {'file': (file.filename, file.stream, file.content_type)}
        data = {}
        if title:
            data['title'] = title
        
        response = requests.post(
            f"{AI_SME_BASE_URL}/upload",
            files=files,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=60
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to upload document'}), response.status_code
    except Exception as e:
        import traceback
        print(f"Error in api_sme_admin_upload: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Transaction Review Admin API Endpoints (Direct Database Access)
# ============================================================================
# These endpoints access the shared database directly, same as other Transaction Review endpoints

def _tx_cfg_get(key, default=None, cast=str):
    """Get a Transaction Review config value from config_kv table"""
    conn = get_db_connection()
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
    conn.close()
    
    if not row or row["value"] is None:
        _tx_cfg_set(key, default)
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

def _tx_cfg_set(key, value):
    """Set a Transaction Review config value in config_kv table"""
    conn = get_db_connection()
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
    conn.close()

def _tx_upsert_country(iso2, level, score, prohibited):
    """Upsert country risk data"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Ensure ref_country_risk table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ref_country_risk(
            iso2 TEXT PRIMARY KEY,
            risk_level TEXT CHECK(risk_level IN ('LOW','MEDIUM','HIGH','HIGH_3RD','PROHIBITED')),
            score INTEGER NOT NULL,
            prohibited INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        INSERT INTO ref_country_risk(iso2, risk_level, score, prohibited)
        VALUES(?,?,?,?)
        ON CONFLICT(iso2) DO UPDATE SET risk_level=excluded.risk_level,
                                      score=excluded.score,
                                      prohibited=excluded.prohibited,
                                      updated_at=CURRENT_TIMESTAMP
    """, (iso2.upper().strip(), level, score, 1 if prohibited else 0))
    conn.commit()
    conn.close()

@csrf.exempt
@app.route('/api/tx_review/admin/config', methods=['GET'])
@role_required('admin')
def api_tx_review_admin_config():
    """Get Transaction Review configuration"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Ensure tables exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS config_kv(
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_country_risk(
                iso2 TEXT PRIMARY KEY,
                risk_level TEXT CHECK(risk_level IN ('LOW','MEDIUM','HIGH','HIGH_3RD','PROHIBITED')),
                score INTEGER NOT NULL,
                prohibited INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Get countries
        countries = cur.execute("SELECT * FROM ref_country_risk ORDER BY iso2").fetchall()
        
        # Get config params
        params = {
            "cfg_high_risk_min_amount": float(_tx_cfg_get("cfg_high_risk_min_amount", 0.0, float)),
            "cfg_median_multiplier": float(_tx_cfg_get("cfg_median_multiplier", 3.0, float)),
            "cfg_expected_out_factor": float(_tx_cfg_get("cfg_expected_out_factor", 1.2, float)),
            "cfg_expected_in_factor": float(_tx_cfg_get("cfg_expected_in_factor", 1.2, float)),
            "cfg_sev_critical": int(_tx_cfg_get("cfg_sev_critical", 90, int)),
            "cfg_sev_high": int(_tx_cfg_get("cfg_sev_high", 70, int)),
            "cfg_sev_medium": int(_tx_cfg_get("cfg_sev_medium", 50, int)),
            "cfg_sev_low": int(_tx_cfg_get("cfg_sev_low", 30, int)),
            "cfg_ai_use_llm": bool(_tx_cfg_get("cfg_ai_use_llm", False, bool)),
            "cfg_ai_model": str(_tx_cfg_get("cfg_ai_model", "gpt-4o-mini", str)),
            "cfg_risky_terms2": _tx_cfg_get("cfg_risky_terms2", [], list),
            "cfg_cash_daily_limit": float(_tx_cfg_get("cfg_cash_daily_limit", 0.0, float)),
        }
        
        toggles = {
            "prohibited_country": bool(_tx_cfg_get("cfg_rule_enabled_prohibited_country", True, bool)),
            "high_risk_corridor": bool(_tx_cfg_get("cfg_rule_enabled_high_risk_corridor", True, bool)),
            "median_outlier": bool(_tx_cfg_get("cfg_rule_enabled_median_outlier", True, bool)),
            "nlp_risky_terms": bool(_tx_cfg_get("cfg_rule_enabled_nlp_risky_terms", True, bool)),
            "expected_out": bool(_tx_cfg_get("cfg_rule_enabled_expected_out", True, bool)),
            "expected_in": bool(_tx_cfg_get("cfg_rule_enabled_expected_in", True, bool)),
            "cash_daily_breach": bool(_tx_cfg_get("cfg_rule_enabled_cash_daily_breach", True, bool)),
            "severity_mapping": bool(_tx_cfg_get("cfg_rule_enabled_severity_mapping", True, bool)),
        }
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "params": params,
            "toggles": toggles,
            "countries": [dict(c) for c in countries]
        })
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_admin_config: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tx_review/admin/config/params', methods=['POST'])
@role_required('admin')
def api_tx_review_admin_config_params():
    """Update Transaction Review rule parameters"""
    try:
        # Numbers / floats
        _tx_cfg_set("cfg_high_risk_min_amount", float(request.form.get("cfg_high_risk_min_amount") or 0))
        _tx_cfg_set("cfg_median_multiplier", float(request.form.get("cfg_median_multiplier") or 3.0))
        _tx_cfg_set("cfg_expected_out_factor", float(request.form.get("cfg_expected_out_factor") or 1.2))
        _tx_cfg_set("cfg_expected_in_factor", float(request.form.get("cfg_expected_in_factor") or 1.2))
        _tx_cfg_set("cfg_cash_daily_limit", float(request.form.get("cfg_cash_daily_limit") or 0))
        
        # Severities
        _tx_cfg_set("cfg_sev_critical", int(request.form.get("cfg_sev_critical") or 90))
        _tx_cfg_set("cfg_sev_high", int(request.form.get("cfg_sev_high") or 70))
        _tx_cfg_set("cfg_sev_medium", int(request.form.get("cfg_sev_medium") or 50))
        _tx_cfg_set("cfg_sev_low", int(request.form.get("cfg_sev_low") or 30))
        
        # AI
        _tx_cfg_set("cfg_ai_use_llm", bool(request.form.get("cfg_ai_use_llm")))
        _tx_cfg_set("cfg_ai_model", (request.form.get("cfg_ai_model") or "gpt-4o-mini").strip())
        
        return jsonify({"status": "ok", "message": "Rule parameters saved"})
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_admin_config_params: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tx_review/admin/config/toggles', methods=['POST'])
@role_required('admin')
def api_tx_review_admin_config_toggles():
    """Update Transaction Review rule toggles"""
    try:
        def flag(name): return bool(request.form.get(name))
        _tx_cfg_set("cfg_rule_enabled_prohibited_country", flag("enable_prohibited_country"))
        _tx_cfg_set("cfg_rule_enabled_high_risk_corridor", flag("enable_high_risk_corridor"))
        _tx_cfg_set("cfg_rule_enabled_median_outlier", flag("enable_median_outlier"))
        _tx_cfg_set("cfg_rule_enabled_nlp_risky_terms", flag("enable_nlp_risky_terms"))
        _tx_cfg_set("cfg_rule_enabled_expected_out", flag("enable_expected_out"))
        _tx_cfg_set("cfg_rule_enabled_expected_in", flag("enable_expected_in"))
        _tx_cfg_set("cfg_rule_enabled_cash_daily_breach", flag("enable_cash_daily_breach"))
        _tx_cfg_set("cfg_rule_enabled_severity_mapping", flag("enable_severity_mapping"))
        
        return jsonify({"status": "ok", "message": "Rule toggles saved"})
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_admin_config_toggles: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tx_review/admin/countries', methods=['GET', 'POST'])
@role_required('admin')
def api_tx_review_admin_countries():
    """Get or update country risk data"""
    try:
        if request.method == 'GET':
            conn = get_db_connection()
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
            
            countries = cur.execute("SELECT * FROM ref_country_risk ORDER BY iso2").fetchall()
            conn.close()
            
            return jsonify({
                "status": "ok",
                "data": [dict(c) for c in countries]
            })
        else:
            # POST - add/update country
            iso2 = request.form.get("iso2", "").upper().strip()
            level = request.form.get("risk_level", "MEDIUM").strip()
            score = int(request.form.get("score", "0"))
            prohibited = 1 if request.form.get("prohibited") else 0
            
            if not iso2:
                return jsonify({"status": "error", "message": "ISO2 code required"}), 400
            
            _tx_upsert_country(iso2, level, score, prohibited)
            return jsonify({"status": "ok", "message": f"Country {iso2} saved"})
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_admin_countries: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tx_review/admin/keywords', methods=['POST'])
@role_required('admin')
def api_tx_review_admin_keywords():
    """Manage risky terms keywords"""
    try:
        action = request.form.get("action")
        items = _tx_cfg_get("cfg_risky_terms2", [], list)
        message = ""
        success = True

        if action == "add":
            term = (request.form.get("new_term") or "").strip()
            if term and not any(t for t in items if (t.get("term") or "").lower() == term.lower()):
                items.append({"term": term, "enabled": True})
                _tx_cfg_set("cfg_risky_terms2", items)
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
                    _tx_cfg_set("cfg_risky_terms2", items)
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
                _tx_cfg_set("cfg_risky_terms2", new_items)
                message = f"Removed keyword: {term}"
            else:
                message = f"Keyword '{term}' not found"
                success = False
        else:
            message = "Unknown action."
            success = False

        if success:
            return jsonify({"status": "ok", "message": message})
        else:
            return jsonify({"status": "error", "message": message}), 400
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_admin_keywords: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tx_review/upload', methods=['POST'])
@role_required('admin')
def api_tx_review_upload():
    """Upload data files for Transaction Review"""
    try:
        import pandas as pd
        from datetime import datetime, timedelta, date
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Ensure tables exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_country_risk(
                iso2 TEXT PRIMARY KEY,
                risk_level TEXT CHECK(risk_level IN ('LOW','MEDIUM','HIGH','HIGH_3RD','PROHIBITED')),
                score INTEGER NOT NULL,
                prohibited INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_sort_codes(
                sort_code TEXT PRIMARY KEY,
                bank_name TEXT,
                branch TEXT,
                schemes TEXT,
                valid_from DATE,
                valid_to DATE
            )
        """)
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
        
        country_count = 0
        sort_count = 0
        tx_count = 0
        
        # Process country file
        if 'country_file' in request.files and request.files['country_file'].filename:
            df = pd.read_csv(request.files['country_file'])
            for _, r in df.iterrows():
                _tx_upsert_country(
                    str(r["iso2"]).strip(),
                    str(r["risk_level"]).strip(),
                    int(r["score"]),
                    int(r.get("prohibited", 0))
                )
                country_count += 1
        
        # Process sort codes file
        if 'sort_file' in request.files and request.files['sort_file'].filename:
            df = pd.read_csv(request.files['sort_file'])
            recs = df.to_dict(orient="records")
            for r in recs:
                cur.execute("""
                    INSERT INTO ref_sort_codes(sort_code, bank_name, branch, schemes, valid_from, valid_to)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(sort_code) DO UPDATE SET bank_name=excluded.bank_name,
                                                       branch=excluded.branch,
                                                       schemes=excluded.schemes,
                                                       valid_from=excluded.valid_from,
                                                       valid_to=excluded.valid_to
                """, (
                    r.get("sort_code"), r.get("bank_name"), r.get("branch"),
                    r.get("schemes"), r.get("valid_from"), r.get("valid_to")
                ))
                sort_count += 1
            conn.commit()
        
        # Process transactions file
        if 'tx_file' in request.files and request.files['tx_file'].filename:
            import sys
            import os
            # Add current directory to path for import
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            from tx_review_ingest import ingest_transactions_csv
            try:
                tx_count, bad_dates = ingest_transactions_csv(conn, request.files['tx_file'])
                if bad_dates > 0:
                    print(f"[ingest_transactions_csv] Skipped {bad_dates} row(s) with invalid txn_date.")
            except Exception as e:
                import traceback
                print(f"Error ingesting transactions: {str(e)}\n{traceback.format_exc()}")
                conn.close()
                return jsonify({
                    "status": "error",
                    "message": f"Failed to ingest transactions: {str(e)}"
                }), 500
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "message": f"Loaded {tx_count} transactions, {country_count} countries, {sort_count} sort codes",
            "transactions": tx_count,
            "countries": country_count,
            "sort_codes": sort_count
        })
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_upload: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/tx_review/sample/<path:filename>', methods=['GET'])
@role_required('admin')
def api_tx_review_sample(filename):
    """Download sample CSV files for Transaction Review"""
    try:
        import os
        # Get the data directory path
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        
        # Allowed filenames for security
        allowed_files = [
            'transactions_sample.csv',
            'transactions_sample_12m.csv',
            'ref_country_risk.csv',
            'ref_sort_codes.csv',
            'customer_cash_limits.csv',
            'kyc_profile.csv',
            'transactions_schema.csv'
        ]
        
        if filename not in allowed_files:
            return jsonify({'error': 'File not allowed'}), 403
        
        file_path = os.path.join(data_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_from_directory(data_dir, filename, as_attachment=True)
    except Exception as e:
        import traceback
        print(f"Error in api_tx_review_sample: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Sumsub Integration
# ============================================================================

# Sumsub Configuration
SUMSUB_APP_TOKEN = os.getenv('SUMSUB_APP_TOKEN')
SUMSUB_SECRET_KEY = os.getenv('SUMSUB_SECRET_KEY')
SUMSUB_BASE_URL = os.getenv('SUMSUB_BASE_URL', 'https://api.sumsub.com')

def convert_country_to_iso3(country_name):
    """Convert country name or ISO2 code to ISO alpha-3 code (required for Sumsub)"""
    # ISO2 to ISO3 mapping
    iso2_to_iso3 = {
        'AD': 'AND', 'AE': 'ARE', 'AF': 'AFG', 'AG': 'ATG', 'AI': 'AIA', 'AL': 'ALB', 'AM': 'ARM',
        'AO': 'AGO', 'AQ': 'ATA', 'AR': 'ARG', 'AS': 'ASM', 'AT': 'AUT', 'AU': 'AUS', 'AW': 'ABW',
        'AX': 'ALA', 'AZ': 'AZE', 'BA': 'BIH', 'BB': 'BRB', 'BD': 'BGD', 'BE': 'BEL', 'BF': 'BFA',
        'BG': 'BGR', 'BH': 'BHR', 'BI': 'BDI', 'BJ': 'BEN', 'BL': 'BLM', 'BM': 'BMU', 'BN': 'BRN',
        'BO': 'BOL', 'BQ': 'BES', 'BR': 'BRA', 'BS': 'BHS', 'BT': 'BTN', 'BV': 'BVT', 'BW': 'BWA',
        'BY': 'BLR', 'BZ': 'BLZ', 'CA': 'CAN', 'CC': 'CCK', 'CD': 'COD', 'CF': 'CAF', 'CG': 'COG',
        'CH': 'CHE', 'CI': 'CIV', 'CK': 'COK', 'CL': 'CHL', 'CM': 'CMR', 'CN': 'CHN', 'CO': 'COL',
        'CR': 'CRI', 'CU': 'CUB', 'CV': 'CPV', 'CW': 'CUW', 'CX': 'CXR', 'CY': 'CYP', 'CZ': 'CZE',
        'DE': 'DEU', 'DJ': 'DJI', 'DK': 'DNK', 'DM': 'DMA', 'DO': 'DOM', 'DZ': 'DZA', 'EC': 'ECU',
        'EE': 'EST', 'EG': 'EGY', 'EH': 'ESH', 'ER': 'ERI', 'ES': 'ESP', 'ET': 'ETH', 'FI': 'FIN',
        'FJ': 'FJI', 'FK': 'FLK', 'FM': 'FSM', 'FO': 'FRO', 'FR': 'FRA', 'GA': 'GAB', 'GB': 'GBR',
        'GD': 'GRD', 'GE': 'GEO', 'GF': 'GUF', 'GG': 'GGY', 'GH': 'GHA', 'GI': 'GIB', 'GL': 'GRL',
        'GM': 'GMB', 'GN': 'GIN', 'GP': 'GLP', 'GQ': 'GNQ', 'GR': 'GRC', 'GS': 'SGS', 'GT': 'GTM',
        'GU': 'GUM', 'GW': 'GNB', 'GY': 'GUY', 'HK': 'HKG', 'HM': 'HMD', 'HN': 'HND', 'HR': 'HRV',
        'HT': 'HTI', 'HU': 'HUN', 'ID': 'IDN', 'IE': 'IRL', 'IL': 'ISR', 'IM': 'IMN', 'IN': 'IND',
        'IO': 'IOT', 'IQ': 'IRQ', 'IR': 'IRN', 'IS': 'ISL', 'IT': 'ITA', 'JE': 'JEY', 'JM': 'JAM',
        'JO': 'JOR', 'JP': 'JPN', 'KE': 'KEN', 'KG': 'KGZ', 'KH': 'KHM', 'KI': 'KIR', 'KM': 'COM',
        'KN': 'KNA', 'KP': 'PRK', 'KR': 'KOR', 'KW': 'KWT', 'KY': 'CYM', 'KZ': 'KAZ', 'LA': 'LAO',
        'LB': 'LBN', 'LC': 'LCA', 'LI': 'LIE', 'LK': 'LKA', 'LR': 'LBR', 'LS': 'LSO', 'LT': 'LTU',
        'LU': 'LUX', 'LV': 'LVA', 'LY': 'LBY', 'MA': 'MAR', 'MC': 'MCO', 'MD': 'MDA', 'ME': 'MNE',
        'MF': 'MAF', 'MG': 'MDG', 'MH': 'MHL', 'MK': 'MKD', 'ML': 'MLI', 'MM': 'MMR', 'MN': 'MNG',
        'MO': 'MAC', 'MP': 'MNP', 'MQ': 'MTQ', 'MR': 'MRT', 'MS': 'MSR', 'MT': 'MLT', 'MU': 'MUS',
        'MV': 'MDV', 'MW': 'MWI', 'MX': 'MEX', 'MY': 'MYS', 'MZ': 'MOZ', 'NA': 'NAM', 'NC': 'NCL',
        'NE': 'NER', 'NF': 'NFK', 'NG': 'NGA', 'NI': 'NIC', 'NL': 'NLD', 'NO': 'NOR', 'NP': 'NPL',
        'NR': 'NRU', 'NU': 'NIU', 'NZ': 'NZL', 'OM': 'OMN', 'PA': 'PAN', 'PE': 'PER', 'PF': 'PYF',
        'PG': 'PNG', 'PH': 'PHL', 'PK': 'PAK', 'PL': 'POL', 'PM': 'SPM', 'PN': 'PCN', 'PR': 'PRI',
        'PS': 'PSE', 'PT': 'PRT', 'PW': 'PLW', 'PY': 'PRY', 'QA': 'QAT', 'RE': 'REU', 'RO': 'ROU',
        'RS': 'SRB', 'RU': 'RUS', 'RW': 'RWA', 'SA': 'SAU', 'SB': 'SLB', 'SC': 'SYC', 'SD': 'SDN',
        'SE': 'SWE', 'SG': 'SGP', 'SH': 'SHN', 'SI': 'SVN', 'SJ': 'SJM', 'SK': 'SVK', 'SL': 'SLE',
        'SM': 'SMR', 'SN': 'SEN', 'SO': 'SOM', 'SR': 'SUR', 'SS': 'SSD', 'ST': 'STP', 'SV': 'SLV',
        'SX': 'SXM', 'SY': 'SYR', 'SZ': 'SWZ', 'TC': 'TCA', 'TD': 'TCD', 'TF': 'ATF', 'TG': 'TGO',
        'TH': 'THA', 'TJ': 'TJK', 'TK': 'TKL', 'TL': 'TLS', 'TM': 'TKM', 'TN': 'TUN', 'TO': 'TON',
        'TR': 'TUR', 'TT': 'TTO', 'TV': 'TUV', 'TW': 'TWN', 'TZ': 'TZA', 'UA': 'UKR', 'UG': 'UGA',
        'UM': 'UMI', 'US': 'USA', 'UY': 'URY', 'UZ': 'UZB', 'VA': 'VAT', 'VC': 'VCT', 'VE': 'VEN',
        'VG': 'VGB', 'VI': 'VIR', 'VN': 'VNM', 'VU': 'VUT', 'WF': 'WLF', 'WS': 'WSM', 'YE': 'YEM',
        'YT': 'MYT', 'ZA': 'ZAF', 'ZM': 'ZMB', 'ZW': 'ZWE'
    }
    
    # Country name to ISO3 mapping
    country_name_to_iso3 = {
        'United Kingdom': 'GBR', 'UK': 'GBR',
        'United States': 'USA', 'USA': 'USA',
        'Canada': 'CAN', 'Australia': 'AUS', 'Germany': 'DEU',
        'France': 'FRA', 'Spain': 'ESP', 'Italy': 'ITA',
        'Netherlands': 'NLD', 'Belgium': 'BEL', 'Switzerland': 'CHE',
        'Austria': 'AUT', 'Sweden': 'SWE', 'Norway': 'NOR',
        'Denmark': 'DNK', 'Finland': 'FIN', 'Ireland': 'IRL',
        'Portugal': 'PRT', 'Poland': 'POL', 'Czech Republic': 'CZE',
        'Hungary': 'HUN', 'Romania': 'ROU', 'Bulgaria': 'BGR',
        'Croatia': 'HRV', 'Slovenia': 'SVN', 'Slovakia': 'SVK',
        'Estonia': 'EST', 'Latvia': 'LVA', 'Lithuania': 'LTU',
        'Luxembourg': 'LUX', 'Malta': 'MLT', 'Cyprus': 'CYP',
        'Greece': 'GRC', 'Japan': 'JPN', 'South Korea': 'KOR',
        'China': 'CHN', 'India': 'IND', 'Brazil': 'BRA',
        'Mexico': 'MEX', 'Argentina': 'ARG', 'Chile': 'CHL',
        'South Africa': 'ZAF', 'Nigeria': 'NGA', 'Egypt': 'EGY',
        'Morocco': 'MAR', 'Tunisia': 'TUN', 'Algeria': 'DZA',
        'Libya': 'LBY', 'Sudan': 'SDN', 'Ethiopia': 'ETH',
        'Kenya': 'KEN', 'Uganda': 'UGA', 'Tanzania': 'TZA',
        'Ghana': 'GHA', 'Senegal': 'SEN', 'Mali': 'MLI',
        'Burkina Faso': 'BFA', 'Niger': 'NER', 'Chad': 'TCD',
        'Cameroon': 'CMR', 'Central African Republic': 'CAF',
        'Democratic Republic of the Congo': 'COD',
        'Republic of the Congo': 'COG', 'Gabon': 'GAB',
        'Equatorial Guinea': 'GNQ', 'Sao Tome and Principe': 'STP',
        'Angola': 'AGO', 'Zambia': 'ZMB', 'Zimbabwe': 'ZWE',
        'Botswana': 'BWA', 'Namibia': 'NAM', 'Lesotho': 'LSO',
        'Swaziland': 'SWZ', 'Madagascar': 'MDG', 'Mauritius': 'MUS',
        'Seychelles': 'SYC', 'Comoros': 'COM', 'Djibouti': 'DJI',
        'Somalia': 'SOM', 'Eritrea': 'ERI', 'Rwanda': 'RWA',
        'Burundi': 'BDI', 'Malawi': 'MWI', 'Mozambique': 'MOZ'
    }
    
    if not country_name:
        return ''
    
    country_clean = str(country_name).strip().upper()
    
    # If already ISO3 (3 letters), return as-is
    if len(country_clean) == 3 and country_clean.isalpha():
        return country_clean
    
    # If ISO2 (2 letters), convert to ISO3
    if len(country_clean) == 2 and country_clean.isalpha():
        return iso2_to_iso3.get(country_clean, country_clean)
    
    # Try country name mapping (case-insensitive)
    country_clean_original = str(country_name).strip()
    if country_clean_original in country_name_to_iso3:
        return country_name_to_iso3[country_clean_original]
    
    for key, value in country_name_to_iso3.items():
        if key.lower() == country_clean_original.lower():
            return value
    
    # If no match found, return original (might already be ISO3 or invalid)
    return country_clean_original

def generate_sumsub_signature(method, url, body, timestamp):
    """Generate Sumsub API signature for authentication"""
    parsed_url = urlparse(url)
    path_with_query = parsed_url.path
    if parsed_url.query:
        path_with_query += f"?{parsed_url.query}"
    
    message = f"{timestamp}{method}{path_with_query}{body}"
    signature = hmac.new(
        SUMSUB_SECRET_KEY.encode() if SUMSUB_SECRET_KEY else b'',
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def extract_sumsub_error_message(response):
    """Extract error message from Sumsub API error response"""
    try:
        error_data = response.json()
        error_message = (
            error_data.get('error') or
            error_data.get('description') or
            error_data.get('message') or
            error_data.get('reason') or
            error_data.get('details') or
            str(error_data)
        )
        if isinstance(error_message, dict):
            error_message = (
                error_message.get('message') or
                error_message.get('description') or
                error_message.get('error') or
                str(error_message)
            )
        return error_message if error_message else response.text
    except (ValueError, json.JSONDecodeError):
        return response.text if response.text else f'HTTP {response.status_code}'

def ensure_sumsub_tables():
    """Ensure Sumsub database tables exist"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Create sumsub_applications table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sumsub_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            applicant_id TEXT NOT NULL,
            external_user_id TEXT,
            level_name TEXT DEFAULT 'id-only',
            status TEXT DEFAULT 'init',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(review_id) REFERENCES reviews(id)
        )
    """)
    
    # Create sumsub_documents table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sumsub_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            document_type TEXT,
            document_number TEXT,
            country_code TEXT,
            verification_status TEXT,
            verification_result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(application_id) REFERENCES sumsub_applications(id)
        )
    """)
    
    # Add sumsub columns to reviews table if they don't exist
    for col in ['sumsub_applicant_id', 'sumsub_verification_status', 
                'sumsub_verification_score', 'sumsub_verification_date', 
                'sumsub_verification_result']:
        try:
            cur.execute(f"SELECT {col} FROM reviews LIMIT 1")
        except sqlite3.OperationalError:
            try:
                col_type = 'TEXT' if col != 'sumsub_verification_score' else 'INTEGER'
                cur.execute(f"ALTER TABLE reviews ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass
    
    conn.commit()
    conn.close()

@csrf.exempt
@app.route('/api/sumsub/create_applicant', methods=['POST'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 
               'qc_review_1', 'qc_review_2', 'qc_review_3',
               'qc_1', 'qc_2', 'qc_3',
               'sme', 'quality_manager', 'admin', 'operations_manager', 'ops_manager')
def create_sumsub_applicant():
    """Create a new Sumsub applicant for identity verification"""
    print(f"\n[SUMSUB] ===== CREATE APPLICANT API CALLED =====")
    print(f"[SUMSUB] Creating applicant - {datetime.now()}")
    
    try:
        ensure_sumsub_tables()
        
        data = request.get_json()
        if not data:
            print("[SUMSUB] ERROR: No JSON data provided")
            return jsonify({'error': 'No JSON data provided'}), 400
            
        review_id = data.get('review_id')
        customer_id = data.get('customer_id')
        level_name = data.get('level_name', 'id-only')
        
        print(f"[SUMSUB] Request data - Review ID: {review_id}, Customer ID: {customer_id}, Level: {level_name}")
        
        if not review_id or not customer_id:
            print("[SUMSUB] ERROR: Missing required fields")
            return jsonify({'error': 'Missing required fields: review_id and customer_id'}), 400
        
        conn = get_db_connection()
        try:
            review = conn.execute(
                "SELECT * FROM reviews WHERE id = ?", (review_id,)
            ).fetchone()
            
            if not review:
                print(f" [SUMSUB] Review not found: {review_id}")
                conn.close()
                return jsonify({'error': 'Review not found'}), 404
                
            print(f" [SUMSUB] Review found: {review['entity_name_original'] if 'entity_name_original' in review.keys() and review['entity_name_original'] else 'N/A'}")
            
        except Exception as db_error:
            print(f" [SUMSUB] Database error: {str(db_error)}")
            conn.close()
            return jsonify({'error': 'Database error'}), 500
        
        entity_name = review['entity_name_original'] if 'entity_name_original' in review.keys() and review['entity_name_original'] else ''
        country_original = review['country_original'] if 'country_original' in review.keys() and review['country_original'] else ''
        country_code = convert_country_to_iso3(country_original)
        
        name_parts = entity_name.split(' ') if entity_name else ['']
        applicant_data = {
            "externalUserId": f"customer_{customer_id}",
            "levelName": level_name,
            "info": {
                "firstName": name_parts[0] if name_parts else '',
                "lastName": ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
                "dob": review['lp1_dob_original'] if 'lp1_dob_original' in review.keys() and review['lp1_dob_original'] else '',
                "country": country_code,
                "email": review['primary_email'] if 'primary_email' in review.keys() and review['primary_email'] else '',
                "phone": review['primary_phone'] if 'primary_phone' in review.keys() and review['primary_phone'] else ''
            }
        }
        
        print(f" [SUMSUB] Applicant data: {json.dumps(applicant_data, indent=2)}")
        
        if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
            print("[SUMSUB] ERROR: Sumsub credentials not configured")
            conn.close()
            return jsonify({'error': 'Sumsub API credentials not configured'}), 500
        
        timestamp = str(int(time.time()))
        url = f"{SUMSUB_BASE_URL}/resources/applicants?levelName={level_name}"
        
        headers = {
            'X-App-Token': SUMSUB_APP_TOKEN,
            'X-App-Access-Ts': timestamp,
            'X-App-Access-Sig': generate_sumsub_signature('POST', url, json.dumps(applicant_data), timestamp),
            'Content-Type': 'application/json'
        }
        
        print(f" [SUMSUB] Making API call to: {url}")
        
        try:
            response = requests.post(url, json=applicant_data, headers=headers, timeout=30)
            
            print(f" [SUMSUB] Response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                applicant_id = result.get('id')
                
                print(f" [SUMSUB] Applicant created successfully: {applicant_id}")
                
                try:
                    conn.execute("""
                        INSERT INTO sumsub_applications 
                        (review_id, applicant_id, external_user_id, level_name, created_at, updated_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        review_id, applicant_id, f"customer_{customer_id}", 
                        level_name, datetime.utcnow().isoformat(), 
                        datetime.utcnow().isoformat(), 'init'
                    ))
                    
                    conn.execute("""
                        UPDATE reviews SET sumsub_applicant_id = ? WHERE id = ?
                    """, (applicant_id, review_id))
                    
                    conn.commit()
                    print(f"[SUMSUB] Database transaction committed successfully")
                    
                except Exception as db_error:
                    print(f" [SUMSUB] Database storage error: {str(db_error)}")
                    conn.rollback()
                    conn.close()
                    return jsonify({'error': 'Database storage failed'}), 500
                
                conn.close()
                return jsonify({
                    'success': True,
                    'applicant_id': applicant_id,
                    'access_token': result.get('accessToken')
                })
            elif response.status_code == 409:
                print(f" [SUMSUB] Applicant already exists (409 Conflict)")
                error_text = response.text
                applicant_match = re.search(r'already exists: ([a-f0-9]+)', error_text)
                
                if applicant_match:
                    existing_applicant_id = applicant_match.group(1)
                    print(f" [SUMSUB] Found existing applicant ID: {existing_applicant_id}")
                    
                    existing_app = conn.execute("""
                        SELECT * FROM sumsub_applications WHERE applicant_id = ?
                    """, (existing_applicant_id,)).fetchone()
                    
                    if existing_app:
                        conn.close()
                        return jsonify({
                            'success': True,
                            'applicant_id': existing_applicant_id,
                            'access_token': 'existing_applicant',
                            'message': 'Using existing applicant'
                        })
                    else:
                        try:
                            conn.execute("""
                                INSERT INTO sumsub_applications 
                                (review_id, applicant_id, external_user_id, level_name, created_at, updated_at, status)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                review_id, existing_applicant_id, f"customer_{customer_id}", 
                                level_name, datetime.utcnow().isoformat(), 
                                datetime.utcnow().isoformat(), 'init'
                            ))
                            
                            conn.execute("""
                                UPDATE reviews SET sumsub_applicant_id = ? WHERE id = ?
                            """, (existing_applicant_id, review_id))
                            
                            conn.commit()
                            conn.close()
                            return jsonify({
                                'success': True,
                                'applicant_id': existing_applicant_id,
                                'access_token': 'existing_applicant',
                                'message': 'Using existing applicant'
                            })
                        except Exception as db_error:
                            conn.rollback()
                            conn.close()
                            return jsonify({'error': 'Database storage failed'}), 500
                else:
                    conn.close()
                    error_message = extract_sumsub_error_message(response)
                    return jsonify({'error': error_message}), 409
            else:
                print(f" [SUMSUB] API call failed with status {response.status_code}")
                error_message = extract_sumsub_error_message(response)
                conn.close()
                return jsonify({'error': error_message}), response.status_code
                
        except requests.exceptions.Timeout:
            conn.close()
            return jsonify({'error': 'Request timeout'}), 408
        except requests.exceptions.ConnectionError:
            conn.close()
            return jsonify({'error': 'Connection error'}), 503
        except requests.exceptions.RequestException as req_error:
            conn.close()
            return jsonify({'error': f'Request error: {str(req_error)}'}), 500
            
    except Exception as e:
        print(f" [SUMSUB] Unexpected error: {str(e)}")
        import traceback
        print(f" [SUMSUB] Traceback: {traceback.format_exc()}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@csrf.exempt
@app.route('/api/sumsub/get_websdk_link', methods=['POST'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 
               'qc_review_1', 'qc_review_2', 'qc_review_3',
               'qc_1', 'qc_2', 'qc_3',
               'sme', 'quality_manager', 'admin', 'operations_manager', 'ops_manager')
def get_sumsub_websdk_link():
    """Generate an external WebSDK link for an applicant"""
    print(f"\n[SUMSUB] ===== GET WEBSDK LINK API CALLED =====")
    
    try:
        if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
            return jsonify({'error': 'Sumsub API credentials not configured'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        applicant_id = data.get('applicant_id')
        external_user_id = data.get('external_user_id')
        level_name = data.get('level_name', 'id-only')
        email = data.get('email')
        phone = data.get('phone')
        ttl_in_secs = data.get('ttl_in_secs', 1800)
        
        if not applicant_id and not external_user_id:
            return jsonify({'error': 'Either applicant_id or external_user_id is required'}), 400
        
        timestamp = str(int(time.time()))
        url = f"{SUMSUB_BASE_URL}/resources/sdkIntegrations/levels/-/websdkLink"
        
        request_body = {
            "levelName": level_name,
            "userId": external_user_id if external_user_id else applicant_id,
            "ttlInSecs": ttl_in_secs
        }
        
        # Add applicant identifiers if provided
        if email or phone:
            request_body["applicantIdentifiers"] = {}
            if email:
                request_body["applicantIdentifiers"]["email"] = email
            if phone:
                request_body["applicantIdentifiers"]["phone"] = phone
        
        headers = {
            'X-App-Token': SUMSUB_APP_TOKEN,
            'X-App-Access-Ts': timestamp,
            'X-App-Access-Sig': generate_sumsub_signature('POST', url, json.dumps(request_body), timestamp),
            'Content-Type': 'application/json'
        }
        
        print(f" [SUMSUB] Request body: {json.dumps(request_body, indent=2)}")
        
        try:
            response = requests.post(url, json=request_body, headers=headers, timeout=30)
            
            print(f" [SUMSUB] Response status: {response.status_code}")
            print(f" [SUMSUB] Response: {response.text[:500]}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                websdk_url = data.get('url')
                
                if websdk_url:
                    return jsonify({
                        'success': True,
                        'url': websdk_url
                    })
                else:
                    return jsonify({'error': 'No URL in response'}), 500
            else:
                error_message = extract_sumsub_error_message(response)
                return jsonify({'error': error_message}), response.status_code
                
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Request timeout'}), 408
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Connection error'}), 503
        except requests.exceptions.RequestException as req_error:
            return jsonify({'error': f'Request error: {str(req_error)}'}), 500
            
    except Exception as e:
        import traceback
        print(f" [SUMSUB] Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@csrf.exempt
@app.route('/api/sumsub/get_applicant_access_token/<applicant_id>', methods=['GET'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 
               'qc_review_1', 'qc_review_2', 'qc_review_3',
               'qc_1', 'qc_2', 'qc_3',
               'sme', 'quality_manager', 'admin', 'operations_manager', 'ops_manager')
def get_sumsub_applicant_access_token(applicant_id):
    """Get a fresh access token for an existing applicant (legacy method)"""
    print(f"\n[SUMSUB] ===== GET APPLICANT ACCESS TOKEN API CALLED =====")
    
    try:
        if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
            return jsonify({'error': 'Sumsub API credentials not configured'}), 500
        
        timestamp = str(int(time.time()))
        url = f"{SUMSUB_BASE_URL}/resources/accessTokens/sdk"
        
        request_body = {
            "ttlInSecs": 600,
            "userId": applicant_id,
            "levelName": "id-only"
        }
        
        headers = {
            'X-App-Token': SUMSUB_APP_TOKEN,
            'X-App-Access-Ts': timestamp,
            'X-App-Access-Sig': generate_sumsub_signature('POST', url, json.dumps(request_body), timestamp),
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, json=request_body, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                data = response.json()
                access_token = data.get('token') or data.get('accessToken') or data.get('access_token') or data.get('value')
                
                if access_token:
                    return jsonify({
                        'success': True,
                        'access_token': access_token
                    })
                else:
                    return jsonify({'error': 'No access token in response'}), 500
            else:
                error_message = extract_sumsub_error_message(response)
                return jsonify({'error': error_message}), response.status_code
                
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Request timeout'}), 408
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Connection error'}), 503
        except requests.exceptions.RequestException as req_error:
            return jsonify({'error': f'Request error: {str(req_error)}'}), 500
            
    except Exception as e:
        import traceback
        print(f" [SUMSUB] Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@csrf.exempt
@app.route('/api/sumsub/get_applicant_status/<applicant_id>')
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 
               'qc_review_1', 'qc_review_2', 'qc_review_3',
               'qc_1', 'qc_2', 'qc_3',
               'sme', 'quality_manager', 'admin', 'operations_manager', 'ops_manager')
def get_sumsub_applicant_status(applicant_id):
    """Get the current status of a Sumsub applicant"""
    print(f"\n[SUMSUB] ===== GET APPLICANT STATUS API CALLED =====")
    
    try:
        if not applicant_id:
            return jsonify({'error': 'No applicant ID provided'}), 400
        
        if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
            return jsonify({'error': 'Sumsub API credentials not configured'}), 500
            
        timestamp = str(int(time.time()))
        url = f"{SUMSUB_BASE_URL}/resources/applicants/{applicant_id}/status"
        
        headers = {
            'X-App-Token': SUMSUB_APP_TOKEN,
            'X-App-Access-Ts': timestamp,
            'X-App-Access-Sig': generate_sumsub_signature('GET', url, '', timestamp)
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response formats
                # Format 1: Direct response with reviewStatus and reviewResult
                review_status = data.get('reviewStatus') or data.get('review', {}).get('reviewStatus', 'unknown')
                review_result = data.get('reviewResult') or data.get('review', {}).get('reviewResult', {})
                review_answer = review_result.get('reviewAnswer', '') if isinstance(review_result, dict) else ''
                
                # Format 2: Nested in review object
                if not review_status or review_status == 'unknown':
                    review_obj = data.get('review', {})
                    review_status = review_obj.get('reviewStatus', 'unknown')
                    review_result = review_obj.get('reviewResult', {})
                    review_answer = review_result.get('reviewAnswer', '') if isinstance(review_result, dict) else ''
                
                print(f" [SUMSUB] Review status: {review_status}, Review answer: {review_answer}")
                
                # Update database with latest status
                conn = get_db_connection()
                try:
                    conn.execute("""
                        UPDATE sumsub_applications 
                        SET status = ?, updated_at = ?
                        WHERE applicant_id = ?
                    """, (review_status, datetime.utcnow().isoformat(), applicant_id))
                    
                    if review_status in ['completed', 'approved', 'rejected']:
                        review_score = data.get('reviewScore', 0) or data.get('score', 0)
                        conn.execute("""
                            UPDATE reviews 
                            SET sumsub_verification_status = ?, 
                                sumsub_verification_score = ?,
                                sumsub_verification_date = ?,
                                sumsub_verification_result = ?
                            WHERE sumsub_applicant_id = ?
                        """, (
                            review_answer,
                            review_score,
                            datetime.utcnow().isoformat(),
                            json.dumps(data),
                            applicant_id
                        ))
                        print(f" [SUMSUB] Updated review table with status: {review_answer}")
                    
                    conn.commit()
                except Exception as db_error:
                    print(f" [SUMSUB] Database update error: {str(db_error)}")
                    import traceback
                    print(f" [SUMSUB] Traceback: {traceback.format_exc()}")
                    conn.rollback()
                    return jsonify({'error': 'Database update failed'}), 500
                finally:
                    conn.close()
                
                return jsonify(data)
            else:
                error_message = extract_sumsub_error_message(response)
                return jsonify({'error': error_message}), response.status_code
                
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Request timeout'}), 408
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Connection error'}), 503
        except requests.exceptions.RequestException as req_error:
            return jsonify({'error': f'Request error: {str(req_error)}'}), 500
            
    except Exception as e:
        import traceback
        print(f" [SUMSUB] Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@csrf.exempt
@app.route('/api/sumsub/get_task_data/<task_id>', methods=['GET'])
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 
               'qc_review_1', 'qc_review_2', 'qc_review_3',
               'qc_1', 'qc_2', 'qc_3',
               'sme', 'quality_manager', 'admin', 'operations_manager', 'ops_manager')
def get_sumsub_task_data(task_id):
    """Get review data for a task to use with Sumsub"""
    try:
        # Ensure Sumsub tables and columns exist
        ensure_sumsub_tables()
        
        conn = get_db_connection()
        
        # Check if sumsub_applicant_id column exists, if not use COALESCE to handle it
        try:
            review = conn.execute(
                "SELECT id, customer_id, task_id, sumsub_applicant_id FROM reviews WHERE task_id = ?", (task_id,)
            ).fetchone()
        except sqlite3.OperationalError:
            # Column doesn't exist yet, select without it
            review = conn.execute(
                "SELECT id, customer_id, task_id FROM reviews WHERE task_id = ?", (task_id,)
            ).fetchone()
        
        conn.close()
        
        if not review:
            return jsonify({'error': 'Review not found'}), 404
        
        # Safely get sumsub_applicant_id
        sumsub_applicant_id = None
        if 'sumsub_applicant_id' in review.keys():
            sumsub_applicant_id = review['sumsub_applicant_id']
        
        return jsonify({
            'review_id': review['id'],
            'customer_id': review['customer_id'],
            'task_id': review['task_id'],
            'sumsub_applicant_id': sumsub_applicant_id
        })
    except Exception as e:
        import traceback
        print(f"[SUMSUB] Error in get_sumsub_task_data: {str(e)}")
        print(f"[SUMSUB] Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@csrf.exempt
@app.route('/api/sumsub/get_applicant_documents/<applicant_id>')
@role_required('reviewer_1', 'reviewer_2', 'reviewer_3', 
               'qc_review_1', 'qc_review_2', 'qc_review_3',
               'qc_1', 'qc_2', 'qc_3',
               'sme', 'quality_manager', 'admin', 'operations_manager', 'ops_manager')
def get_sumsub_applicant_documents(applicant_id):
    """Get documents uploaded by a Sumsub applicant"""
    print(f"\n[SUMSUB] ===== GET APPLICANT DOCUMENTS API CALLED =====")
    
    try:
        if not applicant_id:
            return jsonify({'error': 'No applicant ID provided'}), 400
        
        if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
            return jsonify({'error': 'Sumsub API credentials not configured'}), 500
            
        timestamp = str(int(time.time()))
        url = f"{SUMSUB_BASE_URL}/resources/applicants/{applicant_id}/info/idDocs"
        
        headers = {
            'X-App-Token': SUMSUB_APP_TOKEN,
            'X-App-Access-Ts': timestamp,
            'X-App-Access-Sig': generate_sumsub_signature('GET', url, '', timestamp)
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Store document information in database
                conn = get_db_connection()
                try:
                    application = conn.execute(
                        "SELECT id FROM sumsub_applications WHERE applicant_id = ?", (applicant_id,)
                    ).fetchone()
                    
                    if application and 'idDocs' in data and data['idDocs']:
                        for doc in data['idDocs']:
                            conn.execute("""
                                INSERT OR REPLACE INTO sumsub_documents 
                                (application_id, document_type, document_number, country_code, 
                                 verification_status, verification_result, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                application['id'],
                                doc.get('idDocType', ''),
                                doc.get('idDocNumber', ''),
                                doc.get('country', ''),
                                doc.get('reviewResult', {}).get('reviewAnswer', 'pending'),
                                json.dumps(doc),
                                datetime.utcnow().isoformat()
                            ))
                    conn.commit()
                except Exception as db_error:
                    conn.rollback()
                    return jsonify({'error': 'Database storage failed'}), 500
                finally:
                    conn.close()
                
                return jsonify(data)
            else:
                error_message = extract_sumsub_error_message(response)
                return jsonify({'error': error_message}), response.status_code
                
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Request timeout'}), 408
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Connection error'}), 503
        except requests.exceptions.RequestException as req_error:
            return jsonify({'error': f'Request error: {str(req_error)}'}), 500
            
    except Exception as e:
        import traceback
        print(f" [SUMSUB] Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

# Start Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)

#!/usr/bin/env python3
"""Test chaser cycle logic independently"""

import sqlite3
from datetime import date, timedelta, datetime

db_path = "Due Diligence/scrutinise_workflow.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get user_id for reviewer
cursor.execute("SELECT id FROM users WHERE email = 'reviewer@scrutinise.co.uk'")
user = cursor.fetchone()
user_id = user['id']
print(f"User ID: {user_id}")

# Get assigned tasks
cursor.execute("SELECT * FROM reviews WHERE assigned_to = ?", (user_id,))
my_assigned_rows = [dict(r) for r in cursor.fetchall()]
print(f"Assigned tasks: {len(my_assigned_rows)}")

# Calculate week days
today = date.today()
monday_this = today - timedelta(days=today.weekday())
week_days = [monday_this + timedelta(days=i) for i in range(5)]
print(f"\nCurrent week (Mon-Fri):")
for i, d in enumerate(week_days):
    print(f"  {i}: {d} ({d.strftime('%A')})")

# DUE_MAP and ISSUED_MAP
DUE_MAP = {
    "7": ["Chaser1DueDate", "Chaser_1_DueDate", "chaser1_due", "chaser_1_due", "Outreach1DueDate", "Outreach_Cycle_1_Due", "outreach_chaser_date1"],
    "14": ["Chaser2DueDate", "Chaser_2_DueDate", "chaser2_due", "chaser_2_due", "Outreach2DueDate", "Outreach_Cycle_2_Due", "outreach_chaser_date2"],
    "21": ["Chaser3DueDate", "Chaser_3_DueDate", "chaser3_due", "chaser_3_due", "Outreach3DueDate", "Outreach_Cycle_3_Due", "outreach_chaser_date3"],
    "NTC": ["NTCDueDate", "NTC_DueDate", "ntc_due", "NTC Due Date", "NTC_Due"]
}
ISSUED_MAP = {
    "7": ["Chaser1IssuedDate", "Chaser1DateIssued", "chaser1_issued", "Outreach1Date", "Outreach_Cycle_1_Issued", "Outreach Cycle 1 Issued", "outreach_chaser_issued1"],
    "14": ["Chaser2IssuedDate", "Chaser2DateIssued", "chaser2_issued", "Outreach2Date", "Outreach_Cycle_2_Issued", "Outreach Cycle 2 Issued", "outreach_chaser_issued2"],
    "21": ["Chaser3IssuedDate", "Chaser3DateIssued", "chaser3_issued", "Outreach3Date", "Outreach_Cycle_3_Issued", "Outreach Cycle 3 Issued", "outreach_chaser_issued3"],
    "NTC": ["NTCIssuedDate", "NTC_IssuedDate", "ntc_issued", "outreach_ntc_issued"]
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
    return None

def _is_blank_issued(v):
    if v is None:
        return True
    s = str(v).strip().lower()
    return s in ("", "none", "null", "n/a", "na", "-", "0", "false")

def _is_chaser_issued(rec, chaser_type):
    ik = _coalesce_key(rec, ISSUED_MAP.get(chaser_type, []))
    if ik:
        return not _is_blank_issued(rec.get(ik))
    return False

# Initialize chaser_week_rows
chaser_week_headers = ["7", "14", "21", "NTC"]
chaser_week_rows = [
    {"date": d.strftime("%d/%m/%Y"), "iso": d.isoformat(), **{h: 0 for h in chaser_week_headers}}
    for d in week_days
]
chaser_overdue = {"7": 0, "14": 0, "21": 0, "NTC": 0}

print(f"\n{'='*60}")
print("PROCESSING CHASER CYCLE")
print(f"{'='*60}")

# Process assigned tasks
for rec in my_assigned_rows:
    case_id = rec.get('case_id', 'UNKNOWN')
    
    # Skip if outreach is completed
    outreach_complete = rec.get('outreach_complete')
    if outreach_complete in (1, '1', True, 'true', 'True'):
        print(f"\n{case_id}: SKIPPED (outreach complete)")
        continue
    
    print(f"\n{case_id}: Processing...")
    
    # Check chasers sequentially
    chaser_sequence = ["7", "14", "21", "NTC"]
    found_next_chaser = False
    
    for typ in chaser_sequence:
        # Check prerequisites
        if typ == "7":
            prev_issued = True
        elif typ == "14":
            prev_issued = _is_chaser_issued(rec, "7")
        elif typ == "21":
            prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14")
        elif typ == "NTC":
            prev_issued = _is_chaser_issued(rec, "7") and _is_chaser_issued(rec, "14") and _is_chaser_issued(rec, "21")
        else:
            prev_issued = False
        
        print(f"  {typ}-day: prev_issued={prev_issued}", end="")
        
        if not prev_issued:
            print(" -> SKIP (prerequisites not met)")
            continue
        
        # Check if this chaser is already issued
        if _is_chaser_issued(rec, typ):
            print(" -> Already issued")
            continue
        
        # Get due date
        k = _coalesce_key(rec, DUE_MAP.get(typ, []))
        if not k:
            print(f" -> No due date key found")
            continue
        
        due_val = rec.get(k)
        d = _parse_date_any(due_val)
        if not d:
            print(f" -> Due date parse failed (value: {due_val})")
            continue
        
        print(f" -> Due: {d}", end="")
        
        # Find which row this due date falls into
        row_idx = None
        for idx, week_day in enumerate(week_days):
            if d == week_day:
                row_idx = idx
                break
        
        is_overdue = d < monday_this
        is_in_current_week = row_idx is not None
        
        print(f", overdue={is_overdue}, in_week={is_in_current_week}, row_idx={row_idx}")
        
        if is_overdue:
            chaser_overdue[typ] += 1
            print(f"    ✅ ADDED TO OVERDUE")
            found_next_chaser = True
            break
        elif is_in_current_week:
            chaser_week_rows[row_idx][typ] += 1
            print(f"    ✅ ADDED TO WEEK ROW {row_idx} ({week_days[row_idx]})")
            found_next_chaser = True
            break
        else:
            print(f"    ⏭️  NOT IN CURRENT WEEK (future)")

print(f"\n{'='*60}")
print("FINAL RESULTS")
print(f"{'='*60}")
print("\nChaser Week Rows:")
for row in chaser_week_rows:
    print(f"  {row['date']}: 7={row['7']}, 14={row['14']}, 21={row['21']}, NTC={row['NTC']}")

print(f"\nChaser Overdue: {chaser_overdue}")

conn.close()

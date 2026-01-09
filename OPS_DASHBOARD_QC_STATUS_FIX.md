# Operations Dashboard - QC Status Fix
**Date:** 2026-01-09  
**Issue:** TASK-20260108-001 showing as "Completed" instead of "QC – Awaiting Assignment"

---

## Problem Summary

### Issue Reported
TASK-20260108-001 (CUST2001) is in "QC Waiting Assignment" status but appears in the "Completed" section of the Operations Dashboard Case Status & Age Profile table.

### Root Cause
The `map_raw_status_to_enum()` function in `utils.py` was checking for:
```python
if "qc" in s and ("awaiting assignment" in s or "unassigned" in s):
```

However, the actual status in the database is **"QC Waiting Assignment"** (uses "waiting" not "awaiting"), so the check failed and returned `None`, causing the function to fall back to the derived status of "Completed".

---

## Solution

### Code Change
**File:** `/home/user/webapp/DueDiligenceBackend/Due Diligence/utils.py`  
**Line:** 319

**Before:**
```python
if "qc" in s and ("awaiting assignment" in s or "unassigned" in s):
    return ReviewStatus.QC_UNASSIGNED
```

**After:**
```python
if "qc" in s and ("awaiting assignment" in s or "waiting assignment" in s or "unassigned" in s):
    return ReviewStatus.QC_UNASSIGNED
```

### Status Flow
1. **Raw Status** (database): `"QC Waiting Assignment"`
2. **map_raw_status_to_enum()**: Returns `ReviewStatus.QC_UNASSIGNED` → `"QC – Awaiting Assignment"`
3. **derive_case_status()**: Returns `"Completed"` (because date_completed is set)
4. **best_status_with_raw_override()**: Returns `"QC – Awaiting Assignment"` (raw status takes precedence)

---

## Test Results

### Before Fix
```
ID 125 - CUST2001
  Raw Status:     QC Waiting Assignment
  Derived Status: Completed ❌
  
Dashboard Count:
  Completed: 6 (including CUST2001) ❌
```

### After Fix
```
ID 125 - CUST2001
  Raw Status:     QC Waiting Assignment  
  Derived Status: QC – Awaiting Assignment ✅
  
Dashboard Count:
  QC – Awaiting Assignment: 1 (CUST2001) ✅
  Completed: 5 (CUST3001-CUST3005) ✅
```

### Execution Trace (Verified)
```
Step 1: map_raw_status_to_enum('QC Waiting Assignment')
  Output: QC – Awaiting Assignment ✅

Step 2: derive_case_status(CUST2001)
  Output: Completed (correctly overridden)

Step 3: best_status_with_raw_override(CUST2001)
  Output: QC – Awaiting Assignment ✅
```

---

## Impact on Operations Dashboard

### Case Status & Age Profile Table
**Before:**
- Completed: 6 cases (CUST2001 incorrectly included)
- QC – Awaiting Assignment: 0 cases

**After:**
- Completed: 5 cases (CUST3001, CUST3002, CUST3003, CUST3004, CUST3005)
- QC – Awaiting Assignment: 1 case (CUST2001) ✅

### Expected Behavior
- When a case has status = "QC Waiting Assignment", it will now correctly appear under "QC – Awaiting Assignment"
- Once QC is assigned (qc_assigned_to is set), status will move to "QC – In Progress"
- After QC review is complete (qc_check_date is set), status will move to "Completed"

---

## Data Details

### CUST2001 (TASK-20260108-001) - QC Waiting Assignment
```
id:              125
customer_id:     CUST2001
status:          QC Waiting Assignment
assigned_to:     33 (reviewer1)
completed_by:    33 (reviewer1)
date_assigned:   2026-01-08 20:52:44
date_completed:  2026-01-08T21:24:36
DateSenttoQC:    2026-01-08
qc_assigned_to:  None (awaiting QC assignment)
qc_check_date:   None (QC not started)
```

### Test Submissions (Completed - Not Selected for QC)
```
ID 145 - CUST3001 | Completed: 2026-01-05 ✅
ID 146 - CUST3002 | Completed: 2026-01-06 ✅
ID 147 - CUST3003 | Completed: 2026-01-07 ✅
ID 148 - CUST3004 | Completed: 2026-01-08 ✅
ID 149 - CUST3005 | Completed: 2026-01-09 ✅
```

---

## Deployment Status

### Backend
- **Process:** PM2 (flask-backend)
- **Port:** 5050
- **Status:** ✅ Online with updated utils.py
- **Restart:** Backend restarted after utils.py fix to load new code

### Frontend  
- **Process:** PM2 (frontend)
- **Port:** 5173
- **Status:** ✅ Online
- **URL:** https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

### AI SME
- **Process:** PM2 (ai-sme)
- **Port:** 8000
- **Status:** ✅ Online

---

## Testing Instructions

### 1. Login as Operations Manager
```
Email:    opsmanager@scrutinise.co.uk
Password: Scrutinise2024!
```

### 2. Navigate to Operations Dashboard
- Click **"Operations Dashboard"** in the main navigation

### 3. Verify Case Status & Age Profile
**Expected Counts:**
- **QC – Awaiting Assignment:** 1 case
  - Should list: CUST2001 (TASK-20260108-001)
- **Completed:** 5 cases
  - Should list: CUST3001, CUST3002, CUST3003, CUST3004, CUST3005

### 4. Filter by Status
- Click on **"QC – Awaiting Assignment"** status row
- Should display: 1 case (CUST2001)
- Click on **"Completed"** status row  
- Should display: 5 cases (CUST3001-CUST3005)

### 5. Verify CUST2001 Details
- In the QC – Awaiting Assignment list, click on CUST2001
- Status should show: **"QC – Awaiting Assignment"**
- DateSenttoQC: 2026-01-08
- QC Assigned To: (empty)

---

## Related Files Changed

### Modified
1. **utils.py** - Added "waiting assignment" check
   - Path: `/home/user/webapp/DueDiligenceBackend/Due Diligence/utils.py`
   - Line: 319
   - Change: Added `or "waiting assignment" in s` to QC status check

### Database (scrutinise_workflow.db)
- No schema changes
- Data remains unchanged
- Status derivation logic updated in application code only

---

## Git Backup

### Repository
- **URL:** https://github.com/PatAgora/due-diligence-app
- **Branch:** main
- **Latest Commit:** `ca2ad39` - "✅ QC Status Fix Verified - Operations Dashboard Now Accurate"

### Commit History (Recent)
```
ca2ad39 - QC Status Fix Verified - Operations Dashboard Now Accurate (2026-01-09)
55d0aec - Backend Restarted - QC Status Fix Now Active (2026-01-09)
```

---

## Status: ✅ FIXED AND VERIFIED

### Verification Checklist
- [x] Code change implemented in utils.py
- [x] Backend restarted with updated code
- [x] Status mapping test passed: "QC Waiting Assignment" → "QC – Awaiting Assignment"
- [x] CUST2001 status derivation test passed: Returns "QC – Awaiting Assignment"
- [x] All 6 submissions status verified
- [x] Git commit and push completed
- [x] Documentation created

### Next Steps
1. **Test in UI:** Login and verify Operations Dashboard displays correctly
2. **Monitor:** Check that QC workflow continues to work properly
3. **Verify:** Ensure reviewer dashboard remains unchanged (not affected by this fix)

---

## Technical Notes

### Why This Fix Works
1. **Preserves Raw Status:** `best_status_with_raw_override()` prioritizes raw status when it maps to a known enum
2. **Correct Mapping:** Now recognizes "waiting assignment" variant used in database
3. **Fallback Safe:** If mapping fails, falls back to derived status (existing behavior)

### Status Priority Logic
```
1. Special preservations (AI SME, Awaiting QC Rework, Outreach Complete)
2. Raw status mapping (if not None)
3. Derived status (calculated from record fields)
```

### QC Workflow States
```
Completed → DateSenttoQC set
    ↓
QC Waiting Assignment (qc_assigned_to = None)
    ↓
QC – In Progress (qc_assigned_to set, qc_check_date = None)
    ↓
QC - Complete (qc_check_date set, qc_outcome = Pass/Fail)
    ↓
Completed (if Pass) or QC – Rework Required (if Fail)
```

---

**Fix Confirmed:** TASK-20260108-001 now correctly displays as "QC – Awaiting Assignment" in the Operations Dashboard! 🎉

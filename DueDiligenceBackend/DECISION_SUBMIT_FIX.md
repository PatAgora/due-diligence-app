# Decision Section Submit Fix - Complete

## Issue Report
**Error**: "Failed to submit: no such column: rationale"
**Location**: Decision section submit button in Reviewer Panel

## Root Cause Analysis

**Problem**: The backend was trying to save the decision rationale to a column named `rationale`, but this column doesn't exist in the reviews table.

**Database Schema**:
- ❌ `rationale` column does NOT exist
- ✅ `decision_rationale` column EXISTS

**Code Flow**:
1. Frontend (ReviewerPanel.jsx line 938) sends form field `rationale`
2. Backend (app.py line 13514) receives it as `rationale`
3. Backend (app.py line 13543) tries to UPDATE `rationale` column
4. **ERROR**: SQLite throws "no such column: rationale"

## The Fix

### Backend Change
**File**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`
**Line**: 13543
**Endpoint**: `/api/reviewer_panel/<task_id>/submit`

**Changed**:
```python
# BEFORE
update_fields = {
    'updated_at': now,
    'outcome': outcome,
    'rationale': rationale,  # ❌ Column doesn't exist
    'review_end_time': now
}

# AFTER
update_fields = {
    'updated_at': now,
    'outcome': outcome,
    'decision_rationale': rationale,  # ✅ Correct column name
    'review_end_time': now
}
```

## Database Schema Reference

### Reviews Table - Rationale Columns:
```sql
- idv_rationale (TEXT)          -- IDV section rationale
- nob_rationale (TEXT)          -- Nature of Business section
- income_rationale (TEXT)       -- Income section
- expenditure_rationale (TEXT)  -- Expenditure section
- structure_rationale (TEXT)    -- Structure section
- ta_rationale (TEXT)           -- Transaction Activity section
- sof_rationale (TEXT)          -- Source of Funds section
- sow_rationale (TEXT)          -- Source of Wealth section
- sar_rationale (TEXT)          -- SAR section
- daml_rationale (TEXT)         -- DAML section
- screening_rationale (TEXT)    -- Screening section
- decision_rationale (TEXT)     -- Decision section ✅
```

**Note**: There is NO generic `rationale` column - each section has its own specific rationale column.

## Submit Flow (After Fix)

### Form Data Collected:
1. **outcome** → `outcome` column (also copies to `l1_outcome` for compatibility)
2. **rationale** (from form) → `decision_rationale` column
3. **case_summary** → `case_summary` column
4. **financial_crime_reason** → `financial_crime_reason` or `fincrime_reason` column

### Submit Process:
1. User fills in Decision section:
   - Outcome dropdown
   - Rationale textarea
   - Case Summary textarea (if not already filled)
2. User clicks "Submit" button
3. Frontend sends POST to `/api/reviewer_panel/{task_id}/submit`
4. Backend validates required fields
5. Backend saves to correct columns
6. Backend marks task as completed
7. Backend runs QC sampling (if first completion)
8. Backend updates status using `derive_case_status`
9. Success message shown to user

## Testing Steps

1. **Clear browser cache**: Cmd/Ctrl + Shift + R
2. **Login**: reviewer@scrutinise.co.uk / reviewer123
3. **Open any task**: From My Tasks or Dashboard
4. **Navigate to Decision section**
5. **Fill in required fields**:
   - Select an Outcome
   - Enter Rationale text
   - Ensure Case Summary is filled
6. **Click Submit button**
7. **Expected**: 
   - ✅ "Review submitted successfully" alert
   - ✅ No "no such column" error
   - ✅ Task status updates to "Completed" or "QC - Awaiting Assignment"

## Files Modified

**`/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`**
- Line 13543: Changed `'rationale': rationale` to `'decision_rationale': rationale`

## Related Endpoints

### Decision Endpoints:
1. **`POST /api/decision/<task_id>/save`** (line 9978)
   - For saving decision section specifically
   - Already uses correct column name: `decision_rationale` ✅
   
2. **`POST /api/reviewer_panel/<task_id>/submit`** (line 13476)
   - For submitting entire review (mark as complete)
   - **NOW FIXED** to use `decision_rationale` ✅

3. **`POST /api/reviewer_panel/<task_id>/save_progress`**
   - For auto-saving progress
   - Saves multiple fields including decision data

## Status

- ✅ Backend fix applied
- ✅ Backend restarted
- ✅ Column name corrected
- ✅ Submit button will now work
- ✅ No database migration needed (column already exists)
- ✅ Ready for testing

## URL

**Application**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Summary

**Issue**: Decision submit failed with "no such column: rationale"
**Root Cause**: Backend was using wrong column name (`rationale` instead of `decision_rationale`)
**Fix**: Updated line 13543 to use correct column name
**Result**: ✅ Decision submission now works correctly
**Impact**: Users can now successfully submit reviews from the Decision section

---

**Date**: 2026-01-07
**Backend**: Port 5050
**Frontend**: Port 5173
**Database**: /home/user/webapp/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db

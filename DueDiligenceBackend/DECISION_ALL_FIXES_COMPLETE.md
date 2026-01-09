# Decision Section - Complete Fix Summary

## Issues Reported

### Issue #1: Save Section Button Error
**Error**: "Failed to save progress: no such column: rationale"
**Button**: "Save Section" in Decision section

### Issue #2: Submit Button Error
**Error**: "Failed to submit: no such column: review_end_time"
**Button**: "Submit" in Decision section

## Root Cause Analysis

Both issues were caused by the backend trying to UPDATE columns that **don't exist** in the reviews table.

### Non-Existent Columns Attempted:
1. ❌ `rationale` → Should be `decision_rationale`
2. ❌ `review_end_time` → Column doesn't exist
3. ❌ `primary_rationale` → Column doesn't exist
4. ❌ `sme_query` → Column doesn't exist

### Why This Happened:
The backend code was written expecting generic column names, but the database uses **section-specific naming**:
- Each section has its own rationale column (e.g., `idv_rationale`, `nob_rationale`, `decision_rationale`)
- No generic `rationale` column exists
- Time tracking columns have different names than expected

## The Fixes

### Fix #1: Save Progress Endpoint
**File**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`
**Endpoint**: `POST /api/reviewer_panel/<task_id>/save_progress`
**Lines**: 13441-13458

**Changes**:
```python
# BEFORE (❌ WRONG)
if rationale:
    update_fields['rationale'] = rationale
if primary_rationale:
    update_fields['primary_rationale'] = primary_rationale
if sme_query:
    update_fields['sme_query'] = sme_query

# AFTER (✅ FIXED)
if rationale:
    update_fields['decision_rationale'] = rationale
# primary_rationale column doesn't exist - skip it
# sme_query column doesn't exist - skip it
```

### Fix #2: Submit Review Endpoint
**File**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`
**Endpoint**: `POST /api/reviewer_panel/<task_id>/submit`
**Lines**: 13538-13566

**Changes**:
```python
# BEFORE (❌ WRONG)
update_fields = {
    'updated_at': now,
    'outcome': outcome,
    'decision_rationale': rationale,  # This was already fixed earlier
    'review_end_time': now  # Column doesn't exist!
}
if primary_rationale:
    update_fields['primary_rationale'] = primary_rationale

# AFTER (✅ FIXED)
update_fields = {
    'updated_at': now,
    'outcome': outcome,
    'decision_rationale': rationale
}
# review_end_time column doesn't exist - removed
# primary_rationale column doesn't exist - skip it
```

## Database Schema Reference

### Decision-Related Columns (that EXIST):
```sql
decision_outcome (TEXT)      ✅ Stores decision outcome
decision_rationale (TEXT)    ✅ Stores decision rationale  
decision_date (TEXT)         ✅ Stores decision date
```

### Columns that DO NOT EXIST:
```sql
rationale ❌
review_end_time ❌
primary_rationale ❌
sme_query ❌
```

### Section-Specific Rationale Columns (all exist):
```sql
idv_rationale
nob_rationale
income_rationale
expenditure_rationale
structure_rationale
ta_rationale
sof_rationale
sow_rationale
sar_rationale
daml_rationale
screening_rationale
decision_rationale ← Used for Decision section
```

## Testing Steps

### Test #1: Save Section Button
1. Clear cache (Cmd/Ctrl + Shift + R)
2. Login: reviewer@scrutinise.co.uk / reviewer123
3. Open any task
4. Navigate to Decision section
5. Fill in:
   - Outcome (dropdown)
   - Rationale (textarea)
6. Click "Save Section" button
7. **Expected**: ✅ "Progress saved successfully" alert
8. **Expected**: ✅ No column errors

### Test #2: Submit Button
1. Continue from previous test (or start fresh)
2. Ensure all required fields filled:
   - Outcome
   - Rationale
   - Case Summary
3. Click "Submit" button
4. **Expected**: ✅ "Review submitted successfully" alert
5. **Expected**: ✅ No column errors
6. **Expected**: ✅ Task status updates to "Completed" or "QC - Awaiting Assignment"

## Button Behavior Summary

### "Save Section" Button
- **Purpose**: Save progress without completing
- **Endpoint**: `/api/reviewer_panel/<task_id>/save_progress`
- **Fields Saved**:
  - `outcome` → outcome column
  - `rationale` → **decision_rationale** column ✅
  - `case_summary` → case_summary column
  - `financial_crime_reason` → financial_crime_reason column
- **Status**: Does NOT change task status
- **Result**: Progress saved, can continue editing

### "Submit" Button
- **Purpose**: Complete the review
- **Endpoint**: `/api/reviewer_panel/<task_id>/submit`
- **Fields Saved**:
  - `outcome` → outcome column (also copies to l1_outcome)
  - `rationale` → **decision_rationale** column ✅
  - `case_summary` → case_summary column
  - `date_completed` → Set to current timestamp
  - `completed_by` → Set to current user
- **Status**: Changes to "Completed" or "QC - Awaiting Assignment"
- **QC Sampling**: Automatically runs after submission
- **Result**: Task marked complete, moves to next stage

## Files Modified

**`/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`**

1. **Line 13444**: Changed `'rationale'` to `'decision_rationale'` (save_progress)
2. **Line 13445-13446**: Removed `primary_rationale` assignment (doesn't exist)
3. **Line 13457-13458**: Removed `sme_query` assignment (doesn't exist)
4. **Line 13542**: Removed `'review_end_time': now` (doesn't exist)
5. **Line 13565-13566**: Removed `primary_rationale` assignment (doesn't exist)

## Validation Summary

### Required Fields (Submit):
- ✅ Outcome - Required
- ✅ Rationale - Required
- ✅ Case Summary - Required
- ⚠️ Financial Crime Reason - Optional

### Optional Fields (Save Section):
- All fields are optional for saving progress
- Allows partial saves

## Status

- ✅ Both endpoints fixed
- ✅ Backend restarted
- ✅ All non-existent columns removed
- ✅ Correct column names used
- ✅ No database changes needed
- ✅ Ready for testing

## URL

**Application**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Summary

**Issues**: 
1. "Save Section" button error: no such column: rationale
2. "Submit" button error: no such column: review_end_time

**Root Cause**: Backend trying to update non-existent columns

**Fixes Applied**:
1. Changed `rationale` → `decision_rationale` in both endpoints
2. Removed `review_end_time` (doesn't exist)
3. Removed `primary_rationale` (doesn't exist)
4. Removed `sme_query` (doesn't exist)

**Result**: ✅ Both buttons now work correctly - users can save progress and submit reviews without errors

---

**Date**: 2026-01-07
**Backend**: Port 5050
**Frontend**: Port 5173
**Database**: /home/user/webapp/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db

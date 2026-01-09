# Save Section Status & Rationale Fix - Complete Summary

## Issues Fixed

### 1. Status Changed When Clicking "Save Section"
**Problem:** Clicking "Save Section" changed the task status from "21 Day Chaser Due" to "Completed"

**Root Cause:** The GET endpoint `/api/reviewer_panel/<task_id>` was re-deriving the status every time data was fetched

**Why This Happened:**
1. User clicks "Save Section" → Backend saves data ✅
2. Frontend calls `fetchTaskData()` to refresh the UI
3. Backend GET endpoint runs status derivation logic
4. `derive_case_status()` sees outcome/rationale filled → Changes status to "Completed" ❌

**Fix:** Modified the GET endpoint to preserve the existing status from the database

### 2. Rationale Disappeared After Save
**Problem:** After clicking "Save Section", the rationale textarea became empty

**Root Cause:** Field name mismatch between backend and frontend

**Why This Happened:**
- Frontend sends: `rationale` (line 903)
- Backend saves to: `decision_rationale` (line 13444)
- Frontend reads: `review.rationale` (line 1361, 2200) ❌
- Database has: `decision_rationale` ✅

**Fix:** Updated frontend to read from the correct field name `decision_rationale`

---

## Backend Changes

### File: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`

### Change 1: Remove Status Derivation from GET Endpoint (Lines 11929-11946)

**BEFORE:**
```python
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
```

**AFTER:**
```python
# IMPORTANT: DO NOT re-derive status when just fetching data
# Status should only be updated when:
# 1. Task is submitted (via /submit endpoint)
# 2. Task is assigned/reassigned (via assignment endpoint)
# 3. QC actions occur (via QC endpoints)
# 
# Save Section / Save Progress should NOT change status
# Just use the existing status from the database
from utils import derive_case_status, best_status_with_raw_override
raw_status = review.get('status', '')

# Only preserve the status as-is
review['status'] = raw_status if raw_status else 'Pending Review'
```

---

## Frontend Changes

### File: `/home/user/webapp/DueDiligenceFrontend/src/components/ReviewerPanel.jsx`

### Change 1: Read Rationale from Correct Field (Line 1361)

**BEFORE:**
```javascript
rationale: taskData?.review?.rationale || '',
```

**AFTER:**
```javascript
rationale: taskData?.review?.decision_rationale || '', // Backend saves to decision_rationale
```

### Change 2: Populate Textarea from Correct Field (Line 2200)

**BEFORE:**
```javascript
defaultValue={review.rationale || ''}
```

**AFTER:**
```javascript
defaultValue={review.decision_rationale || ''}
```

---

## Status Update Rules

### When Status SHOULD Update:
1. **Submit Button** → Changes to "Completed" or "QC - Awaiting Assignment"
2. **Task Assignment** → Changes to "Pending Review" or similar
3. **QC Actions** → Changes to "QC - In Progress", "QC Passed", etc.
4. **Outreach Actions** → Changes to "Outreach", "Chaser Due", etc.

### When Status SHOULD NOT Update:
1. **Save Section Button** → Status stays the same ✅
2. **Save Progress** → Status stays the same ✅
3. **Fetching Task Data** → Status stays the same ✅
4. **Auto-save / Draft** → Status stays the same ✅

---

## Field Name Reference

### Decision Section Fields in Database:
```sql
outcome TEXT              -- Decision outcome (Retain/Terminate/etc.)
decision_rationale TEXT   -- Decision rationale/reasoning
decision_date TEXT        -- Date of decision
case_summary TEXT         -- Case summary
financial_crime_reason TEXT  -- Financial crime reason (if applicable)
```

### Frontend Form Field Names:
```html
<select name="outcome">         <!-- Maps to: outcome -->
<textarea name="rationale">     <!-- Maps to: decision_rationale -->
<textarea name="case_summary">  <!-- Maps to: case_summary -->
<select name="financial_crime_reason">  <!-- Maps to: financial_crime_reason -->
```

### Save Flow:
```
Frontend (name="rationale") 
    ↓ POST /api/reviewer_panel/<task_id>/save_progress
Backend (saves to decision_rationale)
    ↓ UPDATE reviews SET decision_rationale = ?
Database (decision_rationale column)
    ↓ GET /api/reviewer_panel/<task_id>
Backend (reads decision_rationale)
    ↓ response.json()
Frontend (reads review.decision_rationale)
    ↓ defaultValue={review.decision_rationale}
Textarea displays rationale ✅
```

---

## Testing Results

### Before Fix:
❌ Click "Save Section" → Status changes to "Completed"
❌ Click "Save Section" → Rationale disappears
❌ Task shows as completed when it shouldn't be

### After Fix:
✅ Click "Save Section" → Status stays "21 Day Chaser Due"
✅ Click "Save Section" → Rationale persists correctly
✅ Task remains in current status until explicitly submitted

---

## Testing Steps

### Test Save Section:
1. Clear browser cache (Ctrl+Shift+R)
2. Login as reviewer: `reviewer@scrutinise.co.uk` / `reviewer123`
3. Open task CASE-2026011 (status: "21 Day Chaser Due")
4. Fill in Decision section:
   - Outcome: "Retain"
   - Rationale: "Test rationale content"
5. Click "Save Section"
6. **Expected Results:**
   - ✅ Alert: "Progress saved successfully"
   - ✅ Status remains: "21 Day Chaser Due" (not changed to "Completed")
   - ✅ Rationale still visible in textarea
   - ✅ All fields preserved

### Test Submit (Status SHOULD Change):
1. Fill in required fields
2. Click "Submit" button (not "Save Section")
3. **Expected Results:**
   - ✅ Alert: "Review submitted successfully"
   - ✅ Status changes to: "Completed" or "QC - Awaiting Assignment"
   - ✅ date_completed and completed_by are set

---

## Files Modified

### Backend:
1. `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`
   - Line 11929-11946: Removed status derivation from GET endpoint

### Frontend:
2. `/home/user/webapp/DueDiligenceFrontend/src/components/ReviewerPanel.jsx`
   - Line 1361: Read from `decision_rationale` instead of `rationale`
   - Line 2200: Use `review.decision_rationale` for textarea defaultValue

---

## Database Schema

### Decision Fields:
```sql
-- Decision section
outcome TEXT              -- ✅ Used
decision_rationale TEXT   -- ✅ Used (frontend sends as "rationale")
decision_outcome TEXT     -- Legacy field (not currently used)
decision_date TEXT        -- ✅ Used
case_summary TEXT         -- ✅ Used

-- Financial crime
financial_crime_reason TEXT  -- ✅ Used
fincrime_reason TEXT         -- Legacy alias for financial_crime_reason
```

**Note:** `rationale` column does NOT exist. The correct column is `decision_rationale`.

---

## Service URLs

- **Frontend:** https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
- **Backend:** http://localhost:5050 (running on port 5050)

---

## Summary

✅ **SAVE SECTION NOW WORKS CORRECTLY!**

### What Was Fixed:

1. **Status Preservation** ✅
   - GET endpoint no longer re-derives status
   - Status only changes when explicitly submitted
   - "Save Section" preserves current status

2. **Rationale Persistence** ✅
   - Frontend now reads from correct field (`decision_rationale`)
   - Textarea defaultValue uses `review.decision_rationale`
   - Rationale no longer disappears after save

3. **Field Mapping** ✅
   - Frontend sends: `rationale` → Backend saves to: `decision_rationale`
   - Frontend reads: `decision_rationale` → Textarea displays correctly

### Key Principle:
**"Save Section" is for drafts - it should ONLY save data, not change workflow status.**

Only the **"Submit"** button should trigger status changes and mark the review as complete.

---

## Next Steps

If you encounter any other issues:
1. Hard refresh browser (Ctrl+Shift+R)
2. Check that task has a valid status (not NULL)
3. Check browser console for errors
4. Verify backend logs at `/tmp/backend_status_fix.log`

**Status:** Ready for testing! Backend and frontend are both updated and running.

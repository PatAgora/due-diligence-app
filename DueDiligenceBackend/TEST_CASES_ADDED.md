# Test Cases Added for Bar Chart Visualization

## Summary

**Added:** 6 test cases with completed dates for Monday, Tuesday, and Wednesday this week

**Distribution:** 1 case (Mon), 3 cases (Tue), 2 cases (Wed)

**Purpose:** To populate the "Individual Output (Completed by Day)" bar chart on Reviewer Dashboard

---

## Test Cases Created

### Monday, January 5, 2026: 1 Case
- **CASE-2026012**
  - Customer: Test Customer 2026012
  - Status: Completed
  - Completed: 2026-01-05T10:00:00
  - Outcome: Retain
  - Assigned to: Reviewer (ID: 5)

### Tuesday, January 6, 2026: 3 Cases
- **CASE-2026013**
  - Customer: Test Customer 2026013
  - Status: Completed
  - Completed: 2026-01-06T10:00:00
  - Outcome: Retain
  - Assigned to: Reviewer (ID: 5)

- **CASE-2026014**
  - Customer: Test Customer 2026014
  - Status: Completed
  - Completed: 2026-01-06T10:00:00
  - Outcome: Retain
  - Assigned to: Reviewer (ID: 5)

- **CASE-2026015**
  - Customer: Test Customer 2026015
  - Status: Completed
  - Completed: 2026-01-06T10:00:00
  - Outcome: Retain
  - Assigned to: Reviewer (ID: 5)

### Wednesday, January 7, 2026: 2 Cases
- **CASE-2026016**
  - Customer: Test Customer 2026016
  - Status: Completed
  - Completed: 2026-01-07T10:00:00
  - Outcome: Retain
  - Assigned to: Reviewer (ID: 5)

- **CASE-2026017**
  - Customer: Test Customer 2026017
  - Status: Completed
  - Completed: 2026-01-07T10:00:00
  - Outcome: Retain
  - Assigned to: Reviewer (ID: 5)

---

## Database Details

### Table: `reviews`

### Fields Set:
```sql
case_id             -- CASE-2026012 to CASE-2026017
task_id             -- Same as case_id
status              -- 'Completed'
assigned_to         -- 5 (Reviewer)
completed_by        -- 5 (Reviewer)
date_completed      -- 2026-01-05, 2026-01-06, or 2026-01-07 at 10:00:00
outcome             -- 'Retain'
decision_rationale  -- Test description with day name
updated_at          -- Same as date_completed
date_assigned       -- One day before completion at 09:00:00
customer_name       -- 'Test Customer {case_number}'
case_summary        -- Test description for bar chart testing
```

---

## Expected Bar Chart Display

When viewing the Reviewer Dashboard, the "Individual Output (Completed by Day)" bar chart should show:

```
Bar Chart:
┌─────┐
│     │
│     │  ┌─────┐
│     │  │     │
│     │  │     │  ┌─────┐
│  1  │  │  3  │  │  2  │
└─────┘  └─────┘  └─────┘
 Mon      Tue      Wed
```

### Expected Values:
- **Monday (05/01):** 1 completed case
- **Tuesday (06/01):** 3 completed cases
- **Wednesday (07/01):** 2 completed cases
- **Total WTD (Week to Date):** 6 completed cases

---

## Verification Query

To verify the test data in the database:

```sql
SELECT 
    DATE(date_completed) as completion_date,
    COUNT(*) as count,
    GROUP_CONCAT(task_id) as cases
FROM reviews
WHERE completed_by = 5
  AND date_completed >= '2026-01-05'
  AND date_completed < '2026-01-08'
GROUP BY DATE(date_completed)
ORDER BY date_completed;
```

**Expected Results:**
| completion_date | count | cases |
|----------------|-------|-------|
| 2026-01-05 | 1 | CASE-2026012 |
| 2026-01-06 | 3 | CASE-2026013,CASE-2026014,CASE-2026015 |
| 2026-01-07 | 2 | CASE-2026016,CASE-2026017 |

---

## Testing Steps

1. **Hard refresh browser** (Ctrl+Shift+R)
2. Login as reviewer: `reviewer@scrutinise.co.uk` / `reviewer123`
3. Go to Reviewer Dashboard
4. Find "Individual Output (Completed by Day)" card
5. **Expected:**
   - ✅ Bar chart displays with 3 bars (Mon, Tue, Wed)
   - ✅ Monday bar shows height of 1
   - ✅ Tuesday bar shows height of 3
   - ✅ Wednesday bar shows height of 2
   - ✅ Total WTD count shows 6

### Filter Test:
1. Change date filter to "Week to Date"
2. **Expected:** Chart shows Monday=1, Tuesday=3, Wednesday=2
3. Change date filter to "Previous Week"
4. **Expected:** Chart shows empty or different data
5. Change back to "Week to Date"
6. **Expected:** Chart shows Monday=1, Tuesday=3, Wednesday=2 again

---

## Dashboard Metrics Update

### Completed Count (WTD):
- **Before:** 1 case (CASE-2026011 completed on 2026-01-08)
- **After:** 7 cases (6 new + 1 existing)
- **Note:** The existing CASE-2026011 was completed on Thursday (today), not included in Mon-Wed range

### Individual Output Chart:
- **Before:** Minimal data (possibly flat line)
- **After:** Bar chart with 3 distinct bars showing 1, 3, 2 pattern

---

## Service URL

**Frontend:** https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Summary

✅ **6 test cases created successfully!**

**Distribution:**
- Monday (2026-01-05): 1 case ✅
- Tuesday (2026-01-06): 3 cases ✅
- Wednesday (2026-01-07): 2 cases ✅

**Purpose:** Populate the bar chart with visible data to demonstrate the chart functionality

**Status:** Complete and ready to view! Just refresh the Reviewer Dashboard to see the bar chart with data.

**Case IDs:** CASE-2026012 through CASE-2026017

**All cases:**
- Assigned to: Reviewer (ID: 5)
- Status: Completed
- Outcome: Retain
- Includes proper date_completed, decision_rationale, and case_summary fields

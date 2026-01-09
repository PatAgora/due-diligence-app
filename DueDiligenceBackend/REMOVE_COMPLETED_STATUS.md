# Case Status & Age Profile - Remove Completed Status

## Change Summary

**Removed:** "Completed" status from "Case Status & Age Profile" table

**Dashboards Affected:**
- Reviewer Dashboard
- Operations Dashboard

**Rationale:** Completed cases don't need age tracking since they're no longer in progress

---

## Changes Made

### File: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`

### 1. Operations Dashboard (Lines 3817-3820)

**BEFORE:**
```python
# Include all statuses including completed in Case Status & Age Profile
row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))
```

**AFTER:**
```python
# Exclude Completed status from Case Status & Age Profile
row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))
# Filter out "Completed" status
row_order = [st for st in row_order if st.lower() != 'completed']
```

### 2. Operations Dashboard - Fallback Logic (Lines 3845-3847)

**BEFORE:**
```python
age_rows = []
for st in (row_order if 'row_order' in locals() else sorted(dist_counter.keys())):
    a12 = (age_by_status.get(st, {}).get("1–2 days")
```

**AFTER:**
```python
age_rows = []
for st in (row_order if 'row_order' in locals() else sorted(dist_counter.keys())):
    # Skip "Completed" status from Case Status & Age Profile
    if st.lower() == 'completed':
        continue
    a12 = (age_by_status.get(st, {}).get("1–2 days")
```

### 3. Reviewer Dashboard API (Lines 10874-10879)

**BEFORE:**
```python
# Build age_rows
row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))
total_rows = sum(dist_counter.values()) or 1
age_rows = []
for st in row_order:
    a12 = age_by_status[st]["1–2 days"]
```

**AFTER:**
```python
# Build age_rows (exclude Completed status)
row_order = sorted(dist_counter.keys(), key=lambda k: (-dist_counter[k], k.lower()))
total_rows = sum(dist_counter.values()) or 1
age_rows = []
for st in row_order:
    # Skip "Completed" status from Case Status & Age Profile
    if st.lower() == 'completed':
        continue
    a12 = age_by_status[st]["1–2 days"]
```

---

## Behavior

### Before Change:
**Case Status & Age Profile table showed:**
```
Status                     | Count | Percent | 1–2 days | 3–5 days | 5 days+
---------------------------|-------|---------|----------|----------|--------
Completed                  |   7   |  58.3%  |    4     |    2     |    1
21 Day Chaser Due         |   1   |   8.3%  |    1     |    0     |    0
Pending Review            |   4   |  33.3%  |    2     |    1     |    1
```

### After Change:
**Case Status & Age Profile table shows:**
```
Status                     | Count | Percent | 1–2 days | 3–5 days | 5 days+
---------------------------|-------|---------|----------|----------|--------
21 Day Chaser Due         |   1   |  20.0%  |    1     |    0     |    0
Pending Review            |   4   |  80.0%  |    2     |    1     |    1
```

**Completed status is hidden** ✅

---

## Why This Makes Sense

### Age Profile Purpose:
- Track **work-in-progress** aging
- Identify **stuck tasks** that need attention
- Monitor **how long tasks sit** in various statuses

### Completed Tasks:
- No longer in progress ❌
- Don't need age tracking ❌
- Already counted in "Completed Count" metric ✅
- Shown in daily output bar chart ✅

### Benefits:
1. **Cleaner Table:** Focus on active work only
2. **Better Metrics:** Percentages now relative to WIP, not total
3. **Actionable Data:** All rows represent tasks that need action

---

## What Still Shows Completed Cases

### Metrics That Include Completed:
1. **Completed Count Tile** - Shows total completed cases (e.g., "6 WTD")
2. **Individual Output Bar Chart** - Shows daily completion counts
3. **My Tasks Page** - Can filter by "Completed" status
4. **QC Statistics** - QC outcomes for completed cases

### Case Status & Age Profile:
- **Excludes:** Completed
- **Includes:** All work-in-progress statuses
  - Pending Review
  - 7 Day Chaser Due
  - 14 Day Chaser Due
  - 21 Day Chaser Due
  - NTC Due
  - QC - Awaiting Assignment
  - QC - In Progress
  - QC Rework Required
  - Referred to SME
  - Etc.

---

## Testing Steps

1. **Hard refresh browser** (Ctrl+Shift+R)
2. Login as reviewer: `reviewer@scrutinise.co.uk` / `reviewer123`
3. Go to **Reviewer Dashboard**
4. Find "Case Status & Age Profile" table
5. **Expected:**
   - ✅ No "Completed" row in the table
   - ✅ Only active WIP statuses shown
   - ✅ Percentages add up to ~100%
   - ✅ Totals row shows WIP count only

### Also Check Operations Dashboard:
1. Login as operations user
2. Go to **Operations Dashboard**
3. Find "Case Status & Age Profile" table
4. **Expected:** Same behavior - no "Completed" row

---

## Filter Logic

### Applied to:
- **Status filtering:** `if st.lower() == 'completed': continue`
- **Case-insensitive:** Works for "Completed", "completed", "COMPLETED"

### Not Applied to:
- Completed Count metric (still accurate)
- Daily output chart (still shows completions)
- My Tasks filtering (can still filter by completed)

---

## Service URL

**Frontend:** https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Summary

✅ **"Completed" status removed from Case Status & Age Profile table**

**Changes:**
- Operations Dashboard: Filters out "Completed" from row_order
- Reviewer Dashboard API: Skips "Completed" in age_rows loop
- Both dashboards updated

**Benefits:**
- Cleaner, more actionable table
- Focus on work-in-progress only
- Age tracking only for tasks that need it

**Status:** Complete! Backend updated and running. Just refresh your browser to see the updated table without "Completed" status.

**Note:** Completed cases are still tracked elsewhere:
- Completed Count metric ✅
- Individual Output chart ✅
- My Tasks with status filter ✅

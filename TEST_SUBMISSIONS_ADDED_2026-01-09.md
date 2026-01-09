# ✅ Test Submissions Added - 2026-01-09

## Summary

Successfully added **5 new test submissions** for reviewer1 (ID 33) spread across the week (2026-01-05 to 2026-01-09). All submissions are complete, not selected for QC, and will show up correctly in both the "Cases Submitted" tile and "Individual Output" graph.

---

## 📦 Backup Details

**Repository**: https://github.com/PatAgora/due-diligence-app  
**Branch**: `main`  
**Commit**: `03ecb92`  
**Date**: 2026-01-09

---

## 📊 Submissions Added

| ID  | Task ID           | Customer | Assigned To | Completed By | Date Completed      | DateSenttoQC | Status    | L1 Outcome |
|-----|-------------------|----------|-------------|--------------|---------------------|--------------|-----------|------------|
| 145 | TASK-20260105-145 | CUST3001 | 33          | 33           | 2026-01-05 14:30:00 | 2026-01-05   | Completed | Pass       |
| 146 | TASK-20260106-146 | CUST3002 | 33          | 33           | 2026-01-06 10:15:00 | 2026-01-06   | Completed | Pass       |
| 147 | TASK-20260107-147 | CUST3003 | 33          | 33           | 2026-01-07 16:45:00 | 2026-01-07   | Completed | Pass       |
| 148 | TASK-20260108-148 | CUST3004 | 33          | 33           | 2026-01-08 11:20:00 | 2026-01-08   | Completed | Pass       |
| 149 | TASK-20260109-149 | CUST3005 | 33          | 33           | 2026-01-09 09:30:00 | 2026-01-09   | Completed | Pass       |

---

## 📅 Daily Breakdown

### Week of Monday, January 5, 2026

| Day               | Count | Customers                    |
|-------------------|-------|------------------------------|
| Monday 05 Jan     | 1     | CUST3001                     |
| Tuesday 06 Jan    | 1     | CUST3002                     |
| Wednesday 07 Jan  | 1     | CUST3003                     |
| **Thursday 08 Jan**   | **2**     | **CUST2001, CUST3004** (Note: CUST2001 was existing) |
| Friday 09 Jan     | 1     | CUST3005                     |

**Total Cases Submitted This Week**: **6 cases**

---

## 🎯 Expected Dashboard Results

### Reviewer Dashboard (reviewer1@scrutinise.co.uk)

#### Cases Submitted Tile
- **Before**: 1 case (CUST2001 only)
- **After**: **6 cases** (CUST2001 + 5 new submissions)
- **Filter**: status=completed, date_range=wtd (week-to-date)

#### Individual Output (Completed by Day) Graph
- **Before**: 1 bar (08 Jan with 1 completion)
- **After**: **5 bars** (one for each day with submissions)
  - Mon 05 Jan: 1 completion (CUST3001)
  - Tue 06 Jan: 1 completion (CUST3002)
  - Wed 07 Jan: 1 completion (CUST3003)
  - Thu 08 Jan: **2 completions** (CUST2001, CUST3004)
  - Fri 09 Jan: 1 completion (CUST3005)

---

## 🔍 Data Characteristics

### Complete Submission Requirements
All submissions meet the requirements to show up correctly:

1. **✅ DateSenttoQC Set**
   - Required for "Cases Submitted" tile filter
   - Each submission has DateSenttoQC matching their completion date

2. **✅ completed_by = 33 (reviewer1)**
   - Required for dashboard filtering
   - Both legacy `completed_by` and `l1_completed_by` columns set

3. **✅ Status: Completed**
   - Indicates review is complete
   - Not selected for QC (no qc_assigned_to, no qc_check_date)

4. **✅ date_completed Set**
   - Required for "Individual Output" graph
   - Both `date_completed` and `l1_date_completed` columns set

5. **✅ l1_outcome: Pass**
   - Indicates successful completion
   - Both `outcome` and `l1_outcome` set to "Pass"

---

## 🧪 Testing Instructions

### Test URL
https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

### Test Steps

1. **Login**
   - Email: `reviewer1@scrutinise.co.uk`
   - Password: `Scrutinise2024!`

2. **Navigate to Reviewer Dashboard**
   - Should automatically load for reviewer1

3. **Verify "Cases Submitted" Tile**
   - Should show: **6 cases**
   - Click the tile → Should navigate to My Tasks
   - Should show 6 tasks: CUST2001, CUST3001, CUST3002, CUST3003, CUST3004, CUST3005

4. **Verify "Individual Output" Graph**
   - Should show **5 bars** (one per day)
   - Heights should be:
     - Mon 05 Jan: 1
     - Tue 06 Jan: 1
     - Wed 07 Jan: 1
     - Thu 08 Jan: **2** (tallest bar)
     - Fri 09 Jan: 1

5. **Click on Graph Bars** (if interactive)
   - Each bar should filter to that day's submissions

---

## 📝 Database Changes

### Tables Modified
- `reviews` table

### Columns Populated
- `id` (auto-increment: 145-149)
- `task_id` (generated: TASK-YYYYMMDD-ID)
- `customer_id` (CUST3001-CUST3005)
- `assigned_to` (33)
- `completed_by` (33)
- `l1_assigned_to` (33)
- `l1_completed_by` (33)
- `l1_date_assigned` (same as completion date)
- `status` ("Completed")
- `date_completed` (timestamps spread across week)
- `l1_date_completed` (matching date_completed)
- `DateSenttoQC` (matching completion date)
- `l1_outcome` ("Pass")
- `outcome` ("Pass")
- `updated_at` (current timestamp)
- `review_timestamp` (current timestamp)

---

## 🔄 Rollback Instructions

To remove these test submissions and restore to previous state:

```bash
cd /home/user/webapp
git checkout 5b97f85  # Commit before submissions were added
```

Or to delete just these 5 records:

```python
import sqlite3

conn = sqlite3.connect('scrutinise_workflow.db')
cur = conn.cursor()

# Delete the 5 test submissions
cur.execute("DELETE FROM reviews WHERE id IN (145, 146, 147, 148, 149)")
conn.commit()
print(f"Deleted {cur.rowcount} test submissions")
conn.close()
```

---

## ✅ Verification Checklist

- [x] 5 new submissions created (IDs 145-149)
- [x] All assigned to reviewer1 (ID 33)
- [x] DateSenttoQC set for all submissions
- [x] date_completed set for all submissions
- [x] Status set to "Completed"
- [x] L1 columns populated correctly
- [x] Spread across 5 days of the week
- [x] Total submissions this week: 6 (including existing CUST2001)
- [x] Daily breakdown matches expected
- [x] Database committed successfully
- [x] Full backup created (commit 03ecb92)
- [x] Pushed to GitHub

---

## 📊 Before vs After Comparison

### Before
```
Cases Submitted Tile: 1 case
Individual Output Graph: 
  Thu 08 Jan: █ (1 case)
```

### After
```
Cases Submitted Tile: 6 cases
Individual Output Graph:
  Mon 05 Jan: █ (1 case)
  Tue 06 Jan: █ (1 case)
  Wed 07 Jan: █ (1 case)
  Thu 08 Jan: ██ (2 cases) ← Tallest bar
  Fri 09 Jan: █ (1 case)
```

---

## 🎉 Summary

**Status**: ✅ **COMPLETE**

- ✅ Added 5 new complete submissions
- ✅ All submissions have DateSenttoQC (required for tile)
- ✅ All submissions have date_completed (required for graph)
- ✅ Status set to "Completed" (not selected for QC)
- ✅ Spread across Monday-Friday this week
- ✅ Dashboard should now show 6 cases in tile
- ✅ Graph should show 5 bars across the week
- ✅ Full backup created and pushed to GitHub

**Ready for testing!** 🚀

---

**Created**: 2026-01-09  
**Commit**: 03ecb92  
**Repository**: https://github.com/PatAgora/due-diligence-app

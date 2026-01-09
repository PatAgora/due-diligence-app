# Alerts Over Time Graph - Issue Assessment
**Date:** 2026-01-09  
**Component:** Transaction Review Dashboard - Alerts Over Time Chart  
**Customer Example:** CUST2002  
**Status:** ⚠️ Working but Not Optimal

---

## 🔍 Issue Report

**User Observation:**
> "For Alerts Over Time — CUST2002 for example it shows 1,1,1 but there are 4 alerts?"

**Current Behavior:**
- Graph displays 4 data points
- Each data point shows a value of **1**
- User can see 4 alerts exist but cannot see useful trend information

---

## 📊 Data Analysis

### CUST2002 Alert Details

**Total Alerts:** 4 alerts

| Alert ID | Transaction ID | Transaction Date | Severity | Score |
|----------|----------------|------------------|----------|-------|
| 3879 | TX000020 | 2025-11-11 | HIGH | 92 |
| 3972 | TX000022 | 2025-12-20 | HIGH | 92 |
| 3968 | TX316091 | 2025-12-23 | CRITICAL | 100 |
| 3878 | TX000015 | 2025-12-30 | HIGH | 76 |

**Date Range:**
- First Alert: 2025-11-11
- Last Alert: 2025-12-30
- Duration: 49 days (~1.6 months)

---

## 🎯 Root Cause Analysis

### Current Implementation

**Backend Query** (`/api/transaction/dashboard` - Line 14829-14851):
```sql
SELECT strftime('%Y-%m-%d', t.txn_date) d, COUNT(*) c
FROM alerts a
JOIN transactions t ON t.id = a.txn_id
WHERE t.customer_id = ? AND t.txn_date BETWEEN ? AND ?
GROUP BY d 
ORDER BY d
```

**What This Does:**
1. Groups alerts by **exact transaction date** (day-level)
2. Counts alerts for each specific day
3. Returns one data point per day that has alerts

**Current Output for CUST2002:**
```
Date          Alert Count
2025-11-11    1
2025-12-20    1
2025-12-23    1
2025-12-30    1
```

**Result:**
- 4 separate data points
- Each showing count of 1
- Graph displays: [1, 1, 1, 1]

---

## ❌ Why This Is Not Optimal

### Problem 1: Sparse Data Points
- **Issue:** Each alert falls on a different day
- **Result:** Each gets its own data point showing "1"
- **Impact:** Graph looks like a flat line at y=1 with 4 dots

### Problem 2: No Trend Visibility
- **Issue:** Day-level grouping doesn't show patterns over time
- **Result:** Cannot see if alerts are increasing, decreasing, or stable
- **Impact:** Graph doesn't provide actionable insights

### Problem 3: Scale Issues
- **Issue:** With alerts spread over 49 days, 4 data points are too sparse
- **Result:** Large gaps between data points
- **Impact:** Looks like missing data rather than a meaningful trend

### Problem 4: User Confusion
- **Issue:** User sees "4 alerts" but graph shows multiple "1"s
- **Result:** Appears contradictory or broken
- **Impact:** Loss of confidence in the dashboard

---

## ✅ What Should Happen Instead

### Better Approach: Time Period Aggregation

Instead of grouping by exact date, group by appropriate time periods based on the data range.

#### Option 1: Monthly Grouping
**Query:**
```sql
SELECT strftime('%Y-%m', t.txn_date) as period, COUNT(*) as c
FROM alerts a
JOIN transactions t ON t.id = a.txn_id
WHERE t.customer_id = ?
GROUP BY period 
ORDER BY period
```

**Expected Output for CUST2002:**
```
Month     Alert Count
2025-11   1
2025-12   3
```

**Graph Display:**
- X-axis: Nov 2025, Dec 2025
- Y-axis: 1, 3
- Visual: Clear upward trend from 1 to 3 alerts

#### Option 2: Weekly Grouping
For shorter periods or more granular analysis:
```sql
SELECT strftime('%Y-W%W', t.txn_date) as period, COUNT(*) as c
FROM alerts a
JOIN transactions t ON t.id = a.txn_id
WHERE t.customer_id = ?
GROUP BY period 
ORDER BY period
```

#### Option 3: Dynamic Grouping
Choose grouping based on date range:
- **< 30 days:** Group by week
- **30-365 days:** Group by month  
- **> 365 days:** Group by quarter

---

## 🔧 Technical Details

### Current Code Location
**File:** `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`  
**Function:** `api_transaction_dashboard()`  
**Lines:** 14829-14851

**Query Section:**
```python
# Alerts over time — group by TRANSACTION DATE (t.txn_date)
if start and end:
    aot_sql = """
        SELECT strftime('%Y-%m-%d', t.txn_date) d, COUNT(*) c
        FROM alerts a
        JOIN transactions t ON t.id = a.txn_id
        WHERE t.customer_id = ? AND t.txn_date BETWEEN ? AND ?
        GROUP BY d ORDER BY d
    """
    aot_params = [customer_id, start, end]
else:
    aot_sql = """
        SELECT strftime('%Y-%m-%d', t.txn_date) d, COUNT(*) c
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
```

### Frontend Display
**File:** `/home/user/webapp/DueDiligenceFrontend/src/components/TransactionDashboard.jsx`  
**Lines:** 188-230

**Chart Component:**
```jsx
<Line
  data={{
    labels: data.labels,      // ['2025-11-11', '2025-12-20', '2025-12-23', '2025-12-30']
    datasets: [{
      label: 'Alerts',
      data: data.values,      // [1, 1, 1, 1]
      tension: 0.3,
      borderColor: '#0d6efd',
      backgroundColor: 'rgba(13, 110, 253, 0.1)',
      fill: true
    }]
  }}
  options={{...}}
/>
```

---

## 💡 Recommended Solutions

### Solution 1: Use Monthly Aggregation (Simplest)
**Pros:**
- Easy to implement (change strftime format)
- Works well for most transaction review periods
- Clear trend visibility
- Consistent grouping

**Cons:**
- Less granular than daily
- May hide short-term spikes

**Implementation:**
Change `strftime('%Y-%m-%d', t.txn_date)` to `strftime('%Y-%m', t.txn_date)`

---

### Solution 2: Dynamic Grouping Based on Period (Recommended)
**Pros:**
- Adapts to different date ranges
- Optimal granularity for each period
- Better user experience

**Cons:**
- More complex to implement
- Need to handle different label formats

**Implementation Logic:**
```python
# Calculate date range
if start and end:
    date_diff = (datetime.strptime(end, '%Y-%m-%d') - 
                 datetime.strptime(start, '%Y-%m-%d')).days
    
    if date_diff <= 30:
        # Weekly grouping for short periods
        date_format = '%Y-W%W'
        label_format = 'Week %W, %Y'
    elif date_diff <= 365:
        # Monthly grouping for medium periods
        date_format = '%Y-%m'
        label_format = '%b %Y'
    else:
        # Quarterly grouping for long periods
        date_format = '%Y-Q'  # Custom handling needed
        label_format = 'Q%q %Y'
else:
    # Default to monthly for "all time"
    date_format = '%Y-%m'
    label_format = '%b %Y'
```

---

### Solution 3: Fill Missing Periods (Most User-Friendly)
**Pros:**
- Shows complete time series
- Makes gaps/zero-alert periods visible
- Best for true "over time" visualization

**Cons:**
- Most complex to implement
- Need to generate all time periods in range

**Implementation:**
1. Query alerts grouped by period
2. Generate all periods in the date range
3. Fill missing periods with count = 0
4. Return complete time series

**Example for CUST2002 (monthly):**
```
Month     Alerts
2025-11   1
2025-12   3

Instead of [1, 3], could show:
[1, 3] with labels ['Nov 2025', 'Dec 2025']
```

---

## 📋 Comparison Summary

| Approach | Complexity | User Experience | Trend Visibility | Data Accuracy |
|----------|-----------|-----------------|------------------|---------------|
| **Current (Daily)** | Low | ❌ Poor | ❌ Poor | ✅ Accurate |
| **Monthly** | Low | ✅ Good | ✅ Good | ✅ Accurate |
| **Dynamic** | Medium | ✅ Excellent | ✅ Excellent | ✅ Accurate |
| **Fill Missing** | High | ✅ Excellent | ✅ Excellent | ✅ Accurate |

---

## 🎯 Impact Assessment

### Current State
- ✅ **Technically Correct:** Query returns accurate data
- ✅ **No Errors:** System working as designed
- ❌ **Not Useful:** Graph doesn't provide insights
- ❌ **User Confusion:** Appears broken or contradictory

### After Fix (Monthly Grouping)
- ✅ **Clear Trends:** Users can see alert patterns
- ✅ **Actionable Insights:** Increasing/decreasing alerts visible
- ✅ **Better UX:** Graph makes sense at a glance
- ✅ **Consistent:** Works across different customers

---

## 📊 Example Comparison

### Current Graph for CUST2002
```
Alerts
  2 |
  1 | •      •  • •
  0 |___________________
     11/11  12/20 12/23 12/30
```
**Interpretation:** Four separate incidents, no pattern visible

### Proposed Monthly Graph for CUST2002
```
Alerts
  3 |          ███
  2 |          ███
  1 | ███      ███
  0 |_______________
     Nov 25   Dec 25
```
**Interpretation:** Alert volume tripled from November to December! 📈

---

## 🚀 Recommendation

**Implement Solution 2: Dynamic Grouping**

**Reasoning:**
1. **Optimal for all use cases** - Adapts to short and long periods
2. **Better user experience** - Shows appropriate detail for each timeframe
3. **Clear trends** - Groups provide meaningful patterns
4. **Moderate complexity** - Not too difficult to implement
5. **Future-proof** - Works as more data accumulates

**Implementation Priority:** Medium
- **Impact:** High (better insights, less confusion)
- **Effort:** Medium (requires logic changes in backend)
- **Risk:** Low (doesn't affect other functionality)

**Quick Win Alternative:**
If dynamic grouping is too complex initially, implement **Solution 1 (Monthly)** first:
- **Effort:** Very Low (one-line change)
- **Impact:** Immediate improvement
- **Can upgrade to dynamic later**

---

## 📝 Summary

### The Graph Is Working, But...

**What's Happening:**
- ✅ Query correctly counts 1 alert per day
- ✅ Graph accurately displays the data
- ✅ Shows 4 total alerts exist

**Why It's Confusing:**
- ❌ Day-level grouping creates sparse data points
- ❌ Each point shows "1" even though there are 4 total alerts
- ❌ No visible trend or pattern
- ❌ Looks broken or incomplete to users

**Solution:**
- Change grouping from daily to monthly (or dynamic)
- Group the 4 alerts into 2 time periods: Nov (1) and Dec (3)
- Graph will show clear upward trend
- User will see "4 alerts total" AND "trend increasing"

**Verdict:** ✅ **System is functioning correctly** but needs **better data aggregation** for meaningful insights.

---

**Status:** Assessment Complete - NO CHANGES MADE (as requested)  
**Next Step:** Implement recommended solution (monthly or dynamic grouping)

# Default Date Filter Changed to Week to Date

## Change Summary

**Changed:** Default date range filter from "All Time" to "Week to Date" (WTD)

**Dashboard:** Reviewer Dashboard

**Effect:** When users first load the dashboard, it now shows current week data by default instead of all-time data

---

## Change Made

### File: `/home/user/webapp/DueDiligenceFrontend/src/components/ReviewerDashboard.jsx`

### Line 16:

**BEFORE:**
```javascript
const [dateRange, setDateRange] = useState(searchParams.get('date_range') || 'all');
```

**AFTER:**
```javascript
const [dateRange, setDateRange] = useState(searchParams.get('date_range') || 'wtd');
```

---

## Behavior

### Before Change:
1. User navigates to Reviewer Dashboard
2. **Default filter:** "All Time"
3. Shows all-time metrics and data
4. User must manually change to "Week to Date" to see current week

### After Change:
1. User navigates to Reviewer Dashboard
2. **Default filter:** "Week to Date" (WTD) ✅
3. Shows current week metrics and data
4. User can change to other filters if needed

---

## Date Range Options

The filter dropdown still includes all options:
- **Week to Date (WTD)** ← Now the default ✅
- Previous Week
- 30 Days
- All Time

**Users can still:**
- Select any date range from the dropdown
- View all-time data by selecting "All Time"
- Switch between different time periods

---

## Affected Metrics

When set to "Week to Date", the dashboard shows:

### Metrics Filtered:
1. **Completed Count** - Cases completed this week (Mon-Today)
2. **Individual Output Bar Chart** - Daily completions this week
3. **QC Statistics** - QC checks performed this week
   - QC Sample count
   - QC Pass/Fail counts
   - QC Pass percentage

### Metrics NOT Filtered (Always Live):
1. **Active WIP** - Current work in progress (live count)
2. **Case Status & Age Profile** - Current status distribution (live)
3. **Rework Age Profile** - Current rework tasks (live)
4. **Chaser Cycle (Current Week)** - Always current week by definition

---

## Why This Makes Sense

### Week to Date is More Relevant:
- **Current performance** - Shows what's happening now
- **Actionable data** - Focus on this week's work
- **Better context** - Aligns with weekly work patterns
- **Less overwhelming** - Manageable time frame

### All Time Can Be Confusing:
- **Too broad** - Years of historical data
- **Less actionable** - Can't change the past
- **Harder to interpret** - Mixed with old data

### Benefits:
1. **Better UX:** Users see relevant data immediately
2. **Consistent with Work Patterns:** Most teams work in weekly cycles
3. **Still Flexible:** Can change to any date range needed
4. **Matches Chaser Table:** Chaser Cycle already shows current week

---

## Testing Steps

1. **Hard refresh browser** (Ctrl+Shift+R)
2. Login as reviewer: `reviewer@scrutinise.co.uk` / `reviewer123`
3. Navigate to **Reviewer Dashboard**
4. **Expected:**
   - ✅ Date filter dropdown shows "Week to Date" selected
   - ✅ Completed Count shows current week total (e.g., "6 WTD")
   - ✅ Individual Output chart shows Mon-Fri of current week
   - ✅ QC Stats show current week numbers

### Test Other Filters:
1. Change filter to "All Time"
2. **Expected:** Numbers change to show all-time totals
3. Change back to "Week to Date"
4. **Expected:** Returns to current week data

---

## URL Parameter

The date range is also stored in the URL parameter:
- Default URL: `/reviewer_dashboard` → Uses WTD
- With parameter: `/reviewer_dashboard?date_range=all` → Uses All Time
- With parameter: `/reviewer_dashboard?date_range=wtd` → Uses WTD (explicit)

**If URL has `date_range` parameter, it takes precedence over the default.**

---

## Edge Cases

### Case 1: User Bookmarked Old URL
- **Old bookmark:** `/reviewer_dashboard?date_range=all`
- **Behavior:** Opens with "All Time" (respects URL parameter) ✅

### Case 2: User Navigates from Menu
- **New navigation:** `/reviewer_dashboard` (no parameter)
- **Behavior:** Opens with "Week to Date" (new default) ✅

### Case 3: User Changes Filter
- **Action:** User selects "30 Days"
- **Behavior:** URL updates to `?date_range=30d`, shows 30-day data ✅
- **Refresh:** Stays on 30 Days (URL parameter persists) ✅

---

## Rollback Instructions

If you need to revert to "All Time" as default:

```javascript
// Change line 16 back to:
const [dateRange, setDateRange] = useState(searchParams.get('date_range') || 'all');
```

---

## Service URL

**Frontend:** https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Summary

✅ **Default date filter changed to "Week to Date"**

**Change:**
- Line 16 of ReviewerDashboard.jsx
- Default: 'all' → 'wtd'

**Benefits:**
- More relevant data shown by default
- Aligns with weekly work cycles
- Better user experience
- Still flexible (all options available)

**Status:** Complete! Just refresh your browser and the dashboard will default to "Week to Date" instead of "All Time".

**Note:** Users can still select "All Time" or any other date range from the dropdown. The default just makes the most common use case (viewing current week) one click easier.

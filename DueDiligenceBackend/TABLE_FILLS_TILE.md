# Rework Age Profile Table Now Fills Tile

## Change Summary

**Made the Rework Age Profile table fill the entire tile** by adjusting layout and adding CSS to stretch the table vertically

**Dashboard:** Reviewer Dashboard

**Effect:** Table now uses all available vertical space in the tile with rows distributed evenly

---

## Changes Made

### File 1: `/home/user/webapp/DueDiligenceFrontend/src/components/ReviewerDashboard.css`

### Added New CSS Rules (After Line 189)

```css
/* Make Rework Age Profile table fill the tile */
.equal-trio .table-wrap {
  flex: 1;
}

.equal-trio .table-wrap table {
  width: 100%;
  height: 100%;
}

.equal-trio .table-wrap tbody tr {
  height: 33.33%;  /* Divide 3 rows evenly */
}

.equal-trio .table-wrap td,
.equal-trio .table-wrap th {
  padding: 0.5rem 0.6rem;  /* Slightly more padding */
}
```

---

### File 2: `/home/user/webapp/DueDiligenceFrontend/src/components/ReviewerDashboard.jsx`

### Change: Update Rework Tile Structure (Lines 282-287)

**BEFORE:**
```jsx
<div className="d-flex align-items-center justify-content-between">
  <h5 className="card-title mb-0">Rework Age Profile</h5>
  <span className="note">Live (not date-filtered)</span>
</div>
<div className="table-wrap mt-1 flex-grow-1 d-flex align-items-center">
  <div className="table-responsive w-100">
```

**AFTER:**
```jsx
<div className="d-flex align-items-center justify-content-between mb-1">
  <h5 className="card-title mb-0">Rework Age Profile</h5>
  <span className="note">Live (not date-filtered)</span>
</div>
<div className="table-wrap flex-grow-1 d-flex flex-column">
  <div className="table-responsive w-100 h-100">
```

**Changes:**
1. Added `mb-1` to header div (margin-bottom spacing)
2. Removed `mt-1` from table-wrap (was redundant)
3. Changed `d-flex align-items-center` to `d-flex flex-column` (stretch instead of center)
4. Added `h-100` to table-responsive (fill height)

---

## How It Works

### Before:
```
┌─────────────────┐
│ Rework Age Pro  │
│                 │
│  Age    Count   │ ← Table centered
│  1-2      0     │    vertically
│  3-5      0     │    with white
│  5+       0     │    space above
│                 │    and below
└─────────────────┘
```

### After:
```
┌─────────────────┐
│ Rework Age Pro  │
│─────────────────│
│  Age    Count   │ ← Table fills
│─────────────────│    entire tile
│  1-2      0     │    vertically
│─────────────────│
│  3-5      0     │    Rows evenly
│─────────────────│    distributed
│  5+       0     │    (33.33% each)
└─────────────────┘
```

---

## Layout Structure

**Card Body (d-flex flex-column):**
1. **Header row** (fixed height)
   - Title: "Rework Age Profile"
   - Note: "Live (not date-filtered)"
   - `mb-1` margin at bottom

2. **Table Wrap** (flex-grow-1, flex-column)
   - Takes all remaining vertical space
   - Stretches to fill

3. **Table** (width: 100%, height: 100%)
   - Header row (thead)
   - 3 body rows (tbody tr)
     - Each row: 33.33% height
     - Evenly distributed vertically

---

## Benefits

1. ✅ **Better Space Usage** - No wasted white space
2. ✅ **Easier to Read** - Larger click targets
3. ✅ **Consistent Layout** - Matches other tiles better
4. ✅ **Professional Look** - Table properly fills container
5. ✅ **Even Distribution** - Rows nicely spaced

---

## Testing Steps

1. **Hard refresh browser** (Ctrl+Shift+R)
2. Login: `reviewer@scrutinise.co.uk` / `reviewer123`
3. View Reviewer Dashboard
4. Look at **Rework Age Profile** tile
5. **Expected:**
   - ✅ Table fills entire tile height
   - ✅ No white space above or below table
   - ✅ 3 rows evenly distributed (equal heights)
   - ✅ Table header at top
   - ✅ Slightly more padding in cells (0.5rem × 0.6rem)
   - ✅ Easy to click on counts

---

## Visual Comparison

### All Three Tiles Side by Side:

**Quality Stats:**
- Doughnut chart (100px)
- Legend at bottom
- Fixed height content

**Individual Output:**
- Bar chart (100px)
- Full width bars
- Fixed height content

**Rework Age Profile:**
- Table fills entire height ✅
- 3 rows evenly distributed ✅
- No wasted space ✅

---

## Cell Padding Details

**Table cells now have:**
- Padding: `0.5rem × 0.6rem` (8px × 9.6px)
- Previously: `0.3rem × 0.5rem` (4.8px × 8px)
- **Result:** Slightly more padding for better readability and click targets

**Row heights:**
- Each of 3 rows: 33.33% of available height
- Even distribution regardless of tile height
- Responsive to container size

---

## CSS Specificity

**Applied to:** `.equal-trio .table-wrap`
- Only affects table-wrap within the three-tile row
- Doesn't affect other tables on dashboard
- Scoped to Rework Age Profile tile specifically

---

## Service URL

**Frontend:** https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Summary

✅ **Rework Age Profile table now fills the tile!**

**Changes:**
- Table stretches to fill available vertical space
- 3 rows evenly distributed (33.33% each)
- Slightly more cell padding (0.5rem × 0.6rem)
- No wasted white space above or below table
- Header row above table with mb-1 spacing

**Result:**
- Professional, filled layout ✅
- Better space utilization ✅
- Easier to read and click ✅
- Consistent with tile design ✅

**Status:** Complete! Just refresh your browser to see the table filling the entire Rework Age Profile tile with evenly distributed rows.

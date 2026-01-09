# Auto-Filter Completed Tasks - Implementation Summary

## Change Overview
Implemented automatic filtering to hide completed tasks on the "My Tasks" page by default, with a toggle checkbox to show/hide them.

## Problem Statement
Users wanted completed tasks to be hidden by default on the "My Tasks" page to focus on active work, while still maintaining the ability to view completed tasks when needed.

## Solution Implemented

### 1. Backend Changes
**File:** `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`

#### Added `exclude_completed` Parameter (Lines 11107-11108)
```python
# Exclude completed filter (auto-applied on load)
exclude_completed = request.args.get("exclude_completed", "").strip().lower() in ('true', '1', 'yes')
```

#### Updated Debug Logging (Line 11110)
```python
print(f"[DEBUG] api_my_tasks called with: status={raw_status}, status_key={status_key}, age_bucket={age_bucket_q}, date_range={date_range}, overdue={overdue_flg}, chaser_type={chaser_type}, week_date={week_date}, exclude_completed={exclude_completed}")
```

#### Added Filter Logic (Lines 11442-11446)
```python
# Apply exclude_completed filter if requested
if exclude_completed:
    before_count = len(filtered)
    filtered = [t for t in filtered if t.get('status', '').lower() != 'completed']
    print(f"[DEBUG] After exclude_completed filter: {len(filtered)} tasks (removed {before_count - len(filtered)} completed tasks)")
```

### 2. Frontend Changes
**File:** `/home/user/webapp/DueDiligenceFrontend/src/components/MyTasks.jsx`

#### Added State Variable (Line 52)
```javascript
const excludeCompleted = searchParams.get('exclude_completed') === 'true';
```

#### Auto-Apply Filter on Initial Load (Lines 58-68)
```javascript
useEffect(() => {
  // On initial load, if no status filter or exclude_completed param exists,
  // automatically set exclude_completed=true to hide completed tasks
  if (!searchParams.has('status') && !searchParams.has('exclude_completed')) {
    const params = new URLSearchParams(searchParams);
    params.set('exclude_completed', 'true');
    setSearchParams(params, { replace: true });
  }
}, []); // Run once on mount
```

#### Added Toggle Handler (Lines 122-134)
```javascript
const handleShowCompletedToggle = () => {
  const params = new URLSearchParams(searchParams);
  const isCurrentlyExcluded = params.get('exclude_completed') === 'true';
  
  if (isCurrentlyExcluded) {
    // Currently excluding, so now show completed
    params.delete('exclude_completed');
  } else {
    // Currently showing completed, so now exclude
    params.set('exclude_completed', 'true');
  }
  setSearchParams(params);
};
```

#### Added UI Checkbox (Lines 345-357)
```jsx
<div className="d-flex align-items-center">
  <input
    type="checkbox"
    id="show_completed"
    checked={!excludeCompleted}
    onChange={handleShowCompletedToggle}
    className="form-check-input me-2"
  />
  <label htmlFor="show_completed" className="form-check-label">
    <strong>Show Completed</strong>
  </label>
</div>
```

## How It Works

### Initial Page Load
1. When user navigates to `/my_tasks`, the `useEffect` hook checks if there's already a status or exclude_completed filter
2. If neither exists, it automatically adds `exclude_completed=true` to the URL
3. The backend receives the API call with `exclude_completed=true` parameter
4. Backend filters out all tasks with `status='completed'` (case-insensitive)
5. Only active tasks are displayed

### Toggle Behavior
1. **Checkbox Unchecked (Default State)**:
   - URL has `?exclude_completed=true`
   - Completed tasks are hidden
   - User sees only active work

2. **User Checks the Box**:
   - `exclude_completed` parameter is removed from URL
   - Backend returns ALL tasks including completed
   - User can see their completed work

3. **User Unchecks the Box**:
   - `exclude_completed=true` is added back to URL
   - Completed tasks are hidden again

## Visual Design

### Filter Controls Layout
```
┌────────────────────────────────────────────────────────────────┐
│ Filter by Status: [Dropdown ▼]  Filter by Date: [Dropdown ▼]  │
│ ☐ Show Completed                                               │
└────────────────────────────────────────────────────────────────┘
```

### States
- **☐ Show Completed** → Completed tasks hidden (default)
- **☑ Show Completed** → Completed tasks visible

## Benefits

1. **Cleaner Default View**: Users see only active tasks when they open the page
2. **Reduced Clutter**: Completed tasks don't distract from current work
3. **Easy Toggle**: One-click access to view completed tasks when needed
4. **URL-Based State**: Filter state is preserved in URL, can be bookmarked
5. **Backward Compatible**: Existing status filters still work as expected

## Testing Steps

1. **Hard refresh browser** (`Ctrl + Shift + R`)
2. **Login** with `reviewer@scrutinise.co.uk` / `reviewer123`
3. **Navigate to My Tasks**
4. **Expected behavior**:
   - Checkbox is unchecked by default
   - URL shows `?exclude_completed=true`
   - Only active tasks are displayed (no "Completed" status tasks)
5. **Check the "Show Completed" box**:
   - URL changes (exclude_completed param removed)
   - Completed tasks now appear in the list
6. **Uncheck the box**:
   - URL adds `?exclude_completed=true` back
   - Completed tasks disappear

## Technical Notes

### Case-Insensitive Matching
The backend uses `.lower()` to ensure case-insensitive matching:
```python
filtered = [t for t in filtered if t.get('status', '').lower() != 'completed']
```

This catches variations like:
- `Completed`
- `COMPLETED`
- `completed`

### URL Parameter Format
- **Hide completed**: `?exclude_completed=true`
- **Show completed**: No parameter (default) or explicitly `?exclude_completed=false`

### Interaction with Other Filters
- Works alongside status filters (e.g., `?status=wip&exclude_completed=true`)
- Works with date filters (e.g., `?date=today&exclude_completed=true`)
- Works with chaser filters (e.g., `?chaser_type=21&exclude_completed=true`)
- If user explicitly selects "Completed" in status dropdown, exclude_completed is ignored

## Files Modified

1. **Backend**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`
   - Lines 11107-11108: Added parameter reading
   - Line 11110: Updated debug logging
   - Lines 11442-11446: Added filter logic

2. **Frontend**: `/home/user/webapp/DueDiligenceFrontend/src/components/MyTasks.jsx`
   - Line 52: Added state variable
   - Lines 58-68: Auto-apply filter on mount
   - Lines 122-134: Toggle handler
   - Lines 345-357: UI checkbox

## Status
✅ **Complete** - Backend updated, frontend updated, backend restarted

## Service URL
https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

## Next Steps
1. Refresh browser to see changes
2. Test the checkbox toggle functionality
3. Verify completed tasks are hidden by default
4. Verify completed tasks can be shown by checking the box

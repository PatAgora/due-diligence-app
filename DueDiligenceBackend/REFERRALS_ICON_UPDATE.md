# My Referrals Icon Update

## Change Overview
Updated the "My Referrals" navigation link icon to be unique and more representative of referrals.

## Problem
The "My Referrals" link in the navbar was using the same generic `bi-clipboard-list` icon as other navigation items, making it less distinguishable.

## Solution
Changed the icon from `bi-clipboard-list` to `bi-arrow-left-right` to better represent the back-and-forth nature of referrals.

## Icon Comparison

### Before
```jsx
<i className="bi bi-clipboard-list"></i> My Referrals
```
- Generic clipboard icon
- Same as other list-based navigation items

### After
```jsx
<i className="bi bi-arrow-left-right"></i> My Referrals
```
- Unique double-arrow icon (⟷)
- Represents the exchange/referral flow
- Visually distinct from other navigation icons

## Icon Meaning
The `bi-arrow-left-right` icon (⟷) symbolizes:
- **Back-and-forth exchange** - referrals being sent and received
- **Bidirectional flow** - cases moving between reviewers and SMEs
- **Transfer** - the act of referring cases to others

## Current Icon Usage in Navbar
- `bi-speedometer2` - Dashboard
- `bi-list-check` - My Tasks
- `bi-arrow-left-right` - **My Referrals** ✨ (NEW)
- `bi-clipboard-check` - QC Sampling
- `bi-people` - Bulk Assign
- `bi-calendar3` - Planning
- `bi-shield-check` - Admin/QC
- `bi-eye` - View options
- `bi-gear` - Settings

## File Modified
**File**: `/home/user/webapp/DueDiligenceFrontend/src/components/BaseLayout.jsx`
- **Line 208**: Changed icon class from `bi-clipboard-list` to `bi-arrow-left-right`

## Visual Result
The "My Referrals" link now displays with a unique double-arrow icon (⟷) that clearly differentiates it from other navigation items and better represents its purpose.

## Testing Steps
1. **Hard refresh** (`Ctrl + Shift + R`)
2. **Login** as a reviewer
3. **Check the sidebar navigation**
4. **Expected**: "My Referrals" should show a double-arrow icon (⟷)

## Service URL
https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

## Status
✅ **Complete** - Icon updated in BaseLayout.jsx

## Design Notes
- The icon is part of Bootstrap Icons library (already included)
- Consistent sizing and styling with other nav icons
- No additional CSS changes needed
- Icon loads instantly (no external dependencies)

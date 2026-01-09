# Identity Verification - TEMPORARY REMOVAL

## ⚠️ IMPORTANT: TO BE RE-ADDED IN THE FUTURE

This feature was temporarily removed on **2026-01-08** and **WILL NEED TO BE ADDED BACK** at a later date.

---

## Change Overview
Temporarily removed the "Identity Verification" navigation link from the sidebar.

## Removal Details

### What Was Removed
**Navigation Link**: "Identity Verification" (with ID card icon 🪪)

**Location**: Sidebar navigation on task view pages

**Visibility**: Only appeared when viewing individual tasks (both reviewer and QC views)

### Original Code (SAVED FOR FUTURE RESTORATION)

**File**: `/home/user/webapp/DueDiligenceFrontend/src/components/BaseLayout.jsx`

**Lines 416-426 (Original)**:
```jsx
{/* Sumsub Identity Verification - direct link (not dropdown) - only on task view pages - independent of Transaction Review */}
{isTaskViewPage && taskId && (
  <Link
    to={location.pathname.startsWith('/qc_review/') 
      ? `/qc_review/${taskId}/sumsub`
      : `/view_task/${taskId}/sumsub`}
    className={`nav-link ${isActive('/sumsub') ? 'active' : ''}`}
  >
    <i className="fas fa-id-card"></i> Identity Verification
  </Link>
)}
```

### Current Code (Commented Out)
```jsx
{/* Sumsub Identity Verification - TEMPORARILY REMOVED (to be re-added later) */}
{/* Removed on 2026-01-08 - will need to add back in the future */}
{/* Original code (lines 417-426):
{isTaskViewPage && taskId && (
  <Link
    to={location.pathname.startsWith('/qc_review/') 
      ? `/qc_review/${taskId}/sumsub`
      : `/view_task/${taskId}/sumsub`}
    className={`nav-link ${isActive('/sumsub') ? 'active' : ''}`}
  >
    <i className="fas fa-id-card"></i> Identity Verification
  </Link>
)}
*/}
```

---

## Feature Details

### What This Feature Does
- **Integration**: Connects to Sumsub identity verification service
- **Purpose**: Allows reviewers to verify customer identity during due diligence
- **Access**: Only visible on task view pages (when reviewing individual cases)
- **Routes**:
  - Reviewer view: `/view_task/${taskId}/sumsub`
  - QC view: `/qc_review/${taskId}/sumsub`

### Icon Used
- **Font Awesome**: `fa-id-card` (🪪)
- **Represents**: Identity card/verification

### When It Appeared
- **Condition**: `isTaskViewPage && taskId`
- **Pages**: Only on individual task review pages
- **Users**: Reviewers and QC staff viewing tasks

---

## What Still Exists (NOT Removed)

The navigation link was removed, but the underlying feature components likely still exist:

1. **Route**: The `/sumsub` route may still be defined in `App.jsx`
2. **Component**: `SumsubVerification.jsx` component probably still exists
3. **Functionality**: Backend endpoints for Sumsub integration probably still active
4. **Direct Access**: Users could potentially access via direct URL

**Note**: Only the navigation link was removed, not the entire feature.

---

## How to Re-Add in the Future

### Step 1: Locate the Code
Go to `/home/user/webapp/DueDiligenceFrontend/src/components/BaseLayout.jsx`

### Step 2: Find the Comment Section
Search for: `"Identity Verification - TEMPORARILY REMOVED"`

Around line 416-429 (may shift with other changes)

### Step 3: Uncomment the Code
Replace the commented-out section with:
```jsx
{/* Sumsub Identity Verification - direct link (not dropdown) - only on task view pages - independent of Transaction Review */}
{isTaskViewPage && taskId && (
  <Link
    to={location.pathname.startsWith('/qc_review/') 
      ? `/qc_review/${taskId}/sumsub`
      : `/view_task/${taskId}/sumsub`}
    className={`nav-link ${isActive('/sumsub') ? 'active' : ''}`}
  >
    <i className="fas fa-id-card"></i> Identity Verification
  </Link>
)}
```

### Step 4: Test
1. Hard refresh browser
2. Open a task view page
3. Check sidebar for "Identity Verification" link
4. Click link to verify it navigates correctly
5. Test in both reviewer and QC views

---

## Alternative: Keep Hidden but Add Toggle

If you want to enable/disable without code changes, consider:

### Option 1: Module Settings
Add to module settings:
```jsx
{isModuleEnabled('identity_verification') && isTaskViewPage && taskId && (
  <Link to={...}>
    <i className="fas fa-id-card"></i> Identity Verification
  </Link>
)}
```

### Option 2: Permission-Based
Use permissions system:
```jsx
{canView('identity_verification') && isTaskViewPage && taskId && (
  <Link to={...}>
    <i className="fas fa-id-card"></i> Identity Verification
  </Link>
)}
```

---

## Files Modified

**File**: `/home/user/webapp/DueDiligenceFrontend/src/components/BaseLayout.jsx`
- **Lines 416-429**: Commented out Identity Verification link
- **Change**: Active link → Commented code with restoration notes

---

## Visual Changes

### Before (Sidebar on Task View Page)
```
✅ Dashboard
✅ My Tasks
✅ Screening
✅ Outreach
✅ Decision
✅ Identity Verification 🪪
✅ Transaction Review
```

### After (Sidebar on Task View Page)
```
✅ Dashboard
✅ My Tasks
✅ Screening
✅ Outreach
✅ Decision
❌ Identity Verification (REMOVED)
✅ Transaction Review
```

---

## Testing Steps

1. **Hard refresh** (`Ctrl + Shift + R`)
2. **Login** as a reviewer
3. **Open any task** (e.g., CASE-2026010)
4. **Check sidebar**
5. **Expected**: No "Identity Verification" link visible

---

## Related Components to Check When Re-Adding

When re-adding this feature, verify these components are still functional:

1. **SumsubVerification.jsx** - Main component
2. **SumsubVerification.css** - Styling
3. **App.jsx** - Route definitions
4. **Backend** - Sumsub API endpoints
5. **Permissions** - Access control settings

---

## Reason for Removal
Temporarily removed from navigation at user request. Feature will be needed again in the future.

---

## Restoration Checklist

When ready to re-add:
- [ ] Uncomment code in BaseLayout.jsx
- [ ] Test navigation link appears
- [ ] Test route navigation works
- [ ] Verify Sumsub component loads
- [ ] Check permissions/access control
- [ ] Test in reviewer view
- [ ] Test in QC view
- [ ] Verify icon displays correctly
- [ ] Update this documentation

---

## Service URL
https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Status
✅ **Temporarily Removed** - Navigation link hidden, code preserved for future restoration

**Removal Date**: 2026-01-08  
**To Be Restored**: Future date (TBD)

---

## Important Notes
1. ⚠️ **Code is preserved** - Not deleted, just commented out
2. ⚠️ **Easy restoration** - Uncomment code to restore
3. ⚠️ **Feature may still work** - Direct URL access might still work
4. ⚠️ **Remember to restore** - This is temporary, not permanent removal

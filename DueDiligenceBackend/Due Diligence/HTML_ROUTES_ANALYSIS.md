# Analysis of HTML-Returning Routes in app.py

## Summary
This document analyzes all routes in `app.py` that return HTML via `render_template()` to determine if they can be safely removed now that the React frontend is in use.

## Routes That CAN Be Safely Removed (React Frontend Has Replacements)

### 1. Dashboard Routes (React Components Exist)
- `/reviewer_dashboard` → React: `/reviewer_dashboard` (ReviewerDashboard.jsx)
- `/qc_lead_dashboard` → React: `/qc_lead_dashboard` (QCLeadDashboard.jsx)
- `/qc_dashboard` → React: `/qc_dashboard` (QCDashboard.jsx)
- `/team_leader_dashboard` → React: `/team_leader_dashboard` (TeamLeaderDashboard.jsx)
- `/qa_dashboard` → React: `/qa_dashboard` (QADashboard.jsx)
- `/sme_dashboard` → React: `/sme_dashboard` (SMEDashboard.jsx)
- `/operations_dashboard` → React: `/operations_dashboard` (OperationsDashboard.jsx)

### 2. Task Management Routes
- `/my_tasks` → React: `/my_tasks` (MyTasks.jsx)
- `/reviewer_panel/<task_id>` → React: `/reviewer_panel/:taskId` (ReviewerPanel.jsx)
- `/view_task/<task_id>` → React: `/view_task/:taskId` (ReviewerPanel.jsx)
- `/review/<task_id>` → React: `/reviewer_panel/:taskId` (ReviewerPanel.jsx)
- `/assign_tasks` → React: `/assign_tasks` (AssignTasks.jsx)
- `/assign_tasks_bulk` → React: `/assign_tasks_bulk` (BulkAssignTasks.jsx)
- `/reassign_tasks` → React: Not in React, but has API endpoint

### 3. QC Routes
- `/qc_assign_tasks` → React: `/qc_assign_tasks` (QCAssignTasks.jsx)
- `/qc_assign_tasks_bulk` → React: `/qc_assign_tasks_bulk` (QCBulkAssignTasks.jsx)
- `/qc_reassign_tasks` → React: `/qc_reassign_tasks` (QCReassignTasks.jsx)
- `/qc_wip_cases` → React: `/qc_wip_cases` (QCWIPCases.jsx)
- `/qc_review/<task_id>` → React: `/qc_review/:taskId` (QCReviewPanel.jsx)
- `/qc_status_dashboard` → No React equivalent found, but has API endpoint
- `/qc_allocation` → No React equivalent found
- `/qcqa_review/<task_id>` → No React equivalent found

### 4. Admin Routes
- `/admin/users` → React: `/admin/users` (AdminUserList.jsx)
- `/admin/invite_user` → React: `/admin/invite-user` (AdminInviteUser.jsx)
- `/admin/create_user` → React: `/admin/users` (handled by AdminUserList)
- `/admin/edit_user/<user_id>` → React: `/admin/edit-user/:userId` (EditUser.jsx)
- `/admin/settings` → React: `/admin/settings` (AdminSettings.jsx)
- `/admin/permissions` → React: `/admin/permissions` (AdminPermissions.jsx)
- `/admin/field_visibility` → React: `/admin/field-visibility` (AdminFieldVisibility.jsx)
- `/admin/team_structure` → React: `/admin/team-structure` (AdminTeamStructure.jsx)
- `/admin/sampling_rates` → React: `/qc/sampling-rates` (SamplingRatesConfig.jsx)
- `/admin/login_audit` → No React equivalent found

### 5. SME Routes
- `/sme_review/<task_id>` → React: `/sme_review/:taskId` (SMEReview.jsx)
- `/sme_queue` → React: `/sme_referrals` (SMEReferrals.jsx)
- `/submit_sme_advice/<task_id>` → API endpoint exists

### 6. Operations Routes
- `/ops/mi` → React: `/operations_dashboard` (OperationsDashboard.jsx)
- `/ops/mi/cases` → React: `/ops/mi/cases` (OperationsCases.jsx)
- `/ops/mi/planning` → React: `/ops/mi/planning` (OperationsPlanning.jsx)

### 7. Search
- `/search` → React: `/search` (SearchResults.jsx)

### 8. Other Routes
- `/completed_cases` → No React equivalent found
- `/tl/cases` → No React equivalent found
- `/export_case_summary/<task_id>` → Export endpoint, should keep
- `/export_team_stats/<int:days>/<lead_name>` → Export endpoint, should keep
- `/export_accreditation_log/<int:level>` → Export endpoint, should keep

## Routes That SHOULD BE KEPT (Still Needed)

### 1. Authentication Routes (Handle Both JSON and HTML)
- `/login` - Returns HTML for GET, JSON for POST (React uses JSON)
- `/verify_2fa` - Returns HTML for GET, JSON for POST (React uses JSON)
- `/forgot_password` - May still need HTML for email links
- `/reset_password/<token>` - Email links need HTML
- `/reset_email_sent` - Email confirmation page
- `/reset_done` - Success page
- `/reset_problem` - Error page
- `/logout` - Redirects, should keep

### 2. Error Pages
- `/404` or 404 handler - Returns `404.html`
- CSRF error handler - Returns `csrf_error.html`

### 3. Export/Download Routes (Not HTML, but file downloads)
- All `/export_*` routes
- `/ops/mi/download`
- `/ops/mi/export_excel`

### 4. API Routes (Already JSON, not HTML)
- All `/api/*` routes return JSON, not HTML

## Routes That NEED INVESTIGATION

### 1. Routes with No Clear React Equivalent
- `/qc_accreditation` - Has React component? Check if used
- `/qc_status_dashboard` - Has API endpoint `/api/qc_status_dashboard`?
- `/qc_allocation` - Check if still used
- `/qcqa_review/<task_id>` - Check if still used
- `/admin/login_audit` - May need for compliance
- `/completed_cases` - Check if still used
- `/tl/cases` - Check if still used

### 2. Routes That May Have Partial Functionality
- `/sme_review/<task_id>` - Has both HTML and API endpoint
- `/submit_review/<task_id>/<int:level>` - POST endpoint, check if HTML needed
- `/submit_qc_decision/<task_id>/<int:level>` - POST endpoint, check if HTML needed

## Recommendations

### SAFE TO REMOVE (High Confidence)
1. All dashboard routes that have React equivalents
2. All task management routes that have React equivalents
3. All admin routes that have React equivalents
4. All QC routes that have React equivalents
5. All operations routes that have React equivalents
6. `/search` HTML route (React has replacement)

### KEEP (Required)
1. Authentication routes (login, verify_2fa) - but can remove HTML returns, keep JSON
2. Password reset routes - needed for email links
3. Error pages (404, CSRF error)
4. Export/download routes
5. All `/api/*` routes (already JSON)

### INVESTIGATE BEFORE REMOVING
1. Routes with no clear React equivalent
2. Routes that may be accessed via direct links or bookmarks
3. Routes used by email notifications or external systems

## Implementation Strategy

1. **Phase 1**: Remove HTML returns from routes that have confirmed React equivalents
2. **Phase 2**: Convert authentication routes to JSON-only (remove HTML fallback)
3. **Phase 3**: Investigate and handle routes with no React equivalent
4. **Phase 4**: Remove unused template files

## Notes

- The React frontend uses API endpoints (JSON) for all data operations
- HTML routes are only needed for:
  - Initial page loads (handled by React Router)
  - Email links (password reset, etc.)
  - Error pages
  - Legacy bookmarks/direct links (should redirect to React)


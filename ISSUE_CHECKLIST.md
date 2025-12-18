# Issue Tracking Checklist - Due Diligence Application

**Last Updated**: December 18, 2025  
**Total Issues**: 20  
**Critical**: 4 | **High**: 6 | **Medium**: 10

---

## 🔴 CRITICAL PRIORITY (Must Fix This Week)

### Issue #1: SME Dashboard - Missing Matrix Table
- **File**: `/DueDiligenceFrontend/src/components/SMEDashboard.jsx`
- **Line**: 188
- **Problem**: Placeholder text "Matrix table would go here"
- **Impact**: SME users cannot see case age profile breakdown
- **Estimated Effort**: 6 hours
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 1)

**Acceptance Criteria:**
- [ ] Matrix table displays status rows
- [ ] Age buckets (0-2, 3-5, 5+ days) shown
- [ ] Data fetched from backend API
- [ ] Table responsive on mobile
- [ ] Empty state handled gracefully

---

### Issue #2: QA Dashboard - Minimal Implementation
- **File**: `/DueDiligenceFrontend/src/components/QADashboard.jsx`
- **Line**: Entire component
- **Problem**: Only basic table, no KPIs or charts
- **Impact**: QA role lacks proper dashboard functionality
- **Estimated Effort**: 2 days
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 2)

**Acceptance Criteria:**
- [ ] 4 KPI cards added (Total, Pending, Completed, Avg Time)
- [ ] Outcome donut chart implemented
- [ ] Trend line chart added
- [ ] Recent reviews table enhanced
- [ ] Date filtering works
- [ ] Backend API returns full dashboard data

---

### Issue #3: Hardcoded File Path
- **File**: `/DueDiligenceBackend/Due Diligence/app.py`
- **Line**: 59
- **Problem**: Hardcoded path `/home/ubuntu/webapp/.env`
- **Impact**: Breaks application portability
- **Estimated Effort**: 5 minutes
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 3)

**Acceptance Criteria:**
- [ ] Line 59 deleted (redundant load_dotenv)
- [ ] Application works without hardcoded path
- [ ] Tested on different machines/paths
- [ ] No other hardcoded paths in codebase

---

### Issue #4: Database File Duplication
- **Files**: Multiple locations
  - `/DueDiligenceBackend/scrutinise_workflow.db` (12KB)
  - `/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db` (336KB) ← Main
  - `/DueDiligenceBackend/AI SME/scrutinise_workflow.db` (176KB)
  - `/DueDiligenceFrontend/scrutinise_workflow.db` (336KB)
- **Problem**: Multiple database files, unclear which is canonical
- **Impact**: Potential data sync issues
- **Estimated Effort**: 2 hours
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 4)

**Acceptance Criteria:**
- [ ] Single canonical database identified
- [ ] Other DB files removed or backed up
- [ ] All references point to canonical DB
- [ ] `*.db` added to .gitignore
- [ ] Documentation updated with DB location

---

## 🟡 HIGH PRIORITY (Fix Within 2 Weeks)

### Issue #5: Team Leader Dashboard - Missing Charts
- **File**: `/DueDiligenceFrontend/src/components/TeamLeaderDashboard.jsx`
- **Line**: After line 160
- **Problem**: Only KPI tiles and table, no visualizations
- **Impact**: Limited analytical capability for team leads
- **Estimated Effort**: 1 day
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 5)

**Acceptance Criteria:**
- [ ] Daily output line chart added
- [ ] Individual performance bar chart added
- [ ] Backend API returns chart data
- [ ] Charts render properly
- [ ] Mobile responsive

---

### Issue #6: Outdated Comment in Reviewer Dashboard
- **File**: `/DueDiligenceFrontend/src/components/ReviewerDashboard.jsx`
- **Line**: 165
- **Problem**: Comment says "placeholder for now" but charts exist
- **Impact**: Developer confusion
- **Estimated Effort**: 5 minutes
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 6)

**Acceptance Criteria:**
- [ ] Comment removed
- [ ] Code review completed

---

### Issue #7: Inconsistent API Response Format
- **Files**: Multiple API endpoints in `app.py`
- **Problem**: Some return raw data, some wrap in objects, inconsistent error handling
- **Impact**: Code maintainability, frontend error handling
- **Estimated Effort**: 1 day
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 7)

**Acceptance Criteria:**
- [ ] Standard API response helper created
- [ ] All API endpoints use standard format
- [ ] Error responses consistent
- [ ] Frontend updated to handle new format
- [ ] Documentation updated

---

### Issue #8: SQL Injection Risks
- **File**: `/DueDiligenceBackend/Due Diligence/app.py`
- **Lines**: Multiple (search needed)
- **Problem**: Some queries use string formatting/interpolation
- **Impact**: Security vulnerability
- **Estimated Effort**: 2 days
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: N/A (Security review required)

**Acceptance Criteria:**
- [ ] All SQL queries use parameterized statements
- [ ] Code reviewed for string interpolation in queries
- [ ] Security scan performed
- [ ] No SQL injection vulnerabilities found

---

### Issue #9: No API Documentation
- **Files**: Backend API routes
- **Problem**: No OpenAPI/Swagger documentation
- **Impact**: Difficult for developers to understand endpoints
- **Estimated Effort**: 3 days
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: N/A

**Acceptance Criteria:**
- [ ] OpenAPI spec generated
- [ ] Swagger UI accessible at `/api/docs`
- [ ] All endpoints documented
- [ ] Request/response schemas defined
- [ ] Examples provided

---

### Issue #10: No Database Indexes
- **File**: Database schema
- **Problem**: Missing indexes on frequently queried columns
- **Impact**: Slow query performance
- **Estimated Effort**: 1 day
- **Status**: ❌ Open
- **Assigned To**: _____________
- **Due Date**: _____________
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 9)

**Acceptance Criteria:**
- [ ] Indexes created on user email, role, team_lead
- [ ] Indexes on reviews: assigned_to, completed_by, status, dates
- [ ] Indexes on QC fields
- [ ] Indexes on SME referral fields
- [ ] Composite indexes for common query patterns
- [ ] Query performance improved (measured)

---

## 🟢 MEDIUM PRIORITY (Fix Within 1 Month)

### Issue #11: Inconsistent Loading States
- **Files**: Multiple components
- **Problem**: Some components show spinner, others don't
- **Impact**: Inconsistent UX
- **Estimated Effort**: 1 day
- **Status**: ❌ Open
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 8)

**Checklist:**
- [ ] Standard loading pattern defined
- [ ] Applied to all data-fetching components
- [ ] Spinner consistent across app

---

### Issue #12: No Pagination
- **Files**: API endpoints returning large datasets
- **Problem**: Loading all records causes performance issues
- **Impact**: Slow load times with large datasets
- **Estimated Effort**: 2 days
- **Status**: ❌ Open
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section 10)

**Checklist:**
- [ ] Pagination helper implemented
- [ ] Applied to /api/my_tasks
- [ ] Applied to other large result sets
- [ ] Frontend pagination controls added

---

### Issue #13: No Caching Layer
- **Files**: Dashboard API endpoints
- **Problem**: Dashboards recalculate on every request
- **Impact**: Slow dashboard load times
- **Estimated Effort**: 3 days
- **Status**: ❌ Open
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section: Quick Performance Wins)

**Checklist:**
- [ ] Caching library installed
- [ ] Dashboard results cached (5 min TTL)
- [ ] Cache invalidation strategy
- [ ] Performance improvement measured

---

### Issue #14: Large Component Files
- **Files**: ReviewerPanel.jsx, QCReviewPanel.jsx
- **Problem**: Components too large (likely 1000+ lines)
- **Impact**: Code maintainability
- **Estimated Effort**: 5 days
- **Status**: ❌ Open

**Checklist:**
- [ ] Components split into smaller parts
- [ ] Logical separation maintained
- [ ] Functionality preserved
- [ ] Tests added for new components

---

### Issue #15: Minimal Test Coverage
- **Files**: Entire codebase
- **Problem**: Only 1 test file found
- **Impact**: Risk of regressions, hard to refactor
- **Estimated Effort**: 2 weeks
- **Status**: ❌ Open
- **Fix Guide**: QUICK_FIX_GUIDE.md (Section: Testing Quick Start)

**Checklist:**
- [ ] Backend unit tests (utils, business logic)
- [ ] Backend integration tests (API endpoints)
- [ ] Frontend component tests
- [ ] E2E tests for critical workflows
- [ ] Coverage > 70%

---

### Issue #16: Not Production-Ready Infrastructure
- **Files**: Deployment configuration
- **Problem**: Using Flask dev server, SQLite, no monitoring
- **Impact**: Cannot deploy to production safely
- **Estimated Effort**: 3 weeks
- **Status**: ❌ Open

**Checklist:**
- [ ] Gunicorn/uWSGI configured
- [ ] PostgreSQL migration complete
- [ ] Nginx reverse proxy set up
- [ ] Process manager (systemd/supervisor)
- [ ] Monitoring (Prometheus/Grafana)
- [ ] Logging (ELK/Cloudwatch)
- [ ] Secret management
- [ ] Load testing passed

---

### Issue #17: Inconsistent Error Handling
- **Files**: Multiple components
- **Problem**: Some show alerts, some inline, some nothing
- **Impact**: Poor UX
- **Estimated Effort**: 1 day
- **Status**: ❌ Open

**Checklist:**
- [ ] Standard error handling pattern
- [ ] Applied consistently
- [ ] User-friendly error messages

---

### Issue #18: No User Documentation
- **Files**: Documentation
- **Problem**: No end-user guide
- **Impact**: Hard for new users to learn system
- **Estimated Effort**: 1 week
- **Status**: ❌ Open

**Checklist:**
- [ ] User guide for each role
- [ ] Screenshots included
- [ ] Common workflows documented
- [ ] FAQ section

---

### Issue #19: No Session Timeout
- **Files**: `app.py` session configuration
- **Problem**: Sessions never expire
- **Impact**: Security concern
- **Estimated Effort**: 2 hours
- **Status**: ❌ Open

**Checklist:**
- [ ] Session timeout configured (e.g., 30 minutes)
- [ ] Idle timeout implemented
- [ ] User warned before timeout
- [ ] Auto-save before timeout

---

### Issue #20: Mobile Responsiveness Issues
- **Files**: Multiple components
- **Problem**: Some tables/dashboards not mobile-friendly
- **Impact**: Poor mobile experience
- **Estimated Effort**: 3 days
- **Status**: ❌ Open

**Checklist:**
- [ ] All dashboards tested on mobile
- [ ] Tables responsive or scrollable
- [ ] Forms work on mobile
- [ ] Touch-friendly interactions

---

## 📊 Progress Summary

### By Priority
- **Critical (4)**: ❌ 0 completed | ⏳ 4 in progress | 🔴 0 remaining
- **High (6)**: ❌ 0 completed | ⏳ 0 in progress | 🟡 6 remaining
- **Medium (10)**: ❌ 0 completed | ⏳ 0 in progress | 🟢 10 remaining

### By Status
- ✅ **Completed**: 0 / 20 (0%)
- ⏳ **In Progress**: 0 / 20 (0%)
- ❌ **Not Started**: 20 / 20 (100%)

### Target Completion
- **Phase 1 (Critical)**: Week 1 - _____________ (target date)
- **Phase 2 (High)**: Week 3 - _____________ (target date)
- **Phase 3 (Medium)**: Week 6 - _____________ (target date)

---

## 🎯 Weekly Sprint Planning

### Sprint 1 (Week 1) - Critical Fixes
- [ ] Issue #1: SME Dashboard Matrix
- [ ] Issue #2: QA Dashboard Overhaul
- [ ] Issue #3: Remove Hardcoded Path
- [ ] Issue #4: Database Cleanup

**Sprint Goal**: Fix all placeholders and critical bugs

---

### Sprint 2 (Week 2) - High Priority Part 1
- [ ] Issue #5: Team Leader Charts
- [ ] Issue #6: Remove Outdated Comment
- [ ] Issue #7: API Response Format
- [ ] Issue #8: SQL Injection Fixes (start)

**Sprint Goal**: Dashboard completeness and API standardization

---

### Sprint 3 (Week 3) - High Priority Part 2
- [ ] Issue #8: SQL Injection Fixes (complete)
- [ ] Issue #9: API Documentation
- [ ] Issue #10: Database Indexes

**Sprint Goal**: Security and performance improvements

---

### Sprint 4-6 (Weeks 4-6) - Medium Priority
- [ ] Issue #11-20: Medium priority issues
- [ ] Production deployment preparation

**Sprint Goal**: Production readiness

---

## 📝 Notes

### Team Assignments
- **Frontend Lead**: _________________
- **Backend Lead**: _________________
- **QA Lead**: _________________
- **DevOps Lead**: _________________

### Review Schedule
- **Daily Standups**: _________________
- **Weekly Reviews**: _________________
- **Sprint Retrospectives**: _________________

### Definition of Done
For an issue to be marked ✅ Complete:
- [ ] Code implemented and tested
- [ ] Code review completed
- [ ] Tests written (if applicable)
- [ ] Documentation updated
- [ ] Deployed to staging
- [ ] QA verification passed
- [ ] Product owner acceptance

---

**Last Review**: December 18, 2025  
**Next Review**: _________________ (after Sprint 1)

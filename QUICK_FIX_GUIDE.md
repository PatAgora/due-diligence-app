# Quick Fix Guide - Due Diligence App Issues

## 🚨 Critical Issues - Fix These First

### 1. SME Dashboard - Missing Matrix Table (Line 188)

**File**: `/DueDiligenceFrontend/src/components/SMEDashboard.jsx`

**Current Code** (Line 184-191):
```jsx
<div className="col-lg-6">
  <div className="card shadow-sm h-100">
    <div className="card-body">
      <h5 className="card-title">Case Stage & Age Profile</h5>
      <p className="text-muted">Matrix table would go here</p>  // ❌ PLACEHOLDER
    </div>
  </div>
</div>
```

**Fix**: Replace with proper table implementation like Operations Dashboard

**Suggested Implementation**:
```jsx
<div className="col-lg-6">
  <div className="card shadow-sm h-100">
    <div className="card-body">
      <h5 className="card-title">Case Stage & Age Profile</h5>
      <div className="table-responsive">
        <table className="table table-sm table-hover">
          <thead className="table-light">
            <tr>
              <th>Status</th>
              <th className="text-center">0-2 Days</th>
              <th className="text-center">3-5 Days</th>
              <th className="text-center">5+ Days</th>
              <th className="text-end">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.age_rows && data.age_rows.length > 0 ? (
              data.age_rows.map((row, idx) => (
                <tr key={idx}>
                  <td className="fw-semibold">{row.status}</td>
                  <td className="text-center">{row.age_0_2 || 0}</td>
                  <td className="text-center">{row.age_3_5 || 0}</td>
                  <td className="text-center">{row.age_5_plus || 0}</td>
                  <td className="text-end fw-bold">{row.total || 0}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="text-center text-muted">No data available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
```

**Backend Change Required**: Ensure API endpoint `/api/sme_dashboard` returns `age_rows` data structure:
```python
# In app.py - api_sme_dashboard function
age_rows = []
# Calculate age buckets by status for SME referrals
# Similar to operations dashboard logic
return jsonify({
    # ... existing fields ...
    'age_rows': age_rows
})
```

---

### 2. QA Dashboard - Completely Reimplement

**File**: `/DueDiligenceFrontend/src/components/QADashboard.jsx`

**Current State**: Only has basic table, no KPIs

**Needed Structure**:
```jsx
function QADashboard() {
  // ... existing state ...
  
  // NEW: Add dashboard data state
  const [dashboardData, setDashboardData] = useState({
    total_qa_tasks: 0,
    pending_qa: 0,
    completed_qa: 0,
    avg_review_time: 0,
    outcomes: {}
  });

  return (
    <BaseLayout>
      <div className="container my-4">
        <h2 className="mb-4">QA Dashboard</h2>

        {/* NEW: Add KPI Cards */}
        <div className="row g-3 mb-4">
          <div className="col-12 col-md-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Total QA Tasks</h6>
                <div className="num">{dashboardData.total_qa_tasks || 0}</div>
              </div>
            </div>
          </div>
          <div className="col-12 col-md-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Pending Review</h6>
                <div className="num">{dashboardData.pending_qa || 0}</div>
              </div>
            </div>
          </div>
          <div className="col-12 col-md-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Completed</h6>
                <div className="num">{dashboardData.completed_qa || 0}</div>
              </div>
            </div>
          </div>
          <div className="col-12 col-md-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Avg Review Time</h6>
                <div className="num">{dashboardData.avg_review_time || 0}h</div>
              </div>
            </div>
          </div>
        </div>

        {/* NEW: Add Outcome Chart */}
        <div className="row g-4 mb-4">
          <div className="col-lg-6">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title">QA Outcomes</h5>
                {/* Add Doughnut chart here */}
              </div>
            </div>
          </div>
          <div className="col-lg-6">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title">Review Trend</h5>
                {/* Add Line chart here */}
              </div>
            </div>
          </div>
        </div>

        {/* Existing table - keep but enhance */}
        <div className="card shadow-sm">
          <div className="card-body">
            <h5 className="card-title">Recent QA Reviews</h5>
            {/* ... existing table code ... */}
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}
```

**Backend Enhancement**: Update `/api/qa_dashboard` to return comprehensive data:
```python
@app.route('/api/qa_dashboard', methods=['GET'])
@role_required('qa', 'admin')
def api_qa_dashboard():
    # ... existing code ...
    
    # NEW: Calculate KPIs
    total_qa_tasks = len(qa_tasks)
    pending_qa = sum(1 for t in qa_tasks if t['qa_outcome'] is None)
    completed_qa = sum(1 for t in qa_tasks if t['qa_outcome'] is not None)
    
    # Calculate average review time
    avg_review_time = calculate_avg_review_time(qa_tasks)
    
    # Outcome distribution
    outcomes = {}
    for task in qa_tasks:
        outcome = task.get('qa_outcome', 'Pending')
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    
    return jsonify({
        'entries': qa_tasks,
        'total_qa_tasks': total_qa_tasks,
        'pending_qa': pending_qa,
        'completed_qa': completed_qa,
        'avg_review_time': avg_review_time,
        'outcomes': outcomes,
        'daily_labels': [...],  # For trend chart
        'daily_counts': [...]   # For trend chart
    })
```

---

### 3. Remove Hardcoded Path

**File**: `/DueDiligenceBackend/Due Diligence/app.py`

**Line 59** - REMOVE:
```python
load_dotenv("/home/ubuntu/webapp/.env")  # ❌ HARDCODED PATH
```

**Fix**: This line is redundant since `load_dotenv()` on line 56 already loads `.env` from current directory.

Simply delete line 59, or make it relative:
```python
from dotenv import load_dotenv
load_dotenv()  # Loads from current directory
# Optional: support multiple locations
load_dotenv(".env")
load_dotenv("../.env")
```

---

### 4. Database File Cleanup

**Issue**: Multiple database files exist

**Files Found**:
- `/DueDiligenceBackend/scrutinise_workflow.db` (12KB)
- `/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db` (336KB) ✅ Main
- `/DueDiligenceBackend/AI SME/scrutinise_workflow.db` (176KB)
- `/DueDiligenceFrontend/scrutinise_workflow.db` (336KB)

**Fix**:
1. Identify canonical database (likely `/Due Diligence/scrutinise_workflow.db`)
2. Delete or move other copies to backup folder
3. Update all references to use single database path
4. Add to `.gitignore`:
```
*.db
*.db-journal
```

**Code Fix** - Centralize database path:
```python
# In app.py - add at top
import os
from pathlib import Path

# Define single source of truth for database
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scrutinise_workflow.db"

# Use DB_PATH everywhere instead of hardcoded paths
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    # ... rest of function
```

---

## 🟡 High Priority Fixes

### 5. Team Leader Dashboard - Add Charts

**File**: `/DueDiligenceFrontend/src/components/TeamLeaderDashboard.jsx`

**Add after line 160** (after team members table):

```jsx
{/* NEW: Add Charts Section */}
<div className="row g-4 mt-4">
  {/* Daily Output Chart */}
  <div className="col-lg-6">
    <div className="card shadow-sm h-100">
      <div className="card-body">
        <h5 className="card-title">Team Daily Output</h5>
        <div style={{ position: 'relative', height: '300px' }}>
          {data.daily_labels && data.daily_labels.length > 0 ? (
            <Line
              data={{
                labels: data.daily_labels,
                datasets: [{
                  label: 'Completed',
                  data: data.daily_counts,
                  borderColor: '#0d6efd',
                  backgroundColor: 'rgba(13, 110, 253, 0.1)',
                  tension: 0.3,
                  fill: true
                }]
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { display: false }
                },
                scales: {
                  y: { beginAtZero: true, ticks: { precision: 0 } }
                }
              }}
            />
          ) : (
            <div className="d-flex align-items-center justify-content-center h-100">
              <p className="text-muted">No output data</p>
            </div>
          )}
        </div>
      </div>
    </div>
  </div>

  {/* Individual Performance Chart */}
  <div className="col-lg-6">
    <div className="card shadow-sm h-100">
      <div className="card-body">
        <h5 className="card-title">Individual Performance</h5>
        <div style={{ position: 'relative', height: '300px' }}>
          {data.reviewer_performance && data.reviewer_performance.length > 0 ? (
            <Bar
              data={{
                labels: data.reviewer_performance.map(r => r.name),
                datasets: [{
                  label: 'Completed',
                  data: data.reviewer_performance.map(r => r.completed),
                  backgroundColor: '#198754'
                }]
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
              }}
            />
          ) : (
            <div className="d-flex align-items-center justify-content-center h-100">
              <p className="text-muted">No performance data</p>
            </div>
          )}
        </div>
      </div>
    </div>
  </div>
</div>
```

**Backend Update**: Modify `/api/team_leader_dashboard` to include chart data:
```python
# Add to existing response
return jsonify({
    # ... existing fields ...
    'daily_labels': daily_labels,
    'daily_counts': daily_counts,
    'reviewer_performance': reviewer_stats
})
```

---

### 6. Remove Outdated Comment

**File**: `/DueDiligenceFrontend/src/components/ReviewerDashboard.jsx`

**Line 165** - DELETE:
```jsx
{/* Charts row - placeholder for now */}  // ❌ OUTDATED COMMENT
```

The charts ARE implemented below this line, so the comment is misleading.

---

### 7. Standardize API Response Format

**Issue**: Inconsistent API responses across endpoints

**Current State**:
- Some APIs return raw data
- Some wrap in `{ data: {...} }`
- Some include `error` field, others don't

**Standard Format** to adopt:
```json
{
  "success": true,
  "data": {
    // ... actual data ...
  },
  "error": null,
  "timestamp": "2025-12-18T10:30:00Z"
}
```

Or on error:
```json
{
  "success": false,
  "data": null,
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE"
  },
  "timestamp": "2025-12-18T10:30:00Z"
}
```

**Implementation Helper**:
```python
# Add to app.py
def api_response(data=None, error=None, status_code=200):
    """Standardized API response format"""
    return jsonify({
        'success': error is None,
        'data': data,
        'error': error,
        'timestamp': datetime.utcnow().isoformat()
    }), status_code

# Usage:
@app.route('/api/some_endpoint')
def some_endpoint():
    try:
        result = do_something()
        return api_response(data=result)
    except Exception as e:
        return api_response(
            error={'message': str(e), 'code': 'INTERNAL_ERROR'},
            status_code=500
        )
```

---

## 🟢 Medium Priority Improvements

### 8. Add Loading States Consistently

**Pattern to Follow**:
```jsx
function SomeComponent() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch('/api/endpoint');
      if (!response.ok) throw new Error('Failed to fetch');
      const json = await response.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-danger">
        <h4 className="alert-heading">Error</h4>
        <p>{error}</p>
        <button className="btn btn-primary" onClick={fetchData}>Retry</button>
      </div>
    );
  }

  return (
    <div>
      {/* Render data */}
    </div>
  );
}
```

**Apply this pattern to**:
- All dashboard components
- All data-fetching components
- Ensure consistent spinner and error UI

---

### 9. Add Database Indexes

**File**: Create new file `/DueDiligenceBackend/Due Diligence/add_indexes.sql`

```sql
-- Performance indexes for common queries

-- User lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_team_lead ON users(team_lead);

-- Review assignments and status
CREATE INDEX IF NOT EXISTS idx_reviews_assigned_to ON reviews(assigned_to);
CREATE INDEX IF NOT EXISTS idx_reviews_completed_by ON reviews(completed_by);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_reviews_date_assigned ON reviews(date_assigned);
CREATE INDEX IF NOT EXISTS idx_reviews_date_completed ON reviews(date_completed);

-- QC workflow
CREATE INDEX IF NOT EXISTS idx_reviews_qc_assigned ON reviews(qc_assigned_to);
CREATE INDEX IF NOT EXISTS idx_reviews_qc_check_date ON reviews(qc_check_date);
CREATE INDEX IF NOT EXISTS idx_reviews_qc_outcome ON reviews(qc_outcome);

-- SME workflow
CREATE INDEX IF NOT EXISTS idx_reviews_referred_sme ON reviews(referred_to_sme);
CREATE INDEX IF NOT EXISTS idx_reviews_sme_returned ON reviews(sme_returned_date);

-- QC Sampling
CREATE INDEX IF NOT EXISTS idx_qc_sampling_review_id ON qc_sampling_log(review_id);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_reviews_assigned_status ON reviews(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_reviews_completed_date ON reviews(completed_by, date_completed);
```

**Run the indexes**:
```bash
cd "Due Diligence"
sqlite3 scrutinise_workflow.db < add_indexes.sql
```

---

### 10. Implement Pagination Helper

**Create**: `/DueDiligenceBackend/Due Diligence/pagination.py`

```python
def paginate_query(query_result, page=1, per_page=50):
    """
    Paginate a list of results
    
    Args:
        query_result: List of items to paginate
        page: Current page number (1-indexed)
        per_page: Items per page
        
    Returns:
        dict with paginated data and metadata
    """
    total = len(query_result)
    total_pages = (total + per_page - 1) // per_page
    
    start = (page - 1) * per_page
    end = start + per_page
    
    items = query_result[start:end]
    
    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    }

# Usage in routes:
@app.route('/api/my_tasks')
def api_my_tasks():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # Get all tasks
    all_tasks = get_user_tasks(user_id)
    
    # Paginate
    result = paginate_query(all_tasks, page, per_page)
    
    return jsonify(result)
```

**Frontend Update** - Add pagination controls:
```jsx
function MyTasks() {
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);

  // ... fetch with ?page=X&per_page=50 ...

  return (
    <div>
      {/* Table */}
      
      {/* Pagination Controls */}
      {pagination && (
        <nav aria-label="Page navigation">
          <ul className="pagination justify-content-center">
            <li className={`page-item ${!pagination.has_prev ? 'disabled' : ''}`}>
              <button 
                className="page-link" 
                onClick={() => setPage(page - 1)}
                disabled={!pagination.has_prev}
              >
                Previous
              </button>
            </li>
            <li className="page-item disabled">
              <span className="page-link">
                Page {pagination.page} of {pagination.total_pages}
              </span>
            </li>
            <li className={`page-item ${!pagination.has_next ? 'disabled' : ''}`}>
              <button 
                className="page-link" 
                onClick={() => setPage(page + 1)}
                disabled={!pagination.has_next}
              >
                Next
              </button>
            </li>
          </ul>
        </nav>
      )}
    </div>
  );
}
```

---

## 📝 Testing Quick Start

**Create**: `/DueDiligenceBackend/Due Diligence/tests/test_dashboards.py`

```python
import unittest
from app import app, get_db

class DashboardTestCase(unittest.TestCase):
    
    def setUp(self):
        self.app = app
        self.client = app.test_client()
        self.app.config['TESTING'] = True
        
    def test_reviewer_dashboard_api(self):
        """Test reviewer dashboard returns valid JSON"""
        # Login first
        self.client.post('/login', json={
            'email': 'reviewer@test.com',
            'password': 'test123'
        })
        
        # Get dashboard
        response = self.client.get('/api/reviewer_dashboard')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertIn('active_wip', data)
        self.assertIn('completed_count', data)
        
    def test_qc_lead_dashboard_api(self):
        """Test QC lead dashboard returns valid JSON"""
        # Similar pattern
        pass
        
    def test_operations_dashboard_filters(self):
        """Test operations dashboard with filters"""
        # Login as ops manager
        # Test date_range filter
        # Test team filter
        pass

if __name__ == '__main__':
    unittest.main()
```

**Run tests**:
```bash
cd "Due Diligence"
python -m pytest tests/test_dashboards.py -v
```

---

## 🔐 Security Quick Fixes

### SQL Injection Prevention

**Bad** (found in some queries):
```python
query = f"SELECT * FROM reviews WHERE id = {task_id}"  # ❌ DANGEROUS
```

**Good** (use parameterized queries):
```python
query = "SELECT * FROM reviews WHERE id = ?"
cur.execute(query, (task_id,))  # ✅ SAFE
```

**Check these files for SQL injection risks**:
```bash
cd "Due Diligence"
grep -n "f\"SELECT\|f'SELECT\|% SELECT" app.py
```

Fix any matches to use parameterized queries.

---

## 📊 Quick Performance Wins

### 1. Add Simple Caching

**Install**: `pip install cachetools`

**Add to app.py**:
```python
from cachetools import TTLCache
from functools import wraps

# Create cache - 100 items, 5 minute TTL
dashboard_cache = TTLCache(maxsize=100, ttl=300)

def cached_dashboard(func):
    """Decorator to cache dashboard results"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create cache key from function name and user_id
        user_id = session.get('user_id')
        date_range = request.args.get('date_range', 'all')
        cache_key = f"{func.__name__}:{user_id}:{date_range}"
        
        # Check cache
        if cache_key in dashboard_cache:
            return dashboard_cache[cache_key]
        
        # Call function
        result = func(*args, **kwargs)
        
        # Store in cache
        dashboard_cache[cache_key] = result
        return result
    
    return wrapper

# Use on dashboard routes:
@app.route('/api/reviewer_dashboard')
@cached_dashboard
def api_reviewer_dashboard():
    # ... existing code ...
```

### 2. Optimize Large Queries

**Before**:
```python
# Loads ALL reviews into memory
cur.execute("SELECT * FROM reviews")
all_reviews = [dict(r) for r in cur.fetchall()]
# Then filter in Python
my_reviews = [r for r in all_reviews if r['assigned_to'] == user_id]
```

**After**:
```python
# Filter in SQL
cur.execute("""
    SELECT * FROM reviews 
    WHERE assigned_to = ? 
    ORDER BY date_assigned DESC
    LIMIT 1000
""", (user_id,))
my_reviews = [dict(r) for r in cur.fetchall()]
```

---

## 🎯 Testing Checklist

After making fixes, test these scenarios:

- [ ] Login as Reviewer → View Dashboard → All KPIs show numbers
- [ ] Login as QC Lead → View Dashboard → Charts render
- [ ] Login as Team Leader → View Dashboard → See new charts
- [ ] Login as SME → View Dashboard → Matrix table visible
- [ ] Login as QA → View Dashboard → KPIs and charts visible
- [ ] Login as Operations Manager → View Dashboard → All sections load
- [ ] Test date range filters on all dashboards
- [ ] Test with empty data (new database)
- [ ] Test with large dataset (1000+ tasks)
- [ ] Test concurrent users (if possible)
- [ ] Check browser console for errors
- [ ] Check network tab for failed API calls
- [ ] Verify mobile responsiveness

---

## 📞 Need Help?

If you encounter issues while implementing these fixes:

1. **Check the main analysis**: See `COMPREHENSIVE_APP_ANALYSIS.md` for context
2. **Review existing code**: Look at similar working implementations
3. **Test incrementally**: Make one change at a time
4. **Use browser DevTools**: Check console and network tabs
5. **Check backend logs**: Look for Python errors/tracebacks

---

**Document Version**: 1.0  
**Last Updated**: December 18, 2025  
**Priority**: Fix Critical items first (Issues 1-4), then High (5-7)

import { useState, useEffect } from 'react';
import { useSearchParams, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useModuleSettings } from '../contexts/ModuleSettingsContext';
import { usePermissions } from '../contexts/PermissionsContext';
import TopNavbar from './TopNavbar';

import './MyTasks.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function MyTasks() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { isModuleEnabled } = useModuleSettings();
  const { canView, canEdit } = usePermissions();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const role = user?.role?.toLowerCase() || '';
  const isActive = (path) => location.pathname.startsWith(path);
  
  const getDashboardPath = () => {
    if (role.includes('operations_manager')) return '/operations_dashboard';
    if (role === 'admin') return '/admin/users';
    if (role.startsWith('qc_lead_')) return '/qc_lead_dashboard';
    if (role.startsWith('qc_')) return '/qc_dashboard';
    if (role.startsWith('team_lead_')) return '/team_leader_dashboard';
    if (role.startsWith('qa_')) return '/qa_dashboard';
    if (role.startsWith('sme_')) return '/sme_dashboard';
    if (role.startsWith('reviewer_')) return '/reviewer_dashboard';
    return '/';
  };

  const isOnDashboard = () => {
    const dashboardPath = getDashboardPath();
    return location.pathname === dashboardPath || location.pathname.startsWith(dashboardPath);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Read filters from URL for display
  const status = searchParams.get('status') || '';
  const date = searchParams.get('date') || '';
  const dateRange = searchParams.get('date_range') || 'all';
  const ageBucket = searchParams.get('age_bucket') || '';
  const excludeCompleted = searchParams.get('exclude_completed') === 'true';

  // Check permissions - can_view allows access, can_edit allows interactions
  // Check both "review_tasks" and "review" (in case database uses "review")
  const canViewTasks = canView('review_tasks') || canView('review');
  const canEditTasks = canEdit('review_tasks') || canEdit('review');
  
  // Auto-filter: Exclude completed cases by default on initial load
  useEffect(() => {
    // Only apply auto-filter if no status filter is already set
    if (!searchParams.has('status') && !searchParams.has('exclude_completed')) {
      const params = new URLSearchParams(searchParams);
      params.set('exclude_completed', 'true');
      setSearchParams(params, { replace: true });
    }
  }, []); // Run only once on mount
  
  useEffect(() => {
    if (canViewTasks) {
      fetchTasks();
    }
  }, [searchParams, canViewTasks]);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      setError(null);

      // Pass ALL searchParams directly to API (like OperationsCases does)
      const params = new URLSearchParams(searchParams);
      const response = await fetch(`${BASE_URL}/api/my_tasks?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load tasks');
      }

      const data = await response.json();
      setTasks(data.tasks || []);
    } catch (err) {
      console.error('Error fetching tasks:', err);
      setError(err.message);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (e) => {
    const newStatus = e.target.value;
    const params = new URLSearchParams(searchParams);
    if (newStatus) {
      params.set('status', newStatus);
    } else {
      params.delete('status');
    }
    setSearchParams(params);
  };

  const handleDateChange = (e) => {
    const newDate = e.target.value;
    const params = new URLSearchParams(searchParams);
    if (newDate) {
      params.set('date', newDate);
    } else {
      params.delete('date');
    }
    setSearchParams(params);
  };

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

  const getRowBgColor = (taskStatus) => {
    if (taskStatus === 'Closed') return '#e8f5e9';
    if (taskStatus?.includes('Rework Required')) return '#fff3e0';
    if (taskStatus?.includes('On Hold')) return '#e3f2fd';
    if (taskStatus?.includes('Referred')) return '#fbe9e7';
    if (taskStatus?.includes('Returned')) return '#ede7f6';
    return '#ffffff';
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return '—';
    }
  };

  // Show access denied if no view permission
  if (!canViewTasks) {
    return (
      <div className="container my-4">
        <div className="alert alert-warning">
          <h4 className="alert-heading">Access Denied</h4>
          <p>You do not have permission to view or edit tasks.</p>
          <p className="mb-0">Please contact your administrator if you believe this is an error.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <>
        <nav className="sidebar-nav scrutinise-dark">
          <div className="sidebar-brand">
            <span className="scrutinise-brand">
              Scrutinise<span className="underbar"></span>
            </span>
          </div>
          <div className="sidebar-content">
            {!isOnDashboard() && (
              <>
                <Link to={getDashboardPath()} className="nav-link">
                  <i className="bi bi-speedometer2"></i> Dashboard
                </Link>
                <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
              </>
            )}
            {(location.pathname.startsWith('/reviewer_dashboard') || 
              location.pathname.startsWith('/reviewer_panel')) && (
              <Link to="/my_tasks" className={`nav-link ${isActive('/my_tasks') ? 'active' : ''}`}>
                <i className="bi bi-list-check"></i> My Tasks
              </Link>
            )}
          </div>
          <div className="mt-auto px-2 pb-3">
            <a href="#" onClick={(e) => { e.preventDefault(); handleLogout(); }} className="nav-link text-danger d-flex align-items-center gap-2">
              <i className="bi bi-box-arrow-right"></i>
              <span>Logout</span>
            </a>
          </div>
        </nav>
        <TopNavbar />
        <main style={{ marginLeft: '240px', marginTop: '60px', padding: '10px 10px 10px 0', minHeight: '100%' }}>
          <div className="text-center py-5">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </main>
      </>
    );
  }

  if (error) {
    return (
      <>
        <TopNavbar />
        <nav className="sidebar-nav scrutinise-dark">
          <div className="sidebar-brand">
            <span className="scrutinise-brand">
              Scrutinise<span className="underbar"></span>
            </span>
          </div>
          <div className="sidebar-content">
            {!isOnDashboard() && (
              <>
                <Link to={getDashboardPath()} className="nav-link">
                  <i className="bi bi-speedometer2"></i> Dashboard
                </Link>
                <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
              </>
            )}
            {(location.pathname.startsWith('/reviewer_dashboard') || 
              location.pathname.startsWith('/reviewer_panel')) && (
              <Link to="/my_tasks" className={`nav-link ${isActive('/my_tasks') ? 'active' : ''}`}>
                <i className="bi bi-list-check"></i> My Tasks
              </Link>
            )}
          </div>
          <div className="mt-auto px-2 pb-3">
            <a href="#" onClick={(e) => { e.preventDefault(); handleLogout(); }} className="nav-link text-danger d-flex align-items-center gap-2">
              <i className="bi bi-box-arrow-right"></i>
              <span>Logout</span>
            </a>
          </div>
        </nav>
        <main style={{ marginLeft: '240px', padding: '10px 10px 10px 0', minHeight: '100%' }}>
          <div className="alert alert-danger">
            Error: {error}
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <nav className="sidebar-nav scrutinise-dark">
        <div className="sidebar-brand">
          <span className="scrutinise-brand">
            Scrutinise<span className="underbar"></span>
          </span>
        </div>
        <div className="sidebar-content">
          {!isOnDashboard() && (
            <>
              <Link to={getDashboardPath()} className="nav-link">
                <i className="bi bi-speedometer2"></i> Dashboard
              </Link>
              <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
            </>
          )}
          {(location.pathname.startsWith('/reviewer_dashboard') || 
            location.pathname.startsWith('/reviewer_panel')) && (
            <Link to="/my_tasks" className={`nav-link ${isActive('/my_tasks') ? 'active' : ''}`}>
              <i className="bi bi-list-check"></i> My Tasks
            </Link>
          )}
        </div>
        <div className="mt-auto px-2 pb-3">
          <a href="#" onClick={(e) => { e.preventDefault(); handleLogout(); }} className="nav-link text-danger d-flex align-items-center gap-2">
            <i className="bi bi-box-arrow-right"></i>
            <span>Logout</span>
          </a>
        </div>
      </nav>
      <TopNavbar />
      <main style={{ marginLeft: '280px', marginTop: '60px', padding: '20px 20px 20px 0', minHeight: '100%' }}>
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="mb-0">My Assigned Tasks</h2>
        </div>

        {/* Display active filters - removed */}

        <form method="get" className="mb-3" style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <div>
            <label htmlFor="status" className="me-2">
              <strong>Filter by Status:</strong>
            </label>
            <select
              name="status"
              id="status"
              onChange={handleStatusChange}
              value={status}
              className="form-select d-inline-block"
              style={{ width: '200px' }}
            >
              <option value="">-- All --</option>
              <option value="wip">WIP</option>
              <option value="In Progress">In Progress</option>
              <option value="Pending Review">Pending Review</option>
              <option value="Rework Required">Rework Required</option>
              <option value="QC - Rework Required">QC - Rework Required</option>
              <option value="Completed">Completed</option>
              {/* Only show SME referral status options if AI SME is disabled */}
              {!isModuleEnabled('ai_sme') && (
                <>
                  <option value="Referred to SME">Referred to SME</option>
                  <option value="Returned from SME">Returned from SME</option>
                </>
              )}
              <option value="Outreach">Outreach</option>
              <option value="7 Day Chaser Due">7 Day Chaser Due</option>
              <option value="14 Day Chaser Due">14 Day Chaser Due</option>
              <option value="21 Day Chaser Due">21 Day Chaser Due</option>
            </select>
          </div>

          <div>
            <label htmlFor="date" className="me-2">
              <strong>Filter by Date:</strong>
            </label>
            <select
              name="date"
              id="date"
              onChange={handleDateChange}
              value={date}
              className="form-select d-inline-block"
              style={{ width: '160px' }}
            >
              <option value="">-- All --</option>
              <option value="today">Today</option>
              <option value="week">This Week</option>
            </select>
          </div>

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
        </form>

        <div className="table-responsive">
          <table className="table table-striped table-hover align-middle" style={{ width: '100%' }}>
            <thead className="table-dark">
              <tr>
                <th>Task ID</th>
                <th>Status</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tasks.length > 0 ? (
                tasks.map((task) => (
                  <tr
                    key={task.task_id || task.id}
                    style={{ backgroundColor: getRowBgColor(task.status) }}
                  >
                    <td>{task.task_id || task.id}</td>
                    <td>{task.status}</td>
                    <td>{formatDate(task.updated_at)}</td>
                    <td>
                      {canEditTasks ? (
                        <Link
                          to={`/view_task/${task.task_id || task.id}`}
                          className="btn btn-sm btn-primary"
                        >
                          Review
                        </Link>
                      ) : (
                        <span className="btn btn-sm btn-secondary" style={{ cursor: 'not-allowed', opacity: 0.6 }}>
                          Review
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="4" className="text-center text-muted py-4">
                    No tasks found for the selected filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}

export default MyTasks;


import { useLocation, Link, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useModuleSettings } from '../contexts/ModuleSettingsContext';
import { usePermissions } from '../contexts/PermissionsContext';
import TopNavbar from './TopNavbar';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function BaseLayout({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { isModuleEnabled } = useModuleSettings();
  const { canView } = usePermissions();
  const isLoginPage = location.pathname === '/login' || location.pathname.startsWith('/login');
  const [taskStatus, setTaskStatus] = useState(null);

  if (isLoginPage) {
    return <>{children}</>;
  }

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const role = user?.role?.toLowerCase() || '';
  const isActive = (path) => location.pathname.startsWith(path);

  // Get the dashboard path based on user role
  const getDashboardPath = () => {
    if (role.includes('operations_manager') || role === 'operations') return '/operations_dashboard';
    if (role === 'admin') return '/admin/users';
    // QC Lead roles: qc_1, qc_2, qc_3 (not qc_lead_)
    if (role === 'qc_1' || role === 'qc_2' || role === 'qc_3') return '/qc_lead_dashboard';
    if (role.startsWith('qc_lead_')) return '/qc_lead_dashboard';
    // QC User roles: qc_review_1, qc_review_2, qc_review_3
    if (role.startsWith('qc_review_')) return '/qc_dashboard';
    if (role.startsWith('qc_')) return '/qc_dashboard';
    if (role.startsWith('team_lead_')) return '/team_leader_dashboard';
    if (role.startsWith('qa_')) return '/qa_dashboard';
    if (role.startsWith('sme_')) return '/sme_referrals';
    if (role.startsWith('reviewer_')) return '/reviewer_dashboard';
    return '/';
  };

  // Check if user is currently on their dashboard
  const isOnDashboard = () => {
    const dashboardPath = getDashboardPath();
    return location.pathname === dashboardPath || location.pathname.startsWith(dashboardPath);
  };

  const isMyTasksPage = location.pathname === '/my_tasks' || location.pathname.startsWith('/my_tasks');
  const isQCDashboardPage = location.pathname === '/qc_lead_dashboard' || location.pathname.startsWith('/qc_lead_dashboard');
  const isQCWIPPage = location.pathname === '/qc_wip_cases' || location.pathname.startsWith('/qc_wip_cases');
  
  // Check if on any dashboard page
  const isDashboardPage = location.pathname === '/reviewer_dashboard' || 
                          location.pathname === '/qc_lead_dashboard' ||
                          location.pathname === '/qc_dashboard' ||
                          location.pathname === '/team_leader_dashboard' ||
                          location.pathname === '/qa_dashboard' ||
                          location.pathname === '/sme_dashboard' ||
                          location.pathname === '/operations_dashboard' ||
                          location.pathname.startsWith('/reviewer_dashboard') ||
                          location.pathname.startsWith('/qc_lead_dashboard') ||
                          location.pathname.startsWith('/qc_dashboard') ||
                          location.pathname.startsWith('/team_leader_dashboard') ||
                          location.pathname.startsWith('/qa_dashboard') ||
                          location.pathname.startsWith('/sme_dashboard') ||
                          location.pathname.startsWith('/operations_dashboard');
  
  // Check if QC user is on my tasks page - should only show dashboard link
  const isQCOnMyTasksPage = (role.startsWith('qc_') || role === 'qc_1' || role === 'qc_2' || role === 'qc_3') && 
                            (isMyTasksPage || isQCWIPPage);
  
  // Check if on a task view page (ReviewerPanel or QCReviewPanel)
  const isTaskViewPage = location.pathname.startsWith('/view_task/') || 
                         location.pathname.startsWith('/qc_review/') ||
                         location.pathname.startsWith('/reviewer_panel/');
  
  // Check if on Transaction Review route
  const isTransactionReviewPage = location.pathname.includes('/transaction/');
  
  // Extract taskId from URL if on task view page
  // Handle both /view_task/:taskId and /view_task/:taskId/transaction/* patterns
  let taskId = null;
  if (isTaskViewPage || isTransactionReviewPage) {
    const parts = location.pathname.split('/').filter(p => p);
    if (parts[0] === 'view_task' || parts[0] === 'qc_review' || parts[0] === 'reviewer_panel') {
      taskId = parts[1];
    }
  }

  // Fetch task status when taskId is available
  useEffect(() => {
    if (taskId && isTaskViewPage) {
      const fetchTaskStatus = async () => {
        try {
          const isQCReview = location.pathname.startsWith('/qc_review/');
          const apiUrl = isQCReview 
            ? `${BASE_URL}/api/qc_review/${taskId}`
            : `${BASE_URL}/api/reviewer_panel/${taskId}`;
          
          const response = await fetch(apiUrl, { credentials: 'include' });
          if (response.ok) {
            const result = await response.json();
            setTaskStatus(result.review?.status || null);
          }
        } catch (e) {
          console.error('Failed to fetch task status:', e);
        }
      };
      fetchTaskStatus();
    } else {
      setTaskStatus(null);
    }
  }, [taskId, isTaskViewPage, location.pathname]);

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
          {/* Dashboard Link - shows when not on dashboard, or if QC user is on my tasks page */}
          {((!isOnDashboard() && canView('view_dashboard')) || isQCOnMyTasksPage) && (
            <>
              <Link
                to={getDashboardPath()}
                className="nav-link"
              >
                <i className="bi bi-speedometer2"></i> Dashboard
              </Link>
              {!isQCOnMyTasksPage && <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />}
            </>
          )}

          {/* Reviewer My Tasks - ALWAYS visible for reviewers on all pages */}
          {isModuleEnabled('due_diligence') && role.startsWith('reviewer_') && canView('review_tasks') && (
            <Link
              to="/my_tasks"
              className={`nav-link ${isActive('/my_tasks') ? 'active' : ''}`}
            >
              <i className="bi bi-list-check"></i> My Tasks
            </Link>
          )}
          
          {/* Hide all other navigation links if QC user is on my tasks page */}
          {!isQCOnMyTasksPage && (
            <>

          {/* Operations Manager specific links */}
          {isModuleEnabled('due_diligence') && (role.includes('operations_manager') || role === 'operations') && canView('assign_tasks') && (
            <>
              <Link
                to="/assign_tasks"
                className={`nav-link ${isActive('/assign_tasks') && !isActive('/assign_tasks_bulk') ? 'active' : ''}`}
              >
                <i className="bi bi-person-plus"></i> Assign Tasks
              </Link>
              {canView('assign_tasks') && (
                <Link
                  to="/assign_tasks_bulk"
                  className={`nav-link ${isActive('/assign_tasks_bulk') ? 'active' : ''}`}
                >
                  <i className="bi bi-people"></i> Bulk Assign
                </Link>
              )}
            </>
          )}

          {isModuleEnabled('due_diligence') && (role.startsWith('team_lead_') || role === 'team_lead') && canView('assign_tasks') && (
            <>
              <Link
                to="/assign_tasks"
                className={`nav-link ${isActive('/assign_tasks') && !isActive('/assign_tasks_bulk') ? 'active' : ''}`}
              >
                <i className="bi bi-person-plus"></i> Assign Tasks
              </Link>
              {canView('assign_tasks') && (
                <Link
                  to="/assign_tasks_bulk"
                  className={`nav-link ${isActive('/assign_tasks_bulk') ? 'active' : ''}`}
                >
                  <i className="bi bi-people"></i> Bulk Assign
                </Link>
              )}
            </>
          )}

          {/* Reviewer links section removed - My Tasks is now always visible above */}

          {/* Referrals - for SME only (unified page with answer capability) */}
          {(role === 'sme' || role.startsWith('sme_')) && (
            <Link
              to="/sme_referrals"
              className={`nav-link ${isActive('/sme_referrals') ? 'active' : ''}`}
            >
              <i className="bi bi-clipboard-list"></i> Referrals
            </Link>
          )}

          {location.pathname.startsWith('/operations_dashboard') && (
            <Link to="/ops/mi/planning" className="nav-link">
              <i className="bi bi-calendar3"></i> Planning
            </Link>
          )}

          {/* QC Lead links */}
          {(role === 'qc_1' || role === 'qc_2' || role === 'qc_3' || role.startsWith('qc_lead_') || (role.startsWith('qc_') && !role.startsWith('qc_review_'))) && canView('view_qc_qa') && (
            <>
              <Link
                to="/qc_manual_sampling"
                className={`nav-link ${isActive('/qc_manual_sampling') ? 'active' : ''}`}
              >
                <i className="bi bi-clipboard-check"></i> QC Sampling
              </Link>
              {canView('assign_tasks') && (
                <>
                  <Link
                    to="/qc_assign_tasks"
                    className={`nav-link ${isActive('/qc_assign_tasks') && !isActive('/qc_assign_tasks_bulk') ? 'active' : ''}`}
                  >
                    <i className="bi bi-person-plus"></i> Assign Tasks
                  </Link>
                  <Link
                    to="/qc_assign_tasks_bulk"
                    className={`nav-link ${isActive('/qc_assign_tasks_bulk') ? 'active' : ''}`}
                  >
                    <i className="bi bi-people"></i> Bulk Assign
                  </Link>
                </>
              )}
              <Link
                to="/qc/sampling-rates"
                className={`nav-link ${isActive('/qc/sampling-rates') ? 'active' : ''}`}
              >
                <i className="bi bi-gear"></i> Sampling Rates
              </Link>
            </>
          )}

          {/* QC Reviewer links - only QC reviewers get assigned tasks, not QC leads */}
          {role.startsWith('qc_review_') && canView('review_tasks') && (
            <Link
              to="/qc_wip_cases"
              className={`nav-link ${isActive('/qc_wip_cases') ? 'active' : ''}`}
            >
              <i className="bi bi-list-check"></i> My Tasks
            </Link>
          )}

          {/* Admin links */}
          {role === 'admin' && canView('manage_settings') && (
            <Link
              to="/qc/sampling-rates"
              className={`nav-link ${isActive('/qc/sampling-rates') ? 'active' : ''}`}
            >
              <i className="bi bi-gear"></i> Sampling Rates
            </Link>
          )}

          {/* AI SME Admin - available to admin and sme roles */}
          {isModuleEnabled('ai_sme') && (role === 'admin' || role === 'sme' || role.startsWith('sme_')) && (
            <>
              <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
              <Link
                to="/ai_sme/admin"
                className={`nav-link ${isActive('/ai_sme/admin') ? 'active' : ''}`}
              >
                <i className="fas fa-brain"></i> AI SME Admin
              </Link>
            </>
          )}

          {/* Transaction Review Admin - available to admin only */}
          {isModuleEnabled('transaction_review') && role === 'admin' && (
            <>
              <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
              <Link
                to="/tx_review/admin"
                className={`nav-link ${isActive('/tx_review/admin') ? 'active' : ''}`}
              >
                <i className="bi bi-arrow-repeat"></i> Transaction Review Admin
              </Link>
            </>
          )}

          {/* Admin Module Settings */}
          {role === 'admin' && (
            <>
              <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
              {canView('manage_settings') && (
                <>
                  <Link
                    to="/admin/module-settings"
                    className={`nav-link ${isActive('/admin/module-settings') ? 'active' : ''}`}
                  >
                    <i className="bi bi-gear"></i> Module Settings
                  </Link>
                  <Link
                    to="/admin/permissions"
                    className={`nav-link ${isActive('/admin/permissions') ? 'active' : ''}`}
                  >
                    <i className="bi bi-shield-check"></i> Permissions
                  </Link>
                  <Link
                    to="/admin/field-visibility"
                    className={`nav-link ${isActive('/admin/field-visibility') ? 'active' : ''}`}
                  >
                    <i className="bi bi-eye"></i> Field Visibility
                  </Link>
                  <Link
                    to="/admin/settings"
                    className={`nav-link ${isActive('/admin/settings') ? 'active' : ''}`}
                  >
                    <i className="bi bi-sliders"></i> Settings
                  </Link>
                  <Link
                    to="/admin/team-structure"
                    className={`nav-link ${isActive('/admin/team-structure') ? 'active' : ''}`}
                  >
                    <i className="bi bi-diagram-3"></i> Team Structure
                  </Link>
                </>
              )}
            </>
          )}

          {/* Transaction Review Dropdown - only on task view pages */}
          {isModuleEnabled('transaction_review') && isTaskViewPage && taskId && (
            <>
              <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
              <div className="accordion accordion-flush" id="txReviewAccordion">
                <div className="accordion-item bg-transparent border-0">
                  <h2 className="accordion-header">
                    <button 
                      className={`accordion-button ${isTransactionReviewPage ? '' : 'collapsed'}`}
                      type="button" 
                      data-bs-toggle="collapse" 
                      data-bs-target="#txReviewOps"
                    >
                      <i className="bi bi-arrow-repeat"></i>
                      Transaction Review
                    </button>
                  </h2>
                  <div id="txReviewOps" className={`accordion-collapse collapse ${isTransactionReviewPage ? 'show' : ''}`}>
                    <div className="accordion-body">
                      <nav className="nav flex-column">
                        <Link
                          to={location.pathname.startsWith('/qc_review/') 
                            ? `/qc_review/${taskId}/transaction/dashboard`
                            : `/view_task/${taskId}/transaction/dashboard`}
                          className={`nav-link ${isActive('/transaction/dashboard') ? 'active' : ''}`}
                        >
                          📊 Dashboard
                        </Link>
                        <Link
                          to={location.pathname.startsWith('/qc_review/') 
                            ? `/qc_review/${taskId}/transaction/alerts`
                            : `/view_task/${taskId}/transaction/alerts`}
                          className={`nav-link ${isActive('/transaction/alerts') ? 'active' : ''}`}
                        >
                          🚨 Alerts
                        </Link>
                        <Link
                          to={location.pathname.startsWith('/qc_review/') 
                            ? `/qc_review/${taskId}/transaction/explore`
                            : `/view_task/${taskId}/transaction/explore`}
                          className={`nav-link ${isActive('/transaction/explore') ? 'active' : ''}`}
                        >
                          🔎 Explore
                        </Link>
                        <Link
                          to={location.pathname.startsWith('/qc_review/') 
                            ? `/qc_review/${taskId}/transaction/ai`
                            : `/view_task/${taskId}/transaction/ai`}
                          className={`nav-link ${isActive('/transaction/ai') && !isActive('/transaction/ai-rationale') ? 'active' : ''}`}
                        >
                          🤖 AI Outreach
                        </Link>
                        <Link
                          to={location.pathname.startsWith('/qc_review/') 
                            ? `/qc_review/${taskId}/transaction/ai-rationale`
                            : `/view_task/${taskId}/transaction/ai-rationale`}
                          className={`nav-link ${isActive('/transaction/ai-rationale') ? 'active' : ''}`}
                        >
                          🧠 AI Rationale
                        </Link>
                      </nav>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
          
          {/* AI SME - direct link (not dropdown) - only on task view pages - independent of Transaction Review */}
          {isModuleEnabled('ai_sme') && isTaskViewPage && taskId && (
            <Link
              to={location.pathname.startsWith('/qc_review/') 
                ? `/qc_review/${taskId}/sme`
                : `/view_task/${taskId}/sme`}
              className={`nav-link ${isActive('/sme') && !isActive('/sme/referrals') ? 'active' : ''}`}
            >
              <i className="fas fa-brain"></i> AI SME
            </Link>
          )}
          
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
          </>
          )}
        </div>

        <div className="mt-auto px-2 pb-3">
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              handleLogout();
            }}
            className="nav-link text-danger d-flex align-items-center gap-2"
          >
            <i className="bi bi-box-arrow-right"></i>
            <span>Logout</span>
          </a>
        </div>
      </nav>
      <main className={`content-wrap ${isMyTasksPage || isDashboardPage ? 'no-left-padding' : ''}`}>{children}</main>
    </>
  );
}

export default BaseLayout;


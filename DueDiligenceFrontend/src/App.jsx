import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ModuleSettingsProvider } from './contexts/ModuleSettingsContext';
import { PermissionsProvider } from './contexts/PermissionsContext';
import { FieldVisibilityProvider } from './contexts/FieldVisibilityContext';
import PermissionGuard from './components/PermissionGuard';
import BaseLayout from './components/BaseLayout';
import Login from './components/Login';
import Verify2FA from './components/Verify2FA';
import ReviewerDashboard from './components/ReviewerDashboard';
import MyTasks from './components/MyTasks';
import QCLeadDashboard from './components/QCLeadDashboard';
import QCDashboard from './components/QCDashboard';
import TeamLeaderDashboard from './components/TeamLeaderDashboard';
import QADashboard from './components/QADashboard';
import SMEDashboard from './components/SMEDashboard';
import SMEReferrals from './components/SMEReferrals';
import AdminUserList from './components/AdminUserList';
import AdminInviteUser from './components/AdminInviteUser';
import EditUser from './components/EditUser';
import ReviewerPanel from './components/ReviewerPanel';
import OperationsDashboard from './components/OperationsDashboard';
import OperationsCases from './components/OperationsCases';
import AssignTasks from './components/AssignTasks';
import BulkAssignTasks from './components/BulkAssignTasks';
import SMEReview from './components/SMEReview';
import SamplingRatesConfig from './components/SamplingRatesConfig';
import QCAssignTasks from './components/QCAssignTasks';
import QCBulkAssignTasks from './components/QCBulkAssignTasks';
import QCReviewPanel from './components/QCReviewPanel';
import QCWIPCases from './components/QCWIPCases';
import QCReassignTasks from './components/QCReassignTasks';
import TransactionReviewWrapper from './components/TransactionReviewWrapper';
import AISMEWrapper from './components/AISMEWrapper';
import SumsubVerificationWrapper from './components/SumsubVerificationWrapper';
import MyReferrals from './components/MyReferrals';
import AISMEAdmin from './components/AISMEAdmin';
import TransactionReviewAdmin from './components/TransactionReviewAdmin';
import AdminModuleSettings from './components/AdminModuleSettings';
import AdminPermissions from './components/AdminPermissions';
import AdminFieldVisibility from './components/AdminFieldVisibility';
import AdminSettings from './components/AdminSettings';
import AdminTeamStructure from './components/AdminTeamStructure';
import ModuleGuard from './components/ModuleGuard';
import QCManualSampling from './components/QCManualSampling';
import OperationsPlanning from './components/OperationsPlanning';
import SearchResults from './components/SearchResults';
import './App.css';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function GoViewRedirect() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    if (taskId) {
      navigate(`/view_task/${taskId}`, { replace: true });
    }
  }, [taskId, navigate]);
  
  return <div>Redirecting...</div>;
}

function HomeRedirect() {
  const { user } = useAuth();
  const role = user?.role?.toLowerCase() || '';
  
  console.log('[HomeRedirect] User role:', role);
  
  // Match Flask app.py home() function exactly
  if (role === 'admin') {
    console.log('[HomeRedirect] Redirecting admin to /admin/users');
    return <Navigate to="/admin/users" replace />;
  } else if (role.startsWith('team_lead') || role === 'team_lead') {
    console.log('[HomeRedirect] Redirecting team_lead to /team_leader_dashboard');
    const level = role.includes('_') ? role.split('_').pop() : '1';
    return <Navigate to={`/team_leader_dashboard?level=${level}`} replace />;
  } else if (role === 'operations_manager' || role === 'operations') {
    console.log('[HomeRedirect] Redirecting operations to /operations_dashboard');
    return <Navigate to="/operations_dashboard" replace />;
  } else if (role.startsWith('reviewer') || role.startsWith('reviewer_')) {
    console.log('[HomeRedirect] Redirecting reviewer to /reviewer_dashboard');
    return <Navigate to="/reviewer_dashboard" replace />;
  } else if (['qc_1', 'qc_2', 'qc_3', 'qc_team_lead'].includes(role)) {
    console.log('[HomeRedirect] Redirecting QC team lead to /qc_lead_dashboard');
    return <Navigate to="/qc_lead_dashboard" replace />;
  } else if (role.startsWith('qc_review') || role === 'qc') {
    console.log('[HomeRedirect] Redirecting QC to /qc_dashboard');
    return <Navigate to="/qc_dashboard" replace />;
  } else if (role.startsWith('qa') || role === 'qa') {
    console.log('[HomeRedirect] Redirecting QA to /qa_dashboard');
    return <Navigate to="/qa_dashboard" replace />;
  } else if (role === 'sme') {
    console.log('[HomeRedirect] Redirecting SME to /sme_dashboard');
    return <Navigate to="/sme_dashboard" replace />;
  }
  
  console.log('[HomeRedirect] No role match for:', role, '- redirecting to /login');
  return <Navigate to="/login" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/verify_2fa" element={<Verify2FA />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <BaseLayout>
              <HomeRedirect />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/reviewer_dashboard"
        element={
          <PrivateRoute>
            <BaseLayout>
              <PermissionGuard feature="view_dashboard">
                <ReviewerDashboard />
              </PermissionGuard>
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/my_tasks"
        element={
          <PrivateRoute>
            <ModuleGuard module="due_diligence">
              <MyTasks />
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/my_referrals"
        element={
          <PrivateRoute>
            <BaseLayout>
              <MyReferrals />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/ai_sme/admin"
        element={
          <PrivateRoute>
            <ModuleGuard module="ai_sme">
              <BaseLayout>
                <AISMEAdmin />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/tx_review/admin"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewAdmin />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_lead_dashboard"
        element={
          <PrivateRoute>
            <BaseLayout>
              <PermissionGuard feature="view_dashboard">
                <QCLeadDashboard />
              </PermissionGuard>
            </BaseLayout>
          </PrivateRoute>
        }
      />
      {/* Placeholder routes for other dashboards */}
      <Route
        path="/qc_dashboard"
        element={
          <PrivateRoute>
            <BaseLayout>
              <PermissionGuard feature="view_dashboard">
                <QCDashboard />
              </PermissionGuard>
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/team_leader_dashboard"
        element={
          <PrivateRoute>
            <BaseLayout>
              <PermissionGuard feature="view_dashboard">
                <TeamLeaderDashboard />
              </PermissionGuard>
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/qa_dashboard"
        element={
          <PrivateRoute>
            <BaseLayout>
              <PermissionGuard feature="view_dashboard">
                <QADashboard />
              </PermissionGuard>
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/sme_dashboard"
        element={
          <PrivateRoute>
            <BaseLayout>
              <PermissionGuard feature="view_dashboard">
                <SMEDashboard />
              </PermissionGuard>
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/sme_referrals"
        element={
          <PrivateRoute>
            <BaseLayout>
              <SMEReferrals />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/users"
        element={
          <PrivateRoute>
            <PermissionGuard feature="edit_users" action="view">
              <BaseLayout>
                <AdminUserList />
              </BaseLayout>
            </PermissionGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/operations_dashboard"
        element={
          <PrivateRoute>
              <PermissionGuard feature="view_dashboard">
                <OperationsDashboard />
              </PermissionGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/ops/mi/cases"
        element={
          <PrivateRoute>
            <OperationsCases />
          </PrivateRoute>
        }
      />
      <Route
        path="/search"
        element={
          <PrivateRoute>
            <BaseLayout>
              <SearchResults />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/ops/mi/planning"
        element={
          <PrivateRoute>
            <ModuleGuard module="due_diligence">
              <OperationsPlanning />
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/invite-user"
        element={
          <PrivateRoute>
            <PermissionGuard feature="invite_users" action="edit">
              <BaseLayout>
                <AdminInviteUser />
              </BaseLayout>
            </PermissionGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/module-settings"
        element={
          <PrivateRoute>
            <BaseLayout>
              <AdminModuleSettings />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/permissions"
        element={
          <PrivateRoute>
            <BaseLayout>
              <AdminPermissions />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/field-visibility"
        element={
          <PrivateRoute>
            <BaseLayout>
              <AdminFieldVisibility />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <PrivateRoute>
            <BaseLayout>
              <AdminSettings />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/team-structure"
        element={
          <PrivateRoute>
            <BaseLayout>
              <AdminTeamStructure />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/edit-user/:userId"
        element={
          <PrivateRoute>
            <PermissionGuard feature="edit_users" action="edit">
              <EditUser />
            </PermissionGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc/sampling-rates"
        element={
          <PrivateRoute>
            <SamplingRatesConfig />
          </PrivateRoute>
        }
      />
      <Route
        path="/reviewer_panel/:taskId"
        element={
          <PrivateRoute>
            <PermissionGuard feature="review_tasks" action="view" fallbackFeature="review">
              <ReviewerPanel />
            </PermissionGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/view_task/:taskId"
        element={
          <PrivateRoute>
            <ModuleGuard module="due_diligence">
              <PermissionGuard feature="review_tasks" action="view" fallbackFeature="review">
                <BaseLayout>
                  <ReviewerPanel />
                </BaseLayout>
              </PermissionGuard>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      {/* Transaction Review routes - render in place of task view */}
      <Route
        path="/view_task/:taskId/transaction/dashboard"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="dashboard" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/view_task/:taskId/transaction/alerts"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="alerts" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/view_task/:taskId/transaction/explore"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="explore" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/view_task/:taskId/transaction/ai"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="ai" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/view_task/:taskId/transaction/ai-rationale"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="ai-rationale" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      {/* QC Review Transaction Review routes */}
      <Route
        path="/qc_review/:taskId/transaction/dashboard"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="dashboard" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId/transaction/alerts"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="alerts" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId/transaction/explore"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="explore" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId/transaction/ai"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="ai" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId/transaction/ai-rationale"
        element={
          <PrivateRoute>
            <ModuleGuard module="transaction_review">
              <BaseLayout>
                <TransactionReviewWrapper view="ai-rationale" />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      {/* AI SME routes */}
      <Route
        path="/view_task/:taskId/sme"
        element={
          <PrivateRoute>
            <ModuleGuard module="ai_sme">
              <BaseLayout>
                <AISMEWrapper />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId/sme"
        element={
          <PrivateRoute>
            <ModuleGuard module="ai_sme">
              <BaseLayout>
                <AISMEWrapper />
              </BaseLayout>
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/view_task/:taskId/sumsub"
        element={
          <PrivateRoute>
            <BaseLayout>
              <SumsubVerificationWrapper />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId/sumsub"
        element={
          <PrivateRoute>
            <BaseLayout>
              <SumsubVerificationWrapper />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      {/* Legacy Flask route redirect - catch /go/view and redirect to React route */}
      <Route
        path="/go/view/:taskId"
        element={
          <PrivateRoute>
            <GoViewRedirect />
          </PrivateRoute>
        }
      />
      <Route
        path="/assign_tasks"
        element={
          <PrivateRoute>
            <AssignTasks />
          </PrivateRoute>
        }
      />
      <Route
        path="/assign_tasks_bulk"
        element={
          <PrivateRoute>
            <BulkAssignTasks />
          </PrivateRoute>
        }
      />
      <Route
        path="/sme_review/:taskId"
        element={
          <PrivateRoute>
            <SMEReview />
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_manual_sampling"
        element={
          <PrivateRoute>
            <ModuleGuard module="due_diligence">
              <QCManualSampling />
            </ModuleGuard>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_assign_tasks"
        element={
          <PrivateRoute>
            <QCAssignTasks />
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_assign_tasks_bulk"
        element={
          <PrivateRoute>
            <QCBulkAssignTasks />
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_review/:taskId"
        element={
          <PrivateRoute>
            <BaseLayout>
              <QCReviewPanel />
            </BaseLayout>
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_wip_cases"
        element={
          <PrivateRoute>
            <QCWIPCases />
          </PrivateRoute>
        }
      />
      <Route
        path="/qc_reassign_tasks"
        element={
          <PrivateRoute>
            <QCReassignTasks />
          </PrivateRoute>
        }
      />
      {/* Catch-all route - redirect unknown paths */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <ModuleSettingsProvider>
        <PermissionsProvider>
          <FieldVisibilityProvider>
            <Router>
              <AppRoutes />
            </Router>
          </FieldVisibilityProvider>
        </PermissionsProvider>
      </ModuleSettingsProvider>
    </AuthProvider>
  );
}

export default App;

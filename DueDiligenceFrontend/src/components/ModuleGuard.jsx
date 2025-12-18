import { Navigate } from 'react-router-dom';
import { useModuleSettings } from '../contexts/ModuleSettingsContext';
import { useAuth } from '../contexts/AuthContext';

function ModuleGuard({ module, children, fallbackPath = '/' }) {
  const { isModuleEnabled, loading } = useModuleSettings();
  const { user } = useAuth();

  if (loading) {
    return <div className="container my-4"><div className="spinner-border" role="status"></div></div>;
  }

  if (!isModuleEnabled(module)) {
    // Get appropriate dashboard path based on role
    const getDashboardPath = () => {
      const role = user?.role?.toLowerCase() || '';
      if (role === 'admin') return '/admin/users';
      if (role.includes('operations_manager')) return '/operations_dashboard';
      if (role.startsWith('team_lead')) {
        const level = role.split('_').pop();
        return `/team_leader_dashboard?level=${level}`;
      }
      if (role.startsWith('reviewer')) return '/reviewer_dashboard';
      if (['qc_1', 'qc_2', 'qc_3'].includes(role)) return '/qc_lead_dashboard';
      if (role.startsWith('qc_review')) return '/qc_dashboard';
      if (role.startsWith('qa')) return '/qa_dashboard';
      if (role === 'sme') return '/sme_dashboard';
      return '/';
    };

    return (
      <div className="container my-4">
        <div className="alert alert-warning">
          <h4 className="alert-heading">Module Disabled</h4>
          <p>
            {module === 'due_diligence' 
              ? 'Due Diligence module is currently disabled. Only dashboards are available.'
              : `The ${module.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} module is currently disabled.`}
          </p>
          <p className="mb-0">
            <a href={getDashboardPath()} className="btn btn-primary">Go to Dashboard</a>
          </p>
        </div>
      </div>
    );
  }

  return children;
}

export default ModuleGuard;


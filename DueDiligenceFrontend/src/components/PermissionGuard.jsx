import React from 'react';
import { usePermissions } from '../contexts/PermissionsContext';

/**
 * PermissionGuard component - similar to ModuleGuard
 * Hides children if user doesn't have permission to view the feature
 */
function PermissionGuard({ feature, action = 'view', children, fallback = null, fallbackFeature = null }) {
  const { canView, canEdit, loading } = usePermissions();

  if (loading) {
    return <div className="container my-4"><div className="spinner-border" role="status"></div></div>;
  }

  let hasAccess = false;
  if (action === 'view') {
    hasAccess = canView(feature);
    // If no access and fallbackFeature is provided, check that too
    if (!hasAccess && fallbackFeature) {
      hasAccess = canView(fallbackFeature);
    }
  } else if (action === 'edit') {
    hasAccess = canEdit(feature);
    // If no access and fallbackFeature is provided, check that too
    if (!hasAccess && fallbackFeature) {
      hasAccess = canEdit(fallbackFeature);
    }
  }

  if (!hasAccess) {
    if (fallback !== null) {
      return fallback;
    }
    // Default fallback message
    return (
      <div className="container my-4">
        <div className="alert alert-warning">
          <h4 className="alert-heading">Access Denied</h4>
          <p className="mb-0">Access to this page is limited. Contact admin for approval.</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export default PermissionGuard;


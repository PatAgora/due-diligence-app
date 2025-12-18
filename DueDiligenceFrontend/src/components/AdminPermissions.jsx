import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { usePermissions } from '../contexts/PermissionsContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AdminPermissions() {
  const { user } = useAuth();
  const { refreshPermissions } = usePermissions();
  const [permissions, setPermissions] = useState({}); // { role_feature: { can_view, can_edit } }
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const roles = [
    'admin', 'team_lead_1', 'team_lead_2', 'team_lead_3',
    'reviewer_1', 'reviewer_2', 'reviewer_3',
    'qc_1', 'qc_2', 'qc_3', 'qc_review_1', 'qc_review_2', 'qc_review_3',
    'qa_1', 'qa_2', 'qa_3',
    'sme', 'operations_manager'
  ];

  const features = [
    { key: 'view_dashboard', label: 'View Dashboard' },
    { key: 'assign_tasks', label: 'Assign Tasks' },
    { key: 'review_tasks', label: 'Review Tasks' },
    { key: 'edit_users', label: 'Edit Users' },
    { key: 'reset_passwords', label: 'Reset Passwords' },
    { key: 'invite_users', label: 'Invite Users' },
    { key: 'view_qc_qa', label: 'View QC/QA' },
    { key: 'manage_settings', label: 'Manage Settings' }
  ];

  useEffect(() => {
    if (user?.role === 'admin') {
      fetchPermissions();
    }
  }, [user]);

  const fetchPermissions = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/admin/permissions`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Convert array to object for easier lookup: { "role_feature": { can_view, can_edit } }
          const permMap = {};
          (data.permissions || []).forEach(perm => {
            const key = `${perm.role}_${perm.feature}`;
            // Direct boolean conversion - API returns explicit booleans
            permMap[key] = {
              can_view: !!perm.can_view,
              can_edit: !!perm.can_edit
            };
          });
          
          // Debug: Check a few sample permissions
          console.log('Sample permissions loaded:');
          console.log('  team_lead_1_view_dashboard:', permMap['team_lead_1_view_dashboard']);
          console.log('  operations_manager_view_dashboard:', permMap['operations_manager_view_dashboard']);
          console.log('  qc_1_view_dashboard:', permMap['qc_1_view_dashboard']);
          console.log('  reviewer_1_view_dashboard:', permMap['reviewer_1_view_dashboard']);
          
          setPermissions(permMap);
        }
      } else {
        setMessage({ type: 'danger', text: 'Failed to load permissions' });
      }
    } catch (error) {
      console.error('Error fetching permissions:', error);
      setMessage({ type: 'danger', text: 'Error loading permissions' });
    } finally {
      setLoading(false);
    }
  };

  const getPermission = (role, feature) => {
    const key = `${role}_${feature}`;
    const perm = permissions[key] || { can_view: false, can_edit: false };
    // Ensure boolean values
    return {
      can_view: !!perm.can_view,
      can_edit: !!perm.can_edit
    };
  };

  const setPermission = (role, feature, field, value) => {
    const key = `${role}_${feature}`;
    setPermissions(prev => ({
      ...prev,
      [key]: {
        ...getPermission(role, feature),
        [field]: value
      }
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      // Convert permissions object back to array format
      const permissionsArray = [];
      roles.forEach(role => {
        features.forEach(feature => {
          const perm = getPermission(role, feature.key);
          // Force admin to always have all permissions enabled (even if someone tries to disable)
          const isAdmin = role === 'admin';
          permissionsArray.push({
            role: role,
            feature: feature.key,
            can_view: isAdmin ? true : perm.can_view,
            can_edit: isAdmin ? true : perm.can_edit
          });
        });
      });

      const response = await fetch(`${BASE_URL}/api/admin/permissions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          permissions: permissionsArray
        })
      });

      if (response.ok) {
        const data = await response.json();
        setMessage({ type: 'success', text: data.message || 'Permissions updated successfully' });
        // Refresh permissions context so changes take effect immediately
        if (refreshPermissions) {
          refreshPermissions();
        }
        // Refresh the page after a short delay to ensure all components pick up the changes
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to update permissions' }));
        setMessage({ type: 'danger', text: errorData.error || 'Failed to update permissions' });
      }
    } catch (error) {
      console.error('Error updating permissions:', error);
      setMessage({ type: 'danger', text: 'Error updating permissions' });
    } finally {
      setSaving(false);
    }
  };

  const formatRole = (role) => {
    return role.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  if (loading) {
    return (
      <div className="container-fluid my-4">
        <div className="text-center">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">
          <i className="bi bi-shield-check me-2"></i>
          Permissions Editor
        </h2>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type} alert-dismissible fade show`} role="alert">
          {message.text}
          <button
            type="button"
            className="btn-close"
            onClick={() => setMessage({ type: '', text: '' })}
            aria-label="Close"
          ></button>
        </div>
      )}

      <div className="card shadow-sm mb-4">
        <div className="card-header bg-primary text-white">
          <h5 className="mb-0">
            <i className="bi bi-table me-2"></i>
            Role-Based Permissions Matrix
          </h5>
        </div>
        <div className="card-body">
          <p className="text-muted mb-4">
            Configure permissions for each role. <strong>Can View</strong> allows access to the feature, 
            <strong> Can Edit</strong> allows modification. If both are unchecked, the feature is denied.
          </p>

          <form onSubmit={handleSubmit}>
            <div className="table-responsive" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
              <table className="table table-bordered table-hover align-middle" style={{ minWidth: '1200px' }}>
                <thead className="table-dark sticky-top" style={{ zIndex: 100 }}>
                  <tr>
                    <th style={{ position: 'sticky', left: 0, zIndex: 101, backgroundColor: '#212529', minWidth: '150px' }}>Role</th>
                    {features.map(feature => (
                      <th key={feature.key} className="text-center" style={{ minWidth: '150px' }}>
                        <div className="d-flex flex-column">
                          <span className="small fw-bold">{feature.label}</span>
                          <div className="d-flex justify-content-around mt-1">
                            <span className="badge bg-info" style={{ fontSize: '0.65rem' }}>View</span>
                            <span className="badge bg-success" style={{ fontSize: '0.65rem' }}>Edit</span>
                          </div>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {roles.map(role => {
                    const isAdmin = role === 'admin';
                    return (
                      <tr key={role} className={isAdmin ? 'table-warning' : ''}>
                        <td 
                          className="fw-semibold" 
                          style={{ position: 'sticky', left: 0, zIndex: 10, backgroundColor: isAdmin ? '#fff3cd' : 'white', minWidth: '150px' }}
                        >
                          {formatRole(role)}
                          {isAdmin && (
                            <span className="badge bg-danger ms-2" title="Admin permissions cannot be restricted">
                              Protected
                            </span>
                          )}
                        </td>
                        {features.map(feature => {
                          const perm = getPermission(role, feature.key);
                          return (
                            <td key={feature.key} className="text-center">
                              <div className="d-flex justify-content-around align-items-center">
                                <div className="form-check form-switch">
                                  <input
                                    className="form-check-input"
                                    type="checkbox"
                                    checked={isAdmin ? true : !!perm.can_view}
                                    onChange={(e) => !isAdmin && setPermission(role, feature.key, 'can_view', e.target.checked)}
                                    disabled={isAdmin}
                                    title={isAdmin ? "Admin always has access" : "Can View"}
                                  />
                                </div>
                                <div className="form-check form-switch">
                                  <input
                                    className="form-check-input"
                                    type="checkbox"
                                    checked={isAdmin ? true : !!perm.can_edit}
                                    onChange={(e) => !isAdmin && setPermission(role, feature.key, 'can_edit', e.target.checked)}
                                    disabled={isAdmin || (!isAdmin && !perm.can_view)}
                                    title={isAdmin ? "Admin always has access" : "Can Edit (requires Can View)"}
                                  />
                                </div>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="mt-4 pt-3 border-top">
              <button type="submit" className="btn btn-success btn-lg" disabled={saving}>
                {saving ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                    Saving...
                  </>
                ) : (
                  <>
                    <i className="bi bi-save me-2"></i>
                    Save Changes
                  </>
                )}
              </button>
              <button
                type="button"
                className="btn btn-outline-secondary btn-lg ms-2"
                onClick={fetchPermissions}
                disabled={saving}
              >
                <i className="bi bi-arrow-clockwise me-2"></i>
                Reset
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card shadow-sm">
        <div className="card-header bg-info text-white">
          <h6 className="mb-0">
            <i className="bi bi-info-circle me-2"></i>
            How Permissions Work
          </h6>
        </div>
        <div className="card-body">
          <ul className="mb-0">
            <li>
              <strong>Admin Protection:</strong> The <span className="badge bg-danger">Admin</span> role always has full access to all features 
              and cannot be restricted. Even if admin permissions are unchecked, admin will still have access.
            </li>
            <li>
              <strong>Can View:</strong> Allows the role to access and see the feature. If unchecked, the feature is completely hidden.
            </li>
            <li>
              <strong>Can Edit:</strong> Allows the role to modify/interact with the feature. Requires "Can View" to be enabled.
            </li>
            <li>
              <strong>Default Behavior:</strong> If no permission entry exists for a role/feature combination, 
              access is allowed by default (for backward compatibility).
            </li>
            <li>
              <strong>Changes Take Effect:</strong> After saving, users may need to refresh their browser to see permission changes.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default AdminPermissions;

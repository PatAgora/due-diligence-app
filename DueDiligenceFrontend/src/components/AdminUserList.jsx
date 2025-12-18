import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import { usePermissions } from '../contexts/PermissionsContext';
import './AdminUserList.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AdminUserList() {
  const { canView, canEdit } = usePermissions();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortOrder, setSortOrder] = useState('desc');
  const [inactiveDays, setInactiveDays] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetchUsers();
  }, [sortOrder, inactiveDays]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (sortOrder) params.append('sort', sortOrder);
      if (inactiveDays) params.append('inactive_days', inactiveDays);

      const response = await fetch(`${BASE_URL}/api/admin/users?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied. Admin role required.');
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setUsers(data.users || []);
    } catch (err) {
      console.error('Error fetching users:', err);
      setError(err.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilters = () => {
    fetchUsers();
  };

  const handleResetFilters = () => {
    setSortOrder('desc');
    setInactiveDays('');
  };

  const handleDeleteUser = async (userId, userName) => {
    if (!window.confirm(`Are you sure you want to delete user: ${userName}?`)) {
      return;
    }

    try {
      const response = await fetch(`${BASE_URL}/api/admin/user/${userId}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to delete user');
      }

      // Refresh the user list
      fetchUsers();
    } catch (err) {
      console.error('Error deleting user:', err);
      alert(`Error: ${err.message}`);
    }
  };

  const handleToggle2FA = async (userId, email) => {
    // Prevent toggling 2FA for admin@scrutinise.co.uk
    if (email.toLowerCase().trim() === 'admin@scrutinise.co.uk') {
      alert('2FA cannot be modified for this user.');
      return;
    }

    try {
      const response = await fetch(`${BASE_URL}/api/admin/users/${userId}/toggle_2fa`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to toggle 2FA');
      }

      const data = await response.json();
      // Refresh the user list
      fetchUsers();
      alert(`2FA ${data.two_factor_enabled ? 'enabled' : 'disabled'} for user.`);
    } catch (err) {
      console.error('Error toggling 2FA:', err);
      alert(`Error: ${err.message}`);
    }
  };

  const isUserInactive = (lastActive) => {
    if (!lastActive) return true; // Never logged in
    
    const lastActiveDate = new Date(lastActive);
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    
    return lastActiveDate <= sevenDaysAgo;
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

  if (error) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="alert alert-danger">
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={fetchUsers}>Retry</button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <>
      <div className="container my-4">
        <h2 className="mb-4">User Management</h2>

        <form className="mb-3 d-flex flex-wrap align-items-center gap-2" onSubmit={(e) => { e.preventDefault(); handleApplyFilters(); }}>
          <label className="form-label me-2 mb-0">Sort by Last Active:</label>
          <select 
            name="sort" 
            className="form-select w-auto"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
          >
            <option value="desc">Most Recent</option>
            <option value="asc">Least Recent</option>
          </select>

          <label className="form-label ms-4 me-2 mb-0">Inactive for more than:</label>
          <select 
            name="inactive_days" 
            className="form-select w-auto"
            value={inactiveDays}
            onChange={(e) => setInactiveDays(e.target.value)}
          >
            <option value="">--</option>
            <option value="7">7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
          </select>

          <button type="submit" className="btn btn-primary">Apply</button>
          <button type="button" className="btn btn-secondary" onClick={handleResetFilters}>Reset</button>
        </form>

        {canEdit('invite_users') && (
          <button className="btn btn-success mb-3" onClick={() => navigate('/admin/invite-user')}>
            Create New User
          </button>
        )}

        <div className="card shadow-sm">
          <div className="card-body">
            {users.length === 0 ? (
              <div className="alert alert-info mb-0">
                <i className="bi bi-info-circle me-2"></i>
                No users found.
              </div>
            ) : (
              <div className="table-responsive">
                <table className="table table-striped table-hover align-middle">
                  <thead className="table-dark">
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Reporting Line</th>
                      <th>Last Active</th>
                      <th>2FA</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id} className={isUserInactive(user.last_active) ? 'table-warning' : ''}>
                        <td>{user.id}</td>
                        <td>{user.name || '—'}</td>
                        <td>{user.email}</td>
                        <td>{user.role?.replace(/_/g, ' ') || '—'}</td>
                        <td>{user.team_lead || '—'}</td>
                        <td>{user.last_active || '—'}</td>
                        <td>
                          {user.email.toLowerCase().trim() === 'admin@scrutinise.co.uk' ? (
                            <span className="text-muted">N/A</span>
                          ) : (
                            <button
                              className={`btn btn-sm ${user.two_factor_enabled ? 'btn-success' : 'btn-outline-secondary'}`}
                              onClick={() => handleToggle2FA(user.id, user.email)}
                              title={user.two_factor_enabled ? '2FA Enabled - Click to disable' : '2FA Disabled - Click to enable'}
                            >
                              {user.two_factor_enabled ? (
                                <><i className="bi bi-shield-check me-1"></i>On</>
                              ) : (
                                <><i className="bi bi-shield me-1"></i>Off</>
                              )}
                            </button>
                          )}
                        </td>
                        <td>
                          {canEdit('edit_users') && (
                            <>
                              <button
                                className="btn btn-sm btn-primary me-1"
                                onClick={() => navigate(`/admin/edit-user/${user.id}`)}
                              >
                                Edit
                              </button>
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => handleDeleteUser(user.id, user.name || user.email)}
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default AdminUserList;


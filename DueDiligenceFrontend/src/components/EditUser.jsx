import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import { usePermissions } from '../contexts/PermissionsContext';
import './EditUser.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function EditUser() {
  const { canEdit } = usePermissions();
  const { userId } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    role: '',
    team_lead: ''
  });

  useEffect(() => {
    fetchUserData();
  }, [userId]);

  const fetchUserData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${BASE_URL}/api/admin/user/${userId}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load user data');
      }

      const data = await response.json();
      setUser(data.user);
      setLeads(data.leads || []);
      setFormData({
        name: data.user.name || '',
        email: data.user.email || '',
        role: data.user.role || '',
        team_lead: data.user.team_lead || ''
      });
    } catch (err) {
      console.error('Error fetching user:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const response = await fetch(`${BASE_URL}/api/admin/user/${userId}`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to update user');
      }

      alert('User updated successfully!');
      navigate('/admin/users');
    } catch (err) {
      console.error('Error updating user:', err);
      setError(err.message);
    } finally {
      setSaving(false);
    }
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

  if (error && !user) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="alert alert-danger">
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={() => navigate('/admin/users')}>
              Back to Users
            </button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container my-4">
        <h2 className="mb-4">Edit User</h2>

        {error && (
          <div className="alert alert-danger alert-dismissible fade show" role="alert">
            {error}
            <button type="button" className="btn-close" onClick={() => setError(null)}></button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="row g-3">
          <div className="col-md-6">
            <label htmlFor="name" className="form-label">Full Name</label>
            <input
              type="text"
              className="form-control"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="col-md-6">
            <label htmlFor="email" className="form-label">Email</label>
            <input
              type="email"
              className="form-control"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="col-md-6">
            <label htmlFor="role" className="form-label">Role</label>
            <select
              className="form-select"
              name="role"
              id="role"
              value={formData.role}
              onChange={handleChange}
              required
            >
              <option value="">-- Select Role --</option>
              
              <optgroup label="Team Leads">
                <option value="team_lead_1">Team Lead (Level 1)</option>
                <option value="team_lead_2">Team Lead (Level 2)</option>
                <option value="team_lead_3">Team Lead (Level 3)</option>
                <option value="qc_1">QC Team Lead (Level 1)</option>
                <option value="qc_2">QC Team Lead (Level 2)</option>
                <option value="qc_3">QC Team Lead (Level 3)</option>
                <option value="qa_1">QA Team Lead (Level 1)</option>
                <option value="qa_2">QA Team Lead (Level 2)</option>
                <option value="qa_3">QA Team Lead (Level 3)</option>
              </optgroup>

              <optgroup label="QC Reviewers">
                <option value="qc_review_1">QC Reviewer (Level 1)</option>
                <option value="qc_review_2">QC Reviewer (Level 2)</option>
                <option value="qc_review_3">QC Reviewer (Level 3)</option>
              </optgroup>

              <optgroup label="Reviewers">
                <option value="reviewer_1">Reviewer (Level 1)</option>
                <option value="reviewer_2">Reviewer (Level 2)</option>
                <option value="reviewer_3">Reviewer (Level 3)</option>
              </optgroup>

              <optgroup label="Other Roles">
                <option value="qc">QC Reviewer (Legacy)</option>
                <option value="qa">QA Reviewer (Legacy)</option>
                <option value="sme">Subject Matter Expert</option>
                <option value="operations_manager">Operations Manager</option>
                <option value="admin">Admin</option>
              </optgroup>
            </select>
          </div>

          <div className="col-md-6">
            <label htmlFor="team_lead" className="form-label">Reporting To (Team Lead)</label>
            <select
              className="form-select"
              name="team_lead"
              id="team_lead"
              value={formData.team_lead}
              onChange={handleChange}
            >
              <option value="">-- None --</option>
              {leads.map((lead, idx) => (
                lead.name && lead.name !== 'None' && (
                  <option key={idx} value={lead.name}>
                    {lead.name}
                  </option>
                )
              ))}
            </select>
          </div>

          <div className="col-12 mt-3">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2"></span>
                  Updating...
                </>
              ) : (
                'Update User'
              )}
            </button>
            <button
              type="button"
              className="btn btn-secondary ms-2"
              onClick={() => navigate('/admin/users')}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </BaseLayout>
  );
}

export default EditUser;


import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import { usePermissions } from '../contexts/PermissionsContext';
import './AdminInviteUser.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function AdminInviteUser() {
  const { canEdit } = usePermissions();
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    role: '',
    team_lead: '',
    password: 'password123'
  });
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetchLeads();
  }, []);

  const fetchLeads = async () => {
    try {
      const response = await fetch(`${BASE_URL}/api/admin/leads`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (response.ok) {
        const data = await response.json();
        setLeads(data.leads || []);
      }
    } catch (err) {
      console.error('Error fetching leads:', err);
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
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${BASE_URL}/api/admin/invite_user`, {
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
        throw new Error(data.error || 'Failed to invite user');
      }

      setSuccess(true);
      setTimeout(() => navigate('/admin/users'), 2000);
    } catch (err) {
      console.error('Error inviting user:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseLayout>
      <div className="container mt-5">
        <h2 className="mb-4">Create New User</h2>

        {success && (
          <div className="alert alert-success">
            <i className="bi bi-check-circle me-2"></i>
            User created successfully! Redirecting...
          </div>
        )}

        {error && (
          <div className="alert alert-danger">
            <i className="bi bi-exclamation-triangle me-2"></i>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label htmlFor="email" className="form-label">Email Address</label>
            <input type="email" name="email" className="form-control" value={formData.email} onChange={handleChange} required />
          </div>

          <div className="mb-3">
            <label htmlFor="name" className="form-label">Full Name</label>
            <input type="text" name="name" className="form-control" placeholder="Optional name" value={formData.name} onChange={handleChange} />
          </div>

          <div className="mb-3">
            <label htmlFor="role" className="form-label">Role</label>
            <select name="role" className="form-select" value={formData.role} onChange={handleChange} required>
              <option value="">Select Role</option>

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
                <option value="qa">QA Reviewer (Legacy)</option>
                <option value="qc">QC Reviewer (Legacy)</option>
                <option value="sme">Subject Matter Expert (SME)</option>
                <option value="operations_manager">Operations Manager</option>
                <option value="admin">Admin</option>
              </optgroup>
            </select>
          </div>

          <div className="mb-3">
            <label htmlFor="team_lead" className="form-label">Team Lead (if applicable)</label>
            <select name="team_lead" className="form-select" value={formData.team_lead} onChange={handleChange}>
              <option value="">-- None --</option>
              {leads.map((lead, idx) => (
                lead.name && (
                  <option key={idx} value={lead.name}>
                    {lead.name}
                  </option>
                )
              ))}
            </select>
          </div>

          <div className="mb-3">
            <label htmlFor="password" className="form-label">Initial Password</label>
            <input type="text" name="password" className="form-control" value={formData.password} onChange={handleChange} required />
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                Creating...
              </>
            ) : (
              'Create User'
            )}
          </button>
        </form>
      </div>
    </BaseLayout>
  );
}

export default AdminInviteUser;


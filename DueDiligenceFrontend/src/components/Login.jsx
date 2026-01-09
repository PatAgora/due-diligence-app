import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authAPI } from '../services/api';
import './Login.css';

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await authAPI.login(email, password);
      
      // Check if 2FA is required
      if (result.requires_2fa) {
        // Redirect to 2FA verification page
        navigate('/verify_2fa');
        return;
      }
      
      // Set user state immediately before navigation
      login(result.user, result.token);
      
      // Redirect based on role (matching Flask app.py login() function exactly)
      const role = result.user?.role?.toLowerCase() || '';
      console.log('[LOGIN] Redirecting user with role:', role);
      
      if (role === 'admin') {
        navigate('/admin/users');
      } else if (role === 'operations' || role === 'operations_manager') {
        navigate('/operations_dashboard');
      } else if (['qc_1', 'qc_2', 'qc_3', 'qc_team_lead'].includes(role)) {
        navigate('/qc_lead_dashboard');
      } else if (role.startsWith('qc_review') || role === 'qc') {
        navigate('/qc_dashboard');
      } else if (role.startsWith('team_lead') || role === 'team_lead') {
        const level = role.includes('_') ? role.split('_').pop() : '1';
        navigate(`/team_leader_dashboard?level=${level}`);
      } else if (role.startsWith('reviewer') || role.startsWith('reviewer_')) {
        navigate('/reviewer_dashboard');
      } else if (role === 'qa' || role.startsWith('qa')) {
        navigate('/qa_dashboard');
      } else if (role === 'sme') {
        navigate('/sme_dashboard');
      } else {
        console.log('[LOGIN] No specific route for role:', role, '- going to home');
        navigate('/');
      }
    } catch (err) {
      setError(err.message || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        {/* Left: branding */}
        <div className="auth-left">
          <div className="logo-wrapper">
            <img
              key="login-logo"
              src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='56' height='56' viewBox='0 0 66 66'><g fill='none' stroke='%23F89D43' stroke-width='5'><circle cx='28' cy='28' r='18'/><line x1='41' y1='41' x2='62' y2='62' stroke-linecap='round'/></g></svg>"
              alt="Scrutinise Logo"
            />
          </div>
          <h1 className="brand-title">
            <span>Scrutinise</span>
            <span className="highlight">Due Diligence</span>
          </h1>
          <div className="tagline">Financial Crime Due Diligence Workflow and Reporting</div>
          <div className="feature">
            <i className="bi bi-speedometer2"></i>
            <span>Real-time Analytics</span>
          </div>
          <div className="feature">
            <i className="bi bi-journal-check"></i>
            <span>Regulatory Standard Audit Trails</span>
          </div>
          <div className="feature">
            <i className="bi bi-diagram-3"></i>
            <span>Customisable Workflows</span>
          </div>
        </div>

        {/* Right: form */}
        <div className="auth-right">
          <div className="login-box">
            <div className="brand-mark">
              <span className="mark-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="7"></circle>
                  <line x1="16.5" y1="16.5" x2="22" y2="22" strokeLinecap="round"></line>
                </svg>
              </span>
              <span>Scrutinise</span>
            </div>
            <h3>Welcome</h3>
            <div className="subcopy">Sign in to access your Due Diligence workflow and analytics tool</div>

            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="email" className="form-label">Email address</label>
                <input
                  type="email"
                  className="form-control"
                  id="email"
                  name="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="mb-3">
                <label htmlFor="password" className="form-label">Password</label>
                <input
                  type="password"
                  className="form-control"
                  id="password"
                  name="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <div className="forgot-password">
                  <Link to="/forgot_password">Forgot your password?</Link>
                </div>
              </div>
              {error && (
                <div className="alert alert-danger mt-3">{error}</div>
              )}
              <div className="d-grid">
                <button type="submit" className="btn btn-login" disabled={loading}>
                  {loading ? 'Signing In...' : 'Sign In'}
                </button>
              </div>
            </form>

            <div className="legal">
              <hr />
              <div> 2025 Scrutinise</div>
              <div className="badges">
                <div className="badge-item">
                  <i className="bi bi-award-fill"></i> ISO 27001 Certified
                </div>
                <div className="badge-item">
                  <i className="bi bi-shield-lock-fill"></i> Enterprise Security
                </div>
                <div className="badge-item">
                  <i className="bi bi-globe2"></i> Global Compliance
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;


import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authAPI } from '../services/api';
import './Login.css';

function Verify2FA() {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (!code || code.length !== 6 || !/^\d+$/.test(code)) {
      setError('Please enter a valid 6-digit code');
      return;
    }
    
    setLoading(true);

    try {
      const result = await authAPI.verify2FA(code);
      login(result.user, result.token);
      
      // Redirect based on role (matching Flask app.py login() function exactly)
      const role = result.user?.role?.toLowerCase() || '';
      if (role === 'admin') {
        navigate('/admin/users');
      } else if (['qc_1', 'qc_2', 'qc_3'].includes(role)) {
        navigate('/qc_lead_dashboard');
      } else if (role.startsWith('qc_review')) {
        navigate('/qc_dashboard');
      } else if (role.startsWith('team_lead')) {
        const level = role.split('_').pop();
        navigate(`/team_leader_dashboard?level=${level}`);
      } else if (role.startsWith('reviewer')) {
        navigate('/reviewer_dashboard');
      } else if (role === 'qa') {
        navigate('/qa_dashboard');
      } else if (role === 'sme') {
        navigate('/sme_dashboard');
      } else {
        navigate('/');
      }
    } catch (err) {
      setError(err.message || 'Invalid or expired code');
      setCode('');
    } finally {
      setLoading(false);
    }
  };

  const handleCodeChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
    setCode(value);
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        {/* Left: branding */}
        <div className="auth-left">
          <div className="logo-wrapper">
            <img
              src="/img/mag-glass.png"
              alt="Scrutinise Logo"
              onError={(e) => {
                e.target.onerror = null;
                e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 66 66"><g fill="none" stroke="%23ff6a00" stroke-width="5"><circle cx="28" cy="28" r="18"/><line x1="41" y1="41" x2="62" y2="62" stroke-linecap="round"/></g></svg>';
              }}
            />
          </div>
          <h1 className="brand-title">
            <span>Scrutinise</span>
            <span className="highlight">Due Diligence</span>
          </h1>
          <div className="tagline">Two-Factor Authentication</div>
          <div className="feature">
            <i className="bi bi-shield-lock-fill"></i>
            <span>Enhanced Security</span>
          </div>
          <div className="feature">
            <i className="bi bi-envelope-check"></i>
            <span>Email Verification</span>
          </div>
          <div className="feature">
            <i className="bi bi-clock-history"></i>
            <span>Code Expires in 10 Minutes</span>
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
            <h3>Verify Your Identity</h3>
            <div className="subcopy">Enter the 6-digit code sent to your email</div>

            <form onSubmit={handleSubmit}>
              {error && (
                <div className="alert alert-danger mt-3" role="alert">
                  {error}
                </div>
              )}

              <div className="mb-3">
                <label htmlFor="code" className="form-label">Verification Code</label>
                <input
                  type="text"
                  id="code"
                  className="form-control"
                  placeholder="000000"
                  value={code}
                  onChange={handleCodeChange}
                  maxLength={6}
                  autoComplete="one-time-code"
                  autoFocus
                  disabled={loading}
                  style={{
                    fontSize: '28px',
                    letterSpacing: '12px',
                    textAlign: 'center',
                    fontFamily: 'monospace',
                    fontWeight: '600',
                    height: '64px'
                  }}
                />
                <div className="form-text text-center mt-2" style={{ fontSize: '0.85rem', color: '#8b8f97' }}>
                  Check your email for the verification code
                </div>
              </div>

              <div className="d-grid">
                <button
                  type="submit"
                  className="btn btn-login"
                  disabled={loading || code.length !== 6}
                >
                  {loading ? 'Verifying...' : 'Verify Code'}
                </button>
              </div>

              <div className="text-center mt-3">
                <button
                  type="button"
                  className="btn btn-link p-0"
                  onClick={() => navigate('/login')}
                  disabled={loading}
                  style={{
                    color: '#0a1e3c',
                    textDecoration: 'none',
                    fontSize: '0.9rem'
                  }}
                >
                  Back to Login
                </button>
              </div>
            </form>

            <div className="legal">
              <hr />
              <div>© 2025 Scrutinise</div>
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

export default Verify2FA;


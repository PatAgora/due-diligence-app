import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function AdminModuleSettings() {
  const { user } = useAuth();
  const [settings, setSettings] = useState({
    due_diligence: true,
    transaction_review: true,
    ai_sme: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    if (user?.role === 'admin') {
      fetchSettings();
    }
  }, [user]);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/admin/module_settings`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.settings) {
          setSettings(data.settings);
        }
      } else {
        setMessage({ type: 'danger', text: 'Failed to load module settings' });
      }
    } catch (error) {
      console.error('Error fetching module settings:', error);
      setMessage({ type: 'danger', text: 'Error loading module settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (module) => {
    setSettings(prev => ({
      ...prev,
      [module]: !prev[module]
    }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await fetch(`${BASE_URL}/api/admin/module_settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          settings: settings
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setMessage({ type: 'success', text: 'Module settings updated successfully' });
          // Reload page after 1 second to reflect changes
          setTimeout(() => {
            window.location.reload();
          }, 1000);
        } else {
          setMessage({ type: 'danger', text: data.error || 'Failed to update settings' });
        }
      } else {
        const errorData = await response.json();
        setMessage({ type: 'danger', text: errorData.error || 'Failed to update settings' });
      }
    } catch (error) {
      console.error('Error saving module settings:', error);
      setMessage({ type: 'danger', text: 'Error saving module settings' });
    } finally {
      setSaving(false);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="container my-4">
        <div className="alert alert-danger">
          <h4>Access Denied</h4>
          <p>Only administrators can access module settings.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="container my-4">
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  const moduleInfo = {
    due_diligence: {
      name: 'Due Diligence',
      description: 'Core task management system. When disabled, only dashboards are visible. All task-related features are disabled.',
      icon: 'bi-clipboard-check'
    },
    transaction_review: {
      name: 'Transaction Review',
      description: 'Transaction analysis and alerting module. When disabled, Transaction Review features are hidden from task pages.',
      icon: 'bi-arrow-repeat'
    },
    ai_sme: {
      name: 'AI SME',
      description: 'AI-powered SME assistant for answering questions. When disabled, AI SME chat is hidden from task pages.',
      icon: 'fas fa-brain'
    }
  };

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">
          <i className="bi bi-gear me-2"></i>
          Module Settings
        </h2>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type} alert-dismissible fade show`} role="alert">
          {message.text}
          <button
            type="button"
            className="btn-close"
            onClick={() => setMessage({ type: '', text: '' })}
          ></button>
        </div>
      )}

      <div className="card shadow-sm">
        <div className="card-header bg-primary text-white">
          <h5 className="mb-0">
            <i className="bi bi-toggle-on me-2"></i>
            Enable/Disable Modules
          </h5>
        </div>
        <div className="card-body">
          <p className="text-muted mb-4">
            Control which modules are available to users. Only administrators can modify these settings.
          </p>

          {Object.keys(moduleInfo).map((moduleKey) => {
            const info = moduleInfo[moduleKey];
            const isEnabled = settings[moduleKey];

            return (
              <div key={moduleKey} className="card mb-3 border">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start">
                    <div className="flex-grow-1">
                      <div className="d-flex align-items-center mb-2">
                        <i className={`${info.icon} me-2 fs-4`}></i>
                        <h5 className="mb-0">{info.name}</h5>
                        <span className={`badge ms-3 ${isEnabled ? 'bg-success' : 'bg-secondary'}`}>
                          {isEnabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>
                      <p className="text-muted mb-0 small">{info.description}</p>
                    </div>
                    <div className="ms-3">
                      <div className="form-check form-switch">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          role="switch"
                          id={`toggle-${moduleKey}`}
                          checked={isEnabled}
                          onChange={() => handleToggle(moduleKey)}
                          style={{ width: '3rem', height: '1.5rem' }}
                        />
                        <label className="form-check-label" htmlFor={`toggle-${moduleKey}`}>
                          {isEnabled ? 'ON' : 'OFF'}
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          <div className="mt-4 pt-3 border-top">
            <button
              className="btn btn-primary btn-lg"
              onClick={handleSave}
              disabled={saving}
            >
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
              className="btn btn-outline-secondary btn-lg ms-2"
              onClick={fetchSettings}
              disabled={saving}
            >
              <i className="bi bi-arrow-clockwise me-2"></i>
              Reset
            </button>
          </div>
        </div>
      </div>

      <div className="card shadow-sm mt-4">
        <div className="card-header bg-info text-white">
          <h6 className="mb-0">
            <i className="bi bi-info-circle me-2"></i>
            Important Notes
          </h6>
        </div>
        <div className="card-body">
          <ul className="mb-0">
            <li>
              <strong>Due Diligence:</strong> When disabled, users can only view their dashboards. 
              All task management features (viewing tasks, assigning tasks, reviewing tasks) are disabled.
            </li>
            <li>
              <strong>Transaction Review:</strong> When disabled, Transaction Review links and features 
              are hidden from task pages and the sidebar.
            </li>
            <li>
              <strong>AI SME:</strong> When disabled, AI SME chat links are hidden from task pages and the sidebar.
            </li>
            <li>
              Changes take effect immediately after saving. Users may need to refresh their browser to see changes.
            </li>
            <li>
              Existing data is preserved when modules are disabled. No data is deleted.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default AdminModuleSettings;


import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AdminSettings() {
  const { user } = useAuth();
  const [settings, setSettings] = useState({
    rework_overdue_days: '5',
    default_task_limit: '50',
    password_expiry_days: '90'
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
      const response = await fetch(`${BASE_URL}/api/admin/settings`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.settings) {
          setSettings(prev => ({
            rework_overdue_days: data.settings.rework_overdue_days || prev.rework_overdue_days,
            default_task_limit: data.settings.default_task_limit || prev.default_task_limit,
            password_expiry_days: data.settings.password_expiry_days || prev.password_expiry_days
          }));
        }
      } else {
        setMessage({ type: 'danger', text: 'Failed to load settings' });
      }
    } catch (error) {
      console.error('Error fetching settings:', error);
      setMessage({ type: 'danger', text: 'Error loading settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await fetch(`${BASE_URL}/api/admin/settings`, {
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
        setMessage({ type: 'success', text: data.message || 'Settings updated successfully' });
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to update settings' }));
        setMessage({ type: 'danger', text: errorData.error || 'Failed to update settings' });
      }
    } catch (error) {
      console.error('Error updating settings:', error);
      setMessage({ type: 'danger', text: 'Error updating settings' });
    } finally {
      setSaving(false);
    }
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
        <h2 className="fw-bold mb-0">System Settings</h2>
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

      <form onSubmit={handleSubmit} className="card shadow-sm">
        <div className="card-body">
          <div className="mb-3">
            <label htmlFor="rework_overdue_days" className="form-label">Rework Overdue Days</label>
            <input
              type="number"
              className="form-control"
              id="rework_overdue_days"
              value={settings.rework_overdue_days}
              onChange={(e) => handleChange('rework_overdue_days', e.target.value)}
              min="1"
            />
            <small className="form-text text-muted">Number of days before rework is considered overdue</small>
          </div>

          <div className="mb-3">
            <label htmlFor="default_task_limit" className="form-label">Default Reviewer Task Limit</label>
            <input
              type="number"
              className="form-control"
              id="default_task_limit"
              value={settings.default_task_limit}
              onChange={(e) => handleChange('default_task_limit', e.target.value)}
              min="1"
            />
            <small className="form-text text-muted">Default maximum number of tasks a reviewer can have assigned</small>
          </div>

          <div className="mb-3">
            <label htmlFor="password_expiry_days" className="form-label">Password Expiry Interval (days)</label>
            <input
              type="number"
              className="form-control"
              id="password_expiry_days"
              value={settings.password_expiry_days}
              onChange={(e) => handleChange('password_expiry_days', e.target.value)}
              min="1"
            />
            <small className="form-text text-muted">Number of days before passwords expire</small>
          </div>
        </div>
        <div className="card-footer">
          <button type="submit" className="btn btn-success" disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default AdminSettings;


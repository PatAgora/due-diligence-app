import React, { useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function AISMEAdminConfig() {
  const [config, setConfig] = useState({
    bot_name: '',
    auto_yes_ms: 30000
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [showSources, setShowSources] = useState(false);

  useEffect(() => {
    loadConfig();
    // Load local storage setting for show sources
    const saved = localStorage.getItem('show_sources');
    setShowSources(saved === '1');
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/sme/admin/config`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.data) {
          setConfig({
            bot_name: data.data.bot_name || 'Assistant',
            auto_yes_ms: data.data.auto_yes_ms || 30000
          });
        }
      }
    } catch (error) {
      console.error('Error loading config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setResult(null);
      
      const formData = new FormData();
      if (config.bot_name.trim()) formData.append('bot_name', config.bot_name.trim());
      if (config.auto_yes_ms) formData.append('auto_yes_ms', config.auto_yes_ms);

      const response = await fetch(`${BASE_URL}/api/sme/admin/config`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      if (data.status === 'ok') {
        setResult({ type: 'success', message: 'Settings saved successfully!' });
      } else {
        setResult({ type: 'error', message: data.message || 'Failed to save settings' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message || 'Failed to save settings' });
    } finally {
      setSaving(false);
      setTimeout(() => setResult(null), 4000);
    }
  };

  const handleShowSourcesChange = (e) => {
    const checked = e.target.checked;
    setShowSources(checked);
    localStorage.setItem('show_sources', checked ? '1' : '0');
  };

  return (
    <div>
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Bot Configuration</h5>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSave}>
              <div className="mb-3">
                <label htmlFor="bot_name" className="form-label">Bot Name</label>
                <input
                  type="text"
                  className="form-control"
                  id="bot_name"
                  value={config.bot_name}
                  onChange={(e) => setConfig({ ...config, bot_name: e.target.value })}
                  placeholder="Assistant"
                  maxLength={48}
                />
                <small className="text-muted">Name shown in the chat interface (1-48 characters)</small>
              </div>

              <div className="mb-3">
                <label htmlFor="auto_yes_ms" className="form-label">Auto-Yes Timer (milliseconds)</label>
                <input
                  type="number"
                  className="form-control"
                  id="auto_yes_ms"
                  value={config.auto_yes_ms}
                  onChange={(e) => setConfig({ ...config, auto_yes_ms: parseInt(e.target.value) || 30000 })}
                  min="5000"
                  max="300000"
                  step="1000"
                />
                <small className="text-muted">
                  If the user doesn't pick Yes/No within this time, the answer is auto-counted as "Yes".
                  Range: 5,000 - 300,000 ms (5 seconds - 5 minutes)
                </small>
              </div>

              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving...' : 'Save Settings'}
              </button>
              
              {result && (
                <div className={`alert alert-${result.type === 'success' ? 'success' : 'danger'} mt-3`}>
                  {result.message}
                </div>
              )}
            </form>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h5 className="mb-0">Browser Settings</h5>
        </div>
        <div className="card-body">
          <div className="form-check">
            <input
              className="form-check-input"
              type="checkbox"
              id="show_sources"
              checked={showSources}
              onChange={handleShowSourcesChange}
            />
            <label className="form-check-label" htmlFor="show_sources">
              Show guidance sources under answers (for all users on this browser)
            </label>
          </div>
          <small className="text-muted">
            This setting is stored in your browser's local storage and affects how answers are displayed for you.
          </small>
        </div>
      </div>
    </div>
  );
}

export default AISMEAdminConfig;


import React, { useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function TransactionReviewConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [newKeyword, setNewKeyword] = useState('');
  const [countries, setCountries] = useState([]);
  const [newCountry, setNewCountry] = useState({ iso2: '', risk_level: 'MEDIUM', score: 0, prohibited: false });

  useEffect(() => {
    loadConfig();
    loadCountries();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/tx_review/admin/config`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Error loading config:', error);
      setResult({ type: 'error', message: 'Failed to load configuration' });
    } finally {
      setLoading(false);
    }
  };

  const loadCountries = async () => {
    try {
      const response = await fetch(`${BASE_URL}/api/tx_review/admin/countries`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setCountries(data.data || []);
      }
    } catch (error) {
      console.error('Error loading countries:', error);
    }
  };

  const handleSaveParams = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setResult(null);
      
      const formData = new FormData(e.target);
      const response = await fetch(`${BASE_URL}/api/tx_review/admin/config/params`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        setResult({ type: 'success', message: 'Parameters saved successfully!' });
        loadConfig();
      } else {
        setResult({ type: 'error', message: 'Failed to save parameters' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message || 'Failed to save parameters' });
    } finally {
      setSaving(false);
      setTimeout(() => setResult(null), 4000);
    }
  };

  const handleSaveToggles = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setResult(null);
      
      const formData = new FormData(e.target);
      const response = await fetch(`${BASE_URL}/api/tx_review/admin/config/toggles`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        setResult({ type: 'success', message: 'Rule toggles saved successfully!' });
        loadConfig();
      } else {
        setResult({ type: 'error', message: 'Failed to save toggles' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message || 'Failed to save toggles' });
    } finally {
      setSaving(false);
      setTimeout(() => setResult(null), 4000);
    }
  };

  const handleKeywordAction = async (action, term = '') => {
    try {
      const formData = new FormData();
      formData.append('action', action);
      if (action === 'add') {
        formData.append('new_term', newKeyword);
      } else {
        formData.append('term', term);
      }

      const response = await fetch(`${BASE_URL}/api/tx_review/admin/keywords`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        setNewKeyword('');
        loadConfig();
      }
    } catch (error) {
      console.error('Error managing keywords:', error);
    }
  };

  const handleCountrySubmit = async (e) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append('iso2', newCountry.iso2.toUpperCase());
      formData.append('risk_level', newCountry.risk_level);
      formData.append('score', newCountry.score);
      if (newCountry.prohibited) formData.append('prohibited', 'on');

      const response = await fetch(`${BASE_URL}/api/tx_review/admin/countries`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        setNewCountry({ iso2: '', risk_level: 'MEDIUM', score: 0, prohibited: false });
        loadCountries();
      }
    } catch (error) {
      console.error('Error adding country:', error);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="alert alert-danger">
        Failed to load configuration. Please ensure Transaction Review service is running.
      </div>
    );
  }

  const params = config.params || {};
  const toggles = config.toggles || {};

  return (
    <div>
      {/* Rule Parameters */}
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Rule Parameters</h5>
        </div>
        <div className="card-body">
          <form onSubmit={handleSaveParams}>
            <div className="row g-3 mb-3">
              <div className="col-md-3">
                <label className="form-label">High-risk min amount (£)</label>
                <input
                  type="number"
                  step="0.01"
                  className="form-control"
                  name="cfg_high_risk_min_amount"
                  defaultValue={params.cfg_high_risk_min_amount}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Outlier vs median (×)</label>
                <input
                  type="number"
                  step="0.1"
                  className="form-control"
                  name="cfg_median_multiplier"
                  defaultValue={params.cfg_median_multiplier}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Expected OUT factor (×)</label>
                <input
                  type="number"
                  step="0.1"
                  className="form-control"
                  name="cfg_expected_out_factor"
                  defaultValue={params.cfg_expected_out_factor}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Expected IN factor (×)</label>
                <input
                  type="number"
                  step="0.1"
                  className="form-control"
                  name="cfg_expected_in_factor"
                  defaultValue={params.cfg_expected_in_factor}
                />
              </div>
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-3">
                <label className="form-label">Cash daily limit (£, global)</label>
                <input
                  type="number"
                  step="0.01"
                  className="form-control"
                  name="cfg_cash_daily_limit"
                  defaultValue={params.cfg_cash_daily_limit}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Severity: Critical ≥</label>
                <input
                  type="number"
                  className="form-control"
                  name="cfg_sev_critical"
                  defaultValue={params.cfg_sev_critical}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Severity: High ≥</label>
                <input
                  type="number"
                  className="form-control"
                  name="cfg_sev_high"
                  defaultValue={params.cfg_sev_high}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Severity: Medium ≥</label>
                <input
                  type="number"
                  className="form-control"
                  name="cfg_sev_medium"
                  defaultValue={params.cfg_sev_medium}
                />
              </div>
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-3">
                <label className="form-label">Severity: Low ≥</label>
                <input
                  type="number"
                  className="form-control"
                  name="cfg_sev_low"
                  defaultValue={params.cfg_sev_low}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">AI Model</label>
                <input
                  type="text"
                  className="form-control"
                  name="cfg_ai_model"
                  defaultValue={params.cfg_ai_model}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Use LLM</label>
                <div className="form-check mt-2">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    name="cfg_ai_use_llm"
                    defaultChecked={params.cfg_ai_use_llm}
                  />
                  <label className="form-check-label">Enable AI/LLM</label>
                </div>
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save Parameters'}
            </button>
          </form>
          {result && (
            <div className={`alert alert-${result.type === 'success' ? 'success' : 'danger'} mt-3`}>
              {result.message}
            </div>
          )}
        </div>
      </div>

      {/* Rule Toggles */}
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Rule Toggles</h5>
        </div>
        <div className="card-body">
          <form onSubmit={handleSaveToggles}>
            <div className="row g-3">
              {Object.entries(toggles).map(([key, value]) => (
                <div key={key} className="col-md-3">
                  <div className="form-check">
                    <input
                      type="checkbox"
                      className="form-check-input"
                      name={`enable_${key}`}
                      defaultChecked={value}
                    />
                    <label className="form-check-label">
                      {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <button type="submit" className="btn btn-primary mt-3" disabled={saving}>
              {saving ? 'Saving...' : 'Save Toggles'}
            </button>
          </form>
        </div>
      </div>

      {/* Keyword Library */}
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Keyword Library (Narrative Risk)</h5>
        </div>
        <div className="card-body">
          <div className="d-flex gap-2 mb-3">
            <input
              type="text"
              className="form-control"
              placeholder="Add keyword…"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
            />
            <button
              className="btn btn-success"
              onClick={() => handleKeywordAction('add')}
              disabled={!newKeyword.trim()}
            >
              Add
            </button>
          </div>
          <div className="table-responsive">
            <table className="table table-sm table-striped">
              <thead>
                <tr>
                  <th>Keyword</th>
                  <th>Enabled</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(params.cfg_risky_terms2 || []).map((term, idx) => (
                  <tr key={idx}>
                    <td>{term.term || term}</td>
                    <td>
                      <span className={`badge ${term.enabled !== false ? 'bg-success' : 'bg-secondary'}`}>
                        {term.enabled !== false ? 'Enabled' : 'Disabled'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn btn-sm btn-outline-primary me-1"
                        onClick={() => handleKeywordAction('toggle', term.term || term)}
                      >
                        Toggle
                      </button>
                      <button
                        className="btn btn-sm btn-outline-danger"
                        onClick={() => handleKeywordAction('delete', term.term || term)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Country Risk Management */}
      <div className="card">
        <div className="card-header">
          <h5 className="mb-0">Country Risk Management</h5>
        </div>
        <div className="card-body">
          <form onSubmit={handleCountrySubmit} className="mb-4">
            <div className="row g-3">
              <div className="col-md-2">
                <label className="form-label">ISO2 Code</label>
                <input
                  type="text"
                  className="form-control"
                  maxLength="2"
                  value={newCountry.iso2}
                  onChange={(e) => setNewCountry({ ...newCountry, iso2: e.target.value.toUpperCase() })}
                  required
                />
              </div>
              <div className="col-md-3">
                <label className="form-label">Risk Level</label>
                <select
                  className="form-select"
                  value={newCountry.risk_level}
                  onChange={(e) => setNewCountry({ ...newCountry, risk_level: e.target.value })}
                >
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="HIGH_3RD">HIGH_3RD</option>
                  <option value="PROHIBITED">PROHIBITED</option>
                </select>
              </div>
              <div className="col-md-2">
                <label className="form-label">Score</label>
                <input
                  type="number"
                  className="form-control"
                  value={newCountry.score}
                  onChange={(e) => setNewCountry({ ...newCountry, score: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div className="col-md-2">
                <label className="form-label">Prohibited</label>
                <div className="form-check mt-2">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    checked={newCountry.prohibited}
                    onChange={(e) => setNewCountry({ ...newCountry, prohibited: e.target.checked })}
                  />
                </div>
              </div>
              <div className="col-md-3">
                <label className="form-label">&nbsp;</label>
                <button type="submit" className="btn btn-primary d-block">
                  Add Country
                </button>
              </div>
            </div>
          </form>
          <div className="table-responsive">
            <table className="table table-sm table-striped">
              <thead>
                <tr>
                  <th>ISO2</th>
                  <th>Risk Level</th>
                  <th>Score</th>
                  <th>Prohibited</th>
                </tr>
              </thead>
              <tbody>
                {countries.map((country) => (
                  <tr key={country.iso2}>
                    <td>{country.iso2}</td>
                    <td>
                      <span className={`badge ${
                        country.risk_level === 'PROHIBITED' ? 'bg-danger' :
                        country.risk_level === 'HIGH' || country.risk_level === 'HIGH_3RD' ? 'bg-warning' :
                        country.risk_level === 'MEDIUM' ? 'bg-info' : 'bg-success'
                      }`}>
                        {country.risk_level}
                      </span>
                    </td>
                    <td>{country.score}</td>
                    <td>{country.prohibited ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TransactionReviewConfig;


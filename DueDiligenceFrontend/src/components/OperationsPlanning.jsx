import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './OperationsPlanning.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function OperationsPlanning() {
  const navigate = useNavigate();
  const [weeks, setWeeks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchPlanningData();
  }, []);

  const fetchPlanningData = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await fetch(`${BASE_URL}/api/ops/planning`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load planning data');
      }

      const data = await response.json();
      setWeeks(data.weeks || []);
    } catch (err) {
      console.error('Error fetching planning data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleForecastChange = (weekValue, value) => {
    setWeeks(prevWeeks => 
      prevWeeks.map(w => 
        w.value === weekValue 
          ? { ...w, forecast: value === '' ? 0 : parseInt(value) || 0 }
          : w
      )
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (saving) return;

    try {
      setSaving(true);
      setError('');

      const forecasts = {};
      weeks.forEach(w => {
        forecasts[`forecast_${w.value}`] = w.forecast || 0;
      });

      const formData = new FormData();
      Object.keys(forecasts).forEach(key => {
        formData.append(key, forecasts[key]);
      });

      const response = await fetch(`${BASE_URL}/api/ops/planning`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        alert('Forecasts updated successfully');
        navigate('/operations_dashboard');
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to save forecasts' }));
        setError(errorData.error || 'Failed to save forecasts');
      }
    } catch (err) {
      console.error('Error saving forecasts:', err);
      setError('Error saving forecasts. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="text-center py-5">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

  if (error && !weeks.length) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="alert alert-danger">{error}</div>
          <button className="btn btn-secondary" onClick={fetchPlanningData}>
            Retry
          </button>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container my-4">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <div>
            <h1 className="fw-bold mb-2">Forecast Planning</h1>
            <p className="text-muted mb-0">
              We've generated the next 6 months of weeks for you. Enter your planned volumes; leave blank for 0.
            </p>
          </div>
          <button
            className="btn btn-outline-secondary"
            onClick={() => navigate('/operations_dashboard')}
          >
            <i className="bi bi-arrow-left me-2"></i>
            Back to Dashboard
          </button>
        </div>

        {error && (
          <div className="alert alert-warning alert-dismissible fade show" role="alert">
            {error}
            <button
              type="button"
              className="btn-close"
              onClick={() => setError('')}
              aria-label="Close"
            ></button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="table-responsive">
          <table className="table table-bordered align-middle">
            <thead className="table-light">
              <tr>
                <th style={{ width: '30%' }}>Week Start</th>
                <th style={{ width: '70%' }}>Forecast Count</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((week) => (
                <tr key={week.value}>
                  <td>{week.label}</td>
                  <td>
                    <input
                      type="number"
                      name={`forecast_${week.value}`}
                      className="form-control"
                      min="0"
                      placeholder="0"
                      value={week.forecast || ''}
                      onChange={(e) => handleForecastChange(week.value, e.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-3">
            <button
              type="submit"
              className="btn btn-success"
              disabled={saving}
            >
              {saving ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                  Saving...
                </>
              ) : (
                <>
                  <i className="bi bi-check-circle me-2"></i>
                  Save All Forecasts
                </>
              )}
            </button>
            <button
              type="button"
              className="btn btn-secondary ms-2"
              onClick={() => navigate('/operations_dashboard')}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </BaseLayout>
  );
}

export default OperationsPlanning;


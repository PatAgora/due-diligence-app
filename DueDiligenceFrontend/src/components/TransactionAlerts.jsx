import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function TransactionAlerts({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [severityFilter, setSeverityFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');

  useEffect(() => {
    if (customerId) {
      fetchAlerts();
    }
  }, [customerId, severityFilter, tagFilter]);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      let url = `${BASE_URL}/api/transaction/alerts?customer_id=${customerId}`;
      if (severityFilter) url += `&severity=${severityFilter}`;
      if (tagFilter) url += `&tag=${tagFilter}`;
      
      const response = await fetch(url, { credentials: 'include' });

      if (!response.ok) {
        throw new Error('Failed to fetch alerts');
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBackToTask = () => {
    const basePath = window.location.pathname.startsWith('/qc_review/') 
      ? `/qc_review/${taskId}`
      : `/view_task/${taskId}`;
    navigate(basePath);
  };

  const getSeverityBadgeClass = (severity) => {
    const s = (severity || '').toUpperCase();
    if (s === 'CRITICAL') return 'danger';
    if (s === 'HIGH') return 'warning';
    if (s === 'MEDIUM') return 'info';
    if (s === 'LOW') return 'secondary';
    return 'secondary';
  };

  if (loading) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="text-center">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="alert alert-danger">
          <h5>Error loading alerts</h5>
          <p>{error}</p>
          <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4 px-5" style={{ paddingTop: '60px' }}>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h2 className="fw-bold mb-0">Transaction Alerts</h2>
        <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
          <i className="bi bi-arrow-left"></i> Back to Task
        </button>
      </div>

      {/* Filters */}
      <div className="row g-2 mb-3">
        <div className="col-auto">
          <label className="form-label">Severity</label>
          <select 
            className="form-select" 
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="">All</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
            <option value="INFO">Info</option>
          </select>
        </div>
        <div className="col-auto">
          <label className="form-label">Tag</label>
          <select 
            className="form-select" 
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
          >
            <option value="">All</option>
            {data?.available_tags?.map(tag => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="card">
        <div className="card-body">
          {data?.alerts && data.alerts.length > 0 ? (
            <div className="table-responsive">
              <table className="table table-striped table-hover">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Transaction ID</th>
                    <th>Severity</th>
                    <th>Score</th>
                    <th>Reasons</th>
                    <th>Tags</th>
                    <th>Country</th>
                  </tr>
                </thead>
                <tbody>
                  {data.alerts.map((alert, idx) => (
                    <tr key={idx}>
                      <td>{alert.txn_date || alert.created_at}</td>
                      <td className="text-monospace small">{alert.txn_id}</td>
                      <td>
                        <span className={`badge bg-${getSeverityBadgeClass(alert.severity)}`}>
                          {alert.severity}
                        </span>
                      </td>
                      <td>{alert.score}</td>
                      <td>{alert.reasons || '—'}</td>
                      <td>{alert.rule_tags || '—'}</td>
                      <td>{alert.country_iso2 || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted">No alerts found for this customer.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default TransactionAlerts;

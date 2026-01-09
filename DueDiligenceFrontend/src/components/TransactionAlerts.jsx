import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function TransactionAlerts({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [severityFilter, setSeverityFilter] = useState('');

  useEffect(() => {
    if (customerId) {
      fetchAlerts();
    }
  }, [customerId, severityFilter]);

  const getSeverityOrder = (severity) => {
    const s = (severity || '').toUpperCase();
    if (s === 'CRITICAL') return 0;
    if (s === 'HIGH') return 1;
    if (s === 'MEDIUM') return 2;
    if (s === 'LOW') return 3;
    return 4;
  };

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      let url = `${BASE_URL}/api/transaction/alerts?customer_id=${customerId}`;
      if (severityFilter) url += `&severity=${severityFilter}`;
      
      const response = await fetch(url, { credentials: 'include' });

      if (!response.ok) {
        throw new Error('Failed to fetch alerts');
      }

      const result = await response.json();
      
      // Debug logging
      console.log('[TransactionAlerts] Raw API response:', JSON.stringify(result, null, 2));
      if (result.alerts && result.alerts.length > 0) {
        console.log('[TransactionAlerts] First alert fields:', {
          transaction_id: result.alerts[0].transaction_id,
          amount: result.alerts[0].amount,
          currency: result.alerts[0].currency,
          transaction_date: result.alerts[0].transaction_date,
          severity: result.alerts[0].severity,
          country_iso2: result.alerts[0].country_iso2
        });
      }
      
      // Sort alerts by severity (CRITICAL, HIGH, MEDIUM, LOW)
      if (result.alerts) {
        result.alerts.sort((a, b) => {
          const orderA = getSeverityOrder(a.severity);
          const orderB = getSeverityOrder(b.severity);
          return orderA - orderB;
        });
      }
      
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
    if (s === 'CRITICAL') return 'danger';  // Red
    if (s === 'HIGH') return 'danger';      // Red
    if (s === 'MEDIUM') return 'warning';   // Orange
    if (s === 'LOW') return 'success';      // Green (changed from grey)
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
                    <th>Amount</th>
                    <th>Country</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {data.alerts.map((alert, idx) => {
                    const isHighRisk = alert.risk_score > 0.7;
                    return (
                      <tr key={idx}>
                        <td>{alert.transaction_date || alert.created_at?.split(' ')[0] || '—'}</td>
                        <td className="text-monospace small">{alert.transaction_id || '—'}</td>
                        <td>
                          <span className={`badge bg-${getSeverityBadgeClass(alert.severity)}`}>
                            {alert.severity}
                          </span>
                        </td>
                        <td>
                          {alert.amount && alert.currency ? (
                            <span>
                              {alert.currency} {parseFloat(alert.amount || 0).toLocaleString('en-GB', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                              })}
                            </span>
                          ) : '—'}
                        </td>
                        <td>
                          {isHighRisk && '🔴 '}
                          {alert.country_iso2 || '—'}
                        </td>
                        <td style={{ maxWidth: '400px' }}>
                          <div style={{ 
                            whiteSpace: 'normal',
                            wordWrap: 'break-word'
                          }}>
                            {alert.reasons || '—'}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted">No alerts found for this customer.</p>
          )}
          
          {data?.alerts && data.alerts.length > 0 && (
            <div className="mt-3 text-muted small">
              <strong>Total Alerts:</strong> {data.alerts.length}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TransactionAlerts;

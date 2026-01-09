import React, { useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function AISMEAdminFeedback() {
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState('all');

  useEffect(() => {
    loadFeedback();
  }, [range]);

  const loadFeedback = async () => {
    try {
      setLoading(true);
      const url = range === 'all'
        ? '${BASE_URL}/api/sme/admin/feedback/data'
        : `${BASE_URL}/api/sme/admin/feedback/data?range=${range}`;
      
      const response = await fetch(url, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setFeedback(data);
      }
    } catch (error) {
      console.error('Error loading feedback:', error);
    } finally {
      setLoading(false);
    }
  };

  const totals = feedback?.totals || {};
  const yes = Number(totals.yes || 0);
  const no = Number(totals.no || 0);
  const total = yes + no;
  const rate = total > 0 ? (yes / total) * 100 : 0;
  const recent = feedback?.recent || [];

  return (
    <div>
      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Feedback Analytics</h5>
          <div className="d-flex gap-2">
            <select
              className="form-select form-select-sm"
              value={range}
              onChange={(e) => setRange(e.target.value)}
              style={{ width: 'auto' }}
            >
              <option value="all">All Time</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
            </select>
            <a
              href={`${BASE_URL}/api/sme/admin/feedback/export?fmt=json${range !== 'all' ? `&range=${range}` : ''}`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export JSON
            </a>
            <a
              href={`${BASE_URL}/api/sme/admin/feedback/export?fmt=csv${range !== 'all' ? `&range=${range}` : ''}`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export CSV
            </a>
          </div>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : (
            <>
              <div className="row mb-4">
                <div className="col-md-4">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <h3>{total}</h3>
                      <small className="text-muted">Total Responses</small>
                    </div>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="card bg-success bg-opacity-10">
                    <div className="card-body text-center">
                      <h3 className="text-success">{yes}</h3>
                      <small className="text-muted">Yes</small>
                    </div>
                  </div>
                </div>
                <div className="col-md-4">
                  <div className="card bg-danger bg-opacity-10">
                    <div className="card-body text-center">
                      <h3 className="text-danger">{no}</h3>
                      <small className="text-muted">No</small>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mb-4">
                <h6>Yes Rate: {rate.toFixed(1)}%</h6>
                <div className="progress" style={{ height: '30px' }}>
                  <div
                    className="progress-bar bg-success"
                    role="progressbar"
                    style={{ width: `${rate}%` }}
                  >
                    {rate.toFixed(1)}%
                  </div>
                </div>
              </div>

              {feedback?.daily && feedback.daily.length > 0 && (
                <div className="mb-4">
                  <h6>Daily Trend</h6>
                  <div className="table-responsive">
                    <table className="table table-sm">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Yes</th>
                          <th>No</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {feedback.daily.slice(0, 10).map((day, idx) => (
                          <tr key={idx}>
                            <td>{day.date || '—'}</td>
                            <td>{day.yes || 0}</td>
                            <td>{day.no || 0}</td>
                            <td>{(day.yes || 0) + (day.no || 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {recent.length > 0 && (
                <div>
                  <h6>Recent Feedback</h6>
                  <div className="list-group">
                    {recent.slice(0, 20).map((item, idx) => (
                      <div key={idx} className="list-group-item">
                        <div className="d-flex justify-content-between align-items-start">
                          <div className="flex-grow-1">
                            <p className="mb-1">{item.question || '—'}</p>
                            <small className="text-muted">
                              {item.ts ? new Date(item.ts).toLocaleString() : '—'}
                              {item.user && ` • User: ${item.user}`}
                            </small>
                          </div>
                          <span className={`badge ${item.helpful ? 'bg-success' : 'bg-danger'}`}>
                            {item.helpful ? 'Yes' : 'No'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default AISMEAdminFeedback;


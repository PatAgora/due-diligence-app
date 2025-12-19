import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import { Doughnut, Line } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import '../styles/agora-theme.css';
import './QADashboard.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

// Register Chart.js components
ChartJS.register(ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

function QADashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dateRange, setDateRange] = useState('wtd');
  const navigate = useNavigate();

  useEffect(() => {
    fetchQAData();
  }, [dateRange]);

  const fetchQAData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${BASE_URL}/api/qa_dashboard?date_range=${dateRange}`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        },
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied. QA role required.');
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const dashboardData = await response.json();
      setData(dashboardData);
    } catch (err) {
      console.error('Error fetching QA dashboard data:', err);
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="container-fluid my-4">
          <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

  if (error) {
    return (
      <BaseLayout>
        <div className="container-fluid my-4">
          <div className="alert alert-danger">
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={fetchQAData}>
              Retry
            </button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  const entries = data?.entries || [];

  return (
    <BaseLayout>
      <div className="container-fluid my-4">
          <h1 className="fw-bold mb-4" style={{ color: 'var(--agora-navy)' }}>QA Dashboard</h1>

          {/* Date filter */}
          <div className="d-flex gap-2 align-items-center mb-4">
            <select
              className="agora-form-select"
              style={{ maxWidth: '180px' }}
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
            >
              <option value="wtd">Current Week</option>
              <option value="prevw">Previous Week</option>
              <option value="30d">Last 30 Days</option>
              <option value="all">All Time</option>
            </select>
          </div>

          {/* KPI tiles */}
          <div className="row g-3 mb-4">
            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-orange">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">Total QA Tasks</span>
                  <i className="bi bi-clipboard-check agora-kpi-icon icon-orange"></i>
                </div>
                <div className="agora-kpi-metric">{data?.total_qa_tasks || 0}</div>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-amber">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">Pending Review</span>
                  <i className="bi bi-hourglass-split agora-kpi-icon icon-amber"></i>
                </div>
                <div className="agora-kpi-metric">{data?.pending_qa || 0}</div>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-green">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">Completed</span>
                  <i className="bi bi-check-circle agora-kpi-icon icon-green"></i>
                </div>
                <div className="agora-kpi-metric">{data?.completed_qa || 0}</div>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-cyan">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">Avg Review Time</span>
                  <i className="bi bi-clock-history agora-kpi-icon icon-cyan"></i>
                </div>
                <div className="agora-kpi-metric">{data?.avg_review_time?.toFixed(1) || 0}h</div>
              </div>
            </div>
          </div>

          {/* Charts row */}
          <div className="row g-4 mb-4">
            {/* QA Outcomes Chart */}
            <div className="col-lg-6">
              <div className="agora-card">
                <div className="agora-card-header">QA Outcomes</div>
                <div className="agora-card-body">
                  <div style={{ position: 'relative', height: '300px' }}>
                    {data?.outcomes && Object.keys(data.outcomes).length > 0 ? (
                      <Doughnut
                        data={{
                          labels: Object.keys(data.outcomes),
                          datasets: [{
                            data: Object.values(data.outcomes),
                            backgroundColor: [
                              '#10b981', // Pass - green
                              '#ef4444', // Fail - red
                              '#f59e0b', // Pending - amber
                              '#06b6d4', // Other - cyan
                            ],
                            borderWidth: 2,
                            borderColor: '#fff'
                          }]
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: {
                              position: 'bottom'
                            },
                            tooltip: {
                              callbacks: {
                                label: (context) => {
                                  const label = context.label || '';
                                  const value = context.parsed || 0;
                                  const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                  const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                  return `${label}: ${value} (${percentage}%)`;
                                }
                              }
                            }
                          },
                          cutout: '60%'
                        }}
                      />
                    ) : (
                      <div className="d-flex align-items-center justify-content-center h-100">
                        <p className="text-muted">No outcome data available</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Review Trend Chart */}
            <div className="col-lg-6">
              <div className="agora-card">
                <div className="agora-card-header">Review Trend</div>
                <div className="agora-card-body">
                  <div style={{ position: 'relative', height: '300px' }}>
                    {data?.daily_labels && data.daily_labels.length > 0 ? (
                      <Line
                        data={{
                          labels: data.daily_labels,
                          datasets: [{
                            label: 'Reviews Completed',
                            data: data.daily_counts,
                            borderColor: '#F89D43',
                            backgroundColor: 'rgba(248, 157, 67, 0.1)',
                            tension: 0.3,
                            fill: true
                          }]
                        }}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: {
                            legend: { display: false },
                            title: { display: false }
                          },
                          scales: {
                            y: {
                              beginAtZero: true,
                              ticks: { precision: 0 },
                              grid: { color: '#e5e7eb' }
                            },
                            x: {
                              grid: { color: '#e5e7eb' }
                            }
                          }
                        }}
                      />
                    ) : (
                      <div className="d-flex align-items-center justify-content-center h-100">
                        <p className="text-muted">No trend data available</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Recent QA Reviews Table */}
          <div className="agora-card">
            <div className="agora-card-header">Recent QA Reviews</div>
            <div className="agora-card-body">
              {entries.length === 0 ? (
                <div className="agora-alert agora-alert-info mb-0">
                  <i className="bi bi-info-circle me-2"></i>
                  No QA tasks available.
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="agora-table">
                    <thead>
                      <tr>
                        <th>Task ID</th>
                        <th>Status</th>
                        <th>QA Outcome</th>
                        <th>QA Comment</th>
                        <th>Last Updated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entries.slice(0, 10).map((row) => (
                        <tr
                          key={row.task_id}
                          onClick={() => navigate(`/view_task/${row.task_id}`)}
                          style={{ cursor: 'pointer' }}
                        >
                          <td className="fw-semibold">{row.task_id}</td>
                          <td>
                            <span className={`agora-badge ${row.status === 'Completed' ? 'agora-badge-success' : 'agora-badge-warning'}`}>
                              {row.status}
                            </span>
                          </td>
                          <td>{row.qa_outcome || <span className="text-muted">Pending</span>}</td>
                          <td className="text-truncate" style={{ maxWidth: '300px' }}>
                            {row.qa_comment || <span className="text-muted">—</span>}
                          </td>
                          <td>{row.updated_at ? new Date(row.updated_at).toLocaleDateString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

export default QADashboard;

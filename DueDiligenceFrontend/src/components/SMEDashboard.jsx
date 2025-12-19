import { useState, useEffect } from 'react';
import BaseLayout from './BaseLayout';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import '../styles/agora-theme.css';
import './SMEDashboard.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

function SMEDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dateRange, setDateRange] = useState('wtd');

  useEffect(() => {
    fetchDashboard();
  }, [dateRange]);

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `${BASE_URL}/api/sme_dashboard?date_range=${dateRange}`,
        {
          credentials: 'include',
          headers: { 'Accept': 'application/json' },
        }
      );

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied. SME role required.');
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const dashboardData = await response.json();
      setData(dashboardData);
    } catch (err) {
      console.error('Error fetching SME dashboard:', err);
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="agora-main-content">
          <div className="agora-container">
            <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
              <div className="spinner-border" style={{ color: 'var(--agora-orange)' }} role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

  if (error) {
    return (
      <BaseLayout>
        <div className="agora-main-content">
          <div className="agora-container">
            <div className="agora-alert agora-alert-danger">
              <h4 className="alert-heading">Error</h4>
              <p>{error}</p>
              <button className="agora-btn agora-btn-primary" onClick={fetchDashboard}>Retry</button>
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="agora-main-content">
        <div className="agora-container">
          <h1 className="fw-bold mb-4" style={{ color: 'var(--agora-navy)' }}>SME Dashboard</h1>

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
                  <span className="agora-kpi-label">SME Queue (Live)</span>
                  <i className="bi bi-inbox agora-kpi-icon icon-orange"></i>
                </div>
                <div className="agora-kpi-metric">{data.open_queue || 0}</div>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-green">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">New Referrals</span>
                  <i className="bi bi-arrow-right-circle agora-kpi-icon icon-green"></i>
                </div>
                <div className="agora-kpi-metric">{data.total_new_referrals || 0}</div>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-cyan">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">Returned to Reviewer</span>
                  <i className="bi bi-arrow-left-circle agora-kpi-icon icon-cyan"></i>
                </div>
                <div className="agora-kpi-metric">{data.total_returned || 0}</div>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-3">
              <div className="agora-kpi-card accent-amber">
                <div className="agora-kpi-top">
                  <span className="agora-kpi-label">Avg TAT (days)</span>
                  <i className="bi bi-clock agora-kpi-icon icon-amber"></i>
                </div>
                <div className="agora-kpi-metric">{data.avg_tat?.toFixed(1) || 0}</div>
              </div>
            </div>
          </div>

          {/* Charts */}
          <div className="row g-4">
            <div className="col-lg-6">
              <div className="agora-card">
                <div className="agora-card-header">SME Output (Returns per Day)</div>
                <div className="agora-card-body">
                  <div style={{ position: 'relative', height: '300px' }}>
                    {data.daily_labels && data.daily_labels.length > 0 ? (
                      <Line
                        data={{
                          labels: data.daily_labels,
                          datasets: [{
                            label: 'Returns',
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
                        <p className="text-muted">No daily output data available</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="col-lg-6">
              <div className="agora-card">
                <div className="agora-card-header">Case Stage & Age Profile</div>
                <div className="agora-card-body">
                  <div className="table-responsive">
                    <table className="agora-table">
                      <thead>
                        <tr>
                          <th>Status</th>
                          <th className="text-center">1-2 Days</th>
                          <th className="text-center">3-5 Days</th>
                          <th className="text-center">5+ Days</th>
                          <th className="text-end">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data?.age_rows && data.age_rows.length > 0 ? (
                          data.age_rows.map((row, idx) => {
                            const ages = row.age_buckets || {};
                            const a12 = ages['1–2 days'] || 0;
                            const a35 = ages['3–5 days'] || 0;
                            const a5p = ages['5 days+'] || 0;
                            const total = a12 + a35 + a5p;
                            return (
                              <tr key={idx}>
                                <td className="fw-semibold">{row.status}</td>
                                <td className="text-center">
                                  <span className={`agora-badge ${a12 > 0 ? 'agora-badge-success' : 'agora-badge-info'}`}>
                                    {a12}
                                  </span>
                                </td>
                                <td className="text-center">
                                  <span className={`agora-badge ${a35 > 0 ? 'agora-badge-warning' : 'agora-badge-info'}`}>
                                    {a35}
                                  </span>
                                </td>
                                <td className="text-center">
                                  <span className={`agora-badge ${a5p > 0 ? 'agora-badge-danger' : 'agora-badge-info'}`}>
                                    {a5p}
                                  </span>
                                </td>
                                <td className="text-end fw-bold">{total}</td>
                              </tr>
                            );
                          })
                        ) : (
                          <tr>
                            <td colSpan="5" className="text-center text-muted py-4">
                              No age profile data available
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default SMEDashboard;


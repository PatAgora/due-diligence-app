import { useState, useEffect } from 'react';
import BaseLayout from './BaseLayout';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
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
        <div className="container my-4">
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
        <div className="container my-4">
          <div className="alert alert-danger">
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={fetchDashboard}>Retry</button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container my-4">
        <h1 className="fw-bold mb-2">SME Dashboard</h1>

        {/* Date filter */}
        <div className="d-flex gap-2 align-items-center mb-4">
          <select
            className="form-select form-select-sm"
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
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>SME Queue (Live)</h6>
                <div className="num">{data.open_queue || 0}</div>
              </div>
            </div>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>New Referrals</h6>
                <div className="num">{data.total_new_referrals || 0}</div>
              </div>
            </div>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Returned to Reviewer</h6>
                <div className="num">{data.total_returned || 0}</div>
              </div>
            </div>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Avg TAT (days)</h6>
                <div className="num">{data.avg_tat?.toFixed(1) || 0}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Charts would go here - requires Chart.js integration */}
        <div className="row g-4">
          <div className="col-lg-6">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title">SME Output (Returns per Day)</h5>
                <div style={{ position: 'relative', height: '300px' }}>
                  {data.daily_labels && data.daily_labels.length > 0 ? (
                    <Line
                      data={{
                        labels: data.daily_labels,
                        datasets: [{
                          label: 'Returns',
                          data: data.daily_counts,
                          borderColor: '#17a2b8',
                          backgroundColor: 'rgba(23, 162, 184, 0.1)',
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
                            ticks: { precision: 0 }
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
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title">Case Stage & Age Profile</h5>
                <div className="table-responsive">
                  <table className="table table-sm table-hover align-middle">
                    <thead className="table-light">
                      <tr className="text-uppercase small text-secondary">
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
                                <span className={`badge ${a12 > 0 ? 'bg-success' : 'bg-light text-muted'}`}>
                                  {a12}
                                </span>
                              </td>
                              <td className="text-center">
                                <span className={`badge ${a35 > 0 ? 'bg-warning' : 'bg-light text-muted'}`}>
                                  {a35}
                                </span>
                              </td>
                              <td className="text-center">
                                <span className={`badge ${a5p > 0 ? 'bg-danger' : 'bg-light text-muted'}`}>
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
    </BaseLayout>
  );
}

export default SMEDashboard;


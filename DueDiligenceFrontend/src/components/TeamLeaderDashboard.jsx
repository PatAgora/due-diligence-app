import { useState, useEffect } from 'react';
import BaseLayout from './BaseLayout';
import { Bar, Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import '../styles/agora-theme.css';
import './TeamLeaderDashboard.css';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend);

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function TeamLeaderDashboard() {
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
        `${BASE_URL}/api/team_leader_dashboard?date_range=${dateRange}`,
        {
          credentials: 'include',
          headers: { 'Accept': 'application/json' },
        }
      );

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied. Team Lead role required.');
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const dashboardData = await response.json();
      setData(dashboardData);
    } catch (err) {
      console.error('Error fetching dashboard:', err);
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
        <h1 className="fw-bold mb-2">Team Leader Dashboard (Level {data.level})</h1>
        <p className="text-muted mb-3">Team: {data.team_lead_name}</p>

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
                <h6>Total Active WIP</h6>
                <div className="num">{data.total_active_wip || 0}</div>
              </div>
            </div>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Completed</h6>
                <div className="num">{data.completed_count || 0}</div>
              </div>
            </div>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>Total QC Checked</h6>
                <div className="num">{data.qc_sample || 0}</div>
              </div>
            </div>
          </div>

          <div className="col-12 col-md-6 col-lg-3">
            <div className="card shadow-sm h-100">
              <div className="card-body kpi">
                <h6>QC Pass %</h6>
                <div className="num">{data.qc_pass_pct?.toFixed(1) || 0}%</div>
              </div>
            </div>
          </div>
        </div>

        {/* Charts row */}
        <div className="row g-4 mb-4">
          {/* Daily Output Chart */}
          <div className="col-lg-6">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title">Team Daily Output</h5>
                <div style={{ position: 'relative', height: '300px' }}>
                  {data.daily_labels && data.daily_labels.length > 0 ? (
                    <Line
                      data={{
                        labels: data.daily_labels,
                        datasets: [{
                          label: 'Completed',
                          data: data.daily_counts,
                          borderColor: '#0d6efd',
                          backgroundColor: 'rgba(13, 110, 253, 0.1)',
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
                      <p className="text-muted">No output data</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Individual Performance Chart */}
          <div className="col-lg-6">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title">Individual Performance</h5>
                <div style={{ position: 'relative', height: '300px' }}>
                  {data.reviewer_performance && data.reviewer_performance.length > 0 ? (
                    <Bar
                      data={{
                        labels: data.reviewer_performance.map(r => r.name),
                        datasets: [{
                          label: 'Completed',
                          data: data.reviewer_performance.map(r => r.completed),
                          backgroundColor: '#198754'
                        }]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                      }}
                    />
                  ) : (
                    <div className="d-flex align-items-center justify-content-center h-100">
                      <p className="text-muted">No performance data</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Team Members */}
        {data.reviewers && data.reviewers.length > 0 && (
          <div className="card shadow-sm">
            <div className="card-body">
              <h5 className="card-title">Team Members</h5>
              <div className="table-responsive">
                <table className="table table-hover">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.reviewers.map((reviewer) => (
                      <tr key={reviewer.id}>
                        <td>{reviewer.name || '—'}</td>
                        <td>{reviewer.email}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </BaseLayout>
  );
}

export default TeamLeaderDashboard;


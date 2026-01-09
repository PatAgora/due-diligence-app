import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend } from 'chart.js';
import BaseLayout from './BaseLayout';

import '../styles/agora-theme.css';
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
import './OperationsDashboard.css';

// Register Chart.js components
ChartJS.register(ArcElement, CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend);

function OperationsDashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  
  // Load filters from localStorage on mount
  const [dateRange, setDateRange] = useState(() => {
    const saved = localStorage.getItem('ops_dashboard_dateRange');
    return saved || 'all';
  });
  const [team, setTeam] = useState(() => {
    const saved = localStorage.getItem('ops_dashboard_team');
    return saved || 'all';
  });

  // Save filters to localStorage when they change
  useEffect(() => {
    localStorage.setItem('ops_dashboard_dateRange', dateRange);
  }, [dateRange]);

  useEffect(() => {
    localStorage.setItem('ops_dashboard_team', team);
  }, [team]);

  useEffect(() => {
    fetchDashboard();
  }, [dateRange, team]);

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (dateRange) params.append('date_range', dateRange);
      if (team) params.append('team', team);

      const response = await fetch(`${BASE_URL}/api/operations/dashboard?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load dashboard data');
      }

      const json = await response.json();
      console.log('Operations Dashboard Data:', json);
      console.log('QC Sample:', json.qc_sample, 'Pass QC:', json.pass_qc);
      console.log('Planning Labels:', json.plan_labels, 'Forecast:', json.plan_forecast, 'Actual:', json.plan_actual);
      console.log('Chaser Headers:', json.chaser_headers, 'Chaser Week Rows:', json.chaser_week_rows);
      setData(json);
    } catch (err) {
      console.error('Error fetching dashboard:', err);
      setError(err.message);
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
            <button className="btn btn-primary" onClick={fetchDashboard}>Retry</button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container-fluid px-2 my-4 mx-2">
        {/* Filters and Export Row */}
        <div className="row g-4 mb-4">
          <div className="col-12 col-xl-8">
            <div className="card shadow-sm p-4 h-100">
              <h5 className="mb-3 fw-bold text-uppercase small text-secondary">Dashboard Filters</h5>
              <div className="row g-3">
                <div className="col-12 col-md-5 col-lg-4">
                  <label className="form-label text-muted small fw-semibold">Date Range</label>
                  <select
                    className="form-select form-select-lg"
                    value={dateRange}
                    onChange={(e) => setDateRange(e.target.value)}
                  >
                    {data?.date_ranges?.map((dr) => (
                      <option key={dr.value} value={dr.value}>
                        {dr.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-12 col-md-5 col-lg-4">
                  <label className="form-label text-muted small fw-semibold">Team</label>
                  <select
                    className="form-select form-select-lg"
                    value={team}
                    onChange={(e) => setTeam(e.target.value)}
                  >
                    {data?.teams?.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-12 col-md-2 col-lg-4">
                  <label className="form-label invisible d-none d-md-block">.</label>
                  <button 
                    type="button" 
                    className="btn btn-warning btn-lg w-100"
                    onClick={fetchDashboard}
                  >
                    <i className="bi bi-funnel me-2"></i>Apply Filters
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div className="col-12 col-xl-4">
            <div className="card shadow-sm p-4 h-100 d-flex flex-column">
              <h5 className="fw-bold text-uppercase small text-secondary mb-3">Export Data</h5>
              <div className="mt-auto">
                <a 
                  href={`${BASE_URL}/ops/mi/export_excel?date_range=${dateRange}&team=${team}`} 
                  className="btn btn-outline-dark btn-lg px-4"
                  download
                >
                  <i className="bi bi-file-earmark-excel me-2"></i>Download Excel
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="row g-3 mb-5">
          <div className="col-sm-6 col-md-3">
            <a href={`/ops/mi/cases?date_range=${dateRange}&team=${team}`} className="text-decoration-none text-reset">
              <div className="kpi-card kpi-accent-orange">
                <div className="kpi-top">
                  <span className="kpi-icon orange"><i className="bi bi-people-fill"></i></span>
                </div>
                <div className="kpi-metric">{data?.total_screened || 0}</div>
                <div className="kpi-label mt-1">Total Population</div>
              </div>
            </a>
          </div>
          <div className="col-sm-6 col-md-3">
            <a href={`/ops/mi/cases?status=Completed&date_range=${dateRange}&team=${team}`} className="text-decoration-none text-reset">
              <div className="kpi-card kpi-accent-green">
                <div className="kpi-top">
                  <span className="kpi-icon green"><i className="bi bi-check2-circle"></i></span>
                </div>
                <div className="kpi-metric">{data?.total_completed || 0}</div>
                <div className="kpi-label mt-1">Completed</div>
              </div>
            </a>
          </div>
          <div className="col-sm-6 col-md-3">
            <a href={`/ops/mi/cases?qc=1&date_range=${dateRange}&team=${team}`} className="text-decoration-none text-reset">
              <div className="kpi-card kpi-accent-cyan">
                <div className="kpi-top">
                  <span className="kpi-icon cyan"><i className="bi bi-clipboard2-check"></i></span>
                </div>
                <div className="kpi-metric">{data?.qc_sample || 0}</div>
                <div className="kpi-label mt-1">Total QC Checked</div>
              </div>
            </a>
          </div>
          <div className="col-sm-6 col-md-3">
            <div className="kpi-card kpi-accent-amber">
              <div className="kpi-top">
                <span className="kpi-icon amber"><i className="bi bi-percent"></i></span>
              </div>
              <div className="kpi-metric">{data?.qc_pass_pct || 0}%</div>
              <div className="kpi-label mt-1">QC Pass Rate</div>
            </div>
          </div>
        </div>

        {/* Charts Row - Quality Stats, Planning, Chaser Cycle */}
        <div className="row g-4 mb-4">
          {/* Quality Stats (Donut Chart) */}
          <div className="col-12 col-lg-4">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title fw-bold mb-3">Quality Stats</h5>
                {data?.qc_sample !== undefined && data.qc_sample > 0 ? (
                  <div style={{ position: 'relative', height: '300px' }}>
                    {(() => {
                      const passCount = data.pass_qc !== undefined ? data.pass_qc : Math.round((data.qc_sample * (data.qc_pass_pct || 0)) / 100);
                      const failCount = data.qc_sample - passCount;
                      const passPct = data.qc_pass_pct !== undefined ? data.qc_pass_pct : (passCount > 0 ? Math.round((passCount / data.qc_sample) * 100) : 0);
                      return (
                        <>
                          <Doughnut
                            data={{
                              labels: ['Pass', 'Fail'],
                              datasets: [{
                                data: [passCount, failCount],
                                backgroundColor: ['#198754', '#dc3545'],
                                borderWidth: 2,
                                borderColor: '#fff'
                              }]
                            }}
                            options={{
                              responsive: true,
                              maintainAspectRatio: false,
                              plugins: {
                                legend: {
                                  display: false
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
                          <div style={{
                            position: 'absolute',
                            top: '50%',
                            left: '50%',
                            transform: 'translate(-50%, -50%)',
                            textAlign: 'center',
                            fontSize: '24px',
                            fontWeight: 'bold'
                          }}>
                            {passPct}%
                          </div>
                        </>
                      );
                    })()}
                    <div className="d-flex align-items-center justify-content-center gap-3 mt-3">
                      <div className="d-flex align-items-center gap-1">
                        <span className="rounded-circle d-inline-block" style={{ width: '12px', height: '12px', background: '#198754' }}></span>
                        <span>Pass</span>
                      </div>
                      <div className="d-flex align-items-center gap-1">
                        <span className="rounded-circle d-inline-block" style={{ width: '12px', height: '12px', background: '#dc3545' }}></span>
                        <span>Fail</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="d-flex align-items-center justify-content-center" style={{ height: '300px' }}>
                    <span className="text-muted">No QC data available</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Planning (Bar Chart) */}
          <div className="col-12 col-lg-4">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title fw-bold mb-3">Planning</h5>
                <div style={{ position: 'relative', height: '300px' }}>
                  {data?.plan_labels && data.plan_labels.length > 0 ? (
                    <Line
                      data={{
                        labels: data.plan_labels,
                        datasets: [
                          {
                            type: 'bar',
                            label: 'Forecast',
                            data: data.plan_forecast || [],
                            backgroundColor: '#87CEEB',
                            borderColor: '#4682B4',
                            borderWidth: 1,
                            order: 2
                          },
                          {
                            type: 'line',
                            label: 'Actual',
                            data: data.plan_actual || [],
                            borderColor: '#dc3545',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 4,
                            pointBackgroundColor: '#dc3545',
                            pointBorderColor: '#dc3545',
                            tension: 0.4,
                            order: 1
                          }
                        ]
                      }}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            display: true,
                            position: 'top'
                          },
                          tooltip: {
                            mode: 'index',
                            intersect: false
                          }
                        },
                        scales: {
                          y: {
                            beginAtZero: true,
                            ticks: {
                              precision: 0,
                              stepSize: 10
                            }
                          },
                          x: {
                            ticks: {
                              maxRotation: 45,
                              minRotation: 45,
                              font: {
                                size: 9
                              },
                              maxTicksLimit: 15
                            }
                          }
                        }
                      }}
                    />
                  ) : (
                    <div className="d-flex align-items-center justify-content-center h-100">
                      <span className="text-muted">No planning data available</span>
                    </div>
                  )}
                </div>
                <div className="mt-3 text-center">
                  <a href="/ops/mi/planning" className="btn btn-outline-secondary btn-sm">Edit Forecast</a>
                </div>
              </div>
            </div>
          </div>

          {/* Chaser Cycle (Current Week) Table */}
          <div className="col-12 col-lg-4">
            <div className="card shadow-sm h-100">
              <div className="card-body">
                <h5 className="card-title fw-bold mb-3">Chaser Cycle (Current Week)</h5>
                {data?.chaser_week_rows && data.chaser_headers ? (
                  <div className="table-responsive">
                    <table className="table table-sm table-bordered align-middle mb-0">
                      <thead className="table-light">
                        <tr>
                          <th className="fw-bold">Date</th>
                          {data.chaser_headers.filter(h => h !== 'Overdue').map((h, idx) => (
                            <th key={idx} className="text-center fw-bold">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.chaser_week_rows.length > 0 ? (
                          <>
                            {data.chaser_week_rows.map((row, idx) => (
                              <tr key={idx}>
                                <td className="fw-semibold">{row.date}</td>
                                {data.chaser_headers.filter(h => h !== 'Overdue').map((h, hIdx) => {
                                  const v = row[h] || 0;
                                  return (
                                    <td key={hIdx} className="text-center">
                                      {v > 0 ? (
                                        <Link 
                                          to={`/ops/mi/cases?date_range=wtd&chaser_type=${h}&week_date=${row.iso}`}
                                          className="text-decoration-none text-body"
                                        >
                                          <span className="chip chip-warn">{v}</span>
                                        </Link>
                                      ) : (
                                        v
                                      )}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                            <tr className="table-warning">
                              <td className="fw-bold">Overdue</td>
                              {data.chaser_headers.filter(h => h !== 'Overdue').map((h, hIdx) => {
                                const overdueCount = data.chaser_overdue?.[h] || 0;
                                return (
                                  <td key={hIdx} className="text-center">
                                    {overdueCount > 0 ? (
                                      <Link 
                                        to={`/ops/mi/cases?date_range=wtd&overdue=1&chaser_type=${h}`}
                                        className="text-decoration-none text-body"
                                      >
                                        <span className="chip chip-danger">{overdueCount}</span>
                                      </Link>
                                    ) : (
                                      overdueCount
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          </>
                        ) : (
                          <tr>
                            <td colSpan={data.chaser_headers.filter(h => h !== 'Overdue').length + 1} className="text-center text-muted">No chaser data</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                    <div className="mt-2">
                      <small className="text-muted">Counts include only items not yet issued. Volumes are clickable and will take you to the cases view filtered to the selected due date/overdue bucket.</small>
                    </div>
                  </div>
                ) : (
                  <div className="d-flex align-items-center justify-content-center" style={{ height: '200px' }}>
                    <span className="text-muted">No chaser cycle data available</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Case Status & Age Profile */}
        <div className="card shadow-sm mb-4">
          <div className="card-body">
            <h4 className="card-title fw-bold mb-3">Case Status & Age Profile</h4>
            <div className="table-responsive">
              <table className="table table-hover align-middle">
                <thead className="table-light">
                  <tr className="text-uppercase small text-secondary">
                    <th>Status</th>
                    <th className="text-end">Count</th>
                    <th className="text-end">Percent</th>
                    <th className="text-center">0-12 Days</th>
                    <th className="text-center">13-35 Days</th>
                    <th className="text-center">36+ Days</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.distribution?.length > 0 ? (
                    data.distribution.map((row, idx) => {
                      const ages = row.age_buckets || {};
                      const a12 = ages['1–2 days'] || 0;
                      const a35 = ages['3–5 days'] || 0;
                      const a5p = ages['5 days+'] || 0;
                      return (
                        <tr key={idx}>
                          <td>
                            <a 
                              href={`/ops/mi/cases?status=${encodeURIComponent(row.status)}&date_range=${dateRange}&team=${team}`}
                              className="text-decoration-none text-body"
                            >
                              {row.status}
                            </a>
                          </td>
                          <td className="text-end fw-bold">
                            <a 
                              href={`/ops/mi/cases?status=${encodeURIComponent(row.status)}&date_range=${dateRange}&team=${team}`}
                              className="text-decoration-none text-body"
                            >
                              {row.count}
                            </a>
                          </td>
                          <td className="text-end fw-bold">{row.pct}%</td>
                          <td className="text-center">
                            <a 
                              href={`/ops/mi/cases?status=${encodeURIComponent(row.status)}&age_bucket=1–2 days&date_range=${dateRange}&team=${team}`}
                              className="text-decoration-none"
                            >
                              <span className="age-cell age-green">{a12}</span>
                            </a>
                          </td>
                          <td className="text-center">
                            <a 
                              href={`/ops/mi/cases?status=${encodeURIComponent(row.status)}&age_bucket=3–5 days&date_range=${dateRange}&team=${team}`}
                              className="text-decoration-none"
                            >
                              <span className="age-cell age-amber">{a35}</span>
                            </a>
                          </td>
                          <td className="text-center">
                            <a 
                              href={`/ops/mi/cases?status=${encodeURIComponent(row.status)}&age_bucket=5 days+&date_range=${dateRange}&team=${team}`}
                              className="text-decoration-none"
                            >
                              <span className="age-cell age-red">{a5p}</span>
                            </a>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan="6" className="text-center text-muted">No data available</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Outcome */}
        <div className="card shadow-sm mb-4">
          <div className="card-body">
            <h4 className="card-title fw-bold mb-3">Outcome</h4>
            <div className="table-responsive">
              <table className="table table-hover align-middle">
                <thead className="table-light">
                  <tr className="text-uppercase small text-secondary">
                    <th>Outcome</th>
                    <th className="text-end" style={{minWidth: '90px'}}>Count</th>
                    <th className="text-end" style={{minWidth: '100px'}}>Percent</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.outcome_breakdown?.length > 0 ? (
                    data.outcome_breakdown.map((row, idx) => (
                      <tr key={idx}>
                        <td>
                          <a 
                            href={`/ops/mi/cases?status=Completed&outcome=${encodeURIComponent(row.label)}&date_range=${dateRange}&team=${team}`}
                            className="text-decoration-none text-body fw-bold"
                          >
                            {row.label}
                          </a>
                        </td>
                        <td className="text-end fw-bold">
                          <a 
                            href={`/ops/mi/cases?status=Completed&outcome=${encodeURIComponent(row.label)}&date_range=${dateRange}&team=${team}`}
                            className="text-decoration-none text-body"
                          >
                            {row.count}
                          </a>
                        </td>
                        <td className="text-end fw-bold">{row.pct}%</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="3" className="text-center text-muted">No outcome data for the selected filters.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default OperationsDashboard;


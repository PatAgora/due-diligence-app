import { useState, useEffect } from 'react';
import '../styles/agora-theme.css';
import { useSearchParams } from 'react-router-dom';
import { reviewerAPI } from '../services/api';
import { usePermissions } from '../contexts/PermissionsContext';
import { Doughnut, Line } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import './ReviewerDashboard.css';

// Register Chart.js components
ChartJS.register(ArcElement, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

function ReviewerDashboard() {
  const { canEdit } = usePermissions();
  const [searchParams, setSearchParams] = useSearchParams();
  const [dateRange, setDateRange] = useState(searchParams.get('date_range') || 'all');
  const canInteract = canEdit('view_dashboard');
  const [dashboardData, setDashboardData] = useState({
    active_wip: 0,
    completed_count: 0,
    qc_sample: 0,
    qc_pass_pct: 0,
    qc_pass_cnt: 0,
    qc_fail_cnt: 0,
    daily_labels: [],
    daily_counts: [],
    rework_buckets: { '1–2 days': 0, '3–5 days': 0, '5 days+': 0 },
    age_rows: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await reviewerAPI.getDashboard(dateRange);
        setDashboardData(data);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
        if (err.message?.includes('403') || err.message?.includes('Access denied')) {
          setError('You do not have access to this dashboard. Please contact your administrator.');
        } else {
          setError('Failed to load dashboard data. Please refresh the page.');
        }
        // Fallback: try to get data from HTML response or use defaults
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [dateRange]);

  const handleDateChange = (e) => {
    const newDateRange = e.target.value;
    setDateRange(newDateRange);
    setSearchParams({ date_range: newDateRange });
  };

  // Helper to render clickable or non-clickable links
  const renderLink = (href, children, className = 'text-decoration-none text-body') => {
    if (canInteract) {
      return <a href={href} className={className}>{children}</a>;
    }
    return <span className={className} style={{ cursor: 'not-allowed', opacity: 0.6 }}>{children}</span>;
  };

  return (
    <div className="container-fluid px-3 my-3 mx-3">
      <h1 className="fw-bold mb-2">Reviewer Dashboard</h1>

      {/* Date filter */}
      <form className="d-flex gap-2 align-items-center mb-4" onSubmit={(e) => e.preventDefault()}>
        <select
          name="date_range"
          className="form-select form-select-sm"
          style={{ maxWidth: '180px' }}
          value={dateRange}
          onChange={handleDateChange}
        >
          <option value="wtd">Current Week</option>
          <option value="prevw">Previous Week</option>
          <option value="30d">Last 30 Days</option>
          <option value="all">All Time</option>
        </select>
        <button className="btn btn-primary btn-sm" type="submit">Apply</button>
      </form>

      {error && (
        <div className="alert alert-warning" role="alert">
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-4">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      )}

      {/* KPI tiles */}
      <div className="row g-3 mb-4">
        <div className="col-12 col-md-6 col-lg-3">
          <div className={`card h-100 shadow-sm status-card ${canInteract ? 'hover-lift' : ''}`}>
            {canInteract ? (
              <a href="/my_tasks?status=wip&date_range=all" className="stretched-link text-decoration-none text-reset"></a>
            ) : (
              <div className="stretched-link" style={{ cursor: 'not-allowed', opacity: 0.6 }}></div>
            )}
            <div className="card-body hover-lift kpi" kpi-compact>
              <h6>Active WIP</h6>
              <div className="num">{dashboardData.active_wip || 0}</div>
            </div>
          </div>
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <div className={`card h-100 shadow-sm status-card ${canInteract ? 'hover-lift' : ''}`}>
            {canInteract ? (
              <a
                href={`/my_tasks?status=completed&date_range=${dateRange}`}
                className="stretched-link text-decoration-none text-reset"
              ></a>
            ) : (
              <div className="stretched-link" style={{ cursor: 'not-allowed', opacity: 0.6 }}></div>
            )}
            <div className="card-body hover-lift kpi" kpi-compact>
              <h6>Completed</h6>
              <div className="num">{dashboardData.completed_count || 0}</div>
            </div>
          </div>
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <div className={`card h-100 shadow-sm status-card ${canInteract ? 'hover-lift' : ''}`}>
            {canInteract ? (
              <a
                href={`/my_tasks?status=qc_checked&date_range=${dateRange}`}
                className="stretched-link text-decoration-none text-reset"
              ></a>
            ) : (
              <div className="stretched-link" style={{ cursor: 'not-allowed', opacity: 0.6 }}></div>
            )}
            <div className="card-body hover-lift kpi" kpi-compact>
              <h6>Total QC Checked</h6>
              <div className="num">{dashboardData.qc_sample || 0}</div>
            </div>
          </div>
        </div>
        <div className="col-12 col-md-6 col-lg-3">
          <div className="card h-100 hover-lift shadow-sm status-card">
            <div className="card-body hover-lift kpi" kpi-compact>
              <h6>QC Pass %</h6>
              <div className="num">{dashboardData.qc_pass_pct?.toFixed(1) || 0}%</div>
              <div className="small text-muted mt-1">
                {dashboardData.qc_pass_cnt || 0}/{dashboardData.qc_sample || 0} passed (
                {dashboardData.qc_fail_cnt || 0} fail)
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Charts row - placeholder for now */}
      <div className="row row-cols-1 row-cols-lg-3 g-0 align-items-stretch metrics-3up equal-trio">
        <div className="col d-flex metric-tile">
          <div className="card hover-lift shadow-sm status-card flex-fill">
            <div className="card-body d-flex flex-column">
              <h5 className="card-title">Quality Stats</h5>
              <div className="mb-2 small text-muted">QC Pass %</div>
              <div style={{ position: 'relative', height: '230px' }}>
                {dashboardData.qc_sample > 0 ? (
                  <Doughnut
                    data={{
                      labels: ['Pass', 'Fail'],
                      datasets: [{
                        data: [dashboardData.qc_pass_cnt || 0, dashboardData.qc_fail_cnt || 0],
                        backgroundColor: ['#198754', '#dc3545'],
                        borderWidth: 2,
                        borderColor: '#fff'
                      }]
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: { display: false },
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
                      }
                    }}
                  />
                ) : (
                  <div className="d-flex align-items-center justify-content-center h-100">
                    <span className="text-muted">No QC data</span>
                  </div>
                )}
              </div>
              <div className="d-flex align-items-center gap-3 mt-3">
                <div className="d-flex align-items-center gap-1">
                  <span
                    className="rounded-circle d-inline-block"
                    style={{ width: '12px', height: '12px', background: '#198754' }}
                  >
                    &nbsp;
                  </span>
                  <span>Pass</span>
                </div>
                <div className="d-flex align-items-center gap-1">
                  <span
                    className="rounded-circle d-inline-block"
                    style={{ width: '12px', height: '12px', background: '#dc3545' }}
                  >
                    &nbsp;
                  </span>
                  <span>Fail</span>
                </div>
                <span className="ms-auto small text-muted">
                  Sample: {dashboardData.qc_sample || 0}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="col d-flex metric-tile">
          <div className="card hover-lift shadow-sm status-card flex-fill">
            <div className="card-body d-flex flex-column">
              <h5 className="card-title">Individual Output (Completed by Day)</h5>
              <div className="flex-grow-1 d-flex align-items-center" style={{ minHeight: '230px' }}>
                {dashboardData.daily_labels && dashboardData.daily_labels.length > 0 ? (
                  <Line
                    data={{
                      labels: dashboardData.daily_labels,
                      datasets: [{
                        label: 'Completed',
                        data: dashboardData.daily_counts,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
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
                  <div className="d-flex align-items-center justify-content-center w-100">
                    <span className="text-muted">No daily output data</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="col d-flex metric-tile">
          <div className="card h-100 hover-lift shadow-sm status-card equal-square flex-fill">
            <div className="card-body hover-lift rework-card">
              <div className="d-flex align-items-center justify-content-between">
                <h5 className="card-title mb-0">Rework Age Profile</h5>
                <span className="note">Live (not date-filtered)</span>
              </div>
              <div className="table-wrap mt-2">
                <div className="table-responsive w-100">
                  <table className="align-middle mb-0 table table-clean table-sm table-tight">
                    <thead>
                      <tr>
                        <th>Age</th>
                        <th className="text-center">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {['1–2 days', '3–5 days', '5 days+'].map((bucket) => {
                        const count = dashboardData.rework_buckets?.[bucket] || 0;
                        const chipClass = bucket.startsWith('1') ? 'chip-green' : (bucket.startsWith('3') ? 'chip-amber' : 'chip-red');
                        return (
                          <tr key={bucket}>
                            <td className="fw-semibold">{bucket}</td>
                            <td className="text-end">
                              {count > 0 ? (
                                canInteract ? (
                                  <a href={`/my_tasks?rework_bucket=${encodeURIComponent(bucket)}&date_range=all`} className="text-decoration-none text-body">
                                    <span className={`chip ${chipClass}`}>{count}</span>
                                  </a>
                                ) : (
                                  <span className={`chip ${chipClass}`} style={{ cursor: 'not-allowed', opacity: 0.6 }}>{count}</span>
                                )
                              ) : (
                                <span className={`chip ${chipClass}`}>{count}</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Case Status & Age Profile */}
      <div className="card hover-lift mt-4 shadow-sm status-card">
        <div className="card-body hover-lift">
          <div className="d-flex align-items-center justify-content-between">
            <h5 className="card-title mb-0">Case Status & Age Profile</h5>
            <span className="note">Live (time since last touched)</span>
          </div>

          <div className="table-responsive mt-2">
            <table className="mb-0 table table-clean table-sm table-striped">
              <thead className="table-light">
                <tr>
                  <th rowSpan="2">Status</th>
                  <th className="text-end" rowSpan="2">Count</th>
                  <th className="text-end" rowSpan="2">Percent</th>
                  <th className="text-end small text-muted" colSpan="3">Time since last touched</th>
                </tr>
                <tr>
                  <th className="text-center">1–2 days</th>
                  <th className="text-center">3–5 days</th>
                  <th className="text-center">5 days+</th>
                </tr>
              </thead>
              <tbody>
                {dashboardData.age_rows && dashboardData.age_rows.length > 0 ? (
                  dashboardData.age_rows.map((row, idx) => (
                    <tr key={idx}>
                      <td>
                        {renderLink(
                          `/my_tasks?status=${encodeURIComponent(row.status)}&date_range=all`,
                          row.status
                        )}
                      </td>
                      <td className="text-end">
                        {renderLink(
                          `/my_tasks?status=${encodeURIComponent(row.status)}&date_range=all`,
                          row.count
                        )}
                      </td>
                      <td className="text-end">{row.pct}%</td>
                      <td className={`text-center ${row.bucket_12 > 0 ? 'hm-success' : 'hm-zero'}`}>
                        {renderLink(
                          `/my_tasks?status=${encodeURIComponent(row.status)}&age_bucket=${encodeURIComponent('1–2 days')}&date_range=all`,
                          row.bucket_12
                        )}
                      </td>
                      <td className={`text-center ${row.bucket_35 > 0 ? 'hm-warning' : 'hm-zero'}`}>
                        {renderLink(
                          `/my_tasks?status=${encodeURIComponent(row.status)}&age_bucket=${encodeURIComponent('3–5 days')}&date_range=all`,
                          row.bucket_35
                        )}
                      </td>
                      <td className={`text-center ${row.bucket_5p > 0 ? 'hm-danger' : 'hm-zero'}`}>
                        {renderLink(
                          `/my_tasks?status=${encodeURIComponent(row.status)}&age_bucket=${encodeURIComponent('5 days+')}&date_range=all`,
                          row.bucket_5p
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="text-center text-muted">No WIP for this reviewer.</td>
                  </tr>
                )}
              </tbody>
              <tfoot>
                <tr className="table-light fw-semibold">
                  <td className="text-end">Totals</td>
                  <td className="text-end">
                    {renderLink(
                      '/my_tasks?status=wip&date_range=all',
                      dashboardData.age_totals?.count || 0
                    )}
                  </td>
                  <td className="text-end">{dashboardData.age_totals?.pct?.toFixed(1) || '0.0'}%</td>
                  <td className="text-end">
                    {renderLink(
                      '/my_tasks?status=wip&age_bucket=1–2 days&date_range=all',
                      dashboardData.age_totals?.bucket_12 || 0
                    )}
                  </td>
                  <td className="text-end">
                    {renderLink(
                      '/my_tasks?status=wip&age_bucket=3–5 days&date_range=all',
                      dashboardData.age_totals?.bucket_35 || 0
                    )}
                  </td>
                  <td className="text-end">
                    {renderLink(
                      '/my_tasks?status=wip&age_bucket=5 days+&date_range=all',
                      dashboardData.age_totals?.bucket_5p || 0
                    )}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="note mt-2">
            Counts include only items currently assigned to you.
            Age buckets use the most recent touch (assignment, SME/QC activity, completion, or update).
          </div>
        </div>
      </div>

      {/* Chaser Cycle (Current Week) */}
      <div className="card hover-lift mt-4 shadow-sm status-card">
        <div className="card-body hover-lift">
          <div className="d-flex align-items-center justify-content-between">
            <h5 className="card-title mb-0">Chaser Cycle (Current Week)</h5>
            <span className="note">Live (due date buckets)</span>
          </div>

          <div className="table-responsive mt-2">
            <table className="mb-0 table table-clean table-sm table-striped">
              <thead className="table-light">
                <tr>
                  <th>Date</th>
                  {dashboardData.chaser_headers?.filter(h => h !== 'Overdue').map((h, idx) => (
                    <th key={idx} className="text-center">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dashboardData.chaser_week_rows && dashboardData.chaser_week_rows.length > 0 ? (
                  <>
                    {dashboardData.chaser_week_rows.map((row, idx) => (
                      <tr key={idx}>
                        <td className="fw-semibold">{row.date}</td>
                        {dashboardData.chaser_headers?.filter(h => h !== 'Overdue').map((h) => {
                          const v = row[h] || 0;
                          return (
                            <td key={h} className="text-center">
                              {v > 0 ? (
                                canInteract ? (
                                  <a href={`/my_tasks?date_range=${dateRange}&chaser_type=${h}&week_date=${row.iso}`} className="text-decoration-none text-body">
                                    <span className="chip chip-warn">{v}</span>
                                  </a>
                                ) : (
                                  <span className="chip chip-warn" style={{ cursor: 'not-allowed', opacity: 0.6 }}>{v}</span>
                                )
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
                      {dashboardData.chaser_headers?.filter(h => h !== 'Overdue').map((h, hIdx) => {
                        const overdueCount = dashboardData.chaser_overdue?.[h] || 0;
                        return (
                          <td key={hIdx} className="text-center">
                            {overdueCount > 0 ? (
                              canInteract ? (
                                <a href={`/my_tasks?date_range=${dateRange}&overdue=1&chaser_type=${h}`} className="text-decoration-none text-body">
                                  <span className="chip chip-danger">{overdueCount}</span>
                                </a>
                              ) : (
                                <span className="chip chip-danger" style={{ cursor: 'not-allowed', opacity: 0.6 }}>{overdueCount}</span>
                              )
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
                    <td colSpan={(dashboardData.chaser_headers?.filter(h => h !== 'Overdue').length || 0) + 1} className="text-muted text-center">No chaser data.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="note mt-2">
            Volumes are clickable and will take you to your <em>My Tasks</em> view filtered to the selected due date/overdue bucket.
          </div>
        </div>
      </div>
    </div>
  );
}

export default ReviewerDashboard;


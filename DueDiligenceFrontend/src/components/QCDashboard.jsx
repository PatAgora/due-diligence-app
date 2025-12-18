import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import Plot from 'react-plotly.js';
import './QCDashboard.css';

function QCDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [dateRange, setDateRange] = useState(searchParams.get('date_range') || 'month');
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`/api/qc_dashboard?date_range=${dateRange}`, {
          credentials: 'include',
          headers: {
            'Accept': 'application/json',
          },
        });
        
        // Check if response is actually JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          const text = await response.text();
          console.error('Non-JSON response:', text.substring(0, 500));
          throw new Error(`Server returned ${response.status}: ${text.substring(0, 100)}`);
        }
        
        if (response.ok) {
          const data = await response.json();
          setDashboardData(data);
        } else {
          const errorData = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
          throw new Error(errorData.error || `HTTP ${response.status}: Failed to fetch dashboard data`);
        }
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
        setError('Failed to load dashboard data. Please refresh the page.');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [dateRange]);

  const handleDateChange = (e) => {
    const newRange = e.target.value;
    setDateRange(newRange);
    setSearchParams({ date_range: newRange });
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-GB', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  if (loading) {
    return (
      <div className="container my-4">
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
      <div className="container my-4">
        <div className="alert alert-danger">{error}</div>
      </div>
    );
  }

  const data = dashboardData || {};

  return (
    <div className="container my-4">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h1 className="fw-bold mb-0">My QC Dashboard (Level {data.level || ''})</h1>
      </div>

      {/* Filters */}
      <div className="row g-2 mb-4 align-items-center">
        <div className="col-auto">
          <label className="form-label me-2 mb-0">Date Range:</label>
          <select
            name="date_range"
            className="form-select form-select-sm d-inline-block"
            style={{ width: 'auto' }}
            value={dateRange}
            onChange={handleDateChange}
          >
            {data.date_ranges?.map((dr) => (
              <option key={dr.value} value={dr.value}>
                {dr.label}
              </option>
            )) || (
              <>
                <option value="today">Today</option>
                <option value="week">This Week</option>
                <option value="month">This Month</option>
                <option value="quarter">This Quarter</option>
                <option value="ytd">Year to Date</option>
                <option value="all">All</option>
              </>
            )}
          </select>
        </div>
      </div>

      {/* KPI Row */}
      <div className="row g-3 mb-4">
        <div className="col-sm-6 col-md-3">
          <div className="card p-4 shadow-sm h-100">
            <h6 className="mb-2">My Active WIP</h6>
            <div className="display-6 text-primary mb-2">{data.active_wip || 0}</div>
            <small className="text-muted">Assigned to me, not finished</small>
          </div>
        </div>
        <div className="col-sm-6 col-md-3">
          <div className="card p-4 shadow-sm h-100">
            <h6 className="mb-2">Completed</h6>
            <div className="display-6 text-primary mb-2">{data.completed_in_range || 0}</div>
            <small className="text-muted">Within selected period</small>
          </div>
        </div>
        <div className="col-sm-6 col-md-3">
          <div className="card p-4 shadow-sm h-100">
            <h6 className="mb-2">Outstanding Reworks</h6>
            <div className="display-6 text-primary mb-2">{data.outstanding_reworks || 0}</div>
            <small className="text-muted">Rework required, not completed</small>
          </div>
        </div>
        <div className="col-sm-6 col-md-3">
          <div className="card p-4 shadow-sm h-100">
            <h6 className="mb-2">QC Pass %</h6>
            <div className="display-6 text-primary mb-2">{data.qc_pass_pct || 0}%</div>
            <small className="text-muted">Sample: {data.qc_sample || 0}</small>
          </div>
        </div>
      </div>

      {/* Charts + Recent */}
      <div className="row g-4 mb-4 align-items-stretch">
        <div className="col-lg-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body d-flex flex-column align-items-center">
              <h5 className="card-title">My QC Outcomes</h5>
              {data.qc_sample > 0 ? (
                <>
                  <Plot
                    data={[{
                      values: [data.qc_pass_pct, 100 - data.qc_pass_pct],
                      labels: ['Pass', 'Fail/Other'],
                      type: 'pie',
                      hole: 0.5,
                      marker: {
                        colors: ['#28a745', '#dc3545']
                      }
                    }]}
                    layout={{
                      height: 260,
                      width: 260,
                      margin: { t: 10, b: 0, l: 0, r: 0 },
                      showlegend: true,
                      legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.2 }
                    }}
                    config={{ displayModeBar: false }}
                  />
                  <p className="mt-2 text-muted small">Pass rate for selected period</p>
                </>
              ) : (
                <div className="flex-fill d-flex align-items-center justify-content-center">
                  <span className="text-muted">No outcomes in the selected period.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="col-lg-8">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <h5 className="card-title mb-3">Recent Completions</h5>
              <div className="table-responsive" style={{ maxHeight: '260px', overflow: 'auto' }}>
                <table className="table table-striped table-sm mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>Task</th>
                      <th className="text-end">QC End</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent && data.recent.length > 0 ? (
                      data.recent.map((r, idx) => (
                        <tr key={idx}>
                          <td>
                            <Link to={`/qc_review/${r.task_id}`}>
                              {r.task_id}
                            </Link>
                          </td>
                          <td className="text-end">{r.qc_end || '—'}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="2" className="text-center text-muted">
                          No recent completions.
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

      {/* My WIP */}
      <div className="card shadow-sm">
        <div className="card-body">
          <h5 className="card-title mb-3">My WIP</h5>
          <div className="table-responsive">
            <table className="table table-striped table-sm mb-0">
              <thead className="table-light">
                <tr>
                  <th>Task</th>
                  <th style={{ width: '170px' }}>QC Start</th>
                  <th style={{ width: '160px' }}>Rework</th>
                </tr>
              </thead>
              <tbody>
                {data.my_wip_rows && data.my_wip_rows.length > 0 ? (
                  data.my_wip_rows.map((r, idx) => (
                    <tr key={idx}>
                      <td>
                        <Link to={`/qc_review/${r.task_id}`}>
                          {r.task_id}
                        </Link>
                      </td>
                      <td>{r.qc_start || '—'}</td>
                      <td>
                        {r.rework_required ? (
                          (r.rework_completed) ? (
                            <div>
                              <span className="badge text-bg-success">Completed</span>
                              {r.rework_completed_time && (
                                <div className="small text-muted mt-1">
                                  {formatDate(r.rework_completed_time)}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="badge text-bg-danger">Required</span>
                          )
                        ) : (
                          // Show completion time if rework was previously completed (qc_rework_completed = 1 but qc_rework_required = 0)
                          (r.rework_completed) && r.rework_completed_time ? (
                            <div>
                              <span className="badge text-bg-success">Completed</span>
                              <div className="small text-muted mt-1">
                                {formatDate(r.rework_completed_time)}
                              </div>
                            </div>
                          ) : (
                            <span className="text-muted">—</span>
                          )
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="3" className="text-center text-muted">
                      No items in your WIP.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default QCDashboard;


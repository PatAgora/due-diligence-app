import { useState, useEffect } from 'react';
import { useSearchParams, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Plot from 'react-plotly.js';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import './QCLeadDashboard.css';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

function QCLeadDashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [dateRange, setDateRange] = useState(searchParams.get('date_range') || 'this_week');
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const role = user?.role?.toLowerCase() || '';
  const isActive = (path) => location.pathname.startsWith(path);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(`/api/qc_lead_dashboard?date_range=${dateRange}`, {
          credentials: 'include',
        });
        if (response.ok) {
          const data = await response.json();
          setDashboardData(data);
        } else {
          throw new Error('Failed to fetch dashboard data');
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
    <>
      <nav className="sidebar-nav scrutinise-dark">
        <div className="sidebar-brand">
          <span className="scrutinise-brand">
            Scrutinise<span className="underbar"></span>
          </span>
        </div>
        <div className="sidebar-content">
          <Link
            to="/qc_lead_dashboard"
            className="nav-link active"
          >
            <i className="bi bi-speedometer2"></i> Dashboard
          </Link>
          <hr className="sidebar-divider my-2" style={{ borderColor: 'rgba(255,255,255,0.1)' }} />
          
          {(role === 'qc_1' || role === 'qc_2' || role === 'qc_3' || role.startsWith('qc_lead_') || (role.startsWith('qc_') && !role.startsWith('qc_review_'))) && (
            <>
              <Link
                to="/qc_assign_tasks"
                className={`nav-link ${isActive('/qc_assign_tasks') && !isActive('/qc_assign_tasks_bulk') ? 'active' : ''}`}
              >
                <i className="bi bi-person-plus"></i> Assign Tasks
              </Link>
              <Link
                to="/qc_assign_tasks_bulk"
                className={`nav-link ${isActive('/qc_assign_tasks_bulk') ? 'active' : ''}`}
              >
                <i className="bi bi-people"></i> Bulk Assign
              </Link>
              <Link
                to="/qc/sampling-rates"
                className={`nav-link ${isActive('/qc/sampling-rates') ? 'active' : ''}`}
              >
                <i className="bi bi-gear"></i> Sampling Rates
              </Link>
            </>
          )}
        </div>

        <div className="mt-auto px-2 pb-3">
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              handleLogout();
            }}
            className="nav-link text-danger d-flex align-items-center gap-2"
          >
            <i className="bi bi-box-arrow-right"></i>
            <span>Logout</span>
          </a>
        </div>
      </nav>
      <main style={{ marginLeft: '24px', padding: '10px 10px 10px 0', minHeight: '100%' }}>
        <div className="container my-4">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h1 className="fw-bold mb-0">QC Lead Dashboard (Level {data.level || ''})</h1>
      </div>

      {/* Filters */}
      <form className="row g-2 mb-4 align-items-center" onSubmit={(e) => e.preventDefault()}>
        <div className="col-auto">
          <select
            name="date_range"
            className="form-select form-select-sm"
            value={dateRange}
            onChange={handleDateChange}
          >
            <option value="this_week">Current Week</option>
            <option value="prev_week">Previous Week</option>
            <option value="last_30">Last 30 Days</option>
            <option value="all_time">All Time</option>
          </select>
        </div>
        <div className="col-auto">
          <button type="submit" className="btn btn-primary btn-sm">
            Apply
          </button>
        </div>
      </form>

      {/* KPI Cards - All in one row */}
      <div className="row g-3 mb-4">
        <div className="col-12 col-sm-6 col-md">
          <a href={`/qc_wip_cases?bucket=all_wip&date_range=${dateRange}`} className="text-decoration-none">
            <div className="card p-4 shadow-sm h-100" style={{ cursor: 'pointer', transition: 'all 0.2s' }} 
                 onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 0.5rem 1rem rgba(0, 0, 0, 0.15)'}
                 onMouseLeave={(e) => e.currentTarget.style.boxShadow = '0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)'}>
              <h6 className="mb-2">Active WIP</h6>
              <div className="display-6 text-primary mb-2">{data.active_wip || 0}</div>
              <small className="text-muted">Assigned tasks at Level {data.level || ''}</small>
            </div>
          </a>
        </div>
        <div className="col-12 col-sm-6 col-md">
          <a href={`/qc_wip_cases?bucket=awaiting_assignment&date_range=${dateRange}`} className="text-decoration-none">
            <div className="card p-4 shadow-sm h-100" style={{ cursor: 'pointer', transition: 'all 0.2s' }} 
                 onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 0.5rem 1rem rgba(0, 0, 0, 0.15)'}
                 onMouseLeave={(e) => e.currentTarget.style.boxShadow = '0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)'}>
              <h6 className="mb-2">Unassigned WIP</h6>
              <div className="display-6 text-warning mb-2">{data.unassigned_wip || 0}</div>
              <small className="text-muted">Awaiting QC assignment</small>
            </div>
          </a>
        </div>
        <div className="col-12 col-sm-6 col-md">
          <a href={`/qc_wip_cases?bucket=completed&date_range=${dateRange}`} className="text-decoration-none">
            <div className="card p-4 shadow-sm h-100" style={{ cursor: 'pointer', transition: 'all 0.2s' }} 
                 onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 0.5rem 1rem rgba(0, 0, 0, 0.15)'}
                 onMouseLeave={(e) => e.currentTarget.style.boxShadow = '0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)'}>
              <h6 className="mb-2">Completed</h6>
              <div className="display-6 text-primary mb-2">{data.total_completed || 0}</div>
              <small className="text-muted">Filtered by selected date</small>
            </div>
          </a>
        </div>
        <div className="col-12 col-sm-6 col-md">
          <a href={`/qc_wip_cases?bucket=rework_pending&date_range=${dateRange}`} className="text-decoration-none">
            <div className="card p-4 shadow-sm h-100" style={{ cursor: 'pointer', transition: 'all 0.2s' }} 
                 onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 0.5rem 1rem rgba(0, 0, 0, 0.15)'}
                 onMouseLeave={(e) => e.currentTarget.style.boxShadow = '0 0.125rem 0.25rem rgba(0, 0, 0, 0.075)'}>
              <h6 className="mb-2">Outstanding Reworks</h6>
              <div className="display-6 text-primary mb-2">{data.outstanding_reworks || 0}</div>
              <small className="text-muted">Not yet finalised</small>
            </div>
          </a>
        </div>
        <div className="col-12 col-sm-6 col-md">
          <div className="card p-4 shadow-sm h-100">
            <h6 className="mb-2">QC Pass %</h6>
            <div className="display-6 text-primary mb-2">{data.qc_pass_pct || 0}%</div>
            <small className="text-muted">Filtered by selected date</small>
          </div>
        </div>
      </div>

      {/* Three panels row */}
      <div className="row g-4 mb-4 align-items-stretch">
        {/* Quality Stats */}
        <div className="col-lg-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body d-flex flex-column align-items-center">
              <h5 className="card-title">Quality Stats</h5>
              {data.qc_sample > 0 ? (
                <>
                  <Plot
                    data={[{
                      values: [data.qc_pass || 0, (data.qc_sample - (data.qc_pass || 0))],
                      labels: ['Pass', 'Fail/Pending'],
                      type: 'pie',
                      hole: 0.5,
                      marker: {
                        colors: ['#28a745', '#dc3545']
                      }
                    }]}
                    layout={{
                      height: 200,
                      width: 200,
                      margin: { t: 10, b: 0, l: 0, r: 0 },
                      showlegend: true,
                      legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.2 }
                    }}
                    config={{ displayModeBar: false }}
                  />
                  <p className="mt-auto text-muted">Sample: {data.qc_sample}</p>
                </>
              ) : (
                <div className="flex-fill d-flex align-items-center justify-content-center w-100" style={{ minHeight: '200px' }}>
                  <span className="text-muted">No QC data available for the selected period.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Individual Output */}
        <div className="col-lg-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body d-flex flex-column">
              <h5 className="card-title">Individual Output (Completed)</h5>
              <div className="flex-grow-1" style={{ position: 'relative', height: '220px' }}>
                {data.individual_output && data.individual_output.length > 0 ? (
                  <Bar
                    data={{
                      labels: data.individual_output.map(item => item.reviewer_name || 'Unknown'),
                      datasets: [{
                        label: 'Completed QC',
                        data: data.individual_output.map(item => item.count || 0),
                        backgroundColor: '#007bff',
                        borderColor: '#0056b3',
                        borderWidth: 1
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
                    <span className="text-muted">No individual output data</span>
                  </div>
                )}
              </div>
              <small className="text-muted mt-2">Completed QC checks by reviewer (date filter applied)</small>
            </div>
          </div>
        </div>

        {/* Sampling Rates */}
        <div className="col-lg-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body d-flex flex-column">
              <h5 className="card-title">Sampling Rates</h5>
              <div className="table-responsive">
                <table className="table table-sm mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>Reviewer</th>
                      <th className="text-end">Rate %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sampling_rates && data.sampling_rates.length > 0 ? (
                      data.sampling_rates.map((s, idx) => (
                        <tr key={idx}>
                          <td className="fw-semibold">{s.reviewer_name}</td>
                          <td className="text-end">{s.rate.toFixed(1)}%</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="2" className="text-muted text-center">
                          No sampling data
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

      {/* Team WIP summary */}
      <div className="card shadow-sm p-3 mb-5">
        <h5 className="mb-3">Team WIP</h5>
        <div className="table-responsive">
          <table className="table table-striped table-sm mb-0">
            <thead className="table-light">
              <tr>
                <th>QC Reviewer</th>
                <th className="text-end">Assigned</th>
                <th className="text-end">In Progress</th>
                <th className="text-end">Rework Pending</th>
                <th className="text-end">Pending Recheck</th>
                <th className="text-end">Total WIP</th>
              </tr>
            </thead>
            <tbody>
              {data.team_wip_rows && data.team_wip_rows.length > 0 ? (
                data.team_wip_rows.map((r, idx) => (
                  <tr key={idx}>
                    <td>{r.reviewer_name}</td>
                    <td className="text-end">
                      <Link to={`/qc_wip_cases?bucket=assigned&reviewer_id=${r.reviewer_id}`} className="cell-link">
                        {r.assigned}
                      </Link>
                    </td>
                    <td className="text-end">
                      <Link to={`/qc_wip_cases?bucket=in_progress&reviewer_id=${r.reviewer_id}`} className="cell-link">
                        {r.in_progress}
                      </Link>
                    </td>
                    <td className="text-end">
                      <Link to={`/qc_wip_cases?bucket=rework_pending&reviewer_id=${r.reviewer_id}`} className="cell-link">
                        {r.rework_pending}
                      </Link>
                    </td>
                    <td className="text-end">
                      <Link to={`/qc_wip_cases?bucket=pending_recheck&reviewer_id=${r.reviewer_id}`} className="cell-link">
                        {r.pending_recheck}
                      </Link>
                    </td>
                    <td className="text-end fw-semibold">
                      <Link to={`/qc_wip_cases?bucket=assigned&reviewer_id=${r.reviewer_id}`} className="cell-link">
                        {r.total_wip}
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="text-center text-muted">
                    No active WIP
                  </td>
                </tr>
              )}
              <tr className="table-active">
                <td className="fw-semibold">Awaiting Assignment</td>
                <td className="text-end" colSpan="5">
                  <Link to="/qc_wip_cases?bucket=awaiting_assignment" className="cell-link">
                    {data.awaiting_assignment || 0}
                  </Link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
        </div>
      </main>
    </>
  );
}

export default QCLeadDashboard;


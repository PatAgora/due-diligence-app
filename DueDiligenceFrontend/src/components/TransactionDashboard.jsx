import React, { useState, useEffect } from 'react';
import '../styles/agora-theme.css';
import { useNavigate } from 'react-router-dom';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

/**
 * Transaction Review Dashboard Component
 * Displays transaction KPIs, charts, and trends for a specific customer
 */
function TransactionDashboard({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState('12m');

  useEffect(() => {
    if (customerId) {
      fetchDashboardData();
    }
  }, [customerId, period]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${BASE_URL}/api/transaction/dashboard?customer_id=${customerId}&period=${period}`,
        { credentials: 'include' }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
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

  if (loading) {
    return (
      <div className="container-fluid my-4">
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
      <div className="container-fluid my-4">
        <div className="alert alert-danger">
          <h5>Error loading dashboard</h5>
          <p>{error}</p>
          <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  if (!data || !data.filter_meta || !data.filter_meta.customer_id) {
    return (
      <div className="container-fluid my-4">
        <div className="card">
          <div className="card-body">
            <h5>No Transaction Data</h5>
            <p>No transaction data found for customer: {customerId}</p>
            <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
              Back to Task
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h2 className="fw-bold mb-0">Transaction Dashboard</h2>
        <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
          <i className="bi bi-arrow-left"></i> Back to Task
        </button>
      </div>

      {/* Period Filter */}
      <div className="row g-2 align-items-end mb-3">
        <div className="col-auto">
          <label className="form-label">Period</label>
          <select 
            className="form-select" 
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            <option value="all">All time</option>
            <option value="3m">Last 3 months</option>
            <option value="6m">Last 6 months</option>
            <option value="12m">Last 12 months</option>
            <option value="ytd">Year to date</option>
          </select>
        </div>
      </div>

      {/* KPI Tiles */}
      <div className="row g-3 mb-4">
        <div className="col-md-3">
          <div className="card" style={{ borderLeft: '6px solid #ff6b35' }}>
            <div className="card-body">
              <div className="text-muted small text-uppercase">Total Money In</div>
              <div className="h4 fw-bold">£{data.tiles?.total_in?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card" style={{ borderLeft: '6px solid #ff6b35' }}>
            <div className="card-body">
              <div className="text-muted small text-uppercase">Total Money Out</div>
              <div className="h4 fw-bold">£{data.tiles?.total_out?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card" style={{ borderLeft: '6px solid #ff6b35' }}>
            <div className="card-body">
              <div className="text-muted small text-uppercase">Cash Deposits</div>
              <div className="h4 fw-bold">£{data.tiles?.cash_in?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
          </div>
        </div>
        <div className="col-md-3">
          <div className="card" style={{ borderLeft: '6px solid #ff6b35' }}>
            <div className="card-body">
              <div className="text-muted small text-uppercase">Cash Withdrawals</div>
              <div className="h4 fw-bold">£{data.tiles?.cash_out?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Additional KPIs */}
      <div className="row g-3 mb-4">
        <div className="col-md-6">
          <div className="card" style={{ borderLeft: '6px solid #ff6b35' }}>
            <div className="card-body">
              <div className="text-muted small text-uppercase">High Risk Payments</div>
              <div className="h4 fw-bold">£{data.tiles?.high_risk_total?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card" style={{ borderLeft: '6px solid #ff6b35' }}>
            <div className="card-body">
              <div className="text-muted small text-uppercase">Critical Alerts</div>
              <div className="h4 fw-bold">{data.kpis?.critical || 0}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="row g-4 mb-4">
        <div className="col-lg-8">
          <div className="card shadow-sm">
            <div className="card-header fw-semibold">
              Alerts Over Time — {customerId}
            </div>
            <div className="card-body" style={{ height: '260px' }}>
              {data.labels && data.labels.length > 0 ? (
                <Line
                  data={{
                    labels: data.labels,
                    datasets: [{
                      label: 'Alerts',
                      data: data.values,
                      tension: 0.3,
                      borderColor: '#0d6efd',
                      backgroundColor: 'rgba(13, 110, 253, 0.1)',
                      fill: true
                    }]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                      y: {
                        beginAtZero: true,
                        ticks: {
                          callback: (value) => value.toLocaleString()
                        }
                      }
                    },
                    plugins: {
                      tooltip: {
                        callbacks: {
                          label: (context) => `${context.dataset.label}: ${context.parsed.y.toLocaleString()}`
                        }
                      }
                    }
                  }}
                />
              ) : (
                <div className="d-flex align-items-center justify-content-center h-100">
                  <span className="text-muted">No alert data available for the selected period</span>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="col-lg-4">
          <div className="card shadow-sm">
            <div className="card-header fw-semibold">
              Top Countries (alerts) — {customerId}
            </div>
            <div className="card-body">
              {data.top_countries && data.top_countries.length > 0 ? (
                <ol className="mb-0">
                  {data.top_countries.map((row, idx) => (
                    <li key={idx}>{row.name || 'Unknown'} — {row.cnt}</li>
                  ))}
                </ol>
              ) : (
                <p className="text-muted mb-0">No data</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Reviewer Metrics */}
      <div className="card shadow-sm mb-4">
        <div className="card-header fw-semibold">Reviewer Metrics</div>
        <div className="card-body">
          <div className="row g-3">
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Avg Cash Deposits</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.avg_cash_deposits?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Avg Cash Withdrawals</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.avg_cash_withdrawals?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Avg Payment In</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.avg_in?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Avg Payment Out</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.avg_out?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Highest Payment In</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.max_in?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Highest Payment Out</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.max_out?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">Overseas Transactions (Value)</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.overseas_value?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
                <div className="text-muted small">{data.metrics?.overseas_pct?.toFixed(1) || '0.0'}% of total</div>
              </div>
            </div>
            <div className="col-6 col-md-3">
              <div className="border rounded p-3 h-100">
                <div className="text-muted small">High/High-3rd/Prohibited (Value)</div>
                <div className="fs-5 fw-semibold">£{data.metrics?.highrisk_value?.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</div>
                <div className="text-muted small">{data.metrics?.highrisk_pct?.toFixed(1) || '0.0'}% of total</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Monthly Money In vs Out Chart */}
      <div className="row g-4 mt-1">
        <div className="col-12">
          <div className="card shadow-sm">
            <div className="card-header fw-semibold">
              Monthly Money In vs Out — {customerId}
            </div>
            <div className="card-body" style={{ height: '300px' }}>
              {data.trend_labels && data.trend_labels.length > 0 ? (
                <Line
                  data={{
                    labels: data.trend_labels,
                    datasets: [
                      {
                        label: 'Money In',
                        data: data.trend_in,
                        tension: 0.3,
                        borderColor: '#198754',
                        backgroundColor: 'rgba(25, 135, 84, 0.1)',
                        fill: true
                      },
                      {
                        label: 'Money Out',
                        data: data.trend_out,
                        tension: 0.3,
                        borderColor: '#dc3545',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        fill: true
                      }
                    ]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                      y: {
                        beginAtZero: true,
                        ticks: {
                          callback: (value) => '£' + value.toLocaleString()
                        }
                      }
                    },
                    plugins: {
                      tooltip: {
                        callbacks: {
                          label: (context) => `${context.dataset.label}: £${context.parsed.y.toLocaleString()}`
                        }
                      }
                    }
                  }}
                />
              ) : (
                <div className="d-flex align-items-center justify-content-center h-100">
                  <span className="text-muted">No trend data available for the selected period</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TransactionDashboard;


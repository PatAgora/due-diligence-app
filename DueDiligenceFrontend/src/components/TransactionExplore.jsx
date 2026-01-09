import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function TransactionExplore({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    risk: '',
    date_from: '',
    date_to: ''
  });

  useEffect(() => {
    if (customerId) {
      fetchTransactions();
    }
  }, [customerId, filters]);

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      let url = `${BASE_URL}/api/transaction/explore?customer_id=${customerId}`;
      if (filters.risk) url += `&risk=${filters.risk}`;
      if (filters.date_from) url += `&date_from=${filters.date_from}`;
      if (filters.date_to) url += `&date_to=${filters.date_to}`;
      
      const response = await fetch(url, { credentials: 'include' });

      if (!response.ok) {
        throw new Error('Failed to fetch transactions');
      }

      const result = await response.json();
      
      // Debug logging
      console.log('[TransactionExplore] Total transactions:', result.transactions?.length);
      if (result.transactions && result.transactions.length > 0) {
        const tx = result.transactions[0];
        console.log('[TransactionExplore] First transaction:', {
          id: tx.id,
          country: tx.counterparty_country,
          risk_score: tx.risk_score,
          risk_level: tx.risk_level,
          has_alert: tx.has_alert,
          alert_severity: tx.alert_severity
        });
      }
      
      setData(result);
    } catch (err) {
      console.error('Error fetching transactions:', err);
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

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
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
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="alert alert-danger">
          <h5>Error loading transactions</h5>
          <p>{error}</p>
          <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4 px-5" style={{ paddingTop: '60px' }}>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h2 className="fw-bold mb-0">Transaction Statement</h2>
        <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
          <i className="bi bi-arrow-left"></i> Back to Task
        </button>
      </div>

      {/* Filters */}
      <form className="row g-2 mb-3" onSubmit={(e) => { e.preventDefault(); fetchTransactions(); }}>
        <div className="col-auto">
          <label className="form-label">Risk Level</label>
          <select 
            className="form-select" 
            value={filters.risk}
            onChange={(e) => handleFilterChange('risk', e.target.value)}
          >
            <option value="">All Transactions</option>
            <option value="HIGH">High Risk Only</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="LOW">Low Risk</option>
          </select>
        </div>
        <div className="col-auto">
          <label className="form-label">From Date</label>
          <input 
            type="date" 
            className="form-control" 
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
          />
        </div>
        <div className="col-auto">
          <label className="form-label">To Date</label>
          <input 
            type="date" 
            className="form-control" 
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
          />
        </div>
        <div className="col-auto d-flex align-items-end">
          <button type="submit" className="btn btn-primary">Apply Filters</button>
        </div>
      </form>

      {/* Bank Statement Table */}
      <div className="card">
        <div className="card-header bg-light">
          <h5 className="mb-0">Transaction History</h5>
        </div>
        <div className="card-body p-0">
          {data?.transactions && data.transactions.length > 0 ? (
            <div className="table-responsive">
              <table className="table table-hover mb-0">
                <thead className="table-light">
                  <tr>
                    <th>Date</th>
                    <th>Reference</th>
                    <th>Description</th>
                    <th>Counterparty</th>
                    <th>Country</th>
                    <th>Payment Method</th>
                    <th className="text-end">Amount</th>
                    <th className="text-center">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {data.transactions.map((tx, idx) => {
                    // Use risk_level from backend instead of calculating from risk_score
                    const riskLevel = tx.risk_level || 'LOW';
                    const riskScore = tx.risk_score || 0;
                    
                    // Map risk level to badge class
                    const riskClass = riskLevel === 'CRITICAL' ? 'danger' :
                                     riskLevel === 'HIGH' ? 'danger' :
                                     riskLevel === 'MEDIUM' ? 'warning' : 
                                     'success';
                    const riskLabel = riskLevel; // Use backend risk level directly
                    
                    return (
                      <tr key={idx} className={tx.flagged ? 'table-warning' : ''}>
                        <td className="text-nowrap">
                          {tx.transaction_date || '—'}
                        </td>
                        <td className="text-monospace small">
                          {tx.reference || `#${tx.id}`}
                        </td>
                        <td style={{ minWidth: '200px' }}>
                          {tx.description || '—'}
                        </td>
                        <td style={{ minWidth: '180px' }}>
                          {tx.counterparty || '—'}
                        </td>
                        <td>
                          <span className={riskLevel === 'CRITICAL' || riskLevel === 'HIGH' ? 'badge bg-danger' : ''}>
                            {tx.counterparty_country || '—'}
                          </span>
                        </td>
                        <td className="text-nowrap">
                          {tx.payment_method || '—'}
                        </td>
                        <td className="text-end fw-bold text-nowrap">
                          {tx.currency} {parseFloat(tx.amount || 0).toLocaleString('en-GB', { 
                            minimumFractionDigits: 2, 
                            maximumFractionDigits: 2 
                          })}
                        </td>
                        <td className="text-center">
                          <span className={`badge bg-${riskClass}`}>
                            {riskLabel}
                          </span>
                          <div className="small text-muted">
                            {(riskScore * 100).toFixed(0)}%
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot className="table-light">
                  <tr>
                    <td colSpan="6" className="text-end fw-bold">Total Transactions:</td>
                    <td className="text-end fw-bold">{data.transactions.length}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          ) : (
            <div className="p-4 text-center text-muted">
              <i className="bi bi-inbox" style={{ fontSize: '3rem' }}></i>
              <p className="mt-2">No transactions found for the selected filters.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TransactionExplore;

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function TransactionExplore({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    direction: '',
    channel: '',
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
      if (filters.direction) url += `&direction=${filters.direction}`;
      if (filters.channel) url += `&channel=${filters.channel}`;
      if (filters.risk) url += `&risk=${filters.risk}`;
      if (filters.date_from) url += `&date_from=${filters.date_from}`;
      if (filters.date_to) url += `&date_to=${filters.date_to}`;
      
      const response = await fetch(url, { credentials: 'include' });

      if (!response.ok) {
        throw new Error('Failed to fetch transactions');
      }

      const result = await response.json();
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
        <h2 className="fw-bold mb-0">Explore Transactions</h2>
        <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
          <i className="bi bi-arrow-left"></i> Back to Task
        </button>
      </div>

      {/* Filters */}
      <form className="row g-2 mb-3" onSubmit={(e) => { e.preventDefault(); fetchTransactions(); }}>
        <div className="col-auto">
          <label className="form-label">Direction</label>
          <select 
            className="form-select" 
            value={filters.direction}
            onChange={(e) => handleFilterChange('direction', e.target.value)}
          >
            <option value="">Any</option>
            <option value="in">In</option>
            <option value="out">Out</option>
          </select>
        </div>
        <div className="col-auto">
          <label className="form-label">Channel</label>
          <select 
            className="form-select" 
            value={filters.channel}
            onChange={(e) => handleFilterChange('channel', e.target.value)}
          >
            <option value="">Any</option>
            {data?.channels?.map(ch => (
              <option key={ch} value={ch}>{ch}</option>
            ))}
          </select>
        </div>
        <div className="col-auto">
          <label className="form-label">Risk</label>
          <select 
            className="form-select" 
            value={filters.risk}
            onChange={(e) => handleFilterChange('risk', e.target.value)}
          >
            <option value="">Any</option>
            <option value="HIGH">High</option>
            <option value="HIGH_3RD">High 3rd</option>
            <option value="PROHIBITED">Prohibited</option>
          </select>
        </div>
        <div className="col-auto">
          <label className="form-label">From</label>
          <input 
            type="date" 
            className="form-control" 
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
          />
        </div>
        <div className="col-auto">
          <label className="form-label">To</label>
          <input 
            type="date" 
            className="form-control" 
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
          />
        </div>
        <div className="col-auto d-flex align-items-end">
          <button type="submit" className="btn btn-primary">Apply</button>
        </div>
      </form>

      {/* Transactions Table */}
      <div className="card">
        <div className="card-body">
          {data?.transactions && data.transactions.length > 0 ? (
            <div className="table-responsive">
              <table className="table table-striped table-hover">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>ID</th>
                    <th>Direction</th>
                    <th className="text-end">Amount</th>
                    <th>Currency</th>
                    <th>Country</th>
                    <th>Channel</th>
                    <th>Narrative</th>
                  </tr>
                </thead>
                <tbody>
                  {data.transactions.map((tx, idx) => (
                    <tr key={idx}>
                      <td>{tx.txn_date}</td>
                      <td className="text-monospace small">{tx.id}</td>
                      <td>{tx.direction}</td>
                      <td className="text-end">£{parseFloat(tx.base_amount || 0).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                      <td>{tx.currency || 'GBP'}</td>
                      <td>{tx.country_iso2 || '—'}</td>
                      <td>{tx.channel || '—'}</td>
                      <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {tx.narrative || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted">No transactions found for this customer.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default TransactionExplore;

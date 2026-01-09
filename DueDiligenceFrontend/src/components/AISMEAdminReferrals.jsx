import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function AISMEAdminReferrals() {
  const [referrals, setReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [editingId, setEditingId] = useState(null);
  const [editAnswer, setEditAnswer] = useState('');
  const [editStatus, setEditStatus] = useState('');

  useEffect(() => {
    loadReferrals();
  }, [statusFilter]);

  const loadReferrals = async () => {
    try {
      setLoading(true);
      const url = statusFilter === 'all'
        ? `${BASE_URL}/api/sme/admin/referrals/data`
        : `${BASE_URL}/api/sme/admin/referrals/data?status=${statusFilter}`;
      
      const response = await fetch(url, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setReferrals(data.data || []);
      }
    } catch (error) {
      console.error('Error loading referrals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (id) => {
    try {
      const formData = new FormData();
      formData.append('id', id);
      if (editAnswer) formData.append('answer', editAnswer);
      if (editStatus) formData.append('status', editStatus);

      const response = await fetch(`${BASE_URL}/api/sme/admin/referrals/update`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      if (response.ok && data.status === 'ok') {
        setEditingId(null);
        setEditAnswer('');
        setEditStatus('');
        loadReferrals();
      } else {
        alert(data.message || 'Failed to update referral');
      }
    } catch (error) {
      alert('Error updating referral: ' + error.message);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const openCount = referrals.filter(r => (r.status || 'open') === 'open').length;
  const closedCount = referrals.filter(r => r.status === 'closed').length;

  return (
    <div>
      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Referrals Management</h5>
          <div className="d-flex gap-2">
            <select
              className="form-select form-select-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ width: 'auto' }}
            >
              <option value="all">All Status</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
            </select>
            <a
              href={`${BASE_URL}/api/sme/admin/referrals/export?fmt=json${statusFilter !== 'all' ? `&status=${statusFilter}` : ''}`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export JSON
            </a>
            <a
              href={`${BASE_URL}/api/sme/admin/referrals/export?fmt=csv${statusFilter !== 'all' ? `&status=${statusFilter}` : ''}`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export CSV
            </a>
          </div>
        </div>
        <div className="card-body">
          <div className="row mb-3">
            <div className="col-md-4">
              <div className="card bg-light">
                <div className="card-body text-center">
                  <h3>{referrals.length}</h3>
                  <small className="text-muted">Total Referrals</small>
                </div>
              </div>
            </div>
            <div className="col-md-4">
              <div className="card bg-warning bg-opacity-10">
                <div className="card-body text-center">
                  <h3 className="text-warning">{openCount}</h3>
                  <small className="text-muted">Open</small>
                </div>
              </div>
            </div>
            <div className="col-md-4">
              <div className="card bg-success bg-opacity-10">
                <div className="card-body text-center">
                  <h3 className="text-success">{closedCount}</h3>
                  <small className="text-muted">Closed</small>
                </div>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : referrals.length === 0 ? (
            <div className="text-center py-4 text-muted">
              <p>No referrals found</p>
            </div>
          ) : (
            <div className="list-group">
              {referrals.map((ref) => (
                <div key={ref.id} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div className="flex-grow-1">
                      <div className="d-flex align-items-center gap-2 mb-2">
                        <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'}`}>
                          {ref.status || 'open'}
                        </span>
                        <small className="text-muted">
                          {formatDate(ref.ts)}
                          {ref.task_id && (
                            <>
                              {' • '}
                              <Link to={`/view_task/${ref.task_id}`} className="text-decoration-none">
                                Task: {ref.task_id}
                              </Link>
                            </>
                          )}
                        </small>
                      </div>
                      <h6 className="mb-1">Question:</h6>
                      <p className="mb-2">{ref.question || '—'}</p>
                      {ref.answer && (
                        <>
                          <h6 className="mb-1">Answer (Chatbot):</h6>
                          <p className="mb-2 text-muted small">{ref.answer}</p>
                        </>
                      )}
                      {editingId === ref.id ? (
                        <div className="mb-3">
                          <label className="form-label">SME Response:</label>
                          <textarea
                            className="form-control mb-2"
                            rows="4"
                            value={editAnswer}
                            onChange={(e) => setEditAnswer(e.target.value)}
                            placeholder="Enter SME response..."
                          />
                          <select
                            className="form-select mb-2"
                            value={editStatus}
                            onChange={(e) => setEditStatus(e.target.value)}
                          >
                            <option value="">Keep current status</option>
                            <option value="open">Open</option>
                            <option value="closed">Closed</option>
                          </select>
                          <div className="d-flex gap-2">
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={() => handleUpdate(ref.id)}
                            >
                              Save
                            </button>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={() => {
                                setEditingId(null);
                                setEditAnswer('');
                                setEditStatus('');
                              }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <h6 className="mb-1">SME Response:</h6>
                          <p className="mb-2 fw-semibold">{ref.sme_response || 'No SME response yet'}</p>
                          <button
                            className="btn btn-sm btn-outline-primary"
                            onClick={() => {
                              setEditingId(ref.id);
                              setEditAnswer(ref.sme_response || '');
                              setEditStatus(ref.status || 'open');
                            }}
                          >
                            <i className="bi bi-pencil me-1"></i>
                            Edit
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  {ref.opened_by && (
                    <small className="text-muted">
                      Opened by: {ref.opened_by} • Count: {ref.count || 1}
                    </small>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AISMEAdminReferrals;


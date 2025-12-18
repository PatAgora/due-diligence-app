import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function SMEReferrals() {
  const [aiReferrals, setAiReferrals] = useState([]);
  const [manualReferrals, setManualReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [editingId, setEditingId] = useState(null);
  const [editAnswer, setEditAnswer] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [editingType, setEditingType] = useState(''); // 'ai' or 'manual'

  useEffect(() => {
    loadReferrals();
    const interval = setInterval(loadReferrals, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [statusFilter]);

  const loadReferrals = async () => {
    try {
      setLoading(true);
      
      // Load AI SME referrals
      const aiUrl = statusFilter === 'all'
        ? `${BASE_URL}/api/sme/admin/referrals/data`
        : `${BASE_URL}/api/sme/admin/referrals/data?status=${statusFilter}`;
      
      const aiResponse = await fetch(aiUrl, {
        credentials: 'include'
      });
      
      if (aiResponse.ok) {
        const aiData = await aiResponse.json();
        setAiReferrals(aiData.data || []);
      }
      
      // Load manual referrals
      const manualResponse = await fetch(`${BASE_URL}/api/my_referrals`, {
        credentials: 'include'
      });
      
      if (manualResponse.ok) {
        const manualData = await manualResponse.json();
        setManualReferrals(manualData.manual_referrals || []);
      }
    } catch (error) {
      console.error('Error loading referrals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (id, type) => {
    try {
      const formData = new FormData();
      formData.append('id', id);
      if (editAnswer) formData.append('answer', editAnswer);
      if (editStatus) formData.append('status', editStatus);

      // For AI referrals, use the admin update endpoint
      // For manual referrals, we'll need to create an endpoint or use the existing one
      const endpoint = type === 'ai' 
        ? `${BASE_URL}/api/sme/admin/referrals/update`
        : `${BASE_URL}/api/sme/manual_referrals/update`;

      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      if (response.ok && data.status === 'ok') {
        setEditingId(null);
        setEditAnswer('');
        setEditStatus('');
        setEditingType('');
        loadReferrals();
      } else {
        const errorMsg = data.message || data.error || `Failed to update referral (Status: ${response.status})`;
        console.error('Update failed:', { status: response.status, data });
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Error updating referral:', error);
      alert('Error updating referral: ' + error.message);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      return isNaN(date) ? dateStr : date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const escapeHtml = (text) => {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  const filteredAiReferrals = statusFilter === 'all' 
    ? aiReferrals 
    : statusFilter === 'open' 
      ? aiReferrals.filter(r => (r.status || 'open') !== 'closed')
      : aiReferrals.filter(r => r.status === 'closed');
  
  const filteredManualReferrals = statusFilter === 'all'
    ? manualReferrals
    : statusFilter === 'open'
      ? manualReferrals.filter(r => r.status !== 'closed')
      : manualReferrals.filter(r => r.status === 'closed');

  const totalCount = aiReferrals.length + manualReferrals.length;
  const openCount = aiReferrals.filter(r => (r.status || 'open') !== 'closed').length + 
                    manualReferrals.filter(r => r.status !== 'closed').length;

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">
          <i className="bi bi-clipboard-list me-2"></i>
          Referrals
        </h2>
        <div className="d-flex align-items-center gap-3">
          <select
            className="form-select form-select-sm"
            style={{ width: 'auto' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="open">Open Only</option>
            <option value="closed">Closed Only</option>
          </select>
          <button className="btn btn-sm btn-outline-secondary" onClick={loadReferrals}>
            <i className="bi bi-arrow-clockwise"></i> Refresh
          </button>
        </div>
      </div>

      <div className="alert alert-info">
        <i className="bi bi-info-circle me-2"></i>
        {totalCount} referral{totalCount === 1 ? '' : 's'} total
        {openCount > 0 && ` • ${openCount} open`}
      </div>

      {/* AI SME Referrals */}
      <div className="card mb-4">
        <div className="card-header bg-primary text-white">
          <h5 className="mb-0">
            <i className="fas fa-brain me-2"></i>
            AI SME Referrals ({filteredAiReferrals.length})
          </h5>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : filteredAiReferrals.length === 0 ? (
            <div className="text-center py-4 text-muted">
              <i className="fas fa-inbox fa-2x mb-2"></i>
              <p>No AI SME referrals found</p>
            </div>
          ) : (
            <div className="list-group">
              {filteredAiReferrals.map((ref) => (
                <div key={ref.id} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div className="flex-grow-1">
                      <div className="d-flex align-items-center gap-2 mb-2">
                        <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'}`}>
                          {ref.status || 'open'}
                        </span>
                        {ref.task_id && (
                          <Link to={`/view_task/${ref.task_id}`} className="text-decoration-none">
                            <strong>Task: {ref.task_id}</strong>
                          </Link>
                        )}
                        <small className="text-muted">
                          {formatDate(ref.ts)}
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
                      {editingId === ref.id && editingType === 'ai' ? (
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
                              onClick={() => handleUpdate(ref.id, 'ai')}
                            >
                              Save
                            </button>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={() => {
                                setEditingId(null);
                                setEditAnswer('');
                                setEditStatus('');
                                setEditingType('');
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
                              setEditingType('ai');
                            }}
                          >
                            <i className="bi bi-pencil me-1"></i>
                            {ref.sme_response ? 'Edit' : 'Answer'}
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

      {/* Manual Referrals */}
      <div className="card">
        <div className="card-header bg-secondary text-white">
          <h5 className="mb-0">
            <i className="fas fa-user-tie me-2"></i>
            Manual Referrals ({filteredManualReferrals.length})
          </h5>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : filteredManualReferrals.length === 0 ? (
            <div className="text-center py-4 text-muted">
              <i className="fas fa-inbox fa-2x mb-2"></i>
              <p>No manual referrals found</p>
            </div>
          ) : (
            <div className="list-group">
              {filteredManualReferrals.map((ref) => (
                <div key={ref.id} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div className="flex-grow-1">
                      <div className="d-flex align-items-center gap-2 mb-2">
                        <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'}`}>
                          {ref.status === 'closed' ? 'Closed' : 'Open'}
                        </span>
                        <Link to={`/view_task/${ref.task_id}`} className="text-decoration-none">
                          <strong>Task: {ref.task_id}</strong>
                        </Link>
                        <small className="text-muted">
                          {formatDate(ref.ts)}
                        </small>
                      </div>
                      <h6 className="mb-1">Query:</h6>
                      <p className="mb-2" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.query) }} />
                      {editingId === ref.id && editingType === 'manual' ? (
                        <div className="mb-3">
                          <label className="form-label">Answer:</label>
                          <textarea
                            className="form-control mb-2"
                            rows="4"
                            value={editAnswer}
                            onChange={(e) => setEditAnswer(e.target.value)}
                            placeholder="Enter answer..."
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
                              onClick={() => handleUpdate(ref.id, 'manual')}
                            >
                              Save
                            </button>
                            <button
                              className="btn btn-sm btn-secondary"
                              onClick={() => {
                                setEditingId(null);
                                setEditAnswer('');
                                setEditStatus('');
                                setEditingType('');
                              }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <h6 className="mb-1">Answer:</h6>
                          {ref.answer ? (
                            <p className="mb-2" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.answer) }} />
                          ) : (
                            <p className="mb-2 text-muted small fst-italic">Awaiting SME response...</p>
                          )}
                          <button
                            className="btn btn-sm btn-outline-primary"
                            onClick={() => {
                              setEditingId(ref.id);
                              setEditAnswer(ref.answer || '');
                              setEditStatus(ref.status || 'open');
                              setEditingType('manual');
                            }}
                          >
                            <i className="bi bi-pencil me-1"></i>
                            {ref.answer ? 'Edit' : 'Answer'}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SMEReferrals;


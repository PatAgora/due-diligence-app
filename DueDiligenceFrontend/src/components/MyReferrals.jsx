import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function MyReferrals() {
  const [aiReferrals, setAiReferrals] = useState([]);
  const [manualReferrals, setManualReferrals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    loadReferrals();
    const interval = setInterval(loadReferrals, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadReferrals = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/my_referrals`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error('Failed to load referrals');
      }
      
      const data = await response.json();
      setAiReferrals(data.ai_sme_referrals || []);
      setManualReferrals(data.manual_referrals || []);
    } catch (error) {
      console.error('Error loading referrals:', error);
    } finally {
      setLoading(false);
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

  const timeAgo = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const now = new Date();
      const then = new Date(dateStr);
      const diffMs = now - then;
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffMins = Math.floor(diffMs / (1000 * 60));

      if (diffDays > 0) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
      if (diffHours > 0) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
      if (diffMins > 0) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
      return 'Just now';
    } catch {
      return '—';
    }
  };

  const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  const filterReferrals = (referrals) => {
    if (!statusFilter) return referrals;
    if (statusFilter === 'open') {
      return referrals.filter(r => r.status !== 'closed');
    } else if (statusFilter === 'closed') {
      return referrals.filter(r => r.status === 'closed');
    }
    return referrals;
  };

  const filteredAiReferrals = filterReferrals(aiReferrals);
  const filteredManualReferrals = filterReferrals(manualReferrals);

  const totalCount = aiReferrals.length + manualReferrals.length;
  const openCount = aiReferrals.filter(r => r.status !== 'closed').length + 
                    manualReferrals.filter(r => r.status !== 'closed').length;

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">
          <i className="fas fa-clipboard-list me-2"></i>
          My Referrals
        </h2>
        <div className="d-flex align-items-center gap-3">
          <select
            className="form-select form-select-sm"
            style={{ width: 'auto' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Referrals</option>
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
        {statusFilter && ` (showing ${filteredAiReferrals.length + filteredManualReferrals.length} ${statusFilter})`}
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
                    <div>
                      <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'} me-2`}>
                        {ref.status === 'closed' ? 'Closed' : 'Open'}
                      </span>
                      {ref.task_id && (
                        <Link to={`/view_task/${ref.task_id}`} className="text-decoration-none ms-2">
                          <strong>Task: {ref.task_id}</strong>
                        </Link>
                      )}
                      <span className="text-muted small ms-2">
                        {ref.count} occurrence{ref.count === 1 ? '' : 's'}
                      </span>
                    </div>
                    <div className="text-muted small text-end">
                      <div>Raised: {formatDate(ref.ts)}</div>
                      <div>({timeAgo(ref.ts)})</div>
                    </div>
                  </div>
                  <div className="mb-2">
                    <strong>Question:</strong>
                    <div className="mt-1 p-2 bg-light rounded" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.question) }} />
                  </div>
                  {ref.answer && (
                    <div className="mb-2">
                      <strong>Answer (Chatbot):</strong>
                      <div className="mt-1 p-2 bg-light rounded text-muted" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.answer) }} />
                    </div>
                  )}
                  <div className="mb-2">
                    <strong>SME Response:</strong>
                    {ref.sme_response ? (
                      <div className="mt-1 p-2 bg-light rounded fw-semibold" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.sme_response) }} />
                    ) : (
                      <div className="mt-1 text-muted small fst-italic">
                        Awaiting SME response...
                      </div>
                    )}
                  </div>
                  {ref.last_ts && (
                    <div className="text-muted small">
                      Updated: {formatDate(ref.last_ts)} ({timeAgo(ref.last_ts)})
                    </div>
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
                    <div>
                      <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'} me-2`}>
                        {ref.status === 'closed' ? 'Closed' : 'Open'}
                      </span>
                      <Link to={`/view_task/${ref.task_id}`} className="text-decoration-none">
                        <strong>Task: {ref.task_id}</strong>
                      </Link>
                    </div>
                    <div className="text-muted small text-end">
                      <div>Raised: {formatDate(ref.ts)}</div>
                      <div>({timeAgo(ref.ts)})</div>
                    </div>
                  </div>
                  <div className="mb-2">
                    <strong>Query:</strong>
                    <div className="mt-1 p-2 bg-light rounded" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.query) }} />
                  </div>
                  {ref.answer && (
                    <div className="mb-2">
                      <strong>Answer:</strong>
                      <div className="mt-1 p-2 bg-light rounded" dangerouslySetInnerHTML={{ __html: escapeHtml(ref.answer) }} />
                    </div>
                  )}
                  {!ref.answer && (
                    <div className="mb-2 text-muted small fst-italic">
                      Awaiting SME response...
                    </div>
                  )}
                  {ref.last_ts && ref.last_ts !== ref.ts && (
                    <div className="text-muted small">
                      Returned: {formatDate(ref.last_ts)} ({timeAgo(ref.last_ts)})
                    </div>
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

export default MyReferrals;


import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import BaseLayout from './BaseLayout';
import './QCWIPCases.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function QCWIPCases() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [level, setLevel] = useState(1);
  const [bucket, setBucket] = useState('');
  const [reviewerName, setReviewerName] = useState('');
  
  // Get dashboard path based on user role
  const getDashboardPath = () => {
    const role = user?.role?.toLowerCase() || '';
    if (role === 'qc_1' || role === 'qc_2' || role === 'qc_3') return '/qc_lead_dashboard';
    if (role.startsWith('qc_lead_')) return '/qc_lead_dashboard';
    if (role.startsWith('qc_review_')) return '/qc_dashboard';
    if (role.startsWith('qc_')) return '/qc_dashboard';
    return '/qc_dashboard'; // Default fallback
  };
  
  // Check if user is a QC lead (can reassign tasks)
  const isQCLead = () => {
    const role = user?.role?.toLowerCase() || '';
    return role === 'qc_1' || role === 'qc_2' || role === 'qc_3' || role.startsWith('qc_lead_');
  };

  const reviewerId = searchParams.get('reviewer_id');
  const bucketParam = searchParams.get('bucket') || 'assigned';
  const dateRangeParam = searchParams.get('date_range');

  useEffect(() => {
    fetchCases();
  }, [reviewerId, bucketParam, dateRangeParam]);

  const fetchCases = async () => {
    try {
      setLoading(true);
      setError('');

      const params = new URLSearchParams();
      if (reviewerId) params.set('reviewer_id', reviewerId);
      params.set('bucket', bucketParam);
      if (dateRangeParam) params.set('date_range', dateRangeParam);

      const response = await fetch(`${BASE_URL}/api/qc_wip_cases?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load cases');
      }

      const data = await response.json();
      setCases(data.cases || []);
      setLevel(data.level || 1);
      setBucket(data.bucket || bucketParam);
      setReviewerName(data.reviewer_name || '');
    } catch (err) {
      console.error('Error fetching cases:', err);
      setError(err.message);
      setCases([]);
    } finally {
      setLoading(false);
    }
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
      <BaseLayout>
        <div className="container my-4">
          <div className="text-center py-5">
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
        <div className="container my-4">
          <div className="alert alert-danger">
            Error: {error}
          </div>
        </div>
      </BaseLayout>
    );
  }

  const bucketLabel = bucket.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const isAllWIP = bucket === 'all_wip' || (!reviewerId && bucket === 'assigned');

  return (
    <BaseLayout>
      <div className="container my-4">
        <div className="d-flex align-items-center justify-content-between mb-3">
          <h1 className="fw-bold mb-0">
            QC WIP
            {isAllWIP ? (
              <small className="text-muted fs-5"> • All Active WIP</small>
            ) : bucket ? (
              <small className="text-muted fs-5"> • {bucketLabel}</small>
            ) : null}
          </h1>
          <div className="d-flex gap-2">
            <Link
              to={getDashboardPath()}
              className="btn btn-sm btn-outline-secondary"
            >
              Back to Dashboard
            </Link>
            {isQCLead() && (
              <>
                {bucket === 'awaiting_assignment' ? (
                  <Link to="/qc_assign_tasks" className="btn btn-sm btn-primary">
                    <i className="bi bi-diagram-3"></i> Allocate QC
                  </Link>
                ) : (
                  <Link 
                    to={`/qc_reassign_tasks${reviewerId ? `?reviewer_id=${reviewerId}` : ''}`} 
                    className="btn btn-sm btn-warning"
                  >
                    <i className="bi bi-arrow-left-right"></i> Reassign QC
                  </Link>
                )}
              </>
            )}
          </div>
        </div>

        {reviewerName && (
          <div className="alert alert-light border shadow-sm mb-3">
            <strong>Reviewer:</strong> {reviewerName}
          </div>
        )}

        <div className="card shadow-sm p-3">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h5 className="mb-0">
              Cases <small className="text-muted">({cases.length})</small>
            </h5>
          </div>

          <div className="table-responsive" style={{ maxHeight: '70vh', overflow: 'auto' }}>
            <table className="table table-striped table-sm align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th style={{ minWidth: '110px' }}>Task</th>
                  <th>Customer</th>
                  <th>Watchlist</th>
                  <th className="text-end" style={{ width: '90px' }}>Score</th>
                  <th style={{ width: '160px' }}>Current QC</th>
                  <th style={{ width: '150px' }}>QC Start</th>
                  <th style={{ width: '150px' }}>QC End</th>
                  <th style={{ width: '140px' }}>Rework</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {cases.length > 0 ? (
                  cases.map((c, idx) => (
                    <tr key={idx}>
                      <td>
                        <Link to={`/qc_review/${c.task_id || c.id}`}>
                          {c.task_id || c.id}
                        </Link>
                      </td>
                      <td>{c.customer_name || c.customer_id || c.customer || '—'}</td>
                      <td>{c.watchlist_name || c.watchlist_id || c.watchlist || '—'}</td>
                      <td className="text-end">
                        {c.match_score ? parseFloat(c.match_score).toFixed(2) : '—'}
                      </td>
                      <td>{c.current_qc || c.reviewer_name || '—'}</td>
                      <td>{formatDate(c.qc_start_time || c.qc_start)}</td>
                      <td>{formatDate(c.qc_end_time || c.qc_end)}</td>
                      <td>
                        {c.rework_required || c.qc_rework_required ? (
                          (c.rework_completed || c.qc_rework_completed) ? (
                            <div>
                              <span className="badge text-bg-success">Completed</span>
                              {c.rework_completed_time && (
                                <div className="small text-muted mt-1">
                                  {formatDate(c.rework_completed_time)}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="badge text-bg-danger">Required</span>
                          )
                        ) : (
                          // Show completion time if rework was previously completed (qc_rework_completed = 1 but qc_rework_required = 0)
                          (c.rework_completed || c.qc_rework_completed) && c.rework_completed_time ? (
                            <div>
                              <span className="badge text-bg-success">Completed</span>
                              <div className="small text-muted mt-1">
                                {formatDate(c.rework_completed_time)}
                              </div>
                            </div>
                          ) : (
                            <span className="text-muted">—</span>
                          )
                        )}
                      </td>
                      <td>{c.status || '—'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="9" className="text-center text-muted py-4">
                      No cases found in this bucket.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default QCWIPCases;


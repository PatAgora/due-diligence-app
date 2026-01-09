import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './SMEReview.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function SMEReview() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [advice, setAdvice] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (taskId) {
      fetchTaskData();
    }
  }, [taskId]);

  const fetchTaskData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `${BASE_URL}/api/sme_review/${taskId}`,
        {
          credentials: 'include',
          headers: { 'Accept': 'application/json' },
        }
      );

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Task not found');
        }
        if (response.status === 403) {
          throw new Error('Access denied. SME role required.');
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const taskData = await response.json();
      setData(taskData);
      setAdvice(taskData.sme_advice || '');
    } catch (err) {
      console.error('Error fetching SME task:', err);
      setError(err.message || 'Failed to load task');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (action) => {
    try {
      setSubmitting(true);

      const response = await fetch(
        `${BASE_URL}/api/sme_review/${taskId}`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({
            advice,
            action, // 'return' or 'save'
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to submit SME review');
      }

      if (action === 'return') {
        alert('Task returned to reviewer successfully!');
        navigate('/sme_dashboard');
      } else {
        alert('SME advice saved successfully!');
      }
    } catch (err) {
      console.error('Error submitting SME review:', err);
      alert('Failed to submit: ' + err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
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
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={() => navigate('/sme_dashboard')}>
              Back to Dashboard
            </button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  const review = data?.review || {};

  return (
    <BaseLayout>
      <div className="container-fluid my-4">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h1 className="fw-bold">SME Review: {taskId}</h1>
          <button
            className="btn btn-outline-secondary"
            onClick={() => navigate('/sme_dashboard')}
          >
            <i className="bi bi-arrow-left me-2"></i>
            Back to Dashboard
          </button>
        </div>

        <div className="row">
          <div className="col-lg-8">
            {/* Reviewer Query */}
            <div className="card mb-3 shadow-sm">
              <div className="card-header bg-warning bg-opacity-10">
                <h5 className="mb-0">
                  <i className="bi bi-question-circle me-2"></i>
                  Reviewer Query
                </h5>
              </div>
              <div className="card-body">
                <p className="mb-0">
                  {review.sme_query || 'No query provided'}
                </p>
              </div>
            </div>

            {/* Task Details */}
            <div className="card mb-3 shadow-sm">
              <div className="card-header">
                <h5 className="mb-0">Task Details</h5>
              </div>
              <div className="card-body">
                <dl className="row mb-0">
                  <dt className="col-sm-3">Customer Name</dt>
                  <dd className="col-sm-9">{review.customer_name || '—'}</dd>

                  <dt className="col-sm-3">Match Score</dt>
                  <dd className="col-sm-9">
                    <span className="badge bg-info">
                      {review.match_score || 'N/A'}
                    </span>
                  </dd>

                  <dt className="col-sm-3">Referred By</dt>
                  <dd className="col-sm-9">{review.referred_by_name || '—'}</dd>

                  <dt className="col-sm-3">Referred Date</dt>
                  <dd className="col-sm-9">
                    {review.sme_selected_date
                      ? new Date(review.sme_selected_date).toLocaleString()
                      : '—'}
                  </dd>
                </dl>
              </div>
            </div>

            {/* SME Advice */}
            <div className="card mb-3 shadow-sm">
              <div className="card-header bg-success bg-opacity-10">
                <h5 className="mb-0">
                  <i className="bi bi-chat-left-text me-2"></i>
                  SME Advice
                </h5>
              </div>
              <div className="card-body">
                <textarea
                  className="form-control"
                  rows="8"
                  value={advice}
                  onChange={(e) => setAdvice(e.target.value)}
                  placeholder="Enter your expert advice here..."
                  disabled={submitting}
                ></textarea>
                <div className="text-muted small mt-2">
                  Provide guidance to help the reviewer make a decision
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="d-flex gap-2">
              <button
                className="btn btn-success"
                onClick={() => handleSubmit('return')}
                disabled={submitting || !advice.trim()}
              >
                {submitting ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2"></span>
                    Submitting...
                  </>
                ) : (
                  <>
                    <i className="bi bi-arrow-return-left me-2"></i>
                    Return to Reviewer
                  </>
                )}
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleSubmit('save')}
                disabled={submitting}
              >
                <i className="bi bi-save me-2"></i>
                Save Draft
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => navigate('/sme_dashboard')}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
          </div>

          {/* Sidebar */}
          <div className="col-lg-4">
            <div className="card shadow-sm sticky-top">
              <div className="card-header">
                <h6 className="mb-0">SME Info</h6>
              </div>
              <div className="card-body">
                <dl className="small mb-0">
                  <dt>Status</dt>
                  <dd>
                    <span className="badge bg-warning">
                      {review.sme_returned_date ? 'Returned' : 'In Progress'}
                    </span>
                  </dd>

                  <dt>Level</dt>
                  <dd>{review.level || '—'}</dd>

                  {review.sme_returned_date && (
                    <>
                      <dt>Returned At</dt>
                      <dd>
                        {new Date(review.sme_returned_date).toLocaleString()}
                      </dd>
                    </>
                  )}
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default SMEReview;


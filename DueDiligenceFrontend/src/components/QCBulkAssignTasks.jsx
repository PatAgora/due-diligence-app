import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './BulkAssignTasks.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function QCBulkAssignTasks() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reviewers, setReviewers] = useState([]);
  const [selectedReviewers, setSelectedReviewers] = useState([]);
  const [taskCount, setTaskCount] = useState('');
  const [priority, setPriority] = useState('date');
  const [unassignedCount, setUnassignedCount] = useState(0);
  const [level, setLevel] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${BASE_URL}/api/qc_assign_tasks_bulk`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load data');
      }

      const data = await response.json();
      setReviewers(data.reviewers || []);
      setUnassignedCount(data.unassigned_count || 0);
      setLevel(data.level || 1);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewerToggle = (reviewerId) => {
    setSelectedReviewers(prev =>
      prev.includes(reviewerId)
        ? prev.filter(id => id !== reviewerId)
        : [...prev, reviewerId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (selectedReviewers.length === 0) {
      alert('Please select at least one reviewer');
      return;
    }

    // Validate task count
    const count = parseInt(taskCount);
    if (!taskCount || isNaN(count) || count < 1) {
      alert('Please enter a valid number of tasks (minimum 1)');
      return;
    }

    try {
      setSubmitting(true);
      setSuccess(false);

      const response = await fetch(`${BASE_URL}/api/qc_assign_tasks_bulk`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          selected_reviewers: selectedReviewers,
          task_count: count,
          priority: priority
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to assign tasks');
      }

      const result = await response.json();
      setSuccess(true);
      alert(result.message || 'Tasks assigned successfully');
      setSelectedReviewers([]);
      fetchData();
    } catch (err) {
      console.error('Error assigning tasks:', err);
      alert(`Error: ${err.message}`);
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
            <button className="btn btn-primary" onClick={fetchData}>Retry</button>
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container my-4">
        <div className="mb-4">
          <h2 className="mb-0">Bulk Assign QC Tasks</h2>
        </div>

        {success && (
          <div className="alert alert-success alert-dismissible fade show">
            Tasks have been assigned successfully.
            <button type="button" className="btn-close" onClick={() => setSuccess(false)}></button>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="row">
            {/* Reviewer Selection */}
            <div className="col-md-6">
              <h5 className="mb-3">QC Reviewers</h5>
              <div className="reviewer-list mb-3">
                {reviewers.length > 0 ? (
                  <div className="list-group">
                    {reviewers.map((reviewer) => (
                      <label
                        key={reviewer.id}
                        className={`list-group-item reviewer-card ${selectedReviewers.includes(reviewer.id) ? 'active' : ''}`}
                      >
                        <div className="d-flex justify-content-between align-items-center">
                          <div className="d-flex align-items-center">
                            <input
                              type="checkbox"
                              className="form-check-input me-3"
                              checked={selectedReviewers.includes(reviewer.id)}
                              onChange={() => handleReviewerToggle(reviewer.id)}
                            />
                            <div>
                              <strong>{reviewer.display_name || reviewer.name}</strong>
                              <br />
                              <small className="text-muted">
                                Level {level} QC Reviewer
                              </small>
                            </div>
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted">No available QC reviewers.</p>
                )}
              </div>
            </div>

            {/* Configuration */}
            <div className="col-md-6">
              <h5 className="mb-3">Assignment Settings</h5>
              
              <div className="mb-3">
                <label htmlFor="task_count" className="form-label">Tasks per Reviewer</label>
                <input
                  type="number"
                  id="task_count"
                  className="form-control"
                  value={taskCount}
                  onChange={(e) => {
                    const val = e.target.value;
                    // Allow empty string, or valid number
                    if (val === '' || (!isNaN(val) && parseInt(val) > 0)) {
                      setTaskCount(val);
                    }
                  }}
                  min="1"
                  required
                  placeholder="Enter number of tasks"
                />
              </div>

              <div className="mb-3">
                <label htmlFor="priority" className="form-label">Assignment Priority</label>
                <select
                  id="priority"
                  className="form-select"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                >
                  <option value="score">Highest Score</option>
                  <option value="date">Oldest First</option>
                </select>
              </div>

              <div className="mb-3">
                <label className="form-label">Unassigned Tasks Available:</label>
                <div>
                  <span className="badge bg-secondary fs-5">{unassignedCount || 0}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 d-flex justify-content-end">
            <button
              type="submit"
              className="btn btn-dark px-4"
              disabled={submitting || selectedReviewers.length === 0}
            >
              {submitting ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2"></span>
                  Assigning...
                </>
              ) : (
                'Assign in Bulk'
              )}
            </button>
          </div>
        </form>
      </div>
    </BaseLayout>
  );
}

export default QCBulkAssignTasks;


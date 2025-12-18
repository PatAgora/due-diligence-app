import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './AssignTasks.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AssignTasks() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [unassignedTasks, setUnassignedTasks] = useState([]);
  const [reviewers, setReviewers] = useState([]);
  const [selectedTasks, setSelectedTasks] = useState([]);
  const [selectedReviewer, setSelectedReviewer] = useState('');
  const [unassignedCount, setUnassignedCount] = useState(0);
  const [assignmentCounts, setAssignmentCounts] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${BASE_URL}/api/assign_tasks`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load assignment data');
      }

      const data = await response.json();
      setUnassignedTasks(data.unassigned_tasks || []);
      setReviewers(data.reviewers || []);
      setUnassignedCount(data.unassigned_count || 0);
      setAssignmentCounts(data.assignment_counts || {});
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleTaskToggle = (taskId) => {
    setSelectedTasks(prev =>
      prev.includes(taskId)
        ? prev.filter(id => id !== taskId)
        : [...prev, taskId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (selectedTasks.length === 0 || !selectedReviewer) {
      alert('Please select both tasks and a reviewer');
      return;
    }

    try {
      setSubmitting(true);

      const response = await fetch(`${BASE_URL}/api/assign_tasks`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          task_ids: selectedTasks,
          reviewer_id: selectedReviewer
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to assign tasks');
      }

      alert(`${selectedTasks.length} task(s) assigned successfully`);
      setSelectedTasks([]);
      setSelectedReviewer('');
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
          <h2 className="mb-0">Assign Tasks to Reviewers</h2>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="row">
            {/* Unassigned Tasks Panel */}
            <div className="col-md-6">
              <h5 className="mb-3">Unassigned Tasks</h5>
              <div className="task-list mb-3">
                {unassignedTasks.length > 0 ? (
                  <div className="list-group">
                    {unassignedTasks.map((task) => (
                      <label
                        key={task.id}
                        className={`list-group-item task-card ${selectedTasks.includes(task.id) ? 'active' : ''}`}
                      >
                        <div className="d-flex justify-content-between align-items-center">
                          <div className="d-flex align-items-center">
                            <input
                              type="checkbox"
                              className="form-check-input me-3"
                              checked={selectedTasks.includes(task.id)}
                              onChange={() => handleTaskToggle(task.id)}
                            />
                            <div>
                              <strong>{task.task_id}</strong>
                              <br />
                              <small className="text-muted">
                                Status: Under Review | Score: {task.total_score?.toFixed(2) || '0.00'}
                              </small>
                            </div>
                          </div>
                          <span className="badge bg-secondary">
                            {task.updated_at ? new Date(task.updated_at).toLocaleDateString() : '—'}
                          </span>
                        </div>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted">No unassigned tasks.</p>
                )}
              </div>
            </div>

            {/* Reviewer Selection Panel */}
            <div className="col-md-6">
              <h5 className="mb-3">Reviewers</h5>
              <div className="reviewer-list">
                {reviewers.length > 0 ? (
                  <div className="list-group">
                    {reviewers.map((reviewer) => (
                      <label
                        key={reviewer.id}
                        className={`list-group-item reviewer-card ${selectedReviewer === reviewer.id.toString() ? 'active' : ''}`}
                      >
                        <div className="d-flex justify-content-between align-items-center">
                          <div className="d-flex align-items-center">
                            <input
                              type="radio"
                              name="reviewer_id"
                              className="form-check-input me-3"
                              value={reviewer.id}
                              checked={selectedReviewer === reviewer.id.toString()}
                              onChange={(e) => setSelectedReviewer(e.target.value)}
                            />
                            <div>
                              <strong>{reviewer.name}</strong>
                              <br />
                              <small className="text-muted">
                                Level {reviewer.level} – {reviewer.role}
                              </small>
                              <br />
                              <small className="text-muted">
                                In Progress: {reviewer.open_tasks || 0}
                              </small>
                            </div>
                          </div>
                          <span className="badge bg-primary" title="Current Open Tasks">
                            {reviewer.open_tasks || 0}
                          </span>
                        </div>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted">No available reviewers.</p>
                )}
              </div>
            </div>
          </div>

          {/* Assign Button and Task Count */}
          <div className="mt-4 d-flex justify-content-between align-items-center">
            <div>
              <label className="form-label mb-0">Unassigned Tasks Available:</label>
              <span className="badge bg-secondary ms-2">{unassignedCount}</span>
            </div>
            <button
              type="submit"
              className="btn btn-dark px-4"
              disabled={submitting || selectedTasks.length === 0 || !selectedReviewer}
            >
              {submitting ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2"></span>
                  Assigning...
                </>
              ) : (
                'Assign Selected'
              )}
            </button>
          </div>
        </form>
      </div>
    </BaseLayout>
  );
}

export default AssignTasks;

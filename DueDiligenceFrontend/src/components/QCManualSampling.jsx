import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './QCManualSampling.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function QCManualSampling() {
  const navigate = useNavigate();
  const [completedTasks, setCompletedTasks] = useState([]);
  const [selectedTasks, setSelectedTasks] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [autoSampling, setAutoSampling] = useState(false);

  useEffect(() => {
    fetchCompletedTasks();
  }, []);

  const fetchCompletedTasks = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await fetch(`${BASE_URL}/api/qc_manual_sampling`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load completed tasks');
      }

      const data = await response.json();
      setCompletedTasks(data.tasks || []);
    } catch (err) {
      console.error('Error fetching completed tasks:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedTasks(new Set(completedTasks.map(t => t.task_id)));
    } else {
      setSelectedTasks(new Set());
    }
  };

  const handleTaskToggle = (taskId) => {
    const newSelected = new Set(selectedTasks);
    if (newSelected.has(taskId)) {
      newSelected.delete(taskId);
    } else {
      newSelected.add(taskId);
    }
    setSelectedTasks(newSelected);
  };

  const handleManualSubmit = async () => {
    if (selectedTasks.size === 0) {
      alert('Please select at least one task to send to QC.');
      return;
    }

    try {
      setSubmitting(true);
      const response = await fetch(`${BASE_URL}/api/qc_manual_sampling`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          task_ids: Array.from(selectedTasks),
          action: 'manual'
        })
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Successfully sent ${data.sent_count || selectedTasks.size} task(s) to QC.`);
        setSelectedTasks(new Set());
        fetchCompletedTasks();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to send tasks to QC' }));
        alert(errorData.error || 'Failed to send tasks to QC');
      }
    } catch (err) {
      console.error('Error sending tasks to QC:', err);
      alert('Error sending tasks to QC. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAutoSampling = async () => {
    try {
      setSubmitting(true);
      setAutoSampling(true);
      
      const response = await fetch(`${BASE_URL}/api/qc_manual_sampling`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          action: 'auto'
        })
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Automatic sampling complete. ${data.sent_count || 0} task(s) sent to QC.`);
        fetchCompletedTasks();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to run automatic sampling' }));
        alert(errorData.error || 'Failed to run automatic sampling');
      }
    } catch (err) {
      console.error('Error running automatic sampling:', err);
      alert('Error running automatic sampling. Please try again.');
    } finally {
      setSubmitting(false);
      setAutoSampling(false);
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
          <div className="alert alert-danger">{error}</div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container-fluid my-4 px-5">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h2 className="fw-bold mb-0">
            <i className="bi bi-clipboard-check me-2"></i>
            QC Sampling
          </h2>
          <div className="d-flex gap-2">
            <button
              className="btn btn-outline-primary"
              onClick={handleAutoSampling}
              disabled={submitting || autoSampling}
            >
              {autoSampling ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                  Running...
                </>
              ) : (
                <>
                  <i className="bi bi-arrow-repeat me-2"></i>
                  Run Automatic Sampling
                </>
              )}
            </button>
          </div>
        </div>

        <div className="card shadow-sm mb-4">
          <div className="card-header bg-primary text-white">
            <h5 className="mb-0">
              <i className="bi bi-list-check me-2"></i>
              Manual Sampling - Select Tasks for QC
            </h5>
          </div>
          <div className="card-body">
            <p className="text-muted mb-3">
              Select completed tasks that have not been sampled yet to manually send them to QC. 
              Tasks not selected will remain in "Completed" status.
            </p>

            {completedTasks.length === 0 ? (
              <div className="alert alert-info">
                <i className="bi bi-info-circle me-2"></i>
                No completed tasks available for sampling. All completed tasks have either been sampled or are already in QC.
              </div>
            ) : (
              <>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div>
                    <strong>{completedTasks.length}</strong> completed task(s) available for sampling
                    {selectedTasks.size > 0 && (
                      <span className="ms-2 text-primary">
                        ({selectedTasks.size} selected)
                      </span>
                    )}
                  </div>
                  <div className="form-check">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      id="selectAll"
                      checked={selectedTasks.size === completedTasks.length && completedTasks.length > 0}
                      onChange={handleSelectAll}
                    />
                    <label className="form-check-label" htmlFor="selectAll">
                      Select All
                    </label>
                  </div>
                </div>

                <div className="table-responsive" style={{ maxHeight: '60vh', overflow: 'auto' }}>
                  <table className="table table-striped table-hover">
                    <thead className="table-light sticky-top">
                      <tr>
                        <th style={{ width: '40px' }}>
                          <input
                            type="checkbox"
                            checked={selectedTasks.size === completedTasks.length && completedTasks.length > 0}
                            onChange={handleSelectAll}
                          />
                        </th>
                        <th>Task ID</th>
                        <th>Customer ID</th>
                        <th>Completed By</th>
                        <th>Completed Date</th>
                        <th>Reviewer</th>
                        <th>Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {completedTasks.map((task) => (
                        <tr key={task.task_id}>
                          <td>
                            <input
                              type="checkbox"
                              checked={selectedTasks.has(task.task_id)}
                              onChange={() => handleTaskToggle(task.task_id)}
                            />
                          </td>
                          <td>
                            <Link
                              to={`/view_task/${task.task_id}`}
                              className="text-decoration-none"
                            >
                              {task.task_id}
                            </Link>
                          </td>
                          <td>{task.customer_id || '—'}</td>
                          <td>{task.completed_by_name || '—'}</td>
                          <td>
                            {task.completed_at 
                              ? new Date(task.completed_at).toLocaleString() 
                              : '—'}
                          </td>
                          <td>{task.reviewer_name || '—'}</td>
                          <td>
                            <span className={`badge ${
                              task.outcome === 'Retain' ? 'bg-success' :
                              task.outcome === 'Exit' ? 'bg-danger' :
                              'bg-secondary'
                            }`}>
                              {task.outcome || '—'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-3 pt-3 border-top">
                  <button
                    className="btn btn-primary btn-lg"
                    onClick={handleManualSubmit}
                    disabled={submitting || selectedTasks.size === 0}
                  >
                    {submitting ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                        Sending to QC...
                      </>
                    ) : (
                      <>
                        <i className="bi bi-send me-2"></i>
                        Send Selected to QC ({selectedTasks.size})
                      </>
                    )}
                  </button>
                  <button
                    className="btn btn-outline-secondary btn-lg ms-2"
                    onClick={fetchCompletedTasks}
                    disabled={submitting}
                  >
                    <i className="bi bi-arrow-clockwise me-2"></i>
                    Refresh
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="card shadow-sm">
          <div className="card-header bg-info text-white">
            <h6 className="mb-0">
              <i className="bi bi-info-circle me-2"></i>
              How It Works
            </h6>
          </div>
          <div className="card-body">
            <ul className="mb-0">
              <li>
                <strong>Manual Sampling:</strong> Select specific completed tasks to send to QC. 
                Selected tasks will move to "QC - Awaiting Allocation" status.
              </li>
              <li>
                <strong>Automatic Sampling:</strong> Runs the automatic sampling process based on configured sampling rates. 
                Tasks are randomly selected according to the rates set in Sampling Rates Configuration.
              </li>
              <li>
                Tasks not selected for sampling will remain in "Completed" status and will not go through QC.
              </li>
              <li>
                Once a task is sent to QC, it can be assigned to QC reviewers via the "Assign Tasks" or "Bulk Assign" pages.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default QCManualSampling;


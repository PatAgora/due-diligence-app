import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './QCAssignTasks.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function QCReassignTasks() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [qcReviewers, setQcReviewers] = useState([]);
  const [assignedRows, setAssignedRows] = useState([]);
  const [selectedTasks, setSelectedTasks] = useState(new Set());
  const [selectedReviewer, setSelectedReviewer] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [level, setLevel] = useState(1);
  const [currentReviewerId, setCurrentReviewerId] = useState(null);
  const [currentReviewerName, setCurrentReviewerName] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError('');
      
      // Get reviewer_id from query params if present
      const reviewerId = searchParams.get('reviewer_id');
      
      // Fetch QC reviewers
      const reviewersResponse = await fetch(`${BASE_URL}/api/qc_assign_tasks`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!reviewersResponse.ok) {
        throw new Error('Failed to load QC reviewers');
      }

      const reviewersData = await reviewersResponse.json();
      setQcReviewers(reviewersData.qc_reviewers || []);
      setLevel(reviewersData.level || 1);

      // Fetch assigned tasks
      const params = new URLSearchParams();
      if (reviewerId) {
        params.set('reviewer_id', reviewerId);
        setCurrentReviewerId(reviewerId);
      }
      params.set('bucket', 'assigned');

      const tasksResponse = await fetch(`${BASE_URL}/api/qc_wip_cases?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!tasksResponse.ok) {
        throw new Error('Failed to load assigned tasks');
      }

      const tasksData = await tasksResponse.json();
      setAssignedRows(tasksData.cases || []);
      if (tasksData.reviewer_name) {
        setCurrentReviewerName(tasksData.reviewer_name);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedTasks(new Set(assignedRows.map(r => r.task_id || r.id)));
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (selectedTasks.size === 0) {
      alert('Please select at least one task.');
      return;
    }

    if (!selectedReviewer) {
      alert('Please select a QC reviewer.');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('qc_reviewer_id', selectedReviewer);
      Array.from(selectedTasks).forEach(taskId => {
        formData.append('task_ids', taskId);
      });

      const response = await fetch(`${BASE_URL}/api/qc_reassign_tasks`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
        headers: { 'Accept': 'application/json' },
      });

      if (response.ok) {
        const data = await response.json();
        alert(`Reassigned ${selectedTasks.size} task(s) to the selected QC reviewer.`);
        setSelectedTasks(new Set());
        setSelectedReviewer('');
        fetchData();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to reassign tasks' }));
        alert(errorData.error || 'Failed to reassign tasks');
      }
    } catch (err) {
      console.error('Error reassigning tasks:', err);
      alert('Error reassigning tasks. Please try again.');
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
      <div className="container my-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h1 className="fw-bold mb-0">Reassign QC Tasks – Level {level}</h1>
          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={() => navigate('/qc_wip_cases' + (currentReviewerId ? `?reviewer_id=${currentReviewerId}` : ''))}
          >
            Back to QC WIP
          </button>
        </div>

        {currentReviewerName && (
          <div className="alert alert-info mb-3">
            <strong>Current Reviewer:</strong> {currentReviewerName}
          </div>
        )}

        <form onSubmit={handleSubmit} className="card shadow-sm p-3">
          <div className="d-flex gap-2 align-items-center mb-3">
            <label className="me-2 mb-0">Reassign to:</label>
            <select
              name="qc_reviewer_id"
              className="form-select form-select-sm w-auto"
              value={selectedReviewer}
              onChange={(e) => setSelectedReviewer(e.target.value)}
              required
            >
              <option value="">Select QC Reviewer…</option>
              {qcReviewers.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.display_name}
                </option>
              ))}
            </select>
            <button type="submit" className="btn btn-primary btn-sm">
              Reassign Selected
            </button>
          </div>

          <div className="table-responsive" style={{ maxHeight: '60vh', overflow: 'auto' }}>
            <table className="table table-striped table-sm align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th style={{ width: '28px' }}>
                    <input
                      type="checkbox"
                      id="chk_all"
                      aria-label="Select all"
                      checked={selectedTasks.size === assignedRows.length && assignedRows.length > 0}
                      onChange={handleSelectAll}
                    />
                  </th>
                  <th>Task</th>
                  <th>Customer</th>
                  <th>Current QC</th>
                  <th>QC Start</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {assignedRows.length > 0 ? (
                  assignedRows.map((row) => {
                    const taskId = row.task_id || row.id;
                    return (
                      <tr key={taskId}>
                        <td>
                          <input
                            type="checkbox"
                            name="task_ids"
                            value={taskId}
                            checked={selectedTasks.has(taskId)}
                            onChange={() => handleTaskToggle(taskId)}
                          />
                        </td>
                        <td>{taskId}</td>
                        <td>{row.customer_name || row.customer_id || row.customer || '—'}</td>
                        <td>{row.current_qc || row.reviewer_name || '—'}</td>
                        <td>{row.qc_start_time || row.qc_start || '—'}</td>
                        <td>{row.status || '—'}</td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="6" className="text-center text-muted">
                      No assigned tasks found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </form>
      </div>
    </BaseLayout>
  );
}

export default QCReassignTasks;


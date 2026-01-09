import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';
import './QCAssignTasks.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function QCAssignTasks() {
  const navigate = useNavigate();
  const [qcReviewers, setQcReviewers] = useState([]);
  const [unassignedRows, setUnassignedRows] = useState([]);
  const [selectedTasks, setSelectedTasks] = useState(new Set());
  const [selectedReviewer, setSelectedReviewer] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [level, setLevel] = useState(1);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await fetch(`${BASE_URL}/api/qc_assign_tasks`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load data');
      }

      const data = await response.json();
      setQcReviewers(data.qc_reviewers || []);
      setUnassignedRows(data.unassigned_rows || []);
      setLevel(data.level || 1);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedTasks(new Set(unassignedRows.map(r => r.task_id)));
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

      const response = await fetch(`${BASE_URL}/api/qc_assign_tasks`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
        headers: { 'Accept': 'application/json' },
      });

      if (response.ok) {
        alert(`Allocated ${selectedTasks.size} task(s) to the selected QC reviewer.`);
        setSelectedTasks(new Set());
        setSelectedReviewer('');
        fetchData();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to allocate tasks' }));
        alert(errorData.error || 'Failed to allocate tasks');
      }
    } catch (err) {
      console.error('Error allocating tasks:', err);
      alert('Error allocating tasks. Please try again.');
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
        <h1 className="fw-bold mb-3">Allocate QC – Level {level}</h1>

        <form onSubmit={handleSubmit} className="card shadow-sm p-3">
          <div className="d-flex gap-2 align-items-center mb-3">
            <label className="me-2 mb-0">Assign to:</label>
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
              Allocate Selected
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
                      checked={selectedTasks.size === unassignedRows.length && unassignedRows.length > 0}
                      onChange={handleSelectAll}
                    />
                  </th>
                  <th>Task</th>
                  <th>Completed At</th>
                  <th>Completed By</th>
                </tr>
              </thead>
              <tbody>
                {unassignedRows.length > 0 ? (
                  unassignedRows.map((row) => (
                    <tr key={row.task_id}>
                      <td>
                        <input
                          type="checkbox"
                          name="task_ids"
                          value={row.task_id}
                          checked={selectedTasks.has(row.task_id)}
                          onChange={() => handleTaskToggle(row.task_id)}
                        />
                      </td>
                      <td>{row.task_id}</td>
                      <td>{row.completed_at || '—'}</td>
                      <td>{row.completed_by || '—'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="4" className="text-center text-muted">
                      No cases awaiting QC assignment.
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

export default QCAssignTasks;


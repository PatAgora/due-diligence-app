import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import BaseLayout from './BaseLayout';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function OperationsCases() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cases, setCases] = useState([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchCases();
  }, [searchParams]);

  const fetchCases = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams(searchParams);
      const response = await fetch(`${BASE_URL}/api/operations/cases?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error('Failed to load cases');
      }

      const data = await response.json();
      setCases(data.cases || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Error fetching cases:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="container-fluid px-4 my-4">
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
        <div className="container-fluid px-4 my-4">
          <div className="alert alert-danger">
            Error: {error}
          </div>
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <div className="container-fluid px-4 my-4">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <div>
            <button className="btn btn-outline-secondary me-2" onClick={() => navigate(-1)}>
              <i className="bi bi-arrow-left me-1"></i>Back
            </button>
            <h2 className="d-inline-block mb-0 ms-2">Cases</h2>
          </div>
          <span className="badge bg-primary fs-6">{total} case(s)</span>
        </div>

        <div className="card shadow-sm">
          <div className="card-body">
            {/* Display active filters */}
            {(searchParams.get('status') || searchParams.get('outcome') || searchParams.get('age_bucket')) && (
              <div className="mb-3">
                <strong>Filters: </strong>
                {searchParams.get('status') && (
                  <span className="badge bg-info me-2">Status: {searchParams.get('status')}</span>
                )}
                {searchParams.get('outcome') && (
                  <span className="badge bg-info me-2">Outcome: {searchParams.get('outcome')}</span>
                )}
                {searchParams.get('age_bucket') && (
                  <span className="badge bg-info me-2">Age: {searchParams.get('age_bucket')}</span>
                )}
                {searchParams.get('qc') && (
                  <span className="badge bg-info me-2">QC Checked</span>
                )}
              </div>
            )}

            <div className="table-responsive">
              <table className="table table-striped table-hover align-middle">
                <thead className="table-dark">
                  <tr>
                    <th>Task ID</th>
                    <th>Customer ID</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Updated At</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.length > 0 ? (
                    cases.map((c) => (
                      <tr key={c.id}>
                        <td>{c.task_id || c.id || '—'}</td>
                        <td>{c.customer_id || '—'}</td>
                        <td>{c.status || '—'}</td>
                        <td>{c.outcome || '—'}</td>
                        <td>{c.updated_at ? new Date(c.updated_at).toLocaleString() : '—'}</td>
                        <td>
                          <button 
                            className="btn btn-sm btn-primary"
                            onClick={() => navigate(`/view_task/${c.task_id || c.id}`)}
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="6" className="text-center text-muted py-4">
                        No cases found for the selected filters
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default OperationsCases;


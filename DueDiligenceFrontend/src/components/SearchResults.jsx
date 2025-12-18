import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { usePermissions } from '../contexts/PermissionsContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function SearchResults() {
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const { canEdit } = usePermissions();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const query = searchParams.get('query') || '';
  const searchType = searchParams.get('type') || 'all';

  useEffect(() => {
    if (query) {
      fetchResults();
    } else {
      setResults([]);
      setLoading(false);
    }
  }, [query, searchType]);

  const fetchResults = async () => {
    try {
      setLoading(true);
      setError('');

      const params = new URLSearchParams({
        query: query,
        type: searchType
      });

      const response = await fetch(`${BASE_URL}/api/search?${params.toString()}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to search' }));
        throw new Error(errorData.error || 'Failed to search');
      }

      const data = await response.json();
      setResults(data.results || []);
    } catch (err) {
      console.error('Error searching:', err);
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-GB', {
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

  const getRowBgColor = (status) => {
    if (!status) return 'transparent';
    const s = status.toLowerCase();
    if (s.includes('completed')) return '#d4edda';
    if (s.includes('rework')) return '#fff3cd';
    if (s.includes('pending')) return '#cfe2ff';
    if (s.includes('overdue') || s.includes('chaser')) return '#f8d7da';
    return 'transparent';
  };

  const canEditTasks = canEdit('review_tasks') || canEdit('review');

  if (loading) {
    return (
      <div className="container-fluid px-3 my-3">
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-fluid px-3 my-3">
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid px-3 my-3">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="mb-1">Search Results</h2>
          <p className="text-muted mb-0">
            {query && (
              <>
                Searching for "<strong>{query}</strong>" in <strong>{searchType === 'all' ? 'All Fields' : searchType.replace('_', ' ').toUpperCase()}</strong>
              </>
            )}
          </p>
        </div>
        <span className="badge bg-primary fs-6">{results.length} result(s)</span>
      </div>

      {results.length > 0 ? (
        <div className="table-responsive">
          <table className="table table-striped table-hover align-middle" style={{ width: '100%' }}>
            <thead className="table-dark">
              <tr>
                <th>Task ID</th>
                <th>Customer ID</th>
                <th>Watchlist ID</th>
                <th>Hit Type</th>
                <th>Total Score</th>
                <th>Status</th>
                <th>Assigned To</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr
                  key={result.task_id}
                  style={{ backgroundColor: getRowBgColor(result.status) }}
                >
                  <td>{result.task_id}</td>
                  <td>{result.customer_id || '—'}</td>
                  <td>{result.watchlist_id || '—'}</td>
                  <td>{result.hit_type || '—'}</td>
                  <td>{result.total_score || '—'}</td>
                  <td>{result.status || 'Unknown'}</td>
                  <td>{result.assigned_to || 'Unassigned'}</td>
                  <td>{formatDate(result.updated_at)}</td>
                  <td>
                    {canEditTasks ? (
                      <Link
                        to={`/view_task/${result.task_id}`}
                        className="btn btn-sm btn-primary"
                      >
                        View
                      </Link>
                    ) : (
                      <span className="btn btn-sm btn-secondary" style={{ cursor: 'not-allowed', opacity: 0.6 }}>
                        View
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="alert alert-info">
          {query ? (
            <>No results found for "<strong>{query}</strong>"</>
          ) : (
            <>Enter a search query to find tasks</>
          )}
        </div>
      )}
    </div>
  );
}

export default SearchResults;


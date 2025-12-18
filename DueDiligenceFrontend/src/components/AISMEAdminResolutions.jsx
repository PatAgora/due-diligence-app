import React, { useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AISMEAdminResolutions() {
  const [resolutions, setResolutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    question: '',
    answer: '',
    approved_by: 'SME',
    ticket_id: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    loadResolutions();
  }, []);

  const loadResolutions = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/sme/admin/resolutions`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setResolutions(data.data || []);
      }
    } catch (error) {
      console.error('Error loading resolutions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setResult(null);
      
      const submitData = new FormData();
      submitData.append('question', formData.question);
      submitData.append('answer', formData.answer);
      submitData.append('approved_by', formData.approved_by);
      if (formData.ticket_id) submitData.append('ticket_id', formData.ticket_id);

      const response = await fetch(`${BASE_URL}/api/sme/admin/resolutions`, {
        method: 'POST',
        credentials: 'include',
        body: submitData
      });

      const data = await response.json();
      if (response.ok && data.status === 'ok') {
        setResult({ type: 'success', message: 'SME Resolution added successfully!' });
        setFormData({ question: '', answer: '', approved_by: 'SME', ticket_id: '' });
        setShowAddForm(false);
        loadResolutions();
      } else {
        setResult({ type: 'error', message: data.message || 'Failed to add resolution' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message || 'Failed to add resolution' });
    } finally {
      setSubmitting(false);
      setTimeout(() => setResult(null), 4000);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      return date.toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div>
      <div className="card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">SME Resolutions</h5>
          <div className="d-flex gap-2">
            <button
              className="btn btn-sm btn-primary"
              onClick={() => setShowAddForm(!showAddForm)}
            >
              <i className="bi bi-plus-circle me-1"></i>
              {showAddForm ? 'Cancel' : 'Add Resolution'}
            </button>
            <a
              href={`${BASE_URL}/api/sme/admin/resolutions/export?fmt=json`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export JSON
            </a>
            <a
              href={`${BASE_URL}/api/sme/admin/resolutions/export?fmt=csv`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export CSV
            </a>
          </div>
        </div>
        <div className="card-body">
          {showAddForm && (
            <div className="card bg-light mb-4">
              <div className="card-body">
                <h6>Add New SME Resolution</h6>
                <form onSubmit={handleSubmit}>
                  <div className="mb-3">
                    <label htmlFor="question" className="form-label">Question *</label>
                    <textarea
                      className="form-control"
                      id="question"
                      rows="2"
                      value={formData.question}
                      onChange={(e) => setFormData({ ...formData, question: e.target.value })}
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label htmlFor="answer" className="form-label">Answer *</label>
                    <textarea
                      className="form-control"
                      id="answer"
                      rows="4"
                      value={formData.answer}
                      onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
                      required
                    />
                  </div>
                  <div className="row">
                    <div className="col-md-6 mb-3">
                      <label htmlFor="approved_by" className="form-label">Approved By</label>
                      <input
                        type="text"
                        className="form-control"
                        id="approved_by"
                        value={formData.approved_by}
                        onChange={(e) => setFormData({ ...formData, approved_by: e.target.value })}
                      />
                    </div>
                    <div className="col-md-6 mb-3">
                      <label htmlFor="ticket_id" className="form-label">Ticket ID (Optional)</label>
                      <input
                        type="text"
                        className="form-control"
                        id="ticket_id"
                        value={formData.ticket_id}
                        onChange={(e) => setFormData({ ...formData, ticket_id: e.target.value })}
                      />
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? 'Adding...' : 'Add Resolution'}
                  </button>
                  {result && (
                    <div className={`alert alert-${result.type === 'success' ? 'success' : 'danger'} mt-3`}>
                      {result.message}
                    </div>
                  )}
                </form>
              </div>
            </div>
          )}

          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : resolutions.length === 0 ? (
            <div className="text-center py-4 text-muted">
              <p>No SME resolutions found</p>
              <small>Add your first resolution above</small>
            </div>
          ) : (
            <div className="list-group">
              {resolutions.map((res) => (
                <div key={res.qa_id} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <div className="flex-grow-1">
                      <div className="d-flex align-items-center gap-2 mb-2">
                        {res.approved && (
                          <span className="badge bg-success">Approved</span>
                        )}
                        {res.ticket_id && (
                          <span className="badge bg-info">Ticket: {res.ticket_id}</span>
                        )}
                        <small className="text-muted">
                          {formatDate(res.created_at)}
                          {res.approved_by && ` • Approved by: ${res.approved_by}`}
                        </small>
                      </div>
                      <h6 className="mb-1">Question:</h6>
                      <p className="mb-2">{res.title || res.question || '—'}</p>
                      <h6 className="mb-1">Answer:</h6>
                      <p className="mb-0 text-muted">{res.answer_preview || '—'}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AISMEAdminResolutions;


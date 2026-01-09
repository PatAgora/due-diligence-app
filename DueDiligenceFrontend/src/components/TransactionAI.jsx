import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function TransactionAI({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState('3m');
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);
  const [building, setBuilding] = useState(false);
  const [outreachText, setOutreachText] = useState(null);
  const [assessing, setAssessing] = useState(false);

  useEffect(() => {
    if (customerId) {
      fetchAIData();
    }
  }, [customerId, period]);

  const fetchAIData = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${BASE_URL}/api/transaction/ai?customer_id=${customerId}&period=${period}`,
        { credentials: 'include' }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch AI data');
      }

      const result = await response.json();
      setData(result);
      
      // Initialize answers state
      const answersMap = {};
      (result.answers || []).forEach(a => {
        if (a.id) {
          answersMap[a.id] = a.answer || '';
        }
      });
      setAnswers(answersMap);
      
      // Clear outreach text on refresh
      setOutreachText(null);
    } catch (err) {
      console.error('Error fetching AI data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBuildQuestions = async () => {
    try {
      setBuilding(true);
      const formData = new FormData();
      formData.append('customer_id', customerId);
      formData.append('period', period);
      formData.append('action', 'build');

      const response = await fetch(
        `${BASE_URL}/api/transaction/ai`,
        {
          method: 'POST',
          credentials: 'include',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error('Failed to build questions');
      }

      const result = await response.json();
      alert(result.message || 'Questions prepared successfully');
      await fetchAIData(); // Refresh data
    } catch (err) {
      console.error('Error building questions:', err);
      alert('Error building questions: ' + err.message);
    } finally {
      setBuilding(false);
    }
  };

  const handleSaveAnswers = async () => {
    try {
      setSaving(true);
      const formData = new FormData();
      formData.append('customer_id', customerId);
      formData.append('period', period);
      formData.append('action', 'save');
      formData.append('case_id', data.case?.id || '');

      // Add all question IDs and answers
      Object.keys(answers).forEach(qid => {
        formData.append('qid', qid);
        formData.append(`answer_${qid}`, answers[qid] || '');
      });

      const response = await fetch(
        `${BASE_URL}/api/transaction/ai`,
        {
          method: 'POST',
          credentials: 'include',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error('Failed to save answers');
      }

      const result = await response.json();
      alert(result.message || 'Responses saved successfully');
      await fetchAIData(); // Refresh data
    } catch (err) {
      console.error('Error saving answers:', err);
      alert('Error saving answers: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleBuildOutreach = async () => {
    try {
      setBuilding(true);
      const formData = new FormData();
      formData.append('customer_id', customerId);
      formData.append('period', period);
      formData.append('action', 'outreach');
      formData.append('case_id', data.case?.id || '');

      const response = await fetch(
        `${BASE_URL}/api/transaction/ai`,
        {
          method: 'POST',
          credentials: 'include',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error('Failed to build outreach pack');
      }

      const result = await response.json();
      setOutreachText(result.outreach_text);
    } catch (err) {
      console.error('Error building outreach:', err);
      alert('Error building outreach: ' + err.message);
    } finally {
      setBuilding(false);
    }
  };

  const handleRunAssessment = async () => {
    try {
      setAssessing(true);
      const formData = new FormData();
      formData.append('customer_id', customerId);
      formData.append('period', period);
      formData.append('action', 'assess');
      formData.append('case_id', data.case?.id || '');

      const response = await fetch(
        `${BASE_URL}/api/transaction/ai`,
        {
          method: 'POST',
          credentials: 'include',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error('Failed to run assessment');
      }

      const result = await response.json();
      alert(result.message || 'Assessment completed successfully');
      await fetchAIData(); // Refresh data to show assessment results
    } catch (err) {
      console.error('Error running assessment:', err);
      alert('Error running assessment: ' + err.message);
    } finally {
      setAssessing(false);
    }
  };

  const handleBackToTask = () => {
    const basePath = window.location.pathname.startsWith('/qc_review/') 
      ? `/qc_review/${taskId}`
      : `/view_task/${taskId}`;
    navigate(basePath);
  };

  if (loading) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="text-center">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="alert alert-danger">
          <h5>Error loading AI Outreach</h5>
          <p>{error}</p>
          <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  const rows = (data?.answers && data.answers.length > 0) ? data.answers : data?.proposed_questions || [];

  return (
    <div className="container-fluid my-4 px-5" style={{ paddingTop: '60px' }}>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h2 className="fw-bold mb-0">AI Outreach</h2>
        <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
          <i className="bi bi-arrow-left"></i> Back to Task
        </button>
      </div>

      {/* Period Filter */}
      <form className="row g-2 align-items-end mb-3">
        <div className="col-auto">
          <label className="form-label">Period</label>
          <select 
            className="form-select" 
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            <option value="all">All time</option>
            <option value="3m">Last 3 months</option>
            <option value="6m">Last 6 months</option>
            <option value="12m">Last 12 months</option>
          </select>
        </div>
        <div className="col-auto">
          <button className="btn btn-outline-secondary mt-4" type="button" onClick={fetchAIData}>
            Apply
          </button>
        </div>
      </form>

      {customerId && (
        <div className="alert alert-info py-2 d-flex align-items-center justify-content-between">
          <div>
            Prepared questions are based on alerts for <strong>{customerId}</strong>
            {data?.period_from && data?.period_to && ` (range: ${data.period_from} → ${data.period_to})`}.
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="d-flex gap-2 mb-3">
        <button 
          className="btn btn-primary" 
          onClick={handleBuildQuestions}
          disabled={building}
        >
          {building ? 'Preparing...' : 'Prepare Questions'}
        </button>
        {data?.case && (
          <button 
            className="btn btn-secondary" 
            onClick={handleBuildOutreach}
            disabled={building}
          >
            Build Outreach Pack
          </button>
        )}
      </div>

      {/* Outreach Email Display */}
      {outreachText && (
        <div className="card mb-3">
          <div className="card-header fw-semibold">Draft Outreach Email</div>
          <div className="card-body">
            <p className="text-muted small mb-2">Copy/paste into your email tool (or export later):</p>
            <pre className="mb-0" style={{ whiteSpace: 'pre-wrap' }}>
              {outreachText}
            </pre>
          </div>
        </div>
      )}

      {/* Questions Table */}
      <div className="card">
        <div className="card-header d-flex align-items-center justify-content-between">
          <div className="fw-semibold">
            {data?.case ? (
              <>{data.case.created_at || '—'}</>
            ) : (
              <>No case yet — click "Prepare Questions"</>
            )}
          </div>

          {data?.case?.assessment_risk && (
            <div>
              <span className="badge text-bg-dark me-2">
                Residual Score: {data.case.assessment_score || '—'}
              </span>
              <span className={`badge text-bg-${data.case.assessment_risk in ['CRITICAL','HIGH'] ? 'danger' : data.case.assessment_risk === 'MEDIUM' ? 'warning' : 'secondary'}`}>
                {data.case.assessment_risk}
              </span>
            </div>
          )}
        </div>

        <div className="card-body p-0">
          <table className="table table-bordered table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th style={{ width: '14rem' }}>Rule Tag</th>
                <th>Customer Question (normalised & transaction-specific)</th>
                <th style={{ width: '36%' }}>Answer / Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.length > 0 ? (
                rows.map((r, idx) => (
                  <tr key={r.id || idx}>
                    <td>
                      <span className="badge text-bg-secondary">{r.tag || '—'}</span>
                      {r.source_details && r.source_details.length > 0 && (
                        <div className="small mt-2">
                          Linked alerts: {r.source_details.length}
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="fw-semibold mb-1">
                        {r.question_nice || r.question || '—'}
                      </div>
                    </td>
                    <td>
                      {r.id ? (
                        <textarea 
                          className="form-control" 
                          rows={4}
                          value={answers[r.id] || ''}
                          onChange={(e) => setAnswers({...answers, [r.id]: e.target.value})}
                          placeholder="Add the customer's response or your notes here..."
                        />
                      ) : (
                        <div className="text-muted">
                          Will be created after you click <strong>Prepare Questions</strong>.
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3} className="text-muted text-center py-5">
                    No questions yet. Click <strong>Prepare Questions</strong> to generate them.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {rows.length > 0 && data?.case && (
            <div className="d-flex gap-2 p-3">
              <button 
                className="btn btn-primary" 
                onClick={handleSaveAnswers}
                disabled={saving}
              >
                {saving ? 'Saving...' : 'Save Responses'}
              </button>
              <button 
                className="btn btn-outline-success" 
                onClick={handleRunAssessment}
                disabled={assessing}
              >
                {assessing ? 'Running...' : 'Run Assessment'}
              </button>
            </div>
          )}
        </div>

        {data?.case?.assessment_summary && (
          <div className="card-footer">
            <h6 className="fw-semibold mb-2">Assessment Summary</h6>
            <pre className="mb-0" style={{ whiteSpace: 'pre-wrap' }}>
              {data.case.assessment_summary}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default TransactionAI;

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function TransactionAIRationale({ customerId, taskId }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState('3m');
  const [natureOfBusiness, setNatureOfBusiness] = useState('');
  const [estIncome, setEstIncome] = useState('');
  const [estExpenditure, setEstExpenditure] = useState('');
  const [generating, setGenerating] = useState(false);
  const [taskStatus, setTaskStatus] = useState(null);
  const isCompleted = taskStatus && taskStatus.toLowerCase() === 'completed';

  useEffect(() => {
    if (customerId) {
      fetchRationaleData();
    }
  }, [customerId, period]);

  // Fetch task status
  useEffect(() => {
    if (taskId) {
      const fetchTaskStatus = async () => {
        try {
          const isQCReview = window.location.pathname.startsWith('/qc_review/');
          const apiUrl = isQCReview 
            ? `${BASE_URL}/api/qc_review/${taskId}`
            : `${BASE_URL}/api/reviewer_panel/${taskId}`;
          
          const response = await fetch(apiUrl, { credentials: 'include' });
          if (response.ok) {
            const result = await response.json();
            setTaskStatus(result.review?.status || null);
          }
        } catch (e) {
          console.error('Failed to fetch task status:', e);
        }
      };
      fetchTaskStatus();
    }
  }, [taskId]);

  const fetchRationaleData = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${BASE_URL}/api/transaction/ai-rationale?customer_id=${customerId}&period=${period}`,
        { credentials: 'include' }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch rationale data');
      }

      const result = await response.json();
      setData(result);
      
      // Pre-fill form if rationale exists
      if (result.rationale) {
        setNatureOfBusiness(result.rationale.nature_of_business || '');
        setEstIncome(result.rationale.est_income ? String(result.rationale.est_income) : '');
        setEstExpenditure(result.rationale.est_expenditure ? String(result.rationale.est_expenditure) : '');
      }
    } catch (err) {
      console.error('Error fetching rationale data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (isCompleted) {
      alert('Cannot update rationale: Task is completed.');
      return;
    }
    try {
      setGenerating(true);
      const formData = new FormData();
      formData.append('customer_id', customerId);
      formData.append('period', period);
      formData.append('action', 'generate');
      if (taskId) {
        formData.append('task_id', taskId);
      }
      formData.append('nature_of_business', natureOfBusiness);
      formData.append('est_income', estIncome);
      formData.append('est_expenditure', estExpenditure);

      const response = await fetch(
        `${BASE_URL}/api/transaction/ai-rationale`,
        {
          method: 'POST',
          credentials: 'include',
          body: formData
        }
      );

      if (!response.ok) {
        throw new Error('Failed to generate rationale');
      }

      const result = await response.json();
      setData(result);
      alert('Rationale generated successfully');
    } catch (err) {
      console.error('Error generating rationale:', err);
      alert('Error generating rationale: ' + err.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopyToClipboard = async () => {
    const rationaleText = data?.rationale?.rationale_text;
    if (!rationaleText) return;
    
    try {
      await navigator.clipboard.writeText(rationaleText);
      alert('Copied to clipboard!');
    } catch (e) {
      alert('Copy failed. Select the text and copy manually.');
    }
  };

  const handleExtractToDueDiligence = async () => {
    if (isCompleted) {
      alert('Cannot extract rationale: Task is completed.');
      return;
    }
    if (!taskId || !data?.rationale?.rationale_text) {
      alert('No rationale available to extract.');
      return;
    }

    try {
      const response = await fetch(`${BASE_URL}/api/transaction/extract_rationale/${taskId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          rationale_text: data.rationale.rationale_text,
          nature_of_business: natureOfBusiness,
          est_income: estIncome,
          est_expenditure: estExpenditure
        })
      });

      if (response.ok) {
        alert('Rationale extracted to Due Diligence module successfully!');
        // Optionally navigate back to task
        const basePath = window.location.pathname.startsWith('/qc_review/') 
          ? `/qc_review/${taskId}`
          : `/view_task/${taskId}`;
        navigate(basePath);
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to extract rationale' }));
        alert(errorData.error || 'Failed to extract rationale');
      }
    } catch (err) {
      console.error('Error extracting rationale:', err);
      alert('Error extracting rationale. Please try again.');
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
          <h5>Error loading AI Rationale</h5>
          <p>{error}</p>
          <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4 px-5" style={{ paddingTop: '60px' }}>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h2 className="fw-bold mb-0">AI Rationale</h2>
        <button className="btn btn-sm btn-outline-secondary" onClick={handleBackToTask}>
          <i className="bi bi-arrow-left"></i> Back to Task
        </button>
      </div>

      {/* Period Filter */}
      <form method="get" className="row g-2 align-items-end mb-3">
        <div className="col-auto">
          <label className="form-label">Period</label>
          <select 
            className="form-select" 
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            disabled={isCompleted}
          >
            <option value="all">All time</option>
            <option value="3m">Last 3 months</option>
            <option value="6m">Last 6 months</option>
            <option value="12m">Last 12 months</option>
            <option value="ytd">Year to date</option>
          </select>
        </div>
        <div className="col-auto">
          <button className="btn btn-outline-secondary mt-4" type="button" onClick={fetchRationaleData} disabled={isCompleted}>
            Apply
          </button>
        </div>
      </form>

      {customerId && (
        <>
          {isCompleted && (
            <div className="alert alert-warning mb-3">
              <i className="fas fa-lock me-2"></i>
              <strong>Task is Completed:</strong> Trasnaction Rationale cannot be updated anymore.
            </div>
          )}
          {/* Analyst Inputs */}
          <form onSubmit={handleGenerate} className="card mb-3">
            <div className="card-header fw-semibold">Analyst Inputs</div>
            <div className="card-body">
              <div className="row g-3">
                <div className="col-12">
                  <label className="form-label">Nature of business</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    value={natureOfBusiness}
                    onChange={(e) => setNatureOfBusiness(e.target.value)}
                    placeholder="e.g., Building supplies"
                    disabled={isCompleted}
                  />
                </div>
                <div className="col-md-6">
                  <label className="form-label">Estimated monthly income (£)</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    value={estIncome}
                    onChange={(e) => setEstIncome(e.target.value)}
                    inputMode="decimal"
                    placeholder="e.g., 11000"
                    disabled={isCompleted}
                  />
                </div>
                <div className="col-md-6">
                  <label className="form-label">Estimated monthly expenditure (£)</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    value={estExpenditure}
                    onChange={(e) => setEstExpenditure(e.target.value)}
                    inputMode="decimal"
                    placeholder="e.g., 7500"
                    disabled={isCompleted}
                  />
                </div>
              </div>
            </div>
            <div className="card-footer d-flex gap-2">
              <button className="btn btn-primary" type="submit" disabled={generating || isCompleted}>
                {generating ? 'Generating...' : 'Generate Rationale'}
              </button>
              {data?.rationale?.rationale_text && (
                <>
                  <button className="btn btn-outline-secondary" type="button" onClick={handleCopyToClipboard}>
                    Copy to clipboard
                  </button>
                  <button className="btn btn-success" type="button" onClick={handleExtractToDueDiligence} disabled={isCompleted}>
                    <i className="bi bi-download me-2"></i>
                    Extract to Due Diligence
                  </button>
                </>
              )}
            </div>
          </form>

          {/* Output */}
          <div className="card">
            <div className="card-header fw-semibold">Rationale Output</div>
            <div className="card-body">
              {data?.rationale?.rationale_text ? (
                <pre className="mb-0" style={{ whiteSpace: 'pre-wrap' }}>
                  {data.rationale.rationale_text}
                </pre>
              ) : (
                <p className="text-muted mb-0">
                  Fill in any analyst inputs above and click <strong>Generate Rationale</strong>.
                </p>
              )}
            </div>
          </div>
        </>
      )}

      {!customerId && (
        <div className="card">
          <div className="card-body">
            <p className="mb-0 text-muted">
              Enter a <strong>Customer</strong> and select a <strong>Period</strong> to begin.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default TransactionAIRationale;

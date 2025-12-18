import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import SumsubVerification from './SumsubVerification';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

/**
 * Wrapper component that fetches review data from task and renders Sumsub verification
 * This replaces the task view when Sumsub link is clicked
 */
function SumsubVerificationWrapper() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [reviewId, setReviewId] = useState(null);
  const [customerId, setCustomerId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (taskId) {
      fetchTaskData();
    }
  }, [taskId]);

  const fetchTaskData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/sumsub/get_task_data/${taskId}`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      setReviewId(result.review_id);
      setCustomerId(result.customer_id);
    } catch (e) {
      console.error("Failed to fetch task data:", e);
      setError(`Failed to load task data: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ marginLeft: '100px', margin: 0, padding: 0, paddingTop: '60px', width: '100%', height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ margin: 0, padding: '1rem', paddingTop: '60px', width: '100%' }}>
        <div className="alert alert-danger">
          <h4 className="alert-heading">Error</h4>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => {
            const basePath = window.location.pathname.startsWith('/qc_review/') 
              ? `/qc_review/${taskId}`
              : `/view_task/${taskId}`;
            navigate(basePath);
          }}>
            Go Back to Task
          </button>
        </div>
      </div>
    );
  }

  if (!reviewId || !customerId) {
    return (
      <div style={{ margin: 0, padding: '1rem', paddingTop: '60px', width: '100%' }}>
        <div className="alert alert-warning">
          <h4 className="alert-heading">Missing Data</h4>
          <p>Review ID or Customer ID not found for this task.</p>
          <button className="btn btn-primary" onClick={() => {
            const basePath = window.location.pathname.startsWith('/qc_review/') 
              ? `/qc_review/${taskId}`
              : `/view_task/${taskId}`;
            navigate(basePath);
          }}>
            Go Back to Task
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ paddingTop: '60px' }}>
      <SumsubVerification taskId={taskId} reviewId={reviewId} customerId={customerId} />
    </div>
  );
}

export default SumsubVerificationWrapper;



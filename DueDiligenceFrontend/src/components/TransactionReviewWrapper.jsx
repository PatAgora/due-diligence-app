import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import TransactionDashboard from './TransactionDashboard';
import TransactionAlerts from './TransactionAlerts';
import TransactionExplore from './TransactionExplore';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';
import TransactionAI from './TransactionAI';
import TransactionAIRationale from './TransactionAIRationale';

/**
 * Wrapper component that fetches customer_id from task and renders Transaction Review UI
 * This replaces the task view when Transaction Review links are clicked
 */
function TransactionReviewWrapper({ view }) {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [customerId, setCustomerId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (taskId) {
      fetchCustomerId();
    }
  }, [taskId]);

  const fetchCustomerId = async () => {
    try {
      setLoading(true);
      // Determine which API endpoint to use based on current route
      const isQCReview = window.location.pathname.startsWith('/qc_review/');
      const apiEndpoint = isQCReview 
        ? `${BASE_URL}/api/qc_review/${taskId}`
        : `${BASE_URL}/api/reviewer_panel/${taskId}`;
      
      const response = await fetch(apiEndpoint, {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Failed to fetch task data');
      }

      const data = await response.json();
      const customerIdFromTask = data?.review?.customer_id || data?.customer_id;
      
      if (!customerIdFromTask) {
        setError('No customer ID found for this task');
      } else {
        setCustomerId(customerIdFromTask);
      }
    } catch (err) {
      console.error('Error fetching customer ID:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="text-center">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <p className="mt-2">Loading transaction data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="alert alert-warning">
          <h5>Unable to load Transaction Review</h5>
          <p>{error}</p>
          <button 
            className="btn btn-sm btn-outline-secondary"
            onClick={() => {
              // Navigate back to task view
              const basePath = window.location.pathname.startsWith('/qc_review/') 
                ? `/qc_review/${taskId}`
                : `/view_task/${taskId}`;
              navigate(basePath);
            }}
          >
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  if (!customerId) {
    return (
      <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
        <div className="alert alert-info">
          <h5>No Customer ID</h5>
          <p>This task does not have a customer ID associated with it. Transaction Review requires a customer ID.</p>
          <button 
            className="btn btn-sm btn-outline-secondary"
            onClick={() => {
              const basePath = window.location.pathname.startsWith('/qc_review/') 
                ? `/qc_review/${taskId}`
                : `/view_task/${taskId}`;
              navigate(basePath);
            }}
          >
            Back to Task
          </button>
        </div>
      </div>
    );
  }

  // Render the appropriate Transaction Review component
  switch (view) {
    case 'dashboard':
      return <TransactionDashboard customerId={customerId} taskId={taskId} />;
    case 'alerts':
      return <TransactionAlerts customerId={customerId} taskId={taskId} />;
    case 'explore':
      return <TransactionExplore customerId={customerId} taskId={taskId} />;
    case 'ai':
      return <TransactionAI customerId={customerId} taskId={taskId} />;
    case 'ai-rationale':
      return <TransactionAIRationale customerId={customerId} taskId={taskId} />;
    default:
      return (
        <div className="container-fluid my-4" style={{ paddingTop: '60px' }}>
          <div className="alert alert-danger">Invalid view: {view}</div>
        </div>
      );
  }
}

export default TransactionReviewWrapper;


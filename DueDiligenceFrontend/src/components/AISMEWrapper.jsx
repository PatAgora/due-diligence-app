import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import AISME from './AISME';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

/**
 * Wrapper component that fetches customer_id from task and renders AI SME chatbot
 * This replaces the task view when AI SME link is clicked
 */
function AISMEWrapper() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [customerId, setCustomerId] = useState(null);
  const [taskStatus, setTaskStatus] = useState(null);
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
      const apiUrl = isQCReview
        ? `${BASE_URL}/api/qc_review/${taskId}`
        : `${BASE_URL}/api/reviewer_panel/${taskId}`;

      const response = await fetch(apiUrl, { credentials: 'include' });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const result = await response.json();

      // Customer ID is optional for AI SME (it's not task-specific)
      // We'll pass taskId to the component for context
      setCustomerId(result.review?.customer_id || null);
      setTaskStatus(result.review?.status || null);
    } catch (e) {
      console.error("Failed to fetch task data:", e);
      setError(`Failed to load task data: ${e.message}`);
    } finally {
      setLoading(false);
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
          <button className="btn btn-primary" onClick={handleBackToTask}>
            Go Back to Task
          </button>
        </div>
      </div>
    );
  }

  // Check if task is completed
  if (taskStatus && taskStatus.toLowerCase() === 'completed') {
    return (
      <div style={{ margin: 0, padding: '1rem', paddingTop: '60px', width: '100%' }}>
        <div className="alert alert-warning">
          <h4 className="alert-heading">
            <i className="fas fa-exclamation-triangle me-2"></i>
            AI SME Not Available
          </h4>
          <p className="mb-0">
            AI SME module is currently unavailable. Task has already been marked as complete.
          </p>
          <button className="btn btn-primary mt-3" onClick={handleBackToTask}>
            Go Back to Task
          </button>
        </div>
      </div>
    );
  }

  // Render the AI SME chatbot component
  // Note: AI SME doesn't require customer_id - it's a general policy/guidance chatbot
  return <AISME taskId={taskId} customerId={customerId} />;
}

export default AISMEWrapper;


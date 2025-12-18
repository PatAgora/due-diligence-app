import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './SumsubVerification.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function SumsubVerification({ taskId, reviewId, customerId }) {
  const navigate = useNavigate();
  const iframeRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [applicantId, setApplicantId] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [websdkUrl, setWebsdkUrl] = useState(null);
  const [status, setStatus] = useState('init');
  const [statusData, setStatusData] = useState(null);

  useEffect(() => {
    if (taskId && reviewId && customerId) {
      initializeVerification();
    }
  }, [taskId, reviewId, customerId]);

  const initializeVerification = async () => {
    try {
      setLoading(true);
      setError(null);

      // First, check if applicant already exists
      const taskDataRes = await fetch(`${BASE_URL}/api/sumsub/get_task_data/${taskId}`, {
        credentials: 'include'
      });

      if (taskDataRes.ok) {
        const taskData = await taskDataRes.json();
        if (taskData.sumsub_applicant_id) {
          // Applicant exists, get WebSDK link
          setApplicantId(taskData.sumsub_applicant_id);
          await getWebsdkLink(taskData.sumsub_applicant_id, customerId);
          return;
        }
      }

      // Create new applicant
      const createRes = await fetch(`${BASE_URL}/api/sumsub/create_applicant`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          review_id: reviewId,
          customer_id: customerId,
          level_name: 'id-only'
        })
      });

      if (!createRes.ok) {
        const errorData = await createRes.json();
        throw new Error(errorData.error || 'Failed to create applicant');
      }

      const createData = await createRes.json();
      if (createData.success && createData.applicant_id) {
        setApplicantId(createData.applicant_id);
        
        // Get WebSDK link instead of access token
        await getWebsdkLink(createData.applicant_id, customerId);
      } else {
        throw new Error('Failed to create applicant');
      }
    } catch (err) {
      console.error('Sumsub initialization error:', err);
      setError(err.message || 'Failed to initialize verification');
      setLoading(false);
    }
  };

  const getWebsdkLink = async (applicantId, customerId) => {
    try {
      // Get review data to get email/phone if available
      const reviewRes = await fetch(`${BASE_URL}/api/reviewer_panel/${taskId}`, {
        credentials: 'include'
      });
      
      let email = null;
      let phone = null;
      if (reviewRes.ok) {
        const reviewData = await reviewRes.json();
        if (reviewData.review) {
          email = reviewData.review.primary_email || null;
          phone = reviewData.review.primary_phone || null;
        }
      }

      const res = await fetch(`${BASE_URL}/api/sumsub/get_websdk_link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          applicant_id: applicantId,
          external_user_id: `customer_${customerId}`,
          level_name: 'id-only',
          email: email,
          phone: phone,
          ttl_in_secs: 1800
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || 'Failed to get WebSDK link');
      }

      const data = await res.json();
      if (data.success && data.url) {
        console.log('[Sumsub] WebSDK URL received:', data.url);
        setWebsdkUrl(data.url);
        setLoading(false);
      } else {
        console.error('[Sumsub] No URL in response:', data);
        throw new Error('No WebSDK URL received');
      }
    } catch (err) {
      console.error('Get WebSDK link error:', err);
      setError(err.message || 'Failed to get WebSDK link');
      setLoading(false);
    }
  };

  const checkStatus = async () => {
    if (!applicantId) return;

    try {
      const res = await fetch(`${BASE_URL}/api/sumsub/get_applicant_status/${applicantId}`, {
        credentials: 'include'
      });

      if (res.ok) {
        const data = await res.json();
        setStatusData(data);
        
        // Handle both response formats
        // Format 1: Direct (reviewStatus at top level)
        // Format 2: Nested (review.reviewStatus)
        const reviewStatus = data.reviewStatus || data.review?.reviewStatus || 'unknown';
        const reviewAnswer = data.reviewResult?.reviewAnswer || data.review?.reviewResult?.reviewAnswer;
        
        // If review is completed with GREEN answer, set status to completed
        if (reviewStatus === 'completed' || reviewAnswer === 'GREEN') {
          setStatus('completed');
        } else if (reviewStatus === 'rejected' || reviewAnswer === 'RED') {
          setStatus('rejected');
        } else {
          setStatus(reviewStatus);
        }
      }
    } catch (err) {
      console.error('Status check error:', err);
    }
  };

  useEffect(() => {
    if (applicantId) {
      // Check status initially and then periodically
      checkStatus();
      const interval = setInterval(checkStatus, 5000); // Check every 5 seconds for faster updates
      return () => clearInterval(interval);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicantId]);
  
  // Also check status when websdkUrl is set (iframe loaded)
  useEffect(() => {
    if (websdkUrl && applicantId) {
      // Check status after a short delay to allow iframe to load
      const timeout = setTimeout(() => {
        checkStatus();
      }, 2000);
      return () => clearTimeout(timeout);
    }
  }, [websdkUrl, applicantId]);



  const handleBackToTask = () => {
    const isQCReview = window.location.pathname.startsWith('/qc_review/');
    const basePath = isQCReview 
      ? `/qc_review/${taskId}`
      : `/view_task/${taskId}`;
    navigate(basePath);
  };

  const getStatusBadge = () => {
    // Check statusData first for most up-to-date info
    if (statusData) {
      const reviewStatus = statusData.reviewStatus || statusData.review?.reviewStatus;
      const reviewAnswer = statusData.reviewResult?.reviewAnswer || statusData.review?.reviewResult?.reviewAnswer;
      
      if (reviewStatus === 'completed' || reviewAnswer === 'GREEN') {
        return <span className="badge bg-success">Verified</span>;
      } else if (reviewStatus === 'rejected' || reviewAnswer === 'RED') {
        return <span className="badge bg-danger">Rejected</span>;
      } else if (reviewAnswer === 'YELLOW') {
        return <span className="badge bg-warning">Pending Review</span>;
      }
    }
    
    // Fallback to status state
    switch (status) {
      case 'completed':
      case 'approved':
        return <span className="badge bg-success">Verified</span>;
      case 'rejected':
        return <span className="badge bg-danger">Rejected</span>;
      case 'pending':
        return <span className="badge bg-warning">Pending</span>;
      default:
        return <span className="badge bg-secondary">In Progress</span>;
    }
  };

  if (loading) {
    return (
      <div className="sumsub-container" style={{ paddingTop: '60px' }}>
        <div className="sumsub-header">
          <div className="sumsub-brand">
            <div className="sumsub-logo">
              <i className="fas fa-id-card"></i>
            </div>
            <div className="sumsub-brand-text">
              <div className="sumsub-brand-title">Identity Verification</div>
              <div className="sumsub-brand-subtitle">Sumsub</div>
            </div>
          </div>
          <button className="sumsub-nav-link" onClick={handleBackToTask}>
            <i className="fas fa-arrow-left"></i> Back to Task
          </button>
        </div>
        <div className="sumsub-main">
          <div className="sumsub-loading">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <p>Initializing verification...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="sumsub-container" style={{ paddingTop: '60px' }}>
        <div className="sumsub-header">
          <div className="sumsub-brand">
            <div className="sumsub-logo">
              <i className="fas fa-id-card"></i>
            </div>
            <div className="sumsub-brand-text">
              <div className="sumsub-brand-title">Identity Verification</div>
              <div className="sumsub-brand-subtitle">Sumsub</div>
            </div>
          </div>
          <button className="sumsub-nav-link" onClick={handleBackToTask}>
            <i className="fas fa-arrow-left"></i> Back to Task
          </button>
        </div>
        <div className="sumsub-main">
          <div className="alert alert-danger">
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={initializeVerification}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="sumsub-container" style={{ paddingTop: '60px' }}>
      <div className="sumsub-header">
        <div className="sumsub-brand">
          <div className="sumsub-logo">
            <i className="fas fa-id-card"></i>
          </div>
          <div className="sumsub-brand-text">
            <div className="sumsub-brand-title">Identity Verification</div>
            <div className="sumsub-brand-subtitle">Sumsub</div>
          </div>
        </div>
        <div className="sumsub-header-right">
          <div className="sumsub-status">
            Status: {getStatusBadge()}
          </div>
          <button className="sumsub-nav-link" onClick={handleBackToTask}>
            <i className="fas fa-arrow-left"></i> Back to Task
          </button>
        </div>
      </div>

      <div className="sumsub-main">
        {websdkUrl ? (
          <div className="sumsub-sdk-container">
            <iframe
              ref={iframeRef}
              src={websdkUrl}
              className="sumsub-iframe"
              title="Sumsub Identity Verification"
              allow="camera; microphone; geolocation"
              style={{ width: '100%', height: '100%', border: 'none' }}
              onLoad={() => {
                console.log('[Sumsub] Iframe loaded successfully');
                console.log('[Sumsub] WebSDK URL:', websdkUrl);
              }}
              onError={(e) => {
                console.error('[Sumsub] Iframe error:', e);
              }}
            />
            {statusData && statusData.review && (
              <div className="alert alert-info mt-3">
                <small>
                  <strong>Status:</strong> {statusData.review.reviewStatus || 'In Progress'}
                  {statusData.review.reviewAnswer && (
                    <> - {statusData.review.reviewAnswer}</>
                  )}
                </small>
              </div>
            )}
          </div>
        ) : (
          <div className="alert alert-warning">
            <p>WebSDK link not available. Please try refreshing the page.</p>
            <button className="btn btn-primary" onClick={initializeVerification}>
              Refresh
            </button>
          </div>
        )}

        {statusData && (
          <div className="sumsub-status-info">
            <h5>Verification Details</h5>
            <div className="row">
              <div className="col-md-6">
                <p><strong>Applicant ID:</strong> {applicantId}</p>
                <p><strong>Status:</strong> {status}</p>
              </div>
              <div className="col-md-6">
                {statusData.review && (
                  <>
                    <p><strong>Review Answer:</strong> {statusData.review.reviewAnswer || 'N/A'}</p>
                    <p><strong>Review Status:</strong> {statusData.review.reviewStatus || 'N/A'}</p>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default SumsubVerification;



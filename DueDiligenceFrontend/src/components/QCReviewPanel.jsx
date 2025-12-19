import React, { useState, useEffect } from 'react';
import '../styles/agora-theme.css';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useModuleSettings } from '../contexts/ModuleSettingsContext';
import { useFieldVisibility } from '../contexts/FieldVisibilityContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';
import './QCReviewPanel.css';

function QCReviewPanel() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isModuleEnabled } = useModuleSettings();
  const { isFieldVisible } = useFieldVisibility();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeSections, setActiveSections] = useState(new Set()); // Track multiple open sections
  const [formData, setFormData] = useState({
    outcome: '',
    comment: '',
    rework_required: false,
    rework_complete_check: false
  });
  const [saving, setSaving] = useState(false);
  const [reworkCompleted, setReworkCompleted] = useState(false);
  const [originalQCDecision, setOriginalQCDecision] = useState(null);
  
  // AI SME Referrals state
  const [aiSmeReferrals, setAiSmeReferrals] = useState([]);
  const [loadingAiReferrals, setLoadingAiReferrals] = useState(false);
  
  // Identity Verification (Sumsub) state
  const [identityVerification, setIdentityVerification] = useState(null);
  const [loadingIdentityVerification, setLoadingIdentityVerification] = useState(false);

  useEffect(() => {
    if (taskId) {
      fetchTaskData();
      fetchAiSmeReferrals();
      fetchIdentityVerification();
    }
  }, [taskId]);
  
  // Determine if QC fields should be locked
  const isQCLocked = () => {
    if (!data?.review) return false;
    // Check both top-level status and review status
    const status = ((data.status || data.review.status || '')).toLowerCase();
    
    // Only lock when task status is "Completed" - allow interaction for "Awaiting QC Rework"
    return status.includes('completed') && !status.includes('awaiting') && !status.includes('rework');
  };
  
  // Fetch AI SME referrals for this task
  const fetchAiSmeReferrals = async () => {
    try {
      setLoadingAiReferrals(true);
      const response = await fetch(`${BASE_URL}/api/my_referrals`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        // Filter referrals for this task
        const taskReferrals = (data.ai_sme_referrals || []).filter(
          ref => ref.task_id === taskId
        );
        setAiSmeReferrals(taskReferrals);
      }
    } catch (error) {
      console.error('Error loading AI SME referrals:', error);
    } finally {
      setLoadingAiReferrals(false);
    }
  };

  // Fetch Identity Verification (Sumsub) status
  const fetchIdentityVerification = async (applicantId = null) => {
    try {
      setLoadingIdentityVerification(true);
      const review = data?.review;
      const applicant_id = applicantId || review?.sumsub_applicant_id;
      
      if (!applicant_id) {
        setIdentityVerification(null);
        return;
      }

      const response = await fetch(
        `${BASE_URL}/api/sumsub/get_applicant_status/${applicant_id}`,
        { credentials: 'include' }
      );
      
      if (response.ok) {
        const verificationData = await response.json();
        setIdentityVerification(verificationData);
      } else {
        setIdentityVerification(null);
      }
    } catch (error) {
      console.error('Error loading identity verification:', error);
      setIdentityVerification(null);
    } finally {
      setLoadingIdentityVerification(false);
    }
  };

  const fetchTaskData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${BASE_URL}/api/qc_review/${taskId}`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        if (response.status === 404) throw new Error('Task not found');
        if (response.status === 403) throw new Error('Access denied');
        throw new Error(`HTTP ${response.status}`);
      }

      const taskData = await response.json();
      setData(taskData);
      
      // Initialize form with existing QC data if available
      if (taskData.review) {
        setFormData({
          outcome: taskData.review.qc_outcome || '',
          comment: taskData.review.qc_comment || '',
          rework_required: taskData.review.qc_rework_required || false,
          rework_complete_check: false
        });
        // Store rework completion status for display
        // Show checkbox if: task is in "Awaiting QC Rework" status OR qc_rework_completed is true
        const taskStatus = ((taskData.status || taskData.review?.status || '')).toLowerCase();
        const isAwaitingQCRework = taskStatus.includes('awaiting qc rework');
        const hasReworkCompleted = taskData.review.qc_rework_completed || false;
        setReworkCompleted(isAwaitingQCRework || hasReworkCompleted);
        
        // Store original QC decision if rework was completed
        if (taskData.review.qc_rework_completed && taskData.review.qc_outcome) {
          setOriginalQCDecision({
            outcome: taskData.review.qc_outcome,
            comment: taskData.review.qc_comment,
            rework_required_date: taskData.review.qc_check_date
          });
        }
        // Fetch identity verification if applicant ID exists
        if (taskData.review.sumsub_applicant_id) {
          // Use setTimeout to ensure data state is updated first
          setTimeout(() => {
            fetchIdentityVerification(taskData.review.sumsub_applicant_id);
          }, 100);
        }
      }
    } catch (err) {
      console.error('Error fetching task data:', err);
      setError(err.message || 'Failed to load task');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e, action = '') => {
    e.preventDefault();
    if (saving) return;

    try {
      setSaving(true);

      const submitData = new FormData();
      submitData.append('outcome', formData.outcome);
      submitData.append('comment', formData.comment);
      
      // If rework complete checkbox is checked, send action as qc_rework_ok
      // and ensure rework_required is false (we're completing the rework, not requiring more)
      if (formData.rework_complete_check && !action) {
        action = 'qc_rework_ok';
        submitData.append('rework_required', ''); // Explicitly set to false when completing rework
      } else {
        submitData.append('rework_required', formData.rework_required ? 'on' : '');
      }
      
      if (action) {
        submitData.append('action', action);
      }

      // Debug logging
      console.log('Submitting QC Review:', {
        outcome: formData.outcome,
        comment: formData.comment,
        rework_required: formData.rework_required,
        rework_complete_check: formData.rework_complete_check,
        action: action,
        taskId: taskId
      });

      const response = await fetch(`${BASE_URL}/api/qc_review/${taskId}`, {
        method: 'POST',
        credentials: 'include',
        body: submitData,
        headers: { 'Accept': 'application/json' },
      });

      if (response.ok) {
        const result = await response.json().catch(() => ({}));
        console.log('QC Review response:', result);
        
        const successMsg = action === 'refer_sme' ? 'Referred to SME.' : 
                          action === 'qc_rework_ok' ? 'Rework confirmed and completed.' : 
                          'QC review submitted.';
        alert(successMsg);
        
        // Redirect based on user role: QC leads go to qc_lead_dashboard, QC reviewers go to qc_dashboard
        const role = user?.role || '';
        if (role === 'qc_1' || role === 'qc_2' || role === 'qc_3' || role.startsWith('qc_lead_')) {
          navigate('/qc_lead_dashboard');
        } else {
          navigate('/qc_dashboard');
        }
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to submit review' }));
        console.error('QC Review error:', errorData);
        alert(errorData.error || 'Failed to submit review');
      }
    } catch (err) {
      console.error('Error submitting review:', err);
      alert('Error submitting review. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <>
        <div className="container my-4">
          <div className="text-center py-5">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <div className="container my-4">
          <div className="alert alert-danger">
            <h4 className="alert-heading">Error</h4>
            <p>{error}</p>
            <button className="btn btn-primary" onClick={() => navigate(-1)}>
              Go Back
            </button>
          </div>
        </div>
      </>
    );
  }

  const review = data?.review || {};
  const match = data?.match || {};
  const level = data?.level || 1;
  const status = data?.status || 'Unknown';
  const reviewerName = data?.reviewer_name || 'Unassigned';
  const totalScore = match?.total_score || review?.total_score || 'N/A';
  const systemRationale = match?.match_explanation || '';

  // DDG sections definition (same as ReviewerPanel)
  const ddgSections = [
    { key: 'idv', label: 'IDV' },
    { key: 'nob', label: 'NOB' },
    { key: 'income', label: 'Income' },
    { key: 'expenditure', label: 'Expenditure' },
    { key: 'structure', label: 'Structure' },
    { key: 'ta', label: 'TA' },
    { key: 'sof', label: 'SOF' },
    { key: 'sow', label: 'SOW' }
  ];

  // Helper function to render field rows
  const renderField = (label, value) => {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return (
      <tr>
        <td className="fw-semibold">{label}</td>
        <td>{value}</td>
      </tr>
    );
  };

  // Get status badge class
  const getStatusClass = (status) => {
    const s = (status || '').toLowerCase();
    if (s.includes('completed')) return 'success';
    if (s.includes('pending') || s.includes('wip')) return 'warning';
    if (s.includes('rework')) return 'danger';
    if (s.includes('referred')) return 'info';
    return 'secondary';
  };
  const statusClass = getStatusClass(status);

  // Render customer details section (similar to ReviewerPanel)
  const renderCustomerDetailsSection = () => {
    // Define the customer detail fields using actual field names from database
    const fields = [
      { label: 'Entity Type', original: 'entity_type_original', enriched: 'entity_type_enriched' },
      { label: 'Entity Name', original: 'entity_name', enriched: 'entity_name_enriched' },
      { label: 'Trading Name', original: 'entity_trading_name', enriched: 'entity_trading_name_enriched' },
      { label: 'Registration Number', original: 'entity_registration_number', enriched: 'entity_registration_number_enriched' },
      { label: 'Country of Incorporation', original: 'entity_country_of_incorporation', enriched: 'entity_country_of_incorporation_enriched' },
      { label: 'Industry', original: 'entity_industry', enriched: 'entity_industry_enriched' },
      { label: 'Phone', original: 'primary_phone' },
      { label: 'Email', original: 'primary_email' },
    ];

    // Also get all other customer-related fields from review/match that aren't in the hardcoded list
    const allCustomerFields = {};
    const excludeKeys = ['task_id', 'match_id', 'id', 'total_score', 'match_score', 
                         'match_explanation', 'created_at', 'updated_at', 'watchlist_id',
                         'status', 'outcome', 'rationale', 'assigned_to', 'completed_by',
                         'qc_assigned_to', 'qc_outcome', 'qc_comment', 'qc_rework_required'];
    
    // Get all fields from review that look like customer data
    Object.keys(review).forEach(key => {
      if (!excludeKeys.includes(key) && 
          (key.includes('customer') || key.includes('phone') || key.includes('email') || 
           key.startsWith('cd_') || key.startsWith('entity_') || key.startsWith('lp1_') ||
           key.includes('address') || key.includes('city') || key.includes('postcode') ||
           key.includes('country') || key.includes('sic') || key.includes('revenue') ||
           key.includes('account') || key.includes('transaction') || key.includes('jurisdiction'))) {
        const isInHardcodedList = fields.some(f => 
          f.original === key || f.enriched === key
        );
        if (!isInHardcodedList && review[key] && review[key] !== '' && review[key] !== 'None' && review[key] !== 'null') {
          allCustomerFields[key] = review[key];
        }
      }
    });

    return (
      <div className="table-responsive">
        <table className="table table-sm">
          <thead className="table-light">
            <tr>
              <th style={{width: '40%'}}>Field</th>
              <th style={{width: '20%'}}>Source</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {fields
              .filter(field => {
                // Check visibility for both original and enriched fields
                const originalVisible = isFieldVisible(field.original);
                const enrichedVisible = field.enriched ? isFieldVisible(field.enriched) : true;
                return originalVisible || enrichedVisible;
              })
              .map(field => {
                const originalValue = review[field.original];
                const enrichedValue = field.enriched ? review[field.enriched] : null;
                const showEnriched = enrichedValue && enrichedValue !== '' && enrichedValue !== 'None' && enrichedValue !== 'null';
                const originalVisible = isFieldVisible(field.original);
                const enrichedVisible = field.enriched ? isFieldVisible(field.enriched) : true;
                
                // Skip if neither original nor enriched is visible
                if (!originalVisible && !enrichedVisible) {
                  return null;
                }
                
                return (
                  <React.Fragment key={field.label}>
                    {originalVisible && (
                      <tr>
                        {showEnriched && enrichedVisible && <td rowSpan="2">{field.label}</td>}
                        {(!showEnriched || !enrichedVisible) && <td>{field.label}</td>}
                        <td>Original</td>
                        <td>
                          <input 
                            type="text" 
                            className="form-control form-control-sm" 
                            value={originalValue || ''} 
                            readOnly 
                          />
                        </td>
                      </tr>
                    )}
                    {showEnriched && enrichedVisible && (
                      <tr>
                        {!originalVisible && <td>{field.label}</td>}
                        <td>Enriched</td>
                        <td>
                          <input 
                            type="text" 
                            className="form-control form-control-sm" 
                            value={enrichedValue} 
                            readOnly 
                          />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            {/* Display additional customer fields that aren't in the hardcoded list */}
            {Object.entries(allCustomerFields)
              .filter(([key]) => isFieldVisible(key))
              .map(([key, value]) => (
                <tr key={key}>
                  <td>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</td>
                  <td>Source</td>
                  <td>
                    <input 
                      type="text" 
                      className="form-control form-control-sm" 
                      value={value || ''} 
                      readOnly 
                    />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    );
  };

  // Don't wrap in BaseLayout here - it's already wrapped in App.jsx routes
  return (
    <>
      <div className="container-fluid my-4 px-5">
        <h2 style={{fontWeight: '800', letterSpacing: '.2px'}}>QC Review Panel</h2>
      
        <div className="row g-4">
          {/* Main Content */}
          <div className="col-12">
            {/* Case Summary */}
            <div className="card shadow-sm mb-4">
              <div className="card-body">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h2 className="h6 mb-0">Case Summary</h2>
                  <button className="btn btn-sm btn-outline-primary">
                    <i className="bi bi-file-earmark-pdf"></i> Export PDF
                  </button>
                </div>
                <table className="table table-sm table-borderless mb-0">
                  <tbody>
                    {renderField('Task ID', taskId)}
                    {renderField('Customer ID', review.customer_id || '—')}
                    {renderField('Task Type', review.hit_type || review.record_type)}
                    <tr>
                      <td className="fw-semibold">Status</td>
                      <td>
                        <span className={`badge bg-${statusClass}`}>{status}</span>
                      </td>
                    </tr>
                    {renderField('Assigned To', (() => {
                      const assignedToId = review.assigned_to;
                      if (!assignedToId) return 'Unassigned';
                      const userName = data?.users?.[assignedToId.toString()];
                      return userName || review.assigned_to_name || `User ${assignedToId}`;
                    })())}
                    {renderField('QC Reviewer', (() => {
                      const qcAssignedToId = review.qc_assigned_to;
                      if (!qcAssignedToId) return 'Unassigned';
                      const userName = data?.users?.[qcAssignedToId.toString()];
                      return userName || review.qc_assigned_to_name || `User ${qcAssignedToId}`;
                    })())}
                    {renderField('Current Risk Rating', review.currentriskrating)}
                    {renderField('Match Score', review.total_score || totalScore)}
                    {renderField('Last Updated', review.updated_at ? new Date(review.updated_at).toLocaleString() : '—')}
                    {renderField('Date Completed', (() => {
                      const dateStr = review.date_completed;
                      return dateStr ? new Date(dateStr).toLocaleString() : '—';
                    })())}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Customer Details */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Customer Details</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('customer')) {
                      newSections.delete('customer');
                    } else {
                      newSections.add('customer');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('customer') && (
                <div className="card-body">
                  {renderCustomerDetailsSection()}
                </div>
              )}
            </div>

            {/* Due Diligence Review - Read-only */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Due Diligence - Review</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('ddg')) {
                      newSections.delete('ddg');
                    } else {
                      newSections.add('ddg');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('ddg') && (
                <div className="card-body">
                  {/* DDG Sections Table - Read-only */}
                  <div className="table-responsive mb-4">
                    <table className="table table-sm">
                      <thead className="table-light">
                        <tr>
                          <th style={{width: '20%'}}>Section</th>
                          <th>Rationale</th>
                          <th style={{width: '16%'}}>Outreach Req.</th>
                          <th style={{width: '16%'}}>Section Complete</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ddgSections.map(section => (
                          <tr key={section.key}>
                            <td>{section.label}</td>
                            <td>
                              <textarea 
                                className="form-control form-control-sm readonly-cell" 
                                rows="2" 
                                value={review[`${section.key}_rationale`] || ''}
                                readOnly
                              />
                            </td>
                            <td className="text-center">
                              <input 
                                type="checkbox" 
                                className="form-check-input" 
                                checked={review[`${section.key}_outreach_required`] == 1}
                                readOnly
                                disabled
                              />
                            </td>
                            <td className="text-center">
                              <input 
                                type="checkbox" 
                                className="form-check-input" 
                                checked={review[`${section.key}_section_completed`] == 1}
                                readOnly
                                disabled
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  
                  {/* FinCrime Concerns Table - Read-only */}
                  <div className="table-responsive">
                    <table className="table table-sm">
                      <thead className="table-light">
                        <tr>
                          <th style={{width: '25%'}}>FinCrime Concern</th>
                          <th>Rationale</th>
                          <th style={{width: '20%'}}>Date Raised</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>SAR</td>
                          <td>
                            <textarea 
                              className="form-control form-control-sm readonly-cell" 
                              rows="2" 
                              value={review.sar_rationale || ''}
                              readOnly
                            />
                          </td>
                          <td>
                            <input 
                              type="text" 
                              className="form-control form-control-sm readonly-cell" 
                              value={review.sar_date_raised || ''}
                              readOnly
                            />
                          </td>
                        </tr>
                        <tr>
                          <td>DAML</td>
                          <td>
                            <textarea 
                              className="form-control form-control-sm readonly-cell" 
                              rows="2" 
                              value={review.daml_rationale || ''}
                              readOnly
                            />
                          </td>
                          <td>
                            <input 
                              type="text" 
                              className="form-control form-control-sm readonly-cell" 
                              value={review.daml_date_raised || ''}
                              readOnly
                            />
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Screening Engine Rationale */}
            {systemRationale && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">Screening Engine Rationale</h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('rationale')) {
                        newSections.delete('rationale');
                      } else {
                        newSections.add('rationale');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    Toggle
                  </button>
                </div>
                {activeSections.has('rationale') && (
                  <div className="card-body">
                    <textarea className="form-control readonly-cell" readOnly rows="4">
                      {systemRationale}
                    </textarea>
                  </div>
                )}
              </div>
            )}

            {/* Identity Verification (Sumsub) */}
            {(identityVerification || data?.review?.sumsub_applicant_id) && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">
                    <i className="fas fa-id-card me-2"></i>
                    Identity Verification
                  </h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('identity_verification')) {
                        newSections.delete('identity_verification');
                      } else {
                        newSections.add('identity_verification');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    {activeSections.has('identity_verification') ? 'Hide' : 'Show'}
                  </button>
                </div>
                {activeSections.has('identity_verification') && (
                  <div className="card-body">
                    {loadingIdentityVerification ? (
                      <div className="text-center py-3">
                        <div className="spinner-border spinner-border-sm text-primary" role="status">
                          <span className="visually-hidden">Loading...</span>
                        </div>
                      </div>
                    ) : (
                      <div>
                        {identityVerification ? (
                          <>
                            <div className="row mb-3">
                              <div className="col-md-6">
                                <strong>Applicant ID:</strong>
                                <p className="text-muted small mb-2">{data?.review?.sumsub_applicant_id || '—'}</p>
                              </div>
                              <div className="col-md-6">
                                <strong>Status:</strong>
                                <p className="mb-2">
                                  <span className={`badge ${
                                    identityVerification.reviewStatus === 'completed' || 
                                    identityVerification.reviewResult?.reviewAnswer === 'GREEN' 
                                      ? 'bg-success' 
                                      : identityVerification.reviewStatus === 'rejected' || 
                                        identityVerification.reviewResult?.reviewAnswer === 'RED'
                                        ? 'bg-danger'
                                        : 'bg-warning'
                                  }`}>
                                    {identityVerification.reviewStatus || identityVerification.review?.reviewStatus || 'Pending'}
                                  </span>
                                </p>
                              </div>
                            </div>
                            {identityVerification.reviewResult && (
                              <div className="mb-3">
                                <strong>Review Answer:</strong>
                                <p className="mb-2">
                                  <span className={`badge ${
                                    identityVerification.reviewResult.reviewAnswer === 'GREEN' 
                                      ? 'bg-success' 
                                      : identityVerification.reviewResult.reviewAnswer === 'RED'
                                        ? 'bg-danger'
                                        : identityVerification.reviewResult.reviewAnswer === 'YELLOW'
                                          ? 'bg-warning'
                                          : 'bg-secondary'
                                  }`}>
                                    {identityVerification.reviewResult.reviewAnswer || '—'}
                                  </span>
                                </p>
                              </div>
                            )}
                            {identityVerification.reviewDate && (
                              <div className="mb-3">
                                <strong>Review Date:</strong>
                                <p className="text-muted small mb-0">
                                  {new Date(identityVerification.reviewDate).toLocaleString()}
                                </p>
                              </div>
                            )}
                            {data?.review?.sumsub_verification_status && (
                              <div className="mb-3">
                                <strong>Verification Status:</strong>
                                <p className="text-muted small mb-0">{data.review.sumsub_verification_status}</p>
                              </div>
                            )}
                            {data?.review?.sumsub_verification_date && (
                              <div className="mb-3">
                                <strong>Verification Date:</strong>
                                <p className="text-muted small mb-0">
                                  {new Date(data.review.sumsub_verification_date).toLocaleString()}
                                </p>
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="text-muted">
                            <p>No verification data available. Identity verification may not have been initiated yet.</p>
                            {data?.review?.sumsub_applicant_id && (
                              <button 
                                className="btn btn-sm btn-outline-primary"
                                onClick={() => fetchIdentityVerification(data.review.sumsub_applicant_id)}
                                disabled={loadingIdentityVerification}
                              >
                                <i className="bi bi-arrow-clockwise me-1"></i>
                                Refresh Status
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* AI SME Referrals - show if there are any AI SME referrals for this task */}
            {aiSmeReferrals.length > 0 && (
              <div className="card shadow-sm mb-4">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">
                    <i className="fas fa-brain me-2"></i>
                    AI SME Referrals ({aiSmeReferrals.length})
                  </h5>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                      const newSections = new Set(activeSections);
                      if (newSections.has('ai_sme')) {
                        newSections.delete('ai_sme');
                      } else {
                        newSections.add('ai_sme');
                      }
                      setActiveSections(newSections);
                    }}
                  >
                    {activeSections.has('ai_sme') ? 'Hide' : 'Show'}
                  </button>
                </div>
                {activeSections.has('ai_sme') && (
                  <div className="card-body">
                    {loadingAiReferrals ? (
                      <div className="text-center py-3">
                        <div className="spinner-border spinner-border-sm text-primary" role="status">
                          <span className="visually-hidden">Loading...</span>
                        </div>
                      </div>
                    ) : (
                      <div className="list-group list-group-flush">
                        {aiSmeReferrals.map((ref, idx) => (
                          <div key={ref.id || idx} className="list-group-item px-0">
                            <div className="d-flex justify-content-between align-items-start mb-2">
                              <div className="flex-grow-1">
                                <div className="d-flex align-items-center gap-2 mb-2">
                                  <span className={`badge ${ref.status === 'closed' ? 'bg-success' : 'bg-warning'}`}>
                                    {ref.status || 'open'}
                                  </span>
                                  <small className="text-muted">
                                    {ref.ts ? new Date(ref.ts).toLocaleString() : '—'}
                                  </small>
                                </div>
                                <h6 className="mb-1">Question:</h6>
                                <p className="mb-2 text-muted small">{ref.question || '—'}</p>
                                {ref.answer && (
                                  <>
                                    <h6 className="mb-1">Answer (Chatbot):</h6>
                                    <p className="mb-2 small text-muted">{ref.answer}</p>
                                  </>
                                )}
                                <h6 className="mb-1">SME Response:</h6>
                                <div className="mb-2">
                                  {ref.sme_response ? (
                                    <p className="mb-0 small fw-semibold">{ref.sme_response}</p>
                                  ) : (
                                    <p className="mb-0 text-muted small fst-italic">Awaiting SME response...</p>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="small text-muted">
                              {ref.count > 1 && `Asked ${ref.count} time${ref.count > 1 ? 's' : ''}`}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="mt-3">
                      <button 
                        className="btn btn-sm btn-outline-primary"
                        onClick={fetchAiSmeReferrals}
                        disabled={loadingAiReferrals}
                      >
                        <i className="bi bi-arrow-clockwise me-1"></i>
                        Refresh
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Decision Information */}
            <div className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">Decision Information</h5>
                <button 
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('decision')) {
                      newSections.delete('decision');
                    } else {
                      newSections.add('decision');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('decision') && (
                <div className="card-body">
                  <div className="row g-3">
                    <div className="col-md-6">
                      <label className="form-label">Outcome 🔒</label>
                      <input
                        type="text"
                        className="form-control readonly-cell"
                        readOnly
                        value={review.outcome || '—'}
                      />
                    </div>
                    <div className="col-md-6">
                      <label className="form-label">Decision RCA 🔒</label>
                      <input
                        type="text"
                        className="form-control readonly-cell"
                        readOnly
                        value={review.rationale || review.primary_rationale || '—'}
                      />
                    </div>
                    <div className="col-12">
                      <label className="form-label">Decision Rationale 🔒</label>
                      <textarea
                        className="form-control readonly-cell"
                        readOnly
                        rows="4"
                        value={review.rationale || '—'}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* QC Review Form */}
            <form onSubmit={(e) => handleSubmit(e)} className="card shadow-sm mb-4">
              <div className="card-header d-flex justify-content-between align-items-center">
                <h5 className="mb-0">QC Review</h5>
                <button 
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    const newSections = new Set(activeSections);
                    if (newSections.has('qc_review')) {
                      newSections.delete('qc_review');
                    } else {
                      newSections.add('qc_review');
                    }
                    setActiveSections(newSections);
                  }}
                >
                  Toggle
                </button>
              </div>
              {activeSections.has('qc_review') && (
                <div className="card-body">
                  {/* Show locked message if QC is locked */}
                  {isQCLocked() && (
                    <div className="alert alert-success mb-3">
                      <i className="bi bi-lock-fill me-2"></i>
                      <strong>QC Review Completed</strong> - This QC review has been finalized and is now locked.
                    </div>
                  )}
                  
                  {reworkCompleted && !isQCLocked() && (
                    <div className="alert alert-info mb-3">
                      <i className="bi bi-info-circle me-2"></i>
                      <strong>Awaiting QC Rework Review</strong> - The reviewer has completed the rework. Please review the changes and use the "Rework Complete" checkbox below to confirm completion.
                    </div>
                  )}
                  
                  {/* Show original QC decision if rework was completed */}
                  {originalQCDecision && !isQCLocked() && (
                    <div className="alert alert-secondary mb-3">
                      <h6 className="alert-heading mb-2">
                        <i className="bi bi-clock-history me-2"></i>
                        Original QC Decision
                      </h6>
                      <div className="mb-1">
                        <strong>Outcome:</strong> <span className="badge bg-warning">{originalQCDecision.outcome}</span>
                      </div>
                      {originalQCDecision.comment && (
                        <div className="mb-1">
                          <strong>Comments:</strong> {originalQCDecision.comment}
                        </div>
                      )}
                      {originalQCDecision.rework_required_date && (
                        <div className="small text-muted">
                          <i className="bi bi-calendar me-1"></i>
                          {new Date(originalQCDecision.rework_required_date).toLocaleString()}
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="mb-3">
                    <label htmlFor="outcome" className="form-label">
                      <strong>QC Outcome</strong>
                    </label>
                    <select
                      id="outcome"
                      name="outcome"
                      className="form-select"
                      value={formData.outcome}
                      onChange={(e) => setFormData({ ...formData, outcome: e.target.value })}
                      required
                      disabled={saving || isQCLocked()}
                    >
                      <option value="">-- Select --</option>
                      <option value="Pass">Pass</option>
                      <option value="Pass with Feedback">Pass with Feedback</option>
                      <option value="Fail">Fail</option>
                    </select>
                  </div>

                  <div className="mb-4">
                    <label htmlFor="comment" className="form-label">
                      <strong>Feedback / Comments</strong>
                    </label>
                    <textarea
                      id="comment"
                      name="comment"
                      className="form-control"
                      rows="3"
                      value={formData.comment}
                      onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                      disabled={saving || isQCLocked()}
                    />
                  </div>

                  <div className="form-check mb-3">
                    <input
                      type="checkbox"
                      className="form-check-input"
                      id="rework_required"
                      checked={formData.rework_required}
                      onChange={(e) => setFormData({ ...formData, rework_required: e.target.checked })}
                      disabled={saving || isQCLocked()}
                    />
                    <label className="form-check-label" htmlFor="rework_required">
                      Rework Required
                    </label>
                  </div>
                  
                  {/* Show Rework Complete checkbox only if rework was completed by reviewer */}
                  {reworkCompleted && (
                    <div className="form-check mb-4">
                      <input
                        type="checkbox"
                        className="form-check-input"
                        id="rework_complete_check"
                        checked={formData.rework_complete_check}
                        onChange={async (e) => {
                          if (e.target.checked && !saving && !isQCLocked()) {
                            // Automatically submit when checked
                            const submitData = new FormData();
                            submitData.append('action', 'qc_rework_ok');
                            submitData.append('rework_required', '');
                            
                            try {
                              setSaving(true);
                              const response = await fetch(`${BASE_URL}/api/qc_review/${taskId}`, {
                                method: 'POST',
                                credentials: 'include',
                                body: submitData,
                                headers: { 'Accept': 'application/json' },
                              });

                              if (response.ok) {
                                const result = await response.json().catch(() => ({}));
                                console.log('QC Rework Complete response:', result);
                                alert('Rework confirmed and completed.');
                                
                                // Redirect based on user role
                                const role = user?.role || '';
                                if (role === 'qc_1' || role === 'qc_2' || role === 'qc_3' || role.startsWith('qc_lead_')) {
                                  navigate('/qc_lead_dashboard');
                                } else {
                                  navigate('/qc_dashboard');
                                }
                              } else {
                                const errorData = await response.json().catch(() => ({ error: 'Failed to submit review' }));
                                console.error('QC Rework Complete error:', errorData);
                                alert(errorData.error || 'Failed to complete rework');
                                // Uncheck if submission failed
                                setFormData({ ...formData, rework_complete_check: false });
                              }
                            } catch (err) {
                              console.error('Error completing rework:', err);
                              alert('Error completing rework. Please try again.');
                              // Uncheck if submission failed
                              setFormData({ ...formData, rework_complete_check: false });
                            } finally {
                              setSaving(false);
                            }
                          } else if (!e.target.checked) {
                            // Just update state if unchecking
                            setFormData({ ...formData, rework_complete_check: false });
                          }
                        }}
                        disabled={saving || isQCLocked()}
                      />
                      <label className="form-check-label" htmlFor="rework_complete_check">
                        <i className="bi bi-check-circle me-1"></i>
                        <strong>Rework Complete</strong> - Check this to confirm rework review completion
                      </label>
                    </div>
                  )}

                  <div className="review-buttons">
                    <button type="submit" className="btn btn-primary" disabled={saving || isQCLocked()}>
                      {saving ? 'Submitting...' : (reworkCompleted ? 'Submit New Review Decision' : 'Submit Review')}
                    </button>
                    {/* Only show Refer to SME button if AI SME is disabled */}
                    {!isModuleEnabled('ai_sme') && (
                      <button
                        type="button"
                        onClick={(e) => handleSubmit(e, 'refer_sme')}
                        className="btn btn-warning"
                        disabled={saving || isQCLocked()}
                      >
                        Refer to SME
                      </button>
                    )}
                  </div>
                </div>
              )}
            </form>
          </div>
        </div>
      </div>
    </>
  );
}

export default QCReviewPanel;

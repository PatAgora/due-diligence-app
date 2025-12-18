import React, { useState, useEffect } from 'react';
import BaseLayout from './BaseLayout';
import './SamplingRatesConfig.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function SamplingRatesConfig() {
  const [globalRate, setGlobalRate] = useState(10);
  const [reviewerRates, setReviewerRates] = useState([]);
  const [allReviewers, setAllReviewers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedReviewer, setSelectedReviewer] = useState('');
  const [newRate, setNewRate] = useState('');

  useEffect(() => {
    fetchSamplingRates();
  }, []);

  const fetchSamplingRates = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/sampling_rates`, {
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();
        setGlobalRate(data.global_rate);
        setReviewerRates(data.reviewer_rates);
        setAllReviewers(data.all_reviewers);
      } else {
        alert('Failed to load sampling rates');
      }
    } catch (error) {
      console.error('Error loading sampling rates:', error);
      alert('Error loading sampling rates');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateGlobalRate = async (e) => {
    e.preventDefault();
    
    if (saving) return;
    
    if (globalRate < 0 || globalRate > 100) {
      alert('Rate must be between 0 and 100');
      return;
    }

    try {
      setSaving(true);
      
      const formData = new FormData();
      formData.append('rate', globalRate);
      
      const response = await fetch(`${BASE_URL}/api/sampling_rates/global`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        alert('Global rate updated successfully');
        fetchSamplingRates();
      } else {
        const error = await response.json();
        alert(`Failed to update: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating global rate:', error);
      alert('Error updating global rate');
    } finally {
      setSaving(false);
    }
  };

  const handleAddReviewerRate = async (e) => {
    e.preventDefault();
    
    if (saving) return;
    
    if (!selectedReviewer) {
      alert('Please select a reviewer');
      return;
    }
    
    if (!newRate || newRate < 0 || newRate > 100) {
      alert('Rate must be between 0 and 100');
      return;
    }

    try {
      setSaving(true);
      
      const formData = new FormData();
      formData.append('rate', newRate);
      
      const response = await fetch(`${BASE_URL}/api/sampling_rates/reviewer/${selectedReviewer}`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (response.ok) {
        alert('Reviewer rate updated successfully');
        setSelectedReviewer('');
        setNewRate('');
        fetchSamplingRates();
      } else {
        const error = await response.json();
        alert(`Failed to update: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating reviewer rate:', error);
      alert('Error updating reviewer rate');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteReviewerRate = async (reviewerId) => {
    if (!confirm('Are you sure you want to remove this custom rate? The reviewer will use the global rate.')) {
      return;
    }

    try {
      setSaving(true);
      
      const response = await fetch(`${BASE_URL}/api/sampling_rates/reviewer/${reviewerId}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (response.ok) {
        alert('Reviewer rate removed successfully');
        fetchSamplingRates();
      } else {
        const error = await response.json();
        alert(`Failed to delete: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error deleting reviewer rate:', error);
      alert('Error deleting reviewer rate');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <BaseLayout>
        <div className="container my-4">
          <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </BaseLayout>
    );
  }

  // Filter out reviewers who already have custom rates
  const availableReviewers = allReviewers.filter(
    reviewer => !reviewerRates.some(rr => rr.reviewer_id === reviewer.id)
  );

  return (
    <BaseLayout>
      <div className="container-fluid my-4">
        <div className="row">
          <div className="col-12">
            <h2 className="mb-4">QC Sampling Rates Configuration</h2>
            
            <div className="card shadow-sm mb-4">
              <div className="card-header bg-primary text-white">
                <h5 className="mb-0">How It Works</h5>
              </div>
              <div className="card-body">
                <p className="mb-2">
                  <strong>QC Sampling</strong> determines what percentage of completed reviews are randomly selected for Quality Control checks.
                </p>
                <ul className="mb-0">
                  <li>The <strong>Global Rate</strong> applies to all reviewers by default</li>
                  <li>You can set <strong>Custom Rates</strong> for specific reviewers (overrides global rate)</li>
                  <li>Accredited reviewers are exempt from QC (set in Reviewer Accreditation)</li>
                  <li>Sampling happens automatically when a reviewer completes a task</li>
                </ul>
              </div>
            </div>

            {/* Global Rate */}
            <div className="card shadow-sm mb-4">
              <div className="card-header">
                <h5 className="mb-0">Global Sampling Rate</h5>
              </div>
              <div className="card-body">
                <form onSubmit={handleUpdateGlobalRate} className="row g-3 align-items-end">
                  <div className="col-md-3">
                    <label htmlFor="globalRate" className="form-label fw-semibold">
                      Default Rate (%)
                    </label>
                    <input
                      type="number"
                      className="form-control"
                      id="globalRate"
                      value={globalRate}
                      onChange={(e) => setGlobalRate(e.target.value)}
                      min="0"
                      max="100"
                      step="1"
                      disabled={saving}
                      required
                    />
                    <div className="form-text">Applies to all reviewers without custom rates</div>
                  </div>
                  <div className="col-md-3">
                    <button type="submit" className="btn btn-primary" disabled={saving}>
                      {saving ? 'Updating...' : 'Update Global Rate'}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            {/* Reviewer-Specific Rates */}
            <div className="card shadow-sm mb-4">
              <div className="card-header">
                <h5 className="mb-0">Reviewer-Specific Rates</h5>
              </div>
              <div className="card-body">
                {/* Existing Custom Rates */}
                {reviewerRates.length > 0 ? (
                  <div className="table-responsive mb-4">
                    <table className="table table-hover">
                      <thead className="table-light">
                        <tr>
                          <th>Reviewer</th>
                          <th>Email</th>
                          <th>Role</th>
                          <th>Custom Rate (%)</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reviewerRates.map((rr) => (
                          <tr key={rr.reviewer_id}>
                            <td>{rr.name}</td>
                            <td>{rr.email}</td>
                            <td><span className="badge bg-secondary">{rr.role}</span></td>
                            <td><strong>{rr.rate}%</strong></td>
                            <td>
                              <button
                                className="btn btn-sm btn-danger"
                                onClick={() => handleDeleteReviewerRate(rr.reviewer_id)}
                                disabled={saving}
                              >
                                <i className="bi bi-trash"></i> Remove
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="alert alert-info">
                    No custom reviewer rates configured. All reviewers use the global rate.
                  </div>
                )}

                {/* Add New Custom Rate */}
                <h6 className="mb-3">Add Custom Rate</h6>
                <form onSubmit={handleAddReviewerRate} className="row g-3 align-items-end">
                  <div className="col-md-4">
                    <label htmlFor="reviewer" className="form-label">Reviewer</label>
                    <select
                      className="form-select"
                      id="reviewer"
                      value={selectedReviewer}
                      onChange={(e) => setSelectedReviewer(e.target.value)}
                      disabled={saving || availableReviewers.length === 0}
                      required
                    >
                      <option value="">Select a reviewer...</option>
                      {availableReviewers.map((reviewer) => (
                        <option key={reviewer.id} value={reviewer.id}>
                          {reviewer.name} ({reviewer.email})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-3">
                    <label htmlFor="rate" className="form-label">Custom Rate (%)</label>
                    <input
                      type="number"
                      className="form-control"
                      id="rate"
                      value={newRate}
                      onChange={(e) => setNewRate(e.target.value)}
                      min="0"
                      max="100"
                      step="1"
                      disabled={saving}
                      required
                    />
                  </div>
                  <div className="col-md-3">
                    <button 
                      type="submit" 
                      className="btn btn-success" 
                      disabled={saving || availableReviewers.length === 0}
                    >
                      {saving ? 'Adding...' : 'Add Custom Rate'}
                    </button>
                  </div>
                </form>

                {availableReviewers.length === 0 && reviewerRates.length > 0 && (
                  <div className="alert alert-warning mt-3 mb-0">
                    All reviewers already have custom rates configured.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </BaseLayout>
  );
}

export default SamplingRatesConfig;


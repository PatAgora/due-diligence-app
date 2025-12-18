import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import AISMEAdminReferrals from './AISMEAdminReferrals';
import AISMEAdminFeedback from './AISMEAdminFeedback';
import AISMEAdminDocs from './AISMEAdminDocs';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';
import AISMEAdminConfig from './AISMEAdminConfig';
import AISMEAdminResolutions from './AISMEAdminResolutions';

function AISMEAdmin() {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState({
    referrals: { total: 0, open: 0 },
    feedback: { total: 0, yesRate: 0 }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);
      
      // Load referral stats
      const referralsRes = await fetch(`${BASE_URL}/api/sme/admin/referrals/data`, {
        credentials: 'include'
      });
      if (referralsRes.ok) {
        const referralsData = await referralsRes.json();
        const items = referralsData.data || [];
        setStats(prev => ({
          ...prev,
          referrals: {
            total: items.length,
            open: items.filter(r => (r.status || 'open') === 'open').length
          }
        }));
      }

      // Load feedback stats
      const feedbackRes = await fetch(`${BASE_URL}/api/sme/admin/feedback/data`, {
        credentials: 'include'
      });
      if (feedbackRes.ok) {
        const feedbackData = await feedbackRes.json();
        const totals = feedbackData.totals || {};
        const yes = Number(totals.yes || 0);
        const no = Number(totals.no || 0);
        const total = yes + no;
        const rate = total > 0 ? Math.round((yes / total) * 100) : 0;
        setStats(prev => ({
          ...prev,
          feedback: { total, yesRate: rate }
        }));
      }
    } catch (error) {
      console.error('Error loading stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: 'bi-speedometer2' },
    { id: 'docs', label: 'Documents', icon: 'bi-file-earmark-text' },
    { id: 'referrals', label: 'Referrals', icon: 'bi-flag' },
    { id: 'feedback', label: 'Feedback', icon: 'bi-graph-up' },
    { id: 'resolutions', label: 'SME Resolutions', icon: 'bi-check-circle' },
    { id: 'config', label: 'Settings', icon: 'bi-gear' }
  ];

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">
          <i className="fas fa-brain me-2"></i>
          AI SME Administration
        </h2>
      </div>

      {/* Tabs */}
      <ul className="nav nav-tabs mb-4" role="tablist">
        {tabs.map(tab => (
          <li key={tab.id} className="nav-item" role="presentation">
            <button
              className={`nav-link ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
              type="button"
            >
              <i className={`bi ${tab.icon} me-2`}></i>
              {tab.label}
            </button>
          </li>
        ))}
      </ul>

      {/* Tab Content */}
      <div className="tab-content">
        {activeTab === 'overview' && (
          <div>
            <div className="row mb-4">
              <div className="col-md-6 mb-3">
                <div className="card">
                  <div className="card-body">
                    <h5 className="card-title">
                      <i className="bi bi-flag me-2"></i>
                      Referrals
                    </h5>
                    <div className="d-flex justify-content-between align-items-center mt-3">
                      <div>
                        <h3 className="mb-0">{stats.referrals.total}</h3>
                        <small className="text-muted">Total Referrals</small>
                      </div>
                      <div>
                        <h3 className="mb-0 text-warning">{stats.referrals.open}</h3>
                        <small className="text-muted">Open</small>
                      </div>
                    </div>
                    <button
                      className="btn btn-primary mt-3"
                      onClick={() => setActiveTab('referrals')}
                    >
                      View All Referrals
                    </button>
                  </div>
                </div>
              </div>
              <div className="col-md-6 mb-3">
                <div className="card">
                  <div className="card-body">
                    <h5 className="card-title">
                      <i className="bi bi-graph-up me-2"></i>
                      Feedback Analytics
                    </h5>
                    <div className="d-flex justify-content-between align-items-center mt-3">
                      <div>
                        <h3 className="mb-0">{stats.feedback.total}</h3>
                        <small className="text-muted">Total Responses</small>
                      </div>
                      <div>
                        <h3 className="mb-0 text-success">{stats.feedback.yesRate}%</h3>
                        <small className="text-muted">Yes Rate</small>
                      </div>
                    </div>
                    <button
                      className="btn btn-primary mt-3"
                      onClick={() => setActiveTab('feedback')}
                    >
                      View Feedback Dashboard
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">Quick Actions</h5>
                <div className="d-flex gap-2 flex-wrap">
                  <button
                    className="btn btn-outline-primary"
                    onClick={() => setActiveTab('docs')}
                  >
                    <i className="bi bi-upload me-2"></i>
                    Upload Document
                  </button>
                  <button
                    className="btn btn-outline-primary"
                    onClick={() => setActiveTab('resolutions')}
                  >
                    <i className="bi bi-check-circle me-2"></i>
                    Add SME Resolution
                  </button>
                  <button
                    className="btn btn-outline-primary"
                    onClick={() => setActiveTab('config')}
                  >
                    <i className="bi bi-gear me-2"></i>
                    Configure Settings
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'docs' && <AISMEAdminDocs />}
        {activeTab === 'referrals' && <AISMEAdminReferrals />}
        {activeTab === 'feedback' && <AISMEAdminFeedback />}
        {activeTab === 'resolutions' && <AISMEAdminResolutions />}
        {activeTab === 'config' && <AISMEAdminConfig />}
      </div>
    </div>
  );
}

export default AISMEAdmin;



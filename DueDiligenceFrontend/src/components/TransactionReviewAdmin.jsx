import React, { useState } from 'react';
import TransactionReviewConfig from './TransactionReviewConfig';
import TransactionReviewDataIngest from './TransactionReviewDataIngest';

function TransactionReviewAdmin() {
  const [activeTab, setActiveTab] = useState('config');

  const tabs = [
    { id: 'config', label: 'Configuration', icon: 'bi-gear' },
    { id: 'ingest', label: 'Data & Ingest', icon: 'bi-upload' }
  ];

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">
          <i className="bi bi-arrow-repeat me-2"></i>
          Transaction Review Administration
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
        {activeTab === 'config' && <TransactionReviewConfig />}
        {activeTab === 'ingest' && <TransactionReviewDataIngest />}
      </div>
    </div>
  );
}

export default TransactionReviewAdmin;


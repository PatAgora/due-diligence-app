import React, { useState } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function TransactionReviewDataIngest() {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [files, setFiles] = useState({
    tx_file: null,
    country_file: null,
    sort_file: null
  });

  const handleFileChange = (name, file) => {
    setFiles(prev => ({ ...prev, [name]: file }));
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    
    const hasFiles = Object.values(files).some(f => f !== null);
    if (!hasFiles) {
      setResult({ type: 'error', message: 'Please select at least one file to upload' });
      return;
    }

    try {
      setUploading(true);
      setResult(null);
      
      const formData = new FormData();
      if (files.tx_file) formData.append('tx_file', files.tx_file);
      if (files.country_file) formData.append('country_file', files.country_file);
      if (files.sort_file) formData.append('sort_file', files.sort_file);

      const response = await fetch(`${BASE_URL}/api/tx_review/upload`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      if (response.ok && data.status === 'ok') {
        setResult({ type: 'success', message: data.message || 'Files uploaded and processed successfully!' });
        setFiles({ tx_file: null, country_file: null, sort_file: null });
        e.target.reset();
      } else {
        setResult({ type: 'error', message: data.error || 'Upload failed' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message || 'Failed to upload files' });
    } finally {
      setUploading(false);
      setTimeout(() => setResult(null), 5000);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-header">
          <h5 className="mb-0">Data Ingestion</h5>
        </div>
        <div className="card-body">
          <p className="text-muted mb-4">
            Upload transactions CSV or reference data files. Transactions CSV should include columns:
            <code className="ms-2">id, txn_date, customer_id, direction, amount, currency, base_amount, country_iso2, payer_sort_code, payee_sort_code, channel, narrative</code>
          </p>

          <form onSubmit={handleUpload}>
            <div className="row g-3 mb-3">
              <div className="col-md-4">
                <label className="form-label">Transactions CSV</label>
                <input
                  type="file"
                  className="form-control"
                  accept=".csv"
                  onChange={(e) => handleFileChange('tx_file', e.target.files[0] || null)}
                />
                {files.tx_file && (
                  <small className="text-muted">Selected: {files.tx_file.name}</small>
                )}
              </div>
              <div className="col-md-4">
                <label className="form-label">Country Risk CSV</label>
                <input
                  type="file"
                  className="form-control"
                  accept=".csv"
                  onChange={(e) => handleFileChange('country_file', e.target.files[0] || null)}
                />
                {files.country_file && (
                  <small className="text-muted">Selected: {files.country_file.name}</small>
                )}
              </div>
              <div className="col-md-4">
                <label className="form-label">Sort Codes CSV</label>
                <input
                  type="file"
                  className="form-control"
                  accept=".csv"
                  onChange={(e) => handleFileChange('sort_file', e.target.files[0] || null)}
                />
                {files.sort_file && (
                  <small className="text-muted">Selected: {files.sort_file.name}</small>
                )}
              </div>
            </div>

            <div className="d-flex gap-2">
              <button type="submit" className="btn btn-primary" disabled={uploading || !Object.values(files).some(f => f !== null)}>
                {uploading ? 'Uploading...' : 'Upload & Process'}
              </button>
              <a
                href={`${BASE_URL}/api/tx_review/sample/transactions_sample.csv`}
                target="_blank"
                className="btn btn-outline-secondary"
              >
                Download Sample Transactions
              </a>
              <a
                href={`${BASE_URL}/api/tx_review/sample/ref_country_risk.csv`}
                target="_blank"
                className="btn btn-outline-secondary"
              >
                Sample Country Risk
              </a>
              <a
                href={`${BASE_URL}/api/tx_review/sample/ref_sort_codes.csv`}
                target="_blank"
                className="btn btn-outline-secondary"
              >
                Sample Sort Codes
              </a>
            </div>
          </form>

          {result && (
            <div className={`alert alert-${result.type === 'success' ? 'success' : 'danger'} mt-3`}>
              {result.message}
            </div>
          )}

          <div className="mt-4">
            <h6>File Format Requirements</h6>
            <ul className="small text-muted">
              <li><strong>Transactions CSV:</strong> Must include all required columns. Date format should be YYYY-MM-DD or DD/MM/YYYY</li>
              <li><strong>Country Risk CSV:</strong> Columns: iso2, risk_level, score, prohibited</li>
              <li><strong>Sort Codes CSV:</strong> Columns: sort_code, bank_name, branch, schemes, valid_from, valid_to</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TransactionReviewDataIngest;


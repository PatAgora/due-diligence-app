import React, { useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AISMEAdminDocs() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');

  useEffect(() => {
    loadDocs();
  }, []);

  const loadDocs = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/sme/admin/docs`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setDocs(data.data || []);
      }
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    if (selectedFile && !title) {
      setTitle(selectedFile.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    try {
      setUploading(true);
      setUploadResult(null);
      const formData = new FormData();
      formData.append('file', file);
      if (title) formData.append('title', title);

      const response = await fetch(`${BASE_URL}/api/sme/admin/upload`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      if (response.ok && (data.status === 'ok' || data.message)) {
        setUploadResult({ type: 'success', message: data.message || 'Document uploaded successfully' });
        setFile(null);
        setTitle('');
        e.target.reset();
        loadDocs();
      } else {
        setUploadResult({ type: 'error', message: data.message || 'Upload failed' });
      }
    } catch (error) {
      setUploadResult({ type: 'error', message: error.message || 'Failed to upload document' });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId, docTitle) => {
    if (!window.confirm(`Are you sure you want to delete "${docTitle}"?`)) return;

    try {
      const formData = new FormData();
      formData.append('doc_id', docId);
      const response = await fetch(`${BASE_URL}/api/sme/admin/docs/delete`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      const data = await response.json();
      if (response.ok && data.status === 'ok') {
        loadDocs();
        setUploadResult({ type: 'success', message: 'Document deleted successfully' });
      } else {
        setUploadResult({ type: 'error', message: data.message || 'Delete failed' });
      }
    } catch (error) {
      setUploadResult({ type: 'error', message: error.message || 'Failed to delete document' });
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div>
      <div className="card mb-4">
        <div className="card-header">
          <h5 className="mb-0">Upload Guidance Document</h5>
        </div>
        <div className="card-body">
          <form onSubmit={handleUpload}>
            <div className="mb-3">
              <label htmlFor="file" className="form-label">Document File</label>
              <input
                type="file"
                className="form-control"
                id="file"
                accept=".pdf,.txt,.md,.docx,.csv"
                onChange={handleFileChange}
                required
              />
            </div>
            <div className="mb-3">
              <label htmlFor="title" className="form-label">Title (Optional)</label>
              <input
                type="text"
                className="form-control"
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Document title"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={uploading || !file}>
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
          {uploadResult && (
            <div className={`alert alert-${uploadResult.type === 'success' ? 'success' : 'danger'} mt-3`}>
              {uploadResult.message}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Stored Documents ({docs.length})</h5>
          <div>
            <a
              href={`${BASE_URL}/api/sme/admin/docs/export?fmt=json`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary me-2"
            >
              Export JSON
            </a>
            <a
              href={`${BASE_URL}/api/sme/admin/docs/export?fmt=csv`}
              target="_blank"
              className="btn btn-sm btn-outline-secondary"
            >
              Export CSV
            </a>
          </div>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : docs.length === 0 ? (
            <div className="text-center py-4 text-muted">
              <i className="fas fa-folder-open fa-3x mb-3"></i>
              <p>No documents uploaded yet</p>
              <small>Upload your first guidance document above to get started</small>
            </div>
          ) : (
            <div className="list-group">
              {docs.map((doc) => (
                <div key={doc.doc_id || doc.id} className="list-group-item">
                  <div className="d-flex justify-content-between align-items-start">
                    <div>
                      <h6 className="mb-1">{doc.title || 'Untitled'}</h6>
                      <small className="text-muted">
                        <i className="bi bi-calendar me-1"></i>
                        Uploaded: {formatDate(doc.uploaded_at)}
                        {doc.chunks && ` • ${doc.chunks} chunks`}
                        {doc.sha256 && ` • SHA: ${doc.sha256.substring(0, 8)}...`}
                      </small>
                    </div>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDelete(doc.doc_id || doc.id, doc.title || 'Untitled')}
                    >
                      <i className="bi bi-trash me-1"></i>
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AISMEAdminDocs;



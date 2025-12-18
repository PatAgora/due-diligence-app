// static/js/admin.js

// ---------- DOM refs ----------
const uploadForm  = document.getElementById('upload-form');
const uploadResult= document.getElementById('upload-result');
const docsList    = document.getElementById('docs-list');
const docsCount   = document.getElementById('docs-count');
const healthEl    = document.getElementById('health');

// ---------- utils ----------
function safe(v, def = '—') { return (v !== null && v !== undefined && v !== '') ? v : def; }
function shortHash(v) { if (!v || typeof v !== 'string') return '—'; return v.length >= 8 ? v.slice(0, 8) + '…' : v; }
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

// ---------- health ----------
async function checkHealth() {
  if (!healthEl) return;
  try {
    await (await fetch('/health')).json();
    healthEl.textContent = 'Ready';
    healthEl.classList.add('ok');
    healthEl.classList.remove('err');
  } catch {
    healthEl.textContent = 'Backend unreachable';
    healthEl.classList.add('err');
    healthEl.classList.remove('ok');
  }
}
checkHealth();

// ---------- doc helpers ----------
function coerceDoc(raw) {
  if (!raw || typeof raw !== 'object') return null;
  return {
    id:         raw.id ?? raw.doc_id ?? raw.uuid ?? raw.sha ?? '',
    title:      raw.title ?? raw.name ?? '',
    filename:   raw.filename ?? raw.original_name ?? raw.file_name ?? '',
    uploadedAt: raw.uploaded_at ?? raw.created_at ?? raw.ts ?? raw.inserted_at ?? null,
    pieces:     raw.pieces ?? raw.chunk_count ?? raw.chunks ?? raw.num_chunks ?? raw.piece_count ?? null,
    sha256:     raw.sha256 ?? raw.sha ?? null,
  };
}
function extractRows(json) {
  if (Array.isArray(json)) return json;
  if (Array.isArray(json?.docs)) return json.docs;
  if (Array.isArray(json?.data)) return json.data;
  if (Array.isArray(json?.data?.docs)) return json.data.docs;
  if (Array.isArray(json?.rows)) return json.rows;
  if (Array.isArray(json?.result)) return json.result;
  return [];
}
const looksLikeDocs = (arr) => {
  if (!Array.isArray(arr) || !arr.length) return false;
  const obj = arr.find(x => x && typeof x === 'object') || {};
  const kset = new Set(Object.keys(obj).map(k => k.toLowerCase()));
  const hints = ['id','doc_id','uuid','title','name','filename','original_name','uploaded_at','created_at','chunk_count','chunks','pieces','sha','sha256'];
  return hints.some(h => kset.has(h));
};
function findDocsArray(node, depth = 0) {
  if (!node || depth > 6) return null;
  if (Array.isArray(node)) return looksLikeDocs(node) ? node : null;
  if (typeof node === 'object') {
    for (const k of Object.keys(node)) {
      const found = findDocsArray(node[k], depth + 1);
      if (found) return found;
    }
  }
  return null;
}

// ---------- documents ----------
async function loadDocs() {
  if (docsList) {
    docsList.innerHTML = `
      <div style="text-align:center;padding:2rem;">
        <i class="fas fa-spinner fa-spin" style="font-size:1.5rem;"></i>
        <p>Loading documents…</p>
      </div>`;
  }

  const render = (rows) => {
    const docs = rows.map(coerceDoc).filter(Boolean);
    if (docsCount) docsCount.textContent = `${docs.length} guidance doc${docs.length === 1 ? '' : 's'}`;

    if (!docs.length) {
      docsList.innerHTML = `
        <div style="text-align:center;padding:3rem;color:var(--text-muted);">
          <i class="fas fa-folder-open" style="font-size:3rem;margin-bottom:1rem;"></i>
          <p>No documents uploaded yet</p>
          <small>Upload your first guidance document above to get started</small>
        </div>`;
      return;
    }

    const container = document.createElement('div');
    docs.forEach(d => {
      const title = (d.title || d.filename || 'Untitled').toString();
      const uploaded = fmtDate(d.uploadedAt);
      const piecesTxt = (d.pieces != null && d.pieces !== '') ? d.pieces : '—';
      const shaTxt = shortHash(d.sha256);

      const row = document.createElement('div');
      row.className = 'doc-item';
      row.innerHTML = `
        <div class="doc-info">
          <div class="doc-title">${title}</div>
          <div class="doc-meta">
            <i class="fas fa-calendar"></i> Uploaded: ${uploaded}
            ${piecesTxt !== '—' ? ` • <i class="fas fa-puzzle-piece"></i> ${piecesTxt} pieces` : ''}
            ${shaTxt !== '—' ? ` • <i class="fas fa-fingerprint"></i> ${shaTxt}` : ''}
          </div>
        </div>
        <div class="doc-actions">
          <button class="btn btn-danger btn-sm" data-id="${d.id}" ${d.id ? '' : 'disabled'}>
            <i class="fas fa-trash"></i> Delete
          </button>
        </div>
      `;
      container.appendChild(row);
    });

    docsList.innerHTML = '';
    docsList.appendChild(container);

    // Delete calls your POST /delete with form-encoded doc_id
    container.querySelectorAll('button[data-id]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        if (!id) return;
        if (!confirm('Delete this document from the store?')) return;

        try {
          const fd = new FormData();
          fd.append('doc_id', id);
          const resp = await fetch('/delete', { method: 'POST', body: fd });
          const payload = await resp.json().catch(() => ({}));
          if (!resp.ok || payload?.status !== 'ok') {
            console.error('Delete failed', resp.status, payload);
            alert('Failed to delete document.');
            return;
          }
          await loadDocs();
          toast('Document deleted', 'success');
        } catch (e) {
          console.error('Delete error:', e);
          alert('Failed to delete document.');
        }
      });
    });
  };

  try {
    // Primary endpoint
    const res = await fetch('/admin/docs', { headers: { 'Accept': 'application/json' } });
    const json = await res.json().catch(() => ({}));

    let rows = extractRows(json);
    if (!rows.length) rows = findDocsArray(json) || [];

    // Fallback to export JSON you said is populated
    if (!rows.length) {
      const exp = await fetch('/admin/docs/export?fmt=json', { headers: { 'Accept': 'application/json' } });
      const expJson = await exp.json().catch(() => ({}));
      rows = extractRows(expJson);
      if (!rows.length) rows = findDocsArray(expJson) || [];
    }

    // Log once to help diagnose if ever empty again
    if (!rows.length) console.warn('Could not locate docs array in response of /admin/docs:', json);

    render(rows);
  } catch (e) {
    console.error('loadDocs error:', e);
    if (docsList) docsList.textContent = 'Failed to load list.';
    if (docsCount) docsCount.textContent = '0 docs';
  }
}

// ---------- upload (POST /upload, not /admin/upload) ----------
if (uploadForm) {
  uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (uploadResult) {
      uploadResult.textContent = 'Uploading…';
      uploadResult.className = 'result-message loading';
      uploadResult.style.display = 'block';
    }

    try {
      const fd = new FormData(uploadForm);
      const res = await fetch('/upload', { method: 'POST', body: fd });
      const data = await res.json().catch(() => ({}));

      if (res.ok && (data.status === 'ok' || data.message)) {
        if (uploadResult) {
          uploadResult.textContent = data.message || `Uploaded: ${safe(data.title, 'untitled')}`;
          uploadResult.className = 'result-message success';
        }
        uploadForm.reset();
        await loadDocs();
      } else {
        if (uploadResult) {
          uploadResult.textContent = data.message || 'Upload failed.';
          uploadResult.className = 'result-message error';
        }
      }
    } catch (err) {
      console.error('Upload error:', err);
      if (uploadResult) {
        uploadResult.textContent = 'Upload error.';
        uploadResult.className = 'result-message error';
      }
    } finally {
      setTimeout(() => { if (uploadResult) uploadResult.style.display = 'none'; }, 3500);
    }
  });
}

// ---------- export buttons (optional) ----------
document.getElementById('export-json')?.addEventListener('click', (e) => {
  e.preventDefault(); window.location.href = '/admin/docs/export?fmt=json';
});
document.getElementById('export-csv')?.addEventListener('click', (e) => {
  e.preventDefault(); window.location.href = '/admin/docs/export?fmt=csv';
});

// ---------- show-sources toggle ----------
(function () {
  const toggle = document.getElementById('show-sources-toggle');
  const result = document.getElementById('settings-result');
  if (!toggle) return;
  toggle.checked = localStorage.getItem('show_sources') === '1';
  toggle.addEventListener('change', () => {
    const on = toggle.checked;
    localStorage.setItem('show_sources', on ? '1' : '0');
    if (result) {
      result.textContent = on ? 'Sources will be shown under answers.' : 'Sources will be hidden.';
      result.className = 'result-message success';
      result.style.display = 'block';
      setTimeout(() => (result.style.display = 'none'), 2000);
    }
  });
})();

// ---------- tiny toast ----------
function toast(message, type = 'info') {
  const n = document.createElement('div');
  n.style.cssText = `
    position:fixed;top:20px;right:20px;z-index:1000;
    padding:0.75rem 1rem;border-radius:8px;color:#fff;font-weight:600;
    background:${type==='success' ? '#22c55e' : type==='error' ? '#ef4444' : '#ff6b35'};
    transform:translateX(120%);transition:transform .25s ease;
    box-shadow:0 6px 20px rgba(0,0,0,.2);
  `;
  n.textContent = message;
  document.body.appendChild(n);
  requestAnimationFrame(() => { n.style.transform = 'translateX(0)'; });
  setTimeout(() => { n.style.transform = 'translateX(120%)'; setTimeout(()=>n.remove(), 300); }, 3000);
}

// ---------- initial ----------
loadDocs();
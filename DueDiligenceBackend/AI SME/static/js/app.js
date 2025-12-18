// static/js/app.js

const chatWindow = document.getElementById('chat-window');
const askForm = document.getElementById('ask-form');
const retrievalHint = document.getElementById('retrieval-hint');
const backendBadge = document.getElementById('backend-badge');
const backendSpan = document.getElementById('backend');
const healthDiv = document.getElementById('health');

// Runtime config (from /health)
let BOT_NAME = 'Assistant';
let AUTO_YES_MS = 30000;

// Simple per-tab/session id for feedback attribution
let SESSION_ID = (typeof crypto !== 'undefined' && crypto.randomUUID)
  ? crypto.randomUUID()
  : 'sess_' + Math.random().toString(36).slice(2);

// ---- Robust fallback detector ----
function isFallbackAnswer(text, serverFlag = false) {
  if (serverFlag) return true; // if backend ever sends a flag, trust it
  if (!text) return false;

  const s = String(text)
    .toLowerCase()
    .normalize('NFKC')           // normalise Unicode
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/\s+/g, ' ')
    .trim();

  // quick substring (fast path)
  if (s.includes('not able to confirm based on the current guidance')) return true;

  // regex variants
  const patterns = [
    /\b(?:i|you)\s+(?:am|are|m)?\s*not\s+able\s+to\s+confirm\s+based\s+on\s+the\s+current\s+guidance\b/i,
    /\b(?:i|you)\s+(?:cannot|can\'?t)\s+confirm\s+based\s+on\s+the\s+current\s+guidance\b/i,
  ];
  const hit = patterns.some(re => re.test(s));
  if (!hit) {
    // helpful during debugging
    console.debug('[fallback check] no match; text=', s);
  }
  return hit;
}

// -------- Health / backend + config --------
async function checkHealth() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    const backend = data.llm_backend || 'unknown';
    BOT_NAME = data.bot_name || BOT_NAME;
    AUTO_YES_MS = Number.isFinite(data.auto_yes_ms) ? data.auto_yes_ms : AUTO_YES_MS;

    if (backendBadge) backendBadge.textContent = `(${backend})`;
    if (backendSpan) backendSpan.textContent = backend;
    if (healthDiv) {
      healthDiv.textContent = 'Ready';
      healthDiv.classList.add('ok');
      healthDiv.classList.remove('err');
    }
  } catch {
    if (healthDiv) {
      healthDiv.textContent = 'Backend unreachable';
      healthDiv.classList.add('err');
      healthDiv.classList.remove('ok');
    }
  }
}
checkHealth();

// -------- Chat helpers --------
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function appendMessage(role, html) {
  const div = document.createElement('div');
  const speaker = role === 'user' ? 'You' : BOT_NAME;
  div.className = `msg ${role}`;
  div.innerHTML = `<strong>${speaker}:</strong> ${html}`;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

// Thinking indicator
function showThinking() {
  const div = document.createElement('div');
  div.className = 'msg assistant thinking';
  div.innerHTML = `<strong>${BOT_NAME}:</strong> <span class="dots">Thinking</span>`;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  let i = 0;
  const timer = setInterval(() => {
    i = (i + 1) % 4;
    const dots = '.'.repeat(i);
    const span = div.querySelector('.dots');
    if (span) span.textContent = `Thinking${dots}`;
  }, 450);

  return {
    replaceWithAnswer(answerText) {
      clearInterval(timer);
      div.classList.remove('thinking');
      div.innerHTML = `<strong>${BOT_NAME}:</strong> ${escapeHtml(answerText)}`;
      chatWindow.scrollTop = chatWindow.scrollHeight;
      return div;
    },
    remove() {
      clearInterval(timer);
      div.remove();
    }
  };
}

// Disable/enable input while waiting
function setInputDisabled(disabled) {
  const input = document.getElementById('q');
  const button = askForm?.querySelector('button[type="submit"]');
  if (input) input.disabled = disabled;
  if (button) {
    button.disabled = disabled;
    button.textContent = disabled ? 'Thinking…' : 'Ask';
  }
}

// ---- Inline feedback + referral ----
function appendFeedbackBlock({ question, answer, autoYesMs }) {
  const ms = Number.isFinite(autoYesMs) ? autoYesMs : AUTO_YES_MS;

  const wrap = document.createElement('div');
  wrap.className = 'msg assistant';
  wrap.innerHTML = `
    <div><strong>${BOT_NAME}:</strong> <em>Did this answer your question?</em></div>
    <div style="margin-top:6px; display:flex; gap:8px;">
      <button class="btn btn-primary btn-md fb-yes">Yes</button>
      <button class="btn btn-ghost btn-md fb-no">No</button>
      <span class="muted-small fb-timer" style="margin-left:8px;"></span>
    </div>
  `;
  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  const btnYes = wrap.querySelector('.fb-yes');
  const btnNo  = wrap.querySelector('.fb-no');
  const timerEl = wrap.querySelector('.fb-timer');

  let decided = false;
  let remaining = Math.max(0, Math.floor(ms / 1000));
  timerEl.textContent = remaining ? `(auto “Yes” in ${remaining}s)` : '';

  const tick = remaining
    ? setInterval(() => {
        if (decided) return;
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(tick);
          if (!decided) doYes(true);
        } else {
          timerEl.textContent = `(auto “Yes” in ${remaining}s)`;
        }
      }, 1000)
    : null;

  function disableButtons() {
    btnYes.disabled = true;
    btnNo.disabled = true;
  }

  async function sendFeedback(helpful) {
    try {
      const fd = new FormData();
      fd.append('q', question);
      fd.append('answer', answer);
      fd.append('helpful', String(helpful));
      fd.append('session_id', SESSION_ID);
      await fetch('/feedback', { method: 'POST', body: fd });
    } catch {}
  }

  function doYes(isAuto = false) {
    decided = true;
    if (tick) clearInterval(tick);
    disableButtons();
    sendFeedback(true);
    const msg = isAuto ? 'Marked as helpful (auto).' : 'Thanks for the feedback!';
    const note = document.createElement('div');
    note.className = 'muted-small';
    note.style.marginTop = '6px';
    note.textContent = msg;
    wrap.appendChild(note);
  }

  function renderInlineReferral() {
    const div = document.createElement('div');
    div.style.marginTop = '10px';
    div.innerHTML = `
      <div class="muted-small" style="margin-bottom:6px;">Please add a short note for the referral:</div>
      <textarea class="ref-note" placeholder="Brief note to SMEs…" style="width:100%; min-height:90px;"></textarea>
      <div style="display:flex; gap:8px; margin-top:8px;">
        <button class="btn btn-primary btn-md ref-submit">Submit referral</button>
        <button class="btn btn-ghost btn-md ref-cancel">Cancel</button>
      </div>
      <div class="muted-small ref-status" style="margin-top:6px;"></div>
    `;
    wrap.appendChild(div);

    const noteEl = div.querySelector('.ref-note');
    const submitEl = div.querySelector('.ref-submit');
    const cancelEl = div.querySelector('.ref-cancel');
    const statusEl = div.querySelector('.ref-status');

    submitEl.addEventListener('click', async () => {
      statusEl.textContent = 'Submitting…';
      try {
        const fd = new FormData();
        fd.append('reason', noteEl.value || 'User indicated the answer did not resolve the query.');
        fd.append('question', question);
        fd.append('answer', answer);
        const res = await fetch('/referral', { method: 'POST', body: fd });
        const data = await res.json();
        statusEl.textContent = data?.message || 'Referral logged';

        const ok = document.createElement('div');
        ok.className = 'muted-small';
        ok.style.marginTop = '6px';
        ok.textContent = '✅ Referral submitted.';
        wrap.appendChild(ok);

        submitEl.disabled = true;
        cancelEl.disabled = true;
        noteEl.disabled = true;
      } catch {
        statusEl.textContent = 'Failed to submit referral.';
      }
    });

    cancelEl.addEventListener('click', () => {
      div.remove();
    });
  }

  function doNo() {
    decided = true;
    if (tick) clearInterval(tick);
    disableButtons();
    sendFeedback(false);

    const note = document.createElement('div');
    note.className = 'muted-small';
    note.style.marginTop = '6px';
    note.textContent = 'Thanks — let’s raise a referral so an SME can help.';
    wrap.appendChild(note);

    renderInlineReferral();
  }

  btnYes.addEventListener('click', () => doYes(false));
  btnNo.addEventListener('click', () => doNo());

  return wrap;
}

// -------- Ask form --------
if (askForm) {
  askForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('q');
    const q = (input?.value || '').trim();
    if (!q) return;

    // render user message
    appendMessage('user', escapeHtml(q));
    window.__lastQuestion = q;
    if (input) input.value = '';
    if (retrievalHint) retrievalHint.textContent = '';
    setInputDisabled(true);

    // thinking row
    const thinking = showThinking();

    // call backend
    const fd = new FormData();
    fd.append('q', q);

    try {
      const res = await fetch('/query', { method: 'POST', body: fd });
      const data = await res.json();

      const answer = data?.answer || '(no answer)';
      window.__lastAnswer = answer;
      const answerDiv = thinking.replaceWithAnswer(answer);

      // backend MAY include a hint like { is_fallback: true } in future
      const serverFallback = !!data?.is_fallback;

      // === Auto-referral on fallback; skip Yes/No ===
      if (isFallbackAnswer(answer, serverFallback)) {
        console.debug('[auto-referral] triggering (detected fallback).');
        try {
          const fdRef = new FormData();
          fdRef.append('reason', 'Auto-referral: bot could not confirm based on current guidance.');
          fdRef.append('question', q);
          fdRef.append('answer', answer);

          const resRef = await fetch('/referral', { method: 'POST', body: fdRef });
          const dataRef = await resRef.json();

          const note = document.createElement('div');
          note.className = 'muted-small';
          note.style.marginTop = '6px';
          note.textContent = (dataRef?.message || 'Referral logged') + ' — you can view it under “My referrals”.';
          answerDiv.appendChild(note);
        } catch (err) {
          console.warn('[auto-referral] failed:', err);
          const note = document.createElement('div');
          note.className = 'muted-small';
          note.style.marginTop = '6px';
          note.textContent = 'Tried to auto-raise a referral but something went wrong.';
          answerDiv.appendChild(note);
        }
        // Do NOT render the Yes/No block
      } else {
        // Normal path: show inline feedback
        appendFeedbackBlock({ question: q, answer, autoYesMs: AUTO_YES_MS });
      }

    } catch (err) {
      console.error(err);
      thinking.replaceWithAnswer('Error contacting the API.');
    } finally {
      setInputDisabled(false);
    }
  });
}
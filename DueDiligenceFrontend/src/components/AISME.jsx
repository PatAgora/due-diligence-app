import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './AISME.css';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AISME({ taskId, customerId }) {
  const navigate = useNavigate();
  const chatWindowRef = useRef(null);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [thinking, setThinking] = useState(false);
  const [healthStatus, setHealthStatus] = useState('Checking…');
  const [botName, setBotName] = useState('Assistant');
  const [autoYesMs, setAutoYesMs] = useState(30000);
  const [showWelcome, setShowWelcome] = useState(true);
  const [lastQuestion, setLastQuestion] = useState('');
  const [lastAnswer, setLastAnswer] = useState('');
  const [referralNotes, setReferralNotes] = useState({});

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/sme/health`, { 
        credentials: 'include',
        cache: 'no-store' 
      });
      if (res.ok) {
        const data = await res.json();
        // Check if the response indicates the service is actually available
        if (data.status === 'ok' && data.llm_backend && data.llm_backend !== 'unknown') {
          setHealthStatus('Online');
          setBotName(data.bot_name || 'Assistant');
          setAutoYesMs(data.auto_yes_ms || 30000);
        } else {
          setHealthStatus('Offline');
        }
      } else {
        // HTTP error (503, etc.) means service is down
        setHealthStatus('Offline');
      }
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus('Offline');
    }
  };

  const escapeHtml = (text) => {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  const appendMessage = (role, html) => {
    const newMessage = {
      id: Date.now() + Math.random(),
      role,
      html,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, newMessage]);
    setShowWelcome(false);
  };

  const isFallbackAnswer = (text) => {
    if (!text) return false;
    const s = String(text).toLowerCase().normalize('NFKC')
      .replace(/[""]/g, '"')
      .replace(/['']/g, "'")
      .replace(/\s+/g, ' ')
      .trim();
    
    if (s.includes('not able to confirm based on the current guidance')) return true;
    
    const patterns = [
      /\b(?:i|you)\s+(?:am|are|m)?\s*not\s+able\s+to\s+confirm\s+based\s+on\s+the\s+current\s+guidance\b/i,
      /\b(?:i|you)\s+(?:cannot|can\'?t)\s+confirm\s+based\s+on\s+the\s+current\s+guidance\b/i,
    ];
    return patterns.some(re => re.test(s));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || thinking) return;

    // Add user message
    appendMessage('user', escapeHtml(q));
    setLastQuestion(q);
    setQuestion('');
    setThinking(true);

    try {
      const formData = new FormData();
      formData.append('q', q);

      const res = await fetch(`${BASE_URL}/api/sme/query`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (!res.ok) {
        throw new Error('Failed to get response');
      }

      const data = await res.json();
      const answer = data?.answer || '(no answer)';
      setLastAnswer(answer);
      
      // Add assistant message
      appendMessage('assistant', escapeHtml(answer));

      // Check if fallback answer - auto-referral
      if (isFallbackAnswer(answer) || data?.is_fallback) {
        // Guard: avoid auto-referral for very short or vague questions
        const isVague = q.trim().length < 12 || /^\s*what\s+(is|are)\b/i.test(q.trim());
        if (isVague) {
          appendFeedbackButtons(q, answer);
        } else {
          try {
            const refFormData = new FormData();
            refFormData.append('reason', 'Auto-referral: bot could not confirm based on current guidance.');
            refFormData.append('question', q);
            refFormData.append('answer', answer);
            if (taskId) refFormData.append('task_id', taskId);

            const refRes = await fetch(`${BASE_URL}/api/sme/referral`, {
              method: 'POST',
              credentials: 'include',
              body: refFormData
            });

            if (refRes.ok) {
              const refData = await refRes.json();
              appendMessage('system', `<em>${refData?.message || 'Referral logged'} — you can view it under "My referrals".</em>`);
            }
          } catch (err) {
            console.warn('Auto-referral failed:', err);
          }
        }
      } else {
        // Show feedback buttons
        appendFeedbackButtons(q, answer);
      }

    } catch (err) {
      console.error(err);
      appendMessage('assistant', 'Error contacting the API.');
    } finally {
      setThinking(false);
    }
  };

  const appendFeedbackButtons = (q, answer) => {
    const feedbackId = Date.now() + Math.random();
    const feedbackMessage = {
      id: feedbackId,
      role: 'feedback',
      question: q,
      answer: answer,
      autoYesMs: autoYesMs,
      remaining: Math.max(0, Math.floor(autoYesMs / 1000))
    };
    setMessages(prev => [...prev, feedbackMessage]);
    
    // Auto-yes timer
    if (autoYesMs > 0) {
      const timer = setInterval(() => {
        setMessages(prev => prev.map(msg => {
          if (msg.id === feedbackId && msg.role === 'feedback') {
            const newRemaining = Math.max(0, (msg.remaining || 0) - 1);
            if (newRemaining <= 0) {
              clearInterval(timer);
              handleFeedback(true, feedbackId);
              return null;
            }
            return { ...msg, remaining: newRemaining };
          }
          return msg;
        }));
      }, 1000);
    }
  };

  const handleFeedback = async (helpful, feedbackId) => {
    if (!helpful) {
      // Show referral form
      setMessages(prev => prev.map(msg => 
        msg.id === feedbackId 
          ? { ...msg, showReferral: true }
          : msg
      ));
    } else {
      // Send positive feedback
      try {
        const formData = new FormData();
        formData.append('q', lastQuestion);
        formData.append('answer', lastAnswer);
        formData.append('helpful', 'true');
        
        await fetch(`${BASE_URL}/api/sme/feedback`, {
          method: 'POST',
          credentials: 'include',
          body: formData
        });
      } catch (err) {
        console.error('Feedback failed:', err);
      }
      
      // Remove feedback buttons
      setMessages(prev => prev.filter(msg => msg.id !== feedbackId));
    }
  };

  const handleReferral = async (feedbackId) => {
    const note = referralNotes[feedbackId] || 'User indicated the answer did not resolve the query.';
    try {
      const formData = new FormData();
      formData.append('reason', note);
      formData.append('question', lastQuestion);
      formData.append('answer', lastAnswer);
      if (taskId) formData.append('task_id', taskId);

      const res = await fetch(`${BASE_URL}/api/sme/referral`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        console.log('[AISME] Referral created:', data);
        appendMessage('system', `<em>✅ ${data?.message || 'Referral submitted'}.</em>`);
        setMessages(prev => prev.filter(msg => msg.id !== feedbackId));
        setReferralNotes(prev => {
          const newNotes = { ...prev };
          delete newNotes[feedbackId];
          return newNotes;
        });
      } else {
        const errorData = await res.json().catch(() => ({ error: 'Unknown error' }));
        console.error('[AISME] Referral failed:', errorData);
        appendMessage('system', `<em>❌ Failed to submit referral: ${errorData.error || 'Unknown error'}</em>`);
      }
    } catch (err) {
      console.error('Referral failed:', err);
      appendMessage('system', '<em>Failed to submit referral.</em>');
    }
  };

  const handleBackToTask = () => {
    const basePath = window.location.pathname.startsWith('/qc_review/') 
      ? `/qc_review/${taskId}`
      : `/view_task/${taskId}`;
    navigate(basePath);
  };

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, thinking]);

  return (
    <div className="aisme-container" style={{ paddingTop: '60px' }}>
      <div className="aisme-header">
        <div className="aisme-brand">
          <div className="aisme-logo">
            <i className="fas fa-brain"></i>
          </div>
          <div className="aisme-brand-text">
            <div className="aisme-brand-title">Scrutinise</div>
            <div className="aisme-brand-subtitle">Your SME</div>
          </div>
        </div>
        <div className="aisme-header-right">
          <div className={`aisme-health ${healthStatus === 'Online' ? 'ok' : 'err'}`}>
            SME Status: <span>{healthStatus}</span>
          </div>
          <button className="aisme-nav-link" onClick={handleBackToTask}>
            <i className="fas fa-arrow-left"></i> Back to Task
          </button>
        </div>
      </div>

      <div className="aisme-main">
        <div className="aisme-chat-box">
          <div 
            ref={chatWindowRef}
            className="aisme-chat-window"
          >
            {showWelcome && messages.length === 0 && (
              <div className="aisme-chat-overlay">
                <div className="aisme-welcome-content">
                  <div className="aisme-ready-indicator">
                    <i className="fas fa-check-circle"></i>
                    <span>I am trained on financial crime policies, procedures and guidance.</span>
                  </div>
                  <button 
                    className="aisme-start-chat-btn"
                    onClick={() => setShowWelcome(false)}
                  >
                    <span>Start Conversation</span>
                    <i className="fas fa-arrow-right"></i>
                  </button>
                </div>
              </div>
            )}

            {messages.map((msg) => {
              if (msg.role === 'user') {
                return (
                  <div key={msg.id} className="aisme-message aisme-message-user">
                    <div className="aisme-message-content">
                      <strong>You:</strong> <span dangerouslySetInnerHTML={{ __html: msg.html }} />
                    </div>
                  </div>
                );
              } else if (msg.role === 'assistant') {
                return (
                  <div key={msg.id} className="aisme-message aisme-message-assistant">
                    <div className="aisme-message-content">
                      <strong>{botName}:</strong> <span dangerouslySetInnerHTML={{ __html: msg.html }} />
                    </div>
                  </div>
                );
              } else if (msg.role === 'feedback') {
                return (
                  <div key={msg.id} className="aisme-message aisme-message-assistant">
                    <div className="aisme-message-content">
                      <div><strong>{botName}:</strong> <em>Did this answer your question?</em></div>
                      <div className="aisme-feedback-buttons">
                        <button 
                          className="aisme-btn aisme-btn-primary"
                          onClick={() => handleFeedback(true, msg.id)}
                        >
                          Yes
                        </button>
                        <button 
                          className="aisme-btn aisme-btn-ghost"
                          onClick={() => handleFeedback(false, msg.id)}
                        >
                          No
                        </button>
                        {msg.remaining > 0 && (
                          <span className="aisme-feedback-timer">
                            (auto "Yes" in {msg.remaining}s)
                          </span>
                        )}
                      </div>
                      {msg.showReferral && (
                        <div className="aisme-referral-form">
                          <div className="aisme-referral-note-label">Please add a short note for the referral:</div>
                          <textarea 
                            className="aisme-referral-textarea"
                            placeholder="Brief note to SMEs…"
                            rows={3}
                            value={referralNotes[msg.id] || ''}
                            onChange={(e) => setReferralNotes(prev => ({ ...prev, [msg.id]: e.target.value }))}
                          />
                          <div className="aisme-referral-actions">
                            <button 
                              className="aisme-btn aisme-btn-primary"
                              onClick={() => handleReferral(msg.id)}
                            >
                              Submit referral
                            </button>
                            <button 
                              className="aisme-btn aisme-btn-ghost"
                              onClick={() => setMessages(prev => prev.filter(m => m.id !== msg.id))}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              } else if (msg.role === 'system') {
                return (
                  <div key={msg.id} className="aisme-message aisme-message-system">
                    <div className="aisme-message-content" dangerouslySetInnerHTML={{ __html: msg.html }} />
                  </div>
                );
              }
              return null;
            })}

            {thinking && (
              <div className="aisme-message aisme-message-assistant aisme-thinking">
                <div className="aisme-message-content">
                  <strong>{botName}:</strong> <span className="aisme-dots">Thinking...</span>
                </div>
              </div>
            )}
          </div>

          {!showWelcome && (
            <form className="aisme-ask-form" onSubmit={handleSubmit}>
            <div className="aisme-form-row">
              <input
                type="text"
                id="aisme-q"
                className="aisme-input"
                placeholder="Ask about your organisation's policies, procedures, or escalation guidance..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={thinking}
              />
              <button 
                className={`aisme-send-btn ${question.trim() ? 'active' : ''}`}
                type="submit"
                disabled={thinking || !question.trim()}
                title="Send message"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          </form>
          )}

          {!showWelcome && (
            <div className="aisme-actions-bar">
              <div className="aisme-powered-by">
                <i className="fas fa-brain"></i>
                Powered by Scrutinise AI
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AISME;

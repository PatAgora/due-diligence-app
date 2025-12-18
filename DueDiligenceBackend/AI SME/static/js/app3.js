/* ===================================================================
   Scrutinise AI - Enhanced Chat Application JavaScript
   Professional enterprise-grade interactions and functionality
   =================================================================== */

(function() {
    'use strict';

    // Global state management
    window.ScrutiniseAI = {
        isTyping: false,
        lastQuestion: '',
        lastAnswer: '',
        messageCount: 0,
        
        // Configuration
        config: {
            typingDelay: 50,
            healthCheckInterval: 15000,
            autoHideOverlayDelay: 300,
            animationDuration: 300
        },
        
        // Utility functions
        utils: {
            debounce(func, wait) {
                let timeout;
                return function executedFunction(...args) {
                    const later = () => {
                        clearTimeout(timeout);
                        func(...args);
                    };
                    clearTimeout(timeout);
                    timeout = setTimeout(later, wait);
                };
            },
            
            escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            },
            
            formatTimestamp() {
                return new Date().toLocaleTimeString('en-US', {
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit'
                });
            },
            
            showNotification(message, type = 'info') {
                // Enhanced notification system
                const notification = document.createElement('div');
                notification.className = `notification notification-${type}`;
                notification.textContent = message;
                
                // Style the notification
                Object.assign(notification.style, {
                    position: 'fixed',
                    top: '20px',
                    right: '20px',
                    padding: '1rem 1.5rem',
                    borderRadius: '8px',
                    color: 'white',
                    fontWeight: '500',
                    zIndex: '1000',
                    transform: 'translateX(100%)',
                    transition: 'transform 0.3s ease',
                    backgroundColor: type === 'error' ? '#ef4444' : 
                                   type === 'success' ? '#22c55e' : '#ff6b35'
                });
                
                document.body.appendChild(notification);
                
                // Animate in
                requestAnimationFrame(() => {
                    notification.style.transform = 'translateX(0)';
                });
                
                // Auto remove
                setTimeout(() => {
                    notification.style.transform = 'translateX(100%)';
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.parentNode.removeChild(notification);
                        }
                    }, 300);
                }, 4000);
            }
        }
    };

    // DOM Ready handler
    function initializeApp() {
        console.log('🧠 Scrutinise AI Chat Interface Loading...');
        
        // Initialize all components
        initializeHealthCheck();
        initializeChatOverlay();
        initializeChatForm();
        initializeQuickActions();
        initializeKeyboardShortcuts();
        initializeAccessibility();
        
        console.log('✅ Scrutinise AI Chat Interface Ready');
    }

    // Health Check System
    function initializeHealthCheck() {
        const statusText = document.getElementById('status-text');
        const statusDot = document.getElementById('status-dot');
        const statusContainer = document.getElementById('sme-status');
        
        if (!statusText || !statusDot || !statusContainer) {
            console.warn('Health check elements not found');
            return;
        }

        async function checkSMEHealth() {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);
                
                const response = await fetch('/health', {
                    cache: 'no-store',
                    signal: controller.signal,
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                // SME is online
                updateHealthStatus(true);
                
            } catch (error) {
                console.warn('Health check failed:', error.message);
                updateHealthStatus(false);
            }
        }
        
        function updateHealthStatus(isOnline) {
            const statusClass = isOnline ? 'online' : 'offline';
            const statusMessage = isOnline ? 'SME Online' : 'SME Offline';
            
            statusText.textContent = statusMessage;
            statusDot.className = `status-dot ${statusClass}`;
            statusContainer.className = `status-indicator ${statusClass}`;
            
            // Update global state
            window.ScrutiniseAI.smeOnline = isOnline;
        }
        
        // Initial check and setup interval
        checkSMEHealth();
        setInterval(checkSMEHealth, window.ScrutiniseAI.config.healthCheckInterval);
    }

    // Chat Overlay Management
    function initializeChatOverlay() {
        const overlay = document.getElementById('chat-hero');
        const chatWindow = document.getElementById('chat-window');
        const inputField = document.getElementById('q');
        const startButton = document.getElementById('startChatBtn');
        
        if (!overlay) {
            console.warn('Chat overlay not found');
            return;
        }

        function hideOverlay() {
            if (!overlay.classList.contains('hidden')) {
                overlay.classList.add('hidden');
                
                // Focus input after overlay is hidden
                setTimeout(() => {
                    if (inputField && window.innerWidth > 768) {
                        inputField.focus();
                    }
                }, window.ScrutiniseAI.config.animationDuration);
                
                console.log('💬 Chat overlay hidden - user ready to interact');
            }
        }

        function showOverlay() {
            overlay.classList.remove('hidden');
            console.log('👁️ Chat overlay shown');
        }

        // Hide overlay on various user interactions
        overlay.addEventListener('click', hideOverlay);
        startButton?.addEventListener('click', hideOverlay);
        inputField?.addEventListener('focus', hideOverlay);
        
        // Hide when first message appears
        if (chatWindow) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        hideOverlay();
                    }
                });
            });
            
            observer.observe(chatWindow, { 
                childList: true, 
                subtree: true 
            });
        }
        
        // Expose methods globally for external use
        window.ScrutiniseAI.overlay = { hide: hideOverlay, show: showOverlay };
    }

    // Enhanced Chat Form
    function initializeChatForm() {
        const form = document.getElementById('ask-form');
        const input = document.getElementById('q');
        const sendButton = document.getElementById('sendBtn');
        const loadingOverlay = document.getElementById('loadingOverlay');
        const chatWindow = document.getElementById('chat-window');
        
        if (!form || !input || !sendButton) {
            console.warn('Chat form elements not found');
            return;
        }

        // Enhanced input interactions
        const debouncedInputHandler = window.ScrutiniseAI.utils.debounce((event) => {
            const hasText = event.target.value.trim().length > 0;
            sendButton.classList.toggle('active', hasText);
            
            // Update placeholder based on context
            if (hasText) {
                sendButton.title = 'Send message (Enter)';
            } else {
                sendButton.title = 'Type a message first';
            }
        }, 150);

        input.addEventListener('input', debouncedInputHandler);
        
        // Enhanced keyboard support
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (input.value.trim() && !window.ScrutiniseAI.isTyping) {
                    form.dispatchEvent(new Event('submit'));
                }
            }
        });
        
        // Form submission with enhanced UX
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            
            const question = input.value.trim();
            if (!question || window.ScrutiniseAI.isTyping) {
                return;
            }
            
            // Validate SME status
            if (!window.ScrutiniseAI.smeOnline) {
                window.ScrutiniseAI.utils.showNotification(
                    'SME is currently offline. Please try again later.', 
                    'error'
                );
                return;
            }
            
            console.log('📤 Submitting question:', question);
            
            // Store question for referrals
            window.ScrutiniseAI.lastQuestion = question;
            window.__lastQuestion = question; // Backward compatibility
            
            // Show user message immediately
            addMessageToChat('user', question);
            
            // Clear input and show loading state
            input.value = '';
            sendButton.classList.remove('active');
            setLoadingState(true);
            
            try {
                // Prepare form data
                const formData = new FormData();
                formData.append('q', question);
                
                // Submit to server
                const response = await fetch(form.action || window.location.pathname, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }
                
                // Handle response based on content type
                const contentType = response.headers.get('Content-Type') || '';
                
                if (contentType.includes('application/json')) {
                    const data = await response.json();
                    handleJsonResponse(data);
                } else {
                    // Assume HTML response with full page
                    const html = await response.text();
                    handleHtmlResponse(html);
                }
                
            } catch (error) {
                console.error('❌ Chat submission failed:', error);
                handleSubmissionError(error);
            } finally {
                setLoadingState(false);
            }
        });
        
        function addMessageToChat(type, content) {
            if (!chatWindow) return;
            
            const messageElement = document.createElement('div');
            messageElement.className = `message ${type}`;
            messageElement.innerHTML = `
                <div class="message-content">
                    ${window.ScrutiniseAI.utils.escapeHtml(content)}
                </div>
                <div class="message-time">${window.ScrutiniseAI.utils.formatTimestamp()}</div>
            `;
            
            chatWindow.appendChild(messageElement);
            chatWindow.scrollTop = chatWindow.scrollHeight;
            
            window.ScrutiniseAI.messageCount++;
            
            // Store last answer if it's from assistant
            if (type === 'assistant') {
                window.ScrutiniseAI.lastAnswer = content;
                window.__lastAnswer = content; // Backward compatibility
            }
        }
        
        function setLoadingState(isLoading) {
            window.ScrutiniseAI.isTyping = isLoading;
            
            if (loadingOverlay) {
                loadingOverlay.style.display = isLoading ? 'flex' : 'none';
            }
            
            input.disabled = isLoading;
            sendButton.disabled = isLoading;
            
            if (isLoading) {
                // Add typing indicator to chat
                const typingElement = document.createElement('div');
                typingElement.className = 'message assistant typing';
                typingElement.id = 'typing-indicator';
                typingElement.innerHTML = `
                    <div class="message-content">
                        <div class="typing-dots">
                            <span></span><span></span><span></span>
                        </div>
                    </div>
                `;
                
                if (chatWindow) {
                    chatWindow.appendChild(typingElement);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            } else {
                // Remove typing indicator
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) {
                    typingIndicator.remove();
                }
                
                // Re-focus input
                if (window.innerWidth > 768) {
                    setTimeout(() => input.focus(), 100);
                }
            }
        }
        
        function handleJsonResponse(data) {
            if (data.answer) {
                addMessageToChat('assistant', data.answer);
                
                // Handle retrieval hint
                const retrievalHint = document.getElementById('retrieval-hint');
                if (retrievalHint && data.retrieval_info) {
                    retrievalHint.textContent = data.retrieval_info;
                }
                
                console.log('✅ JSON response processed successfully');
            } else {
                throw new Error('No answer in response data');
            }
        }
        
        function handleHtmlResponse(html) {
            // Parse the HTML response to extract chat content
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Look for new chat content
            const newChatWindow = doc.getElementById('chat-window');
            if (newChatWindow && chatWindow) {
                // Replace chat content
                chatWindow.innerHTML = newChatWindow.innerHTML;
                chatWindow.scrollTop = chatWindow.scrollHeight;
                
                // Extract last answer for referrals
                const messages = chatWindow.querySelectorAll('.message.assistant');
                if (messages.length > 0) {
                    const lastMessage = messages[messages.length - 1];
                    const content = lastMessage.querySelector('.message-content');
                    if (content) {
                        window.ScrutiniseAI.lastAnswer = content.textContent.trim();
                        window.__lastAnswer = window.ScrutiniseAI.lastAnswer;
                    }
                }
                
                console.log('✅ HTML response processed successfully');
            } else {
                throw new Error('Could not find chat content in HTML response');
            }
        }
        
        function handleSubmissionError(error) {
            addMessageToChat('assistant', 
                'I apologise, but I encountered an error processing your request. Please try again or contact support if the problem persists.'
            );
            
            window.ScrutiniseAI.utils.showNotification(
                'Failed to send message. Please try again.', 
                'error'
            );
        }
        
        // Expose methods globally
        window.ScrutiniseAI.chat = {
            addMessage: addMessageToChat,
            setLoading: setLoadingState
        };
    }

    // Enhanced Referral Modal - DISABLED (automated by bot)
    /*function initializeReferralModal() {
        const modal = document.getElementById('referral-modal');
        const openButton = document.getElementById('raise-referral');
        const closeButton = document.getElementById('referral-close');
        const cancelButton = document.getElementById('referral-cancel');
        const form = document.getElementById('referral-form');
        const resultDiv = document.getElementById('referral-result');
        const questionPreview = document.getElementById('ref-q-preview');
        const answerPreview = document.getElementById('ref-a-preview');
        
        if (!modal || !openButton) {
            console.warn('Referral modal elements not found');
            return;
        }

        function openModal() {
            // Pre-populate with last interaction
            if (questionPreview) {
                questionPreview.value = window.ScrutiniseAI.lastQuestion || 
                                      window.__lastQuestion || '';
            }
            
            if (answerPreview) {
                answerPreview.value = window.ScrutiniseAI.lastAnswer || 
                                    window.__lastAnswer || '';
            }
            
            // Clear previous result
            if (resultDiv) {
                resultDiv.textContent = '';
                resultDiv.className = 'result-message';
            }
            
            // Show modal
            if (modal.showModal) {
                modal.showModal();
            } else {
                modal.setAttribute('open', 'open');
                modal.style.display = 'block';
            }
            
            // Focus first interactive element
            const firstInput = modal.querySelector('button, input, textarea, select');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 100);
            }
            
            console.log('📝 Referral modal opened');
        }
        
        function closeModal() {
            if (modal.close) {
                modal.close();
            } else {
                modal.removeAttribute('open');
                modal.style.display = 'none';
            }
            
            console.log('❌ Referral modal closed');
        }
        
        // Event listeners
        openButton.addEventListener('click', openModal);
        closeButton?.addEventListener('click', closeModal);
        cancelButton?.addEventListener('click', closeModal);
        
        // Close on backdrop click
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                closeModal();
            }
        });
        
        // Enhanced keyboard support
        modal.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
        
        // Form submission
        form?.addEventListener('submit', async (event) => {
            event.preventDefault();
            
            if (!resultDiv) return;
            
            resultDiv.textContent = 'Submitting referral...';
            resultDiv.className = 'result-message loading';
            
            try {
                const formData = new FormData();
                formData.append('reason', '');
                formData.append('question', window.ScrutiniseAI.lastQuestion || 
                                         window.__lastQuestion || '');
                formData.append('answer', window.ScrutiniseAI.lastAnswer || 
                                       window.__lastAnswer || '');
                
                const response = await fetch('/referral', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }
                
                const data = await response.json();
                
                resultDiv.textContent = data?.message || 'Referral submitted successfully';
                resultDiv.className = 'result-message success';
                
                // Auto-close after success
                setTimeout(() => {
                    closeModal();
                    window.ScrutiniseAI.utils.showNotification(
                        'Referral submitted successfully', 
                        'success'
                    );
                }, 1500);
                
                console.log('✅ Referral submitted successfully');
                
            } catch (error) {
                console.error('❌ Referral submission failed:', error);
                
                resultDiv.textContent = 'Failed to submit referral. Please try again.';
                resultDiv.className = 'result-message error';
            }
        });
        
        // Expose methods globally
        window.ScrutiniseAI.referral = {
            open: openModal,
            close: closeModal
        };
    }*/

    // Quick Actions System
    function initializeQuickActions() {
        const quickActionButtons = document.querySelectorAll('.quick-action');
        const inputField = document.getElementById('q');
        const form = document.getElementById('ask-form');
        
        if (quickActionButtons.length === 0) {
            console.log('ℹ️ No quick actions found (this is normal if side panel is disabled)');
            return;
        }

        quickActionButtons.forEach(button => {
            button.addEventListener('click', () => {
                const query = button.dataset.query;
                
                if (query && inputField) {
                    inputField.value = query;
                    inputField.dispatchEvent(new Event('input')); // Trigger input validation
                    
                    // Focus input for immediate editing
                    inputField.focus();
                    inputField.setSelectionRange(query.length, query.length);
                    
                    // Optional: Auto-submit after delay
                    if (button.dataset.autoSubmit === 'true') {
                        setTimeout(() => {
                            if (form && !window.ScrutiniseAI.isTyping) {
                                form.dispatchEvent(new Event('submit'));
                            }
                        }, 500);
                    }
                    
                    console.log('🚀 Quick action triggered:', query);
                }
            });
        });
    }

    // Keyboard Shortcuts
    function initializeKeyboardShortcuts() {
        document.addEventListener('keydown', (event) => {
            // Ctrl/Cmd + Enter: Submit form
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                const form = document.getElementById('ask-form');
                if (form && !window.ScrutiniseAI.isTyping) {
                    event.preventDefault();
                    form.dispatchEvent(new Event('submit'));
                }
            }
            
            // Ctrl/Cmd + R: Disabled (referrals automated)
            
            // Ctrl/Cmd + K: Focus input
            if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
                const input = document.getElementById('q');
                if (input) {
                    event.preventDefault();
                    input.focus();
                    input.select();
                }
            }
        });
        
        console.log('⌨️ Keyboard shortcuts initialised');
    }

    // Accessibility Enhancements
    function initializeAccessibility() {
        // Announce page changes to screen readers
        const announcer = document.createElement('div');
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.className = 'sr-only';
        announcer.style.cssText = `
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        `;
        document.body.appendChild(announcer);
        
        // Skip link
        const skipLink = document.createElement('a');
        skipLink.href = '#chat-window';
        skipLink.textContent = 'Skip to chat';
        skipLink.className = 'skip-link';
        skipLink.style.cssText = `
            position: absolute;
            top: -40px;
            left: 6px;
            background: var(--brand-orange);
            color: white;
            padding: 8px;
            border-radius: 4px;
            text-decoration: none;
            z-index: 1000;
            transition: top 0.3s;
        `;
        
        skipLink.addEventListener('focus', () => {
            skipLink.style.top = '6px';
        });
        
        skipLink.addEventListener('blur', () => {
            skipLink.style.top = '-40px';
        });
        
        document.body.insertBefore(skipLink, document.body.firstChild);
        
        // Enhanced focus management
        const focusableElements = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
        
        // Trap focus in modal
        document.addEventListener('keydown', (event) => {
            const modal = document.querySelector('dialog[open]');
            if (modal && event.key === 'Tab') {
                const focusables = Array.from(modal.querySelectorAll(focusableElements));
                const firstFocusable = focusables[0];
                const lastFocusable = focusables[focusables.length - 1];
                
                if (event.shiftKey) {
                    if (document.activeElement === firstFocusable) {
                        event.preventDefault();
                        lastFocusable.focus();
                    }
                } else {
                    if (document.activeElement === lastFocusable) {
                        event.preventDefault();
                        firstFocusable.focus();
                    }
                }
            }
        });
        
        // Expose announcer globally
        window.ScrutiniseAI.announcer = announcer;
        
        console.log('♿ Accessibility enhancements initialised');
    }

    // Error boundary
    window.addEventListener('error', (event) => {
        console.error('💥 JavaScript Error:', event.error);
        
        // Try to show user-friendly error message
        if (window.ScrutiniseAI?.utils?.showNotification) {
            window.ScrutiniseAI.utils.showNotification(
                'An unexpected error occurred. Please refresh the page.', 
                'error'
            );
        }
    });

    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (event) => {
        console.error('💥 Unhandled Promise Rejection:', event.reason);
        
        if (window.ScrutiniseAI?.utils?.showNotification) {
            window.ScrutiniseAI.utils.showNotification(
                'A network error occurred. Please check your connection.', 
                'error'
            );
        }
    });

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeApp);
    } else {
        initializeApp();
    }

    // Performance monitoring
    window.addEventListener('load', () => {
        // Basic performance metrics
        if ('performance' in window && 'getEntriesByType' in performance) {
            const navTiming = performance.getEntriesByType('navigation')[0];
            if (navTiming) {
                console.log(`⚡ Page loaded in ${Math.round(navTiming.loadEventEnd - navTiming.fetchStart)}ms`);
            }
        }
    });

})();
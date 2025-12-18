// ===== SCRUTINISE AI LOGIN PAGE FUNCTIONALITY =====

class ScrutiniseLogin {
    constructor() {
        this.form = document.getElementById('loginForm');
        this.passwordToggle = document.getElementById('passwordToggle');
        this.passwordInput = document.getElementById('password');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.aiAvatar = document.getElementById('aiAvatar');
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.initAIAvatar();
        this.initFormValidation();
        this.initAnimations();
    }
    
    bindEvents() {
        // Form submission
        this.form.addEventListener('submit', this.handleFormSubmit.bind(this));
        
        // Password toggle
        this.passwordToggle.addEventListener('click', this.togglePassword.bind(this));
        
        // Input focus effects
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('focus', this.handleInputFocus.bind(this));
            input.addEventListener('blur', this.handleInputBlur.bind(this));
            input.addEventListener('input', this.handleInputChange.bind(this));
        });
        
        // Social login buttons removed - app requires specific access
        
        // Keyboard accessibility
        document.addEventListener('keydown', this.handleKeydown.bind(this));
    }
    
    initAIAvatar() {
        // AI brain is now integrated in HTML/CSS
        const avatar = this.aiAvatar;
        
        // Add hover effect for enhanced interaction
        avatar.addEventListener('mouseenter', this.animateAvatar.bind(this));
        
        // Add additional neural activity on interaction
        avatar.addEventListener('click', this.triggerNeuralBurst.bind(this));
    }
    
    animateAvatar() {
        const avatar = this.aiAvatar;
        avatar.style.transform = 'scale(1.05)';
        setTimeout(() => {
            avatar.style.transform = 'scale(1)';
        }, 300);
    }
    
    triggerNeuralBurst() {
        const avatar = this.aiAvatar;
        const neuralNodes = document.querySelectorAll('.neural-node');
        
        // Add pulse effect to brain icon
        avatar.classList.add('pulse-active');
        setTimeout(() => {
            avatar.classList.remove('pulse-active');
        }, 800);
        
        // Trigger neural activity
        neuralNodes.forEach((node, index) => {
            node.style.animation = 'none';
            setTimeout(() => {
                node.style.animation = `brainPulse 0.8s ease-in-out`;
            }, index * 100);
        });
    }
    
    initFormValidation() {
        const emailInput = document.getElementById('email');
        const passwordInput = document.getElementById('password');
        
        // Real-time validation
        emailInput.addEventListener('input', () => {
            this.validateEmail(emailInput);
        });
        
        passwordInput.addEventListener('input', () => {
            this.validatePassword(passwordInput);
        });
    }
    
    validateEmail(input) {
        const email = input.value;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const isValid = email.length === 0 || emailRegex.test(email); // Allow empty for backend validation
        
        this.updateInputState(input, isValid, email.length > 0);
        return email.length > 0 && isValid; // Must have content and be valid for form submission
    }
    
    validatePassword(input) {
        const password = input.value;
        const isValid = password.length === 0 || password.length >= 3; // Allow empty, minimum 3 chars when present
        
        this.updateInputState(input, isValid, password.length > 0);
        return password.length > 0; // Just need content for form submission
    }
    
    updateInputState(input, isValid, hasContent) {
        const wrapper = input.parentElement;
        
        // Remove existing classes
        wrapper.classList.remove('valid', 'invalid', 'has-content');
        
        if (hasContent) {
            wrapper.classList.add('has-content');
            
            if (isValid) {
                wrapper.classList.add('valid');
            } else {
                wrapper.classList.add('invalid');
            }
        }
    }
    
    handleFormSubmit(e) {
        // Validate form before submission
        const isEmailValid = this.validateEmail(document.getElementById('email'));
        const isPasswordValid = this.validatePassword(document.getElementById('password'));
        
        if (!isEmailValid || !isPasswordValid) {
            e.preventDefault();
            this.showError('Please check your email and password');
            return false;
        }
        
        // Show loading state for visual feedback
        this.showLoading();
        
        // Allow form to submit normally to Flask backend
        // The loading overlay will be hidden when the new page loads
        return true;
    }
    

    
    togglePassword() {
        const type = this.passwordInput.type === 'password' ? 'text' : 'password';
        this.passwordInput.type = type;
        
        const icon = this.passwordToggle.querySelector('i');
        icon.className = type === 'password' ? 'fas fa-eye' : 'fas fa-eye-slash';
    }
    
    handleInputFocus(e) {
        const wrapper = e.target.parentElement;
        wrapper.classList.add('focused');
    }
    
    handleInputBlur(e) {
        const wrapper = e.target.parentElement;
        wrapper.classList.remove('focused');
    }
    
    handleInputChange(e) {
        const input = e.target;
        const wrapper = input.parentElement;
        
        if (input.value.length > 0) {
            wrapper.classList.add('has-content');
        } else {
            wrapper.classList.remove('has-content', 'valid', 'invalid');
        }
    }
    

    
    handleKeydown(e) {
        // Enter key on form elements
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
            e.preventDefault();
            this.form.dispatchEvent(new Event('submit'));
        }
        
        // Escape key to close any modals or overlays
        if (e.key === 'Escape') {
            this.hideLoading();
        }
    }
    
    showLoading() {
        this.loadingOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    hideLoading() {
        this.loadingOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    showSuccess() {
        this.hideLoading();
        
        // Create success message
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.innerHTML = `
            <div class="success-content">
                <i class="fas fa-check-circle"></i>
                <h3>Welcome Back!</h3>
                <p>Redirecting to your dashboard...</p>
            </div>
        `;
        
        document.body.appendChild(successDiv);
        
        // Animate in
        setTimeout(() => {
            successDiv.classList.add('show');
        }, 100);
        
        // Remove after redirect
        setTimeout(() => {
            successDiv.remove();
        }, 3000);
    }
    
    showError(message) {
        // Create error message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <div class="error-content">
                <i class="fas fa-exclamation-circle"></i>
                <p>${message}</p>
            </div>
        `;
        
        document.body.appendChild(errorDiv);
        
        // Animate in
        setTimeout(() => {
            errorDiv.classList.add('show');
        }, 100);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            errorDiv.classList.remove('show');
            setTimeout(() => {
                errorDiv.remove();
            }, 300);
        }, 4000);
    }
    
    initAnimations() {
        // Intersection Observer for fade-in animations
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -100px 0px'
        };
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-in');
                }
            });
        }, observerOptions);
        
        // Observe elements for animation
        document.querySelectorAll('.feature-item, .form-group, .security-item').forEach(el => {
            observer.observe(el);
        });
    }
}

// ===== ADDITIONAL STYLES FOR DYNAMIC ELEMENTS =====
const additionalStyles = `
    /* Enhanced Brain Icon Interactions */
    .ai-avatar:hover::before {
        transform: translate(-50%, -50%) scale(1.1);
        transition: all 0.3s ease-in-out;
        color: #2d2d2d;
    }
    
    .ai-avatar:hover::after {
        animation-duration: 1s;
        opacity: 0.8 !important;
    }
    
    .ai-avatar:hover .neural-node {
        animation-duration: 1s;
    }
    
    /* AI Avatar Click Effect */
    .ai-avatar:active {
        transform: scale(0.95);
    }
    
    /* Brain pulse effect on interaction */
    .ai-avatar.pulse-active::after {
        animation: brainPulseActive 0.8s ease-in-out;
    }
    
    @keyframes brainPulseActive {
        0% { opacity: 0; transform: translate(-50%, -50%) scale(1); }
        50% { opacity: 1; transform: translate(-50%, -50%) scale(1.2); }
        100% { opacity: 0; transform: translate(-50%, -50%) scale(1); }
    }
    
    /* Input States */
    .input-wrapper.focused {
        transform: translateY(-2px);
    }
    
    .input-wrapper.valid input {
        border-color: var(--success);
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
    }
    
    .input-wrapper.invalid input {
        border-color: var(--error);
        box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
    }
    
    /* Success Message */
    .success-message {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease-in-out;
    }
    
    .success-message.show {
        opacity: 1;
        visibility: visible;
    }
    
    .success-content {
        text-align: center;
        padding: 40px;
        background: var(--white);
        border-radius: 16px;
        box-shadow: var(--shadow-xl);
        transform: translateY(20px);
        transition: transform 0.3s ease-in-out;
    }
    
    .success-message.show .success-content {
        transform: translateY(0);
    }
    
    .success-content i {
        font-size: 3rem;
        color: var(--success);
        margin-bottom: 16px;
    }
    
    .success-content h3 {
        font-size: 1.5rem;
        color: var(--primary-black);
        margin-bottom: 8px;
    }
    
    .success-content p {
        color: var(--text-light);
    }
    
    /* Error Message */
    .error-message {
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 2000;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease-in-out;
    }
    
    .error-message.show {
        opacity: 1;
        visibility: visible;
        transform: translateX(-50%) translateY(0);
    }
    
    .error-content {
        background: var(--error);
        color: var(--white);
        padding: 16px 24px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: var(--shadow-lg);
        max-width: 400px;
    }
    
    .error-content i {
        font-size: 1.2rem;
    }
    
    /* Animation Classes */
    .animate-in {
        animation: fadeInUp 0.6s ease-out forwards;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ScrutiniseLogin();
});

// ===== UTILITY FUNCTIONS =====

// Theme switcher (for future use)
const ThemeSwitcher = {
    init() {
        const savedTheme = localStorage.getItem('scrutinise-theme') || 'light';
        this.setTheme(savedTheme);
    },
    
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('scrutinise-theme', theme);
    },
    
    toggle() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }
};

// Accessibility helpers
const AccessibilityHelpers = {
    init() {
        this.addKeyboardNavigation();
        this.addAriaLabels();
        this.addFocusIndicators();
    },
    
    addKeyboardNavigation() {
        // Add tab index for custom elements
        document.querySelectorAll('.social-btn, .password-toggle').forEach(el => {
            if (!el.hasAttribute('tabindex')) {
                el.setAttribute('tabindex', '0');
            }
        });
    },
    
    addAriaLabels() {
        // Add ARIA labels for screen readers
        const passwordToggle = document.getElementById('passwordToggle');
        if (passwordToggle) {
            passwordToggle.setAttribute('aria-label', 'Toggle password visibility');
        }
        
        const aiAvatar = document.getElementById('aiAvatar');
        if (aiAvatar) {
            aiAvatar.setAttribute('aria-label', 'Scrutinise AI Assistant Avatar');
        }
    },
    
    addFocusIndicators() {
        // Ensure focus is visible for keyboard users
        const focusableElements = document.querySelectorAll(
            'button, input, a, .social-btn, .password-toggle'
        );
        
        focusableElements.forEach(el => {
            el.addEventListener('focus', function() {
                this.classList.add('keyboard-focus');
            });
            
            el.addEventListener('blur', function() {
                this.classList.remove('keyboard-focus');
            });
        });
    }
};

// Initialize accessibility helpers
document.addEventListener('DOMContentLoaded', () => {
    AccessibilityHelpers.init();
    ThemeSwitcher.init();
});
// API service for communicating with Flask backend

// IMPORTANT: Always use empty string to force relative URLs (which use Vite proxy)
// Never use http://localhost:5050 as it will fail from HTTPS pages (mixed content)
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : '';

// Helper function to get CSRF token from cookies
function getCSRFToken() {
  const name = 'csrf_token=';
  const decodedCookie = decodeURIComponent(document.cookie);
  const ca = decodedCookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) === 0) {
      return c.substring(name.length, c.length);
    }
  }
  return '';
}

// Helper function to make API requests
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultOptions = {
    credentials: 'include', // Include cookies for session management
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  };

  // Add CSRF token if available
  const csrfToken = getCSRFToken();
  if (csrfToken) {
    defaultOptions.headers['X-CSRFToken'] = csrfToken;
  }

  const response = await fetch(url, { ...defaultOptions, ...options });
  
  // Handle redirects (Flask might redirect on auth failure)
  if (response.redirected && response.url.includes('/login')) {
    throw new Error('Unauthorized');
  }

  return response;
}

// Auth API
export const authAPI = {
  login: async (email, password) => {
    // Flask login expects form data, not JSON
    const formData = new URLSearchParams();
    formData.append('email', email);
    formData.append('password', password);

    let response;
    try {
      console.log('[LOGIN] Attempting fetch to:', `${API_BASE_URL}/login`);
      console.log('[LOGIN] API_BASE_URL value:', API_BASE_URL);
      response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
        },
        body: formData.toString(),
      });
      console.log('[LOGIN] Fetch successful, status:', response.status);
    } catch (networkError) {
      console.error('[LOGIN] Network error during login:', networkError);
      console.error('[LOGIN] Error type:', networkError.name);
      console.error('[LOGIN] Error message:', networkError.message);
      console.error('[LOGIN] Error stack:', networkError.stack);
      throw networkError; // Throw original error to see actual message
    }

    let data;
    try {
      data = await response.json();
    } catch (parseError) {
      console.error('Error parsing login response:', parseError);
      throw new Error('Server returned invalid response. Please try again.');
    }
    
    if (response.ok) {
      // Check if 2FA is required
      if (data.requires_2fa) {
        return { requires_2fa: true, message: data.message || '2FA code sent to your email' };
      }
      
      if (data.success && data.user) {
        return { user: data.user, token: 'session-based' };
      }
      
      // Fallback: get user info from session
      const userResponse = await fetch(`${API_BASE_URL}/api/user`, {
        credentials: 'include',
      });
      
      if (userResponse.ok) {
        const userData = await userResponse.json();
        return { user: userData, token: 'session-based' };
      }
      
      // Last fallback
      return { user: { email }, token: 'session-based' };
    }

    // Error response
    throw new Error(data.error || 'Invalid email or password');
  },

  logout: async () => {
    await fetch(`${API_BASE_URL}/logout`, {
      method: 'GET',
      credentials: 'include',
    });
  },

  getCurrentUser: async () => {
    const response = await fetch(`${API_BASE_URL}/api/user`, {
      credentials: 'include',
    });
    
    if (response.ok) {
      return await response.json();
    }
    return null;
  },

  verify2FA: async (code) => {
    const formData = new URLSearchParams();
    formData.append('code', code);

    const response = await fetch(`${API_BASE_URL}/verify_2fa`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
      },
      body: formData.toString(),
    });

    const data = await response.json();
    
    if (response.ok && data.success && data.user) {
      return { user: data.user, token: 'session-based' };
    }

    throw new Error(data.error || 'Invalid or expired code');
  },
};

// Reviewer Dashboard API
export const reviewerAPI = {
  getDashboard: async (dateRange = 'all') => {
    const url = `/api/reviewer_dashboard?date_range=${dateRange}`;
    console.log('[DEBUG] Calling reviewer dashboard API:', url);
    const response = await apiRequest(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    console.log('[DEBUG] Response status:', response.status, 'URL:', response.url);
    console.log('[DEBUG] Content-Type:', response.headers.get('content-type'));

    if (response.ok) {
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      // If we got HTML instead of JSON, log the response
      const text = await response.text();
      console.error('[ERROR] Expected JSON but got HTML. Response preview:', text.substring(0, 200));
      throw new Error('Dashboard endpoint returned HTML instead of JSON. Check server logs.');
    }
    
    // Handle error responses
    if (response.status === 403) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'Access denied');
    }
    
    const errorText = await response.text().catch(() => 'Failed to fetch dashboard data');
    throw new Error(errorText);
  },

  getMyTasks: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.append('status', filters.status);
    if (filters.date) params.append('date', filters.date);
    if (filters.date_range) params.append('date_range', filters.date_range);
    if (filters.age_bucket) params.append('age_bucket', filters.age_bucket);

    const response = await apiRequest(`/api/my_tasks?${params.toString()}`, {
      method: 'GET',
    });

    if (response.ok) {
      return await response.json();
    }
    
    if (response.status === 403) {
      throw new Error('Access denied');
    }
    
    throw new Error('Failed to fetch tasks');
  },
};

// Review API
export const reviewAPI = {
  getTask: async (taskId) => {
    const response = await apiRequest(`/view_task/${taskId}`, {
      method: 'GET',
    });

    if (response.ok) {
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      throw new Error('View task endpoint needs JSON API');
    }
    
    throw new Error('Failed to fetch task');
  },

  saveReview: async (taskId, fields) => {
    const response = await apiRequest(`/api/reviews/${taskId}/save`, {
      method: 'POST',
      body: JSON.stringify({ fields }),
    });

    if (response.ok) {
      return await response.json();
    }
    
    const error = await response.json().catch(() => ({ error: 'Failed to save review' }));
    throw new Error(error.error || 'Failed to save review');
  },

  saveDecision: async (taskId, outcome, financialCrimeReason, caseSummary) => {
    const response = await apiRequest(`/api/decision/${taskId}/save`, {
      method: 'POST',
      body: JSON.stringify({
        outcome,
        financial_crime_reason: financialCrimeReason,
        case_summary: caseSummary,
      }),
    });

    if (response.ok) {
      return await response.json();
    }
    
    const error = await response.json().catch(() => ({ error: 'Failed to save decision' }));
    throw new Error(error.error || 'Failed to save decision');
  },
};

export default {
  auth: authAPI,
  reviewer: reviewerAPI,
  review: reviewAPI,
};



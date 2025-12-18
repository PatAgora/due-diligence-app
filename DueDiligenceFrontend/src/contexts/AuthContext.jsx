import { createContext, useContext, useState, useEffect, useRef } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const justLoggedInRef = useRef(false);

  useEffect(() => {
    // Check for stored auth data and verify session (only on initial mount)
    const checkAuth = async () => {
      // Skip check if we just logged in (avoid race condition)
      if (justLoggedInRef.current) {
        setLoading(false);
        return;
      }

      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        try {
          // Verify session is still valid
          const currentUser = await authAPI.getCurrentUser();
          if (currentUser && currentUser.id) {
            setUser(currentUser);
            setToken('session-based');
            localStorage.setItem('user', JSON.stringify(currentUser));
          } else {
            // Session expired or invalid, clear storage
            localStorage.removeItem('user');
            localStorage.removeItem('token');
            setUser(null);
            setToken(null);
          }
        } catch (err) {
          // Network error or other issue - keep stored user for now
          // The backend will handle auth on protected routes
          console.warn('Auth check error:', err);
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, []); // Only run on mount

  const login = (userData, authToken) => {
    // Set flag to prevent checkAuth from interfering
    justLoggedInRef.current = true;
    
    // Set user state immediately
    setUser(userData);
    setToken(authToken);
    setLoading(false); // Set loading to false immediately so PrivateRoute doesn't block
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('token', authToken);
    
    // Clear the flag after navigation completes
    setTimeout(() => {
      justLoggedInRef.current = false;
    }, 2000);
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem('user');
      localStorage.removeItem('token');
      // Clear all dashboard filter preferences on logout
      localStorage.removeItem('ops_dashboard_dateRange');
      localStorage.removeItem('ops_dashboard_team');
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}


import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined ? import.meta.env.VITE_API_BASE_URL : '';

const PermissionsContext = createContext();

export function PermissionsProvider({ children }) {
  const { user } = useAuth();
  const [permissions, setPermissions] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      fetchPermissions();
    } else {
      setLoading(false);
    }
  }, [user]);

  const fetchPermissions = async () => {
    try {
      // Fetch current user's permissions (not all permissions)
      const response = await fetch(`${BASE_URL}/api/user/permissions`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.permissions) {
          // Store permissions as a map: feature -> {can_view, can_edit}
          setPermissions(data.permissions);
        }
      } else if (response.status === 401 || response.status === 500) {
        // User not authenticated or server error - use default permissions (all allowed)
        console.log('[Permissions] Could not fetch permissions - using defaults');
        setPermissions({});
      }
    } catch (error) {
      console.error('Error fetching permissions:', error);
      // Default to allowing all if permissions can't be loaded
      setPermissions({});
    } finally {
      setLoading(false);
    }
  };

  const hasPermission = (feature, action = 'view') => {
    if (!user || !user.role) return true; // Default to allow if no user/role
    
    // Admin always has full access - cannot be restricted
    if (user.role === 'admin' || user.role === 'admin@scrutinise.co.uk') {
      return true;
    }
    
    const perm = permissions[feature];
    
    // If no permission entry exists, default to allow (backward compatibility)
    if (!perm) return true;
    
    if (action === 'view') {
      return perm.can_view;
    } else if (action === 'edit') {
      return perm.can_edit;
    }
    
    return false;
  };

  const canView = (feature) => hasPermission(feature, 'view');
  const canEdit = (feature) => hasPermission(feature, 'edit');

  return (
    <PermissionsContext.Provider 
      value={{ 
        permissions, 
        loading, 
        hasPermission, 
        canView, 
        canEdit,
        refreshPermissions: fetchPermissions 
      }}
    >
      {children}
    </PermissionsContext.Provider>
  );
}

export function usePermissions() {
  const context = useContext(PermissionsContext);
  if (!context) {
    // Return safe defaults if context not available
    return {
      permissions: {},
      loading: false,
      hasPermission: () => true,
      canView: () => true,
      canEdit: () => true,
      refreshPermissions: () => {}
    };
  }
  return context;
}

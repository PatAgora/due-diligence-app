import React, { createContext, useContext, useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

const ModuleSettingsContext = createContext();

export function ModuleSettingsProvider({ children }) {
  const [settings, setSettings] = useState({
    due_diligence: true,
    transaction_review: true,
    ai_sme: true
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await fetch(`${BASE_URL}/api/admin/module_settings`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.settings) {
          setSettings(data.settings);
        }
      }
    } catch (error) {
      console.error('Error fetching module settings:', error);
      // Default to all enabled on error
    } finally {
      setLoading(false);
    }
  };

  const isModuleEnabled = (moduleName) => {
    return settings[moduleName] !== false; // Default to true if not set
  };

  return (
    <ModuleSettingsContext.Provider value={{ settings, loading, isModuleEnabled, refreshSettings: fetchSettings }}>
      {children}
    </ModuleSettingsContext.Provider>
  );
}

export function useModuleSettings() {
  const context = useContext(ModuleSettingsContext);
  if (!context) {
    // Return default values if context not available
    return {
      settings: { due_diligence: true, transaction_review: true, ai_sme: true },
      loading: false,
      isModuleEnabled: () => true,
      refreshSettings: () => {}
    };
  }
  return context;
}


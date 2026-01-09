import React, { createContext, useContext, useState, useEffect } from 'react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const FieldVisibilityContext = createContext();

export const useFieldVisibility = () => {
  const context = useContext(FieldVisibilityContext);
  if (!context) {
    throw new Error('useFieldVisibility must be used within FieldVisibilityProvider');
  }
  return context;
};

export const FieldVisibilityProvider = ({ children }) => {
  const [fieldVisibility, setFieldVisibility] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFieldVisibility();
  }, []);

  const fetchFieldVisibility = async () => {
    try {
      const response = await fetch(`${BASE_URL}/api/admin/field_visibility`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          // Convert visibility object - ensure all fields are included
          const visibility = {};
          
          // First, initialize all fields from all_fields list to true (default visible)
          if (data.all_fields) {
            data.all_fields.forEach(field => {
              visibility[field] = true; // Default to visible
            });
          }
          
          // Then override with actual visibility settings from database
          Object.entries(data.visibility || {}).forEach(([field, isVisible]) => {
            visibility[field] = isVisible === true || isVisible === 1;
          });
          
          setFieldVisibility(visibility);
        }
      } else if (response.status === 401) {
        // User doesn't have admin permissions - use default visibility (all visible)
        console.log('[FieldVisibility] User not authorized for admin endpoint - using defaults');
        setFieldVisibility({});
      }
    } catch (error) {
      console.error('Error fetching field visibility:', error);
      // On error, default to all fields visible
      setFieldVisibility({});
    } finally {
      setLoading(false);
    }
  };

  // Check if a field is visible
  // This handles both direct field names and mapped field names
  const isFieldVisible = (fieldName) => {
    if (loading) return true; // Show all fields while loading
    
    // If no visibility settings, show all fields
    if (Object.keys(fieldVisibility).length === 0) return true;
    
    // Direct check
    if (fieldVisibility.hasOwnProperty(fieldName)) {
      // Explicitly check for true/1, default to false if not explicitly true
      return fieldVisibility[fieldName] === true || fieldVisibility[fieldName] === 1;
    }
    
    // Check mapped field names
    const mappedField = getMappedFieldName(fieldName);
    if (mappedField) {
      if (fieldVisibility.hasOwnProperty(mappedField)) {
        // Explicitly check for true/1, default to false if not explicitly true
        return fieldVisibility[mappedField] === true || fieldVisibility[mappedField] === 1;
      }
      // If mapping exists but field not in settings, default to false (hidden)
      return false;
    }
    
    // If no mapping found and field not in settings, default to visible (for backward compatibility)
    return true;
  };

  // Map database field names to admin field names
  const getMappedFieldName = (dbFieldName) => {
    // Handle original/enriched suffixes
    const baseField = dbFieldName
      .replace(/_original$/, '')
      .replace(/_enriched$/, '');
    
    // Map common field name patterns to admin field names
    // This maps the actual database field names to the field names used in admin settings
    
    // Entity fields - check specific fields first to avoid false matches
    if (baseField === 'entity_trading_name' || baseField.startsWith('entity_trading_name_')) {
      return 'entity_name';
    }
    if (baseField === 'entity_incorp_date' || baseField.startsWith('entity_incorp_date_')) {
      return 'entity_registration_number';
    }
    if (baseField === 'entity_status' || baseField.startsWith('entity_status_')) {
      return 'entity_type';
    }
    // Then check general entity fields
    if (baseField === 'entity_name' || baseField.startsWith('entity_name_')) {
      return 'entity_name';
    }
    if (baseField === 'entity_type' || baseField.startsWith('entity_type_')) {
      return 'entity_type';
    }
    if (baseField === 'entity_registration_number' || baseField.startsWith('entity_registration_number_')) {
      return 'entity_registration_number';
    }
    if (baseField === 'entity_country_of_incorporation' || baseField.startsWith('entity_country_of_incorporation_')) {
      return 'entity_country_of_incorporation';
    }
    if (baseField === 'entity_industry' || baseField.startsWith('entity_industry_')) {
      return 'entity_industry';
    }
    
    // Address fields - check for address-related fields but exclude entity fields
    if ((baseField.includes('address') || baseField.includes('city') || baseField.includes('postcode')) 
        && !baseField.startsWith('entity_') && !baseField.startsWith('lp1_')) {
      return 'address';
    }
    // Country field (but not entity_country_of_incorporation which is handled above)
    if (baseField === 'country' || (baseField.includes('country') && !baseField.startsWith('entity_') && !baseField.startsWith('payer_') && !baseField.startsWith('beneficiary_'))) {
      return 'address';
    }
    
    // Contact fields
    if (baseField === 'primary_phone' || baseField.includes('phone')) {
      return 'customer_contact_numbers';
    }
    if (baseField === 'primary_email' || baseField.includes('email')) {
      return 'customer_email_address';
    }
    
    // Linked party fields
    if (baseField.startsWith('lp1_')) {
      return 'entity_related_persons';
    }
    
    // Direct mappings
    const directMappings = {
      // Watchlist fields
      'watchlist_name': 'watchlist_name',
      'watchlist_dob': 'watchlist_dob',
      'watchlist_nationality': 'watchlist_nationality',
      'watchlist_address': 'watchlist_address',
      'watchlist_document_type': 'watchlist_document_type',
      'watchlist_id_number': 'watchlist_id_number',
      'watchlist_contact_numbers': 'watchlist_contact_numbers',
      'watchlist_email_address': 'watchlist_email_address',
      
      // Individual customer fields
      'first_name': 'first_name',
      'middle_name': 'middle_name',
      'last_name': 'last_name',
      'dob': 'dob',
      'nationality': 'nationality',
      'customer_gender': 'customer_gender',
      'customer_nationalities': 'customer_nationalities',
      'customer_contact_numbers': 'customer_contact_numbers',
      'customer_email_address': 'customer_email_address',
      'document_type': 'document_type',
      'id_number': 'id_number',
      
      // Payment fields
      'payment_reference': 'payment_reference',
      'payment_date': 'payment_date',
      'payment_amount': 'payment_amount',
      'payment_currency': 'payment_currency',
      'payer_name': 'payer_name',
      'payer_country': 'payer_country',
      'beneficiary_name': 'beneficiary_name',
      'beneficiary_country': 'beneficiary_country',
      'payment_purpose': 'payment_purpose',
      'payment_channel': 'payment_channel',
      
      // Outcome fields
      'match_type': 'match_type',
      'match_probability': 'match_probability',
      'match_reasons': 'match_reasons',
      'match_explanation': 'match_explanation',
      'screening_rationale': 'screening_rationale',
    };
    
    return directMappings[baseField] || null;
  };

  const value = {
    fieldVisibility,
    loading,
    isFieldVisible,
    refresh: fetchFieldVisibility
  };

  return (
    <FieldVisibilityContext.Provider value={value}>
      {children}
    </FieldVisibilityContext.Provider>
  );
};


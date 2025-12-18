import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AdminFieldVisibility() {
  const { user } = useAuth();
  const [allFields, setAllFields] = useState([]);
  const [visibleFields, setVisibleFields] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const fieldGroups = [
    {
      title: '🔍 Watchlist Fields',
      fields: [
        'watchlist_name', 'watchlist_dob', 'watchlist_nationality',
        'watchlist_address', 'watchlist_document_type', 'watchlist_id_number',
        'watchlist_contact_numbers', 'watchlist_email_address'
      ]
    },
    {
      title: '👤 Individual Customer Fields',
      fields: [
        'first_name', 'middle_name', 'last_name', 'dob', 'nationality',
        'customer_gender', 'customer_nationalities', 'customer_contact_numbers',
        'customer_email_address', 'document_type', 'id_number', 'address'
      ]
    },
    {
      title: '🏢 Customer Entity Fields',
      fields: [
        'entity_name', 'entity_type', 'entity_registration_number',
        'entity_country_of_incorporation', 'entity_industry', 'entity_related_persons'
      ]
    },
    {
      title: '💸 Customer Payment Fields',
      fields: [
        'payment_reference', 'payment_date', 'payment_amount', 'payment_currency',
        'payer_name', 'payer_country', 'beneficiary_name', 'beneficiary_country',
        'payment_purpose', 'payment_channel'
      ]
    },
    {
      title: '✅ Outcome Fields',
      fields: [
        'match_type', 'match_probability', 'match_reasons',
        'match_explanation', 'screening_rationale'
      ]
    }
  ];

  useEffect(() => {
    if (user?.role === 'admin') {
      fetchFieldVisibility();
    }
  }, [user]);

  const fetchFieldVisibility = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/admin/field_visibility`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setAllFields(data.all_fields || []);
          const visible = new Set();
          Object.entries(data.visibility || {}).forEach(([field, isVisible]) => {
            if (isVisible) visible.add(field);
          });
          // Default all fields to visible if no visibility settings exist
          if (visible.size === 0 && data.all_fields) {
            data.all_fields.forEach(field => visible.add(field));
          }
          setVisibleFields(visible);
        }
      } else {
        setMessage({ type: 'danger', text: 'Failed to load field visibility settings' });
      }
    } catch (error) {
      console.error('Error fetching field visibility:', error);
      setMessage({ type: 'danger', text: 'Error loading field visibility settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (field) => {
    setVisibleFields(prev => {
      const newSet = new Set(prev);
      if (newSet.has(field)) {
        newSet.delete(field);
      } else {
        newSet.add(field);
      }
      return newSet;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await fetch(`${BASE_URL}/api/admin/field_visibility`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          visible_fields: Array.from(visibleFields)
        })
      });

      if (response.ok) {
        const data = await response.json();
        setMessage({ type: 'success', text: data.message || 'Field visibility updated successfully' });
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to update field visibility' }));
        setMessage({ type: 'danger', text: errorData.error || 'Failed to update field visibility' });
      }
    } catch (error) {
      console.error('Error updating field visibility:', error);
      setMessage({ type: 'danger', text: 'Error updating field visibility' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="container-fluid my-4">
        <div className="text-center">
          <div className="spinner-border" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">Field Visibility Settings</h2>
      </div>

      {message.text && (
        <div className={`alert alert-${message.type} alert-dismissible fade show`} role="alert">
          {message.text}
          <button
            type="button"
            className="btn-close"
            onClick={() => setMessage({ type: '', text: '' })}
            aria-label="Close"
          ></button>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        {fieldGroups.map((group, groupIdx) => (
          <div key={groupIdx} className="mb-5">
            <h4 className="mt-4 mb-3">{group.title}</h4>
            <div className="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">
              {group.fields.map((field) => (
                <div key={field} className="col">
                  <div className="form-check border p-3 rounded shadow-sm bg-light">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      id={field}
                      checked={visibleFields.has(field)}
                      onChange={() => handleToggle(field)}
                    />
                    <label
                      className="form-check-label fw-semibold"
                      htmlFor={field}
                      title={field.replace(/_/g, ' ')}
                    >
                      {field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="mt-5">
          <button type="submit" className="btn btn-success" disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default AdminFieldVisibility;


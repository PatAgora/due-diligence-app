import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050';

function AdminTeamStructure() {
  const { user } = useAuth();
  const [teamData, setTeamData] = useState({ nodes_by_level: {}, role_labels: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (user?.role === 'admin') {
      fetchTeamStructure();
    }
  }, [user]);

  const fetchTeamStructure = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BASE_URL}/api/admin/team_structure`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setTeamData({
            nodes_by_level: data.nodes_by_level || {},
            role_labels: data.role_labels || {}
          });
        }
      } else {
        setError('Failed to load team structure');
      }
    } catch (err) {
      console.error('Error fetching team structure:', err);
      setError('Error loading team structure');
    } finally {
      setLoading(false);
    }
  };

  const getInitials = (name) => {
    if (!name) return '??';
    const parts = name.split(' ').slice(0, 2);
    return parts.map(p => p[0]?.toUpperCase() || '').join('');
  };

  const formatRole = (role, roleLabels) => {
    return roleLabels[role] || role.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
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

  if (error) {
    return (
      <div className="container-fluid my-4">
        <div className="alert alert-danger">{error}</div>
      </div>
    );
  }

  return (
    <div className="container-fluid my-4 px-5">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0">Team Structure</h2>
        <div className="d-flex gap-2">
          <span className="badge bg-secondary">Team Leads</span>
          <span className="badge bg-secondary">Reviewers</span>
          <span className="badge bg-secondary">Levels 1–3</span>
        </div>
      </div>

      <div
        style={{
          background: '#f7f8fb',
          borderRadius: '14px',
          padding: '18px',
          boxShadow: '0 1px 0 rgba(16,24,40,.04) inset, 0 1px 2px rgba(16,24,40,.06)'
        }}
      >
        <div
          style={{
            position: 'relative',
            overflow: 'auto',
            height: '70vh',
            background: 'linear-gradient(180deg,#fff, #fbfcff)',
            border: '1px solid #eef0f4',
            borderRadius: '12px',
            padding: '24px'
          }}
        >
          <div
            style={{
              minWidth: '720px',
              display: 'grid',
              gridTemplateColumns: 'repeat(3, minmax(240px, 1fr))',
              gap: '24px'
            }}
          >
            {[1, 2, 3].map(level => (
              <section key={level}>
                <h2
                  style={{
                    fontSize: '.9rem',
                    fontWeight: 700,
                    color: '#64748b',
                    letterSpacing: '.3px',
                    textTransform: 'uppercase',
                    margin: '0 0 .5rem 2px'
                  }}
                >
                  Level {level}
                </h2>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'flex-start' }}>
                  {(teamData.nodes_by_level[level] || []).map((member) => (
                    <div
                      key={member.id}
                      style={{
                        position: 'relative',
                        width: '220px',
                        border: '1px solid #e6e9ef',
                        borderRadius: '14px',
                        background: '#fff',
                        boxShadow: '0 1px 2px rgba(16,24,40,.06)',
                        padding: '12px',
                        transition: 'transform .15s ease, box-shadow .15s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = '0 8px 20px rgba(16,24,40,.08)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = '0 1px 2px rgba(16,24,40,.06)';
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div
                          style={{
                            width: '38px',
                            height: '38px',
                            borderRadius: '10px',
                            display: 'grid',
                            placeItems: 'center',
                            fontWeight: 800,
                            background: 'linear-gradient(135deg,#e0e7ff,#f0f9ff)',
                            color: '#334155',
                            border: '1px solid #e5e7eb'
                          }}
                        >
                          {getInitials(member.name)}
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, lineHeight: 1.15 }}>{member.name}</div>
                          <div style={{ fontSize: '.8rem', color: '#64748b', marginTop: '2px' }}>
                            {formatRole(member.role, teamData.role_labels)}
                          </div>
                        </div>
                      </div>
                      <div
                        style={{
                          display: 'inline-block',
                          fontSize: '.7rem',
                          fontWeight: 600,
                          border: '1px solid #e5e7eb',
                          color: '#0f172a',
                          background: '#f8fafc',
                          padding: '.15rem .45rem',
                          borderRadius: '999px',
                          marginTop: '8px'
                        }}
                      >
                        Level {level}
                      </div>
                    </div>
                  ))}
                  {(teamData.nodes_by_level[level] || []).length === 0 && (
                    <div style={{ color: '#94a3b8' }}>No team members at Level {level}.</div>
                  )}
                </div>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminTeamStructure;


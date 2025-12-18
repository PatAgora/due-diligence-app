import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

function TopNavbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState('task_id');

  const isLoginPage = location.pathname === '/login' || location.pathname.startsWith('/login');
  
  if (isLoginPage) {
    return null;
  }

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?type=${searchType}&query=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <nav className="top-navbar" style={{
      position: 'fixed',
      top: 0,
      left: '240px',
      right: 0,
      height: '60px',
      backgroundColor: '#ffffff',
      borderBottom: '1px solid #e5e7eb',
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      zIndex: 1050,
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', width: '100%', maxWidth: '800px' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: '#ffffff',
              fontSize: '14px',
              cursor: 'pointer',
              minWidth: '140px'
            }}
          >
            <option value="task_id">Task ID</option>
            <option value="customer_id">Customer ID</option>
            <option value="watchlist_id">Watchlist ID</option>
            <option value="all">All Fields</option>
          </select>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            style={{
              flex: 1,
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '14px',
              minWidth: '200px'
            }}
          />
          <button
            type="submit"
            style={{
              padding: '8px 16px',
              backgroundColor: '#0b1320',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <i className="bi bi-search"></i> Search
          </button>
        </form>
      </div>
      {user && (
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '14px', color: '#6b7280' }}>
            {user.name || user.email}
          </span>
        </div>
      )}
    </nav>
  );
}

export default TopNavbar;


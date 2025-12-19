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
      background: 'linear-gradient(135deg, #1a2332 0%, #2D3847 100%)',
      borderBottom: '1px solid rgba(248, 157, 67, 0.2)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      zIndex: 1050,
      boxShadow: '0 2px 4px rgba(0, 0, 0, 0.3)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', width: '100%', maxWidth: '800px' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
          <select
            value={searchType}
            onChange={(e) => setSearchType(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '6px',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              fontSize: '14px',
              cursor: 'pointer',
              minWidth: '140px'
            }}
          >
            <option value="task_id" style={{ backgroundColor: '#2D3847', color: '#ffffff' }}>Task ID</option>
            <option value="customer_id" style={{ backgroundColor: '#2D3847', color: '#ffffff' }}>Customer ID</option>
            <option value="watchlist_id" style={{ backgroundColor: '#2D3847', color: '#ffffff' }}>Watchlist ID</option>
            <option value="all" style={{ backgroundColor: '#2D3847', color: '#ffffff' }}>All Fields</option>
          </select>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            style={{
              flex: 1,
              padding: '8px 12px',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '6px',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              fontSize: '14px',
              minWidth: '200px'
            }}
          />
          <button
            type="submit"
            style={{
              padding: '8px 16px',
              backgroundColor: '#F89D43',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s ease'
            }}
            onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#e08932'}
            onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#F89D43'}
          >
            <i className="bi bi-search"></i> Search
          </button>
        </form>
      </div>
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '20px' }}>
        {user && (
          <span style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.85)', fontWeight: 500 }}>
            {user.name || user.email}
          </span>
        )}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px',
          paddingLeft: '20px',
          borderLeft: '1px solid rgba(255, 255, 255, 0.2)'
        }}>
          <span style={{ 
            fontSize: '12px', 
            color: 'rgba(255, 255, 255, 0.7)',
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            Powered By
          </span>
          <img 
            src="/img/agora_logo.jpg" 
            alt="Agora Consulting" 
            style={{ 
              height: '40px',
              display: 'block'
            }} 
          />
        </div>
      </div>
    </nav>
  );
}

export default TopNavbar;

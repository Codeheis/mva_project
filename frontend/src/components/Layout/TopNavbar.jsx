import { useState } from 'react';
import { Search, Upload, LogOut, User, Play } from 'lucide-react';

export default function TopNavbar({
  userToken, username,
  onLogout, onLoginClick, onRegisterClick, onProfileClick, onUploadClick, onSearch,
}) {
  const [query, setQuery] = useState('');
  const submit = () => onSearch?.(query);

  return (
    <header
      className="fixed inset-x-0 top-0 z-40 h-14 flex items-center px-4 gap-4"
      style={{
        background: 'rgba(15,15,23,0.85)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Brand */}
      <button
        onClick={() => onSearch?.('')}
        className="flex items-center gap-2.5 min-w-[180px] shrink-0"
      >
        <span
          className="h-8 w-8 rounded-xl flex items-center justify-center shadow-glow-sm"
          style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
        >
          <Play size={14} fill="white" color="white" className="ml-0.5" />
        </span>
        <span className="font-bold tracking-tight text-white text-[15px]">VideoHub</span>
      </button>

      {/* Search */}
      <div className="flex-1 hidden sm:flex items-center gap-2 max-w-xl mx-auto">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="Search videos…"
            className="neu-input w-full h-9 pl-9 pr-4 text-sm"
          />
        </div>
        <button onClick={submit} className="btn-ghost h-9 px-4 text-sm font-medium">
          Search
        </button>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 ml-auto">
        {userToken ? (
          <>
            <button
              onClick={onUploadClick}
              className="hidden sm:flex items-center gap-1.5 h-9 px-3 text-sm font-medium rounded-[10px] transition"
              style={{
                background: 'rgba(99,102,241,0.12)',
                border: '1px solid rgba(99,102,241,0.25)',
                color: '#818cf8',
              }}
            >
              <Upload size={14} /> Upload
            </button>

            <button
              onClick={onProfileClick}
              className="flex items-center gap-2 h-9 px-3 btn-ghost text-sm font-medium"
            >
              <span
                className="h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
              >
                {username ? username[0].toUpperCase() : <User size={12} />}
              </span>
              <span className="hidden sm:inline text-white/80">{username || 'Profile'}</span>
            </button>

            <button onClick={onLogout} className="btn-ghost h-9 w-9 flex items-center justify-center" title="Sign out">
              <LogOut size={15} className="text-white/50" />
            </button>
          </>
        ) : (
          <>
            <button onClick={onLoginClick} className="btn-ghost h-9 px-4 text-sm font-medium">
              Sign in
            </button>
            <button
              onClick={onRegisterClick}
              className="btn-primary h-9 px-4 text-sm"
            >
              Sign up
            </button>
          </>
        )}
      </div>
    </header>
  );
}

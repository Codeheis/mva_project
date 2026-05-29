import { useState } from 'react';
import { Eye, EyeOff, Play, AlertCircle, Loader2 } from 'lucide-react';

export default function LoginView({ onSuccessToken, onNavigateHome, onNavigateToRegister }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw]     = useState(false);
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password) { setError('Username and password are required.'); return; }
    setBusy(true);
    try {
      const res = await fetch('http://localhost/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: username.trim(), password }),
      });
      if (!res.ok) {
        let msg = `Login failed (${res.status})`;
        try { const j = await res.json(); msg = j?.detail || msg; } catch { /* ignore */ }
        throw new Error(msg);
      }
      let token;
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const j = await res.json();
        token = j?.access_token || j?.token || '';
      } else {
        token = (await res.text()).trim();
      }
      if (!token) throw new Error('Empty token returned by server.');
      onSuccessToken(token);
      onNavigateHome();
    } catch (err) {
      setError(err?.message || 'Login failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">

        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <span
            className="h-14 w-14 rounded-2xl flex items-center justify-center mb-4 shadow-glow"
            style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
          >
            <Play size={22} fill="white" color="white" className="ml-0.5" />
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white">Welcome back</h1>
          <p className="text-white/40 text-sm mt-1">Sign in to your VideoHub account</p>
        </div>

        {/* Card */}
        <div className="neu-card p-7">
          <form onSubmit={handleLogin} className="space-y-4">

            <div>
              <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">
                Username
              </label>
              <input
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="neu-input w-full px-4 py-2.5 text-sm"
                placeholder="your_username"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  type={showPw ? 'text' : 'password'}
                  className="neu-input w-full px-4 py-2.5 pr-11 text-sm"
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  tabIndex={-1}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div
                className="flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm"
                style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5' }}
              >
                <AlertCircle size={15} className="shrink-0" />
                {error}
              </div>
            )}

            <button type="submit" disabled={busy} className="btn-primary w-full py-2.5 text-sm mt-1">
              {busy
                ? <span className="flex items-center justify-center gap-2"><Loader2 size={15} className="animate-spin" /> Signing in…</span>
                : 'Sign in'}
            </button>
          </form>

          <div
            className="mt-5 pt-5 text-center text-sm text-white/40"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            Don't have an account?{' '}
            <button
              onClick={onNavigateToRegister}
              className="font-semibold transition"
              style={{ color: '#818cf8' }}
              onMouseEnter={e => e.target.style.color = '#a5b4fc'}
              onMouseLeave={e => e.target.style.color = '#818cf8'}
            >
              Create one
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

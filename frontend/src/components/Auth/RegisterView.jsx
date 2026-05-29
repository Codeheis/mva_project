import { useState } from 'react';
import { Eye, EyeOff, UserPlus, AlertCircle, Loader2 } from 'lucide-react';

export default function RegisterView({ onSuccessTokenOrNavigateLogin }) {
  const [username, setUsername] = useState('');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw]     = useState(false);
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState('');

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !email.trim() || !password) { setError('All fields are required.'); return; }
    setBusy(true);
    try {
      const res = await fetch('http://localhost/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), email: email.trim(), password }),
      });
      if (!res.ok) {
        let msg = `Registration failed (${res.status})`;
        try { const j = await res.json(); msg = j?.detail || msg; } catch { /* ignore */ }
        throw new Error(msg);
      }
      onSuccessTokenOrNavigateLogin?.();
    } catch (err) {
      setError(err?.message || 'Registration failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-[400px]">

        <div className="flex flex-col items-center mb-8">
          <span
            className="h-14 w-14 rounded-2xl flex items-center justify-center mb-4 shadow-glow"
            style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
          >
            <UserPlus size={20} color="white" />
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white">Create account</h1>
          <p className="text-white/40 text-sm mt-1">Join VideoHub and start sharing</p>
        </div>

        <div className="neu-card p-7">
          <form onSubmit={handleRegister} className="space-y-4">

            <div>
              <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Username</label>
              <input
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="neu-input w-full px-4 py-2.5 text-sm"
                placeholder="your_username"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Email</label>
              <input
                value={email}
                onChange={e => setEmail(e.target.value)}
                type="email"
                className="neu-input w-full px-4 py-2.5 text-sm"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">Password</label>
              <div className="relative">
                <input
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  type={showPw ? 'text' : 'password'}
                  className="neu-input w-full px-4 py-2.5 pr-11 text-sm"
                  placeholder="••••••••"
                  autoComplete="new-password"
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
                ? <span className="flex items-center justify-center gap-2"><Loader2 size={15} className="animate-spin" /> Creating account…</span>
                : 'Create account'}
            </button>
          </form>

          <div
            className="mt-5 pt-5 text-center text-sm text-white/40"
            style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            Already have an account?{' '}
            <button
              onClick={onSuccessTokenOrNavigateLogin}
              className="font-semibold transition"
              style={{ color: '#818cf8' }}
              onMouseEnter={e => e.target.style.color = '#a5b4fc'}
              onMouseLeave={e => e.target.style.color = '#818cf8'}
            >
              Sign in
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

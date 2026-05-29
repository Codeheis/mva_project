import { useEffect, useMemo, useState } from 'react';
import TopNavbar from './components/Layout/TopNavbar';
import LeftSidebar from './components/Layout/LeftSidebar';
import { getTokenFromLocalStorage, setTokenInLocalStorage } from './utils/auth';
import LoginView from './components/Auth/LoginView';
import RegisterView from './components/Auth/RegisterView';
import HomeFeedView from './components/Home/HomeFeedView';
import UploadView from './components/Upload/UploadView';
import { Lock, LogOut, Hash, AtSign, Mail } from 'lucide-react';

export default function App() {
  const [page,        setPage]        = useState('home');
  const [userToken,   setUserToken]   = useState(() => getTokenFromLocalStorage());
  const [userMeta,    setUserMeta]    = useState({ id: null, username: '', email: '', bio: '' });
  const [searchQuery, setSearchQuery] = useState('');

  // Hydrate session on token change
  useEffect(() => {
    if (!userToken) { setUserMeta({ id: null, username: '', email: '', bio: '' }); return; }
    let cancelled = false;
    fetch('http://localhost/api/auth/verify', { headers: { Authorization: `Bearer ${userToken}` } })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        if (cancelled) return;
        const u = data?.user || data?.current_user || data;
        setUserMeta({ id: u?.id ?? null, username: u?.username ?? '', email: u?.email ?? '', bio: u?.bio ?? '' });
      })
      .catch(() => {
        if (!cancelled) { setTokenInLocalStorage(''); setUserToken(''); }
      });
    return () => { cancelled = true; };
  }, [userToken]);

  const logout = () => {
    setTokenInLocalStorage(''); setUserToken('');
    setUserMeta({ id: null, username: '', email: '', bio: '' });
    setPage('home');
  };

  const handleSearch = (q) => { setSearchQuery(q); setPage('home'); };

  const navProps = useMemo(() => ({
    userToken,
    username: userMeta.username,
    onLogout: logout,
    onLoginClick:    () => setPage('login'),
    onRegisterClick: () => setPage('register'),
    onProfileClick:  () => setPage('profile'),
    onUploadClick:   () => setPage('upload'),
    onSearch: handleSearch,
  }), [userToken, userMeta.username]);

  return (
    <div className="min-h-screen" style={{ background: '#0f0f17', color: '#fff' }}>
      <TopNavbar {...navProps} />
      <LeftSidebar page={page} setPage={setPage} userToken={userToken} />

      <main className="pt-14 pl-60">
        <div className="mx-auto max-w-[1400px] px-6 py-6">

          {page === 'home' && (
            <HomeFeedView userToken={userToken} searchQuery={searchQuery} />
          )}

          {page === 'login' && (
            <LoginView
              onSuccessToken={token => { setTokenInLocalStorage(token); setUserToken(token); }}
              onNavigateHome={() => setPage('home')}
              onNavigateToRegister={() => setPage('register')}
            />
          )}

          {page === 'register' && (
            <RegisterView onSuccessTokenOrNavigateLogin={() => setPage('login')} />
          )}

          {page === 'upload' && userToken && (
            <UploadView userToken={userToken} onUploaded={() => setPage('home')} />
          )}

          {page === 'upload' && !userToken && (
            <div className="min-h-[calc(100vh-3.5rem)] flex items-center justify-center">
              <div className="text-center">
                <span
                  className="h-16 w-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
                >
                  <Lock size={28} className="text-white/20" />
                </span>
                <p className="text-white/50 font-medium">Sign in to upload videos</p>
                <button
                  onClick={() => setPage('login')}
                  className="btn-primary mt-4 px-6 py-2.5 text-sm"
                >
                  Sign in
                </button>
              </div>
            </div>
          )}

          {page === 'profile' && (
            <div className="max-w-2xl mx-auto space-y-5">
              <div>
                <h2 className="text-lg font-bold text-white">Profile</h2>
                <p className="text-white/30 text-xs mt-0.5">Your account details</p>
              </div>

              {userToken ? (
                <>
                  {/* Avatar card */}
                  <div
                    className="rounded-2xl p-6 flex items-center gap-5"
                    style={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
                  >
                    <span
                      className="h-16 w-16 rounded-2xl flex items-center justify-center text-2xl font-bold text-white shrink-0 shadow-glow-sm"
                      style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
                    >
                      {userMeta.username ? userMeta.username[0].toUpperCase() : '?'}
                    </span>
                    <div>
                      <p className="text-white font-semibold text-lg leading-tight">{userMeta.username || '—'}</p>
                      <p className="text-white/40 text-sm mt-0.5">{userMeta.email || '—'}</p>
                      {userMeta.bio && <p className="text-white/30 text-sm mt-1">{userMeta.bio}</p>}
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'User ID',  value: userMeta.id ?? '—',           Icon: Hash   },
                      { label: 'Username', value: userMeta.username || '—',      Icon: AtSign },
                      { label: 'Email',    value: userMeta.email    || '—',      Icon: Mail   },
                    ].map(({ label, value, Icon }) => (
                      <div
                        key={label}
                        className="rounded-xl p-4"
                        style={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)' }}
                      >
                        <div className="flex items-center gap-1.5 mb-2">
                          <Icon size={11} className="text-white/25" />
                          <p className="text-[10px] text-white/35 uppercase tracking-wider font-semibold">{label}</p>
                        </div>
                        <p className="text-white font-semibold text-sm truncate">{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Sign out */}
                  <button
                    onClick={logout}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition"
                    style={{
                      background: 'rgba(239,68,68,0.08)',
                      border: '1px solid rgba(239,68,68,0.2)',
                      color: '#f87171',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.14)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'rgba(239,68,68,0.08)'}
                  >
                    <LogOut size={15} /> Sign out
                  </button>
                </>
              ) : (
                <div
                  className="rounded-2xl p-8 text-center"
                  style={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <p className="text-white/40">You must be signed in to view your profile.</p>
                  <button onClick={() => setPage('login')} className="btn-primary mt-4 px-6 py-2.5 text-sm">
                    Sign in
                  </button>
                </div>
              )}
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

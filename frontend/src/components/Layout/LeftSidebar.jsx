import { Home, Upload, User, LogIn, UserPlus, Wifi } from 'lucide-react';

const NAV = [
  { id: 'home',     label: 'Home',     Icon: Home,     auth: false, guest: false },
  { id: 'upload',   label: 'Upload',   Icon: Upload,   auth: true,  guest: false },
  { id: 'profile',  label: 'Profile',  Icon: User,     auth: true,  guest: false },
  { id: 'login',    label: 'Sign in',  Icon: LogIn,    auth: false, guest: true  },
  { id: 'register', label: 'Register', Icon: UserPlus, auth: false, guest: true  },
];

export default function LeftSidebar({ page, setPage, userToken }) {
  const isAuth = !!userToken;
  const visible = NAV.filter(item => {
    if (item.auth  && !isAuth) return false;
    if (item.guest &&  isAuth) return false;
    return true;
  });

  return (
    <aside
      className="fixed left-0 top-14 bottom-0 w-60 z-30 flex flex-col"
      style={{
        background: 'rgba(19,19,31,0.9)',
        backdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5 overflow-y-auto">
        {visible.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setPage(id)}
            className={`sidebar-item${page === id ? ' active' : ''}`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>

      {/* Status panel */}
      <div className="px-3 pb-4">
        <div
          className="rounded-xl p-3 text-xs"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="flex items-center gap-1.5 mb-2.5">
            <Wifi size={11} className="text-white/30" />
            <span className="text-white/40 font-semibold uppercase tracking-wider text-[10px]">System</span>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-white/30">Auth</span>
              <span className="flex items-center gap-1" style={{ color: isAuth ? '#34d399' : 'rgba(255,255,255,0.25)' }}>
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: isAuth ? '#34d399' : 'rgba(255,255,255,0.2)' }}
                />
                {isAuth ? 'Active' : 'Guest'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-white/30">API</span>
              <span className="text-white/40">localhost</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

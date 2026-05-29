import { useEffect, useMemo, useState } from 'react';
import { Play, Monitor, AlertCircle, Loader2, X, Calendar, User } from 'lucide-react';

const MINIO_BASE = 'http://localhost:9000/processed-videos';

const STATUS_STYLES = {
  READY:      { bg: 'rgba(52,211,153,0.12)', border: 'rgba(52,211,153,0.3)',  color: '#34d399', dot: '#34d399' },
  PROCESSING: { bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.3)',  color: '#fbbf24', dot: '#fbbf24', pulse: true },
  PENDING:    { bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.3)',  color: '#818cf8', dot: '#818cf8' },
  FAILED:     { bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.3)',   color: '#f87171', dot: '#f87171' },
};

function StatusBadge({ status }) {
  const s = (status || '').toUpperCase();
  const st = STATUS_STYLES[s] || { bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.4)', dot: 'rgba(255,255,255,0.2)' };
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold"
      style={{ background: st.bg, border: `1px solid ${st.border}`, color: st.color }}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full shrink-0${st.pulse ? ' animate-pulse' : ''}`}
        style={{ background: st.dot }}
      />
      {s || 'UNKNOWN'}
    </span>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl overflow-hidden animate-pulse" style={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.05)' }}>
      <div className="h-44" style={{ background: 'rgba(255,255,255,0.04)' }} />
      <div className="p-3 space-y-2">
        <div className="h-3.5 rounded-lg w-3/4" style={{ background: 'rgba(255,255,255,0.07)' }} />
        <div className="h-2.5 rounded-lg w-1/2" style={{ background: 'rgba(255,255,255,0.04)' }} />
      </div>
    </div>
  );
}

export default function HomeFeedView({ userToken, searchQuery = '' }) {
  const [videos, setVideos]       = useState([]);
  const [busy, setBusy]           = useState(false);
  const [error, setError]         = useState('');
  const [activeVideo, setActive]  = useState(null);

  const headers = useMemo(() => userToken ? { Authorization: `Bearer ${userToken}` } : {}, [userToken]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setBusy(true); setError('');
      try {
        const url = searchQuery.trim()
          ? `http://localhost/api/catalog/videos?search=${encodeURIComponent(searchQuery.trim())}`
          : 'http://localhost/api/catalog/videos';
        const res = await fetch(url, { headers });
        if (!res.ok) throw new Error(`Failed to load videos (${res.status})`);
        const data = await res.json();
        if (!cancelled) setVideos(Array.isArray(data) ? data : data?.videos || []);
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load videos.');
      } finally {
        if (!cancelled) setBusy(false);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [headers, searchQuery]);

  const thumbUrl  = v => v?.thumbnail_path ? `${MINIO_BASE}/${v.thumbnail_path}` : null;
  const streamUrl = v => `http://localhost/api/catalog/videos/${v.id}/stream${userToken ? `?token=${encodeURIComponent(userToken)}` : ''}`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">
            {searchQuery ? `Results for "${searchQuery}"` : 'Latest Videos'}
          </h2>
          <p className="text-white/30 text-xs mt-0.5">{videos.length} video{videos.length !== 1 ? 's' : ''}</p>
        </div>
        {busy && <Loader2 size={18} className="animate-spin text-white/30" />}
      </div>

      {/* Error */}
      {error && (
        <div
          className="flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm"
          style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5' }}
        >
          <AlertCircle size={15} className="shrink-0" /> {error}
        </div>
      )}

      {/* Skeleton */}
      {busy && videos.length === 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty */}
      {!busy && videos.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <span
            className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            <Monitor size={28} className="text-white/20" />
          </span>
          <p className="text-white/40 font-medium">No videos found</p>
          <p className="text-white/20 text-sm mt-1">Upload a video to get started</p>
        </div>
      )}

      {/* Grid */}
      {videos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {videos.map(video => {
            const status  = (video?.status || '').toUpperCase();
            const isReady = status === 'READY';
            const thumb   = thumbUrl(video);
            return (
              <button
                key={video.id}
                type="button"
                onClick={() => isReady && setActive(video)}
                className={`text-left rounded-2xl overflow-hidden transition-all group${isReady ? ' cursor-pointer' : ' cursor-default'}`}
                style={{
                  background: '#13131f',
                  border: '1px solid rgba(255,255,255,0.06)',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
                  opacity: isReady ? 1 : 0.75,
                  ...(isReady ? {} : {}),
                }}
                onMouseEnter={e => isReady && (e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)')}
                onMouseLeave={e => isReady && (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)')}
              >
                {/* Thumbnail */}
                <div className="relative h-44 overflow-hidden" style={{ background: '#0f0f17' }}>
                  {thumb
                    ? <img src={thumb} alt={video.title} className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" />
                    : <div className="w-full h-full flex items-center justify-center"><Play size={32} className="text-white/10" /></div>
                  }
                  {isReady && (
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: 'rgba(0,0,0,0.5)' }}>
                      <span
                        className="h-12 w-12 rounded-full flex items-center justify-center shadow-glow"
                        style={{ background: 'rgba(99,102,241,0.85)', backdropFilter: 'blur(8px)' }}
                      >
                        <Play size={18} fill="white" color="white" className="ml-0.5" />
                      </span>
                    </div>
                  )}
                  <div className="absolute top-2 right-2">
                    <StatusBadge status={video.status} />
                  </div>
                </div>

                {/* Info */}
                <div className="p-3">
                  <p className="font-semibold text-white text-sm leading-snug line-clamp-2">{video.title || 'Untitled'}</p>
                  {video.description && (
                    <p className="text-white/35 text-xs mt-1 line-clamp-1">{video.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-white/25">
                    {video.uploader_id && (
                      <span className="flex items-center gap-1"><User size={10} /> {video.uploader_id}</span>
                    )}
                    {video.created_at && (
                      <span className="flex items-center gap-1"><Calendar size={10} /> {new Date(video.created_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Modal */}
      {activeVideo && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(12px)' }}
          onClick={e => e.target === e.currentTarget && setActive(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="w-full max-w-4xl rounded-2xl overflow-hidden shadow-2xl"
            style={{ background: '#13131f', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            {/* Modal header */}
            <div
              className="flex items-center justify-between gap-4 px-5 py-4"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="min-w-0">
                <p className="text-white font-semibold truncate">{activeVideo.title || 'Video'}</p>
                {activeVideo.description && (
                  <p className="text-white/35 text-sm truncate mt-0.5">{activeVideo.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setActive(null)}
                className="btn-ghost h-8 w-8 flex items-center justify-center shrink-0"
                aria-label="Close"
              >
                <X size={15} />
              </button>
            </div>

            {/* Video */}
            <div style={{ background: '#000' }}>
              <video
                src={streamUrl(activeVideo)}
                controls
                autoPlay
                className="w-full max-h-[70vh]"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

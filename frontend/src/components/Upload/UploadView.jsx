import { useRef, useState } from 'react';
import { UploadCloud, Film, AlertCircle, CheckCircle2, Loader2, X } from 'lucide-react';

const ACCEPTED = ['video/mp4', 'video/x-matroska', 'video/quicktime'];
const MAX_MB   = 100;

export default function UploadView({ userToken, onUploaded }) {
  const [file,        setFile]        = useState(null);
  const [title,       setTitle]       = useState('');
  const [description, setDescription] = useState('');
  const [progress,    setProgress]    = useState(0);
  const [busy,        setBusy]        = useState(false);
  const [error,       setError]       = useState('');
  const [success,     setSuccess]     = useState(false);
  const inputRef = useRef();

  const pickFile = (f) => {
    setError(''); setSuccess(false);
    if (!f) return;
    if (!ACCEPTED.includes(f.type)) { setError('Only MP4, MKV, or MOV files are accepted.'); return; }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`File must be under ${MAX_MB} MB.`); return; }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file)         { setError('Please select a video file.'); return; }
    if (!title.trim()) { setError('Title is required.'); return; }
    setBusy(true); setError(''); setProgress(0);

    const form = new FormData();
    form.append('video', file);
    form.append('title', title.trim());
    if (description.trim()) form.append('description', description.trim());

    try {
      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', 'http://localhost/api/upload/');
        xhr.setRequestHeader('Authorization', `Bearer ${userToken}`);
        xhr.upload.onprogress = ev => {
          if (ev.lengthComputable) setProgress(Math.round((ev.loaded / ev.total) * 100));
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve();
          else {
            let msg = `Upload failed (${xhr.status})`;
            try { msg = JSON.parse(xhr.responseText)?.detail || msg; } catch { /* ignore */ }
            reject(new Error(msg));
          }
        };
        xhr.onerror = () => reject(new Error('Network error during upload.'));
        xhr.send(form);
      });
      setSuccess(true); setFile(null); setTitle(''); setDescription(''); setProgress(0);
      onUploaded?.();
    } catch (err) {
      setError(err?.message || 'Upload failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-bold text-white">Upload Video</h2>
        <p className="text-white/30 text-xs mt-0.5">MP4, MKV, MOV · max {MAX_MB} MB</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">

        {/* Drop zone */}
        <div
          onDrop={e => { e.preventDefault(); pickFile(e.dataTransfer.files?.[0]); }}
          onDragOver={e => e.preventDefault()}
          onClick={() => !busy && inputRef.current?.click()}
          className="rounded-2xl border-2 border-dashed transition-all cursor-pointer"
          style={{
            borderColor: file ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.08)',
            background:  file ? 'rgba(99,102,241,0.05)' : 'rgba(255,255,255,0.02)',
          }}
          onMouseEnter={e => !file && (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)')}
          onMouseLeave={e => !file && (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)')}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED.join(',')}
            className="hidden"
            onChange={e => pickFile(e.target.files?.[0])}
          />
          <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
            {file ? (
              <>
                <span
                  className="h-12 w-12 rounded-xl flex items-center justify-center mb-3"
                  style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}
                >
                  <Film size={22} style={{ color: '#818cf8' }} />
                </span>
                <p className="text-white font-medium text-sm">{file.name}</p>
                <p className="text-white/35 text-xs mt-1">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); setFile(null); setTitle(''); }}
                  className="mt-3 flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition"
                >
                  <X size={12} /> Remove
                </button>
              </>
            ) : (
              <>
                <span
                  className="h-12 w-12 rounded-xl flex items-center justify-center mb-3"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}
                >
                  <UploadCloud size={22} className="text-white/25" />
                </span>
                <p className="text-white/60 font-medium text-sm">Drop video here or click to browse</p>
                <p className="text-white/25 text-xs mt-1">MP4, MKV, MOV up to {MAX_MB} MB</p>
              </>
            )}
          </div>
        </div>

        {/* Title */}
        <div>
          <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">
            Title <span style={{ color: '#818cf8' }}>*</span>
          </label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            className="neu-input w-full px-4 py-2.5 text-sm"
            placeholder="My awesome video"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs font-semibold text-white/50 uppercase tracking-wider mb-2">
            Description <span className="text-white/25 normal-case font-normal">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={3}
            className="neu-input w-full px-4 py-2.5 text-sm resize-none"
            placeholder="Optional description…"
          />
        </div>

        {/* Progress */}
        {busy && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-white/40">
              <span>Uploading…</span><span>{progress}%</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
              <div
                className="h-full rounded-full transition-all duration-200"
                style={{ width: `${progress}%`, background: 'linear-gradient(90deg,#6366f1,#818cf8)' }}
              />
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            className="flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5' }}
          >
            <AlertCircle size={15} className="shrink-0" /> {error}
          </div>
        )}

        {/* Success */}
        {success && (
          <div
            className="flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm"
            style={{ background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.25)', color: '#6ee7b7' }}
          >
            <CheckCircle2 size={15} className="shrink-0" />
            Video uploaded! Transcoding is queued — it will appear as READY shortly.
          </div>
        )}

        <button type="submit" disabled={busy || !file} className="btn-primary w-full py-2.5 text-sm">
          {busy
            ? <span className="flex items-center justify-center gap-2"><Loader2 size={15} className="animate-spin" /> Uploading…</span>
            : 'Upload Video'}
        </button>
      </form>
    </div>
  );
}

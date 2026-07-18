import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API = 'http://localhost:5000/api';

const TYPE_COLORS = { tiff: '#e74c3c', shapefile: '#2980b9', csv: '#27ae60', other: '#8e44ad' };
const TYPE_EMOJI  = { tiff: '🗺', shapefile: '📐', csv: '📊', other: '📁' };

function Badge({ type }) {
  const color = TYPE_COLORS[type] || TYPE_COLORS.other;
  const emoji = TYPE_EMOJI[type] || '📁';
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded font-medium"
      style={{ background: color + '33', color }}>
      {emoji} {type?.toUpperCase() || 'FILE'}
    </span>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-700 bg-slate-750">
        <h3 className="font-semibold text-slate-100 text-sm">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

const inputCls = "w-full bg-slate-700 text-slate-100 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 placeholder-slate-500";
const btnPrimary = "bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors";
const btnSecondary = "bg-slate-700 hover:bg-slate-600 text-slate-200 font-medium px-4 py-2 rounded-lg text-sm transition-colors";
const btnDanger = "bg-red-800 hover:bg-red-700 text-red-100 font-medium px-3 py-1.5 rounded text-xs transition-colors";

// ─────────────────────────────────────────────────────────────────
// DatasetCard
// ─────────────────────────────────────────────────────────────────
function DatasetCard({ record, source, onDelete, isAdmin }) {
  const handleDownload = () => {
    window.open(`${API}/datasets/${record.id}/download?source=${source}`, '_blank');
  };

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 hover:border-slate-500 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Badge type={record.file_type} />
            {record.contributor && (
              <span className="text-xs text-slate-400">by {record.contributor}</span>
            )}
          </div>
          <h4 className="font-semibold text-slate-100 text-sm truncate">{record.name}</h4>
          {record.description && (
            <p className="text-xs text-slate-400 mt-1 line-clamp-2">{record.description}</p>
          )}
          <p className="text-xs text-slate-500 mt-1">
            {record.original_filename} · {record.created_at ? new Date(record.created_at).toLocaleDateString() : ''}
          </p>
        </div>
        <div className="flex flex-col gap-1.5 shrink-0">
          <button onClick={handleDownload} className={btnSecondary}>⬇ Download</button>
          {isAdmin && (
            <button onClick={() => onDelete(record.id)} className={btnDanger}>🗑 Delete</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Admin login modal
// ─────────────────────────────────────────────────────────────────
function AdminLogin({ onSuccess }) {
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true); setErr('');
    try {
      await axios.post(`${API}/admin/verify`, { password: pw });
      onSuccess();
    } catch {
      setErr('Incorrect password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex gap-2 items-center">
      <input
        type="password"
        placeholder="Admin password…"
        value={pw}
        onChange={e => setPw(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit()}
        className={inputCls + ' max-w-xs'}
      />
      <button onClick={submit} disabled={loading} className={btnPrimary}>
        {loading ? '…' : '🔑 Login'}
      </button>
      {err && <p className="text-red-400 text-xs">{err}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Upload / Link form
// ─────────────────────────────────────────────────────────────────
function UploadForm({ source, onSuccess }) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [contributor, setContributor] = useState('');
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [mode, setMode] = useState('upload'); // 'upload' | 'link'
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!name.trim()) { setErr('Name is required.'); return; }
    setBusy(true); setErr('');
    try {
      if (mode === 'upload') {
        if (!file) { setErr('Select a file first.'); setBusy(false); return; }
        const fd = new FormData();
        fd.append('file', file);
        fd.append('name', name);
        fd.append('description', desc);
        fd.append('source', source);
        if (contributor) fd.append('contributor', contributor);
        await axios.post(`${API}/datasets/upload`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      } else {
        if (!url.trim()) { setErr('Paste a URL first.'); setBusy(false); return; }
        await axios.post(`${API}/datasets/link`, { url, name, description: desc, source, contributor: contributor || undefined });
      }
      setName(''); setDesc(''); setContributor(''); setFile(null); setUrl('');
      onSuccess();
    } catch (e) {
      setErr(e.response?.data?.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {['upload', 'link'].map(m => (
          <button key={m} onClick={() => setMode(m)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              mode === m ? 'bg-emerald-600 text-white' : 'bg-slate-700 text-slate-400 hover:text-white'
            }`}>
            {m === 'upload' ? '📤 Upload File' : '🔗 Paste URL'}
          </button>
        ))}
      </div>

      {mode === 'upload' ? (
        <div className="border-2 border-dashed border-slate-600 rounded-xl p-6 text-center hover:border-emerald-600 transition-colors cursor-pointer relative">
          <input type="file" accept=".tif,.tiff,.shp,.zip,.csv,.geojson,.gpkg,.kml"
            onChange={e => setFile(e.target.files[0])}
            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" />
          <p className="text-slate-300 text-sm">
            {file ? `📁 ${file.name}` : 'Drag & drop or click to select'}
          </p>
          <p className="text-slate-500 text-xs mt-1">.tiff, .shp/.zip, .csv, .geojson, .gpkg, .kml</p>
        </div>
      ) : (
        <input type="url" placeholder="https://… direct file link or CDN URL"
          value={url} onChange={e => setUrl(e.target.value)} className={inputCls} />
      )}

      <div className="grid grid-cols-2 gap-3">
        <input placeholder="Dataset name *" value={name} onChange={e => setName(e.target.value)} className={inputCls} />
        {source === 'community' && (
          <input placeholder="Your name (optional)" value={contributor} onChange={e => setContributor(e.target.value)} className={inputCls} />
        )}
      </div>
      <textarea placeholder="Description (optional)" value={desc} onChange={e => setDesc(e.target.value)}
        rows={2} className={inputCls + ' resize-none'} />

      {err && <p className="text-red-400 text-xs">{err}</p>}

      <button onClick={submit} disabled={busy} className={btnPrimary}>
        {busy ? '⏳ Uploading…' : '✅ Submit Dataset'}
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// Main RareData Page
// ─────────────────────────────────────────────────────────────────
export default function RareDataPage() {
  const [tab, setTab] = useState('official');        // 'official' | 'community' | 'admin'
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [search, setSearch] = useState('');

  const source = tab === 'admin' ? 'admin' : tab === 'official' ? 'admin' : 'community';

  const loadDatasets = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/datasets?source=${source}`);
      setRecords(res.data.records || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDatasets(); }, [tab]);

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this dataset?')) return;
    try {
      await axios.delete(`${API}/datasets/${id}?source=${source}`);
      loadDatasets();
    } catch (e) {
      alert(e.response?.data?.detail || 'Delete failed');
    }
  };

  const downloadAll = () => {
    window.open(`${API}/datasets/download-all?source=${source}`, '_blank');
  };

  const filtered = records.filter(r =>
    !search || r.name?.toLowerCase().includes(search.toLowerCase()) ||
    r.description?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">🗄 RARE DATA — Dataset Repository</h1>
        <p className="text-slate-400 text-sm mt-1">
          Browse, download, and manage geospatial datasets covering Rwanda.
          Official datasets are curated by admins; Community uploads are contributed by anyone.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-2 border-b border-slate-700 pb-2">
        {[['official','📦 Official Datasets'],['community','🤝 Community Uploads'],['admin','🔐 Admin Panel']].map(([key, label]) => (
          <button key={key} onClick={() => { setTab(key); setShowUploadForm(false); }}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              tab === key ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* Official / Community Tabs */}
      {(tab === 'official' || tab === 'community') && (
        <>
          {/* Search + download-all */}
          <div className="flex gap-3 items-center">
            <input placeholder="🔍 Search datasets…" value={search} onChange={e => setSearch(e.target.value)}
              className={inputCls + ' flex-1'} />
            <button onClick={downloadAll} className={btnSecondary}>⬇ Download All</button>
            {tab === 'community' && (
              <button onClick={() => setShowUploadForm(v => !v)} className={btnPrimary}>
                {showUploadForm ? '✕ Cancel' : '+ Contribute'}
              </button>
            )}
          </div>

          {/* Community upload form */}
          {tab === 'community' && showUploadForm && (
            <Section title="Contribute a Dataset">
              <UploadForm source="community" onSuccess={() => { setShowUploadForm(false); loadDatasets(); }} />
            </Section>
          )}

          {/* Dataset list */}
          {loading ? (
            <div className="text-center text-slate-400 py-12">Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="text-center text-slate-500 py-12">
              <p className="text-4xl mb-3">📭</p>
              <p>No datasets found.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {filtered.map(r => (
                <DatasetCard key={r.id} record={r} source={source} onDelete={handleDelete} isAdmin={isAdmin} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Admin Tab */}
      {tab === 'admin' && (
        <div className="space-y-5">
          {!isAdmin ? (
            <Section title="🔐 Admin Login">
              <p className="text-slate-400 text-sm mb-4">Enter the admin password to manage official datasets.</p>
              <AdminLogin onSuccess={() => setIsAdmin(true)} />
            </Section>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400 font-semibold text-sm">✅ Admin Logged In</span>
                  <button onClick={() => setIsAdmin(false)} className={btnDanger}>Logout</button>
                </div>
                <button onClick={() => setShowUploadForm(v => !v)} className={btnPrimary}>
                  {showUploadForm ? '✕ Cancel' : '+ Upload Official Dataset'}
                </button>
              </div>

              {showUploadForm && (
                <Section title="Upload Official Dataset">
                  <UploadForm source="admin" onSuccess={() => { setShowUploadForm(false); loadDatasets(); }} />
                </Section>
              )}

              <div className="flex gap-3">
                <input placeholder="🔍 Search…" value={search} onChange={e => setSearch(e.target.value)}
                  className={inputCls + ' flex-1'} />
                <button onClick={downloadAll} className={btnSecondary}>⬇ Download All</button>
                <button onClick={loadDatasets} className={btnSecondary}>🔄 Refresh</button>
              </div>

              {loading ? (
                <div className="text-center text-slate-400 py-12">Loading…</div>
              ) : (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {filtered.map(r => (
                    <DatasetCard key={r.id} record={r} source="admin" onDelete={handleDelete} isAdmin={true} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

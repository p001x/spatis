import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, GeoJSON, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const API = 'http://localhost:5000/api';
const RWANDA_CENTER = [-1.94, 29.87];
const DEFAULT_CLASSES = ['Forest', 'Cropland', 'Bare Ground', 'Water', 'Urban', 'Shrubland'];
const CLASS_COLORS = ['#1a9850','#fdae61','#d73027','#2166ac','#8c510a','#762a83','#40004b','#f7f7f7'];

const inputCls = "w-full bg-slate-700 text-slate-100 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 placeholder-slate-500";
const btnPrimary = "bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors";
const btnSecondary = "bg-slate-700 hover:bg-slate-600 text-slate-200 font-medium px-4 py-2 rounded-lg text-sm transition-colors";
const btnDanger = "bg-red-800 hover:bg-red-700 text-red-100 font-medium px-3 py-1.5 rounded text-xs transition-colors";

function colorForClass(label, classes) {
  const idx = classes.indexOf(label);
  return CLASS_COLORS[idx % CLASS_COLORS.length] || '#94a3b8';
}

// ── Click handler that adds a sample point ────────────────────────────────────
function ClickHandler({ enabled, onAdd }) {
  useMapEvents({
    click(e) {
      if (!enabled) return;
      onAdd({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

// ── Fit map to GeoJSON ────────────────────────────────────────────────────────
function FitBounds({ geojson }) {
  const map = useMap();
  useEffect(() => {
    if (!geojson) return;
    try {
      const layer = L.geoJSON(geojson);
      if (layer.getBounds().isValid()) {
        map.fitBounds(layer.getBounds(), { padding: [20, 20] });
      }
    } catch { /* ignore */ }
  }, [geojson, map]);
  return null;
}

// ── Sample marker ─────────────────────────────────────────────────────────────
function SampleMarker({ sample, color, onDelete }) {
  const geom = sample.geometry;
  if (!geom) return null;

  const pos = geom.type === 'Point'
    ? [geom.coordinates[1], geom.coordinates[0]]
    : null;

  if (!pos) return null;

  const icon = L.divIcon({
    className: '',
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.5)"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });

  return (
    <Marker position={pos} icon={icon}
      eventHandlers={{ click: () => onDelete(sample.id) }}>
    </Marker>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Digitization Page
// ─────────────────────────────────────────────────────────────────────────────
export default function DigitizationPage() {
  // Samples state
  const [samples, setSamples] = useState([]);
  const [loadingSamples, setLoadingSamples] = useState(false);

  // Current drawing config
  const [activeClass, setActiveClass] = useState(DEFAULT_CLASSES[0]);
  const [customClasses, setCustomClasses] = useState(DEFAULT_CLASSES);
  const [newClass, setNewClass] = useState('');
  const [digitizing, setDigitizing] = useState(false);
  const [creator, setCreator] = useState('');

  // Context layer (optional XYZ tile URL to overlay while digitizing)
  const [contextTileUrl, setContextTileUrl] = useState('');

  // Panel tab
  const [panel, setPanel] = useState('digitize'); // 'digitize' | 'samples' | 'export'

  // Load samples on mount
  const loadSamples = useCallback(async () => {
    setLoadingSamples(true);
    try {
      const res = await axios.get(`${API}/samples`);
      setSamples(res.data.samples || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSamples(false);
    }
  }, []);

  useEffect(() => { loadSamples(); }, []);

  // Add a point sample via click
  const handleMapClick = async ({ lat, lng }) => {
    try {
      await axios.post(`${API}/samples`, {
        geometry: { type: 'Point', coordinates: [lng, lat] },
        class_label: activeClass,
        creator: creator || 'anonymous',
        color: colorForClass(activeClass, customClasses),
      });
      loadSamples();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to save sample');
    }
  };

  // Delete sample
  const handleDeleteSample = async (id) => {
    if (!window.confirm('Remove this sample?')) return;
    try {
      await axios.delete(`${API}/samples/${id}`);
      loadSamples();
    } catch (e) {
      alert('Delete failed');
    }
  };

  // Export GeoJSON
  const exportGeoJSON = () => {
    window.open(`${API}/samples/export/geojson`, '_blank');
  };

  // Add custom class
  const addCustomClass = () => {
    const c = newClass.trim();
    if (!c || customClasses.includes(c)) return;
    setCustomClasses(prev => [...prev, c]);
    setActiveClass(c);
    setNewClass('');
  };

  // Build a simple GeoJSON FeatureCollection of all samples for the GeoJSON layer
  const samplesGeojson = {
    type: 'FeatureCollection',
    features: samples
      .filter(s => s.geometry?.type !== 'Point') // points shown as markers
      .map(s => ({
        type: 'Feature',
        geometry: s.geometry,
        properties: { class_label: s.class_label, id: s.id },
      })),
  };

  const classCounts = samples.reduce((acc, s) => {
    acc[s.class_label] = (acc[s.class_label] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left panel */}
      <div className="w-72 bg-slate-900 border-r border-slate-700 flex flex-col overflow-hidden shrink-0">
        {/* Panel tab switcher */}
        <div className="flex border-b border-slate-700 bg-slate-900">
          {[['digitize','✏️ Digitize'],['samples','🗂 Samples'],['export','⬇ Export']].map(([key, label]) => (
            <button key={key} onClick={() => setPanel(key)}
              className={`flex-1 py-2.5 text-xs font-medium transition-colors ${
                panel === key ? 'border-b-2 border-emerald-500 text-emerald-400' : 'text-slate-400 hover:text-slate-200'
              }`}>
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">

          {/* ── DIGITIZE PANEL ── */}
          {panel === 'digitize' && (
            <>
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wide block mb-2">Active Class</label>
                <div className="flex flex-wrap gap-1.5">
                  {customClasses.map((cls, i) => (
                    <button key={cls} onClick={() => setActiveClass(cls)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all border ${
                        activeClass === cls
                          ? 'text-white border-transparent shadow'
                          : 'bg-slate-800 text-slate-300 border-slate-600 hover:border-slate-400'
                      }`}
                      style={activeClass === cls ? { background: colorForClass(cls, customClasses) } : {}}>
                      {cls}
                    </button>
                  ))}
                </div>
              </div>

              {/* Add new class */}
              <div className="flex gap-2">
                <input placeholder="New class…" value={newClass}
                  onChange={e => setNewClass(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addCustomClass()}
                  className={inputCls} />
                <button onClick={addCustomClass} className={btnSecondary}>+</button>
              </div>

              {/* Creator name */}
              <div>
                <label className="text-xs text-slate-400 block mb-1">Your name (optional)</label>
                <input placeholder="anonymous" value={creator} onChange={e => setCreator(e.target.value)} className={inputCls} />
              </div>

              {/* Toggle digitizing */}
              <button
                onClick={() => setDigitizing(v => !v)}
                className={`w-full py-2.5 rounded-lg font-semibold text-sm transition-all ${
                  digitizing
                    ? 'bg-amber-600 hover:bg-amber-500 text-white'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                }`}>
                {digitizing ? '⏸ Pause — Click map to plot' : '▶ Start Digitizing'}
              </button>

              {digitizing && (
                <div className="bg-emerald-900/40 border border-emerald-700 rounded-lg p-3 text-xs text-emerald-300">
                  <p className="font-semibold mb-1">🖱 Click anywhere on the map</p>
                  <p>A <strong>{activeClass}</strong> sample will be saved at that location.</p>
                </div>
              )}

              {/* Context tile URL */}
              <div>
                <label className="text-xs text-slate-400 block mb-1">Map context layer (optional XYZ tile URL)</label>
                <input placeholder="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  value={contextTileUrl} onChange={e => setContextTileUrl(e.target.value)} className={inputCls} />
              </div>
            </>
          )}

          {/* ── SAMPLES PANEL ── */}
          {panel === 'samples' && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-white">{samples.length} samples</span>
                <button onClick={loadSamples} className={btnSecondary} disabled={loadingSamples}>
                  {loadingSamples ? '⏳' : '🔄'}
                </button>
              </div>

              {/* Class summary */}
              {Object.keys(classCounts).length > 0 && (
                <div className="space-y-2">
                  {Object.entries(classCounts).map(([cls, count]) => (
                    <div key={cls} className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full shrink-0"
                        style={{ background: colorForClass(cls, customClasses) }} />
                      <span className="text-sm text-slate-300 flex-1">{cls}</span>
                      <span className="text-xs font-mono bg-slate-700 text-slate-300 px-2 py-0.5 rounded">{count}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-2 max-h-80 overflow-y-auto">
                {samples.map(s => (
                  <div key={s.id}
                    className="flex items-center gap-2 bg-slate-800 rounded-lg px-3 py-2 border border-slate-700">
                    <span className="w-3 h-3 rounded-full shrink-0"
                      style={{ background: colorForClass(s.class_label, customClasses) }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-slate-200 truncate">{s.class_label}</p>
                      <p className="text-xs text-slate-500">
                        {s.geometry?.type} · {s.creator || 'anon'}
                      </p>
                    </div>
                    <button onClick={() => handleDeleteSample(s.id)} className="text-red-400 hover:text-red-300 text-xs">
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ── EXPORT PANEL ── */}
          {panel === 'export' && (
            <div className="space-y-3">
              <p className="text-sm text-slate-300">
                Download all <strong className="text-white">{samples.length}</strong> digitized samples as GeoJSON.
              </p>
              <button onClick={exportGeoJSON} className={btnPrimary + ' w-full'}>
                ⬇ Download GeoJSON
              </button>
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-400 space-y-1">
                <p className="font-semibold text-slate-300">Class summary</p>
                {Object.entries(classCounts).map(([cls, n]) => (
                  <div key={cls} className="flex justify-between">
                    <span>{cls}</span>
                    <span className="font-mono">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <MapContainer
          center={RWANDA_CENTER}
          zoom={9}
          className="w-full h-full"
          style={{ cursor: digitizing ? 'crosshair' : 'grab' }}>

          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Optional context tile layer */}
          {contextTileUrl && (
            <TileLayer key={contextTileUrl} url={contextTileUrl} opacity={0.7} maxZoom={20} />
          )}

          {/* Non-point samples as GeoJSON */}
          {samplesGeojson.features.length > 0 && (
            <GeoJSON key={JSON.stringify(samplesGeojson)}
              data={samplesGeojson}
              style={f => ({
                color: colorForClass(f.properties.class_label, customClasses),
                weight: 2,
                fillOpacity: 0.4,
              })}
            />
          )}

          {/* Point samples as markers */}
          {samples.filter(s => s.geometry?.type === 'Point').map(s => (
            <SampleMarker
              key={s.id}
              sample={s}
              color={colorForClass(s.class_label, customClasses)}
              onDelete={handleDeleteSample}
            />
          ))}

          <ClickHandler enabled={digitizing} onAdd={handleMapClick} />
        </MapContainer>

        {/* Digitizing status pill */}
        {digitizing && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-50 bg-emerald-700 text-white text-xs px-4 py-1.5 rounded-full shadow-lg font-semibold pointer-events-none">
            ✏️ Click map to add a <em>{activeClass}</em> sample
          </div>
        )}

        {/* Sample count pill */}
        <div className="absolute bottom-4 left-4 z-40 bg-slate-900/80 backdrop-blur rounded-lg px-3 py-1.5 text-xs text-slate-300 border border-slate-700">
          {samples.length} samples · {Object.keys(classCounts).length} classes
        </div>
      </div>
    </div>
  );
}

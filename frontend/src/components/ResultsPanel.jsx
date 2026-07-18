import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

// Colour palette matching backend classify_utils.class_palette()
function classPalette(n) {
  const full = [
    '#1a9850','#66bd63','#a6d96a','#d9ef8b','#ffffbf',
    '#fee08b','#fdae61','#f46d43','#d73027','#a50026',
  ];
  n = Math.max(1, Math.min(n, full.length));
  if (n === 1) return [full[4]];
  const step = (full.length - 1) / (n - 1);
  return Array.from({ length: n }, (_, i) => full[Math.round(i * step)]);
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">
        {typeof value === 'number' ? value.toFixed(2) : value}
      </p>
    </div>
  );
}

function ClassAreaChart({ areas, nClasses }) {
  const palette = classPalette(nClasses || Object.keys(areas).length);
  const data = Object.entries(areas).map(([cls, area], i) => ({
    cls: cls.replace(/ *\([^)]*\)/, ''), // strip breakpoint suffix from label for axis
    fullLabel: cls,
    area: typeof area === 'number' ? parseFloat(area.toFixed(2)) : area,
    color: palette[i] || '#94a3b8',
  }));

  return (
    <ResponsiveContainer width="100%" height={230}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 60 }}>
        <XAxis
          dataKey="cls"
          tick={{ fontSize: 10, fill: '#94a3b8' }}
          angle={-35}
          textAnchor="end"
          interval={0}
        />
        <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
        <Tooltip
          contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
          labelStyle={{ color: '#e2e8f0', fontSize: 12 }}
          formatter={(v, _, p) => [`${v} km²`, p.payload.fullLabel]}
        />
        {data.map((d, i) => (
          <Bar key={i} data={[d]} dataKey="area" fill={d.color} radius={[3, 3, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function Breakpoints({ values }) {
  if (!values?.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {values.map((bp, i) => (
        <span key={i} className="bg-slate-700 text-slate-300 text-xs px-2 py-0.5 rounded font-mono">
          {typeof bp === 'number' ? bp.toFixed(4) : bp}
        </span>
      ))}
    </div>
  );
}

function ColorSwatch({ i, n, label }) {
  const pal = classPalette(n);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-300">
      <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: pal[i] || '#666' }} />
      {label}
    </span>
  );
}

// ── Factor Panel card ─────────────────────────────────────────────────────────

function FactorPanel({ panel, nClasses, factorMeta }) {
  const palette = classPalette(nClasses);
  const meta = factorMeta || {};
  const weightPct = meta.weight_pct;
  const reversed  = meta.reversed || false;
  const desc      = meta.description || '';

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Card header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-slate-750 border-b border-slate-700">
        <span className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-600 text-white font-bold text-sm shrink-0">
          {panel.letter}
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-100 text-sm truncate">{panel.title}</p>
          {weightPct !== undefined && (
            <p className="text-xs text-emerald-400">AHP weight: {weightPct}%</p>
          )}
        </div>
        {reversed && (
          <span className="text-xs bg-amber-700/40 text-amber-300 px-2 py-0.5 rounded shrink-0">
            ↔ Reversed
          </span>
        )}
      </div>

      <div className="p-4 space-y-3">
        {/* AHP weight bar */}
        {weightPct !== undefined && (
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Weight</span>
              <span className="font-bold text-emerald-400">{weightPct}%</span>
            </div>
            <div className="h-1.5 w-full bg-slate-700 rounded-full">
              <div className="h-1.5 bg-emerald-500 rounded-full" style={{ width: `${weightPct}%` }} />
            </div>
          </div>
        )}

        {/* Description */}
        {desc && <p className="text-xs text-slate-400 italic">{desc}</p>}

        {/* Thumbnail */}
        {panel.thumb_url && (
          <img
            src={panel.thumb_url}
            alt={panel.title}
            className="w-full rounded border border-slate-600"
            style={{ imageRendering: 'pixelated' }}
          />
        )}

        {/* Breakpoints */}
        {panel.breakpoints?.length > 0 && (
          <div>
            <p className="text-xs text-slate-500 mb-1">Quantile Breakpoints:</p>
            <Breakpoints values={panel.breakpoints} />
          </div>
        )}

        {/* Area chart */}
        {panel.areas && Object.keys(panel.areas).length > 0 && (
          <div>
            <p className="text-xs text-slate-500 mb-1">Area by Class (km²):</p>
            <ClassAreaChart areas={panel.areas} nClasses={nClasses} />
          </div>
        )}

        {/* Legend swatches */}
        {panel.areas && (
          <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
            {Object.keys(panel.areas).map((cls, i) => (
              <ColorSwatch key={cls} i={i} n={nClasses} label={cls.replace(/ *\([^)]*\)/, '')} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── AHP Table ─────────────────────────────────────────────────────────────────

function AhpTable({ ahpData }) {
  if (!ahpData) return null;
  const { weights_norm, consistency_ratio, lambda_max, factors } = ahpData;
  if (!weights_norm || !factors) return null;

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700">
        <p className="font-semibold text-slate-100 text-sm">AHP Weight Summary</p>
        <p className="text-xs text-slate-400 mt-0.5">
          CR = {typeof consistency_ratio === 'number' ? consistency_ratio.toFixed(4) : '—'}
          {consistency_ratio < 0.1 ? ' ✅ Acceptable' : ' ⚠ Check weights'}
        </p>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-slate-700">
          <tr>
            <th className="text-left px-4 py-2 text-slate-300">Factor</th>
            <th className="text-right px-4 py-2 text-slate-300">Weight</th>
            <th className="text-right px-4 py-2 text-slate-300">%</th>
          </tr>
        </thead>
        <tbody>
          {factors.map((f, i) => (
            <tr key={f} className="border-t border-slate-700">
              <td className="px-4 py-2 text-slate-200">{f}</td>
              <td className="px-4 py-2 text-right font-mono text-slate-200">
                {weights_norm[i]?.toFixed(4)}
              </td>
              <td className="px-4 py-2 text-right font-mono text-emerald-400">
                {(weights_norm[i] * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main exported component ───────────────────────────────────────────────────

export default function ResultsPanel({ result, activeTab, setActiveTab }) {
  if (!result) return null;

  const tabs       = ['Map', 'Statistics', 'Factor Maps / Classify', 'Report'];
  const stats      = result.stats || {};
  const classAreas = result.class_areas_km2 || result.class_areas || {};
  const breakpoints = result.breakpoints || [];
  const nClasses   = result.n_classes || result.classify?.n_classes || Object.keys(classAreas).length || 5;
  const factorMaps = result.factor_maps || {};

  // Build unified factor panel list
  const factorPanels = (() => {
    if (result.classify?.panels?.length > 0) {
      return result.classify.panels.map(p => {
        // Try to find matching factorMaps key by panel name
        const key = Object.keys(factorMaps).find(k =>
          p.name?.includes(k) || p.title?.toLowerCase().includes(k.toLowerCase())
        );
        return { ...p, _meta: key ? factorMaps[key] : undefined };
      });
    }
    if (Object.keys(factorMaps).length > 0) {
      return Object.entries(factorMaps).map(([key, fm], i) => ({
        letter: 'ABCDEFGHIJ'[i],
        name: key,
        title: fm.label || fm.title || key,
        thumb_url: fm.thumb_url,
        areas: fm.areas || fm.class_areas_km2 || {},
        breakpoints: fm.breakpoints || [],
        _meta: fm,
      }));
    }
    return [];
  })();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-slate-700 bg-slate-900 shrink-0">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab === 'Map' && '🗺 '}
            {tab === 'Statistics' && '📊 '}
            {tab === 'Factor Maps' && '🔬 '}
            {tab === 'Factor Maps / Classify' && '🔬 '}
            {tab === 'Report' && '📄 '}
            {tab}
          </button>
        ))}
      </div>

      {/* ── Statistics Tab ─────────────────────────────────────────────────── */}
      {activeTab === 'Statistics' && (
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          <h2 className="text-lg font-bold text-white">
            {result.district} — Statistics
          </h2>

          {/* Metric cards */}
          {Object.keys(stats).length > 0 && (
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(stats).map(([k, v]) => (
                <StatCard key={k} label={k} value={v} />
              ))}
            </div>
          )}

          {/* Class area chart */}
          {Object.keys(classAreas).length > 0 && (
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <p className="text-sm font-semibold text-slate-200 mb-3">Area by Class (km²)</p>
              <div className="flex flex-col xl:flex-row gap-6">
                <div className="flex-1 min-w-0">
                  <ClassAreaChart areas={classAreas} nClasses={nClasses} />
                </div>
                <div className="w-full xl:w-64 h-[230px] shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={Object.entries(classAreas).map(([cls, area], i) => ({ name: cls.replace(/ *\([^)]*\)/, ''), value: typeof area === 'number' ? area : parseFloat(area) }))}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {Object.keys(classAreas).map((cls, index) => (
                          <Cell key={`cell-${index}`} fill={classPalette(nClasses)[index] || '#666'} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                        labelStyle={{ color: '#e2e8f0', fontSize: 12 }}
                        formatter={(v) => `${v.toFixed(2)} km²`}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-4">
                {Object.keys(classAreas).map((cls, i) => (
                  <ColorSwatch key={cls} i={i} n={nClasses} label={cls.replace(/ *\([^)]*\)/, '')} />
                ))}
              </div>
            </div>
          )}

          {/* Breakpoints */}
          {breakpoints.length > 0 && (
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <p className="text-sm font-semibold text-slate-200 mb-2">Classification Breakpoints</p>
              <Breakpoints values={breakpoints} />
            </div>
          )}

          {/* AHP Table (Landfill) */}
          {result.ahp_data && <AhpTable ahpData={result.ahp_data} />}

          {/* Weights used (Landfill) */}
          {result.weights_used && (
            <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-700">
                <p className="font-semibold text-slate-100 text-sm">AHP Weights Used</p>
              </div>
              <div className="p-4 space-y-3">
                {Object.entries(result.weights_used).map(([k, v]) => (
                  <div key={k}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300 capitalize">{k}</span>
                      <span className="font-bold text-emerald-400">{(v * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-700 rounded-full">
                      <div className="h-1.5 bg-emerald-500 rounded-full" style={{ width: `${v * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Data table */}
          {Object.keys(classAreas).length > 0 && (
            <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-700">
                  <tr>
                    <th className="text-left px-4 py-2 text-slate-300">Class</th>
                    <th className="text-right px-4 py-2 text-slate-300">Area (km²)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(classAreas).map(([cls, area], i) => (
                    <tr key={cls} className="border-t border-slate-700 hover:bg-slate-750">
                      <td className="px-4 py-2 text-slate-200">
                        <span className="inline-flex items-center gap-2">
                          <span className="w-3 h-3 rounded-sm shrink-0"
                            style={{ background: classPalette(nClasses)[i] || '#666' }} />
                          {cls}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-slate-200">
                        {typeof area === 'number' ? area.toFixed(2) : area}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Factor Maps / Classify Tab ─────────────────────────────────────────── */}
      {activeTab === 'Factor Maps / Classify' && (
        <div className="flex-1 overflow-y-auto p-5">
          {factorPanels.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 py-20">
              <p className="text-5xl mb-4">🔬</p>
              <p className="text-base font-medium">No factor maps for this module.</p>
              <p className="text-sm mt-1">Factor maps are available for RUSLE and Landfill analyses.</p>
            </div>
          ) : (
            <>
              <h2 className="text-lg font-bold text-white mb-4">
                Factor Maps — {result.district}
                <span className="ml-2 text-sm font-normal text-slate-400">
                  ({nClasses}-class quantile classification)
                </span>
              </h2>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {factorPanels.map((panel, i) => (
                  <FactorPanel
                    key={i}
                    panel={panel}
                    nClasses={nClasses}
                    factorMeta={panel._meta || factorMaps[panel.name] || factorMaps[panel.letter?.toLowerCase()]}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Report Tab ─────────────────────────────────────────────────── */}
      {activeTab === 'Report' && (
        <div className="flex-1 overflow-y-auto p-5 space-y-4 max-w-2xl">
          <h2 className="text-lg font-bold text-white mb-2">Download PDF Report</h2>
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <p className="text-sm text-slate-300 mb-4">
              Generate a comprehensive PDF report containing the analysis metadata, 
              statistics, area by class, and interpretation notes.
            </p>
            <button
              onClick={async () => {
                try {
                  const res = await fetch('http://localhost:5000/api/report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      module_name: result.module_name || 'Environmental',
                      district: result.district || 'Rwanda',
                      date_range: result.start_date && result.end_date ? `${result.start_date} to ${result.end_date}` : (result.year ? String(result.year) : 'Analysis Period'),
                      stats: result.stats || {},
                      class_areas: result.class_areas_km2 || result.class_areas || {},
                      extra_notes: result.extra_notes || 'All analyses are computed on-demand using Google Earth Engine satellite imagery.',
                    })
                  });
                  if (!res.ok) throw new Error('Report generation failed');
                  const blob = await res.blob();
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${(result.module_name || 'Analysis').replace(/ /g, '_')}_${result.district || 'Report'}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  window.URL.revokeObjectURL(url);
                } catch (e) {
                  alert(e.message);
                }
              }}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              📄 Download PDF Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState } from 'react';
import axios from 'axios';

const DISTRICTS = [
  "Bugesera","Burera","Gakenke","Gasabo","Gatsibo",
  "Gicumbi","Gisagara","Huye","Kamonyi","Karongi",
  "Kayonza","Kicukiro","Kirehe","Muhanga","Musanze",
  "Ngoma","Ngororero","Nyabihu","Nyagatare","Nyamagabe",
  "Nyamasheke","Nyanza","Nyarugenge","Nyaruguru","Rubavu",
  "Ruhango","Rulindo","Rusizi","Rutsiro","Rwamagana"
];

const API_BASE_URL = 'http://localhost:5000/api';

const DEFAULT_LANDFILL_WEIGHTS = { river: 30, residential: 25, slope: 20, road: 15, lulc: 10 };
const DEFAULT_LANDFILL_REVERSE = { river: false, residential: false, slope: false, road: false, lulc: false };
const DEFAULT_RUSLE_REVERSE    = { R: false, K: false, LS: false, C: false, P: false };

function SectionTitle({ children }) {
  return <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mt-5 mb-2">{children}</p>;
}

function FormGroup({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-300 mb-1">{label}</label>
      {children}
    </div>
  );
}

const selectCls = "w-full bg-slate-700 text-slate-100 border border-slate-600 rounded p-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500";
const inputCls  = "w-full bg-slate-700 text-slate-100 border border-slate-600 rounded p-2 text-sm";

export default function Sidebar({ onResult, onLoading, onError }) {
  const [module,   setModule]   = useState('ndvi');
  const [district, setDistrict] = useState('Gasabo');
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate,   setEndDate]   = useState('2024-06-30');
  const [year,      setYear]      = useState(2023);
  const [startYear, setStartYear] = useState(2015);
  const [endYear,   setEndYear]   = useState(2024);
  const [gridSize,  setGridSize]  = useState(6);
  const [nClasses,  setNClasses]  = useState(5);

  // Landfill AHP
  const [weights,         setWeights]         = useState(DEFAULT_LANDFILL_WEIGHTS);
  const [landfillReverse, setLandfillReverse] = useState(DEFAULT_LANDFILL_REVERSE);

  // RUSLE factor reversal
  const [rusleReverse, setRusleReverse] = useState(DEFAULT_RUSLE_REVERSE);

  const toggleLandfillReverse = (key) =>
    setLandfillReverse(prev => ({ ...prev, [key]: !prev[key] }));

  const toggleRusleReverse = (key) =>
    setRusleReverse(prev => ({ ...prev, [key]: !prev[key] }));

  // Normalize landfill weights so they always sum to 100
  const normalizeWeights = (changedKey, newVal) => {
    const raw = { ...weights, [changedKey]: Math.max(0, Math.min(100, Number(newVal))) };
    const total = Object.values(raw).reduce((a, b) => a + b, 0);
    if (total === 0) return;
    const normalized = {};
    Object.entries(raw).forEach(([k, v]) => (normalized[k] = Math.round((v / total) * 100)));
    setWeights(normalized);
  };

  const runAnalysis = async () => {
    onLoading(true);
    onError(null);
    try {
      let endpoint = `/${module.replace('_', '-')}`;
      let payload  = { district, n_classes: nClasses };

      if (['ndvi','lst','air_pollution','uhi'].includes(module)) {
        payload.start_date = startDate;
        payload.end_date   = endDate;
      }
      if (module === 'uhi')       payload.grid_size = gridSize;
      if (module === 'rusle') {
        payload.year        = year;
        payload.reverse_r   = rusleReverse.R;
        payload.reverse_k   = rusleReverse.K;
        payload.reverse_ls  = rusleReverse.LS;
        payload.reverse_c   = rusleReverse.C;
        payload.reverse_p   = rusleReverse.P;
      }
      if (module === 'landslide') {
        payload.start_year = startYear;
        payload.end_year   = endYear;
      }
      if (module === 'landfill') {
        // Build custom_weights (fractions summing to 1)
        const total = Object.values(weights).reduce((a, b) => a + b, 0);
        payload.custom_weights = Object.fromEntries(
          Object.entries(weights).map(([k, v]) => [k, v / total])
        );
        payload.reverse_river       = landfillReverse.river;
        payload.reverse_residential = landfillReverse.residential;
        payload.reverse_slope       = landfillReverse.slope;
        payload.reverse_road        = landfillReverse.road;
        payload.reverse_lulc        = landfillReverse.lulc;
      }

      const res = await axios.post(`${API_BASE_URL}${endpoint}`, payload);
      onResult(res.data);
    } catch (err) {
      console.error(err);
      onError(err.response?.data?.detail || err.message);
    } finally {
      onLoading(false);
    }
  };

  const needsDates     = ['ndvi','lst','air_pollution','uhi'].includes(module);
  const isRusle        = module === 'rusle';
  const isLandslide    = module === 'landslide';
  const isLandfill     = module === 'landfill';

  const LANDFILL_FACTOR_LABELS = {
    river:       'Distance from Rivers',
    residential: 'Distance from Residential',
    slope:       'Slope',
    road:        'Road Accessibility',
    lulc:        'Land Cover (LULC)',
  };
  const RUSLE_FACTOR_LABELS = { R: 'Rainfall Erosivity (R)', K: 'Soil Erodibility (K)', LS: 'Slope Length (LS)', C: 'Cover Factor (C)', P: 'Support Practice (P)' };

  return (
    <div className="w-72 bg-slate-900 border-r border-slate-700 flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="p-5 pb-3 border-b border-slate-700">
        <h1 className="text-lg font-bold text-white">Rwanda GeoPortal</h1>
        <p className="text-xs text-emerald-400 mt-0.5">Environmental Analysis Platform</p>
      </div>

      <div className="p-4 flex flex-col gap-3 flex-1">
        {/* Module */}
        <FormGroup label="Analysis Module">
          <select value={module} onChange={e => setModule(e.target.value)} className={selectCls}>
            <option value="ndvi">🌿 NDVI – Vegetation Health</option>
            <option value="lst">🌡 LST – Surface Temperature</option>
            <option value="rusle">🌧 RUSLE – Soil Erosion</option>
            <option value="slope">⛰ Slope & Terrain</option>
            <option value="landfill">🗑 Landfill Siting (AHP)</option>
            <option value="air_pollution">💨 Air Pollution (NO₂)</option>
            <option value="landslide">🏔 Landslide Susceptibility</option>
            <option value="uhi">🏙 Urban Heat Island</option>
          </select>
        </FormGroup>

        {/* District */}
        <FormGroup label="District">
          <select value={district} onChange={e => setDistrict(e.target.value)} className={selectCls}>
            {DISTRICTS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </FormGroup>

        {/* Date inputs */}
        {needsDates && (
          <>
            <FormGroup label="Start Date">
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className={inputCls} />
            </FormGroup>
            <FormGroup label="End Date">
              <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className={inputCls} />
            </FormGroup>
          </>
        )}

        {/* Year */}
        {isRusle && (
          <FormGroup label={`Year: ${year}`}>
            <input type="range" min="2018" max="2024" value={year} onChange={e => setYear(Number(e.target.value))}
              className="w-full accent-emerald-500" />
          </FormGroup>
        )}

        {/* Landslide years */}
        {isLandslide && (
          <>
            <FormGroup label={`Start Year: ${startYear}`}>
              <input type="range" min="1981" max="2024" value={startYear} onChange={e => setStartYear(Number(e.target.value))}
                className="w-full accent-emerald-500" />
            </FormGroup>
            <FormGroup label={`End Year: ${endYear}`}>
              <input type="range" min="1981" max="2024" value={endYear} onChange={e => setEndYear(Number(e.target.value))}
                className="w-full accent-emerald-500" />
            </FormGroup>
          </>
        )}

        {/* UHI grid */}
        {module === 'uhi' && (
          <FormGroup label={`Grid Size: ${gridSize}`}>
            <input type="range" min="3" max="12" value={gridSize} onChange={e => setGridSize(Number(e.target.value))}
              className="w-full accent-emerald-500" />
          </FormGroup>
        )}

        {/* Classification */}
        <SectionTitle>Classification</SectionTitle>
        <FormGroup label={`Number of Classes: ${nClasses}`}>
          <input type="range" min="2" max="10" value={nClasses} onChange={e => setNClasses(Number(e.target.value))}
            className="w-full accent-emerald-500" />
          <div className="flex justify-between text-xs text-slate-500 mt-0.5"><span>2</span><span>10</span></div>
        </FormGroup>

        {/* RUSLE Factor Reversal */}
        {isRusle && (
          <>
            <SectionTitle>Factor Reversal (RUSLE)</SectionTitle>
            <p className="text-xs text-slate-500 -mt-2">Flip scoring direction of any factor (1↔5).</p>
            {Object.entries(RUSLE_FACTOR_LABELS).map(([key, label]) => (
              <label key={key} className="flex items-center gap-2 cursor-pointer hover:bg-slate-800 rounded px-2 py-1">
                <input type="checkbox" checked={rusleReverse[key]} onChange={() => toggleRusleReverse(key)}
                  className="w-4 h-4 accent-emerald-500" />
                <span className="text-sm text-slate-300">Reverse {label.split('(')[0].trim()}</span>
              </label>
            ))}
          </>
        )}

        {/* Landfill AHP Weights + Factor Reversal */}
        {isLandfill && (
          <>
            <SectionTitle>AHP Weights</SectionTitle>
            <p className="text-xs text-slate-500 -mt-2">Adjust and weights auto-normalize to 100%.</p>
            {Object.entries(LANDFILL_FACTOR_LABELS).map(([key, label]) => (
              <div key={key} className="bg-slate-800 rounded p-2 mb-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-300">{label}</span>
                  <span className="text-xs font-bold text-emerald-400">{weights[key]}%</span>
                </div>
                <input type="range" min="1" max="100" value={weights[key]}
                  onChange={e => normalizeWeights(key, e.target.value)}
                  className="w-full h-1.5 accent-emerald-500" />
                <div className="flex items-center gap-2 mt-1.5">
                  <input type="checkbox" id={`rev_${key}`} checked={landfillReverse[key]}
                    onChange={() => toggleLandfillReverse(key)} className="w-3.5 h-3.5 accent-amber-400" />
                  <label htmlFor={`rev_${key}`} className="text-xs text-amber-400 cursor-pointer">Reverse scoring</label>
                </div>
              </div>
            ))}
            <div className="flex justify-between text-xs mt-1 px-1">
              <span className="text-slate-400">Total weight:</span>
              <span className="font-bold text-emerald-400">
                {Object.values(weights).reduce((a,b) => a+b, 0)}%
              </span>
            </div>
          </>
        )}
      </div>

      {/* Run button */}
      <div className="p-4 border-t border-slate-700">
        <button onClick={runAnalysis}
          className="w-full bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white font-bold py-2.5 px-4 rounded-lg transition-all text-sm shadow-lg shadow-emerald-900/40">
          ▶ Run Analysis
        </button>
      </div>
    </div>
  );
}

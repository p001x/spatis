import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import MapViewer from './components/MapViewer';
import ResultsPanel from './components/ResultsPanel';
import RareDataPage from './pages/RareDataPage';
import DigitizationPage from './pages/DigitizationPage';

const NAV_ITEMS = [
  { key: 'analysis',     label: '🌍 Analysis',      desc: 'Environmental Modules' },
  { key: 'rare-data',    label: '🗄 RARE DATA',      desc: 'Dataset Repository' },
  { key: 'digitization', label: '✏️ Digitization',   desc: 'Sample Collection' },
];

function TopNav({ activePage, setActivePage }) {
  return (
    <div className="flex items-center bg-slate-900 border-b border-slate-700 px-4 shrink-0">
      {NAV_ITEMS.map(item => (
        <button
          key={item.key}
          onClick={() => setActivePage(item.key)}
          className={`px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
            activePage === item.key
              ? 'border-emerald-500 text-emerald-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState('analysis');
  const [result,     setResult]     = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);
  const [activeTab,  setActiveTab]  = useState('Map');

  const handleResult = (data) => {
    setResult(data);
    setActiveTab('Map');
  };

  let center = null;
  if (result?.center) {
    if (result.center.type === 'Point') {
      center = [result.center.coordinates[1], result.center.coordinates[0]];
    } else if (Array.isArray(result.center) && result.center.length === 2) {
      center = result.center;
    }
  }

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 overflow-hidden text-slate-100">
      {/* Top Navigation */}
      <TopNav activePage={activePage} setActivePage={setActivePage} />

      {/* Page Content */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── Analysis Page ── */}
        {activePage === 'analysis' && (
          <>
            <Sidebar onResult={handleResult} onLoading={setLoading} onError={setError} />
            <div className="flex-1 flex flex-col overflow-hidden relative">

              {/* Loading overlay */}
              {loading && (
                <div className="absolute inset-0 z-50 bg-slate-950/70 flex items-center justify-center backdrop-blur-sm">
                  <div className="bg-slate-800 p-8 rounded-2xl shadow-2xl text-center border border-slate-700 max-w-sm">
                    <div className="animate-spin rounded-full h-14 w-14 border-b-2 border-emerald-500 mx-auto mb-5" />
                    <p className="text-lg font-semibold text-slate-100">Processing on Google Earth Engine</p>
                    <p className="text-sm text-slate-400 mt-2">This may take 20–40 seconds…</p>
                  </div>
                </div>
              )}

              {/* Error banner */}
              {error && (
                <div className="mx-4 mt-4 z-40 bg-red-900/80 text-red-100 px-5 py-3 rounded-lg border border-red-700 shrink-0">
                  <p className="font-bold text-sm">Analysis Error</p>
                  <p className="text-xs mt-1 break-words">{error}</p>
                </div>
              )}

              {/* Map (always mounted) */}
              <div className="flex-1 relative overflow-hidden">
                <div className={`absolute inset-0 ${activeTab !== 'Map' ? 'invisible' : ''}`}>
                  <MapViewer tileUrl={result?.tile_url} center={center} />
                </div>

                {/* Floating stats pill */}
                {activeTab === 'Map' && result?.stats && (
                  <div className="absolute bottom-5 right-5 z-40 bg-slate-900/90 backdrop-blur rounded-xl p-4 border border-slate-700 min-w-52 shadow-xl">
                    <p className="text-xs font-bold uppercase tracking-wide text-emerald-400 mb-2">
                      {result.district} Summary
                    </p>
                    {Object.entries(result.stats).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-sm py-0.5">
                        <span className="text-slate-400 capitalize">{k}:</span>
                        <span className="font-mono text-slate-200">{typeof v === 'number' ? v.toFixed(3) : v}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Tab pill overlay on map */}
                {result && activeTab === 'Map' && (
                  <div className="absolute top-3 left-1/2 -translate-x-1/2 z-40 flex gap-1 bg-slate-900/80 backdrop-blur rounded-full px-2 py-1.5 border border-slate-700">
                    {['Map','Statistics','Factor Maps / Classify', 'Report'].map(tab => (
                      <button key={tab} onClick={() => setActiveTab(tab)}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                          activeTab === tab
                            ? 'bg-emerald-600 text-white shadow'
                            : 'text-slate-300 hover:text-white hover:bg-slate-700'
                        }`}>
                        {tab}
                      </button>
                    ))}
                  </div>
                )}

                {/* Results Panel (Statistics / Factor Maps) */}
                {result && activeTab !== 'Map' && (
                  <div className="absolute inset-0 bg-slate-950 overflow-hidden">
                    <ResultsPanel result={result} activeTab={activeTab} setActiveTab={setActiveTab} />
                  </div>
                )}

                {/* Empty state */}
                {!result && !loading && (
                  <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 bg-slate-900/80 backdrop-blur rounded-xl px-6 py-4 border border-slate-700 text-center">
                    <p className="text-sm text-slate-300">
                      Select a <strong>module</strong> and <strong>district</strong>, then click <strong>Run Analysis</strong>.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* ── RARE DATA Page ── */}
        {activePage === 'rare-data' && <RareDataPage />}

        {/* ── Digitization Page ── */}
        {activePage === 'digitization' && <DigitizationPage />}
      </div>
    </div>
  );
}

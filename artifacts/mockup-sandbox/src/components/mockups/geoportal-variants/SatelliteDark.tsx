import {
  Leaf, Thermometer, Mountain, Wind, Trash2,
  AlertTriangle, Database, Flame, Edit, Layers,
  Play, ChevronDown, Globe2, Satellite,
} from "lucide-react";

const modules = [
  { label: "NDVI", icon: Leaf, description: "Vegetation Health", active: true },
  { label: "LST", icon: Thermometer, description: "Land Surface Temp" },
  { label: "RUSLE", icon: Mountain, description: "Soil Erosion" },
  { label: "Slope", icon: Mountain, description: "Topography" },
  { label: "Landfill", icon: Trash2, description: "Site Suitability" },
  { label: "Air Pollution", icon: Wind, description: "NO₂ Monitoring" },
  { label: "Landslide", icon: AlertTriangle, description: "Susceptibility" },
  { label: "UHI", icon: Flame, description: "Urban Heat Island" },
  { label: "RARE DATA", icon: Database, description: "Dataset Repository" },
  { label: "Samples", icon: Edit, description: "Digitization" },
];

const classes = [
  { label: "Very Low", pct: 12, color: "#1a9850" },
  { label: "Low", pct: 23, color: "#66bd63" },
  { label: "Moderate", pct: 35, color: "#ffffbf" },
  { label: "High", pct: 20, color: "#fdae61" },
  { label: "Very High", pct: 10, color: "#d73027" },
];

export function SatelliteDark() {
  return (
    <div
      className="flex h-screen w-full overflow-hidden text-sm"
      style={{ background: "#0b0f14", color: "#c9d6e3", fontFamily: "'Inter', sans-serif" }}
    >
      {/* ── Nav sidebar ── */}
      <nav
        className="w-52 shrink-0 flex flex-col"
        style={{ background: "#0d1521", borderRight: "1px solid #1e2d3d" }}
      >
        {/* Logo */}
        <div className="p-4" style={{ borderBottom: "1px solid #1e2d3d" }}>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-7 h-7 rounded flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #00d4aa 0%, #007aff 100%)" }}
            >
              <Satellite className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-bold text-white text-sm leading-tight tracking-wide">RWANDA</div>
              <div className="text-[9px] tracking-[0.15em] uppercase" style={{ color: "#00d4aa" }}>
                GeoPortal
              </div>
            </div>
          </div>
        </div>

        {/* Module list */}
        <div className="flex-1 overflow-y-auto p-2">
          <div
            className="text-[9px] uppercase tracking-widest px-2 py-2 font-semibold"
            style={{ color: "#3d5a73" }}
          >
            Analysis Modules
          </div>
          {modules.map((m) => (
            <div
              key={m.label}
              className="flex items-center gap-2.5 px-2 py-2 rounded-md mb-0.5 cursor-pointer transition-all"
              style={
                m.active
                  ? { background: "rgba(0,212,170,0.12)", color: "#00d4aa", borderLeft: "2px solid #00d4aa" }
                  : { color: "#6b8aa0" }
              }
            >
              <m.icon className="w-3.5 h-3.5 shrink-0" />
              <div>
                <div className="font-medium text-xs leading-tight" style={m.active ? { color: "#00d4aa" } : {}}>
                  {m.label}
                </div>
                <div className="text-[10px] leading-tight" style={{ color: m.active ? "#00a882" : "#3d5a73" }}>
                  {m.description}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="p-3" style={{ borderTop: "1px solid #1e2d3d" }}>
          <div className="flex items-center gap-1.5">
            <Globe2 className="w-3 h-3" style={{ color: "#3d5a73" }} />
            <span className="text-[9px]" style={{ color: "#3d5a73" }}>
              Powered by Google Earth Engine
            </span>
          </div>
        </div>
      </nav>

      {/* ── Controls panel ── */}
      <aside
        className="w-60 shrink-0 flex flex-col overflow-y-auto"
        style={{ background: "#0f1a28", borderRight: "1px solid #1e2d3d" }}
      >
        <div className="p-4" style={{ borderBottom: "1px solid #1e2d3d" }}>
          <div className="flex items-center gap-2 mb-1">
            <Leaf className="w-4 h-4" style={{ color: "#00d4aa" }} />
            <span className="font-semibold text-white text-sm">NDVI Analysis</span>
          </div>
          <p className="text-[11px] leading-relaxed" style={{ color: "#4a6a82" }}>
            Normalized Difference Vegetation Index from Sentinel-2 SR 10 m imagery.
          </p>
        </div>

        <div className="p-4 space-y-4">
          {/* District */}
          <div>
            <label className="text-[10px] uppercase tracking-widest font-semibold block mb-1.5" style={{ color: "#4a6a82" }}>
              District
            </label>
            <div
              className="flex items-center justify-between px-3 py-2 rounded-md cursor-pointer"
              style={{ background: "#162032", border: "1px solid #1e2d3d", color: "#c9d6e3" }}
            >
              <span className="text-sm">Gasabo</span>
              <ChevronDown className="w-3.5 h-3.5" style={{ color: "#3d5a73" }} />
            </div>
          </div>

          {/* Dates */}
          {["Start date", "End date"].map((label, i) => (
            <div key={label}>
              <label className="text-[10px] uppercase tracking-widest font-semibold block mb-1.5" style={{ color: "#4a6a82" }}>
                {label}
              </label>
              <div
                className="px-3 py-2 rounded-md text-sm"
                style={{ background: "#162032", border: "1px solid #1e2d3d", color: "#c9d6e3" }}
              >
                {i === 0 ? "2026-01-16" : "2026-07-16"}
              </div>
            </div>
          ))}

          {/* Classes */}
          <div>
            <label className="text-[10px] uppercase tracking-widest font-semibold block mb-1.5" style={{ color: "#4a6a82" }}>
              Classes: <span style={{ color: "#00d4aa" }}>5</span>
            </label>
            <div className="relative">
              <div className="h-1 rounded-full" style={{ background: "#1e2d3d" }}>
                <div className="h-1 rounded-full w-2/5" style={{ background: "linear-gradient(90deg, #00d4aa, #007aff)" }} />
              </div>
              <div
                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2"
                style={{ left: "calc(40% - 6px)", background: "#00d4aa", borderColor: "#0f1a28" }}
              />
            </div>
          </div>

          {/* Button */}
          <button
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-md font-semibold text-sm transition-all"
            style={{ background: "linear-gradient(135deg, #00d4aa 0%, #007aff 100%)", color: "#0b0f14" }}
          >
            <Play className="w-3.5 h-3.5" />
            Calculate NDVI
          </button>

          {/* Legend */}
          <div style={{ borderTop: "1px solid #1e2d3d", paddingTop: "1rem" }}>
            <p className="text-[10px] uppercase tracking-widest font-semibold mb-2" style={{ color: "#4a6a82" }}>
              Classification
            </p>
            <div className="space-y-1.5">
              {classes.map((c) => (
                <div key={c.label} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: c.color }} />
                  <div className="flex-1 flex justify-between items-center">
                    <span className="text-[11px]" style={{ color: "#6b8aa0" }}>{c.label}</span>
                    <span className="text-[11px] font-mono" style={{ color: "#4a6a82" }}>{c.pct}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </aside>

      {/* ── Map area ── */}
      <main className="flex-1 relative overflow-hidden">
        {/* Simulated satellite map */}
        <div
          className="absolute inset-0"
          style={{
            background: "linear-gradient(160deg, #0a1a0f 0%, #071510 30%, #0d1f0a 60%, #091408 100%)",
          }}
        >
          {/* Grid overlay */}
          <svg className="absolute inset-0 w-full h-full opacity-10">
            <defs>
              <pattern id="grid-dark" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#00d4aa" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid-dark)" />
          </svg>

          {/* Rwanda shape suggestion */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative">
              <div
                className="w-64 h-52 rounded-[40%_60%_55%_45%/45%_55%_60%_40%] opacity-30"
                style={{ background: "radial-gradient(ellipse, #2d7a4f 0%, #1a4a30 50%, transparent 80%)" }}
              />
              <div
                className="absolute inset-8 rounded-[50%_40%_60%_50%/40%_60%_50%_55%] opacity-40"
                style={{ background: "radial-gradient(ellipse, #00d4aa 0%, #2d7a4f 50%, transparent 80%)" }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <span
                  className="text-xs font-semibold uppercase tracking-widest"
                  style={{ color: "#00d4aa", opacity: 0.8 }}
                >
                  Gasabo District
                </span>
              </div>
            </div>
          </div>

          {/* Top status bar */}
          <div
            className="absolute top-0 left-0 right-0 flex items-center justify-between px-4 py-2"
            style={{ background: "rgba(11,15,20,0.8)", borderBottom: "1px solid #1e2d3d" }}
          >
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: "#00d4aa" }} />
                <span className="text-[11px]" style={{ color: "#4a6a82" }}>GEE Ready</span>
              </div>
              <span className="text-[11px]" style={{ color: "#4a6a82" }}>Sentinel-2 SR · 10 m</span>
            </div>
            <div className="flex gap-2">
              {["Map", "Stats", "Classification"].map((t, i) => (
                <div
                  key={t}
                  className="px-3 py-1 rounded text-[11px] font-medium cursor-pointer"
                  style={
                    i === 0
                      ? { background: "rgba(0,212,170,0.15)", color: "#00d4aa", border: "1px solid rgba(0,212,170,0.3)" }
                      : { color: "#3d5a73" }
                  }
                >
                  {t}
                </div>
              ))}
            </div>
          </div>

          {/* Scale bar */}
          <div
            className="absolute bottom-4 right-4 px-2 py-1 rounded text-[10px]"
            style={{ background: "rgba(11,15,20,0.8)", color: "#3d5a73", border: "1px solid #1e2d3d" }}
          >
            0 ──── 10 km
          </div>
        </div>
      </main>
    </div>
  );
}

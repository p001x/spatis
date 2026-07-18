import {
  Leaf, Thermometer, Mountain, Wind, Trash2,
  AlertTriangle, Database, Flame, Edit,
  Play, ChevronDown, TreePine, Globe2,
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
  { label: "Very Low", pct: 12, color: "#a50026" },
  { label: "Low", pct: 23, color: "#f46d43" },
  { label: "Moderate", pct: 35, color: "#fee08b" },
  { label: "High", pct: 20, color: "#66bd63" },
  { label: "Very High", pct: 10, color: "#1a9850" },
];

export function ForestCanopy() {
  return (
    <div
      className="flex h-screen w-full overflow-hidden text-sm"
      style={{ background: "#f2f5f0", color: "#1a2e1a", fontFamily: "'Inter', sans-serif" }}
    >
      {/* ── Nav sidebar ── */}
      <nav
        className="w-52 shrink-0 flex flex-col"
        style={{ background: "#1a3326", color: "#c8ddc8" }}
      >
        {/* Logo */}
        <div className="p-5" style={{ borderBottom: "1px solid #243d2d" }}>
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: "rgba(255,255,255,0.12)" }}
            >
              <TreePine className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <div className="font-bold text-white text-sm leading-tight">Rwanda</div>
              <div className="text-[10px] leading-tight" style={{ color: "#7aad7a" }}>
                Environmental GeoPortal
              </div>
            </div>
          </div>
        </div>

        {/* Module list */}
        <div className="flex-1 overflow-y-auto py-3 px-3">
          <div
            className="text-[9px] uppercase tracking-widest px-2 py-2 font-semibold"
            style={{ color: "#3d6647" }}
          >
            Analysis Modules
          </div>
          {modules.map((m) => (
            <div
              key={m.label}
              className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg mb-0.5 cursor-pointer"
              style={
                m.active
                  ? { background: "#2d7a4f", color: "#ffffff" }
                  : { color: "#7aad7a" }
              }
            >
              <m.icon className="w-3.5 h-3.5 shrink-0" style={m.active ? { color: "#b8f0c8" } : {}} />
              <div>
                <div className="font-medium text-[11px] leading-tight">
                  {m.label}
                </div>
                <div className="text-[10px] leading-tight" style={m.active ? { color: "#a0d8a0" } : { color: "#3d6647" }}>
                  {m.description}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="p-4" style={{ borderTop: "1px solid #243d2d" }}>
          <div className="flex items-center gap-1.5">
            <Globe2 className="w-3 h-3" style={{ color: "#3d6647" }} />
            <span className="text-[10px]" style={{ color: "#3d6647" }}>
              Powered by Google Earth Engine
            </span>
          </div>
        </div>
      </nav>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top header bar */}
        <div
          className="h-12 shrink-0 flex items-center justify-between px-5"
          style={{ background: "#ffffff", borderBottom: "1px solid #dce8d4" }}
        >
          <div className="flex items-center gap-2">
            <Leaf className="w-4 h-4" style={{ color: "#2d7a4f" }} />
            <span className="font-semibold text-sm" style={{ color: "#1a3326" }}>
              NDVI Analysis
            </span>
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: "#e8f5e8", color: "#2d7a4f" }}
            >
              Gasabo · 2026
            </span>
          </div>
          <div className="flex gap-1.5">
            {["Map", "Statistics", "Classification"].map((t, i) => (
              <button
                key={t}
                className="px-3 py-1.5 rounded-md text-[11px] font-medium"
                style={
                  i === 0
                    ? { background: "#2d7a4f", color: "#ffffff" }
                    : { background: "#f2f5f0", color: "#5a7a5a", border: "1px solid #dce8d4" }
                }
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Content: controls + map side by side */}
        <div className="flex-1 flex overflow-hidden">
          {/* Controls */}
          <aside
            className="w-60 shrink-0 overflow-y-auto"
            style={{ background: "#ffffff", borderRight: "1px solid #dce8d4" }}
          >
            <div className="p-4 space-y-4">
              <p className="text-[11px] leading-relaxed" style={{ color: "#5a7a5a" }}>
                Normalized Difference Vegetation Index from Sentinel-2 SR 10 m imagery.
                Cloud-masked median composite.
              </p>

              <div>
                <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "#3a5a3a" }}>
                  District
                </label>
                <div
                  className="flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer"
                  style={{ background: "#f2f5f0", border: "1.5px solid #c8ddc8", color: "#1a3326" }}
                >
                  <span className="text-sm font-medium">Gasabo</span>
                  <ChevronDown className="w-3.5 h-3.5" style={{ color: "#7aad7a" }} />
                </div>
              </div>

              {["Start date", "End date"].map((label, i) => (
                <div key={label}>
                  <label className="text-[11px] font-semibold block mb-1.5" style={{ color: "#3a5a3a" }}>
                    {label}
                  </label>
                  <div
                    className="px-3 py-2 rounded-lg text-sm font-medium"
                    style={{ background: "#f2f5f0", border: "1.5px solid #c8ddc8", color: "#1a3326" }}
                  >
                    {i === 0 ? "2026-01-16" : "2026-07-16"}
                  </div>
                </div>
              ))}

              <div>
                <label className="text-[11px] font-semibold block mb-2" style={{ color: "#3a5a3a" }}>
                  Classification: <span style={{ color: "#2d7a4f" }}>5 classes</span>
                </label>
                <div className="relative h-2 rounded-full" style={{ background: "#dce8d4" }}>
                  <div className="h-2 rounded-full w-2/5" style={{ background: "#2d7a4f" }} />
                  <div
                    className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full shadow-md"
                    style={{ left: "calc(40% - 8px)", background: "#2d7a4f", border: "2px solid white" }}
                  />
                </div>
              </div>

              <button
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-semibold text-sm"
                style={{ background: "#2d7a4f", color: "#ffffff" }}
              >
                <Play className="w-3.5 h-3.5" />
                Calculate NDVI
              </button>

              {/* Legend */}
              <div style={{ borderTop: "1px solid #dce8d4", paddingTop: "1rem" }}>
                <p className="text-[11px] font-semibold mb-2" style={{ color: "#3a5a3a" }}>
                  Legend
                </p>
                <div className="space-y-2">
                  {classes.map((c) => (
                    <div key={c.label} className="flex items-center gap-2.5">
                      <div className="w-3 h-3 rounded" style={{ background: c.color }} />
                      <span className="text-[11px] flex-1" style={{ color: "#5a7a5a" }}>{c.label}</span>
                      <div
                        className="h-1.5 rounded-full"
                        style={{ width: `${c.pct * 1.5}px`, background: c.color, opacity: 0.7 }}
                      />
                      <span className="text-[10px] w-7 text-right" style={{ color: "#7aad7a" }}>{c.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </aside>

          {/* Map */}
          <div className="flex-1 relative" style={{ background: "#2a4a2a" }}>
            <div
              className="absolute inset-0"
              style={{
                background: "linear-gradient(145deg, #1a4a2a 0%, #2d6040 35%, #1e5530 65%, #143820 100%)",
              }}
            >
              {/* Topographic lines */}
              <svg className="absolute inset-0 w-full h-full opacity-15">
                {[100, 180, 250, 320, 400].map((y) => (
                  <ellipse key={y} cx="50%" cy="45%" rx={`${y}px`} ry={`${y * 0.6}px`}
                    fill="none" stroke="#7aad7a" strokeWidth="1" />
                ))}
              </svg>

              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <div
                    className="w-48 h-36 mx-auto rounded-[45%_55%_50%_50%/40%_50%_60%_55%] opacity-50"
                    style={{ background: "radial-gradient(ellipse, #4a9a5a 0%, #2d6040 60%, transparent 80%)" }}
                  />
                  <p className="text-xs mt-4 font-medium" style={{ color: "#7aad7a" }}>Gasabo District</p>
                </div>
              </div>

              {/* Stats overlay bottom */}
              <div
                className="absolute bottom-4 left-4 right-4 rounded-xl p-3 flex gap-4"
                style={{ background: "rgba(20,40,20,0.85)", border: "1px solid rgba(122,173,122,0.2)" }}
              >
                {[
                  { label: "Mean NDVI", value: "0.42" },
                  { label: "Max NDVI", value: "0.81" },
                  { label: "Coverage", value: "94.2%" },
                  { label: "Valid px", value: "18,432" },
                ].map((s) => (
                  <div key={s.label} className="flex-1 text-center">
                    <div className="text-sm font-bold" style={{ color: "#b8ddb8" }}>{s.value}</div>
                    <div className="text-[10px]" style={{ color: "#5a7a5a" }}>{s.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

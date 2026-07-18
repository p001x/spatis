import {
  Leaf, Thermometer, Mountain, Wind, Trash2,
  AlertTriangle, Database, Flame, Edit,
  Play, ChevronDown, BarChart3, MapPin, Layers,
} from "lucide-react";

const modules = [
  { label: "NDVI", icon: Leaf, description: "Vegetation Health", active: true, color: "#22c55e" },
  { label: "LST", icon: Thermometer, description: "Land Surface Temp", color: "#f97316" },
  { label: "RUSLE", icon: Mountain, description: "Soil Erosion", color: "#eab308" },
  { label: "Slope", icon: Mountain, description: "Topography", color: "#8b5cf6" },
  { label: "Landfill", icon: Trash2, description: "Site Suitability", color: "#ec4899" },
  { label: "Air Pollution", icon: Wind, description: "NO₂ Monitoring", color: "#06b6d4" },
  { label: "Landslide", icon: AlertTriangle, description: "Susceptibility", color: "#ef4444" },
  { label: "UHI", icon: Flame, description: "Urban Heat Island", color: "#f97316" },
  { label: "RARE DATA", icon: Database, description: "Dataset Repository", color: "#6366f1" },
  { label: "Samples", icon: Edit, description: "Digitization", color: "#14b8a6" },
];

const bars = [
  { label: "Very Low", value: 12, color: "#1a9850" },
  { label: "Low", value: 24, color: "#66bd63" },
  { label: "Moderate", value: 37, color: "#ffffbf" },
  { label: "High", value: 19, color: "#fdae61" },
  { label: "Very High", value: 8, color: "#d73027" },
];

export function DataTerrain() {
  return (
    <div
      className="flex h-screen w-full overflow-hidden"
      style={{ background: "#f1f5f9", color: "#1e293b", fontFamily: "'Inter', sans-serif", fontSize: "13px" }}
    >
      {/* ── Slim icon rail ── */}
      <div
        className="w-14 shrink-0 flex flex-col items-center py-3 gap-2"
        style={{ background: "#0f1f3d", borderRight: "1px solid #1a3060" }}
      >
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center mb-2"
          style={{ background: "linear-gradient(135deg, #f59e0b, #ef4444)" }}
        >
          <Layers className="w-4 h-4 text-white" />
        </div>
        {modules.map((m) => (
          <div
            key={m.label}
            className="w-9 h-9 rounded-lg flex items-center justify-center cursor-pointer transition-all"
            title={m.label}
            style={
              m.active
                ? { background: "rgba(245,158,11,0.18)", border: "1.5px solid #f59e0b" }
                : { background: "rgba(255,255,255,0.04)" }
            }
          >
            <m.icon
              className="w-4 h-4"
              style={{ color: m.active ? "#f59e0b" : "#3d5a80" }}
            />
          </div>
        ))}
      </div>

      {/* ── Full left panel ── */}
      <div
        className="w-56 shrink-0 flex flex-col"
        style={{ background: "#172040", color: "#94a3b8" }}
      >
        {/* Header */}
        <div className="px-4 pt-4 pb-3" style={{ borderBottom: "1px solid #1e3060" }}>
          <div className="font-bold text-white text-sm">Rwanda GeoPortal</div>
          <div className="text-[10px] mt-0.5" style={{ color: "#475569" }}>
            Environmental Intelligence Platform
          </div>
        </div>

        {/* Active module detail */}
        <div className="p-4" style={{ borderBottom: "1px solid #1e3060" }}>
          <div className="flex items-center gap-2 mb-3">
            <div
              className="w-6 h-6 rounded flex items-center justify-center"
              style={{ background: "rgba(34,197,94,0.15)" }}
            >
              <Leaf className="w-3.5 h-3.5" style={{ color: "#22c55e" }} />
            </div>
            <span className="font-semibold text-white text-xs">NDVI Analysis</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "#475569" }}>District</div>
              <div
                className="flex items-center justify-between px-2.5 py-1.5 rounded-md"
                style={{ background: "#0f1f3d", border: "1px solid #1e3060" }}
              >
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-3 h-3" style={{ color: "#f59e0b" }} />
                  <span className="text-xs text-white">Gasabo</span>
                </div>
                <ChevronDown className="w-3 h-3" style={{ color: "#475569" }} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {["Start", "End"].map((t, i) => (
                <div key={t}>
                  <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "#475569" }}>{t}</div>
                  <div
                    className="px-2 py-1.5 rounded-md text-[11px] text-white"
                    style={{ background: "#0f1f3d", border: "1px solid #1e3060" }}
                  >
                    {i === 0 ? "Jan 2026" : "Jul 2026"}
                  </div>
                </div>
              ))}
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <div className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>Classes</div>
                <div
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold"
                  style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b" }}
                >
                  5
                </div>
              </div>
              <div className="relative h-1.5 rounded-full" style={{ background: "#1e3060" }}>
                <div className="h-1.5 rounded-full" style={{ width: "40%", background: "#f59e0b" }} />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full"
                  style={{ left: "calc(40% - 7px)", background: "#f59e0b", border: "2px solid #172040" }}
                />
              </div>
            </div>

            <button
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-bold"
              style={{ background: "#f59e0b", color: "#0f1f3d" }}
            >
              <Play className="w-3 h-3" />
              Run Analysis
            </button>
          </div>
        </div>

        {/* Stats cards */}
        <div className="p-3 space-y-2">
          <div className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>Results</div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "Mean", value: "0.42" },
              { label: "Max", value: "0.81" },
              { label: "Area (km²)", value: "167" },
              { label: "Confidence", value: "94%" },
            ].map((s) => (
              <div
                key={s.label}
                className="p-2 rounded-lg"
                style={{ background: "#0f1f3d", border: "1px solid #1e3060" }}
              >
                <div className="text-sm font-bold text-white">{s.value}</div>
                <div className="text-[10px]" style={{ color: "#475569" }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Map ── */}
      <div className="flex-1 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(135deg, #1e3a2f 0%, #2d5a3d 40%, #1a4a30 70%, #0f2a1a 100%)" }}
        >
          {/* Grid */}
          <svg className="absolute inset-0 w-full h-full opacity-10">
            <defs>
              <pattern id="grid-dt" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#94a3b8" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid-dt)" />
          </svg>

          {/* District blob */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="w-56 h-44 rounded-[40%_60%_55%_45%/45%_55%_60%_40%] opacity-60"
              style={{ background: "radial-gradient(ellipse, #f59e0b55 0%, #22c55e44 50%, transparent 80%)" }}
            />
          </div>

          {/* Top toolbar */}
          <div
            className="absolute top-0 left-0 right-0 flex items-center gap-3 px-4 py-2.5"
            style={{ background: "rgba(15,31,61,0.9)", borderBottom: "1px solid rgba(245,158,11,0.2)" }}
          >
            <div className="flex gap-1">
              {["Map", "Stats", "Classification"].map((t, i) => (
                <button
                  key={t}
                  className="px-3 py-1 rounded text-[11px] font-medium"
                  style={
                    i === 0
                      ? { background: "#f59e0b", color: "#0f1f3d" }
                      : { color: "#475569" }
                  }
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="flex-1" />
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full" style={{ background: "#22c55e" }} />
              <span className="text-[11px]" style={{ color: "#475569" }}>GEE · Sentinel-2 SR 10m</span>
            </div>
          </div>

          {/* Right: bar chart overlay */}
          <div
            className="absolute right-4 top-14 bottom-4 w-52 rounded-xl p-4 flex flex-col gap-3"
            style={{ background: "rgba(15,31,61,0.92)", border: "1px solid rgba(245,158,11,0.15)" }}
          >
            <div className="flex items-center gap-2">
              <BarChart3 className="w-3.5 h-3.5" style={{ color: "#f59e0b" }} />
              <span className="text-xs font-semibold text-white">Classification</span>
            </div>
            <div className="flex-1 flex flex-col justify-center gap-2.5">
              {bars.map((b) => (
                <div key={b.label} className="space-y-1">
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-sm" style={{ background: b.color }} />
                      <span className="text-[11px]" style={{ color: "#94a3b8" }}>{b.label}</span>
                    </div>
                    <span className="text-[11px] font-mono" style={{ color: "#f59e0b" }}>{b.value}%</span>
                  </div>
                  <div className="h-1.5 rounded-full" style={{ background: "#1e3060" }}>
                    <div
                      className="h-1.5 rounded-full"
                      style={{ width: `${b.value * 2.5}px`, background: b.color, maxWidth: "100%" }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div style={{ borderTop: "1px solid #1e3060", paddingTop: "0.75rem" }}>
              <div className="text-[10px] mb-1.5" style={{ color: "#475569" }}>Coverage gradient</div>
              <div
                className="h-3 rounded"
                style={{
                  background: "linear-gradient(90deg, #1a9850, #66bd63, #ffffbf, #fdae61, #d73027)",
                }}
              />
              <div className="flex justify-between mt-1">
                <span className="text-[9px]" style={{ color: "#475569" }}>Low</span>
                <span className="text-[9px]" style={{ color: "#475569" }}>High</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

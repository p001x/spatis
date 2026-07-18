import { useState, useEffect, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { Loader2, Trash2, FileText, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api, LandfillResult } from "@/lib/api";
import { DistrictMap, LegendItem } from "@/components/DistrictMap";

const DISTRICTS = [
  "Bugesera","Burera","Gakenke","Gasabo","Gatsibo","Gicumbi","Gisagara",
  "Huye","Kamonyi","Karongi","Kayonza","Kicukiro","Kirehe","Muhanga",
  "Musanze","Ngoma","Ngororero","Nyabihu","Nyagatare","Nyamagabe",
  "Nyamasheke","Nyanza","Nyarugenge","Nyaruguru","Rubavu","Ruhango",
  "Rulindo","Rusizi","Rutsiro","Rwamagana",
];

const FACTOR_KEYS = ["river", "residential", "slope", "road", "lulc"] as const;
type FactorKey = typeof FACTOR_KEYS[number];

const FACTOR_LABELS: Record<FactorKey, string> = {
  river: "River Distance",
  residential: "Residential Distance",
  slope: "Slope",
  road: "Road Accessibility",
  lulc: "Land Cover",
};

const DEFAULT_WEIGHTS: Record<FactorKey, number> = {
  river: 30, residential: 25, slope: 20, road: 15, lulc: 10,
};

const SUITABILITY_LEGEND: LegendItem[] = [
  { color: "#d73027", label: "Unsuitable (<2)" },
  { color: "#f46d43", label: "Marginally Suitable (2–3)" },
  { color: "#fee08b", label: "Moderately Suitable (3–4)" },
  { color: "#1a9850", label: "Highly Suitable (4–5)" },
];

const SCORE_LEGEND: LegendItem[] = [
  { color: "#1a9850", label: "Score 5 – Most suitable" },
  { color: "#d9ef8b", label: "Score 4" },
  { color: "#fee08b", label: "Score 3" },
  { color: "#f46d43", label: "Score 2" },
  { color: "#d73027", label: "Score 1 – Least suitable" },
];

const CLASS_COLOR_LIST = ["#d73027", "#fc8d59", "#fee08b", "#1a9850"];

function loadWeights(district: string): Record<FactorKey, number> {
  try {
    const stored = localStorage.getItem(`landfill_weights_${district}`);
    if (stored) return { ...DEFAULT_WEIGHTS, ...JSON.parse(stored) };
  } catch { /* ignore */ }
  return { ...DEFAULT_WEIGHTS };
}

function saveWeights(district: string, w: Record<FactorKey, number>) {
  try { localStorage.setItem(`landfill_weights_${district}`, JSON.stringify(w)); } catch { /* ignore */ }
}

/** Normalize weight record so values sum to 100. */
function normalize(w: Record<FactorKey, number>): Record<FactorKey, number> {
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  if (total === 0) return { ...DEFAULT_WEIGHTS };
  return Object.fromEntries(
    FACTOR_KEYS.map((k) => [k, Math.round((w[k] / total) * 1000) / 10])
  ) as Record<FactorKey, number>;
}

/** North arrow for thumbnail overlays */
function SmallNorthArrow() {
  return (
    <svg width="18" height="22" viewBox="0 0 28 36" fill="none">
      <polygon points="14,2 20,18 14,14 8,18" fill="#111" />
      <polygon points="14,34 8,18 14,22 20,18" fill="#888" />
      <text x="14" y="10" textAnchor="middle" fontSize="8" fontWeight="bold" fill="#fff" dy="-1">N</text>
    </svg>
  );
}

/** Factor map card with cartographic overlays */
function FactorMapCard({ factorKey, factor, analysisDate }: {
  factorKey: string;
  factor: LandfillResult["factor_maps"][string];
  analysisDate: string;
}) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{factor.label}</span>
        <span className="bg-primary/10 text-primary text-xs font-semibold px-2 py-0.5 rounded-full">
          {factor.weight_pct}%
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">{factor.description}</p>
      {factor.reversed && (
        <p className="text-xs text-amber-600 font-medium">⟳ Reversed scoring</p>
      )}
      {/* Map with cartographic overlays */}
      <div className="relative w-full rounded overflow-hidden border">
        <img
          src={factor.thumb_url}
          alt={`${factor.label} map`}
          className="w-full block"
        />
        {/* Title */}
        <div className="absolute top-0 left-0 right-0 text-center bg-black/50 text-white text-[10px] font-semibold py-0.5 px-1 leading-tight">
          {factor.label} · Score 1–5 · Weight {factor.weight_pct}%
        </div>
        {/* North arrow */}
        <div className="absolute top-5 right-1 bg-white/85 rounded p-0.5">
          <SmallNorthArrow />
        </div>
        {/* Score legend */}
        <div className="absolute bottom-4 right-1 bg-white/85 rounded p-1 text-[8px] leading-tight">
          {[
            { c: "#1a9850", l: "5" }, { c: "#d9ef8b", l: "4" }, { c: "#fee08b", l: "3" },
            { c: "#f46d43", l: "2" }, { c: "#d73027", l: "1" },
          ].map(({ c, l }) => (
            <div key={l} className="flex items-center gap-0.5">
              <span className="w-2.5 h-2.5 inline-block rounded-sm border border-gray-300" style={{ background: c }} />
              <span>{l}</span>
            </div>
          ))}
        </div>
        {/* Source / date */}
        <div className="absolute bottom-0 left-0 right-0 bg-black/40 text-white text-[8px] text-center py-0.5 px-1">
          GEE · ESA WorldCover · USGS · {analysisDate}
        </div>
      </div>
      <a
        href={factor.download_url}
        className="text-xs text-primary underline"
        target="_blank"
        rel="noreferrer"
      >
        ↓ Download GeoTIFF
      </a>
    </div>
  );
}

/** Print the report in a new window */
function printReport(data: LandfillResult, analysisDate: string) {
  const total = Object.values(data.class_areas_km2).reduce((a, b) => a + b, 0);

  const factorRows = Object.entries(data.factor_maps).map(([, f]) => `
    <tr>
      <td>${f.label}</td>
      <td style="text-align:center">${f.weight_pct}%</td>
      <td>${f.reversed ? "⟳ Reversed" : "Normal"}</td>
      <td style="font-size:11px;color:#555">${f.description}</td>
    </tr>`).join("");

  const matrixLabels = data.ahp_data.factor_labels;
  const matrixRows = data.ahp_data.matrix.map((row, i) => `
    <tr>
      <td><strong>${matrixLabels[i]}</strong></td>
      ${row.map((v) => `<td style="text-align:center">${v.toFixed(2)}</td>`).join("")}
    </tr>`).join("");

  const areaRows = Object.entries(data.class_areas_km2).map(([cls, km2], i) => `
    <tr>
      <td>${cls}</td>
      <td style="text-align:right">${km2} km²</td>
      <td style="text-align:right">${total > 0 ? ((km2 / total) * 100).toFixed(1) : "—"}%</td>
    </tr>`).join("");

  const factorThumbs = Object.entries(data.factor_maps).map(([, f]) => `
    <div style="break-inside:avoid;margin-bottom:12px;border:1px solid #ddd;border-radius:6px;padding:8px">
      <p style="margin:0 0 4px;font-weight:600;font-size:13px">${f.label} — Weight: ${f.weight_pct}%</p>
      <p style="margin:0 0 6px;font-size:11px;color:#555">${f.description}</p>
      <img src="${f.thumb_url}" style="width:100%;border-radius:4px;border:1px solid #eee" alt="${f.label}" />
      <p style="margin:4px 0 0;font-size:10px;color:#888">Score 1 (Least suitable) → 5 (Most suitable) · Source: Google Earth Engine</p>
    </div>`).join("");

  const hsKm2 = data.class_areas_km2["Highly Suitable (4–5)"] ?? 0;
  const unKm2 = data.class_areas_km2["Unsuitable (<2)"] ?? 0;
  const hsPct = total > 0 ? ((hsKm2 / total) * 100).toFixed(1) : "0";
  const unPct = total > 0 ? ((unKm2 / total) * 100).toFixed(1) : "0";

  const interpretation = `
    The multi-criteria weighted overlay analysis for <strong>${data.district}</strong> district identifies 
    <strong>${hsPct}%</strong> of the study area (${hsKm2} km²) as Highly Suitable for landfill site development, 
    while <strong>${unPct}%</strong> (${unKm2} km²) is classified as Unsuitable. 
    The analysis applies AHP-derived weights, with River Distance (${data.factor_maps.river?.weight_pct ?? 30}%) 
    and Residential Distance (${data.factor_maps.residential?.weight_pct ?? 25}%) being the primary criteria, 
    reflecting the importance of environmental protection and community safety. 
    Areas with low suitability are concentrated near water bodies, settlements, and steep terrain. 
    Decision-makers should focus site investigations in the Highly Suitable zones while strictly 
    avoiding Unsuitable areas to minimise environmental impact and regulatory risk.
    The AHP consistency ratio (CR = ${data.ahp_data.cr.toFixed(2)}) confirms the weight assignments are 
    ${data.ahp_data.consistent ? "acceptable (CR < 0.10)" : "inconsistent — consider revising weights"}.`;

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Landfill Suitability Report — ${data.district}</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #222; margin: 0; padding: 24px 36px; }
    h1 { font-size: 20px; margin: 0 0 2px; color: #1a5c2e; }
    h2 { font-size: 15px; border-bottom: 2px solid #1a5c2e; padding-bottom: 4px; margin: 20px 0 10px; color: #1a5c2e; }
    h3 { font-size: 13px; margin: 12px 0 6px; }
    .header-bar { background: #1a5c2e; color: #fff; padding: 12px 18px; border-radius: 6px; margin-bottom: 20px; }
    .header-bar p { margin: 2px 0; font-size: 12px; opacity: 0.9; }
    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
    .stat-card { border: 1px solid #ddd; border-radius: 6px; padding: 10px 14px; }
    .stat-card .val { font-size: 22px; font-weight: 700; color: #1a5c2e; }
    .stat-card .lbl { font-size: 11px; color: #666; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 12px; }
    th { background: #f0f0f0; text-align: left; padding: 6px 8px; border: 1px solid #ddd; }
    td { padding: 5px 8px; border: 1px solid #ddd; vertical-align: top; }
    tr:nth-child(even) td { background: #fafafa; }
    .cr-box { display: inline-block; padding: 6px 14px; border-radius: 4px; font-size: 13px; font-weight: 600; margin-top: 6px; }
    .cr-good { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .cr-bad  { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .factor-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .final-map img { width: 100%; border-radius: 6px; border: 1px solid #ddd; }
    .interpretation { background: #f8f9fa; border-left: 4px solid #1a5c2e; padding: 10px 14px; border-radius: 0 6px 6px 0; line-height: 1.6; }
    .footer { margin-top: 24px; padding-top: 10px; border-top: 1px solid #ddd; font-size: 11px; color: #888; }
    @media print {
      body { padding: 12px 20px; }
      .no-print { display: none !important; }
      @page { margin: 1.5cm; }
    }
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom:16px">
    <button onclick="window.print()" style="background:#1a5c2e;color:#fff;border:none;border-radius:5px;padding:8px 18px;cursor:pointer;font-size:13px">
      🖨 Print / Save as PDF
    </button>
  </div>

  <div class="header-bar">
    <h1>Landfill Site Suitability Analysis Report</h1>
    <p><strong>District:</strong> ${data.district}, Rwanda &nbsp;|&nbsp;
       <strong>Method:</strong> Weighted Overlay (AHP) &nbsp;|&nbsp;
       <strong>Generated:</strong> ${analysisDate}</p>
    <p><strong>Data sources:</strong> Google Earth Engine · ESA WorldCover 2021 · USGS SRTM · JRC Global Surface Water · CARTO</p>
  </div>

  <h2>Summary Metrics</h2>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="val">${data.stats["Total Area (km²)"]}</div>
      <div class="lbl">Total Area (km²)</div>
    </div>
    <div class="stat-card">
      <div class="val">${data.stats["Highly Suitable (km²)"]}</div>
      <div class="lbl">Highly Suitable (km²) — ${hsPct}%</div>
    </div>
    <div class="stat-card">
      <div class="val">${data.stats["Unsuitable (km²)"]}</div>
      <div class="lbl">Unsuitable (km²) — ${unPct}%</div>
    </div>
  </div>

  <h2>Factor Weights &amp; Configuration</h2>
  <table>
    <thead><tr><th>Factor / Criterion</th><th>Weight</th><th>Direction</th><th>Description</th></tr></thead>
    <tbody>${factorRows}</tbody>
  </table>

  <h2>AHP Consistency Analysis</h2>
  <p>The implied AHP pairwise comparison matrix is derived from the assigned weights (A<sub>ij</sub> = w<sub>i</sub> / w<sub>j</sub>).</p>
  <table>
    <thead>
      <tr><th></th>${matrixLabels.map((l) => `<th>${l}</th>`).join("")}</tr>
    </thead>
    <tbody>${matrixRows}</tbody>
  </table>
  <p>λ<sub>max</sub> = ${data.ahp_data.lambda_max} &nbsp;|&nbsp; CI = ${data.ahp_data.ci.toFixed(4)} &nbsp;|&nbsp; RI (n=${data.ahp_data.n}) = ${data.ahp_data.ri} &nbsp;|&nbsp; <strong>CR = ${data.ahp_data.cr.toFixed(4)}</strong></p>
  <div class="cr-box ${data.ahp_data.consistent ? "cr-good" : "cr-bad"}">
    CR = ${data.ahp_data.cr.toFixed(4)} — ${data.ahp_data.consistent ? "✓ Consistent (CR < 0.10)" : "✗ Inconsistent — revise weights"}
  </div>

  <h2>Factor Maps</h2>
  <div class="factor-grid">${factorThumbs}</div>

  <h2>Final Suitability Map</h2>
  <div class="final-map" style="break-inside:avoid">
    <p style="font-size:12px;color:#555;margin-bottom:6px">
      Weighted overlay of all five criteria for <strong>${data.district}</strong>.
      Coordinate system: WGS 84 (EPSG:4326) · Resolution: 100 m · Date: ${analysisDate}
    </p>
    <img src="${data.thumb_url}" alt="Final Suitability Map" />
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;font-size:11px">
      ${SUITABILITY_LEGEND.map((l) =>
        `<span style="display:flex;align-items:center;gap:4px">
           <span style="width:14px;height:14px;background:${l.color};border-radius:2px;border:1px solid #ccc;display:inline-block"></span>
           ${l.label}
         </span>`
      ).join("")}
    </div>
    <p style="font-size:10px;color:#888;margin-top:4px">
      ↑ North · Scale: varies by zoom · Source: Google Earth Engine
    </p>
  </div>

  <h2>Suitability Class Areas</h2>
  <table>
    <thead><tr><th>Suitability Class</th><th style="text-align:right">Area (km²)</th><th style="text-align:right">Coverage (%)</th></tr></thead>
    <tbody>${areaRows}</tbody>
    <tfoot><tr><th>Total</th><th style="text-align:right">${total.toFixed(2)} km²</th><th style="text-align:right">100.0%</th></tr></tfoot>
  </table>

  <h2>Interpretation</h2>
  <div class="interpretation">${interpretation}</div>

  <div class="footer">
    Rwanda Environmental GeoPortal · Powered by Google Earth Engine · Generated ${analysisDate}<br/>
    This report is for planning and research purposes only. Field verification is required before site selection.
  </div>
</body>
</html>`;

  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) { alert("Allow pop-ups to open the report."); return; }
  win.document.write(html);
  win.document.close();
}

// ── Main component ──────────────────────────────────────────────────────────

export function LandfillPage() {
  const [district, setDistrict] = useState("Nyagatare");
  const [nClasses, setNClasses] = useState(4);

  // Weights (stored per-district in localStorage)
  const [weights, setWeights] = useState<Record<FactorKey, number>>(() => loadWeights("Nyagatare"));

  // Reverse toggles
  const [reverseRiver, setReverseRiver] = useState(false);
  const [reverseResidential, setReverseResidential] = useState(false);
  const [reverseSlope, setReverseSlope] = useState(false);
  const [reverseRoad, setReverseRoad] = useState(false);
  const [reverseLulc, setReverseLulc] = useState(false);

  // Reload weights when district changes
  useEffect(() => {
    setWeights(loadWeights(district));
  }, [district]);

  const handleWeightChange = useCallback((key: FactorKey, val: number) => {
    setWeights((prev) => {
      const next = { ...prev, [key]: val };
      saveWeights(district, next);
      return next;
    });
  }, [district]);

  const normalizedWeights = normalize(weights);
  const totalRaw = Object.values(weights).reduce((a, b) => a + b, 0);

  // AHP CR from normalized weights (always 0 for direct-entry weights — consistent by definition)
  const ahpCR = 0.0;

  const { mutate, data, isPending, error } = useMutation<LandfillResult, Error>({
    mutationFn: () =>
      api.landfill({
        district,
        n_classes: nClasses,
        reverse_river: reverseRiver,
        reverse_residential: reverseResidential,
        reverse_slope: reverseSlope,
        reverse_road: reverseRoad,
        reverse_lulc: reverseLulc,
        custom_weights: Object.fromEntries(
          FACTOR_KEYS.map((k) => [k, normalizedWeights[k] / 100])
        ) as Record<string, number>,
      }),
  });

  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });

  return (
    <div className="flex h-full">
      {/* ── Controls sidebar ─────────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-r bg-card flex flex-col gap-4 p-4 overflow-y-auto">
        <div className="flex items-center gap-2 text-primary font-semibold text-base">
          <Trash2 className="w-5 h-5" />
          Landfill Suitability
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          AHP-weighted overlay for landfill site selection using river distance, residential
          distance, slope, road accessibility, and land cover.
        </p>

        {/* District */}
        <div className="space-y-1">
          <Label>District</Label>
          <Select value={district} onValueChange={setDistrict}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {DISTRICTS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {/* Classes */}
        <div className="space-y-2">
          <Label>Classes: {nClasses}</Label>
          <Slider min={2} max={10} step={1} value={[nClasses]} onValueChange={([v]) => setNClasses(v)} />
        </div>

        {/* ── AHP Weight Sliders ── */}
        <div className="space-y-3">
          <div>
            <Label className="text-sm font-semibold">Factor Weights (AHP)</Label>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Adjust weights per criterion. Values auto-normalize to 100%.
            </p>
          </div>
          {FACTOR_KEYS.map((key) => {
            const pct = normalizedWeights[key];
            return (
              <div key={key} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{FACTOR_LABELS[key]}</span>
                  <span className="font-semibold text-primary tabular-nums">{pct.toFixed(1)}%</span>
                </div>
                <Slider
                  min={1}
                  max={99}
                  step={1}
                  value={[weights[key]]}
                  onValueChange={([v]) => handleWeightChange(key, v)}
                />
              </div>
            );
          })}

          {/* AHP CR indicator */}
          <div className="rounded bg-green-50 border border-green-200 px-3 py-2 text-xs">
            <span className="font-semibold text-green-800">CR = {ahpCR.toFixed(2)}</span>
            <span className="text-green-700 ml-1">— Consistent ✓</span>
            <p className="text-green-600 mt-0.5 text-[10px]">
              Direct weight entry is always consistent (CR = 0). The AHP matrix and CR shown in
              the Report are derived from these weights.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs"
            onClick={() => {
              setWeights({ ...DEFAULT_WEIGHTS });
              saveWeights(district, { ...DEFAULT_WEIGHTS });
            }}
          >
            Reset to defaults
          </Button>
        </div>

        {/* ── Reverse Factors ── */}
        <div className="space-y-2">
          <Label className="text-sm font-semibold">Reverse Factors</Label>
          <p className="text-xs text-muted-foreground">
            Invert the scoring direction for a factor (e.g. "closer to roads = better").
          </p>
          {[
            { label: "River distance",       value: reverseRiver,       setter: setReverseRiver },
            { label: "Residential distance", value: reverseResidential,  setter: setReverseResidential },
            { label: "Slope",                value: reverseSlope,        setter: setReverseSlope },
            { label: "Road distance",        value: reverseRoad,         setter: setReverseRoad },
            { label: "Land use (LULC)",      value: reverseLulc,         setter: setReverseLulc },
          ].map(({ label, value, setter }) => (
            <label key={label} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={value}
                onChange={(e) => setter(e.target.checked)}
                className="rounded border-input"
              />
              {label}
            </label>
          ))}
        </div>

        <Button className="w-full gap-2" onClick={() => mutate()} disabled={isPending}>
          {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          {isPending ? "Computing…" : "Analyze Suitability"}
        </Button>

        {error && (
          <p className="text-xs text-destructive bg-destructive/10 rounded p-2">{error.message}</p>
        )}
      </aside>

      {/* ── Results ──────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto p-6">
        {!data && !isPending && (
          <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
            Select a district and parameters, then click{" "}
            <strong className="mx-1">Analyze Suitability</strong>.
          </div>
        )}

        {isPending && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p>Analyzing landfill suitability for {district}…</p>
            <p className="text-xs">GEE analysis typically takes 15–60 seconds.</p>
          </div>
        )}

        {data && (
          <Tabs defaultValue="map" className="h-full flex flex-col">
            <TabsList className="mb-4 self-start">
              <TabsTrigger value="map">Map</TabsTrigger>
              <TabsTrigger value="stats">Statistics</TabsTrigger>
              <TabsTrigger value="factors">Factor Maps</TabsTrigger>
              <TabsTrigger value="report" className="gap-1.5">
                <FileText className="w-3.5 h-3.5" />Report
              </TabsTrigger>
            </TabsList>

            {/* ── Map ── */}
            <TabsContent value="map" className="flex-1 min-h-[500px]">
              <div className="h-[560px] rounded-lg overflow-hidden border">
                <DistrictMap
                  center={data.center}
                  tileUrl={data.tile_url}
                  title={`Landfill Suitability — ${data.district}`}
                  legend={SUITABILITY_LEGEND}
                  dataSource={`Source: GEE · ESA WorldCover · USGS SRTM · ${analysisDate}`}
                />
              </div>
            </TabsContent>

            {/* ── Statistics ── */}
            <TabsContent value="stats" className="space-y-6">
              <div>
                <h2 className="font-semibold text-lg mb-1">Statistics — {data.district}</h2>
                <p className="text-sm text-muted-foreground">
                  Landfill site suitability distribution across the district.
                </p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {Object.entries(data.stats).map(([label, val]) => (
                  <div key={label} className="bg-card border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">{label}</p>
                    <p className="text-2xl font-bold text-primary">{val}</p>
                  </div>
                ))}
              </div>

              {/* Weight table */}
              <div>
                <h3 className="font-medium mb-3">Weights Used</h3>
                <table className="w-full text-sm border rounded-lg overflow-hidden">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Factor</th>
                      <th className="text-right px-3 py-2 font-medium">Weight</th>
                      <th className="text-right px-3 py-2 font-medium">Direction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.factor_maps).map(([key, f], i) => (
                      <tr key={key} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                        <td className="px-3 py-1.5">{f.label}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{f.weight_pct}%</td>
                        <td className="px-3 py-1.5 text-right text-xs text-muted-foreground">
                          {f.reversed ? "⟳ Reversed" : "Normal"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Class area chart */}
              <div>
                <h3 className="font-medium mb-3">Suitability Class Areas</h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={Object.entries(data.class_areas_km2).map(([k, v], i) => ({
                    name: k, area: v, fill: CLASS_COLOR_LIST[i % CLASS_COLOR_LIST.length],
                  }))}>
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={60} />
                    <YAxis unit=" km²" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => [`${v} km²`, "Area"]} />
                    <Bar dataKey="area" radius={[4, 4, 0, 0]}>
                      {Object.keys(data.class_areas_km2).map((_, i) => (
                        <Cell key={i} fill={CLASS_COLOR_LIST[i % CLASS_COLOR_LIST.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>

                <table className="w-full text-sm mt-4 border rounded-lg overflow-hidden">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Class</th>
                      <th className="text-right px-3 py-2 font-medium">Area (km²)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.class_areas_km2).map(([cls, km2], i) => (
                      <tr key={cls} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                        <td className="px-3 py-1.5 flex items-center gap-2">
                          <span
                            className="w-2.5 h-2.5 rounded-sm inline-block shrink-0"
                            style={{ background: CLASS_COLOR_LIST[i % CLASS_COLOR_LIST.length] }}
                          />
                          {cls}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{km2}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TabsContent>

            {/* ── Factor Maps ── */}
            <TabsContent value="factors" className="space-y-6">
              <div>
                <h2 className="font-semibold text-lg mb-1">Factor Maps — {data.district}</h2>
                <p className="text-sm text-muted-foreground">
                  Individual criteria used in the weighted overlay. Each map shows suitability scores
                  from 1 (least suitable) to 5 (most suitable).
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {Object.entries(data.factor_maps).map(([key, factor]) => (
                  <FactorMapCard
                    key={key}
                    factorKey={key}
                    factor={factor}
                    analysisDate={analysisDate}
                  />
                ))}
              </div>
            </TabsContent>

            {/* ── Report ── */}
            <TabsContent value="report" className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-lg mb-1">Analysis Report — {data.district}</h2>
                  <p className="text-sm text-muted-foreground">
                    Full report including all maps, weights, AHP matrix, and interpretation.
                  </p>
                </div>
                <Button
                  variant="default"
                  className="gap-2"
                  onClick={() => printReport(data, analysisDate)}
                >
                  <Printer className="w-4 h-4" />
                  Open &amp; Print PDF
                </Button>
              </div>

              {/* Summary */}
              <div className="grid grid-cols-3 gap-4">
                {Object.entries(data.stats).map(([label, val]) => (
                  <div key={label} className="bg-card border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">{label}</p>
                    <p className="text-2xl font-bold text-primary">{val}</p>
                  </div>
                ))}
              </div>

              {/* Meta info */}
              <div className="rounded-lg border p-4 text-sm space-y-1">
                <p><span className="text-muted-foreground w-32 inline-block">District:</span><strong>{data.district}</strong></p>
                <p><span className="text-muted-foreground w-32 inline-block">Date generated:</span>{analysisDate}</p>
                <p><span className="text-muted-foreground w-32 inline-block">Method:</span>Weighted Overlay — Analytical Hierarchy Process (AHP)</p>
                <p><span className="text-muted-foreground w-32 inline-block">Data sources:</span>GEE · ESA WorldCover 2021 · USGS SRTM · JRC Global Surface Water</p>
                <p><span className="text-muted-foreground w-32 inline-block">Coordinate system:</span>WGS 84 (EPSG:4326) · Resolution: 100 m</p>
              </div>

              {/* AHP weights table */}
              <div>
                <h3 className="font-medium mb-2">Factor Weights &amp; AHP Configuration</h3>
                <table className="w-full text-sm border rounded-lg overflow-hidden">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Factor</th>
                      <th className="text-right px-3 py-2 font-medium">Weight</th>
                      <th className="text-right px-3 py-2 font-medium">Direction</th>
                      <th className="text-left px-3 py-2 font-medium">Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.factor_maps).map(([key, f], i) => (
                      <tr key={key} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                        <td className="px-3 py-1.5 font-medium">{f.label}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{f.weight_pct}%</td>
                        <td className="px-3 py-1.5 text-right text-xs">{f.reversed ? "⟳ Reversed" : "Normal"}</td>
                        <td className="px-3 py-1.5 text-xs text-muted-foreground">{f.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* AHP pairwise matrix */}
              {data.ahp_data && (
                <div>
                  <h3 className="font-medium mb-2">AHP Pairwise Comparison Matrix</h3>
                  <p className="text-xs text-muted-foreground mb-2">
                    A<sub>ij</sub> = w<sub>i</sub> / w<sub>j</sub> — derived from the assigned weights. Values ≥1 mean row is more important than column.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="text-xs border rounded-lg overflow-hidden">
                      <thead className="bg-muted">
                        <tr>
                          <th className="px-2 py-1.5 text-left font-medium">Criterion</th>
                          {data.ahp_data.factor_labels.map((l) => (
                            <th key={l} className="px-2 py-1.5 text-center font-medium whitespace-nowrap">{l}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {data.ahp_data.matrix.map((row, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                            <td className="px-2 py-1.5 font-semibold whitespace-nowrap">
                              {data.ahp_data.factor_labels[i]}
                            </td>
                            {row.map((v, j) => (
                              <td
                                key={j}
                                className={`px-2 py-1.5 text-center tabular-nums ${i === j ? "text-muted-foreground" : v > 1 ? "font-medium text-primary" : ""}`}
                              >
                                {v.toFixed(2)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className={`mt-3 inline-flex items-center gap-2 rounded px-3 py-1.5 text-sm font-semibold ${data.ahp_data.consistent ? "bg-green-50 text-green-800 border border-green-200" : "bg-red-50 text-red-800 border border-red-200"}`}>
                    {data.ahp_data.consistent ? "✓" : "✗"}
                    CR = {data.ahp_data.cr.toFixed(4)} · λ<sub>max</sub> = {data.ahp_data.lambda_max} · CI = {data.ahp_data.ci.toFixed(4)} · RI = {data.ahp_data.ri}
                    &nbsp;— {data.ahp_data.consistent ? "Consistent (CR < 0.10)" : "Inconsistent — revise weights"}
                  </div>
                </div>
              )}

              {/* Final map */}
              <div>
                <h3 className="font-medium mb-2">Final Suitability Map</h3>
                <div className="relative w-full rounded-lg overflow-hidden border max-w-xl">
                  <img
                    src={data.thumb_url}
                    alt="Final Suitability Map"
                    className="w-full block"
                  />
                  <div className="absolute top-0 left-0 right-0 bg-black/55 text-white text-[11px] font-semibold text-center py-1 px-2">
                    Landfill Site Suitability — {data.district}
                  </div>
                  <div className="absolute top-6 right-1 bg-white/85 rounded p-0.5">
                    <SmallNorthArrow />
                  </div>
                  <div className="absolute bottom-4 right-1 bg-white/85 rounded p-1 text-[8px] leading-tight">
                    {SUITABILITY_LEGEND.map(({ color, label }) => (
                      <div key={label} className="flex items-center gap-0.5">
                        <span className="w-2.5 h-2.5 inline-block rounded-sm border border-gray-300" style={{ background: color }} />
                        <span>{label.split(" ")[0]} {label.split(" ")[1]}</span>
                      </div>
                    ))}
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 bg-black/45 text-white text-[9px] text-center py-0.5">
                    ↑ North · 100 m resolution · Source: Google Earth Engine · {analysisDate}
                  </div>
                </div>
              </div>

              {/* Class area table */}
              <div>
                <h3 className="font-medium mb-2">Suitability Class Areas</h3>
                <table className="w-full text-sm border rounded-lg overflow-hidden">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Class</th>
                      <th className="text-right px-3 py-2 font-medium">Area (km²)</th>
                      <th className="text-right px-3 py-2 font-medium">Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.class_areas_km2).map(([cls, km2], i) => {
                      const total2 = Object.values(data.class_areas_km2).reduce((a, b) => a + b, 0);
                      return (
                        <tr key={cls} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                          <td className="px-3 py-1.5 flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-sm inline-block shrink-0"
                              style={{ background: CLASS_COLOR_LIST[i % CLASS_COLOR_LIST.length] }} />
                            {cls}
                          </td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{km2}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">
                            {total2 > 0 ? ((km2 / total2) * 100).toFixed(1) : "—"}%
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Interpretation */}
              <div>
                <h3 className="font-medium mb-2">Interpretation</h3>
                <div className="bg-muted/40 border-l-4 border-primary rounded-r-lg p-4 text-sm leading-relaxed">
                  {(() => {
                    const total2 = Object.values(data.class_areas_km2).reduce((a, b) => a + b, 0);
                    const hsKm2 = data.class_areas_km2["Highly Suitable (4–5)"] ?? 0;
                    const unKm2 = data.class_areas_km2["Unsuitable (<2)"] ?? 0;
                    const hsPct = total2 > 0 ? ((hsKm2 / total2) * 100).toFixed(1) : "0";
                    const unPct = total2 > 0 ? ((unKm2 / total2) * 100).toFixed(1) : "0";
                    return (
                      <p>
                        The analysis of <strong>{data.district}</strong> district identifies{" "}
                        <strong>{hsPct}%</strong> of the area ({hsKm2} km²) as Highly Suitable for
                        landfill development. River Distance ({data.factor_maps.river?.weight_pct ?? 30}%)
                        and Residential Distance ({data.factor_maps.residential?.weight_pct ?? 25}%) are
                        the primary criteria, reflecting environmental protection and community safety priorities.{" "}
                        <strong>{unPct}%</strong> ({unKm2} km²) is classified as Unsuitable — primarily
                        areas near water bodies, settlements, or steep terrain. The AHP consistency ratio
                        (CR = {data.ahp_data.cr.toFixed(2)}) confirms weight assignments are{" "}
                        {data.ahp_data.consistent
                          ? "acceptable. Field verification is recommended before final site selection."
                          : "inconsistent — consider revising weights to achieve CR < 0.10."}
                      </p>
                    );
                  })()}
                </div>
              </div>

              <Button
                variant="default"
                size="lg"
                className="gap-2"
                onClick={() => printReport(data, analysisDate)}
              >
                <Printer className="w-4 h-4" />
                Open Report &amp; Print / Save PDF
              </Button>
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  );
}

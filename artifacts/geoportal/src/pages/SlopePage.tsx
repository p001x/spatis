import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Loader2, Mountain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, SlopeResult } from "@/lib/api";
import { DistrictMap } from "@/components/DistrictMap";

const DISTRICTS = [
  "Bugesera","Burera","Gakenke","Gasabo","Gatsibo","Gicumbi","Gisagara",
  "Huye","Kamonyi","Karongi","Kayonza","Kicukiro","Kirehe","Muhanga",
  "Musanze","Ngoma","Ngororero","Nyabihu","Nyagatare","Nyamagabe",
  "Nyamasheke","Nyanza","Nyarugenge","Nyaruguru","Rubavu","Ruhango",
  "Rulindo","Rusizi","Rutsiro","Rwamagana",
];

const SLOPE_COLORS = ["#2166ac","#92c5de","#fee08b","#f4a582","#d6604d"];

const LAYER_OPTIONS = [
  { key: "slope", label: "Slope" },
  { key: "hillshade", label: "Hillshade" },
  { key: "aspect", label: "Aspect" },
];

const palette = (n: number) => {
  const full = ["#2166ac","#4393c3","#92c5de","#d1e5f0","#f7f7f7",
                "#fddbc7","#f4a582","#d6604d","#b2182b","#67001f"];
  if (n === 1) return [full[4]];
  const step = (full.length - 1) / (n - 1);
  return Array.from({ length: n }, (_, i) => full[Math.round(i * step)]);
};

export function SlopePage() {
  const [district, setDistrict] = useState("Musanze");
  const [nClasses, setNClasses] = useState(5);
  const [activeLayer, setActiveLayer] = useState("slope");

  const { mutate, data, isPending, error } = useMutation<SlopeResult, Error>({
    mutationFn: () => api.slope({ district, n_classes: nClasses }),
  });

  const getActiveTileUrl = () => {
    if (!data) return "";
    if (activeLayer === "hillshade") return data.hillshade_tile_url;
    if (activeLayer === "aspect") return data.aspect_tile_url;
    return data.slope_tile_url;
  };

  return (
    <div className="flex h-full">
      {/* ── Controls sidebar ─────────────────────────────────────── */}
      <aside className="w-64 shrink-0 border-r bg-card flex flex-col gap-5 p-5 overflow-y-auto">
        <div className="flex items-center gap-2 text-primary font-semibold text-lg">
          <Mountain className="w-5 h-5" />
          Terrain Analysis
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Slope, hillshade and aspect derived from SRTM 30 m DEM.
          Slope in degrees, hillshade at 315° azimuth, aspect in degrees from north.
        </p>

        <div className="space-y-1">
          <Label>District</Label>
          <Select value={district} onValueChange={setDistrict}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DISTRICTS.map((d) => (
                <SelectItem key={d} value={d}>{d}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Classes: {nClasses}</Label>
          <Slider
            min={2}
            max={10}
            step={1}
            value={[nClasses]}
            onValueChange={([v]) => setNClasses(v)}
          />
        </div>

        <Button
          className="w-full gap-2"
          onClick={() => mutate()}
          disabled={isPending}
        >
          {isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Mountain className="w-4 h-4" />
          )}
          {isPending ? "Computing…" : "Analyze Terrain"}
        </Button>

        {error && (
          <p className="text-xs text-destructive bg-destructive/10 rounded p-2">
            {error.message}
          </p>
        )}
      </aside>

      {/* ── Results ──────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto p-6">
        {!data && !isPending && (
          <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
            Select a district, then click <strong className="mx-1">Analyze Terrain</strong>.
          </div>
        )}

        {isPending && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p>Analyzing terrain for {district}…</p>
            <p className="text-xs">GEE analysis typically takes 15–60 seconds.</p>
          </div>
        )}

        {data && (
          <Tabs defaultValue="map" className="h-full flex flex-col">
            <TabsList className="mb-4 self-start">
              <TabsTrigger value="map">Map</TabsTrigger>
              <TabsTrigger value="stats">Statistics</TabsTrigger>
              <TabsTrigger value="classify">Classification</TabsTrigger>
            </TabsList>

            {/* Map */}
            <TabsContent value="map" className="flex-1 min-h-[500px] space-y-3">
              <div className="flex flex-wrap gap-2">
                {LAYER_OPTIONS.map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => setActiveLayer(key)}
                    className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${
                      activeLayer === key
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-card border-input hover:bg-muted"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="h-[520px] rounded-lg overflow-hidden border">
                <DistrictMap center={data.center} tileUrl={getActiveTileUrl()} />
              </div>
              <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                <span>
                  <strong className="text-foreground">Slope:</strong> blue (flat) → red (steep)
                </span>
                <span>
                  <strong className="text-foreground">Hillshade:</strong> black (shadow) → white (lit)
                </span>
                <span>
                  <strong className="text-foreground">Aspect:</strong> circular color wheel (N/E/S/W)
                </span>
              </div>
            </TabsContent>

            {/* Statistics */}
            <TabsContent value="stats" className="space-y-6">
              <div>
                <h2 className="font-semibold text-lg mb-1">
                  Terrain Statistics — {data.district}
                </h2>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {Object.entries(data.stats).map(([label, val]) => (
                  <div key={label} className="bg-card border rounded-lg p-4">
                    <p className="text-xs text-muted-foreground mb-1">{label}</p>
                    <p className="text-2xl font-bold text-primary">{val}</p>
                  </div>
                ))}
              </div>

              <div>
                <h3 className="font-medium mb-3">Slope Class Areas</h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={Object.entries(data.class_areas_km2).map(([k, v], i) => ({
                      name: k,
                      area: v,
                      fill: SLOPE_COLORS[i % SLOPE_COLORS.length],
                    }))}
                  >
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
                    <YAxis unit=" km²" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => [`${v} km²`, "Area"]} />
                    <Bar dataKey="area" radius={[4, 4, 0, 0]}>
                      {Object.keys(data.class_areas_km2).map((_, i) => (
                        <Cell key={i} fill={SLOPE_COLORS[i % SLOPE_COLORS.length]} />
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
                            style={{ background: SLOPE_COLORS[i % SLOPE_COLORS.length] }}
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

            {/* Classification */}
            <TabsContent value="classify" className="space-y-6">
              <div>
                <h2 className="font-semibold text-lg mb-1">
                  Quantile Classification — {data.district}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Breakpoints computed from the actual pixel distribution within the district.
                </p>
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-2 text-xs">
                {palette(data.classify.n_classes).map((color, i) => {
                  const labels: Record<number, string[]> = {
                    2: ["Flat","Steep"],
                    3: ["Flat","Moderate","Steep"],
                    4: ["Flat","Gentle","Moderate","Steep"],
                    5: ["Flat","Gentle","Moderate","Steep","Very Steep"],
                    6: ["Flat","Gentle","Moderate","Steep","Very Steep","Cliff"],
                  };
                  const lbl = (labels[data.classify.n_classes] ?? [])[i] ?? `Class ${i + 1}`;
                  return (
                    <span key={i} className="flex items-center gap-1">
                      <span className="w-3 h-3 rounded-sm" style={{ background: color }} />
                      {lbl}
                    </span>
                  );
                })}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {data.classify.panels.map((panel) => (
                  <div key={panel.letter} className="border rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="bg-primary text-primary-foreground font-bold px-2 py-0.5 rounded text-sm">
                        {panel.letter}
                      </span>
                      <span className="font-medium">{panel.title}</span>
                    </div>
                    {panel.breakpoints.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        Breakpoints: {panel.breakpoints.map((b) => b.toFixed(4)).join(" | ")}
                      </p>
                    )}
                    <img
                      src={panel.thumb_url}
                      alt={`${panel.title} classified thumbnail`}
                      className="w-full rounded object-cover border"
                    />
                    <ResponsiveContainer width="100%" height={160}>
                      <BarChart
                        data={Object.entries(panel.areas).map(([k, v], i) => ({
                          name: k.split(" (")[0],
                          area: v,
                          fill: palette(data.classify.n_classes)[i],
                        }))}
                      >
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis unit=" km²" tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(v: number) => [`${v} km²`, "Area"]} />
                        <Bar dataKey="area" radius={[3, 3, 0, 0]}>
                          {Object.keys(panel.areas).map((_, i) => (
                            <Cell key={i} fill={palette(data.classify.n_classes)[i]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  );
}

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
import { Loader2, AlertTriangle } from "lucide-react";
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
import { api, LandslideResult } from "@/lib/api";
import { DistrictMap } from "@/components/DistrictMap";

const DISTRICTS = [
  "Bugesera","Burera","Gakenke","Gasabo","Gatsibo","Gicumbi","Gisagara",
  "Huye","Kamonyi","Karongi","Kayonza","Kicukiro","Kirehe","Muhanga",
  "Musanze","Ngoma","Ngororero","Nyabihu","Nyagatare","Nyamagabe",
  "Nyamasheke","Nyanza","Nyarugenge","Nyaruguru","Rubavu","Ruhango",
  "Rulindo","Rusizi","Rutsiro","Rwamagana",
];

const YEARS = Array.from({ length: 2024 - 1981 + 1 }, (_, i) => 1981 + i);

const SUSCEPTIBILITY_COLORS = ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"];
const SUSCEPTIBILITY_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High"];

export function LandslidePage() {
  const [district, setDistrict] = useState("Musanze");
  const [startYear, setStartYear] = useState(2015);
  const [endYear, setEndYear] = useState(2024);
  const [nClasses, setNClasses] = useState(5);
  const [activeLayer, setActiveLayer] = useState<"continuous" | "classified">("continuous");

  const { mutate, data, isPending, error } = useMutation<LandslideResult, Error>({
    mutationFn: () =>
      api.landslide({ district, start_year: startYear, end_year: endYear, n_classes: nClasses }),
  });

  const currentTileUrl = data
    ? activeLayer === "continuous"
      ? data.lsi_tile_url
      : data.lsi_class_tile_url
    : undefined;

  return (
    <div className="flex h-full">
      {/* ── Controls sidebar ─────────────────────────────────────── */}
      <aside className="w-64 shrink-0 border-r bg-card flex flex-col gap-5 p-5 overflow-y-auto">
        <div className="flex items-center gap-2 text-primary font-semibold text-lg">
          <AlertTriangle className="w-5 h-5" />
          Landslide Susceptibility
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Landslide Susceptibility Index (LSI) computed from slope, rainfall,
          land use, soil, and proximity factors over the selected period.
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

        <div className="space-y-1">
          <Label>Start year</Label>
          <Select value={String(startYear)} onValueChange={(v) => setStartYear(Number(v))}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {YEARS.map((y) => (
                <SelectItem key={y} value={String(y)}>{y}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label>End year</Label>
          <Select value={String(endYear)} onValueChange={(v) => setEndYear(Number(v))}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {YEARS.map((y) => (
                <SelectItem key={y} value={String(y)}>{y}</SelectItem>
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
            <AlertTriangle className="w-4 h-4" />
          )}
          {isPending ? "Computing…" : "Analyze Susceptibility"}
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
            Select a district and year range, then click{" "}
            <strong className="mx-1">Analyze Susceptibility</strong>.
          </div>
        )}

        {isPending && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p>Analyzing landslide susceptibility for {district}…</p>
            <p className="text-xs">GEE analysis typically takes 15–60 seconds.</p>
          </div>
        )}

        {data && (
          <Tabs defaultValue="map" className="h-full flex flex-col">
            <TabsList className="mb-4 self-start">
              <TabsTrigger value="map">Map</TabsTrigger>
              <TabsTrigger value="stats">Statistics</TabsTrigger>
              <TabsTrigger value="classification">Classification</TabsTrigger>
            </TabsList>

            {/* Map */}
            <TabsContent value="map" className="flex-1 min-h-[500px]">
              <div className="flex gap-2 mb-3">
                <Button
                  size="sm"
                  variant={activeLayer === "continuous" ? "default" : "outline"}
                  onClick={() => setActiveLayer("continuous")}
                >
                  LSI Continuous
                </Button>
                <Button
                  size="sm"
                  variant={activeLayer === "classified" ? "default" : "outline"}
                  onClick={() => setActiveLayer("classified")}
                >
                  LSI Classified
                </Button>
              </div>
              <div className="h-[520px] rounded-lg overflow-hidden border">
                <DistrictMap center={data.center} tileUrl={currentTileUrl!} />
              </div>
              <div className="mt-3 flex flex-wrap gap-3 text-xs">
                {SUSCEPTIBILITY_LABELS.map((label, i) => (
                  <span key={label} className="flex items-center gap-1.5">
                    <span
                      className="w-3 h-3 rounded-sm inline-block"
                      style={{ background: SUSCEPTIBILITY_COLORS[i] }}
                    />
                    {label}
                  </span>
                ))}
              </div>
            </TabsContent>

            {/* Statistics */}
            <TabsContent value="stats" className="space-y-6">
              <div>
                <h2 className="font-semibold text-lg mb-1">
                  Statistics — {data.district}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Landslide Susceptibility Index distribution across the district.
                </p>
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
                <h3 className="font-medium mb-3">Susceptibility Class Areas</h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart
                    data={Object.entries(data.class_areas_km2).map(([k, v], i) => ({
                      name: k,
                      area: v,
                      fill: SUSCEPTIBILITY_COLORS[i % SUSCEPTIBILITY_COLORS.length],
                    }))}
                  >
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={55} />
                    <YAxis unit=" km²" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => [`${v} km²`, "Area"]} />
                    <Bar dataKey="area" radius={[4, 4, 0, 0]}>
                      {Object.keys(data.class_areas_km2).map((_, i) => (
                        <Cell key={i} fill={SUSCEPTIBILITY_COLORS[i % SUSCEPTIBILITY_COLORS.length]} />
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
                            style={{ background: SUSCEPTIBILITY_COLORS[i % SUSCEPTIBILITY_COLORS.length] }}
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
            <TabsContent value="classification" className="space-y-6">
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
                {SUSCEPTIBILITY_LABELS.slice(0, data.classify.n_classes).map((label, i) => (
                  <span key={label} className="flex items-center gap-1">
                    <span
                      className="w-3 h-3 rounded-sm"
                      style={{ background: SUSCEPTIBILITY_COLORS[i % SUSCEPTIBILITY_COLORS.length] }}
                    />
                    {label}
                  </span>
                ))}
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
                          fill: SUSCEPTIBILITY_COLORS[i % SUSCEPTIBILITY_COLORS.length],
                        }))}
                      >
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis unit=" km²" tick={{ fontSize: 10 }} />
                        <Tooltip formatter={(v: number) => [`${v} km²`, "Area"]} />
                        <Bar dataKey="area" radius={[3, 3, 0, 0]}>
                          {Object.keys(panel.areas).map((_, i) => (
                            <Cell key={i} fill={SUSCEPTIBILITY_COLORS[i % SUSCEPTIBILITY_COLORS.length]} />
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

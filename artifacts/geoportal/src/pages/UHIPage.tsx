import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Thermometer } from "lucide-react";
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
import { api, UHIResult } from "@/lib/api";
import { DistrictMap } from "@/components/DistrictMap";

const DISTRICTS = [
  "Bugesera","Burera","Gakenke","Gasabo","Gatsibo","Gicumbi","Gisagara",
  "Huye","Kamonyi","Karongi","Kayonza","Kicukiro","Kirehe","Muhanga",
  "Musanze","Ngoma","Ngororero","Nyabihu","Nyagatare","Nyamagabe",
  "Nyamasheke","Nyanza","Nyarugenge","Nyaruguru","Rubavu","Ruhango",
  "Rulindo","Rusizi","Rutsiro","Rwamagana",
];

function today() {
  return new Date().toISOString().slice(0, 10);
}
function sixMonthsAgo() {
  const d = new Date();
  d.setMonth(d.getMonth() - 6);
  return d.toISOString().slice(0, 10);
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-card border rounded-lg p-4">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className="text-2xl font-bold text-primary">{value}</p>
    </div>
  );
}

export function UHIPage() {
  const [district, setDistrict] = useState("Kicukiro");
  const [startDate, setStartDate] = useState(sixMonthsAgo());
  const [endDate, setEndDate] = useState(today());
  const [gridSize, setGridSize] = useState(5);
  const [activeLayer, setActiveLayer] = useState<"lst" | "ndbi">("lst");

  const { mutate, data, isPending, error } = useMutation<UHIResult, Error>({
    mutationFn: () =>
      api.uhi({
        district,
        start_date: startDate,
        end_date: endDate,
        grid_size: gridSize,
      }),
  });

  const tileUrl = data
    ? activeLayer === "lst"
      ? data.lst_tile_url
      : data.ndbi_tile_url
    : "";

  return (
    <div className="flex h-full">
      {/* ── Controls sidebar ─────────────────────────────────────── */}
      <aside className="w-64 shrink-0 border-r bg-card flex flex-col gap-5 p-5 overflow-y-auto">
        <div className="flex items-center gap-2 text-primary font-semibold text-lg">
          <Thermometer className="w-5 h-5" />
          UHI Analysis
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Urban Heat Island analysis using Land Surface Temperature (LST) and
          Normalized Difference Built-up Index (NDBI).
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
          <Label htmlFor="uhi-start-date">Start date</Label>
          <input
            id="uhi-start-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="uhi-end-date">End date</Label>
          <input
            id="uhi-end-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="space-y-2">
          <Label>Grid: {gridSize}x{gridSize}</Label>
          <Slider
            min={3}
            max={12}
            step={1}
            value={[gridSize]}
            onValueChange={([v]) => setGridSize(v)}
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
            <Thermometer className="w-4 h-4" />
          )}
          {isPending ? "Analyzing…" : "Analyze UHI"}
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
            Select a district and date range, then click{" "}
            <strong className="mx-1">Analyze UHI</strong>.
          </div>
        )}

        {isPending && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p>Analyzing UHI for {district}…</p>
            <p className="text-xs">GEE analysis typically takes 15–60 seconds.</p>
          </div>
        )}

        {data && (
          <Tabs defaultValue="map" className="h-full flex flex-col">
            <TabsList className="mb-4 self-start">
              <TabsTrigger value="map">Map</TabsTrigger>
              <TabsTrigger value="analysis">Analysis</TabsTrigger>
              <TabsTrigger value="grid">Grid Table</TabsTrigger>
            </TabsList>

            {/* Map Tab */}
            <TabsContent value="map" className="flex-1 space-y-4">
              <div className="flex gap-2">
                <Button
                  variant={activeLayer === "lst" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveLayer("lst")}
                >
                  LST
                </Button>
                <Button
                  variant={activeLayer === "ndbi" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setActiveLayer("ndbi")}
                >
                  NDBI
                </Button>
              </div>

              <div className="h-[480px] rounded-lg overflow-hidden border">
                <DistrictMap center={data.center} tileUrl={tileUrl} />
              </div>

              <div className="flex gap-4">
                {data.lst_thumb_url && (
                  <div className="flex-1 space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">LST Thumbnail</p>
                    <img
                      src={data.lst_thumb_url}
                      alt="LST thumbnail"
                      className="w-full rounded border object-cover"
                    />
                  </div>
                )}
                {data.ndbi_thumb_url && (
                  <div className="flex-1 space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">NDBI Thumbnail</p>
                    <img
                      src={data.ndbi_thumb_url}
                      alt="NDBI thumbnail"
                      className="w-full rounded border object-cover"
                    />
                  </div>
                )}
              </div>
            </TabsContent>

            {/* Analysis Tab */}
            <TabsContent value="analysis" className="space-y-6">
              <div>
                <h2 className="font-semibold text-lg mb-1">UHI Analysis — {district}</h2>
                <p className="text-sm text-muted-foreground">
                  {data.n_cells_with_data} / {data.n_cells_total} cells with data
                </p>
              </div>

              {data.regression === null ? (
                <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
                  Not enough data for regression analysis.
                </div>
              ) : (
                <div className="space-y-4">
                  <h3 className="font-medium">Regression: LST ~ NDBI</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatCard label="R²" value={data.regression.r2.toFixed(4)} />
                    <StatCard label="Slope" value={data.regression.slope.toFixed(4)} />
                    <StatCard label="p-value" value={data.regression.p_value.toExponential(2)} />
                    <StatCard label="n (cells)" value={data.regression.n} />
                  </div>
                </div>
              )}

              <div className="flex gap-4 flex-wrap">
                {data.bivariate_png && (
                  <div className="flex-1 min-w-[260px] space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">Bivariate Map</p>
                    <img
                      src={"data:image/png;base64," + data.bivariate_png}
                      alt="Bivariate map"
                      className="w-full rounded border"
                    />
                  </div>
                )}
                {data.scatter_png && (
                  <div className="flex-1 min-w-[260px] space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">Scatter Plot</p>
                    <img
                      src={"data:image/png;base64," + data.scatter_png}
                      alt="Scatter plot"
                      className="w-full rounded border"
                    />
                  </div>
                )}
              </div>

              {/* LST Stats */}
              <div>
                <h3 className="font-medium mb-2">LST Statistics</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Object.entries(data.lst_stats).map(([k, v]) => (
                    <div key={k} className="bg-card border rounded-lg p-3">
                      <p className="text-xs text-muted-foreground mb-1">{k}</p>
                      <p className="text-lg font-bold text-primary">
                        {v !== null ? v.toFixed(2) : "—"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* NDBI Stats */}
              <div>
                <h3 className="font-medium mb-2">NDBI Statistics</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Object.entries(data.ndbi_stats).map(([k, v]) => (
                    <div key={k} className="bg-card border rounded-lg p-3">
                      <p className="text-xs text-muted-foreground mb-1">{k}</p>
                      <p className="text-lg font-bold text-primary">
                        {v !== null ? v.toFixed(4) : "—"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            {/* Grid Table Tab */}
            <TabsContent value="grid" className="space-y-4">
              <h2 className="font-semibold text-lg">Grid Cell Data</h2>
              <div className="rounded-lg border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Grid ID</th>
                      <th className="text-right px-4 py-2 font-medium">LST (°C)</th>
                      <th className="text-right px-4 py-2 font-medium">NDBI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.grid_table.map((row, i) => (
                      <tr key={row.grid_id} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                        <td className="px-4 py-1.5">{row.grid_id}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {row.LST !== null ? row.LST.toFixed(2) : "—"}
                        </td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {row.NDBI !== null ? row.NDBI.toFixed(4) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  );
}

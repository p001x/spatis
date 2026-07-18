import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, Download, Upload, Edit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api, TrainingSample, BASE } from "@/lib/api";

export function SampleDigitizationPage() {
  const qc = useQueryClient();

  // Add Sample form state
  const [classLabel, setClassLabel] = useState("");
  const [color, setColor] = useState("#0F6E4F");
  const [creator, setCreator] = useState("");
  const [geoJsonText, setGeoJsonText] = useState("");
  const [parseError, setParseError] = useState("");

  // GEE Upload state
  const [geeFile, setGeeFile] = useState<File | null>(null);
  const [assetName, setAssetName] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["samples"],
    queryFn: () => api.samples.list(),
  });
  const samples = data?.samples ?? [];

  const addMut = useMutation({
    mutationFn: () => {
      setParseError("");
      let geometry: any;
      try {
        geometry = JSON.parse(geoJsonText);
      } catch {
        throw new Error("Invalid GeoJSON — check your input.");
      }
      return api.samples.add({ geometry, class_label: classLabel, color, creator });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["samples"] });
      setGeoJsonText("");
      setClassLabel("");
      setCreator("");
    },
    onError: (e: Error) => setParseError(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.samples.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });

  const geeMut = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      if (geeFile) fd.append("file", geeFile);
      fd.append("asset_name", assetName);
      return fetch(BASE + "/samples/push-to-gee", { method: "POST", body: fd }).then((r) => {
        if (!r.ok) return r.json().then((e) => Promise.reject(new Error(e.detail ?? r.statusText)));
        return r.json();
      });
    },
    onSuccess: () => {
      setGeeFile(null);
      setAssetName("");
    },
  });

  // Download GeoJSON helper
  const downloadGeoJSON = () => {
    const fc = {
      type: "FeatureCollection",
      features: samples.map((s) => ({
        type: "Feature",
        geometry: s.geometry,
        properties: {
          id: s.id,
          class_label: s.class_label,
          color: s.color,
          creator: s.creator,
          created_at: s.created_at,
        },
      })),
    };
    const blob = new Blob([JSON.stringify(fc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "training_samples.geojson";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto p-6">
      <div className="flex items-center gap-2 text-primary font-semibold text-xl mb-2">
        <Edit className="w-5 h-5" />
        Sample Digitization
      </div>
      <p className="text-sm text-muted-foreground mb-6">
        Add and manage training samples for land cover classification.
      </p>

      <Tabs defaultValue="map" className="flex-1 flex flex-col">
        <TabsList className="mb-4 self-start">
          <TabsTrigger value="map">Map &amp; Samples</TabsTrigger>
          <TabsTrigger value="gee">GEE Asset Upload</TabsTrigger>
        </TabsList>

        {/* MAP & SAMPLES TAB */}
        <TabsContent value="map" className="flex-1 space-y-6">
          <div className="flex gap-4">
            {/* Left sidebar */}
            <div className="w-72 shrink-0 space-y-4">
              <div className="border rounded-lg p-4 space-y-3">
                <p className="font-medium text-sm">Add Sample</p>

                <div className="space-y-1">
                  <Label>Class Label</Label>
                  <input
                    value={classLabel}
                    onChange={(e) => setClassLabel(e.target.value)}
                    placeholder="e.g. Forest, Urban, Water"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div className="space-y-1">
                  <Label>Color</Label>
                  <input
                    type="color"
                    value={color}
                    onChange={(e) => setColor(e.target.value)}
                    className="w-full h-9 rounded-md border border-input cursor-pointer"
                  />
                </div>

                <div className="space-y-1">
                  <Label>Creator</Label>
                  <input
                    value={creator}
                    onChange={(e) => setCreator(e.target.value)}
                    placeholder="Your name"
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>

                <div className="space-y-1">
                  <Label>Geometry (GeoJSON)</Label>
                  <textarea
                    value={geoJsonText}
                    onChange={(e) => setGeoJsonText(e.target.value)}
                    placeholder='{"type":"Point","coordinates":[29.87,-1.94]}'
                    rows={5}
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring font-mono resize-y"
                  />
                </div>

                {parseError && (
                  <p className="text-xs text-destructive">{parseError}</p>
                )}
                {addMut.isSuccess && (
                  <p className="text-xs text-green-600">Sample saved!</p>
                )}

                <Button
                  className="w-full gap-2"
                  onClick={() => addMut.mutate()}
                  disabled={addMut.isPending || !classLabel || !geoJsonText}
                >
                  {addMut.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Edit className="w-4 h-4" />
                  )}
                  Save Sample
                </Button>
              </div>
            </div>

            {/* Map */}
            <div className="flex-1">
              <div className="rounded-lg border overflow-hidden" style={{ height: "500px" }}>
                <MapContainer
                  center={[-1.94, 29.87]}
                  zoom={9}
                  style={{ height: "100%", width: "100%" }}
                  scrollWheelZoom
                >
                  <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  />
                  {samples.map((s) => {
                    if (!s.geometry) return null;
                    return (
                      <GeoJSON
                        key={s.id}
                        data={s.geometry}
                        style={() => ({
                          color: s.color,
                          fillColor: s.color,
                          fillOpacity: 0.4,
                          weight: 2,
                        })}
                      />
                    );
                  })}
                </MapContainer>
              </div>
            </div>
          </div>

          {/* Samples table */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Samples ({samples.length})</h3>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={downloadGeoJSON}
                disabled={samples.length === 0}
              >
                <Download className="w-4 h-4" />
                Download GeoJSON
              </Button>
            </div>

            {isLoading ? (
              <div className="flex items-center gap-2 text-muted-foreground py-4">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading samples…
              </div>
            ) : (
              <div className="rounded-lg border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">Class</th>
                      <th className="text-left px-4 py-2 font-medium">Geometry Type</th>
                      <th className="text-left px-4 py-2 font-medium">Creator</th>
                      <th className="text-left px-4 py-2 font-medium">Created</th>
                      <th className="px-4 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {samples.map((s, i) => (
                      <tr key={s.id} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                        <td className="px-4 py-2 flex items-center gap-2">
                          <span
                            className="w-3 h-3 rounded-full inline-block shrink-0"
                            style={{ background: s.color }}
                          />
                          {s.class_label}
                        </td>
                        <td className="px-4 py-2 text-muted-foreground">
                          {s.geometry?.type ?? "—"}
                        </td>
                        <td className="px-4 py-2">{s.creator || "—"}</td>
                        <td className="px-4 py-2 text-muted-foreground text-xs">
                          {s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}
                        </td>
                        <td className="px-4 py-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => deleteMut.mutate(s.id)}
                            disabled={deleteMut.isPending}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                    {samples.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                          No samples yet. Add one above.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </TabsContent>

        {/* GEE ASSET UPLOAD TAB */}
        <TabsContent value="gee" className="space-y-6 max-w-xl">
          <div>
            <h2 className="font-semibold text-lg mb-1">Push to Google Earth Engine</h2>
            <p className="text-sm text-muted-foreground">
              Upload a geospatial file and push it as a GEE asset. Supported formats: GeoTIFF,
              ZIP (Shapefile), GeoJSON, GPKG, KML, CSV.
            </p>
          </div>

          <div className="border rounded-lg p-4 space-y-4">
            <div className="space-y-1">
              <Label>File</Label>
              <input
                type="file"
                accept=".tif,.tiff,.zip,.geojson,.json,.gpkg,.kml,.csv"
                onChange={(e) => setGeeFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
            </div>

            <div className="space-y-1">
              <Label>Asset Name</Label>
              <input
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                placeholder="e.g. projects/my-project/assets/my_layer"
                className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {geeMut.error && (
              <p className="text-xs text-destructive">{(geeMut.error as Error).message}</p>
            )}
            {geeMut.isSuccess && (
              <div className="rounded-md bg-green-50 border border-green-200 p-3 text-sm space-y-1">
                <p className="text-green-700 font-medium">Upload successful!</p>
                <p className="text-green-600 text-xs font-mono">{(geeMut.data as any)?.asset_id}</p>
              </div>
            )}

            <Button
              className="gap-2"
              onClick={() => geeMut.mutate()}
              disabled={geeMut.isPending || !geeFile || !assetName}
            >
              {geeMut.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              {geeMut.isPending ? "Uploading…" : "Upload to GEE"}
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, Download, Upload, Link as LinkIcon, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MapContainer, TileLayer, Rectangle } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { api, DatasetRecord } from "@/lib/api";
import { BASE } from "@/lib/api";

const FILE_TYPE_COLORS: Record<string, string> = {
  tiff: "#ef4444",
  shapefile: "#3b82f6",
  csv: "#22c55e",
  other: "#a855f7",
};

function Badge({ type }: { type: string }) {
  const color = FILE_TYPE_COLORS[type] ?? FILE_TYPE_COLORS.other;
  return (
    <span
      className="inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded text-white uppercase"
      style={{ backgroundColor: color }}
    >
      {type}
    </span>
  );
}

function SummaryRow({ records }: { records: DatasetRecord[] }) {
  const totalMb = records.reduce((s, r) => s + (r.file_size_mb ?? 0), 0);
  const spatial = records.filter((r) => r.bbox && r.bbox.length === 4).length;
  return (
    <div className="flex gap-4 text-sm text-muted-foreground mb-3">
      <span><strong className="text-foreground">{records.length}</strong> datasets</span>
      <span><strong className="text-foreground">{totalMb.toFixed(1)}</strong> MB total</span>
      <span><strong className="text-foreground">{spatial}</strong> with spatial extent</span>
    </div>
  );
}

function DatasetMap({ records }: { records: DatasetRecord[] }) {
  const spatial = records.filter((r) => r.bbox && r.bbox.length === 4);
  return (
    <MapContainer
      center={[-1.94, 29.87]}
      zoom={8}
      style={{ height: "300px", width: "100%" }}
      scrollWheelZoom={false}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      {spatial.map((r) => {
        const [minx, miny, maxx, maxy] = r.bbox!;
        const color = FILE_TYPE_COLORS[r.file_type] ?? FILE_TYPE_COLORS.other;
        return (
          <Rectangle
            key={r.id}
            bounds={[[miny, minx], [maxy, maxx]]}
            pathOptions={{ color, weight: 2, fillOpacity: 0.2 }}
          />
        );
      })}
    </MapContainer>
  );
}

function DatasetList({
  records,
  source,
  onDelete,
}: {
  records: DatasetRecord[];
  source: string;
  onDelete?: (id: string) => void;
}) {
  return (
    <div className="rounded-lg border overflow-hidden mt-3">
      <table className="w-full text-sm">
        <thead className="bg-muted">
          <tr>
            <th className="text-left px-4 py-2 font-medium">Name</th>
            <th className="text-left px-4 py-2 font-medium">Type</th>
            <th className="text-right px-4 py-2 font-medium">Size (MB)</th>
            <th className="text-left px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr key={r.id} className={i % 2 === 0 ? "bg-background" : "bg-muted/30"}>
              <td className="px-4 py-2">
                <div className="font-medium">{r.name}</div>
                {r.description && (
                  <div className="text-xs text-muted-foreground">{r.description}</div>
                )}
                {r.contributor && (
                  <div className="text-xs text-muted-foreground">By: {r.contributor}</div>
                )}
              </td>
              <td className="px-4 py-2">
                <Badge type={r.file_type} />
              </td>
              <td className="px-4 py-2 text-right tabular-nums">
                {r.file_size_mb?.toFixed(2) ?? "—"}
              </td>
              <td className="px-4 py-2">
                <span className={`text-xs ${r.status === "ready" ? "text-green-600" : r.status === "error" ? "text-red-500" : "text-muted-foreground"}`}>
                  {r.status}
                </span>
                {r.error_message && (
                  <div className="text-xs text-red-500">{r.error_message}</div>
                )}
              </td>
              <td className="px-4 py-2 flex gap-2 justify-end">
                <a
                  href={`${BASE}/datasets/${r.id}/download?source=${source}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button variant="ghost" size="icon" className="h-7 w-7">
                    <Download className="w-3.5 h-3.5" />
                  </Button>
                </a>
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive hover:text-destructive"
                    onClick={() => onDelete(r.id)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                )}
              </td>
            </tr>
          ))}
          {records.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground text-sm">
                No datasets yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function OfficialTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["datasets", "admin"],
    queryFn: () => api.datasets.list("admin"),
  });
  const records = data?.records ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <SummaryRow records={records} />
      <div className="rounded-lg border overflow-hidden">
        <DatasetMap records={records} />
      </div>
      <DatasetList records={records} source="admin" />
    </div>
  );
}

function CommunityTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["datasets", "community"],
    queryFn: () => api.datasets.list("community"),
  });
  const records = data?.records ?? [];

  const [file, setFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploadDesc, setUploadDesc] = useState("");
  const [uploadContrib, setUploadContrib] = useState("");

  const [linkUrl, setLinkUrl] = useState("");
  const [linkName, setLinkName] = useState("");
  const [linkDesc, setLinkDesc] = useState("");
  const [linkContrib, setLinkContrib] = useState("");

  const uploadMut = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      if (file) fd.append("file", file);
      fd.append("name", uploadName);
      fd.append("description", uploadDesc);
      fd.append("contributor", uploadContrib);
      fd.append("source", "community");
      return api.datasets.upload(fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["datasets", "community"] });
      setFile(null);
      setUploadName("");
      setUploadDesc("");
      setUploadContrib("");
    },
  });

  const linkMut = useMutation({
    mutationFn: () =>
      api.datasets.addLink({
        source_url: linkUrl,
        name: linkName,
        description: linkDesc,
        contributor: linkContrib,
        source: "community",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["datasets", "community"] });
      setLinkUrl("");
      setLinkName("");
      setLinkDesc("");
      setLinkContrib("");
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <SummaryRow records={records} />
        <div className="rounded-lg border overflow-hidden">
          <DatasetMap records={records} />
        </div>
        <DatasetList records={records} source="community" />
      </div>

      {/* File upload form */}
      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex items-center gap-2 font-medium text-sm">
          <Upload className="w-4 h-4" /> Upload File
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>File</Label>
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label>Name</Label>
            <input
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              placeholder="Dataset name"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-1">
            <Label>Description</Label>
            <input
              value={uploadDesc}
              onChange={(e) => setUploadDesc(e.target.value)}
              placeholder="Short description"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-1">
            <Label>Contributor</Label>
            <input
              value={uploadContrib}
              onChange={(e) => setUploadContrib(e.target.value)}
              placeholder="Your name or org"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        {uploadMut.error && (
          <p className="text-xs text-destructive">{(uploadMut.error as Error).message}</p>
        )}
        {uploadMut.isSuccess && (
          <p className="text-xs text-green-600">Uploaded successfully!</p>
        )}
        <Button
          onClick={() => uploadMut.mutate()}
          disabled={uploadMut.isPending || !file || !uploadName}
          className="gap-2"
        >
          {uploadMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          Upload
        </Button>
      </div>

      {/* GitHub link form */}
      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex items-center gap-2 font-medium text-sm">
          <LinkIcon className="w-4 h-4" /> Link from GitHub / URL
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1 sm:col-span-2">
            <Label>URL</Label>
            <input
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="https://github.com/…"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-1">
            <Label>Name</Label>
            <input
              value={linkName}
              onChange={(e) => setLinkName(e.target.value)}
              placeholder="Dataset name"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-1">
            <Label>Contributor</Label>
            <input
              value={linkContrib}
              onChange={(e) => setLinkContrib(e.target.value)}
              placeholder="Your name or org"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Description</Label>
            <input
              value={linkDesc}
              onChange={(e) => setLinkDesc(e.target.value)}
              placeholder="Short description"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        {linkMut.error && (
          <p className="text-xs text-destructive">{(linkMut.error as Error).message}</p>
        )}
        {linkMut.isSuccess && (
          <p className="text-xs text-green-600">Linked successfully!</p>
        )}
        <Button
          onClick={() => linkMut.mutate()}
          disabled={linkMut.isPending || !linkUrl || !linkName}
          className="gap-2"
        >
          {linkMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <LinkIcon className="w-4 h-4" />}
          Link Dataset
        </Button>
      </div>
    </div>
  );
}

function AdminTab() {
  const qc = useQueryClient();
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [authError, setAuthError] = useState("");

  const [file, setFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploadDesc, setUploadDesc] = useState("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["datasets", "admin"],
    queryFn: () => api.datasets.list("admin"),
    enabled: authed,
  });
  const records = data?.records ?? [];

  const signIn = async () => {
    setAuthError("");
    try {
      const res = await api.adminVerify(password);
      if (res.ok) {
        setAuthed(true);
        refetch();
      } else {
        setAuthError("Invalid password.");
      }
    } catch {
      setAuthError("Authentication failed.");
    }
  };

  const uploadMut = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      if (file) fd.append("file", file);
      fd.append("name", uploadName);
      fd.append("description", uploadDesc);
      fd.append("source", "admin");
      return api.datasets.upload(fd);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["datasets", "admin"] });
      setFile(null);
      setUploadName("");
      setUploadDesc("");
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.datasets.delete(id, "admin"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["datasets", "admin"] }),
  });

  if (!authed) {
    return (
      <div className="max-w-sm space-y-4 py-8">
        <div className="flex items-center gap-2 font-semibold">
          <Database className="w-5 h-5 text-primary" /> Admin Sign In
        </div>
        <div className="space-y-1">
          <Label>Password</Label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && signIn()}
            placeholder="Admin password"
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        {authError && <p className="text-xs text-destructive">{authError}</p>}
        <Button onClick={signIn} className="w-full">Sign In</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex items-center gap-2 font-medium text-sm">
          <Upload className="w-4 h-4" /> Upload Official Dataset
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>File</Label>
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label>Name</Label>
            <input
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              placeholder="Dataset name"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Description</Label>
            <input
              value={uploadDesc}
              onChange={(e) => setUploadDesc(e.target.value)}
              placeholder="Short description"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>
        {uploadMut.error && (
          <p className="text-xs text-destructive">{(uploadMut.error as Error).message}</p>
        )}
        {uploadMut.isSuccess && <p className="text-xs text-green-600">Uploaded successfully!</p>}
        <Button
          onClick={() => uploadMut.mutate()}
          disabled={uploadMut.isPending || !file || !uploadName}
          className="gap-2"
        >
          {uploadMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          Upload
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : (
        <DatasetList
          records={records}
          source="admin"
          onDelete={(id) => deleteMut.mutate(id)}
        />
      )}
    </div>
  );
}

export function RareDataPage() {
  return (
    <div className="flex h-full overflow-y-auto">
      <main className="flex-1 p-6">
        <div className="flex items-center gap-2 text-primary font-semibold text-xl mb-2">
          <Database className="w-5 h-5" />
          RARE DATA — Dataset Repository
        </div>
        <p className="text-sm text-muted-foreground mb-6">
          Discover, download, and contribute geospatial datasets for Rwanda.
        </p>

        <Tabs defaultValue="official">
          <TabsList className="mb-4">
            <TabsTrigger value="official">Official Datasets</TabsTrigger>
            <TabsTrigger value="community">Community Uploads</TabsTrigger>
            <TabsTrigger value="admin">Admin Upload</TabsTrigger>
          </TabsList>

          <TabsContent value="official">
            <OfficialTab />
          </TabsContent>
          <TabsContent value="community">
            <CommunityTab />
          </TabsContent>
          <TabsContent value="admin">
            <AdminTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

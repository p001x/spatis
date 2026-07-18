/**
 * Typed API client for the GeoPortal FastAPI backend.
 * All calls go through Vite's dev proxy (/api → localhost:8000)
 * so the same code works in production behind the reverse proxy.
 */

export const BASE = "/api";

export interface NDVIRequest {
  district: string;
  start_date: string;
  end_date: string;
  n_classes: number;
}

export interface ClassifyPanel {
  letter: string;
  name: string;
  title: string;
  tile_url: string;
  thumb_url: string;
  areas: Record<string, number>;
  breakpoints: number[];
}

export interface NDVIResult {
  tile_url: string;
  stats: Record<string, number>;
  class_areas_km2: Record<string, number>;
  classify: {
    panels: ClassifyPanel[];
    n_classes: number;
    percentile_steps: number[];
  };
  center: [number, number];
  district: string;
  start_date: string;
  end_date: string;
}

export interface LSTResult {
  tile_url: string;
  stats: Record<string, number>;
  class_areas_km2: Record<string, number>;
  classify: { panels: ClassifyPanel[]; n_classes: number; percentile_steps: number[] };
  center: [number, number];
  district: string;
  start_date: string;
  end_date: string;
}

export interface RUSLEResult {
  tile_url: string;
  risk_index: {
    tile_url: string;
    thumb_url: string;
    mean: number;
    std_dev: number;
    class_areas_km2: Record<string, number>;
    weight_pct_each: number;
  };
  stats: Record<string, number>;
  factor_means: Record<string, number>;
  class_areas_km2: Record<string, number>;
  n_class_soil_loss_km2: Record<string, number>;
  n_class_soil_loss_tile: string;
  factor_maps: Record<string, {
    label: string;
    tile_url: string;
    thumb_url: string;
    download_url: string;
    class_tile_url?: string;
    class_thumb_url?: string;
    reversed?: boolean;
    direction_desc?: string;
  }>;
  reverse_flags: Record<string, boolean>;
  center: [number, number];
  district: string;
  year: number;
}

export interface SlopeResult {
  slope_tile_url: string;
  hillshade_tile_url: string;
  aspect_tile_url: string;
  stats: Record<string, number>;
  class_areas_km2: Record<string, number>;
  classify: { panels: ClassifyPanel[]; n_classes: number; percentile_steps: number[] };
  center: [number, number];
  district: string;
}

export interface AhpData {
  weights: Record<string, number>;
  matrix: number[][];
  factor_labels: string[];
  lambda_max: number;
  ci: number;
  cr: number;
  ri: number;
  consistent: boolean;
  n: number;
}

export interface LandfillFactorMap {
  label: string;
  weight_pct: number;
  reversed: boolean;
  description: string;
  tile_url: string;
  thumb_url: string;
  download_url: string;
}

export interface LandfillResult {
  tile_url: string;
  thumb_url: string;
  stats: Record<string, number>;
  class_areas_km2: Record<string, number>;
  classify: { panels: ClassifyPanel[]; n_classes: number; percentile_steps: number[] };
  factor_maps: Record<string, LandfillFactorMap>;
  reverse_flags: Record<string, boolean>;
  weights_used: Record<string, number>;
  ahp_data: AhpData;
  center: [number, number];
  district: string;
}

export interface AirPollutionResult {
  tile_url: string;
  stats: Record<string, number>;
  exceeds_who: boolean;
  time_series: Array<{ year: number; month: number; "NO2 (µmol/m²)": number }>;
  classify: { panels: ClassifyPanel[]; n_classes: number; percentile_steps: number[] };
  center: [number, number];
  district: string;
  start_date: string;
  end_date: string;
}

export interface LandslideResult {
  lsi_tile_url: string;
  lsi_class_tile_url: string;
  stats: Record<string, number>;
  class_areas_km2: Record<string, number>;
  classify: { panels: ClassifyPanel[]; n_classes: number; percentile_steps: number[] };
  center: [number, number];
  district: string;
  start_year: number;
  end_year: number;
}

export interface UHIResult {
  center: [number, number];
  lst_tile_url: string;
  ndbi_tile_url: string;
  lst_thumb_url: string;
  ndbi_thumb_url: string;
  lst_stats: Record<string, number | null>;
  ndbi_stats: Record<string, number | null>;
  n_cells_total: number;
  n_cells_with_data: number;
  regression: {
    slope: number;
    intercept: number;
    r2: number;
    p_value: number;
    n: number;
  } | null;
  bivariate_png: string;
  scatter_png: string;
  grid_table: Array<{ grid_id: number; LST: number; NDBI: number }>;
}

export interface DatasetRecord {
  id: string;
  name: string;
  description: string;
  file_type: string;
  original_filename: string;
  bbox?: number[];
  file_size_mb: number;
  status: string;
  error_message?: string;
  source: string;
  contributor?: string;
  source_url?: string;
}

export interface TrainingSample {
  id: string;
  geometry: any;
  class_label: string;
  source_filename: string;
  source_url: string;
  creator: string;
  color: string;
  created_at: string;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  districts: () => get<{ districts: string[] }>("/districts"),
  ndvi: (req: NDVIRequest) => post<NDVIResult>("/ndvi", req),
  lst: (req: { district: string; start_date: string; end_date: string; n_classes: number }) =>
    post<LSTResult>("/lst", req),
  rusle: (req: {
    district: string;
    year: number;
    n_classes: number;
    reverse_r: boolean;
    reverse_k: boolean;
    reverse_ls: boolean;
    reverse_c: boolean;
    reverse_p: boolean;
  }) => post<RUSLEResult>("/rusle", req),
  slope: (req: { district: string; n_classes: number }) =>
    post<SlopeResult>("/slope", req),
  landfill: (req: {
    district: string;
    n_classes?: number;
    reverse_river?: boolean;
    reverse_residential?: boolean;
    reverse_slope?: boolean;
    reverse_road?: boolean;
    reverse_lulc?: boolean;
    custom_weights?: Record<string, number>;
  }) => post<LandfillResult>("/landfill", req),
  airPollution: (req: any) => post<AirPollutionResult>("/air-pollution", req),
  landslide: (req: any) => post<LandslideResult>("/landslide", req),
  uhi: (req: any) => post<UHIResult>("/uhi", req),
  adminVerify: (password: string) => post<{ ok: boolean }>("/admin/verify", { password }),
  samples: {
    list: () => get<{ samples: TrainingSample[] }>("/samples"),
    add: (body: any) => post<TrainingSample>("/samples", body),
    delete: (id: string) =>
      fetch(BASE + "/samples/" + id, { method: "DELETE" }).then((r) => r.json()) as Promise<{ ok: boolean }>,
  },
  datasets: {
    list: (source: string) => get<{ records: DatasetRecord[] }>("/datasets?source=" + source),
    upload: async (fd: FormData) => {
      const r = await fetch(BASE + "/datasets/upload", { method: "POST", body: fd });
      if (!r.ok) {
        const e = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(e.detail ?? r.statusText);
      }
      return r.json() as Promise<DatasetRecord>;
    },
    addLink: (body: any) => post<DatasetRecord>("/datasets/link", body),
    delete: (id: string, source: string) =>
      fetch(BASE + "/datasets/" + id + "?source=" + source, { method: "DELETE" }).then((r) =>
        r.json()
      ) as Promise<{ ok: boolean }>,
  },
};

import { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// Fix Leaflet default icon path broken by bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

export interface LegendItem {
  color: string;
  label: string;
}

interface Props {
  center: [number, number];
  tileUrl: string;
  zoom?: number;
  title?: string;
  legend?: LegendItem[];
  dataSource?: string;
}

/** Updates the GEE tile layer when tileUrl changes. */
function GEELayer({ tileUrl }: { tileUrl: string }) {
  const map = useMap();
  useEffect(() => {
    const layer = L.tileLayer(tileUrl, {
      attribution: "Google Earth Engine",
      opacity: 0.85,
    });
    layer.addTo(map);
    return () => { map.removeLayer(layer); };
  }, [tileUrl, map]);
  return null;
}

/** Fly to a new center when it changes. */
function FlyTo({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom, { duration: 1.2 });
  }, [center, zoom, map]);
  return null;
}

/** Leaflet scale bar (metric). */
function ScaleBar() {
  const map = useMap();
  useEffect(() => {
    const ctrl = L.control.scale({ imperial: false, position: "bottomleft" });
    ctrl.addTo(map);
    return () => { map.removeControl(ctrl); };
  }, [map]);
  return null;
}

/** North arrow SVG. */
function NorthArrow() {
  return (
    <svg width="28" height="36" viewBox="0 0 28 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polygon points="14,2 20,18 14,14 8,18" fill="#1a1a1a" />
      <polygon points="14,34 8,18 14,22 20,18" fill="#888" />
      <text x="14" y="10" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#fff" dy="-1">N</text>
    </svg>
  );
}

export function DistrictMap({
  center,
  tileUrl,
  zoom = 10,
  title,
  legend,
  dataSource = "Source: Google Earth Engine · ESA WorldCover · USGS SRTM · CARTO",
}: Props) {
  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: "100%", width: "100%", borderRadius: "0.5rem" }}
        scrollWheelZoom
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />
        <GEELayer tileUrl={tileUrl} />
        <FlyTo center={center} zoom={zoom} />
        <ScaleBar />
      </MapContainer>

      {/* Map title */}
      {title && (
        <div
          style={{ position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)", zIndex: 1000 }}
          className="bg-white/90 border border-gray-200 shadow rounded px-3 py-1 text-xs font-semibold text-gray-800 pointer-events-none whitespace-nowrap"
        >
          {title}
        </div>
      )}

      {/* North arrow */}
      <div
        style={{ position: "absolute", top: 8, right: 8, zIndex: 1000 }}
        className="bg-white/90 border border-gray-200 shadow rounded p-1 pointer-events-none"
        title="North"
      >
        <NorthArrow />
      </div>

      {/* Legend */}
      {legend && legend.length > 0 && (
        <div
          style={{ position: "absolute", bottom: 28, right: 8, zIndex: 1000 }}
          className="bg-white/92 border border-gray-200 shadow rounded p-2 pointer-events-none text-[11px]"
        >
          <p className="font-semibold text-gray-700 mb-1">Legend</p>
          {legend.map((item) => (
            <div key={item.label} className="flex items-center gap-1.5 py-0.5">
              <span
                className="inline-block w-3 h-3 rounded-sm shrink-0 border border-gray-300"
                style={{ background: item.color }}
              />
              <span className="text-gray-700">{item.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Data source */}
      <div
        style={{ position: "absolute", bottom: 4, left: "50%", transform: "translateX(-50%)", zIndex: 1000 }}
        className="bg-white/80 text-[9px] text-gray-500 px-2 py-0.5 rounded pointer-events-none whitespace-nowrap"
      >
        {dataSource}
      </div>
    </div>
  );
}

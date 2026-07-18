import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Center of Rwanda roughly
const DEFAULT_CENTER = [-1.9403, 29.8739];
const DEFAULT_ZOOM = 9;

function MapUpdater({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.flyTo(center, zoom || map.getZoom());
    }
  }, [center, zoom, map]);
  return null;
}

export default function MapViewer({ tileUrl, center }) {
  return (
    <div className="w-full h-full relative z-0">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        className="w-full h-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {tileUrl && (
          <TileLayer
            key={tileUrl} // re-mounts when URL changes
            url={tileUrl}
            opacity={0.8}
            maxZoom={20}
          />
        )}
        
        <MapUpdater center={center} />
      </MapContainer>
    </div>
  );
}

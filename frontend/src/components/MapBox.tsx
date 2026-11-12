import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useState } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";

export type MapMarker = {
  id: string;
  lat: number;
  lng: number;
  label: string;
  detail?: string;
  tone?: "depot" | "stop" | "vehicle" | "done";
};

export type MapLine = {
  id: string;
  points: [number, number][];
  tone?: "planned" | "travelled";
};

const TONES: Record<string, string> = {
  depot: "#6366f1",
  stop: "#38bdf8",
  vehicle: "#f59e0b",
  done: "#10b981",
};

const icon = (tone: string) =>
  L.divIcon({
    className: "",
    html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;
      background:${TONES[tone] ?? TONES.stop};border:2px solid #0b1220;
      box-shadow:0 0 0 2px ${TONES[tone] ?? TONES.stop}55"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });

/**
 * Leaflet wrapper that degrades honestly: if the tile provider is unreachable we
 * show a banner and keep the overlay data (markers/polylines) and the caller's
 * list view usable, rather than blanking the page.
 */
export function MapBox({
  markers,
  lines = [],
  center,
  zoom = 11,
  height = "460px",
  fallback,
}: {
  markers: MapMarker[];
  lines?: MapLine[];
  center: [number, number];
  zoom?: number;
  height?: string;
  fallback?: React.ReactNode;
}) {
  const [tilesFailed, setTilesFailed] = useState(false);

  return (
    <div className="relative" style={{ height }}>
      {tilesFailed && (
        <div
          role="status"
          className="absolute inset-x-3 top-3 z-[500] rounded-lg border border-amber-500/40 bg-amber-500/15 px-3 py-2 text-xs text-amber-100 backdrop-blur"
        >
          Map tiles are unavailable. Route geometry and stop order are still shown
          below.
        </div>
      )}
      <MapContainer center={center} zoom={zoom} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          eventHandlers={{ tileerror: () => setTilesFailed(true) }}
        />
        {lines.map((line) => (
          <Polyline
            key={line.id}
            positions={line.points}
            pathOptions={{
              color: line.tone === "travelled" ? "#10b981" : "#6366f1",
              weight: 4,
              opacity: 0.85,
              dashArray: line.tone === "travelled" ? undefined : "6 6",
            }}
          />
        ))}
        {markers.map((marker) => (
          <Marker
            key={marker.id}
            position={[marker.lat, marker.lng]}
            icon={icon(marker.tone ?? "stop")}
          >
            <Popup>
              <span className="text-xs font-semibold">{marker.label}</span>
              {marker.detail && (
                <>
                  <br />
                  <span className="text-[11px] text-slate-600">{marker.detail}</span>
                </>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      {tilesFailed && fallback && <div className="mt-3">{fallback}</div>}
    </div>
  );
}

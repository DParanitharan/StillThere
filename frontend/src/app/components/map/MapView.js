"use client";

import { useEffect, useState, useMemo } from "react";
import styles from "./MapView.module.css";

const SG_BOUNDS = [
  [1.15, 103.58], // southwest (lat, lng)
  [1.48, 104.1], // northeast (lat, lng)
];

function FlyTo({ searchPoint, useMap }) {
  const map = useMap();

  useEffect(() => {
    if (!searchPoint) return;

    if (searchPoint.label === "Singapore") {
      map.fitBounds(SG_BOUNDS, { padding: [30, 30], duration: 0.8 });
    } else {
      map.flyTo([searchPoint.lat, searchPoint.lng], 16, { duration: 0.8 });
    }
  }, [searchPoint, map]);

  return null;
}

function FitBounds({ geojson, useMap, L }) {
  const map = useMap();

  useEffect(() => {
    if (!geojson || !geojson.features?.length) return;

    try {
      const geoLayer = L.geoJSON(geojson);
      const bounds = geoLayer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 18 });
      }
    } catch (e) {
      console.warn("FitBounds failed:", e);
    }
  }, [geojson, map, L]);

  return null;
}

export default function MapView({
  geoData,
  buildingsGeoData,
  searchPoint,
  chatOverlay,
}) {
  const [MapComponents, setMapComponents] = useState(null);
  const [showSatellite, setShowSatellite] = useState(false);

  useEffect(() => {
    if (!geoData && !searchPoint) return;

    const loadMap = async () => {
      const L = await import("leaflet");
      const { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap } =
        await import("react-leaflet");
      await import("leaflet/dist/leaflet.css");

      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
        iconUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
        shadowUrl:
          "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
      });
      setMapComponents({
        MapContainer,
        TileLayer,
        GeoJSON,
        Marker,
        Popup,
        useMap,
        L,
      });
    };
    loadMap();
  }, [geoData, searchPoint]);

  const getInputStyle = () => ({
    color: "#3388ff",
    weight: 2,
    fillColor: "#3388ff",
    fillOpacity: 0.15,
  });

  const getClassifiedStyle = (feature) => {
    const status = feature?.properties?.status;
    switch (status) {
      case "unchanged":
        return {
          color: "#16a34a",
          weight: 2,
          fillColor: "#16a34a",
          fillOpacity: 0.3,
        };
      case "modified":
        return {
          color: "#f59e0b",
          weight: 2,
          fillColor: "#f59e0b",
          fillOpacity: 0.4,
        };
      case "removed":
        return {
          color: "#ef4444",
          weight: 2,
          fillColor: "#ef4444",
          fillOpacity: 0.4,
        };
      default:
        return {
          color: "#6b7280",
          weight: 1,
          fillColor: "#6b7280",
          fillOpacity: 0.2,
        };
    }
  };

  const getChatOverlayStyle = (feature) => {
    const classification = feature?.properties?.classification;
    const fillColors = {
      unchanged: "#16a34a",
      modified: "#f59e0b",
      removed: "#ef4444",
      new: "#3b82f6",
    };
    const fillColor = fillColors[classification] || "#06b6d4";

    return {
      color: "#06b6d4",
      weight: 3,
      fillColor: fillColor,
      fillOpacity: 0.5,
      dashArray: "6 3",
    };
  };

  const onEachFeature = (feature, layer) => {
    const props = feature?.properties || {};
    let metrics = {};
    try {
      metrics = props.metrics ? JSON.parse(props.metrics) : {};
    } catch (e) {
      metrics = {};
    }

    const statusColor =
      {
        unchanged: "#16a34a",
        modified: "#f59e0b",
        removed: "#ef4444",
      }[props.status] || "#6b7280";

    layer.bindPopup(
      `<div style="min-width:200px">` +
        `<h4 style="margin:0 0 8px;color:${statusColor}">` +
        `${(props.status || "unknown").toUpperCase()}</h4>` +
        `<table style="font-size:12px;width:100%">` +
        `<tr><td><b>Building ID</b></td><td>${props.input_idx ?? "—"}</td></tr>` +
        `<tr><td><b>IoU</b></td><td>${(props.iou ?? 0).toFixed(3)}</td></tr>` +
        `<tr><td><b>SAM Confidence</b></td><td>${(props.confidence ?? 0).toFixed(2)}</td></tr>` +
        `<tr><td><b>SAM Score</b></td><td>${(metrics.sam_score ?? 0).toFixed(2)}</td></tr>` +
        `</table>` +
        `</div>`,
    );
  };

  const onEachChatFeature = (feature, layer) => {
    const props = feature?.properties || {};
    const classification = props.classification;
    const statusColor =
      {
        unchanged: "#16a34a",
        modified: "#f59e0b",
        removed: "#ef4444",
        new: "#3b82f6",
      }[classification] || "#06b6d4";

    const rows = Object.entries(props)
      .filter(([k]) => k !== "st_asgeojson")
      .map(([k, v]) => {
        const displayVal =
          typeof v === "number"
            ? v.toLocaleString(undefined, { maximumFractionDigits: 4 })
            : String(v ?? "—");
        return `<tr><td><b>${k}</b></td><td>${displayVal}</td></tr>`;
      })
      .join("");

    layer.bindPopup(
      `<div style="min-width:220px">` +
        `<h4 style="margin:0 0 8px;color:${statusColor}">` +
        `🔍 Query Result</h4>` +
        `<table style="font-size:12px;width:100%">${rows}</table>` +
        `</div>`,
    );
  };

  const getCenter = (data) => {
    if (!data || !data.features || data.features.length === 0) {
      return [1.3521, 103.8198];
    }

    let minLat = Infinity,
      maxLat = -Infinity;
    let minLng = Infinity,
      maxLng = -Infinity;

    data.features.forEach((feature) => {
      if (!feature.geometry?.coordinates) return;
      const coords = feature.geometry.coordinates;

      const processCoords = (coordArray) => {
        if (typeof coordArray[0] === "number") {
          minLng = Math.min(minLng, coordArray[0]);
          maxLng = Math.max(maxLng, coordArray[0]);
          minLat = Math.min(minLat, coordArray[1]);
          maxLat = Math.max(maxLat, coordArray[1]);
        } else {
          coordArray.forEach(processCoords);
        }
      };

      processCoords(coords);
    });

    if (!isFinite(minLat)) return [1.3521, 103.8198];
    return [(minLat + maxLat) / 2, (minLng + maxLng) / 2];
  };

  const chatOverlayKey = useMemo(() => {
    if (!chatOverlay?.features?.length) return "chat-none";
    return `chat-${chatOverlay.features.length}-${Date.now()}`;
  }, [chatOverlay]);

  if (!geoData && !searchPoint) {
    return (
      <div className={styles.placeholder}>
        <div className={styles.placeholderContent}>
          <span className={styles.placeholderIcon}>🗺️</span>
          <h2>No Map Data</h2>
          <p>Upload a shapefile to visualise building footprints</p>
          <div className={styles.instructions}>
            <div className={styles.step}>
              <span className={styles.stepNumber}>1</span>
              <span>Upload a ZIP file containing your shapefile</span>
            </div>
            <div className={styles.step}>
              <span className={styles.stepNumber}>2</span>
              <span>View polygons rendered on the map</span>
            </div>
            <div className={styles.step}>
              <span className={styles.stepNumber}>3</span>
              <span>Run analysis to detect changes</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!MapComponents) {
    return (
      <div className={styles.placeholder}>
        <div className={styles.loadingContent}>
          <div className={styles.spinner}></div>
          <p>Loading map...</p>
        </div>
      </div>
    );
  }

  const { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap, L } =
    MapComponents;
  const center = searchPoint
    ? [searchPoint.lat, searchPoint.lng]
    : getCenter(geoData);
  const hasClassifiedData = buildingsGeoData?.features?.length > 0;
  const hasChatOverlay = chatOverlay?.features?.length > 0;
  const inputKey = geoData ? `input-${geoData.features?.length}` : "none";
  const buildingsKey = buildingsGeoData
    ? `bld-${buildingsGeoData.features?.length}-${buildingsGeoData.features?.[0]?.properties?.status}`
    : "none";

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      <MapContainer
        center={center}
        zoom={15}
        style={{ height: "100%", width: "100%" }}
      >
        {!showSatellite && (
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        )}

        {showSatellite && (
          <TileLayer
            attribution="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
        )}

        {geoData?.features?.length > 0 && !hasClassifiedData && (
          <GeoJSON key={inputKey} data={geoData} style={getInputStyle} />
        )}

        {hasClassifiedData && (
          <GeoJSON
            key={buildingsKey}
            data={buildingsGeoData}
            style={getClassifiedStyle}
            onEachFeature={onEachFeature}
          />
        )}

        {hasChatOverlay && (
          <GeoJSON
            key={chatOverlayKey}
            data={chatOverlay}
            style={getChatOverlayStyle}
            onEachFeature={onEachChatFeature}
          />
        )}

        {hasChatOverlay && (
          <FitBounds geojson={chatOverlay} useMap={useMap} L={L} />
        )}

        <FlyTo searchPoint={searchPoint} useMap={useMap} />
        {searchPoint && (
          <Marker position={[searchPoint.lat, searchPoint.lng]}>
            <Popup>{searchPoint.label || "Selected location"}</Popup>
          </Marker>
        )}
      </MapContainer>

      {/* Satellite toggle button */}
      <button
        onClick={() => setShowSatellite(!showSatellite)}
        style={{
          position: "absolute",
          top: 10,
          right: 10,
          zIndex: 1000,
          padding: "8px 14px",
          backgroundColor: showSatellite ? "#1e293b" : "#fff",
          color: showSatellite ? "#fff" : "#1e293b",
          border: "2px solid #1e293b",
          borderRadius: "8px",
          cursor: "pointer",
          fontSize: "13px",
          fontWeight: "bold",
          boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
          fontFamily: "inherit",
        }}
      >
        {showSatellite ? "🗺️ Street" : "🛰️ Satellite"}
      </button>

      <div className={styles.legend}>
        <h4>Legend</h4>
        {[
          { label: "Unchanged", color: "#16a34a" },
          { label: "Modified", color: "#f59e0b" },
          { label: "Removed", color: "#ef4444" },
          ...(hasChatOverlay
            ? [{ label: "Query Result", color: "#06b6d4" }]
            : []),
        ].map(({ label, color }) => (
          <div key={label} className={styles.legendItem}>
            <span
              className={styles.legendColor}
              style={{ backgroundColor: color }}
            ></span>
            {label}
          </div>
        ))}
      </div>

      <div className={styles.featureCount}>
        {(hasClassifiedData
          ? buildingsGeoData.features.length
          : geoData?.features?.length) || 0}{" "}
        features
        {hasChatOverlay && ` · ${chatOverlay.features.length} query results`}
      </div>
    </div>
  );
}

import React, { useEffect, useRef } from "react";
import L from "leaflet";

export default function LiveMap({ events, onRunAI }) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(null);

  // Initialize Map
  useEffect(() => {
    if (mapRef.current) return; // already initialized

    // Center of Bengaluru
    const map = L.map(mapContainerRef.current).setView([12.9716, 77.5946], 12);
    
    // Light thematic tiles for premium dashboard light re-theme
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 20
    }).addTo(map);

    mapRef.current = map;
    markersRef.current = L.layerGroup().addTo(map);

    // Clean up on unmount
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update Markers when events change
  useEffect(() => {
    if (!mapRef.current || !markersRef.current) return;

    markersRef.current.clearLayers();

    events.forEach(e => {
      const isHigh = e.priority === "High";
      const color = isHigh ? "#DC2626" : "#D97706";

      const icon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color:${color}; width:13px; height:13px; border-radius:50%; border:2px solid #FFFFFF; box-shadow: 0 1px 6px rgba(0,0,0,0.3), 0 0 8px ${color};"></div>`,
        iconSize: [13, 13],
        iconAnchor: [6.5, 6.5]
      });

      const marker = L.marker([e.latitude, e.longitude], { icon: icon });

      // Create popup content
      const container = document.createElement("div");
      container.style.fontFamily = "'Inter', sans-serif";
      container.style.color = "var(--text-primary)";
      container.style.width = "200px";

      container.innerHTML = `
        <div style="font-size:11px; text-transform:uppercase; color:${color}; font-weight:700; margin-bottom:4px;">
          ${e.priority} Priority Incident
        </div>
        <div style="font-size:13px; font-weight:700; margin-bottom:2px; color:var(--text-primary);">
          ${e.event_cause.replace(/_/g, " ").toUpperCase()}
        </div>
        <div style="font-size:11px; color:var(--text-secondary); margin-bottom:8px; line-height:1.4;">
          ${e.corridor || "Non-corridor"} <br>
          ${e.address || "Bengaluru"}
        </div>
      `;

      const actionBtn = document.createElement("button");
      actionBtn.className = "btn btn-primary";
      actionBtn.style.width = "100%";
      actionBtn.style.fontSize = "10px";
      actionBtn.style.padding = "6px";
      actionBtn.style.justifyContent = "center";
      actionBtn.style.height = "auto";
      actionBtn.textContent = "🔮 See AI Recommendation";
      actionBtn.onclick = () => {
        onRunAI(e.id);
      };

      container.appendChild(actionBtn);

      marker.bindPopup(container);
      markersRef.current.addLayer(marker);
    });
  }, [events, onRunAI]);

  // Center map on specific coords
  const focusIncident = (lat, lon) => {
    if (mapRef.current) {
      mapRef.current.setView([lat, lon], 14);
      markersRef.current.eachLayer(layer => {
        if (layer.getLatLng().lat === lat && layer.getLatLng().lng === lon) {
          layer.openPopup();
        }
      });
    }
  };

  return (
    <div className="screen active">
      <div className="page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div className="page-title">Live Incident Map</div>
          <div className="page-sub">
            <span className="live-dot"></span>
            {events.length} active incidents monitored across city corridors
          </div>
        </div>
        <div>
          <button className="btn btn-ghost" onClick={() => focusIncident(12.9716, 77.5946)}>📍 Center Bengaluru</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2.1fr 1fr", gap: "20px", alignItems: "start" }}>
        <div>
          <div className="map-container" style={{ height: "520px" }}>
            <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />
          </div>
        </div>

        <div>
          <div className="card-title">Live Active Feed</div>
          <div className="incident-panel">
            {events.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)", fontSize: "13px" }}>
                No active incidents. Bengaluru roads are clear!
              </div>
            ) : (
              events.map(e => {
                const isHigh = e.priority === "High";
                const causeLabel = e.event_cause.replace(/_/g, " ").toUpperCase();
                const badgeColor = isHigh ? "badge-red" : "badge-blue";
                const dateObj = e.start_datetime ? new Date(e.start_datetime) : null;
                const timeLabel = dateObj ? dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recent";

                return (
                  <div
                    key={e.id}
                    className="incident-card"
                    onClick={() => focusIncident(e.latitude, e.longitude)}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
                      <span className={`badge ${badgeColor}`}>{e.priority} Priority</span>
                      <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontWeight: "500" }}>{timeLabel}</span>
                    </div>
                    <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)", marginBottom: "2px" }}>
                      {causeLabel}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      {e.corridor || "Non-corridor"} · {e.address || "Bengaluru"}
                    </div>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", alignItems: "center", borderTop: "1px solid var(--border)", paddingTop: "8px" }}>
                      {e.requires_road_closure === 1 && (
                        <span className="badge badge-amber" style={{ fontSize: "9px", padding: "2px 6px" }}>Road Closure</span>
                      )}
                      {e.authenticated ? (
                        <span className="badge badge-green" style={{ fontSize: "9px", padding: "2px 6px" }}>✓ Verified</span>
                      ) : (
                        <span className="badge" style={{ fontSize: "9px", padding: "2px 6px", background: "var(--bg)", color: "var(--text-tertiary)" }}>Unverified</span>
                      )}
                      <button
                        className="btn btn-primary"
                        style={{ padding: "4px 8px", fontSize: "9px", marginLeft: "auto", height: "auto" }}
                        onClick={(evt) => {
                          evt.stopPropagation();
                          onRunAI(e.id);
                        }}
                      >
                        🔮 See AI Rec
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect, useRef, useMemo } from "react";
import L from "leaflet";

const API = import.meta.env.VITE_API_URL || "";

const STATUS_COLOR = {
  Low: "var(--green)",
  Medium: "var(--amber)",
  High: "var(--red)",
  Unknown: "var(--text-tertiary)",
};

const STATUS_BG = {
  Low: "rgba(0,200,83,0.08)",
  Medium: "rgba(255,160,0,0.08)",
  High: "rgba(255,82,82,0.08)",
  Unknown: "rgba(255,255,255,0.04)",
};

const RISK_ICON = { Low: "🟢", Medium: "🟡", High: "🔴", Unknown: "⚪" };

const PRIORITY_FILTERS = ["All", "High", "Low"];

const CCTV_VIDEOS = [
  "/215258_medium.mp4",
  "/istockphoto-1131595282-640_adpp_is.mp4",
  "/istockphoto-1162603138-640_adpp_is.mp4",
];

export default function LiveMap({ events, onRunAI, onScanComplete, addToast }) {
  // Map refs
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef(null);

  // Data state
  const [traffic, setTraffic] = useState([]);
  const [weather, setWeather] = useState(null);
  const [trafficLoading, setTrafficLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportForm, setReportForm] = useState({ event_cause: 'vehicle_breakdown', corridor: 'Non-corridor', veh_type: 'N/A', address: '', reporter_name: 'Field Officer' });
  const [reportSubmitting, setReportSubmitting] = useState(false);

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("All");
  const [cctvData, setCctvData] = useState(null);

  // Filtered events
  const filteredEvents = useMemo(() => {
    let result = events;
    
    if (priorityFilter !== "All") {
      result = result.filter((e) => e.priority === priorityFilter);
    }
    
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter((e) => 
        (e.event_cause || "").toLowerCase().includes(q) ||
        (e.corridor || "").toLowerCase().includes(q) ||
        (e.address || "").toLowerCase().includes(q)
      );
    }

    return result;
  }, [events, searchQuery, priorityFilter]);

  // Initialize Map
  useEffect(() => {
    if (mapRef.current) return; // already initialized

    const map = L.map(mapContainerRef.current).setView([12.9716, 77.5946], 12);
    
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const tileUrl = isDark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    
    L.tileLayer(tileUrl, {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      maxZoom: 20
    }).addTo(map);

    mapRef.current = map;
    markersRef.current = L.layerGroup().addTo(map);

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Update Markers when filtered events change
  useEffect(() => {
    if (!mapRef.current || !markersRef.current) return;

    markersRef.current.clearLayers();

    filteredEvents.forEach(e => {
      const isHigh = e.priority === "High";
      const color = isHigh ? "#DC2626" : "#D97706";

      const icon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color:${color}; width:13px; height:13px; border-radius:50%; border:2px solid #FFFFFF; box-shadow: 0 1px 6px rgba(0,0,0,0.3), 0 0 8px ${color};"></div>`,
        iconSize: [13, 13],
        iconAnchor: [6.5, 6.5]
      });

      const marker = L.marker([e.latitude, e.longitude], { icon: icon });

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

      const cctvBtn = document.createElement("button");
      cctvBtn.className = "btn";
      cctvBtn.style.width = "100%";
      cctvBtn.style.fontSize = "10px";
      cctvBtn.style.padding = "6px";
      cctvBtn.style.justifyContent = "center";
      cctvBtn.style.height = "auto";
      cctvBtn.style.marginTop = "6px";
      cctvBtn.style.background = "var(--bg)";
      cctvBtn.style.color = "var(--text-secondary)";
      cctvBtn.style.border = "1px solid var(--border)";
      cctvBtn.textContent = "📹 View Live Camera";
      cctvBtn.onmouseover = () => { cctvBtn.style.background = "var(--card-bg)"; cctvBtn.style.color = "var(--text-primary)"; };
      cctvBtn.onmouseout = () => { cctvBtn.style.background = "var(--bg)"; cctvBtn.style.color = "var(--text-secondary)"; };
      cctvBtn.onclick = () => {
        const randomVid = CCTV_VIDEOS[Math.floor(Math.random() * CCTV_VIDEOS.length)];
        setCctvData({ corridor: e.corridor || "Bengaluru Traffic", videoUrl: randomVid });
      };

      container.appendChild(actionBtn);
      container.appendChild(cctvBtn);

      marker.bindPopup(container);
      markersRef.current.addLayer(marker);
    });
  }, [filteredEvents, onRunAI]);

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

  // Fetch Live Traffic and Weather
  useEffect(() => {
    async function fetchLive() {
      try {
        const [trafficRes, weatherRes] = await Promise.all([
          fetch(`${API}/api/traffic/live`),
          fetch(`${API}/api/traffic/weather`),
        ]);
        if (trafficRes.ok) {
          const d = await trafficRes.json();
          setTraffic(d.corridors || []);
          setLastUpdate(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
        }
        if (weatherRes.ok) {
          setWeather(await weatherRes.json());
        }
      } catch (e) {
        console.error("Live traffic fetch failed:", e);
      } finally {
        setTrafficLoading(false);
      }
    }
    fetchLive();
    const interval = setInterval(fetchLive, 120000); // refresh every 2 min
    return () => clearInterval(interval);
  }, []);

  // Smooth scan without page reload
  const handleScan = async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API}/api/scan`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        addToast?.("✅", data.message || "Scan complete!");
        // Refresh events without page reload
        if (onScanComplete) await onScanComplete();
      } else {
        addToast?.("⚠️", "Scan failed — check API connection.");
      }
    } catch (e) {
      console.error("Scan failed:", e);
      addToast?.("❌", "Network error during scan.");
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="screen active">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <div className="page-title">Live Intelligence Map</div>
          <div className="page-sub">
            <span className="live-dot"></span>
            Real-time incident mapping & live corridor congestion
            {lastUpdate && <span style={{ marginLeft: 8, color: "var(--text-tertiary)" }}>· Updated {lastUpdate}</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <button
            onClick={() => setShowReportModal(true)}
            style={{
              background: "linear-gradient(135deg, #dc2626, #b91c1c)",
              color: "white", border: "none", borderRadius: "8px",
              padding: "9px 16px", fontWeight: "700", fontSize: "12px",
              cursor: "pointer", display: "flex", alignItems: "center", gap: "6px"
            }}
          >
            📝 Report Incident
          </button>
          <button
            className={`btn btn-scan ${scanning ? "scanning" : ""}`}
            onClick={handleScan}
            disabled={scanning}
          >
            {scanning ? "⏳ Scanning..." : "🔍 Scan Live Anomalies"}
          </button>
          {weather && (
            <div className="card" style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
              <span style={{ fontSize: "22px" }}>
                {weather.condition === "Rain" ? "🌧" : weather.condition === "Clouds" ? "☁️" : "☀️"}
              </span>
              <div>
                <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)" }}>
                  {weather.temperature_c != null ? `${Math.round(weather.temperature_c)}°C` : "—"}
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-tertiary)", textTransform: "uppercase" }}>
                  {weather.condition_detail || weather.condition || "Bengaluru"}
                </div>
              </div>
              {weather.rainfall_mm > 0 && (
                <div style={{ fontSize: "11px", color: "var(--blue)", fontWeight: "700" }}>
                  💧 {weather.rainfall_mm}mm rain
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main Content: Map & Incidents */}
      <div style={{ display: "grid", gridTemplateColumns: "2.1fr 1fr", gap: "20px", alignItems: "start", marginBottom: "20px" }}>
        {/* Leaflet Map */}
        <div>
          <div className="map-container" style={{ height: "450px" }}>
            <div ref={mapContainerRef} style={{ width: "100%", height: "100%" }} />
          </div>
          <div style={{ marginTop: "10px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="btn btn-ghost" onClick={() => focusIncident(12.9716, 77.5946)}>📍 Recenter Bengaluru</button>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", alignSelf: "center" }}>
                Showing {filteredEvents.length} of {events.length} incidents
              </span>
            </div>
            <div style={{ fontSize: "11px", color: "var(--amber)", fontWeight: "600", display: "flex", alignItems: "center", gap: "6px", background: "rgba(245, 158, 11, 0.1)", padding: "4px 10px", borderRadius: "99px", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
              <span style={{ fontSize: "14px" }}>💡</span> Click any map marker to view its Live Camera feed
            </div>
          </div>
        </div>

        {/* Active Incident Feed */}
        <div>
          <div className="card-title" style={{ marginBottom: "8px" }}>Active Incidents</div>
          
          {/* Search */}
          <div className="search-wrapper">
            <input
              className="search-input"
              type="text"
              placeholder="Search by cause, corridor, address..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Priority Filter Pills */}
          <div className="filter-pills">
            {PRIORITY_FILTERS.map((f) => (
              <button
                key={f}
                className={`filter-pill ${priorityFilter === f ? "active" : ""}`}
                onClick={() => setPriorityFilter(f)}
              >
                {f === "All" ? `All (${events.length})` : `${f} (${events.filter(e => e.priority === f).length})`}
              </button>
            ))}
          </div>

          <div className="incident-panel" style={{ maxHeight: "390px", overflowY: "auto", paddingRight: "5px" }}>
            {filteredEvents.length === 0 ? (
              <div style={{ padding: "30px", textAlign: "center", color: "var(--text-secondary)", fontSize: "13px" }}>
                {events.length === 0 ? "No active incidents. Press 'Scan Live Anomalies' to fetch." : "No incidents match your search."}
              </div>
            ) : (
              filteredEvents.map(e => {
                const isHigh = e.priority === "High";
                const causeLabel = e.event_cause.replace(/_/g, " ").toUpperCase();
                const badgeColor = isHigh ? "badge-red" : "badge-blue";
                const dateObj = e.start_datetime ? new Date(e.start_datetime) : null;
                const timeLabel = dateObj ? dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recent";

                return (
                  <div
                    key={e.id}
                    className="incident-card"
                    style={{ marginBottom: "10px" }}
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
                      <button
                        className="btn btn-primary"
                        style={{ padding: "4px 8px", fontSize: "9px", marginLeft: "auto", height: "auto" }}
                        onClick={(evt) => {
                          evt.stopPropagation();
                          onRunAI(e.id);
                        }}
                      >
                        🔮 AI Recommendation
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Corridor Health Grid (Bottom) */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: "16px" }}>
          Live Corridor Congestion Monitor
        </div>
        {trafficLoading ? (
          <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "30px", fontSize: "13px" }}>
            Fetching real-time corridor data...
          </div>
        ) : traffic.length === 0 ? (
          <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "30px", fontSize: "13px" }}>
            Traffic data initializing — first snapshot arriving momentarily...
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "12px" }}>
            {traffic.map((c, i) => {
              const pct = c.congestion_percent != null ? Math.round(c.congestion_percent) : null;
              const status = c.status || "Unknown";
              const color = STATUS_COLOR[status];
              const bg = STATUS_BG[status];
              return (
                <div
                  key={i}
                  style={{ background: bg, border: `1px solid ${color}33`, borderRadius: "8px", padding: "10px 14px" }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <span style={{ fontWeight: "700", fontSize: "13px", color: "var(--text-primary)" }}>
                      {c.corridor}
                    </span>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {c.incident_count > 0 && (
                        <span className="badge badge-red" style={{ fontSize: "9px" }}>
                          {c.incident_count} incident{c.incident_count > 1 ? "s" : ""}
                        </span>
                      )}
                      <span style={{ fontSize: "12px", fontWeight: "800", color }}>
                        {pct != null ? `${pct}%` : "—"}
                      </span>
                    </div>
                  </div>
                  {/* Congestion bar */}
                  <div style={{ height: "5px", background: "var(--bg)", borderRadius: "99px", overflow: "hidden", marginBottom: "5px" }}>
                    <div style={{ height: "100%", width: `${pct ?? 0}%`, background: color, borderRadius: "99px", transition: "width 0.5s ease" }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--text-tertiary)" }}>
                    <span>
                      {c.current_speed != null ? `${c.current_speed} km/h` : "Speed N/A"}
                    </span>
                    <span style={{ color: "var(--text-secondary)" }}>
                      {RISK_ICON[c.risk_30min || "Unknown"]} +30m · {RISK_ICON[c.risk_60min || "Unknown"]} +60m
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* CCTV Modal */}
      {cctvData && (
        <div className="cctv-overlay" onClick={() => setCctvData(null)}>
          <div className="cctv-modal" onClick={e => e.stopPropagation()}>
            <div className="cctv-header">
              <div className="cctv-cam-name">
                <div className="cctv-rec"></div>
                CAM: {cctvData.corridor.toUpperCase()}
              </div>
              <button className="cctv-close" onClick={() => setCctvData(null)}>✖</button>
            </div>
            <div className="cctv-feed-container">
              <video src={cctvData.videoUrl} autoPlay loop muted playsInline />
              <div className="cctv-scanline"></div>
              <div style={{ position: "absolute", top: "16px", left: "16px", backgroundColor: "rgba(220, 38, 38, 0.8)", color: "white", padding: "4px 8px", fontSize: "10px", fontWeight: "bold", borderRadius: "4px", letterSpacing: "1px", zIndex: 4, backdropFilter: "blur(4px)", border: "1px solid rgba(255,255,255,0.3)" }}>
                ⚠️ SIMULATED DEMO FEED
              </div>
              <div className="cctv-timestamp">LIVE - {new Date().toLocaleTimeString("en-IN")}</div>
            </div>
          </div>
        </div>
      )}

      {/* Report Incident Modal */}
      {showReportModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
          zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(6px)"
        }} onClick={(e) => e.target === e.currentTarget && setShowReportModal(false)}>
          <div style={{
            background: "var(--card-bg)", border: "1px solid var(--border)",
            borderRadius: "16px", padding: "28px", width: "480px", maxHeight: "90vh",
            overflowY: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.5)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", color: "var(--text-primary)", margin: 0 }}>📝 Report New Incident</h3>
              <button onClick={() => setShowReportModal(false)} style={{ background: "none", border: "none", fontSize: "18px", cursor: "pointer", color: "var(--text-tertiary)" }}>✕</button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {/* Event Cause */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Event Cause</label>
                <select
                  value={reportForm.event_cause}
                  onChange={e => setReportForm(p => ({...p, event_cause: e.target.value}))}
                  style={{ width: "100%", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}
                >
                  {["vehicle_breakdown","accident","construction","water_logging","vip_movement","public_event","pot_holes","tree_fall","Stationary Traffic","Jam","Queueing Traffic","abandoned_vehicle","oil_spill","pedestrian_incident","others"].map(c => (
                    <option key={c} value={c}>{c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</option>
                  ))}
                </select>
              </div>

              {/* Corridor */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Corridor</label>
                <select
                  value={reportForm.corridor}
                  onChange={e => setReportForm(p => ({...p, corridor: e.target.value}))}
                  style={{ width: "100%", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}
                >
                  {["Tumkur Road","Mysore Road","Bellary Road 1","Bellary Road 2","Hosur Road","ORR East 1","ORR East 2","ORR North 1","Old Madras Road","Bannerghata Road","Magadi Road","West of Chord Road","CBD 1","Non-corridor"].map(c => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>

              {/* Vehicle Type */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Vehicle Type</label>
                <select
                  value={reportForm.veh_type}
                  onChange={e => setReportForm(p => ({...p, veh_type: e.target.value}))}
                  style={{ width: "100%", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}
                >
                  {["N/A","heavy_vehicle","lcv","private_car","bus","two_wheeler"].map(v => (
                    <option key={v} value={v}>{v.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</option>
                  ))}
                </select>
              </div>

              {/* Address */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Address / Landmark</label>
                <input
                  value={reportForm.address}
                  onChange={e => setReportForm(p => ({...p, address: e.target.value}))}
                  placeholder="e.g. Near Silk Board Junction"
                  style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}
                />
              </div>

              {/* Reporter Name */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Reporter Name</label>
                <input
                  value={reportForm.reporter_name}
                  onChange={e => setReportForm(p => ({...p, reporter_name: e.target.value}))}
                  placeholder="Officer name or badge ID"
                  style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}
                />
              </div>

              {/* Submit */}
              <button
                disabled={reportSubmitting}
                onClick={async () => {
                  setReportSubmitting(true);
                  try {
                    const res = await fetch(`${API}/api/incidents/report`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(reportForm),
                    });
                    if (res.ok) {
                      setShowReportModal(false);
                      setReportForm({ event_cause: 'vehicle_breakdown', corridor: 'Non-corridor', veh_type: 'N/A', address: '', reporter_name: 'Field Officer' });
                      addToast?.("✅", "Incident reported successfully!");
                      if (onScanComplete) await onScanComplete();
                    } else {
                      addToast?.("❌", "Failed to submit incident report.");
                    }
                  } catch (err) {
                    addToast?.("❌", "Network error submitting report.");
                  } finally {
                    setReportSubmitting(false);
                  }
                }}
                style={{
                  background: reportSubmitting ? "var(--border)" : "linear-gradient(135deg, #dc2626, #b91c1c)",
                  color: "white", border: "none", borderRadius: "10px",
                  padding: "12px", fontWeight: "700", fontSize: "14px",
                  cursor: reportSubmitting ? "not-allowed" : "pointer", marginTop: "4px"
                }}
              >
                {reportSubmitting ? "Submitting..." : "📝 Submit Incident Report"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

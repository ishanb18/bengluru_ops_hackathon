import React, { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

export default function LiveMap({ events, onRunAI }) {
  const [traffic, setTraffic] = useState([]);
  const [weather, setWeather] = useState(null);
  const [trafficLoading, setTrafficLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

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

  return (
    <div className="screen active">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <div className="page-title">Live Traffic Intelligence</div>
          <div className="page-sub">
            Real-time congestion across 10 Bengaluru corridors · TomTom Flow API
            {lastUpdate && <span style={{ marginLeft: 8, color: "var(--text-tertiary)" }}>· Updated {lastUpdate}</span>}
          </div>
        </div>
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

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "20px" }}>

        {/* Corridor Health Grid */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: "16px" }}>
            Corridor Congestion Monitor
          </div>
          {trafficLoading ? (
            <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "30px", fontSize: "13px" }}>
              Fetching real-time corridor data...
            </div>
          ) : traffic.length === 0 ? (
            <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "30px", fontSize: "13px" }}>
              Traffic data initializing — first snapshot in ~10 minutes after server start.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
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
                        <span style={{ fontSize: "10px", fontWeight: "700", color, padding: "2px 7px", border: `1px solid ${color}`, borderRadius: "4px" }}>
                          {status}
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
                        {c.free_flow_speed != null ? ` (free-flow: ${c.free_flow_speed} km/h)` : ""}
                      </span>
                      <span style={{ color: "var(--text-secondary)" }}>
                        {RISK_ICON[c.risk_30min || "Unknown"]} 30min · {RISK_ICON[c.risk_60min || "Unknown"]} 60min
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Panel: Active Incidents + Summary stats */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Summary Stats */}
          {traffic.length > 0 && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: "10px" }}>Network Summary</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                {[
                  { label: "High Congestion", value: traffic.filter(c => c.status === "High").length, color: "var(--red)" },
                  { label: "Medium Congestion", value: traffic.filter(c => c.status === "Medium").length, color: "var(--amber)" },
                  { label: "Free Flowing", value: traffic.filter(c => c.status === "Low").length, color: "var(--green)" },
                  { label: "Active Incidents", value: traffic.reduce((s, c) => s + (c.incident_count || 0), 0), color: "var(--blue)" },
                ].map((stat, i) => (
                  <div key={i} style={{ background: "var(--bg)", borderRadius: "8px", padding: "10px", border: "1px solid var(--border)" }}>
                    <div style={{ fontSize: "20px", fontWeight: "800", color: stat.color }}>{stat.value}</div>
                    <div style={{ fontSize: "10px", color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: "700" }}>{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Active Incidents */}
          <div className="card" style={{ flex: 1 }}>
            <div className="card-title" style={{ marginBottom: "12px" }}>Active Incidents</div>
            {events.length === 0 ? (
              <div style={{ color: "var(--text-secondary)", fontSize: "12px", textAlign: "center", padding: "20px" }}>
                No active incidents detected.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "380px", overflowY: "auto" }}>
                {events.slice(0, 12).map((ev, i) => (
                  <div
                    key={ev.id || i}
                    style={{
                      background: "var(--bg)",
                      border: `1px solid ${ev.priority === "High" ? "var(--red)" : "var(--border)"}`,
                      borderRadius: "8px",
                      padding: "8px 12px",
                      cursor: "pointer",
                    }}
                    onClick={() => onRunAI(ev.id)}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-primary)" }}>
                        {ev.event_cause?.replace(/_/g, " ")}
                      </span>
                      <span style={{
                        fontSize: "9px",
                        fontWeight: "700",
                        color: ev.priority === "High" ? "var(--red)" : "var(--amber)",
                        textTransform: "uppercase",
                      }}>
                        {ev.priority}
                      </span>
                    </div>
                    <div style={{ fontSize: "10px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                      {ev.corridor || "Non-corridor"} · {ev.address?.slice(0, 45) || "Bengaluru"}
                    </div>
                    <div style={{ fontSize: "10px", color: "var(--blue)", marginTop: "3px" }}>
                      ▶ Run AI Analysis
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

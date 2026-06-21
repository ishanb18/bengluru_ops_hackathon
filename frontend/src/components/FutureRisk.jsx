import React, { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";

const RISK_COLOR = {
  Low: "var(--green)",
  Medium: "var(--amber)",
  High: "var(--red)",
  null: "var(--text-tertiary)",
  undefined: "var(--text-tertiary)",
};

const RISK_BAR_PCT = { Low: 25, Medium: 60, High: 90 };

export default function FutureRisk() {
  const [forecast, setForecast] = useState([]);
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  useEffect(() => {
    async function fetchForecast() {
      setLoading(true);
      try {
        const [forecastRes, weatherRes] = await Promise.all([
          fetch(`${API}/api/traffic/forecast`),
          fetch(`${API}/api/traffic/weather`),
        ]);
        if (forecastRes.ok) {
          const d = await forecastRes.json();
          setForecast(d.corridors || []);
          setLastUpdate(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
        }
        if (weatherRes.ok) {
          setWeather(await weatherRes.json());
        }
      } catch (e) {
        console.error("Forecast fetch failed:", e);
      } finally {
        setLoading(false);
      }
    }
    fetchForecast();
    const interval = setInterval(fetchForecast, 120000);
    return () => clearInterval(interval);
  }, []);

  const RiskCell = ({ risk }) => {
    const color = RISK_COLOR[risk] || "var(--text-tertiary)";
    const pct = RISK_BAR_PCT[risk] || 0;
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "4px" }}>
        <div style={{
          padding: "3px 10px",
          borderRadius: "20px",
          border: `1px solid ${color}`,
          color,
          fontSize: "10px",
          fontWeight: "800",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          minWidth: "64px",
          textAlign: "center",
          background: `${color}11`,
        }}>
          {risk || "—"}
        </div>
        <div style={{ width: "60px", height: "3px", background: "var(--bg)", borderRadius: "99px", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: "99px" }} />
        </div>
      </div>
    );
  };

  const [refreshing, setRefreshing] = useState(false);

  const handleRefreshForecast = async () => {
    setRefreshing(true);
    try {
      // 1. Trigger a TomTom incident scan
      await fetch(`${API}/api/scan`, { method: "POST" });
      // 2. Wait a moment for data to settle, then re-fetch forecast
      await new Promise(r => setTimeout(r, 500));
      const [forecastRes, weatherRes] = await Promise.all([
        fetch(`${API}/api/traffic/forecast`),
        fetch(`${API}/api/traffic/weather`),
      ]);
      if (forecastRes.ok) {
        const d = await forecastRes.json();
        setForecast(d.corridors || []);
        setLastUpdate(new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }));
      }
      if (weatherRes.ok) {
        setWeather(await weatherRes.json());
      }
    } catch (e) {
      console.error("Refresh forecast failed:", e);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="screen active">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <div className="page-title">Future Risk View</div>
          <div className="page-sub">
            Predicted congestion at 30-min and 60-min horizons for all corridors
            {lastUpdate && <span style={{ marginLeft: 8, color: "var(--text-tertiary)" }}>· {lastUpdate}</span>}
          </div>
        </div>
        {weather && (
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", justifyContent: "flex-end" }}>
            {[
              { icon: weather.condition === "Rain" ? "🌧" : "🌤", label: "Condition", val: weather.condition },
              { icon: "🌡", label: "Temp", val: weather.temperature_c != null ? `${Math.round(weather.temperature_c)}°C` : "—" },
              { icon: "💧", label: "Rain 1hr", val: `${weather.rainfall_mm ?? 0}mm` },
              { icon: "👁", label: "Visibility", val: weather.visibility_m != null ? `${(weather.visibility_m / 1000).toFixed(1)}km` : "—" },
            ].map((w, i) => (
              <div key={i} className="card" style={{ padding: "8px 14px", textAlign: "center" }}>
                <div style={{ fontSize: "16px" }}>{w.icon}</div>
                <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)" }}>{w.val}</div>
                <div style={{ fontSize: "9px", color: "var(--text-tertiary)", textTransform: "uppercase" }}>{w.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title" style={{ marginBottom: "16px" }}>Corridor Risk Forecast</div>

        {/* Table header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
          gap: "8px",
          padding: "6px 12px",
          borderRadius: "6px",
          background: "var(--bg)",
          marginBottom: "8px",
          fontSize: "10px",
          fontWeight: "700",
          color: "var(--text-tertiary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}>
          <span>Corridor</span>
          <span style={{ textAlign: "center" }}>Now</span>
          <span style={{ textAlign: "center" }}>+30 min</span>
          <span style={{ textAlign: "center" }}>+60 min</span>
          <span style={{ textAlign: "center" }}>Incidents</span>
        </div>

        {loading ? (
          <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "30px", fontSize: "13px" }}>
            Loading forecast data...
          </div>
        ) : forecast.length === 0 ? (
          <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "30px", fontSize: "13px" }}>
            Forecast unavailable — click "Refresh Forecast" below to populate live data.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {forecast.map((c, i) => (
              <div
                key={i}
                style={{
                  display: "grid",
                  gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
                  gap: "8px",
                  alignItems: "center",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  background: i % 2 === 0 ? "var(--bg)" : "transparent",
                  border: "1px solid transparent",
                  transition: "border-color 0.15s",
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "var(--border)"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "transparent"}
              >
                <span style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)" }}>
                  {c.corridor}
                </span>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <RiskCell risk={c.now_status} />
                </div>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <RiskCell risk={c.risk_30min} />
                </div>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <RiskCell risk={c.risk_60min} />
                </div>
                <div style={{ textAlign: "center" }}>
                  {c.incident_count > 0 ? (
                    <span className="badge badge-red" style={{ fontSize: "10px" }}>
                      ⚠ {c.incident_count}
                    </span>
                  ) : (
                    <span style={{ fontSize: "11px", color: "var(--green)" }}>✓ Clear</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Risk Legend + Refresh Button */}
      <div className="card" style={{ marginTop: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
          <div className="card-title" style={{ marginBottom: 0 }}>Risk Classification</div>
          <button
            className="btn btn-scan"
            onClick={handleRefreshForecast}
            disabled={refreshing}
            style={{ padding: "7px 14px", fontSize: "12px" }}
          >
            {refreshing ? "⏳ Refreshing..." : "🔄 Refresh Forecast"}
          </button>
        </div>
        <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", fontSize: "12px" }}>
          {[
            { label: "Low", desc: "< 35% congestion. Free flowing traffic.", color: "var(--green)" },
            { label: "Medium", desc: "35–65% congestion. Moderate delays.", color: "var(--amber)" },
            { label: "High", desc: "> 65% congestion. Significant impact.", color: "var(--red)" },
          ].map(({ label, desc, color }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: color }} />
              <span style={{ fontWeight: "700", color }}>{label}</span>
              <span style={{ color: "var(--text-tertiary)" }}>{desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from "react";

export default function Analytics() {
  const [corridors, setCorridors] = useState([]);
  const [monthlyTrend, setMonthlyTrend] = useState([]);
  const [junctions, setJunctions] = useState([]);
  const [peakHours, setPeakHours] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAnalytics() {
      try {
        const [corridorsRes, trendRes, junctionsRes, peakRes] = await Promise.all([
          fetch("http://localhost:8000/api/analytics/corridor-risk"),
          fetch("http://localhost:8000/api/analytics/monthly-trend"),
          fetch("http://localhost:8000/api/analytics/top-junctions"),
          fetch("http://localhost:8000/api/analytics/peak-hours")
        ]);

        if (corridorsRes.ok) setCorridors(await corridorsRes.json());
        if (trendRes.ok) setMonthlyTrend(await trendRes.json());
        if (junctionsRes.ok) setJunctions(await junctionsRes.json());
        if (peakRes.ok) setPeakHours(await peakRes.json());
      } catch (err) {
        console.error("Error loading analytics data:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div className="screen active" style={{ textAlign: "center", padding: "40px" }}>
        <div style={{ color: "var(--text-secondary)", fontSize: "13px" }}>Querying post-event database analytics...</div>
      </div>
    );
  }

  // Find max count to scale monthly trends chart
  const maxTrendCount = monthlyTrend.length > 0 ? Math.max(...monthlyTrend.map(t => t.incident_count)) : 1;

  return (
    <div className="screen active">
      <div className="page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div className="page-title">Post-Event Learning & Analytics</div>
          <div className="page-sub">Historical database findings on 8,173 traffic events for predictive insights</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "20px", alignItems: "start", marginBottom: "20px" }}>
        
        <div className="card">
          <div className="card-title">Corridor Risk Index (Top 6)</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "8px" }}>
            {corridors.slice(0, 6).map((c, index) => {
              const score = Math.round(c.risk_score);
              const color = score > 70 ? "var(--red)" : score > 40 ? "var(--amber)" : "var(--green)";
              return (
                <div key={index} className="risk-bar-row">
                  <span className="risk-name">{c.corridor}</span>
                  <div className="risk-bar-bg">
                    <div
                      className="risk-bar-fill"
                      style={{ width: `${score}%`, backgroundColor: color }}
                    ></div>
                  </div>
                  <span className="risk-score">{score}%</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-title">Live Hourly Congestion Trend</div>
          <div className="chart-bar" style={{ height: "180px", alignItems: "flex-end" }}>
            {monthlyTrend.map((t, idx) => {
              const pct = (t.incident_count / maxTrendCount) * 100;
              return (
                <div className="bar-col" key={idx} style={{ height: "100%", justifyContent: "flex-end" }}>
                  <div style={{ fontSize: "10px", color: "var(--text-secondary)", marginBottom: "2px", fontWeight: "600" }}>{t.incident_count}</div>
                  <div
                    className="bar-rect"
                    style={{
                      height: `${pct * 0.7}%`,
                      backgroundColor: "var(--primary)",
                      boxShadow: "0 2px 8px rgba(79, 70, 229, 0.15)",
                      width: "32px"
                    }}
                  ></div>
                  <span className="bar-lbl" style={{ marginTop: "4px" }}>{t.month}</span>
                </div>
              );
            })}
          </div>
        </div>

      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "20px", alignItems: "start" }}>
        
        <div className="card">
          <div className="card-title">Top Worst Junctions</div>
          <div style={{ maxHeight: "280px", overflowY: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Junction Name</th>
                  <th style={{ textAlign: "right" }}>Incidents</th>
                </tr>
              </thead>
              <tbody>
                {junctions.slice(0, 5).map((j, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: "700", color: "var(--text-primary)" }}>{j.junction}</td>
                    <td style={{ textAlign: "right" }}>
                      <span className="badge badge-amber" style={{ fontSize: "11px", fontFamily: "JetBrains Mono, monospace" }}>
                        {j.incident_count} events
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Peak Congestion Hours by Zone</div>
          <div style={{ maxHeight: "280px", overflowY: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Zone</th>
                  <th>Peak Hour</th>
                  <th style={{ textAlign: "right" }}>Incidents Count</th>
                </tr>
              </thead>
              <tbody>
                {peakHours.slice(0, 5).map((ph, idx) => {
                  const hourFormatted = ph.peak_hour_label || (
                    typeof ph.peak_hour === "number"
                      ? `${String(ph.peak_hour).padStart(2, "0")}:00 – ${String((ph.peak_hour + 1) % 24).padStart(2, "0")}:00`
                      : String(ph.peak_hour)
                  );
                  return (
                    <tr key={idx}>
                      <td style={{ fontWeight: "700", color: "var(--text-primary)" }}>{ph.zone}</td>
                      <td style={{ color: "var(--amber)", fontFamily: "JetBrains Mono, monospace", fontWeight: "600" }}>{hourFormatted}</td>
                      <td style={{ textAlign: "right", color: "var(--text-secondary)", fontWeight: "600" }}>{ph.incident_count}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}

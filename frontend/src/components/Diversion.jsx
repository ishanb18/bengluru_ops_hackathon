import React, { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "";

// Top corridors to dynamically pre-fetch summary diversions for the summary panel
const TOP_CORRIDORS_FOR_PANEL = [
  "Mysore Road", "Bellary Road 1", "ORR East 1", "Hosur Road", "Old Madras Road"
];

const EVENT_CAUSES = [
  { value: "vehicle_breakdown", label: "Vehicle Breakdown" },
  { value: "accident", label: "Accident" },
  { value: "construction", label: "Construction" },
  { value: "water_logging", label: "Water Logging (Flooding)" },
  { value: "vip_movement", label: "VIP Movement" },
  { value: "public_event", label: "Public Event" },
  { value: "tree_fall", label: "Tree Fall" },
  { value: "pot_holes", label: "Pot Holes" },
  { value: "others", label: "Other / Debris" },
];

const VEH_TYPES = [
  { value: "heavy_vehicle", label: "Heavy Vehicle (HGV)" },
  { value: "lcv", label: "LCV" },
  { value: "private_car", label: "Car" },
  { value: "two_wheeler", label: "Two-Wheeler" },
  { value: "N/A", label: "N/A" },
];

export default function Diversion({ availableCorridors }) {
  const [selectedCorridor, setSelectedCorridor] = useState("");
  const [eventCause, setEventCause] = useState("vehicle_breakdown");
  const [vehType, setVehType] = useState("N/A");
  const [hour, setHour] = useState(9);
  const [diversions, setDiversions] = useState([]);
  const [routesStress, setRoutesStress] = useState([]);
  const [loading, setLoading] = useState(false);
  const [corridorSummary, setCorridorSummary] = useState({});
  const [summaryLoading, setSummaryLoading] = useState(false);

  // Auto-select first non-null corridor once corridors load
  useEffect(() => {
    if (!selectedCorridor && availableCorridors && availableCorridors.length > 0) {
      const first = availableCorridors.filter(c => c !== "Non-corridor")[0];
      if (first) setSelectedCorridor(first);
    }
  }, [availableCorridors]);

  // Fetch alternate routes for the selected corridor
  useEffect(() => {
    if (!selectedCorridor) return;
    async function fetchDiversions() {
      setLoading(true);
      try {
        const queryParams = new URLSearchParams({
          event_cause: eventCause,
          veh_type: vehType,
          hour: hour.toString()
        });
        const res = await fetch(
          `${API}/api/diversion/${encodeURIComponent(selectedCorridor)}?${queryParams.toString()}`
        );
        if (res.ok) {
          const data = await res.json();
          setDiversions(data.alternates || []);
        } else {
          setDiversions([]);
        }
      } catch (err) {
        console.error("Error fetching diversion routes:", err);
        setDiversions([]);
      } finally {
        setLoading(false);
      }
    }
    fetchDiversions();
  }, [selectedCorridor, eventCause, vehType, hour]);

  // Fetch corridor risk stress scores for the bar chart panel
  useEffect(() => {
    async function fetchStress() {
      try {
        const res = await fetch(`${API}/api/analytics/corridor-risk`);
        if (res.ok) {
          const data = await res.json();
          setRoutesStress(data || []);
        }
      } catch (err) {
        console.error("Error fetching routes stress:", err);
      }
    }
    fetchStress();
  }, []);

  // Dynamically fetch live first-alternate for summary panel corridors
  useEffect(() => {
    async function fetchSummary() {
      setSummaryLoading(true);
      const results = {};
      await Promise.all(
        TOP_CORRIDORS_FOR_PANEL.map(async (corridor) => {
          try {
            const res = await fetch(
              `${API}/api/diversion/${encodeURIComponent(corridor)}`
            );
            if (res.ok) {
              const data = await res.json();
              const firstAlt = data.alternates?.[0];
              results[corridor] = firstAlt ? firstAlt.name : "No alternate found";
            } else {
              results[corridor] = "Unavailable";
            }
          } catch {
            results[corridor] = "API Error";
          }
        })
      );
      setCorridorSummary(results);
      setSummaryLoading(false);
    }
    fetchSummary();
  }, []);

  const getStressPillClass = (stressStr) => {
    const s = (stressStr || "").toLowerCase();
    if (s.includes("low")) return "stress-low";
    if (s.includes("medium") || s.includes("mod")) return "stress-med";
    return "stress-high";
  };

  return (
    <div className="screen active">
      <div className="page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div className="page-title">Diversion Suggestion Engine</div>
          <div className="page-sub">Blocked corridor → alternate routes dynamically adjusted by incident characteristics</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "20px", alignItems: "start" }}>
        
        <div>
          <div className="card">
            <div className="card-title">Simulator Parameters</div>
            
            <div className="grid2" style={{ marginBottom: "12px" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Blocked Corridor</label>
                <select
                  className="form-select"
                  value={selectedCorridor}
                  onChange={(e) => setSelectedCorridor(e.target.value)}
                >
                  {availableCorridors && availableCorridors.length > 0 ? (
                    availableCorridors.filter(c => c !== "Non-corridor").map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))
                  ) : (
                    <option value="">Loading corridors...</option>
                  )}
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Incident Cause</label>
                <select
                  className="form-select"
                  value={eventCause}
                  onChange={(e) => setEventCause(e.target.value)}
                >
                  {EVENT_CAUSES.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid2" style={{ marginBottom: "16px" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Vehicle Type Involved</label>
                <select
                  className="form-select"
                  value={vehType}
                  onChange={(e) => setVehType(e.target.value)}
                >
                  {VEH_TYPES.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Time of Day</label>
                <select
                  className="form-select"
                  value={hour}
                  onChange={(e) => setHour(parseInt(e.target.value))}
                >
                  <option value={6}>Early Morning (05:00 – 07:00)</option>
                  <option value={9}>Morning Rush (08:00 – 10:00)</option>
                  <option value={13}>Midday (12:00 – 14:00)</option>
                  <option value={18}>Evening Rush (17:00 – 20:00)</option>
                  <option value={2}>Late Night (23:00 – 05:00)</option>
                </select>
              </div>
            </div>
            
            <div className="divider" style={{ margin: "16px 0" }}></div>

            <div className="card-title" style={{ marginBottom: "12px" }}>
              Alternative Options for: {selectedCorridor || "—"}
            </div>

            {loading ? (
              <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "20px", fontSize: "13px" }}>
                Analyzing alternate route capacities...
              </div>
            ) : diversions.length === 0 ? (
              <div style={{ color: "var(--text-secondary)", textAlign: "center", padding: "20px", fontSize: "13px" }}>
                No active diversions configured for this corridor.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {diversions.map((div, index) => {
                  const stressClass = getStressPillClass(div.stress_level);
                  
                  return (
                    <div className="divert-card primary" key={index}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                        <span style={{ fontWeight: "700", fontSize: "14px", color: "var(--text-primary)" }}>
                          ✓ {div.name}
                        </span>
                        <span className={`stress-pill ${stressClass}`}>
                          Stress Level: {div.stress_level} ({Math.round(div.stress_score)}%)
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "6px" }}>
                        <span style={{ fontSize: "11px", color: "var(--amber)", fontWeight: "700" }}>
                          ⏱ Est. Delay: +{div.extra_minutes} mins
                        </span>
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                        {div.notes}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          
          <div className="card">
            <div className="card-title">Live Corridor Diversion Summary</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "12px" }}>
              {summaryLoading ? (
                <div style={{ color: "var(--text-secondary)", fontSize: "12px", padding: "8px 0" }}>
                  Loading live diversion data...
                </div>
              ) : (
                TOP_CORRIDORS_FOR_PANEL.map((corridor, i) => (
                  <div
                    key={corridor}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      borderBottom: i < TOP_CORRIDORS_FOR_PANEL.length - 1 ? "1px solid var(--border)" : "none",
                      paddingBottom: "6px"
                    }}
                  >
                    <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                      {corridor} blocked
                    </span>
                    <span className="mono" style={{ color: "var(--text-secondary)", maxWidth: "120px", textAlign: "right" }}>
                      → {corridorSummary[corridor] || "Fetching..."}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-title">Alternate Route Stress Scores</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {routesStress.slice(0, 5).map((route, index) => {
                const color = route.risk_score > 70 ? "var(--red)" : route.risk_score > 40 ? "var(--amber)" : "var(--green)";
                return (
                  <div key={index}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
                      <span style={{ color: "var(--text-secondary)", fontWeight: "600" }}>{route.corridor}</span>
                      <span className="mono" style={{ color: "var(--text-primary)", fontWeight: "700" }}>
                        {route.risk_score}%
                      </span>
                    </div>
                    <div style={{ height: "6px", background: "var(--bg)", borderRadius: "99px", border: "1px solid var(--border)", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${route.risk_score}%`, backgroundColor: color, borderRadius: "99px" }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}

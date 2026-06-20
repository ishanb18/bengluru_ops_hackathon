import React, { useState, useEffect } from "react";

export default function Diversion({ availableCorridors }) {
  const [selectedCorridor, setSelectedCorridor] = useState("Bellary Road 1");
  const [eventCause, setEventCause] = useState("vehicle_breakdown");
  const [vehType, setVehType] = useState("N/A");
  const [hour, setHour] = useState(9);
  const [diversions, setDiversions] = useState([]);
  const [routesStress, setRoutesStress] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch alternate routes for the selected corridor incorporating query parameters
  useEffect(() => {
    async function fetchDiversions() {
      setLoading(true);
      try {
        const queryParams = new URLSearchParams({
          event_cause: eventCause,
          veh_type: vehType,
          hour: hour.toString()
        });
        const res = await fetch(`http://localhost:8000/api/diversion/${encodeURIComponent(selectedCorridor)}?${queryParams.toString()}`);
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

  // Fetch all routes stress scores for the stress display from the correct endpoint
  useEffect(() => {
    async function fetchStress() {
      try {
        const res = await fetch("http://localhost:8000/api/analytics/corridor-risk");
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

  const getStressPillClass = (stressStr) => {
    const s = stressStr.toLowerCase();
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
                    <option value="Loading...">Loading...</option>
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
                  <option value="vehicle_breakdown">Vehicle breakdown</option>
                  <option value="accident">Accident</option>
                  <option value="construction">Construction</option>
                  <option value="water_logging">Water logging (flooding)</option>
                  <option value="vip_movement">VIP movement</option>
                  <option value="public_event">Public event</option>
                  <option value="tree_fall">Tree fall</option>
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
                  <option value="heavy_vehicle">Heavy vehicle (HGV)</option>
                  <option value="lcv">LCV</option>
                  <option value="private_car">Car</option>
                  <option value="two_wheeler">Two-wheeler</option>
                  <option value="N/A">N/A</option>
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Time of Day</label>
                <select
                  className="form-select"
                  value={hour}
                  onChange={(e) => setHour(parseInt(e.target.value))}
                >
                  <option value={9}>Morning Rush (08:00 – 10:00)</option>
                  <option value={13}>Midday (12:00 – 14:00)</option>
                  <option value={18}>Evening Rush (17:00 – 20:00)</option>
                  <option value={2}>Late Night (23:00 – 05:00)</option>
                </select>
              </div>
            </div>
            
            <div className="divider" style={{ margin: "16px 0" }}></div>

            <div className="card-title" style={{ marginBottom: "12px" }}>Alternative Options for: {selectedCorridor}</div>

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
            <div className="card-title">All Corridor Diversions</div>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "6px" }}>
                <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>Mysore Road blocked</span>
                <span className="mono" style={{ color: "var(--text-secondary)" }}>→ Magadi Rd · NICE</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "6px" }}>
                <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>Bellary Road 1 blocked</span>
                <span className="mono" style={{ color: "var(--text-secondary)" }}>→ Bellary Rd 2 · Hebbal</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "6px" }}>
                <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>ORR East 1 blocked</span>
                <span className="mono" style={{ color: "var(--text-secondary)" }}>→ ORR East 2</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid var(--border)", paddingBottom: "6px" }}>
                <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>Hosur Road blocked</span>
                <span className="mono" style={{ color: "var(--text-secondary)" }}>→ Bannerghatta Road</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "6px" }}>
                <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>Old Madras Rd blocked</span>
                <span className="mono" style={{ color: "var(--text-secondary)" }}>→ KR Pura alternate</span>
              </div>
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

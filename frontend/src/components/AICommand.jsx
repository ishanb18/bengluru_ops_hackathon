import React from "react";

export default function AICommand({
  inputs,
  onChange,
  onClassify,
  classResult,
  durResult,
  manResult,
  loading,
  availableCorridors
}) {
  const causeText = inputs.event_cause ? inputs.event_cause.replace(/_/g, " ").toUpperCase() : "INCIDENT";

  // Timeline schedule helper
  const getTimelineItems = (minutes) => {
    const totalMin = minutes || 45;
    const now = new Date();
    
    const offsets = [0, 0.15, 0.5, 1.0]; 
    const labels = [
      "Incident Reported & Geotagged",
      "Field Unit Dispatched",
      "Resolution Active & Diverting Traffic",
      "Roadway Cleared & Flow Restored"
    ];
    
    const descriptions = [
      "Logged automatically into BengaluruOps AI Command.",
      "Closest patrol vehicle routed with turn-by-turn navigation.",
      "Cones set up. Redirections enabled at nearby junctions.",
      "Final clearance. Traffic begins dispersing on corridor."
    ];

    return labels.map((label, i) => {
      const msOffset = Math.round(offsets[i] * totalMin * 60 * 1000);
      const timeAtStep = new Date(now.getTime() + msOffset);
      const timeStr = timeAtStep.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      
      let statusClass = "pending";
      if (i === 0) statusClass = "done";
      else if (i === 1) statusClass = "active";
      
      return {
        label,
        description: descriptions[i],
        time: timeStr,
        status: statusClass
      };
    });
  };

  const timelineItems = getTimelineItems(durResult ? durResult.estimated_minutes : null);
  const durBucket = durResult ? durResult.bucket : "Medium";
  const durMinutes = durResult ? Math.round(durResult.estimated_minutes) : 60;

  // Manpower defaults
  const officers = manResult ? manResult.officer_count : 4;
  const barricades = manResult ? manResult.barricade_count : 8;
  const towTruck = manResult ? manResult.tow_truck_needed : false;
  const bbmp = manResult ? manResult.bbmp_escalation : false;
  const notes = manResult && manResult.notes?.length
    ? manResult.notes.join(" · ")
    : "Deploy standard traffic control units to prevent bottleneck build up.";
  const stations = manResult && manResult.nearest_stations ? manResult.nearest_stations : [
    { name: "Ulsoor Traffic PS", distance_label: "~1.4 km", estimated_response_min: 8 },
    { name: "Shivajinagar PS", distance_label: "~2.3 km", estimated_response_min: 12 },
    { name: "Cubbon Park PS", distance_label: "~3.5 km", estimated_response_min: 16 }
  ];

  return (
    <div className="screen active">
      <div className="page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div className="page-title">AI Command Predictor</div>
          <div className="page-sub">Enter attributes below to simulate real-time ML prediction pipelines</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "20px", alignItems: "start" }}>
        
        {/* Left Column: Form Inputs */}
        <div className="card">
          <div className="card-title">Simulator Inputs</div>
          
          <div className="form-group">
            <label className="form-label">Event cause</label>
            <select
              className="form-select"
              value={inputs.event_cause}
              onChange={(e) => onChange("event_cause", e.target.value)}
            >
              <option value="vehicle_breakdown">Vehicle breakdown</option>
              <option value="accident">Accident</option>
              <option value="construction">Construction</option>
              <option value="water_logging">Water logging</option>
              <option value="vip_movement">VIP movement</option>
              <option value="public_event">Public event</option>
              <option value="pot_holes">Pot holes</option>
              <option value="tree_fall">Tree fall</option>
              <option value="Stationary Traffic">Stationary Traffic</option>
              <option value="Jam">Jam</option>
              <option value="Queueing Traffic">Queueing Traffic</option>
              <option value="abandoned_vehicle">Abandoned Vehicle</option>
              <option value="oil_spill">Oil Spill</option>
              <option value="pedestrian_incident">Pedestrian Incident</option>
              <option value="others">Other / Debris</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Corridor</label>
            <select
              className="form-select"
              value={inputs.corridor}
              onChange={(e) => onChange("corridor", e.target.value)}
            >
              {availableCorridors && availableCorridors.length > 0 ? (
                availableCorridors.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))
              ) : (
                <option value="Non-corridor">Loading...</option>
              )}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Vehicle type involved</label>
            <select
              className="form-select"
              value={inputs.veh_type}
              onChange={(e) => onChange("veh_type", e.target.value)}
            >
              <option value="heavy_vehicle">Heavy vehicle (HGV)</option>
              <option value="lcv">LCV</option>
              <option value="private_car">Car</option>
              <option value="bus">Bus (BMTC/KSRTC)</option>
              <option value="two_wheeler">Two-wheeler</option>
              <option value="N/A">N/A</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Time of report</label>
            <select
              className="form-select"
              value={inputs.hour}
              onChange={(e) => onChange("hour", parseInt(e.target.value))}
            >
              <option value={6}>05:00 – 07:00 (Early morning peak)</option>
              <option value={9}>08:00 – 10:00 (Morning rush)</option>
              <option value={13}>12:00 – 14:00 (Afternoon)</option>
              <option value={18}>17:00 – 20:00 (Evening rush)</option>
              <option value={22}>21:00 – 23:00 (Night peak)</option>
            </select>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            <div className="form-group">
              <label className="form-label">Day of Week</label>
              <select
                className="form-select"
                value={inputs.weekday}
                onChange={(e) => onChange("weekday", parseInt(e.target.value))}
              >
                <option value={0}>Mon</option>
                <option value={1}>Tue</option>
                <option value={2}>Wed</option>
                <option value={3}>Thu</option>
                <option value={4}>Fri</option>
                <option value={5}>Sat</option>
                <option value={6}>Sun</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Event Type</label>
              <select
                className="form-select"
                value={inputs.event_type}
                onChange={(e) => onChange("event_type", e.target.value)}
              >
                <option value="unplanned">Unplanned</option>
                <option value="planned">Planned (Festival/Rally)</option>
              </select>
            </div>
          </div>

          <button
            className="btn btn-primary"
            style={{ width: "100%", padding: "10px", justifyContent: "center", fontWeight: "600", marginTop: "4px" }}
            onClick={onClassify}
            disabled={loading}
          >
            {loading ? "Running AI Models..." : "🔮 Run AI Recommendation"}
          </button>
        </div>

        {/* Right Column: Prediction Verdicts & Recs */}
        <div className="ai-results-grid">
          
          {/* Section 1: Classification & SHAP */}
          <div className="card">
            <div className="card-title">Prediction Verdict & Confidence</div>
            
            {!classResult ? (
              <div style={{ color: "var(--text-secondary)", fontStyle: "italic", textAlign: "center", padding: "10px 0", fontSize: "13px" }}>
                Click "Run AI Recommendation" to execute the inference pipeline
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "16px", alignItems: "start" }}>
                <div>
                  <div className="result-box">
                    <div className={`result-main ${classResult.priority === "High" ? "high" : "low"}`}>
                      {classResult.priority.toUpperCase()} PRIORITY
                    </div>
                    <div style={{ display: "flex", gap: "6px", marginTop: "8px", marginBottom: "12px", flexWrap: "wrap" }}>
                      <span className={classResult.requires_closure ? "badge badge-red" : "badge badge-green"}>
                        Road closure: {classResult.requires_closure ? "YES" : "NO"}
                      </span>
                      <span className="badge badge-blue">
                        Confidence: {Math.round(classResult.confidence * 100)}%
                      </span>
                    </div>

                    <div className="form-label">Confidence score</div>
                    <div className="confidence-bar">
                      <div className="confidence-fill" style={{ width: `${classResult.confidence * 100}%` }}></div>
                    </div>
                  </div>

                  {classResult.recommended_action && (
                    <div style={{ marginTop: "12px", background: "var(--amber-dim)", borderLeft: "4px solid var(--amber)", padding: "10px 12px", borderRadius: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--amber)", textTransform: "uppercase", display: "block", marginBottom: "2px" }}>
                        ⚠️ Auto-recommended action
                      </span>
                      <span style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-primary)" }}>
                        {classResult.recommended_action}
                      </span>
                    </div>
                  )}

                  {classResult.llm_verification && (
                    <div style={{ marginTop: "12px", background: classResult.llm_verification.verified ? "var(--green-dim)" : "var(--bg)", borderLeft: `4px solid ${classResult.llm_verification.verified ? "var(--green)" : "var(--border)"}`, padding: "10px 12px", borderRadius: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: "700", color: classResult.llm_verification.verified ? "var(--green)" : "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "2px", display: "flex", justifyContent: "space-between" }}>
                        <span>🌐 Web Search LLM Verification</span>
                        <span>{classResult.llm_verification.score}% Conf</span>
                      </span>
                      <span style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-primary)" }}>
                        {classResult.llm_verification.summary}
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <div style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", marginBottom: "8px" }}>
                    SHAP Feature Explanation
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    {classResult.shap_explanation && classResult.shap_explanation.length > 0 ? (() => {
                      // Normalize bar widths relative to max SHAP magnitude in this result
                      const maxAbsVal = Math.max(...classResult.shap_explanation.map(s => Math.abs(s.value)), 0.001);

                      // Convert OHE feature names to human-readable labels
                      const formatShapLabel = (raw) => {
                        if (!raw || raw === "shap_unavailable") return "Unavailable";
                        const prefixMap = {
                          "corridor_": "📍 ",
                          "event_cause_": "⚡ ",
                          "veh_type_": "🚗 ",
                          "weekday_name_": "📅 ",
                          "event_type_": "📋 ",
                        };
                        for (const [prefix, icon] of Object.entries(prefixMap)) {
                          if (raw.startsWith(prefix)) {
                            const suffix = raw.slice(prefix.length).replace(/_/g, " ");
                            // Special labels
                            if (suffix === "Non corridor" || suffix === "Non-corridor") return icon + "No Named Corridor";
                            return icon + suffix;
                          }
                        }
                        const numericMap = {
                          "is_peak_hour": "🕐 Peak Hour",
                          "hour": "🕐 Hour of Day",
                          "weekday": "📅 Day of Week",
                          "month": "📆 Month",
                          "has_cargo_data": "🚛 Cargo Vehicle",
                          "has_junction": "🔀 Junction Involved",
                        };
                        return numericMap[raw] || raw.replace(/_/g, " ");
                      };

                      return classResult.shap_explanation.map((shap, index) => {
                        const isPositive = shap.value >= 0;
                        const absVal = Math.abs(shap.value);
                        // Proportional bar — max 90px wide
                        const barWidth = Math.round((absVal / maxAbsVal) * 90);

                        return (
                          <div className="shap-row" key={index} style={{ padding: "4px 0" }}>
                            <span className="shap-label" style={{ fontSize: "11px" }}>{formatShapLabel(shap.feature)}</span>
                            <div style={{ flex: 1, display: "flex", justifyContent: isPositive ? "flex-start" : "flex-end", margin: "0 8px" }}>
                              <div
                                className={isPositive ? "shap-bar-pos" : "shap-bar-neg"}
                                style={{ width: `${barWidth}px`, minWidth: "4px" }}
                              ></div>
                            </div>
                            <span className="shap-val" style={{ fontSize: "11px", color: isPositive ? "var(--red)" : "var(--green)" }}>
                              {isPositive ? "+" : ""}{shap.value.toFixed(3)}
                            </span>
                          </div>
                        );
                      });
                    })() : (
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px" }}>
                        <span className="shap-label">SHAP Unavailable</span>
                        <span className="shap-val" style={{ color: "var(--red)" }}>+0.000</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: Duration Timeline & Resources */}
          {classResult && (
            <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.3fr", gap: "16px", alignItems: "start" }}>
              
              {/* Clearance Duration & Milestones */}
              <div className="card">
                <div className="card-title">Duration & Schedule</div>
                
                <div className={`dur-card ${durBucket.toLowerCase()}`} style={{ padding: "12px 14px", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "8px", position: "relative", overflow: "hidden", marginBottom: "14px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "10px", fontWeight: "600", color: "var(--text-secondary)" }}>{causeText} BUCKET</span>
                    <span style={{ fontSize: "11px", fontWeight: "700", color: durBucket === "Slow" ? "var(--red)" : durBucket === "Medium" ? "var(--amber)" : "var(--green)" }}>
                      {durBucket.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ fontSize: "28px", fontWeight: "800", color: "var(--text-primary)", margin: "4px 0" }}>
                    {durMinutes} <span style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-secondary)" }}>mins</span>
                  </div>
                </div>

                <div className="timeline">
                  {timelineItems.map((item, i) => (
                    <div className={`tl-item ${item.status}`} key={i} style={{ paddingBottom: "12px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                        <div className="tl-label" style={{ fontSize: "12px" }}>{item.label}</div>
                        <span className="mono" style={{ fontSize: "10px", fontWeight: "600", color: item.status === "done" ? "var(--green)" : item.status === "active" ? "var(--amber)" : "var(--text-tertiary)" }}>
                          {item.time}
                        </span>
                      </div>
                      <div className="tl-sub" style={{ fontSize: "11px", marginTop: "1px" }}>{item.description}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Resource recommendations & Police stations */}
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                
                <div className="card">
                  <div className="card-title">Manpower & Dispatch</div>
                  
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div className="deploy-card">
                      <div className="deploy-icon" style={{ background: "var(--blue-dim)", color: "var(--blue)" }}>👮</div>
                      <div>
                        <div style={{ fontSize: "10px", color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: "700" }}>Officers needed</div>
                        <div style={{ fontSize: "16px", fontWeight: "700" }}>{officers} Officers</div>
                      </div>
                    </div>

                    <div className="deploy-card">
                      <div className="deploy-icon" style={{ background: "var(--amber-dim)", color: "var(--amber)" }}>🚧</div>
                      <div>
                        <div style={{ fontSize: "10px", color: "var(--text-tertiary)", textTransform: "uppercase", fontWeight: "700" }}>Barricading</div>
                        <div style={{ fontSize: "16px", fontWeight: "700" }}>{barricades} Sets</div>
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", margin: "4px 0" }}>
                      <span className={towTruck ? "badge badge-red" : "badge badge-green"}>
                        Tow Truck: {towTruck ? "YES" : "NO"}
                      </span>
                      {bbmp && (
                        <span className="badge badge-red">
                          Municipal Escalation
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontStyle: "italic", borderTop: "1px solid var(--border)", paddingTop: "8px" }}>
                      "{notes}"
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="card-title">Closest Stations & ETAs</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    {stations.map((st, idx) => {
                      const distLabel = st.distance_label || (st.distance ? `~${st.distance} km` : "—");
                      const eta = st.estimated_response_min ?? st.eta_minutes ?? 15;
                      const maxEta = Math.max(...stations.map(s => s.estimated_response_min ?? s.eta_minutes ?? 15));
                      const fillPct = maxEta > 0 ? (eta / maxEta) * 100 : 50;

                      return (
                        <div className="station-row" key={idx} style={{ padding: "6px 0" }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: "600", fontSize: "12px", color: "var(--text-primary)" }}>{st.name}</div>
                            <div style={{ display: "flex", gap: "6px", fontSize: "11px", color: "var(--text-secondary)", marginTop: "1px" }}>
                              <span>{distLabel}</span>
                              <span>·</span>
                              <span style={{ color: "var(--amber)", fontWeight: "600" }}>ETA: {eta}m</span>
                            </div>
                            <div className="dist-bar">
                              <div className="dist-fill" style={{ width: `${fillPct}%` }}></div>
                            </div>
                          </div>
                          <button className="btn btn-ghost" style={{ padding: "3px 6px", fontSize: "10px", border: "1px solid var(--border)", background: "var(--bg)", marginLeft: "8px" }}>Dispatch</button>
                        </div>
                      );
                    })}
                  </div>
                </div>

              </div>

            </div>
          )}

        </div>

      </div>
    </div>
  );
}

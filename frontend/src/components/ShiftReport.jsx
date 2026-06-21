import React, { useState, useEffect, useCallback, useRef } from "react";

const API = import.meta.env.VITE_API_URL || "";

const CAUSE_ICONS = {
  "Vehicle Breakdown": "🚛",
  "Accident": "💥",
  "Construction": "🚧",
  "Water Logging": "🌊",
  "Vip Movement": "🚨",
  "Public Event": "🎭",
  "Pot Holes": "🕳️",
  "Tree Fall": "🌳",
  "Stationary Traffic": "🚗",
  "Jam": "🔴",
  "Queueing Traffic": "🚦",
  "Abandoned Vehicle": "🚘",
  "Oil Spill": "🛢️",
  "Pedestrian Incident": "🚶",
  "Others": "📌",
};

function getCauseIcon(cause) {
  return CAUSE_ICONS[cause] || "📌";
}

function StatusBadge({ status }) {
  if (status === "active")
    return <span className="badge badge-red">● Active</span>;
  if (status === "closed")
    return <span className="badge badge-green">✓ Closed</span>;
  return <span className="badge badge-blue">{status}</span>;
}

function PriorityBadge({ priority }) {
  return priority === "High" ? (
    <span className="badge badge-red">⚠ High</span>
  ) : (
    <span className="badge badge-amber">Low</span>
  );
}

function SummaryCard({ icon, value, label, color }) {
  return (
    <div className="shift-summary-card" style={{ borderTop: `3px solid ${color}` }}>
      <div style={{ fontSize: "22px", marginBottom: "6px" }}>{icon}</div>
      <div className="metric-val" style={{ color, fontSize: "24px" }}>{value}</div>
      <div className="metric-lbl">{label}</div>
    </div>
  );
}

export default function ShiftReport({ addToast }) {
  const [hours, setHours] = useState(8);
  const [zoneFilter, setZoneFilter] = useState("");
  const [corridorFilter, setCorridorFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [zones, setZones] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [exportingPDF, setExportingPDF] = useState(false);
  const printRef = useRef(null);

  // Load filter options
  useEffect(() => {
    async function loadFilters() {
      try {
        const [zonesRes, corridorsRes] = await Promise.all([
          fetch(`${API}/api/analytics/metadata/zones`),
          fetch(`${API}/api/analytics/metadata/corridors`),
        ]);
        if (zonesRes.ok) setZones(await zonesRes.json());
        if (corridorsRes.ok) {
          const cors = await corridorsRes.json();
          setCorridors(cors.filter((c) => c !== "Non-corridor"));
        }
      } catch (err) {
        console.error("Failed to load filter options:", err);
      }
    }
    loadFilters();
  }, []);

  const fetchTimeline = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ hours });
      if (zoneFilter) params.append("zone", zoneFilter);
      if (corridorFilter) params.append("corridor", corridorFilter);

      const res = await fetch(`${API}/api/incidents/timeline?${params}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      } else {
        addToast?.("⚠️", "Failed to load timeline data.");
      }
    } catch (err) {
      addToast?.("⚠️", "Backend connection error.");
    } finally {
      setLoading(false);
    }
  }, [hours, zoneFilter, corridorFilter]);

  // Auto-fetch on mount and when filters change
  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  const handleExportPDF = () => {
    setExportingPDF(true);
    setTimeout(() => {
      const printContent = printRef.current;
      if (!printContent) return;

      const win = window.open("", "_blank", "width=900,height=700");
      const now = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

      win.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>BengaluruOps — Shift Report</title>
          <style>
            body { font-family: Arial, sans-serif; font-size: 12px; color: #1a1a1a; margin: 20px; }
            h1 { font-size: 18px; color: #0066cc; margin-bottom: 4px; }
            .meta { font-size: 11px; color: #666; margin-bottom: 20px; }
            .summary-row { display: flex; gap: 20px; margin-bottom: 20px; }
            .summary-box { border: 1px solid #ddd; border-radius: 6px; padding: 10px 16px; min-width: 120px; }
            .summary-box .val { font-size: 22px; font-weight: 700; }
            .summary-box .lbl { font-size: 10px; color: #666; text-transform: uppercase; }
            table { width: 100%; border-collapse: collapse; margin-top: 12px; }
            th { font-size: 10px; font-weight: 700; color: #666; text-transform: uppercase; padding: 8px; border-bottom: 2px solid #ddd; text-align: left; }
            td { padding: 7px 8px; border-bottom: 1px solid #eee; font-size: 11px; }
            .high { color: #dc2626; font-weight: 700; }
            .low { color: #d97706; }
            .active { color: #dc2626; }
            .closed { color: #16a34a; }
            .badge { font-size: 10px; padding: 2px 7px; border-radius: 12px; background: #f0f0f0; }
            .footer { margin-top: 30px; font-size: 10px; color: #999; border-top: 1px solid #ddd; padding-top: 10px; }
          </style>
        </head>
        <body>
          <h1>🚦 BengaluruOps — Shift Handover Report</h1>
          <div class="meta">
            Generated: ${now} IST &nbsp;|&nbsp;
            Period: Last ${hours} hours &nbsp;|&nbsp;
            Zone: ${zoneFilter || "All"} &nbsp;|&nbsp;
            Corridor: ${corridorFilter || "All"}
          </div>

          <div class="summary-row">
            <div class="summary-box">
              <div class="val">${data?.total_events ?? 0}</div>
              <div class="lbl">Total Events</div>
            </div>
            <div class="summary-box">
              <div class="val" style="color:#dc2626">${data?.high_priority_count ?? 0}</div>
              <div class="lbl">High Priority</div>
            </div>
            <div class="summary-box">
              <div class="val" style="color:#0066cc">${data?.closure_count ?? 0}</div>
              <div class="lbl">Road Closures</div>
            </div>
            <div class="summary-box">
              <div class="val" style="color:#16a34a">${data?.resolved_count ?? 0}</div>
              <div class="lbl">Resolved</div>
            </div>
          </div>

          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Event</th>
                <th>Corridor</th>
                <th>Zone</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              ${(data?.events || [])
                .map(
                  (ev, i) => `
                <tr>
                  <td>${i + 1}</td>
                  <td>${ev.event_cause}</td>
                  <td>${ev.corridor}</td>
                  <td>${ev.zone}</td>
                  <td class="${ev.priority === "High" ? "high" : "low"}">${ev.priority}</td>
                  <td class="${ev.status === "active" ? "active" : "closed"}">${ev.status}</td>
                  <td>${ev.duration_bucket || "—"}</td>
                  <td>${ev.elapsed_label}</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>

          <div class="footer">
            BengaluruOps 2.0 — AI Traffic Command Center &nbsp;|&nbsp;
            Bengaluru Traffic Police &nbsp;|&nbsp;
            This is an automated report. Please verify critical events independently before handover.
          </div>
        </body>
        </html>
      `);
      win.document.close();
      win.focus();
      setTimeout(() => {
        win.print();
        setExportingPDF(false);
      }, 400);
    }, 100);
  };

  // Client-side search filtering
  const filteredEvents = (data?.events || []).filter((ev) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      ev.event_cause.toLowerCase().includes(q) ||
      ev.corridor.toLowerCase().includes(q) ||
      ev.zone.toLowerCase().includes(q) ||
      ev.address.toLowerCase().includes(q)
    );
  });

  const now = new Date().toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  return (
    <div className="screen active" ref={printRef}>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div className="page-title">📋 Incident Timeline — Shift Report</div>
          <div className="page-sub">
            Chronological activity log for field officer handover · Generated {now} IST
          </div>
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            className="btn btn-ghost"
            onClick={fetchTimeline}
            disabled={loading}
            id="shift-refresh-btn"
          >
            {loading ? "⏳ Loading..." : "🔄 Refresh"}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleExportPDF}
            disabled={!data || exportingPDF}
            id="shift-export-btn"
            style={{
              background: "linear-gradient(135deg, #dc2626, #ef4444)",
              border: "none",
            }}
          >
            {exportingPDF ? "⏳ Preparing..." : "📄 Export PDF"}
          </button>
        </div>
      </div>

      {/* Filters Row */}
      <div
        className="card"
        style={{
          marginBottom: "20px",
          padding: "16px 20px",
          display: "flex",
          gap: "12px",
          alignItems: "flex-end",
          flexWrap: "wrap",
        }}
      >
        {/* Time Window */}
        <div className="form-group" style={{ marginBottom: 0, minWidth: "160px" }}>
          <label className="form-label">⏱ Time Window</label>
          <div style={{ display: "flex", gap: "6px" }}>
            {[8, 12, 24].map((h) => (
              <button
                key={h}
                className={`filter-pill ${hours === h ? "active" : ""}`}
                onClick={() => setHours(h)}
                id={`shift-hours-${h}`}
                style={{ padding: "6px 14px", fontSize: "12px" }}
              >
                {h}H
              </button>
            ))}
          </div>
        </div>

        {/* Zone Filter */}
        <div className="form-group" style={{ marginBottom: 0, flex: 1, minWidth: "180px" }}>
          <label className="form-label">🗺 Filter by Zone</label>
          <select
            className="form-select"
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value)}
            id="shift-zone-filter"
          >
            <option value="">All Zones</option>
            {zones.map((z) => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        </div>

        {/* Corridor Filter */}
        <div className="form-group" style={{ marginBottom: 0, flex: 1, minWidth: "200px" }}>
          <label className="form-label">🛣 Filter by Corridor</label>
          <select
            className="form-select"
            value={corridorFilter}
            onChange={(e) => setCorridorFilter(e.target.value)}
            id="shift-corridor-filter"
          >
            <option value="">All Corridors</option>
            {corridors.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="form-group" style={{ marginBottom: 0, flex: 1.5, minWidth: "200px" }}>
          <label className="form-label">🔍 Search Events</label>
          <input
            type="text"
            className="search-input"
            placeholder="Search cause, corridor, zone..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            id="shift-search"
            style={{ paddingLeft: "12px" }}
          />
        </div>
      </div>

      {/* Summary Cards */}
      {data && (
        <div className="grid4" style={{ marginBottom: "20px" }}>
          <SummaryCard
            icon="📊"
            value={data.total_events}
            label={`Events in Last ${hours}H`}
            color="var(--primary)"
          />
          <SummaryCard
            icon="🚨"
            value={data.high_priority_count}
            label="High Priority"
            color="var(--red)"
          />
          <SummaryCard
            icon="🚧"
            value={data.closure_count}
            label="Road Closures"
            color="var(--amber)"
          />
          <SummaryCard
            icon="✅"
            value={data.resolved_count}
            label="Resolved / Closed"
            color="var(--green)"
          />
        </div>
      )}

      {/* Timeline Feed */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {/* Card Header */}
        <div
          style={{
            padding: "14px 20px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div className="card-title" style={{ marginBottom: 0 }}>
            Chronological Event Feed
          </div>
          {data && (
            <span className="badge badge-blue">
              {filteredEvents.length} event{filteredEvents.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center" }}>
            <div className="shift-spinner" />
            <div style={{ color: "var(--text-secondary)", fontSize: "13px", marginTop: "12px" }}>
              Loading incident timeline...
            </div>
          </div>
        ) : !data || filteredEvents.length === 0 ? (
          <div style={{ padding: "48px 24px", textAlign: "center" }}>
            <div style={{ fontSize: "40px", marginBottom: "12px" }}>📭</div>
            <div style={{ color: "var(--text-secondary)", fontSize: "14px", fontWeight: "600" }}>
              No incidents found
            </div>
            <div style={{ color: "var(--text-tertiary)", fontSize: "12px", marginTop: "4px" }}>
              Adjust the time window or filter options above
            </div>
          </div>
        ) : (
          <div style={{ maxHeight: "520px", overflowY: "auto" }}>
            {/* Sticky column headers */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "32px 1fr 1fr 1fr 90px 80px 90px 80px",
                gap: "8px",
                padding: "10px 20px",
                background: "var(--bg)",
                borderBottom: "1px solid var(--border)",
                position: "sticky",
                top: 0,
                zIndex: 2,
              }}
            >
              {["#", "Event Cause", "Corridor", "Zone", "Priority", "Status", "Duration", "Time"].map((h) => (
                <div
                  key={h}
                  style={{
                    fontSize: "10px",
                    fontWeight: "700",
                    color: "var(--text-tertiary)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  {h}
                </div>
              ))}
            </div>

            {/* Event rows */}
            {filteredEvents.map((ev, idx) => (
              <div
                key={ev.id}
                className="shift-event-row"
                style={{
                  display: "grid",
                  gridTemplateColumns: "32px 1fr 1fr 1fr 90px 80px 90px 80px",
                  gap: "8px",
                  padding: "12px 20px",
                  borderBottom: "1px solid var(--border)",
                  alignItems: "center",
                  transition: "background 0.15s",
                  borderLeft: ev.priority === "High" ? "3px solid var(--red)" : "3px solid transparent",
                }}
              >
                {/* Index */}
                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--text-tertiary)",
                    fontFamily: "JetBrains Mono, monospace",
                    fontWeight: "600",
                  }}
                >
                  {idx + 1}
                </div>

                {/* Event cause */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "16px" }}>{getCauseIcon(ev.event_cause)}</span>
                  <div>
                    <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-primary)" }}>
                      {ev.event_cause}
                    </div>
                    {ev.address && (
                      <div
                        style={{
                          fontSize: "10px",
                          color: "var(--text-tertiary)",
                          marginTop: "1px",
                          maxWidth: "160px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ev.address}
                      </div>
                    )}
                  </div>
                </div>

                {/* Corridor */}
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "500" }}>
                  {ev.corridor}
                </div>

                {/* Zone */}
                <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{ev.zone}</div>

                {/* Priority */}
                <div>
                  <PriorityBadge priority={ev.priority} />
                  {ev.requires_road_closure && (
                    <div style={{ fontSize: "10px", color: "var(--amber)", marginTop: "3px" }}>
                      🚧 Closed
                    </div>
                  )}
                </div>

                {/* Status */}
                <div>
                  <StatusBadge status={ev.status} />
                </div>

                {/* Duration */}
                <div>
                  {ev.duration_bucket ? (
                    <span
                      className={`badge ${
                        ev.duration_bucket === "Fast"
                          ? "badge-green"
                          : ev.duration_bucket === "Medium"
                          ? "badge-amber"
                          : "badge-red"
                      }`}
                    >
                      {ev.duration_bucket}
                    </span>
                  ) : (
                    <span style={{ color: "var(--text-tertiary)", fontSize: "12px" }}>—</span>
                  )}
                </div>

                {/* Elapsed */}
                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--text-tertiary)",
                    fontFamily: "JetBrains Mono, monospace",
                    fontWeight: "600",
                  }}
                >
                  {ev.elapsed_label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer note */}
      <div
        style={{
          marginTop: "16px",
          padding: "12px 16px",
          background: "var(--primary-dim)",
          borderRadius: "10px",
          border: "1px solid var(--primary)",
          fontSize: "12px",
          color: "var(--text-secondary)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <span style={{ fontSize: "18px" }}>ℹ️</span>
        <span>
          <strong style={{ color: "var(--text-primary)" }}>Shift Handover Note:</strong> This report
          reflects the last {hours} hours of activity. High-priority events (red left border) require
          explicit handover acknowledgment. Use the <strong>Export PDF</strong> button to generate the
          formal handover document.
        </span>
      </div>
    </div>
  );
}

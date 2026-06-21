import React, { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "";

function DaysBar({ days }) {
  // Visual severity bar: green < 7d, amber 7-14d, red > 14d
  const maxDays = 30;
  const pct = Math.min((days / maxDays) * 100, 100);
  const color = days <= 7 ? "var(--amber)" : days <= 14 ? "var(--red)" : "#7c1d1d";
  return (
    <div style={{ marginTop: "6px" }}>
      <div style={{ height: "5px", background: "var(--border)", borderRadius: "99px", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: "99px", transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

function TicketModal({ ticket, onClose }) {
  if (!ticket) return null;
  return (
    <div
      style={{
        position: "fixed", inset: 0,
        background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 9999,
        animation: "fadeIn 0.2s ease-out",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--card-bg)",
          border: "1px solid var(--border)",
          borderRadius: "16px",
          padding: "32px",
          maxWidth: "440px",
          width: "90%",
          boxShadow: "0 24px 60px rgba(0,0,0,0.25)",
          animation: "slideUp 0.25s cubic-bezier(0.22,1,0.36,1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ fontSize: "48px", marginBottom: "8px" }}>✅</div>
          <div style={{ fontSize: "18px", fontWeight: "800", color: "var(--green)" }}>
            Escalation Raised!
          </div>
          <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "4px" }}>
            BBMP has been notified
          </div>
        </div>

        {/* Ticket Details */}
        <div
          style={{
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: "10px",
            padding: "16px",
            marginBottom: "20px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
            <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontWeight: "700", textTransform: "uppercase" }}>
              Ticket ID
            </span>
            <span
              style={{
                fontFamily: "JetBrains Mono, monospace",
                fontSize: "14px",
                fontWeight: "700",
                color: "var(--primary)",
              }}
            >
              {ticket.ticket_id}
            </span>
          </div>
          {[
            { label: "Assigned To", value: ticket.assigned_to },
            { label: "Priority Level", value: ticket.priority_level },
            { label: "Escalated At", value: ticket.escalated_at },
            { label: "Est. Response", value: `${ticket.estimated_response_days}–${ticket.estimated_response_days + 1} days` },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderTop: "1px solid var(--border)" }}>
              <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{label}</span>
              <span style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-primary)", textAlign: "right", maxWidth: "60%" }}>{value}</span>
            </div>
          ))}
        </div>

        <div
          style={{
            fontSize: "11px",
            color: "var(--text-tertiary)",
            textAlign: "center",
            marginBottom: "20px",
            lineHeight: "1.5",
          }}
        >
          {ticket.message}
        </div>

        <button
          className="btn btn-primary"
          style={{ width: "100%", justifyContent: "center" }}
          onClick={onClose}
        >
          Done — Close
        </button>
      </div>
    </div>
  );
}

export default function PotholeTracker({ addToast }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [escalating, setEscalating] = useState({});
  const [escalatedIds, setEscalatedIds] = useState(new Set());
  const [ticketModal, setTicketModal] = useState(null);
  const [sortBy, setSortBy] = useState("days"); // "days" | "priority" | "corridor"

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/analytics/pothole-escalation`);
      if (res.ok) {
        setData(await res.json());
      }
    } catch (err) {
      addToast?.("⚠️", "Failed to load pothole data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleEscalate = async (incidentId) => {
    if (escalatedIds.has(incidentId)) {
      addToast?.("ℹ️", "This incident has already been escalated.");
      return;
    }

    setEscalating((prev) => ({ ...prev, [incidentId]: true }));
    try {
      const res = await fetch(`${API}/api/analytics/pothole-escalation/escalate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_id: incidentId }),
      });

      if (res.ok) {
        const ticket = await res.json();
        setEscalatedIds((prev) => new Set([...prev, incidentId]));
        setTicketModal(ticket);
        addToast?.("✅", `BBMP Ticket ${ticket.ticket_id} raised successfully`);
      } else {
        addToast?.("❌", "Failed to raise escalation. Try again.");
      }
    } catch (err) {
      addToast?.("❌", "Backend error — could not escalate.");
    } finally {
      setEscalating((prev) => ({ ...prev, [incidentId]: false }));
    }
  };

  // Sort escalations
  const sortedEscalations = [...(data?.escalations || [])].sort((a, b) => {
    if (sortBy === "days") return (b.duration_days || 0) - (a.duration_days || 0);
    if (sortBy === "priority") return a.priority === "High" ? -1 : 1;
    if (sortBy === "corridor") return (a.corridor || "").localeCompare(b.corridor || "");
    return 0;
  });

  return (
    <div className="screen active">
      {/* Ticket success modal */}
      <TicketModal ticket={ticketModal} onClose={() => setTicketModal(null)} />

      {/* Header */}
      <div className="page-header" style={{ marginBottom: "20px" }}>
        <div>
          <div className="page-title">🕳️ Pothole Escalation Tracker</div>
          <div className="page-sub">
            Long-running pothole incidents beyond Traffic Police jurisdiction — escalate to BBMP
          </div>
        </div>
        <button
          className="btn btn-ghost"
          onClick={fetchData}
          disabled={loading}
          id="pothole-refresh-btn"
        >
          {loading ? "⏳ Loading..." : "🔄 Refresh"}
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "60px" }}>
          <div className="shift-spinner" />
          <div style={{ color: "var(--text-secondary)", fontSize: "13px", marginTop: "12px" }}>
            Scanning active pothole incidents...
          </div>
        </div>
      ) : (
        <>
          {/* KPI Summary */}
          <div className="grid3" style={{ marginBottom: "20px" }}>
            <div className="card" style={{ borderTop: "3px solid var(--amber)" }}>
              <div style={{ fontSize: "22px", marginBottom: "6px" }}>🕳️</div>
              <div className="metric-val" style={{ color: "var(--amber)" }}>
                {data?.total_potholes_active ?? 0}
              </div>
              <div className="metric-lbl">Total Active Potholes</div>
            </div>
            <div className="card" style={{ borderTop: "3px solid var(--red)" }}>
              <div style={{ fontSize: "22px", marginBottom: "6px" }}>🚨</div>
              <div className="metric-val" style={{ color: "var(--red)" }}>
                {data?.needs_escalation ?? 0}
              </div>
              <div className="metric-lbl">Require BBMP Escalation</div>
            </div>
            <div className="card" style={{ borderTop: "3px solid var(--green)" }}>
              <div style={{ fontSize: "22px", marginBottom: "6px" }}>✅</div>
              <div className="metric-val" style={{ color: "var(--green)" }}>
                {escalatedIds.size}
              </div>
              <div className="metric-lbl">Escalated This Session</div>
            </div>
          </div>

          {/* Info Banner */}
          <div
            style={{
              padding: "14px 18px",
              background: "var(--amber-dim)",
              border: "1px solid var(--amber)",
              borderRadius: "10px",
              marginBottom: "20px",
              display: "flex",
              alignItems: "flex-start",
              gap: "12px",
            }}
          >
            <span style={{ fontSize: "20px", flexShrink: 0 }}>⚠️</span>
            <div>
              <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)", marginBottom: "2px" }}>
                Jurisdiction Alert — BBMP Action Required
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5" }}>
                {data?.message || "Pothole incidents open for 24+ hours exceed Traffic Police jurisdiction."}
                {" "}These require BBMP Maintenance Division intervention. Click <strong>Escalate to BBMP</strong> to raise a formal ticket.
              </div>
            </div>
          </div>

          {/* Sort controls */}
          {sortedEscalations.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
                Sort by:
              </span>
              {[
                { key: "days", label: "⏱ Duration" },
                { key: "priority", label: "⚠ Priority" },
                { key: "corridor", label: "🛣 Corridor" },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  className={`filter-pill ${sortBy === key ? "active" : ""}`}
                  onClick={() => setSortBy(key)}
                  id={`pothole-sort-${key}`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Escalation Cards */}
          {sortedEscalations.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "48px" }}>
              <div style={{ fontSize: "48px", marginBottom: "12px" }}>🎉</div>
              <div style={{ fontSize: "16px", fontWeight: "700", color: "var(--green)", marginBottom: "6px" }}>
                No Potholes Require Escalation
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                All active pothole incidents are within normal resolution time.
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {sortedEscalations.map((ev) => {
                const isEscalated = escalatedIds.has(ev.id);
                const isLoading = escalating[ev.id];
                const days = ev.duration_days ?? 0;
                const severity =
                  days > 14 ? "critical" : days > 7 ? "high" : "medium";
                const severityColor =
                  severity === "critical"
                    ? "#7c1d1d"
                    : severity === "high"
                    ? "var(--red)"
                    : "var(--amber)";

                return (
                  <div
                    key={ev.id}
                    className="card"
                    style={{
                      borderLeft: `4px solid ${isEscalated ? "var(--green)" : severityColor}`,
                      padding: "18px 20px",
                      opacity: isEscalated ? 0.75 : 1,
                      transition: "all 0.3s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px" }}>
                      {/* Left: info */}
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                          <span style={{ fontSize: "22px" }}>🕳️</span>
                          <div>
                            <div style={{ fontSize: "14px", fontWeight: "700", color: "var(--text-primary)" }}>
                              Pothole Incident{" "}
                              <span
                                style={{
                                  fontFamily: "JetBrains Mono, monospace",
                                  fontSize: "12px",
                                  color: "var(--text-tertiary)",
                                }}
                              >
                                #{ev.id}
                              </span>
                            </div>
                            {ev.address && (
                              <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "1px" }}>
                                📍 {ev.address}
                              </div>
                            )}
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "10px" }}>
                          <span className={`badge ${ev.priority === "High" ? "badge-red" : "badge-amber"}`}>
                            ⚠ {ev.priority} Priority
                          </span>
                          {ev.corridor && ev.corridor !== "Non-corridor" && (
                            <span className="badge badge-blue">🛣 {ev.corridor}</span>
                          )}
                          <span
                            className="badge"
                            style={{
                              background: `${severityColor}20`,
                              color: severityColor,
                              border: `1px solid ${severityColor}40`,
                            }}
                          >
                            {severity === "critical" ? "🔴 Critical" : severity === "high" ? "🟠 High" : "🟡 Medium"} Age
                          </span>
                          {isEscalated && (
                            <span className="badge badge-green">✅ Escalated</span>
                          )}
                        </div>

                        {/* Duration bar */}
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginBottom: "3px" }}>
                              Open Duration
                            </div>
                            <DaysBar days={days} />
                          </div>
                          <div
                            style={{
                              fontFamily: "JetBrains Mono, monospace",
                              fontSize: "20px",
                              fontWeight: "800",
                              color: severityColor,
                              minWidth: "70px",
                              textAlign: "right",
                            }}
                          >
                            {days > 0 ? `${days}d` : `${Math.round((ev.duration_minutes || 0) / 60)}h`}
                          </div>
                        </div>
                      </div>

                      {/* Right: action */}
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px", alignItems: "flex-end", flexShrink: 0 }}>
                        <div
                          style={{
                            fontSize: "11px",
                            color: "var(--text-tertiary)",
                            fontWeight: "600",
                            textAlign: "right",
                          }}
                        >
                          Recommended Action:
                        </div>
                        <div
                          style={{
                            fontSize: "11px",
                            color: "var(--amber)",
                            fontWeight: "700",
                            textAlign: "right",
                            maxWidth: "160px",
                          }}
                        >
                          {ev.action}
                        </div>

                        <button
                          className="btn"
                          id={`escalate-btn-${ev.id}`}
                          disabled={isEscalated || isLoading}
                          onClick={() => handleEscalate(ev.id)}
                          style={{
                            marginTop: "8px",
                            background: isEscalated
                              ? "var(--green-dim)"
                              : "linear-gradient(135deg, #f59e0b, #d97706)",
                            color: isEscalated ? "var(--green)" : "#ffffff",
                            border: isEscalated ? "1px solid var(--green)" : "none",
                            fontWeight: "700",
                            fontSize: "12px",
                            padding: "8px 16px",
                            whiteSpace: "nowrap",
                            cursor: isEscalated ? "default" : "pointer",
                            boxShadow: isEscalated ? "none" : "0 4px 12px rgba(245,158,11,0.3)",
                          }}
                        >
                          {isLoading
                            ? "⏳ Escalating..."
                            : isEscalated
                            ? "✅ Escalated"
                            : "📤 Escalate to BBMP"}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Escalated session summary */}
          {escalatedIds.size > 0 && (
            <div
              style={{
                marginTop: "20px",
                padding: "14px 18px",
                background: "var(--green-dim)",
                border: "1px solid var(--green)",
                borderRadius: "10px",
                display: "flex",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <span style={{ fontSize: "22px" }}>📬</span>
              <div>
                <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--green)", marginBottom: "2px" }}>
                  {escalatedIds.size} escalation{escalatedIds.size > 1 ? "s" : ""} submitted this session
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  BBMP Maintenance Division has been notified. Expected response within 48–72 hours.
                  Follow up if no action within 5 business days.
                </div>
              </div>
            </div>
          )}

          {/* Instruction note */}
          <div
            style={{
              marginTop: "16px",
              padding: "12px 16px",
              background: "var(--bg)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              fontSize: "12px",
              color: "var(--text-tertiary)",
            }}
          >
            <strong style={{ color: "var(--text-secondary)" }}>ℹ️ Escalation Policy:</strong> Pothole
            incidents open for more than <strong>24 hours</strong> are automatically flagged. Traffic
            Police authority covers traffic management only — road surface repairs require BBMP Maintenance
            Division. Escalation tickets are logged and tracked via the BBMP Works Management System.
          </div>
        </>
      )}
    </div>
  );
}

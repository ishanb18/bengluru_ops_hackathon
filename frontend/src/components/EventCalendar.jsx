import React, { useState, useEffect } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

const CORRIDORS = [
  "Tumkur Road", "Mysore Road", "Bellary Road 1", "Bellary Road 2",
  "Hosur Road", "ORR East 1", "ORR East 2", "ORR North 1",
  "Old Madras Road", "Bannerghata Road", "Magadi Road",
  "West of Chord Road", "CBD 1", "Non-corridor"
];

const EVENT_TYPES = ["Public Event", "VIP Movement", "Road Work", "Sports Event", "Festival"];

const TYPE_EMOJI = {
  "Public Event": "🎉",
  "VIP Movement": "👑",
  "Road Work": "🚧",
  "Sports Event": "🏆",
  "Festival": "🪔",
};

const IMPACT_COLOR = {
  High: "var(--red)",
  Medium: "var(--amber)",
  Low: "var(--green)",
};

const EMPTY_FORM = {
  title: "",
  event_type: "Public Event",
  corridor: "Tumkur Road",
  date: "",
  time: "08:00",
  duration_hours: 2,
  impact: "Medium",
  description: "",
};

export default function EventCalendar() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const fetchEvents = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/planned-events`);
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEvents(); }, []);

  const showToast = (msg, color = "var(--green)") => {
    setToast({ msg, color });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSubmit = async () => {
    if (!form.title || !form.date) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/planned-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, duration_hours: parseFloat(form.duration_hours) }),
      });
      if (res.ok) {
        setShowModal(false);
        setForm(EMPTY_FORM);
        await fetchEvents();
        showToast("✅ Event scheduled successfully!");
      }
    } catch (e) {
      showToast("❌ Failed to schedule event", "var(--red)");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await fetch(`${BACKEND_URL}/api/planned-events/${id}`, { method: "DELETE" });
      await fetchEvents();
      showToast("🗑️ Event removed");
    } catch (e) {}
  };

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", weekday: "short" });
  };

  const daysUntil = (dateStr) => {
    const diff = new Date(dateStr) - new Date();
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    if (days < 0) return "Past";
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    return `In ${days} days`;
  };

  return (
    <div style={{ padding: "0" }}>
      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed", top: "20px", right: "20px", zIndex: 9999,
          background: toast.color, color: "white", padding: "12px 20px",
          borderRadius: "10px", fontWeight: "700", fontSize: "13px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
        }}>{toast.msg}</div>
      )}

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h2 style={{ fontSize: "20px", fontWeight: "800", color: "var(--text-primary)", margin: 0 }}>Event Calendar</h2>
          <p style={{ fontSize: "12px", color: "var(--text-tertiary)", margin: "4px 0 0" }}>
            Scheduled operations, VIP movements, and planned road work — {events.length} upcoming events
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          style={{
            background: "linear-gradient(135deg, #3b82f6, #6366f1)",
            color: "white", border: "none", borderRadius: "10px",
            padding: "10px 18px", fontWeight: "700", fontSize: "13px",
            cursor: "pointer", display: "flex", alignItems: "center", gap: "6px"
          }}
        >
          + Schedule Event
        </button>
      </div>

      {/* Events List */}
      {loading ? (
        <div style={{ textAlign: "center", color: "var(--text-tertiary)", padding: "60px" }}>Loading events...</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {events.map((ev, idx) => (
            <div key={ev.id} style={{
              display: "grid",
              gridTemplateColumns: "90px 1fr",
              gap: "16px",
              alignItems: "stretch",
            }}>
              {/* Date Column */}
              <div style={{
                background: "var(--card-bg)",
                border: "1px solid var(--border)",
                borderRadius: "12px",
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                padding: "12px 8px",
                textAlign: "center",
              }}>
                <div style={{ fontSize: "22px", fontWeight: "900", color: IMPACT_COLOR[ev.impact], lineHeight: 1 }}>
                  {new Date(ev.date).getDate()}
                </div>
                <div style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-secondary)", textTransform: "uppercase" }}>
                  {new Date(ev.date).toLocaleString("en-IN", { month: "short" })}
                </div>
                <div style={{ fontSize: "9px", color: "var(--text-tertiary)", marginTop: "4px", fontWeight: "600" }}>
                  {daysUntil(ev.date)}
                </div>
              </div>

              {/* Event Card */}
              <div className="card" style={{ padding: "14px 16px", position: "relative" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      <span style={{ fontSize: "16px" }}>{TYPE_EMOJI[ev.event_type] || "📋"}</span>
                      <span style={{ fontSize: "14px", fontWeight: "800", color: "var(--text-primary)" }}>{ev.title}</span>
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "6px" }}>
                      <span style={{
                        background: IMPACT_COLOR[ev.impact] + "22",
                        color: IMPACT_COLOR[ev.impact],
                        fontSize: "10px", fontWeight: "700",
                        padding: "2px 8px", borderRadius: "20px",
                        border: `1px solid ${IMPACT_COLOR[ev.impact]}44`
                      }}>{ev.impact} Impact</span>
                      <span style={{ fontSize: "10px", color: "var(--text-tertiary)", background: "var(--bg-secondary)", padding: "2px 8px", borderRadius: "20px" }}>
                        {ev.event_type}
                      </span>
                      <span style={{ fontSize: "10px", color: "var(--text-tertiary)", background: "var(--bg-secondary)", padding: "2px 8px", borderRadius: "20px" }}>
                        📍 {ev.corridor}
                      </span>
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-secondary)", lineHeight: 1.5 }}>{ev.description}</div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "6px", marginLeft: "12px" }}>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>{ev.time} · {ev.duration_hours}h</div>
                      <div style={{ fontSize: "12px", fontWeight: "700", color: "var(--amber)" }}>👮 {ev.manpower_needed} officers</div>
                    </div>
                    <button
                      onClick={() => handleDelete(ev.id)}
                      style={{
                        background: "transparent", border: "1px solid var(--border)",
                        borderRadius: "6px", padding: "4px 8px", cursor: "pointer",
                        color: "var(--text-tertiary)", fontSize: "12px"
                      }}
                    >🗑️</button>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {events.length === 0 && (
            <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--text-tertiary)" }}>
              <div style={{ fontSize: "40px", marginBottom: "12px" }}>📅</div>
              <div style={{ fontWeight: "700" }}>No planned events scheduled</div>
              <div style={{ fontSize: "12px", marginTop: "4px" }}>Click "+ Schedule Event" to add one</div>
            </div>
          )}
        </div>
      )}

      {/* Schedule Modal */}
      {showModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
          zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(4px)"
        }} onClick={(e) => e.target === e.currentTarget && setShowModal(false)}>
          <div style={{
            background: "var(--card-bg)", border: "1px solid var(--border)",
            borderRadius: "16px", padding: "28px", width: "520px", maxHeight: "90vh",
            overflowY: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.4)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "20px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "800", color: "var(--text-primary)", margin: 0 }}>📅 Schedule New Event</h3>
              <button onClick={() => setShowModal(false)} style={{ background: "none", border: "none", fontSize: "18px", cursor: "pointer", color: "var(--text-tertiary)" }}>✕</button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {/* Title */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Event Title *</label>
                <input
                  value={form.title}
                  onChange={e => setForm(p => ({...p, title: e.target.value}))}
                  placeholder="e.g. Ganesh Chaturthi Procession"
                  style={{
                    width: "100%", boxSizing: "border-box", padding: "10px 12px",
                    background: "var(--bg-secondary)", border: "1px solid var(--border)",
                    borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px"
                  }}
                />
              </div>

              {/* Event Type + Impact row */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Event Type</label>
                  <select value={form.event_type} onChange={e => setForm(p => ({...p, event_type: e.target.value}))}
                    style={{ width: "100%", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}>
                    {EVENT_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Traffic Impact</label>
                  <select value={form.impact} onChange={e => setForm(p => ({...p, impact: e.target.value}))}
                    style={{ width: "100%", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}>
                    <option>Low</option>
                    <option>Medium</option>
                    <option>High</option>
                  </select>
                </div>
              </div>

              {/* Corridor */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Affected Corridor</label>
                <select value={form.corridor} onChange={e => setForm(p => ({...p, corridor: e.target.value}))}
                  style={{ width: "100%", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}>
                  {CORRIDORS.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>

              {/* Date + Time + Duration */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Date *</label>
                  <input type="date" value={form.date} onChange={e => setForm(p => ({...p, date: e.target.value}))}
                    style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }} />
                </div>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Time</label>
                  <input type="time" value={form.time} onChange={e => setForm(p => ({...p, time: e.target.value}))}
                    style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }} />
                </div>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Duration (hrs)</label>
                  <input type="number" min="0.5" step="0.5" value={form.duration_hours} onChange={e => setForm(p => ({...p, duration_hours: e.target.value}))}
                    style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", background: "var(--bg-secondary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }} />
                </div>
              </div>

              {/* Description */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm(p => ({...p, description: e.target.value}))}
                  placeholder="Expected impact, diversions, special instructions..."
                  rows={3}
                  style={{
                    width: "100%", boxSizing: "border-box", padding: "10px 12px",
                    background: "var(--bg-secondary)", border: "1px solid var(--border)",
                    borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px",
                    resize: "vertical", fontFamily: "inherit"
                  }}
                />
              </div>

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={submitting || !form.title || !form.date}
                style={{
                  background: submitting ? "var(--border)" : "linear-gradient(135deg, #3b82f6, #6366f1)",
                  color: "white", border: "none", borderRadius: "10px",
                  padding: "12px", fontWeight: "700", fontSize: "14px",
                  cursor: submitting ? "not-allowed" : "pointer", marginTop: "4px"
                }}
              >
                {submitting ? "Scheduling..." : "📅 Schedule Event"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

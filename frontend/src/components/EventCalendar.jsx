import React, { useState, useEffect } from "react";

const BACKEND_URL = import.meta.env.VITE_API_URL || "";

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

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

// ─── Helper: Get calendar grid for a month ────────────────────────────────────
function getCalendarGrid(year, month) {
  const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const prevMonthDays = new Date(year, month, 0).getDate();

  const cells = [];

  // Leading days from previous month
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({ day: prevMonthDays - i, inMonth: false, date: null });
  }

  // Days of current month
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({ day: d, inMonth: true, date: dateStr });
  }

  // Trailing days to fill the last row
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    for (let i = 1; i <= remaining; i++) {
      cells.push({ day: i, inMonth: false, date: null });
    }
  }

  return cells;
}

// ─── Event Dot Indicators ─────────────────────────────────────────────────────
function EventDots({ dayEvents }) {
  if (!dayEvents || dayEvents.length === 0) return null;
  // Show up to 3 dots, then a "+N" indicator
  const shown = dayEvents.slice(0, 3);
  const extra = dayEvents.length - 3;
  return (
    <div style={{ display: "flex", gap: "3px", justifyContent: "center", marginTop: "4px", flexWrap: "wrap" }}>
      {shown.map((ev, i) => (
        <div
          key={i}
          title={`${TYPE_EMOJI[ev.event_type] || "📋"} ${ev.title} (${ev.impact})`}
          style={{
            width: "7px", height: "7px", borderRadius: "50%",
            background: IMPACT_COLOR[ev.impact] || "var(--primary)",
            boxShadow: `0 0 0 2px ${(IMPACT_COLOR[ev.impact] || "var(--primary)") + "33"}`,
            flexShrink: 0,
          }}
        />
      ))}
      {extra > 0 && (
        <span style={{ fontSize: "8px", fontWeight: "800", color: "var(--text-tertiary)", lineHeight: "7px" }}>
          +{extra}
        </span>
      )}
    </div>
  );
}

// ─── Selected Day Detail Panel ────────────────────────────────────────────────
function DayDetailPanel({ date, events, onClose, onDelete }) {
  if (!date) return null;
  const d = new Date(date + "T00:00:00");
  const formatted = d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="card" style={{ marginTop: "20px", padding: "20px", animation: "slideUp 0.25s ease-out" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
        <div>
          <div className="card-title" style={{ marginBottom: "2px" }}>Events on {formatted}</div>
          <div style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
            {events.length} event{events.length !== 1 ? "s" : ""} scheduled
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "var(--bg)", border: "1px solid var(--border)",
            borderRadius: "8px", width: "32px", height: "32px",
            cursor: "pointer", fontSize: "14px", color: "var(--text-tertiary)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >✕</button>
      </div>

      {events.length === 0 ? (
        <div style={{ textAlign: "center", padding: "24px", color: "var(--text-tertiary)" }}>
          <div style={{ fontSize: "28px", marginBottom: "8px" }}>📭</div>
          <div style={{ fontSize: "13px" }}>No events on this date</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {events.map((ev) => (
            <div
              key={ev.id}
              style={{
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderLeft: `4px solid ${IMPACT_COLOR[ev.impact] || "var(--primary)"}`,
                borderRadius: "10px",
                padding: "14px 16px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <span style={{ fontSize: "18px" }}>{TYPE_EMOJI[ev.event_type] || "📋"}</span>
                    <span style={{ fontSize: "14px", fontWeight: "800", color: "var(--text-primary)" }}>{ev.title}</span>
                  </div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "8px" }}>
                    <span style={{
                      background: (IMPACT_COLOR[ev.impact] || "var(--primary)") + "18",
                      color: IMPACT_COLOR[ev.impact] || "var(--primary)",
                      fontSize: "10px", fontWeight: "700",
                      padding: "3px 10px", borderRadius: "20px",
                      border: `1px solid ${(IMPACT_COLOR[ev.impact] || "var(--primary)") + "40"}`
                    }}>
                      {ev.impact} Impact
                    </span>
                    <span className="badge badge-blue" style={{ fontSize: "10px" }}>{ev.event_type}</span>
                    <span className="badge" style={{ fontSize: "10px", background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                      📍 {ev.corridor}
                    </span>
                  </div>
                  {ev.description && (
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "6px" }}>
                      {ev.description}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: "16px", fontSize: "11px", color: "var(--text-tertiary)", fontWeight: "600" }}>
                    <span>🕐 {ev.time} · {ev.duration_hours}h</span>
                    <span>👮 {ev.manpower_needed} officers</span>
                  </div>
                </div>

                <button
                  onClick={() => onDelete(ev.id)}
                  title="Delete event"
                  style={{
                    background: "transparent", border: "1px solid var(--border)",
                    borderRadius: "6px", padding: "5px 8px", cursor: "pointer",
                    color: "var(--text-tertiary)", fontSize: "13px", marginLeft: "12px",
                    transition: "all 0.15s",
                  }}
                >🗑️</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// ─── Main Component ───────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

export default function EventCalendar() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  // Calendar state
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState(null);

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
        // Navigate to the month of the new event
        const d = new Date(form.date);
        setViewYear(d.getFullYear());
        setViewMonth(d.getMonth());
        setSelectedDate(form.date);
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

  // ── Month navigation ────────────────────────────────────────────────────────
  const goToPrevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear(viewYear - 1);
    } else {
      setViewMonth(viewMonth - 1);
    }
    setSelectedDate(null);
  };

  const goToNextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear(viewYear + 1);
    } else {
      setViewMonth(viewMonth + 1);
    }
    setSelectedDate(null);
  };

  const goToToday = () => {
    setViewYear(today.getFullYear());
    setViewMonth(today.getMonth());
    setSelectedDate(null);
  };

  // ── Build event lookup by date ──────────────────────────────────────────────
  const eventsByDate = {};
  events.forEach((ev) => {
    if (!eventsByDate[ev.date]) eventsByDate[ev.date] = [];
    eventsByDate[ev.date].push(ev);
  });

  const calendarCells = getCalendarGrid(viewYear, viewMonth);
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  // Events for selected date
  const selectedEvents = selectedDate ? (eventsByDate[selectedDate] || []) : [];

  // Count events in current month view
  const monthEventCount = Object.keys(eventsByDate).filter((d) => {
    return d.startsWith(`${viewYear}-${String(viewMonth + 1).padStart(2, "0")}`);
  }).reduce((sum, d) => sum + eventsByDate[d].length, 0);

  return (
    <div style={{ padding: 0 }}>
      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed", top: "20px", right: "20px", zIndex: 9999,
          background: toast.color, color: "white", padding: "12px 20px",
          borderRadius: "10px", fontWeight: "700", fontSize: "13px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)", animation: "toastIn 0.3s ease-out",
        }}>{toast.msg}</div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h2 style={{ fontSize: "20px", fontWeight: "800", color: "var(--text-primary)", margin: 0 }}>
            📅 Event Calendar
          </h2>
          <p style={{ fontSize: "12px", color: "var(--text-tertiary)", margin: "4px 0 0" }}>
            Scheduled operations, VIP movements, and planned road work — {events.length} total events
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          style={{
            background: "linear-gradient(135deg, #3b82f6, #6366f1)",
            color: "white", border: "none", borderRadius: "10px",
            padding: "10px 18px", fontWeight: "700", fontSize: "13px",
            cursor: "pointer", display: "flex", alignItems: "center", gap: "6px",
            boxShadow: "0 4px 14px rgba(59,130,246,0.3)",
          }}
        >
          + Schedule Event
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "60px" }}>
          <div className="shift-spinner" />
          <div style={{ color: "var(--text-tertiary)", fontSize: "13px", marginTop: "12px" }}>Loading calendar...</div>
        </div>
      ) : (
        <>
          {/* ── Calendar Card ────────────────────────────────────────────────────── */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>

            {/* Month Navigation Bar */}
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "16px 20px",
              borderBottom: "1px solid var(--border)",
              background: "var(--bg)",
            }}>
              <button onClick={goToPrevMonth} className="cal-nav-btn" title="Previous month">
                ‹
              </button>

              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <h3 style={{ fontSize: "18px", fontWeight: "800", color: "var(--text-primary)", margin: 0 }}>
                  {MONTH_NAMES[viewMonth]} {viewYear}
                </h3>
                {monthEventCount > 0 && (
                  <span className="badge badge-blue" style={{ fontSize: "10px" }}>
                    {monthEventCount} event{monthEventCount !== 1 ? "s" : ""}
                  </span>
                )}
                <button
                  onClick={goToToday}
                  className="cal-today-btn"
                  title="Go to today"
                >
                  Today
                </button>
              </div>

              <button onClick={goToNextMonth} className="cal-nav-btn" title="Next month">
                ›
              </button>
            </div>

            {/* Weekday Headers */}
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(7, 1fr)",
              borderBottom: "1px solid var(--border)",
            }}>
              {WEEKDAY_LABELS.map((label, i) => (
                <div
                  key={label}
                  style={{
                    textAlign: "center",
                    padding: "10px 0",
                    fontSize: "11px",
                    fontWeight: "700",
                    color: i === 0 ? "var(--red)" : "var(--text-tertiary)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Calendar Grid */}
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(7, 1fr)",
            }}>
              {calendarCells.map((cell, idx) => {
                const isToday = cell.date === todayStr;
                const isSelected = cell.date === selectedDate;
                const dayEvents = cell.date ? (eventsByDate[cell.date] || []) : [];
                const hasEvents = dayEvents.length > 0;
                const isSunday = idx % 7 === 0;

                // Determine the highest impact event on this day for subtle bg tint
                let maxImpact = null;
                if (hasEvents) {
                  if (dayEvents.some((e) => e.impact === "High")) maxImpact = "High";
                  else if (dayEvents.some((e) => e.impact === "Medium")) maxImpact = "Medium";
                  else maxImpact = "Low";
                }

                return (
                  <div
                    key={idx}
                    onClick={() => {
                      if (cell.inMonth && cell.date) {
                        setSelectedDate(isSelected ? null : cell.date);
                      }
                    }}
                    style={{
                      minHeight: "80px",
                      padding: "8px 6px",
                      borderRight: (idx + 1) % 7 !== 0 ? "1px solid var(--border)" : "none",
                      borderBottom: idx < calendarCells.length - 7 ? "1px solid var(--border)" : "none",
                      cursor: cell.inMonth ? "pointer" : "default",
                      background: isSelected
                        ? "var(--primary-dim)"
                        : isToday
                        ? "var(--blue-dim)"
                        : hasEvents && maxImpact
                        ? (IMPACT_COLOR[maxImpact] || "var(--primary)").replace(")", ", 0.04)").replace("var(", "rgba(").replace("--red", "239, 68, 68").replace("--amber", "245, 158, 11").replace("--green", "34, 197, 94")
                        : "transparent",
                      opacity: cell.inMonth ? 1 : 0.3,
                      transition: "background 0.15s ease",
                      position: "relative",
                    }}
                    className={cell.inMonth ? "cal-day-cell" : ""}
                  >
                    {/* Day Number */}
                    <div style={{
                      display: "flex", justifyContent: "center", marginBottom: "2px",
                    }}>
                      <span style={{
                        fontSize: "13px",
                        fontWeight: isToday || hasEvents ? "800" : "500",
                        color: !cell.inMonth
                          ? "var(--text-tertiary)"
                          : isToday
                          ? "var(--primary)"
                          : isSunday
                          ? "var(--red)"
                          : "var(--text-primary)",
                        width: isToday ? "28px" : "auto",
                        height: isToday ? "28px" : "auto",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: "50%",
                        background: isToday ? "var(--primary)" : "transparent",
                        ...(isToday && { color: "#ffffff" }),
                      }}>
                        {cell.day}
                      </span>
                    </div>

                    {/* Event dots */}
                    {cell.inMonth && <EventDots dayEvents={dayEvents} />}

                    {/* Mini event label (first event title, truncated) */}
                    {cell.inMonth && hasEvents && (
                      <div style={{
                        marginTop: "3px",
                        fontSize: "9px",
                        fontWeight: "700",
                        color: IMPACT_COLOR[dayEvents[0].impact] || "var(--text-secondary)",
                        textAlign: "center",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        padding: "0 2px",
                        lineHeight: "1.3",
                      }}>
                        {TYPE_EMOJI[dayEvents[0].event_type] || ""} {dayEvents[0].title.length > 14 ? dayEvents[0].title.slice(0, 14) + "…" : dayEvents[0].title}
                      </div>
                    )}

                    {/* Selected indicator */}
                    {isSelected && (
                      <div style={{
                        position: "absolute", bottom: "2px", left: "50%", transform: "translateX(-50%)",
                        width: "20px", height: "3px", borderRadius: "2px",
                        background: "var(--primary)",
                      }} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Legend */}
          <div style={{
            display: "flex", alignItems: "center", gap: "20px",
            marginTop: "14px", padding: "0 4px",
          }}>
            <span style={{ fontSize: "11px", color: "var(--text-tertiary)", fontWeight: "600" }}>Legend:</span>
            {[
              { color: "var(--red)", label: "High Impact" },
              { color: "var(--amber)", label: "Medium Impact" },
              { color: "var(--green)", label: "Low Impact" },
            ].map(({ color, label }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: color, boxShadow: `0 0 0 2px ${color}33` }} />
                <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>{label}</span>
              </div>
            ))}
            <div style={{ display: "flex", alignItems: "center", gap: "5px", marginLeft: "8px" }}>
              <div style={{ width: "20px", height: "20px", borderRadius: "50%", background: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "10px", color: "#fff", fontWeight: "800" }}>
                {today.getDate()}
              </div>
              <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Today</span>
            </div>
          </div>

          {/* ── Selected Day Detail Panel ──────────────────────────────────────── */}
          {selectedDate && (
            <DayDetailPanel
              date={selectedDate}
              events={selectedEvents}
              onClose={() => setSelectedDate(null)}
              onDelete={handleDelete}
            />
          )}

          {/* ── Upcoming Events Summary (below calendar) ──────────────────────── */}
          {events.length > 0 && !selectedDate && (
            <div className="card" style={{ marginTop: "20px" }}>
              <div className="card-title">Upcoming Events Overview</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {events.slice(0, 5).map((ev) => {
                  const d = new Date(ev.date + "T00:00:00");
                  const diff = Math.ceil((d - new Date()) / (1000 * 60 * 60 * 24));
                  const countdown = diff < 0 ? "Past" : diff === 0 ? "Today" : diff === 1 ? "Tomorrow" : `In ${diff}d`;

                  return (
                    <div
                      key={ev.id}
                      onClick={() => {
                        setViewYear(d.getFullYear());
                        setViewMonth(d.getMonth());
                        setSelectedDate(ev.date);
                      }}
                      style={{
                        display: "flex", alignItems: "center", gap: "12px",
                        padding: "10px 12px",
                        background: "var(--bg)",
                        border: "1px solid var(--border)",
                        borderRadius: "8px",
                        cursor: "pointer",
                        transition: "all 0.15s",
                        borderLeft: `3px solid ${IMPACT_COLOR[ev.impact] || "var(--primary)"}`,
                      }}
                      className="cal-upcoming-row"
                    >
                      <div style={{ fontSize: "20px", flexShrink: 0 }}>{TYPE_EMOJI[ev.event_type] || "📋"}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "13px", fontWeight: "700", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {ev.title}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-tertiary)", marginTop: "2px" }}>
                          📍 {ev.corridor} · 🕐 {ev.time} · {ev.duration_hours}h
                        </div>
                      </div>
                      <div style={{ textAlign: "right", flexShrink: 0 }}>
                        <div style={{ fontSize: "12px", fontWeight: "700", color: IMPACT_COLOR[ev.impact], marginBottom: "2px" }}>
                          {countdown}
                        </div>
                        <div style={{ fontSize: "10px", color: "var(--text-tertiary)" }}>
                          {d.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Schedule Modal ──────────────────────────────────────────────────────── */}
      {showModal && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
          zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center",
          backdropFilter: "blur(4px)", animation: "fadeIn 0.2s ease-out",
        }} onClick={(e) => e.target === e.currentTarget && setShowModal(false)}>
          <div style={{
            background: "var(--card-bg)", border: "1px solid var(--border)",
            borderRadius: "16px", padding: "28px", width: "520px", maxHeight: "90vh",
            overflowY: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
            animation: "slideUp 0.25s cubic-bezier(0.22,1,0.36,1)",
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
                  className="form-select"
                />
              </div>

              {/* Event Type + Impact */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Event Type</label>
                  <select value={form.event_type} onChange={e => setForm(p => ({...p, event_type: e.target.value}))} className="form-select">
                    {EVENT_TYPES.map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Traffic Impact</label>
                  <select value={form.impact} onChange={e => setForm(p => ({...p, impact: e.target.value}))} className="form-select">
                    <option>Low</option>
                    <option>Medium</option>
                    <option>High</option>
                  </select>
                </div>
              </div>

              {/* Corridor */}
              <div>
                <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Affected Corridor</label>
                <select value={form.corridor} onChange={e => setForm(p => ({...p, corridor: e.target.value}))} className="form-select">
                  {CORRIDORS.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>

              {/* Date + Time + Duration */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Date *</label>
                  <input type="date" value={form.date} onChange={e => setForm(p => ({...p, date: e.target.value}))} className="form-select" />
                </div>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Time</label>
                  <input type="time" value={form.time} onChange={e => setForm(p => ({...p, time: e.target.value}))} className="form-select" />
                </div>
                <div>
                  <label style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>Duration (hrs)</label>
                  <input type="number" min="0.5" step="0.5" value={form.duration_hours} onChange={e => setForm(p => ({...p, duration_hours: e.target.value}))} className="form-select" />
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
                  className="form-select"
                  style={{ resize: "vertical", fontFamily: "inherit" }}
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
                  cursor: submitting ? "not-allowed" : "pointer", marginTop: "4px",
                  boxShadow: submitting ? "none" : "0 4px 14px rgba(59,130,246,0.3)",
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

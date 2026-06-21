import React, { useState, useEffect, useCallback } from "react";
import LiveMap from "./components/LiveMap";
import AICommand from "./components/AICommand";
import Diversion from "./components/Diversion";
import Analytics from "./components/Analytics";
import FutureRisk from "./components/FutureRisk";
import EventCalendar from "./components/EventCalendar";
import ShiftReport from "./components/ShiftReport";
import PotholeTracker from "./components/PotholeTracker";

const BACKEND_URL = import.meta.env.VITE_API_URL || "";

// ── Toast Notification System ───────────────────────────────────────────
function ToastContainer({ toasts }) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.exiting ? "toast-exit" : ""}`}>
          <span className="toast-icon">{t.icon}</span>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}

// Navigation items
const NAV_ITEMS = [
  { icon: "🗺", label: "Live Monitor", id: 0 },
  { icon: "🔮", label: "AI Command Predictor", id: 1 },
  { icon: "🔀", label: "Diversion Suggestion", id: 2 },
  { icon: "📊", label: "Analytics Dashboard", id: 3 },
  { icon: "⚡", label: "Future Risk View", id: 4 },
  { icon: "📅", label: "Event Calendar", id: 5 },
  { icon: "📋", label: "Shift Report", id: 6 },
  { icon: "🕳️", label: "Pothole Tracker", id: 7 },
];

export default function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({
    total_incidents: 0,
    active_incidents: 0,
    high_priority_active: 0,
    road_closures_active: 0
  });

  const [availableCorridors, setAvailableCorridors] = useState([]);
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("bengaluruops-theme") === "dark";
  });

  // Toast state
  const [toasts, setToasts] = useState([]);
  const addToast = useCallback((icon, message) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, icon, message, exiting: false }]);
    setTimeout(() => {
      setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 250);
    }, 3500);
  }, []);

  // Apply dark mode
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    localStorage.setItem("bengaluruops-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  // Classifier inputs state
  const [classifierInputs, setClassifierInputs] = useState({
    event_cause: "vehicle_breakdown",
    corridor: "Tumkur Road",
    veh_type: "N/A",
    hour: 9,
    weekday: 0,
    event_type: "unplanned"
  });

  // Prediction states
  const [classificationResult, setClassificationResult] = useState(null);
  const [durationResult, setDurationResult] = useState(null);
  const [manpowerResult, setManpowerResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch function (reusable for scan refresh)
  const fetchData = useCallback(async () => {
    try {
      const [statsRes, eventsRes, corridorsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/incidents/summary`),
        fetch(`${BACKEND_URL}/api/incidents?status=active&page_size=1000`),
        fetch(`${BACKEND_URL}/api/analytics/metadata/corridors`)
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (eventsRes.ok) {
        const eventsData = await eventsRes.json();
        setEvents(eventsData.events || []);
      }

      if (corridorsRes.ok) {
        const corridorsData = await corridorsRes.json();
        setAvailableCorridors(corridorsData);
      }
    } catch (err) {
      console.error("Error fetching live map details:", err);
    }
  }, []);

  // Fetch KPI statistics and active events on load and poll every 10s
  useEffect(() => {
    fetchData();
    runAIPipeline();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleClassifierChange = (key, value) => {
    setClassifierInputs(prev => ({
      ...prev,
      [key]: value
    }));
  };

  // Centralized model pipeline execution
  const runAIPipeline = async (overrideInputs = null) => {
    setLoading(true);
    const inputs = overrideInputs || classifierInputs;
    
    try {
      // 1. Classification (Priority & Closure)
      const classRes = await fetch(`${BACKEND_URL}/api/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_cause: inputs.event_cause,
          corridor: inputs.corridor,
          zone: "Unknown",
          veh_type: inputs.veh_type,
          hour: inputs.hour,
          weekday: inputs.weekday,
          event_type: inputs.event_type
        })
      });

      let priorityVal = "Low";
      let closureVal = false;
      let classData = null;

      if (classRes.ok) {
        classData = await classRes.json();
        setClassificationResult(classData);
        priorityVal = classData.priority;
        closureVal = classData.requires_closure;
      }

      // 2. Duration prediction
      const durRes = await fetch(`${BACKEND_URL}/api/duration`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_cause: inputs.event_cause,
          corridor: inputs.corridor,
          zone: "Unknown",
          veh_type: inputs.veh_type,
          hour: inputs.hour,
          weekday: inputs.weekday,
          event_type: inputs.event_type
        })
      });

      let durationMinutes = 45;
      let durData = null;
      if (durRes.ok) {
        durData = await durRes.json();
        setDurationResult(durData);
        durationMinutes = durData.estimated_minutes;
      }

      // 3. Manpower recommendations
      const manRes = await fetch(`${BACKEND_URL}/api/manpower`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          priority: priorityVal,
          requires_closure: closureVal,
          corridor: inputs.corridor,
          duration_bucket: durData?.bucket || "Medium",
          veh_type: inputs.veh_type,
        })
      });

      if (manRes.ok) {
        const manData = await manRes.json();
        setManpowerResult(manData);
      }

    } catch (err) {
      console.error("Error executing A.I. prediction pipeline:", err);
      addToast("⚠️", "AI Pipeline failed. Check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  // Pre-fills and automatically executes the pipeline from active incident card trigger
  const runAIForIncident = async (id) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/incidents/${id}`);
      if (res.ok) {
        const incident = await res.json();
        
        // Match Cause options
        let causeVal = incident.event_cause || "vehicle_breakdown";
        const validCauses = ["vehicle_breakdown", "accident", "construction", "water_logging", "vip_movement", "public_event", "pot_holes", "tree_fall", "Stationary Traffic", "Jam", "Queueing Traffic", "abandoned_vehicle", "oil_spill", "pedestrian_incident", "others"];
        if (!validCauses.includes(causeVal)) causeVal = "vehicle_breakdown";

        // Match Corridor options — use live corridors from API, fall back to a safe default
        let corridorVal = incident.corridor || "Non-corridor";
        if (availableCorridors.length > 0 && !availableCorridors.includes(corridorVal)) {
          corridorVal = "Non-corridor";
        }

        // Match Vehicle Type options
        let vehVal = incident.veh_type || "N/A";
        const validVehs = ["heavy_vehicle", "lcv", "private_car", "bus", "two_wheeler", "N/A"];
        if (!validVehs.includes(vehVal)) vehVal = "N/A";

        // Map hour bucket
        const hr = incident.hour || 9;
        let timeVal = 9;
        if (hr >= 5 && hr <= 7) timeVal = 6;
        else if (hr >= 8 && hr <= 10) timeVal = 9;
        else if (hr >= 12 && hr <= 14) timeVal = 13;
        else if (hr >= 17 && hr <= 20) timeVal = 18;
        else if (hr >= 21 && hr <= 23) timeVal = 22;

        const newInputs = {
          event_cause: causeVal,
          corridor: corridorVal,
          veh_type: vehVal,
          hour: timeVal,
          weekday: incident.weekday !== null ? incident.weekday : 0,
          event_type: incident.event_type || "unplanned"
        };

        setClassifierInputs(newInputs);
        setActiveTab(1); // Switch to AI Predictor tab
        addToast("🔮", `AI analyzing: ${causeVal.replace(/_/g, " ")} on ${corridorVal}`);
        runAIPipeline(newInputs); // trigger pipeline
      }
    } catch (err) {
      console.error("Error loading incident attributes:", err);
    }
  };

  return (
    <div className="app-container">
      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} />

      {/* Left Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div className="logo-text">
              Bengaluru<span className="logo-accent">Ops</span>
            </div>
            <button
              className="theme-toggle"
              onClick={() => setDarkMode(!darkMode)}
              title={darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {darkMode ? "☀️" : "🌙"}
            </button>
          </div>
          <span style={{ fontSize: "10px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            AI Traffic Command Center
          </span>
        </div>

        <nav>
          <ul className="sidebar-menu">
            {NAV_ITEMS.map((item) => (
              <li key={item.id}>
                <button
                  className={`sidebar-link ${activeTab === item.id ? "active" : ""}`}
                  onClick={() => setActiveTab(item.id)}
                >
                  <span style={{ fontSize: "15px" }}>{item.icon}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div>Status: <span style={{ color: "var(--green)", fontWeight: "700" }}>● ONLINE</span></div>
          <div>BTP Operations v2.0</div>
          <div>© Bengaluru Traffic Police</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {/* Header section */}
        <header className="page-header">
          <div>
            <span style={{ fontSize: "10px", textTransform: "uppercase", color: "var(--text-tertiary)", fontWeight: "700", letterSpacing: "0.05em" }}>
              Active Session Command
            </span>
            <h1 style={{ fontSize: "20px", fontWeight: "800", color: "var(--text-primary)", marginTop: "2px" }}>
              Congestion Operations Dashboard
            </h1>
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className="badge badge-green">
              <span className="live-dot" style={{ width: "6px", height: "6px", margin: 0, marginRight: "4px" }}></span> Active Node
            </span>
            <span className="badge badge-blue">
              Bengaluru City
            </span>
          </div>
        </header>

        {/* KPI Counters Bar */}
        <div className="grid4" style={{ marginBottom: "24px" }}>
          <div className="card kpi-card kpi-total">
            <div className="metric-val" key={stats.total_incidents}>{stats.total_incidents.toLocaleString()}</div>
            <div className="metric-lbl">Total database incidents</div>
          </div>
          <div className="card kpi-card kpi-active">
            <div className="metric-val" style={{ color: "var(--amber)" }} key={stats.active_incidents}>{stats.active_incidents}</div>
            <div className="metric-lbl">Active congestion alerts</div>
          </div>
          <div className="card kpi-card kpi-high">
            <div className="metric-val" style={{ color: "var(--red)" }} key={stats.high_priority_active}>{stats.high_priority_active}</div>
            <div className="metric-lbl">High priority dispatch</div>
          </div>
          <div className="card kpi-card kpi-closure">
            <div className="metric-val" style={{ color: "var(--blue)" }} key={stats.road_closures_active}>{stats.road_closures_active}</div>
            <div className="metric-lbl">Active road closures</div>
          </div>
        </div>

        {/* Screen Switcher */}
        {activeTab === 0 && <LiveMap events={events} onRunAI={runAIForIncident} onScanComplete={fetchData} addToast={addToast} />}
        {activeTab === 1 && (
          <AICommand
            inputs={classifierInputs}
            onChange={handleClassifierChange}
            onClassify={() => runAIPipeline()}
            classResult={classificationResult}
            durResult={durationResult}
            manResult={manpowerResult}
            loading={loading}
            availableCorridors={availableCorridors}
          />
        )}
        {activeTab === 2 && <Diversion availableCorridors={availableCorridors} />}
        {activeTab === 3 && <Analytics stats={stats} />}
        {activeTab === 4 && <FutureRisk />}
        {activeTab === 5 && <EventCalendar />}
        {activeTab === 6 && <ShiftReport addToast={addToast} />}
        {activeTab === 7 && <PotholeTracker addToast={addToast} />}
      </main>
    </div>
  );
}

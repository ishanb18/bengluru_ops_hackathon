import React, { useState, useEffect } from "react";
import LiveMap from "./components/LiveMap";
import AICommand from "./components/AICommand";
import Diversion from "./components/Diversion";
import Analytics from "./components/Analytics";

const BACKEND_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [activeTab, setActiveTab] = useState(0); // 0: Live Monitor, 1: AI Predictor, 2: Diversions, 3: Analytics
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({
    total_incidents: 0,
    active_incidents: 0,
    high_priority_active: 0,
    road_closures_active: 0
  });

  const [availableCorridors, setAvailableCorridors] = useState([]);

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

  // Fetch KPI statistics and active events on load and poll every 10s
  useEffect(() => {
    async function fetchData() {
      try {
        const [statsRes, eventsRes, corridorsRes] = await Promise.all([
          fetch(`${BACKEND_URL}/api/incidents/summary`),
          fetch(`${BACKEND_URL}/api/incidents?status=active`),
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
    }

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
        const validCauses = ["vehicle_breakdown", "accident", "construction", "water_logging", "vip_movement", "public_event", "pot_holes", "tree_fall", "others"];
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
        runAIPipeline(newInputs); // trigger pipeline
      }
    } catch (err) {
      console.error("Error loading incident attributes:", err);
    }
  };

  return (
    <div className="app-container">
      {/* Left Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <div className="logo-text">
            Bengaluru<span className="logo-accent">Ops</span>
          </div>
          <span style={{ fontSize: "10px", fontWeight: "700", color: "var(--text-tertiary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Traffic Command Center
          </span>
        </div>

        <nav>
          <ul className="sidebar-menu">
            <li>
              <button className={`sidebar-link ${activeTab === 0 ? "active" : ""}`} onClick={() => setActiveTab(0)}>
                🗺 Live Monitor
              </button>
            </li>
            <li>
              <button className={`sidebar-link ${activeTab === 1 ? "active" : ""}`} onClick={() => setActiveTab(1)}>
                🔮 AI Command Predictor
              </button>
            </li>
            <li>
              <button className={`sidebar-link ${activeTab === 2 ? "active" : ""}`} onClick={() => setActiveTab(2)}>
                🔀 Diversion Suggestion
              </button>
            </li>
            <li>
              <button className={`sidebar-link ${activeTab === 3 ? "active" : ""}`} onClick={() => setActiveTab(3)}>
                📊 Analytics Dashboard
              </button>
            </li>
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div>Status: <span style={{ color: "var(--green)", fontWeight: "700" }}>● ONLINE</span></div>
          <div>BTP Operations DB v1.2</div>
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
          <div className="card">
            <div className="metric-val">{stats.total_incidents}</div>
            <div className="metric-lbl">Total database incidents</div>
          </div>
          <div className="card">
            <div className="metric-val" style={{ color: "var(--amber)" }}>{stats.active_incidents}</div>
            <div className="metric-lbl">Active congestion alerts</div>
          </div>
          <div className="card">
            <div className="metric-val" style={{ color: "var(--red)" }}>{stats.high_priority_active}</div>
            <div className="metric-lbl">High priority dispatch</div>
          </div>
          <div className="card">
            <div className="metric-val" style={{ color: "var(--blue)" }}>{stats.road_closures_active}</div>
            <div className="metric-lbl">Active road closures</div>
          </div>
        </div>

        {/* Screen Switcher */}
        {activeTab === 0 && <LiveMap events={events} onRunAI={runAIForIncident} />}
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
        {activeTab === 3 && <Analytics />}
      </main>
    </div>
  );
}

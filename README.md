# 🚦 BengaluruOps 2.0 — AI Traffic Command Center

BengaluruOps is a next-generation AI traffic command center built for the Bengaluru Traffic Police. It fuses real-time TomTom network congestion data with machine learning models to dynamically forecast road risks, recommend manpower deployments, verify incidents using LLM Web Search, and intelligently reroute traffic during major bottlenecks.

---

## 🌟 Key Features
- **Live Incident Mapping**: Visualizes active crashes, breakdowns, and hazards on an interactive CARTO map.
- **Future Risk Forecasting**: Polls real-time speeds and calculates 30-min and 60-min predictive congestion models.
- **AI Command Predictor**: Uses trained ML classification to dynamically cap confidence scores and allocate traffic units.
- **Tavily Web Verification**: Employs an LLM Agent + Tavily REST API to automatically search the web for context on an incident.
- **Automated Routing API**: Suggests the fastest diversions around blockages using the TomTom Routing Engine.

---

## 💻 Tech Stack
- **Frontend**: React (Vite), CSS3 (Dark/Light themes), Leaflet (Maps)
- **Backend**: FastAPI, Python 3.11+, SQLite (Hybrid state management)
- **Machine Learning**: XGBoost, Scikit-Learn, SHAP (Explainability)
- **External APIs**: TomTom (Incidents/Flow/Routing), OpenWeather (Rain factors), Groq (LLM Inference), Tavily (Web Search)

---

## ⚙️ Prerequisites & Installation

To run this application locally, you will need **Python 3.11+** and **Node.js (v18+)** installed.

### 1. Clone the Repository
```bash
git clone https://github.com/ishanb18/bengluru_ops_hackathon.git
cd bengluru_ops_hackathon
```

### 2. Backend Setup (FastAPI)
Open a terminal and navigate to the `backend` directory:
```bash
cd backend

# Create a virtual environment (Optional but recommended)
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On Mac/Linux

# Install all python dependencies
pip install -r requirements.txt
```

**Set up Backend Environment Variables:**
Create a `.env` file in the `backend` directory (i.e. `backend/.env`) and add the following API keys:
```env
TOMTOM_API_KEY=your_primary_tomtom_key
TOMTOM_API_KEY_FALLBACK=your_backup_tomtom_key
GROQ_API_KEY=your_groq_llm_key
OPENWEATHER_API_KEY=your_openweather_key
```

### 3. Frontend Setup (React/Vite)
Open a new terminal and navigate to the `frontend` directory:
```bash
cd frontend

# Install Node modules
npm install
```

**Set up Frontend Environment Variables:**
Create a `.env` file in the `frontend` directory (i.e. `frontend/.env`) to map the API to the backend:
```env
VITE_API_URL=http://127.0.0.1:8000
```
*(Note: We use `127.0.0.1` instead of `localhost` to prevent IPv6 resolution errors in certain browsers).*

---

## 🚀 Running the Application

You will need to run the backend and the frontend simultaneously in two separate terminals.

### Start the Backend
In your `backend` terminal, start the FastAPI Uvicorn server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*(The backend will automatically create the SQLite database, seed it with historical data, load the ML models, and start the background weather/traffic collectors).*

### Start the Frontend
In your `frontend` terminal, start the Vite development server:
```bash
npm run dev
```

### Access the App
Open your browser and navigate to:
👉 **http://localhost:5173**

---

## 📌 Usage Guide
1. **Live Monitor:** The map initializes with the default state. Click the **"🔍 Scan Live Anomalies"** button to fetch the latest incidents from TomTom.
2. **AI Command Predictor:** Click **"🔮 AI Recommendation"** on any map incident to load it into the predictor. The Groq LLM will automatically run a web search using Tavily to verify the event.
3. **Future Risk View:** Click **"🔄 Refresh Forecast"** to instantly poll live speeds across Bengaluru and update the predictive grid.
4. **Dark Mode:** Use the ☀️/🌙 toggle in the top left of the sidebar to switch between light and dark themes.

---

## 📜 License
This project was built for the Flipkart GRiD 6.0 Hackathon. 

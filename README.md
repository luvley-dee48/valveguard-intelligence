# ValveGuard Intelligence

AI-assisted condition monitoring and predictive maintenance for industrial control valves.

> **Note:** Items marked `TODO` are details only you can confirm (team name, screenshots, live URL). Everything else is based on the project's actual code structure and API.

---

## 1. Problem Statement

Industrial plants (steam headers, feedwater lines, cooling loops, condensate and process lines) depend on hundreds of control valves. When a valve degrades, the symptoms are subtle at first: the actuator responds more slowly, the positioner falls behind its command signal, vibration creeps up. Today these problems are usually found in one of two ways:

- **Run to failure.** The valve fails in service, causing unplanned downtime, safety risk, and expensive emergency repairs.
- **Calendar-based maintenance.** Valves are inspected on a fixed schedule whether they need it or not, which wastes technician time and still misses faults that develop between inspections.

Maintenance teams also drown in raw telemetry. A reading table does not tell an engineer *which valve to look at first* or *why*.

**ValveGuard Intelligence** turns valve telemetry into prioritised, explainable maintenance decisions:

- Ingests readings per valve (position, command, pressure, temperature, vibration, response time).
- Computes health scores, findings, and alerts with a transparent rules pipeline.
- Predicts degradation for each valve.
- Uses an AI model (Google Gemini API) to write plain-language investigation reports that a maintenance engineer can review, accept, or reject.
- Logs every AI call so the AI's real contribution is auditable.

---

## 2. Key Features

| Area | What it does |
|---|---|
| **Fleet Overview** | Fleet-wide health summary, priorities, and a one-click **Load demo fleet** |
| **Valve registry** | Create, view, update, and delete valves per organisation |
| **Telemetry** | Post and query readings per valve |
| **Prediction** | Degradation prediction per valve (`/api/valves/{id}/prediction`) |
| **Alerts** | Computed and manual alerts with status management |
| **AI investigation reports** | Gemini-written reports per valve, with a human review step |
| **Audit trail** | `/api/activity` and `/api/system/ai-calls` record what happened and what the AI contributed |
| **Auth** | Email signup and login, optional Google sign-in, and a no-signup demo session |
| **Demo fleet** | 21 simulated valves (V-101 to V-121); a few (e.g. V-107, V-113) are deliberately degrading so the pipeline has real faults to find |

Only telemetry is simulated. Priorities, findings, health, and alerts are computed by the same rules (`app/analytics.py`) used for live data, so the demo exercises the real pipeline.

---

## 3. Tech Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2, Uvicorn, PyJWT
- **Database:** SQLite (tables are created automatically on startup)
- **AI:** Google Gemini API (`app/gemini.py`, `app/ai.py`)
- **Frontend:** Vite 8 + TypeScript (dev server on port 8080, proxies `/api` to the backend)
- **Tests:** pytest

---

## 4. Project Structure

```
valveguard-intelligence/
├── app/
│   ├── main.py        # FastAPI app + startup
│   ├── api.py         # valves, readings, reports, alerts, fleet routes
│   ├── analytics.py   # health scores, findings, priorities, predictions
│   ├── ai.py          # AI report generation + rate limiting
│   ├── gemini.py      # Gemini client
│   ├── auth.py        # signup, login, Google sign-in, JWT
│   ├── demo.py        # demo session + AI status
│   ├── seed.py        # simulated demo fleet
│   ├── system.py      # system status, tables, requests, AI-call log
│   ├── db.py          # SQLAlchemy models
│   └── config.py      # environment configuration
├── src/               # frontend source
├── run.sh             # starts the backend
├── requirements.txt   # Python dependencies
├── package.json       # frontend dependencies and scripts
├── vite.config.ts     # frontend config + /api proxy
└── .env               # local secrets (never commit)
```

---

## 5. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | **3.10 or newer** | `python3 --version` |
| Node.js | **20.19+ or 22.12+** (needed by Vite 8) | `node -v` |
| npm | comes with Node | `npm -v` |
| Git | any recent | `git --version` |

On Ubuntu / WSL, install Python venv support if needed:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
```

---

## 6. Setup

### 6.1 Clone

```bash
git clone https://github.com/luvley-dee48/valveguard-intelligence.git
cd valveguard-intelligence
```

### 6.2 Backend environment

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
python --version                   # must be 3.10 or newer
pip install --upgrade pip
pip install -r requirements.txt
```

### 6.3 Configure `.env`

```bash
cp .env.example .env
```

Generate a real secret key and put it in `.env`:

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

Then edit `.env`:

```env
# Required. Must be long and random. Placeholders are rejected at startup.
# Leave empty to auto-generate a new key on every restart.
SECRET_KEY=paste_the_generated_value_here

# Optional: enables the AI investigation features
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_model_name
```

Get a free Gemini API key from Google AI Studio. **Never commit `.env` or share your keys.**

> If `SECRET_KEY` is a placeholder or too short, the backend refuses to start with:
> `RuntimeError: SECRET_KEY is a placeholder or too short.`

### 6.4 Frontend dependencies

```bash
npm install
```

---

## 7. Running the Application

You need **two terminals**, one for the backend and one for the frontend.

### Terminal 1: Backend (port 8000)

```bash
cd valveguard-intelligence
source .venv/bin/activate
bash run.sh
```

Expected output:

```
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```

The database tables are created automatically on first start.

### Terminal 2: Frontend (port 8080)

```bash
cd valveguard-intelligence
npm run dev
```

Expected output:

```
VITE v8.x ready
➜  Local:   http://localhost:8080/
```

### Open the app

**http://localhost:8080**

The frontend proxies every `/api/...` request to the backend at `127.0.0.1:8000`. If the backend is not running, the Vite terminal shows `ECONNREFUSED 127.0.0.1:8000`.

> Port 8000 serves **only** `/api/...` routes. Opening `http://127.0.0.1:8000/` in a browser returns `{"detail":"Not Found"}`, which is normal.

---

## 8. Loading the Demo Data

There is no separate seed command. The seeder (`app/seed.py`) runs when you load the demo fleet.

**From the UI**

1. Open http://localhost:8080
2. Start the demo session from the landing page (or sign up / log in).
3. Go to **Fleet Overview** and click **Load demo fleet**.

This creates valves V-101 to V-121 with 24 readings each (12 hours, every 30 minutes), plus computed health, findings, and alerts.

**From the terminal (optional)**

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/demo/session \
  | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('token') or d.get('access_token') or d)")

curl -s -X POST http://127.0.0.1:8000/api/fleet/demo -H "Authorization: Bearer $TOKEN"
curl -s http://127.0.0.1:8000/api/valves -H "Authorization: Bearer $TOKEN"
```

---

## 9. Checking the AI Investigation (Gemini)

The AI features need `GEMINI_API_KEY` in `.env`. Without it the app still works, and AI features report "not configured".

### Step 1: Confirm the backend and AI configuration

Open in a browser (note the **single** slash after the port):

```
http://127.0.0.1:8000/api/health
```

Expected when AI is set up:

```json
{ "status": "ok", "ai": { "configured": true }, "google_client_id": null }
```

If you see `"configured": false`, the key is missing or not loaded. Check `.env` and restart `bash run.sh`.

### Step 2: Check AI status

```
http://127.0.0.1:8000/api/demo/ai-status
```

or

```bash
curl http://127.0.0.1:8000/api/demo/ai-status
```

### Step 3: Run the AI self-test

This sends a test request to the model and confirms it responds.

```bash
curl -X POST http://127.0.0.1:8000/api/system/ai-selftest \
  -H "Authorization: Bearer $TOKEN"
```

### Step 4: Generate an investigation report for a valve

Pick a valve ID from `GET /api/valves`, then:

```bash
# Degradation prediction
curl http://127.0.0.1:8000/api/valves/VALVE_ID/prediction \
  -H "Authorization: Bearer $TOKEN"

# AI-written investigation report
curl -X POST http://127.0.0.1:8000/api/valves/VALVE_ID/reports \
  -H "Authorization: Bearer $TOKEN"

# Review it
curl http://127.0.0.1:8000/api/reports -H "Authorization: Bearer $TOKEN"
```

The seeded valves **V-107** (slowing actuator) and **V-113** (positioner losing control) are the best ones to investigate, since they contain deliberate faults.

### Step 5: Audit what the AI did

```bash
curl http://127.0.0.1:8000/api/system/ai-calls -H "Authorization: Bearer $TOKEN"
```

Every model call (or fallback) is logged here, so the AI's real contribution is auditable.

### Interactive testing

FastAPI provides a built-in API explorer where you can run every endpoint from the browser:

```
http://127.0.0.1:8000/docs
```

Click **Authorize**, paste the token from `/api/demo/session`, and try any route.

---

## 10. API Reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health + AI configuration |
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Log in |
| POST | `/api/auth/google` | Google sign-in |
| GET / PATCH | `/api/auth/me` | Current user |
| GET | `/api/demo/ai-status` | AI availability |
| POST | `/api/demo/session` | Start a demo session |
| GET / POST | `/api/valves` | List / create valves |
| GET / PATCH / DELETE | `/api/valves/{valve_id}` | Valve detail |
| GET / POST | `/api/valves/{valve_id}/readings` | Telemetry |
| GET | `/api/valves/{valve_id}/prediction` | Degradation prediction |
| POST | `/api/valves/{valve_id}/reports` | Generate AI report |
| GET | `/api/reports`, `/api/reports/{id}` | Reports |
| POST | `/api/reports/{id}/review` | Human review |
| GET / POST | `/api/alerts` | Alerts |
| PATCH / DELETE | `/api/alerts/{alert_id}` | Alert management |
| GET / PATCH | `/api/settings` | Org settings |
| GET | `/api/fleet/overview` | Fleet summary |
| POST | `/api/fleet/demo` | Load demo fleet |
| GET | `/api/activity` | Activity log |
| GET | `/api/system/status` | System status |
| GET | `/api/system/tables/{name}` | Inspect a table |
| GET | `/api/system/requests` | Request log |
| GET | `/api/system/ai-calls` | AI call audit log |
| POST | `/api/system/ai-selftest` | AI self-test |

---

## 11. Running Tests

```bash
source .venv/bin/activate
pytest
```

---

## 12. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Python 3.10 or newer is required` | Your venv uses an older Python. Delete `.venv`, recreate with `/usr/bin/python3 -m venv .venv` (Ubuntu 22.04 ships 3.10). |
| `SECRET_KEY is a placeholder or too short` | Set `SECRET_KEY` in `.env` to a long random value (section 6.3). |
| Vite shows `ECONNREFUSED 127.0.0.1:8000` | Backend isn't running. Start it with `bash run.sh`. |
| `{"detail":"Not Found"}` in the browser | Double slash (`8000//api/...`), a missing `/api` prefix, or opening a POST route in the address bar. Use `http://127.0.0.1:8000/api/health`. |
| `styleText is not exported from node:util` | Node is too old. Upgrade to 20.19+ or 22.12+, then `rm -rf node_modules && npm install`. |
| `"ai": {"configured": false}` | `GEMINI_API_KEY` is missing in `.env`. Add it and restart the backend. |
| Empty Fleet Overview | Click **Load demo fleet**, or call `POST /api/fleet/demo`. |
| 401 Unauthorized | Session expired. Start a new demo session. |
| `vite-tsconfig-paths` warning | Harmless. Optionally replace the plugin with `resolve.tsconfigPaths: true`. |

---

## 13. Security Notes

- Keep `.env` out of version control (confirm it is in `.gitignore`).
- Never paste API keys or `SECRET_KEY` values in chats, screenshots, or issues. Rotate any that were exposed.
- Use a fixed `SECRET_KEY` in production so user sessions survive restarts.

---

## 14. Team and License

- **Author:** `TODO`
- **License:** `TODO`
- **Live demo:** `TODO`
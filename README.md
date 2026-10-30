# Nexora: AI Industrial Intelligence Platform

A fleet-monitoring dashboard with a Python backend, a real database, login/sign-up, and
Gemma 4 (through the Gemini API) used for one specific job: explaining sensor anomalies.

- **Frontend:** plain HTML/CSS/JS in `frontend/` (no build step), served by the backend.
- **Backend:** FastAPI + SQLAlchemy in `app/`. SQLite by default; any SQLAlchemy URL works.
- **Auth:** sign up / log in, PBKDF2 password hashes, JWT bearer tokens. The first account is `admin`.

## Verify it yourself (System check page)

Log in, then open **System check** in the sidebar. Every item is live from the running server:

1. **Login and accounts**: who you are, token lifetime, how passwords are stored, and a view of the `users` table (admin only, never shows hashes).
2. **Database and seeded data**: every table created by `app/db.py` with row counts and a "View rows" button. Demo rows come from `app/seed.py`.
3. **POST / PUT / PATCH / DELETE**: "Run live CRUD test" creates a temporary asset, reads it, replaces it, edits one field (which raises an alert by rule), deletes it, and shows each real request, status code and result.
4. **Live API requests**: what the server actually received from the browser (tick "Changes only" to hide GETs).
5. **Gemma 4**: exact model identifier, endpoint, the code path, a "Run live Gemma 4 test" button (shows the prompt, the raw model reply, the model name the API reports, and latency) and the `ai_calls` history.

## Gemma 4 proof

| Question | Answer |
|---|---|
| Exact model | `gemma-4-26b-a4b-it` (set in `app/config.py` / `.env` as `GEMINI_MODEL`; `gemma-4-31b-it` also works) |
| Where it is called | `app/ai.py` `_call_gemini()` posts to `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent` |
| What triggers it | **Alerts > Analyze with AI** (`POST /api/alerts/{id}/analyze`) and **AI Insights > Generate insights** (`POST /api/insights/generate`) |
| What it contributes | A structured diagnosis (probable cause, failure mode, urgency, confidence, next checks, uncertainty) for the asset, shown on the alert and turned into insight cards |
| What the app does without it | Falls back to `rule_based()` and says so in the UI: the card reads "Rule-based diagnosis" and the call is logged with `source = rules` and the reason |
| Human control | Output is stored as *pending review*. A person must approve or reject it. The model cannot raise alerts, change severity, create work orders or touch equipment |
| Output safety | Strict schema validation (`Diagnosis`), shown only as escaped text, asset names sanitised before they enter the prompt, 30 calls per user per hour |
| Evidence | The `ai_calls` table and the System check page record model, API-reported `modelVersion`, latency and errors for every call |
| Without a key | `GEMINI_API_KEY` empty means the server prints `Gemma 4 inference: DISABLED` at startup and every AI card is labelled as rule-based. It never pretends |

Using a Gemini-branded model name instead of a Gemma 4 id would make the System page show a red "Not a Gemma 4 model" chip.

## Run it

```bash
bash run.sh                     # Linux / WSL / Mac: makes .venv, installs, copies .env, starts the server
# or by hand:
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env ; then add GEMINI_API_KEY
uvicorn app.main:app --reload   # open http://localhost:8000  (Python 3.10+ required)
python -m pytest                # backend tests
```

**Always open `http://localhost:8000` from the running server.** Double-clicking an `index.html` file shows a page with no backend, no login and no data.

The database file (`nexora.db`) and 12 demo assets are created on first start.
Set `SEED_DEMO_DATA=false` for an empty production database. Interactive API docs: `/docs`.

## What the AI does, and what it does not

**Task that benefits from AI.** Turning a handful of sensor numbers (vibration, temperature,
trend, health score) into a short plain-language diagnosis: probable cause, urgency, and the
next inspection steps. Reading across signals and wording a caveat is where a language model
helps; picking a threshold is not.

**What stays conventional (no model):** health scores, threshold alerts, de-duplication and
auto-clearing of alerts, the 72-hour failure-risk forecast (least-squares trend + normal CDF),
all CRUD, authentication, and which assets get diagnosed.

**Why an open model.** Gemma 4 weights are open, so the same prompt can later run on the plant's
own hardware if sensor data must not leave the site. This build uses the hosted Gemini API
(`gemma-4-26b-a4b-it`, or `gemma-4-31b-it`); local inference is a swap of `_call_gemini` in
`app/ai.py`.

**Human control.** The model never changes severity, opens alerts, creates work orders or
touches equipment. Each diagnosis is saved as *pending review*; a person must press
"Approve and draft work order" or "Reject" (`POST /api/alerts/{id}/analysis/review`).
Generated insights start as *pending* too. Model output is validated against a strict schema,
shown only as escaped text, and capped at 30 calls per user per hour.

**Failure path.** No API key, a network error, a bad reply or a schema mismatch all fall back to
the rule-based diagnosis, clearly labelled "Rule-based diagnosis" in the UI.

**Data sent to the hosted API:** asset tag, asset type and numeric readings only. No names,
emails or notes. Read the current Gemini API terms before use: unpaid services must not receive
sensitive, confidential or personal information, and there are age and permitted-use rules.
Do not send real plant data on the free tier unless you have checked you are allowed to.

## API (all except auth need `Authorization: Bearer <token>`)

| Resource | Methods |
|---|---|
| `/api/auth/signup`, `/login` | POST |
| `/api/auth/me` | GET, PATCH |
| `/api/assets`, `/api/assets/{id}` | GET, POST, PUT (replace), PATCH (partial), DELETE (admin) |
| `/api/assets/{id}/readings` | GET, POST (updates health, status and alerts) |
| `/api/assets/{id}/prediction` | GET |
| `/api/alerts`, `/api/alerts/{id}` | GET, POST, PUT, PATCH, DELETE |
| `/api/alerts/{id}/analyze`, `/analysis/review` | POST (AI diagnosis, human decision) |
| `/api/insights`, `/api/insights/{id}`, `/generate` | GET, POST, PATCH, DELETE |
| `/api/workflows`, `/api/workflows/{id}`, `/run` | GET, POST, PUT, PATCH, DELETE |
| `/api/integrations`, `/api/integrations/{id}` | GET, POST, PUT, PATCH, DELETE |
| `/api/settings` | GET, PUT, PATCH (admin) |
| `/api/metrics/{mtbf\|oee\|energy}` | GET, PUT (admin) |
| `/api/overview`, `/analytics/fleet`, `/activity`, `/reports/summary`, `/ai/status` | GET |

Every screen re-fetches from these endpoints after a change, so the UI always shows what is in the database.
Try it: on **Telemetry**, send a vibration reading above the alarm. The asset's health, status, an alert, the
activity feed and the overview KPIs all update; send a normal reading and the alert clears itself.

## Deploy (PrimeCloud or any container host)

```bash
docker build -t nexora .
docker run -p 8000:8000 -v nexora-data:/data \
  -e SECRET_KEY=... -e GEMINI_API_KEY=... -e SEED_DEMO_DATA=false nexora
```

On a platform that injects `PORT`, the container honours it. Put it behind HTTPS, set a strong
`SECRET_KEY`, and keep the volume mounted so the SQLite file persists. For more than one instance,
point `DATABASE_URL` at PostgreSQL (add the driver to `requirements.txt`). I could not test against
PrimeCloud itself, so check their current deploy steps for ports, volumes and environment variables.

## Known limits (be upfront about these in a demo)

- Seeded assets, alerts and insights are **demo data**. MTBF, OEE and energy are manual values
  (Settings, admin) until connected to a plant data source.
- Integrations are connection records only. Workflows record runs; they do not call Maximo, SAP or Slack.
- Login throttling and the AI rate limit are in memory, so they reset on restart and are per instance.
- Fonts and icons load from Google Fonts and cdnjs (Font Awesome), as in the original dashboard.
- Tokens live in `localStorage`; fine for a demo, consider httpOnly cookies for production.

# ValveGuard — evidence-backed valve maintenance intelligence

ValveGuard turns industrial valve telemetry into ranked, evidence-backed investigation reports.
Deterministic rules decide what is wrong. **Gemma 4, called through the Gemini API, is what drafts the
explanation a technician reads** — on screen, in the running product, not in a diagram.

- **Product:** React 19 + TanStack Start in `src/` (Vite, port 3000)
- **API:** FastAPI + SQLAlchemy in `app/` (port 8000). SQLite by default; any SQLAlchemy URL works.
- **Auth:** sign up / log in, PBKDF2 password hashes, JWT bearer tokens, every row scoped to an organisation.

## Where Gemma 4 actually runs

| Question | Answer |
|---|---|
| Exact model identifier | `gemma-4-26b-a4b-it` — the default `GEMINI_MODEL` in `app/config.py`; `gemma-4-31b-it` is the other hosted Gemma 4 size the API documents |
| HTTP endpoint | `POST https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent` with the `x-goog-api-key` header |
| Inference code | `app/ai.py`: `build_prompt()` → `_call_gemini()` → `_extract_json()` → `Diagnosis.model_validate()` |
| Trigger in the product | **/demo → Run Gemma 4 investigation** → `POST /api/valves/{id}/reports` → `create_report()` in `app/api.py` → `ai.diagnose()` |
| Contribution to the demo | The text of the report card: summary, 1–3 likely explanations with likelihood, recommended first action, next checks, data gaps, urgency and confidence. Saved as `pending` until a person accepts, rejects or asks for more data |
| What it never does | Decide what is flagged or compute health/priority (`app/analytics.py` does that), raise or clear alerts, change severity, order work, or touch equipment |
| Fallback | No key, timeout, HTTP error, non-JSON reply or schema mismatch → `rule_based()` answers, and the card is labelled **Rule-based fallback** with the reason (`no_api_key`, `HTTP 429: …`, `validation error`) |
| Audit | Every call *and* every fallback is written to the `ai_calls` table with model, the API-reported `modelVersion`, latency and error; shown on `/demo` and served by `GET /api/system/ai-calls` |

This is the hosted route in the MLH partner guidance — the Gemini API, not local inference — and a
`gemini-*` model id is never substituted for the Gemma 4 diagnosis.

## Run it (two processes, two terminals)

```bash
# terminal 1 — API
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # set GEMINI_API_KEY=... (leave empty to see the labelled fallback)
uvicorn app.main:app --reload --port 8000

# terminal 2 — product
npm install
npm run dev                                             # http://localhost:8080
```

Open **http://localhost:8080/demo** (use whatever port `npm run dev` prints if it differs — add
`-- --port 3000` to change it). The Vite dev server proxies `/api` to `127.0.0.1:8000`, so the
browser only talks to its own origin.

Both terminals must be running. If the API is not up, the page loads but the valve list shows a
connection error (`ECONNREFUSED 127.0.0.1:8000` in the Vite log) — start terminal 1.

Leave `SECRET_KEY` empty to let the app generate `.secret_key` on first run; startup rejects
placeholder values on purpose.

## What the demo does, step by step

1. `POST /api/demo/session` creates an isolated demo organisation and seeds the 20 simulated valves
   from `app/seed.py`. No sign-up form, and it is not special-cased later.
2. `GET /api/valves` returns the fleet with health, priority and findings computed by
   `app/analytics.py`. Three valves are flagged: V-113 (urgent), V-107 (inspect soon), V-121 (verify sensor).
3. **Run Gemma 4 investigation** posts `POST /api/valves/{id}/reports`. `build_evidence()` assembles the
   telemetry and the rule findings, then `app/ai.py` sends the prompt and validates the reply.
4. The report card shows the diagnosis plus a provenance chip — `gemma-4-26b-a4b-it · Gemini API`, or
   `Rule-based fallback` — and the call log below lists model, `modelVersion`, latency and error.
5. Accept / Needs more data / False positive posts `POST /api/reports/{id}/review` and is recorded with
   the reviewer's name.

The demo's readings are simulated. The database, the anomaly rules, the HTTP request to Google and the
stored audit rows are real.

## Verify

```bash
python -m pytest        # 17 backend tests, including the demo session and the model-call path
npx tsc --noEmit        # frontend types
npm run build           # production build
python tests/gemini.py  # with a key in .env: prints HTTP status, the reply and the modelVersion Google reports
```

The test suite runs without a key, so it asserts the labelled fallback; `test_gemini_report_is_stored_when_model_answers`
stubs `_call_gemini` to prove that a successful reply is stored with the model id.

## API

All routes except `/api/health` and `/api/demo/*` need `Authorization: Bearer <token>`.

| Resource | Methods |
|---|---|
| `/api/auth/signup`, `/api/auth/login`, `/api/auth/google`, `/api/auth/me` | POST, POST, POST, GET / PATCH |
| `/api/demo/session` | POST — public, isolated demo org + 20 valves |
| `/api/demo/ai-status` | GET — public, model id and endpoint; never the key |
| `/api/valves`, `/api/valves/{id}` | GET, POST / GET, PATCH, DELETE (admin) |
| `/api/valves/{id}/readings`, `/prediction` | GET, POST / GET |
| `/api/valves/{id}/reports` | POST — AI investigation |
| `/api/reports`, `/api/reports/{id}`, `/api/reports/{id}/review` | GET / GET / POST — human decision |
| `/api/alerts`, `/api/alerts/{id}` | GET, POST / PATCH, DELETE |
| `/api/settings` | GET, PATCH (admin) |
| `/api/fleet/overview`, `/api/fleet/demo`, `/api/activity` | GET, POST, GET |
| `/api/system/status`, `/tables/{name}`, `/requests`, `/ai-calls`, `/ai-selftest` | GET (ai-selftest: POST, admin) |

Interactive docs at `http://localhost:8000/docs`.

## Deploy

**API (container):**

```bash
docker build -t valveguard .
docker run -p 8000:8000 -v valveguard-data:/data \
  -e SECRET_KEY=... -e GEMINI_API_KEY=... valveguard
```

Mount the volume so `/data/valveguard.db` persists. On a platform that injects `PORT`, the container
honours it. For more than one instance, point `DATABASE_URL` at PostgreSQL and add the driver.

**Product:** `npm run build`, then serve the output. The `/api` proxy exists only in `vite dev`; in
production set `VITE_API_BASE` to the API origin and add that origin to `CORS_ORIGINS`.

## Known limits (worth saying in a demo)

- Readings are simulated. MTBF/OEE/energy metrics are not implemented.
- `/signup` and `/login` are still UI prototypes: they validate input but do not create accounts. The
  real auth endpoints exist and are exercised by the demo session and the tests.
- Every demo visit creates its own organisation; rows accumulate. Add pruning before public hosting.
- Login throttling, the AI rate limit (30 calls/user/hour) and demo-session throttling are in memory,
  so they reset on restart and are per instance.
- Integrations, workflows and report export are not built.
- Fonts and icons load from Google Fonts and cdnjs.
- Model output is advisory only. It does not certify safety or authorise repairs.

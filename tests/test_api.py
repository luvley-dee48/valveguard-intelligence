import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_CLIENT_ID"] = "test-client.apps.googleusercontent.com"
from fastapi.testclient import TestClient

from app.main import app


def client():
    return TestClient(app)


def signup(c, email="a@example.com", company="Acme Power"):
    r = c.post("/api/auth/signup", json={"name": "Alex Morgan", "email": email, "password": "supersecret1",
                                         "company": company})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}, r.json()["user"]


def with_demo(c, email="a@example.com"):
    h, user = signup(c, email)
    assert c.post("/api/fleet/demo", headers=h).status_code == 201
    return h, user


def by_tag(c, h):
    return {v["tag"]: v for v in c.get("/api/valves", headers=h).json()}


def test_auth_flow():
    with client() as c:
        assert c.get("/api/valves").status_code == 401
        h, user = signup(c)
        assert user["role"] == "admin" and user["org"]["name"] == "Acme Power" and user["org"]["plan"] == "free"
        assert c.post("/api/auth/signup", json={"name": "X Y", "email": "A@example.com", "password": "supersecret1"}).status_code == 409
        assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong"}).status_code == 401
        r = c.post("/api/auth/login", json={"email": "A@example.com", "password": "supersecret1"})
        assert r.status_code == 200 and r.json()["user"]["email"] == "a@example.com"
        assert c.get("/api/auth/me", headers={"Authorization": "Bearer " + r.json()["token"]}).json()["org"]["name"] == "Acme Power"
        assert c.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
        assert c.post("/api/auth/signup", json={"name": "Bo", "email": "bad", "password": "supersecret1"}).status_code == 422
        # every signup is the admin of its own organisation
        _, u2 = signup(c, "b@example.com", "Other Co")
        assert u2["role"] == "admin" and u2["org"]["id"] != user["org"]["id"]


def test_placeholder_secret_is_refused(monkeypatch):
    import importlib

    from app import config
    monkeypatch.setenv("SECRET_KEY", "change-me-to-a-long-random-string")
    try:
        importlib.reload(config)
        raise AssertionError("placeholder secret was accepted")
    except RuntimeError as e:
        assert "SECRET_KEY" in str(e)
    finally:
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough")
        importlib.reload(config)


def test_google_sign_in(monkeypatch):
    from app import auth
    claims = {"sub": "g-123", "email": "Gina@Example.com", "email_verified": True, "name": "Gina G"}
    monkeypatch.setattr(auth, "verify_google_token", lambda cred: claims)
    with client() as c:
        r = c.post("/api/auth/google", json={"credential": "x" * 30})
        assert r.status_code == 200 and r.json()["created"] is True
        assert r.json()["user"]["email"] == "gina@example.com" and r.json()["user"]["google_linked"]
        again = c.post("/api/auth/google", json={"credential": "x" * 30}).json()
        assert again["created"] is False and again["user"]["id"] == r.json()["user"]["id"]
        # a Google-only account has no password, so password login explains why
        assert c.post("/api/auth/login", json={"email": "gina@example.com", "password": "whatever1"}).status_code == 401
        # Google verifies the email, so it links to an existing password account
        signup(c, "pat@example.com")
        monkeypatch.setattr(auth, "verify_google_token", lambda cred: {**claims, "sub": "g-456", "email": "pat@example.com"})
        linked = c.post("/api/auth/google", json={"credential": "x" * 30}).json()
        assert linked["created"] is False and linked["user"]["email"] == "pat@example.com"
        # unverified Google emails are rejected
        monkeypatch.setattr(auth, "verify_google_token", lambda cred: {**claims, "sub": "g-789", "email_verified": False})
        assert c.post("/api/auth/google", json={"credential": "x" * 30}).status_code == 401


def test_google_token_verification_rejects_bad_tokens():
    with client() as c:
        assert c.post("/api/auth/google", json={"credential": "not-a-jwt-but-long-enough-string"}).status_code in (401, 502)


def test_demo_fleet_rules_and_counts():
    with client() as c:
        h, _ = signup(c)
        assert c.get("/api/fleet/overview", headers=h).json()["valves"]["total"] == 0
        ov = c.post("/api/fleet/demo", headers=h).json()
        assert c.post("/api/fleet/demo", headers=h).status_code == 409
        v = ov["valves"]
        assert v["total"] == 20 and v["flagged"] == 3 and v["normal"] == 17
        assert (v["inspect_soon"], v["urgent_review"], v["verify_sensor"]) == (1, 1, 1)
        valves = by_tag(c, h)
        assert valves["V-107"]["priority"] == "inspect_soon" and valves["V-107"]["finding"].startswith("Response time +")
        assert valves["V-113"]["priority"] == "urgent_review"
        assert valves["V-121"]["priority"] == "verify_sensor" and "vibration" in valves["V-121"]["finding"].lower()
        # list is ranked most urgent first, and every valve carries its own sparkline data
        order = c.get("/api/valves", headers=h).json()
        assert order[0]["tag"] == "V-113" and len(order[0]["trend"]) >= 20
        # overview numbers are the same rows the list shows
        assert ov["avg_health"] == round(sum(x["health"] for x in order) / 20)
        assert ov["alerts"]["active"] == len(c.get("/api/alerts?status=active", headers=h).json())
        assert sum(a["valves"] for a in ov["areas"]) == 20
        det = c.get(f"/api/valves/{valves['V-113']['id']}", headers=h).json()
        assert {f["rule"] for f in det["findings"]} >= {"response_time", "position_deviation"}


def test_filters_and_search():
    with client() as c:
        h, _ = with_demo(c)
        assert len(c.get("/api/valves?priority=flagged", headers=h).json()) == 3
        assert [v["tag"] for v in c.get("/api/valves?priority=urgent_review", headers=h).json()] == ["V-113"]
        assert [v["tag"] for v in c.get("/api/valves?q=v-107", headers=h).json()] == ["V-107"]
        assert len(c.get("/api/valves?area=Feedwater", headers=h).json()) == 4
        assert c.get("/api/valves?priority=bogus", headers=h).status_code == 422
        assert c.get("/api/valves?q=zzz", headers=h).json() == []


def test_tenant_isolation():
    with client() as c:
        h1, _ = with_demo(c, "one@example.com")
        h2, _ = signup(c, "two@example.com", "Rival Co")
        assert c.get("/api/valves", headers=h2).json() == []
        assert c.get("/api/fleet/overview", headers=h2).json()["valves"]["total"] == 0
        vid = by_tag(c, h1)["V-113"]["id"]
        rep = c.post(f"/api/valves/{vid}/reports", headers=h1).json()
        alert = c.get("/api/alerts", headers=h1).json()[0]
        # org 2 can neither read nor change org 1's rows, and gets 404 so ids don't leak
        for method, url, body in [("get", f"/api/valves/{vid}", None), ("patch", f"/api/valves/{vid}", {"name": "x"}),
                                  ("delete", f"/api/valves/{vid}", None), ("get", f"/api/valves/{vid}/readings", None),
                                  ("post", f"/api/valves/{vid}/readings", {"position_pct": 1, "command_pct": 1, "response_ms": 5}),
                                  ("post", f"/api/valves/{vid}/reports", None), ("get", f"/api/reports/{rep['id']}", None),
                                  ("post", f"/api/reports/{rep['id']}/review", {"decision": "accepted"}),
                                  ("patch", f"/api/alerts/{alert['id']}", {"status": "resolved"}),
                                  ("delete", f"/api/alerts/{alert['id']}", None)]:
            r = getattr(c, method)(url, headers=h2, **({"json": body} if body is not None else {}))
            assert r.status_code == 404, (method, url, r.status_code)
        assert c.get("/api/reports", headers=h2).json() == [] and c.get("/api/alerts", headers=h2).json() == []
        assert c.post("/api/alerts", headers=h2, json={"valve_id": vid, "severity": "low", "title": "sneaky"}).status_code == 404
        # the same tag can exist in two organisations
        assert c.post("/api/valves", headers=h2, json={"tag": "V-113", "position_pct": 50, "command_pct": 50, "response_ms": 500}).status_code == 201
        assert len(c.get("/api/valves", headers=h1).json()) == 20
        # system tables are scoped too
        assert c.get("/api/system/tables/valves?limit=50", headers=h2).json()["rows"][0]["org_id"] != by_tag(c, h1)["V-113"].get("org_id", -1)
        assert len(c.get("/api/system/tables/valves?limit=50", headers=h2).json()["rows"]) == 1


def test_valve_crud_telemetry_and_alert_sync():
    with client() as c:
        h, _ = signup(c)
        r = c.post("/api/valves", headers=h, json={"tag": "V-900", "area": "Test", "position_pct": 50, "command_pct": 50,
                                                   "response_ms": 800, "baseline_response_ms": 800})
        assert r.status_code == 201 and r.json()["priority"] == "normal" and r.json()["finding"] == "Within baseline"
        vid = r.json()["id"]
        assert c.post("/api/valves", headers=h, json={"tag": "V-900", "position_pct": 1, "command_pct": 1, "response_ms": 5}).status_code == 409
        assert c.post("/api/valves", headers=h, json={"tag": "bad tag!", "position_pct": 1, "command_pct": 1, "response_ms": 5}).status_code == 422
        # a bad reading opens exactly one alert per rule, repeat readings don't duplicate it
        c.post(f"/api/valves/{vid}/readings", headers=h, json={"position_pct": 40, "command_pct": 55, "response_ms": 1700})
        c.post(f"/api/valves/{vid}/readings", headers=h, json={"position_pct": 40, "command_pct": 55, "response_ms": 1800})
        active = c.get(f"/api/alerts?status=active&valve_id={vid}", headers=h).json()
        assert sorted(a["rule"] for a in active) == ["position_deviation", "response_time"]
        assert all(a["severity"] == "critical" for a in active)
        assert c.get(f"/api/valves/{vid}", headers=h).json()["priority"] == "urgent_review"
        # recovery resolves them
        r = c.post(f"/api/valves/{vid}/readings", headers=h, json={"position_pct": 50, "command_pct": 50, "response_ms": 800}).json()
        assert r["valve"]["priority"] == "normal" and r["findings"] == []
        assert c.get(f"/api/alerts?status=active&valve_id={vid}", headers=h).json() == []
        assert len(c.get(f"/api/valves/{vid}/readings", headers=h).json()) == 4
        pred = c.get(f"/api/valves/{vid}/prediction", headers=h).json()
        assert pred["metric"] == "response_ms" and len(pred["actual"]) == 4 and len(pred["forecast"]) == 24
        assert c.patch(f"/api/valves/{vid}", headers=h, json={"name": "Renamed"}).json()["name"] == "Renamed"
        assert c.patch(f"/api/valves/{vid}", headers=h, json={"baseline_response_ms": 400}).json()["priority"] == "urgent_review"
        assert c.delete(f"/api/valves/{vid}", headers=h).status_code == 204
        assert c.get(f"/api/valves/{vid}", headers=h).status_code == 404
        # manual alerts
        a = c.post("/api/alerts", headers=h, json={"severity": "low", "title": "Manual check"}).json()
        assert c.patch(f"/api/alerts/{a['id']}", headers=h, json={"status": "resolved"}).json()["status"] == "resolved"
        assert c.delete(f"/api/alerts/{a['id']}", headers=h).status_code == 204


def test_missing_sensors_do_not_look_flatlined():
    with client() as c:
        h, _ = signup(c)
        vid = c.post("/api/valves", headers=h, json={"tag": "V-1", "position_pct": 50, "command_pct": 50, "response_ms": 800}).json()["id"]
        for _ in range(10):
            c.post(f"/api/valves/{vid}/readings", headers=h, json={"position_pct": 50, "command_pct": 50, "response_ms": 800})
        assert c.get(f"/api/valves/{vid}", headers=h).json()["priority"] == "normal"
        for _ in range(10):  # a transmitter that really does repeat one value
            c.post(f"/api/valves/{vid}/readings", headers=h, json={"position_pct": 50, "command_pct": 50, "response_ms": 800, "vibration_mm_s": 1.3})
        assert c.get(f"/api/valves/{vid}", headers=h).json()["priority"] == "verify_sensor"


def test_free_plan_limits(monkeypatch):
    from app import api
    monkeypatch.setattr(api, "FREE_VALVE_LIMIT", 2)
    monkeypatch.setattr(api, "FREE_REPORTS_PER_MONTH", 1)
    with client() as c:
        h, _ = signup(c)
        assert c.post("/api/fleet/demo", headers=h).status_code == 403  # 20 > 2
        body = {"position_pct": 5, "command_pct": 5, "response_ms": 5}
        v1 = c.post("/api/valves", headers=h, json={"tag": "A", **body}).json()
        assert c.post("/api/valves", headers=h, json={"tag": "B", **body}).status_code == 201
        assert c.post("/api/valves", headers=h, json={"tag": "C", **body}).status_code == 403
        assert c.post(f"/api/valves/{v1['id']}/reports", headers=h).status_code == 201
        assert c.post(f"/api/valves/{v1['id']}/reports", headers=h).status_code == 403
        u = c.get("/api/fleet/overview", headers=h).json()["org"]
        assert u["valves_used"] == 2 and u["valve_limit"] == 2 and u["reports_used_this_month"] == 1


def test_report_flow_with_rules_fallback():
    with client() as c:
        h, _ = with_demo(c)
        vid = by_tag(c, h)["V-113"]["id"]
        rep = c.post(f"/api/valves/{vid}/reports", headers=h).json()
        assert rep["source"] == "rules" and rep["error"] == "no_api_key" and rep["review"] == "pending"
        ev, an = rep["evidence"], rep["analysis"]
        assert ev["priority"] == "urgent_review" and {f["rule"] for f in ev["findings"]} >= {"response_time", "position_deviation"}
        assert an["likely_explanations"][0]["cause"] and an["recommended_first_action"] and an["urgency"] == "within_24h"
        r = c.post(f"/api/reports/{rep['id']}/review", headers=h, json={"decision": "needs_data", "note": "Need fault codes"}).json()
        assert r["review"] == "needs_data" and r["reviewed_by"] == "Alex Morgan" and r["review_note"] == "Need fault codes"
        assert c.post(f"/api/reports/{rep['id']}/review", headers=h, json={"decision": "approved"}).status_code == 422
        r = c.post(f"/api/reports/{rep['id']}/review", headers=h, json={"decision": "accepted"}).json()
        assert r["review"] == "accepted"
        assert all(a["status"] != "open" for a in c.get(f"/api/alerts?valve_id={vid}", headers=h).json())
        assert [x["id"] for x in c.get(f"/api/reports?valve_id={vid}", headers=h).json()] == [rep["id"]]
        assert c.get(f"/api/reports/{rep['id']}", headers=h).json()["valve_tag"] == "V-113"
        # a healthy valve gets an honest "nothing wrong" report, not an invented fault
        ok = c.post(f"/api/valves/{by_tag(c, h)['V-101']['id']}/reports", headers=h).json()
        assert ok["analysis"]["likely_explanations"][0]["cause"] == "No fault indicated"


def test_gemini_parsing_and_prompt(monkeypatch):
    from app import ai
    monkeypatch.setattr(ai, "GEMINI_API_KEY", "x")
    sent = {}
    good = ('Sure!\n```json\n{"summary":"Slow and drifting.","likely_explanations":[{"cause":"Positioner drift","likelihood":"High"},'
            '"Actuator friction"],"recommended_first_action":"Check positioner","next_checks":"Air supply","data_gaps":["Fault codes"],'
            '"urgency":"Within 24h","confidence":85}\n```')

    def fake(prompt):
        sent["prompt"] = prompt
        return good, "gemma-test-1"
    monkeypatch.setattr(ai, "_call_gemini", fake)
    r = ai.diagnose(ai.SAMPLE_CTX)
    a = r["analysis"]
    assert r["source"] == "gemini" and r["api_model_version"] == "gemma-test-1"
    assert a["urgency"] == "within_24h" and a["confidence"] == 0.85 and a["next_checks"] == ["Air supply"]
    assert a["likely_explanations"][0] == {"cause": "Positioner drift", "likelihood": "high"}
    assert a["likely_explanations"][1]["likelihood"] == "medium"
    # the prompt carries the backend's computed findings and tells the model not to recompute them
    assert "Response time +110%" in sent["prompt"] and "urgent_review" in sent["prompt"] and "ALREADY computed" in sent["prompt"]
    st = ai.selftest()
    assert st["ok"] and st["parsed"]["recommended_first_action"] == "Check positioner"
    for bad in ("not json", '{"summary":"x"}', '{"summary":"x","likely_explanations":[],"recommended_first_action":"y","confidence":0.5}'):
        monkeypatch.setattr(ai, "_call_gemini", lambda p, b=bad: (b, None))
        out = ai.diagnose(ai.SAMPLE_CTX)
        assert out["source"] == "rules" and out["error"]
    monkeypatch.setattr(ai, "_call_gemini", lambda p: (_ for _ in ()).throw(KeyError("candidates")))
    assert ai.diagnose(ai.SAMPLE_CTX)["source"] == "rules"


def test_gemini_report_is_stored_when_model_answers(monkeypatch):
    from app import ai
    monkeypatch.setattr(ai, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai, "_call_gemini", lambda p: ('{"summary":"S","likely_explanations":[{"cause":"C","likelihood":"low"}],'
                                                       '"recommended_first_action":"A","confidence":0.7,"urgency":"monitor"}', "v1"))
    with client() as c:
        h, _ = with_demo(c)
        rep = c.post(f"/api/valves/{by_tag(c, h)['V-107']['id']}/reports", headers=h).json()
        assert rep["source"] == "gemini" and rep["model"] == ai.GEMINI_MODEL and rep["error"] is None
        calls = c.get("/api/system/ai-calls", headers=h).json()
        assert calls[0]["source"] == "gemini" and calls[0]["valve_tag"] == "V-107"


def test_settings_reevaluate_valves():
    with client() as c:
        h, _ = with_demo(c)
        before = by_tag(c, h)
        s = c.patch("/api/settings", headers=h, json={"sensitivity": "strict"}).json()
        assert s["sensitivity"] == "strict" and s["thresholds"]["response_inspect_ratio"] < 1.4
        after = by_tag(c, h)
        assert sum(v["priority"] != "normal" for v in after.values()) >= sum(v["priority"] != "normal" for v in before.values())
        assert c.get("/api/settings", headers=h).json()["sensitivity"] == "strict"
        assert c.patch("/api/settings", headers=h, json={"sensitivity": "wild"}).status_code == 422


def test_system_page_endpoints():
    with client() as c:
        h, _ = with_demo(c, "s@example.com")
        st = c.get("/api/system/status", headers=h).json()
        names = {t["name"]: t["rows"] for t in st["database"]["tables"]}
        assert names["valves"] == 20 and names["users"] == 1 and st["google_sign_in"] is True
        assert "password_hash" not in str(st) and "google_sub" not in str(st)
        rows = c.get("/api/system/tables/users", headers=h).json()
        assert "password_hash" not in rows["columns"] and rows["rows"][0]["email"] == "s@example.com"
        assert c.get("/api/system/tables/nope", headers=h).status_code == 404
        t = c.post("/api/system/ai-selftest", headers=h).json()
        assert t["ok"] is False and t["error"] == "no_api_key" and "GEMINI_API_KEY" in t["hint"]
        log = c.get("/api/system/requests", headers=h).json()
        assert any(r["method"] == "POST" and r["path"] == "/api/fleet/demo" and r["status"] == 201 for r in log)
        h2, _ = signup(c, "other@example.com", "Rival")
        assert c.get("/api/system/requests", headers=h2).json() == []
        assert c.get("/api/health").json()["google_client_id"] == "test-client.apps.googleusercontent.com"


def test_cors_allows_the_react_app():
    with client() as c:
        for origin in ("http://localhost:8080", "https://my-app.lovable.app"):
            r = c.options("/api/valves", headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                                                  "Access-Control-Request-Headers": "authorization"})
            assert r.headers.get("access-control-allow-origin") == origin, origin
        r = c.options("/api/valves", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
        assert "access-control-allow-origin" not in r.headers

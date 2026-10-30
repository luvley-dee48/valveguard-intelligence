import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["GEMINI_API_KEY"] = ""
from fastapi.testclient import TestClient
from app.main import app

def client():
    return TestClient(app)

def signup(c, email="a@example.com"):
    r = c.post("/api/auth/signup", json={"name": "Alex Morgan", "email": email, "password": "supersecret1"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}, r.json()["user"]

def test_auth_flow():
    with client() as c:
        assert c.get("/api/assets").status_code == 401
        h, user = signup(c)
        assert user["role"] == "admin"
        assert c.post("/api/auth/signup", json={"name": "X Y", "email": "a@example.com", "password": "supersecret1"}).status_code == 409
        assert c.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong"}).status_code == 401
        r = c.post("/api/auth/login", json={"email": "A@example.com", "password": "supersecret1"})
        assert r.status_code == 200 and c.get("/api/auth/me", headers={"Authorization": "Bearer " + r.json()["token"]}).json()["email"] == "a@example.com"
        assert c.post("/api/auth/signup", json={"name": "Bo", "email": "bad", "password": "supersecret1"}).status_code == 422
        h2, u2 = signup(c, "b@example.com")
        assert u2["role"] == "operator"
        assert c.delete("/api/assets/1", headers=h2).status_code == 403

def test_asset_crud_and_sync():
    with client() as c:
        h, _ = signup(c, "c@example.com")
        assets = c.get("/api/assets", headers=h).json()
        assert len(assets) == 12 and assets[0]["tag"] == "C-201"
        r = c.post("/api/assets", headers=h, json={"tag": "P-900", "name": "Test pump", "type": "pump", "vibration": 1.0, "temperature": 60})
        assert r.status_code == 201; aid = r.json()["id"]
        assert r.json()["status"] == "healthy"
        assert c.post("/api/assets", headers=h, json={"tag": "P-900", "name": "x", "type": "pump"}).status_code == 409
        r = c.patch(f"/api/assets/{aid}", headers=h, json={"vibration": 8.0})
        assert r.json()["status"] == "critical"
        alerts = c.get("/api/alerts?status=active", headers=h).json()
        mine = [a for a in alerts if a["asset_id"] == aid]
        assert len(mine) == 1 and mine[0]["severity"] == "critical"
        c.post(f"/api/assets/{aid}/readings", headers=h, json={"vibration": 8.5, "temperature": 70})
        assert len([a for a in c.get("/api/alerts?status=active", headers=h).json() if a["asset_id"] == aid]) == 1
        c.post(f"/api/assets/{aid}/readings", headers=h, json={"vibration": 1.0, "temperature": 60})
        assert not [a for a in c.get("/api/alerts?status=active", headers=h).json() if a["asset_id"] == aid]
        r = c.put(f"/api/assets/{aid}", headers=h, json={"tag": "P-900", "name": "Renamed", "type": "pump", "vibration": 1.0, "temperature": 60})
        assert r.json()["name"] == "Renamed"
        assert c.delete(f"/api/assets/{aid}", headers=h).status_code == 204
        assert c.get(f"/api/assets/{aid}", headers=h).status_code == 404

def test_alerts_ai_review():
    with client() as c:
        h, _ = signup(c, "d@example.com")
        a = c.post("/api/alerts", headers=h, json={"severity": "low", "title": "Manual check"}).json()
        assert c.post(f"/api/alerts/{a['id']}/analyze", headers=h).status_code == 422
        top = c.get("/api/alerts?severity=critical", headers=h).json()[0]
        r = c.post(f"/api/alerts/{top['id']}/analyze", headers=h).json()
        assert r["ai_review"] == "pending" and r["ai_analysis"]["source"] == "rules"
        assert r["ai_analysis"]["analysis"]["urgency"] in ("immediate", "within_24h")
        r = c.post(f"/api/alerts/{top['id']}/analysis/review", headers=h, json={"decision": "approve"}).json()
        assert r["ai_review"] == "approved" and r["status"] == "acknowledged"
        assert c.post(f"/api/alerts/{top['id']}/analysis/review", headers=h, json={"decision": "approve"}).status_code == 409
        assert c.patch(f"/api/alerts/{a['id']}", headers=h, json={"status": "resolved"}).json()["status"] == "resolved"
        assert c.put(f"/api/alerts/{a['id']}", headers=h, json={"severity": "medium", "title": "Edited"}).json()["title"] == "Edited"
        assert c.delete(f"/api/alerts/{a['id']}", headers=h).status_code == 204

def test_overview_workflows_settings():
    with client() as c:
        h, _ = signup(c, "e@example.com")
        o = c.get("/api/overview", headers=h).json()
        assert o["kpis"]["assets"] == 12 and o["alert_summary"]["total"] == o["kpis"]["alerts"]
        pred = c.get(f"/api/assets/{o['top_risk_asset_id']}/prediction", headers=h).json()
        assert len(pred["actual"]) == 24 and len(pred["forecast"]) == 24 and pred["failure_probability_72h"] > 0.9
        g = c.post("/api/insights/generate", headers=h).json()
        assert g["created"] == [] and g["skipped_existing"] >= 1      # seeded insights already pending
        ins = [i for i in c.get("/api/insights", headers=h).json() if i["asset_tag"] == "C-201"][0]
        assert c.patch(f"/api/insights/{ins['id']}", headers=h, json={"status": "dismissed"}).json()["status"] == "dismissed"
        g = c.post("/api/insights/generate", headers=h).json()
        assert g["created"] and all(i["status"] == "pending" and i["source"] == "rules" for i in g["created"])
        wf = c.post("/api/workflows", headers=h, json={"name": "My flow", "steps": [{"kind": "trigger", "label": "T"}]}).json()
        assert c.post(f"/api/workflows/{wf['id']}/run", headers=h).json()["run_count"] == 1
        assert c.patch(f"/api/workflows/{wf['id']}", headers=h, json={"enabled": False}).json()["enabled"] is False
        assert c.post(f"/api/workflows/{wf['id']}/run", headers=h).status_code == 409
        assert c.delete(f"/api/workflows/{wf['id']}", headers=h).status_code == 204
        s = c.put("/api/settings", headers=h, json={"sensitivity": "strict", "auto_work_order": False, "vibration_alarm": 5, "temperature_alarm": 85, "plant_name": "South Plant"}).json()
        assert s["sensitivity"] == "strict" and c.get("/api/settings", headers=h).json()["plant_name"] == "South Plant"
        assert c.put("/api/metrics/oee", headers=h, json={"value": 90.1, "delta": 1}).status_code == 200
        i = c.post("/api/integrations", headers=h, json={"name": "SAP"}).json()
        assert c.patch(f"/api/integrations/{i['id']}", headers=h, json={"status": "disconnected"}).json()["status"] == "disconnected"
        assert c.delete(f"/api/integrations/{i['id']}", headers=h).status_code == 204
        assert c.get("/api/analytics/fleet", headers=h).json()["risk"]
        assert c.get("/api/reports/summary", headers=h).json()["assets"]["total"] == 12

def test_gemini_parsing(monkeypatch):
    from app import ai
    monkeypatch.setattr(ai, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(ai, "_call_gemini", lambda p: ('Sure!\n```json\n{"probable_cause":"Bearing wear","failure_mode":"Bearing","urgency":"Within 24h","confidence":85,"recommended_actions":["Inspect"],"uncertainty_notes":""}\n```', "gemma-4-26b-a4b-it-test"))
    ctx = dict(tag="C-1", type="pump", vibration=7, temperature=70, health=50, vib_alarm=6, temp_alarm=90, slope_per_hour=.2, hours_to_threshold=0, failure_probability_72h=.9, recent_vibration=[6, 7])
    r = ai.diagnose(ctx)
    assert r["source"] == "gemini" and r["analysis"]["urgency"] == "within_24h" and r["analysis"]["confidence"] == .85
    assert r["api_model_version"] == "gemma-4-26b-a4b-it-test" and r["latency_ms"] >= 0
    st = ai.selftest()
    assert st["ok"] and st["raw_reply"] and st["parsed"]["failure_mode"] == "Bearing"
    monkeypatch.setattr(ai, "_call_gemini", lambda p: ("not json", None))
    assert ai.diagnose(ctx)["source"] == "rules"


def test_system_page_endpoints():
    with client() as c:
        h, _ = signup(c, "s@example.com")
        st = c.get("/api/system/status", headers=h).json()
        names = {t["name"]: t["rows"] for t in st["database"]["tables"]}
        assert names["assets"] == 12 and names["users"] == 1 and "ai_calls" in names
        assert "password_hash" not in str(st) and st["ai"]["model"] == "gemma-4-26b-a4b-it" and st["ai"]["is_gemma4"]
        rows = c.get("/api/system/tables/users", headers=h).json()
        assert "password_hash" not in rows["columns"] and rows["rows"][0]["email"] == "s@example.com"
        assert c.get("/api/system/tables/nope", headers=h).status_code == 404
        h2, _ = signup(c, "t@example.com")
        assert c.get("/api/system/tables/users", headers=h2).status_code == 403
        # no key configured: self-test reports it plainly, never crashes
        t = c.post("/api/system/ai-selftest", headers=h).json()
        assert t["ok"] is False and t["error"] == "no_api_key" and "GEMINI_API_KEY" in t["hint"]
        # a write shows up in the request log; AI fallback is logged too
        c.post("/api/assets", headers=h, json={"tag": "Z-1", "name": "Log me", "type": "pump"})
        crit = c.get("/api/alerts?severity=critical", headers=h).json()[0]
        c.post(f"/api/alerts/{crit['id']}/analyze", headers=h)
        log = c.get("/api/system/requests", headers=h).json()
        assert any(r["method"] == "POST" and r["path"] == "/api/assets" and r["status"] == 201 for r in log)
        calls = c.get("/api/system/ai-calls", headers=h).json()
        assert calls[0]["kind"] == "alert_analysis" and calls[0]["source"] == "rules" and calls[0]["error"] == "no_api_key"

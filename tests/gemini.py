"""Quick Gemini check. Run:  python test_gemini.py"""
import os, sys, time
from pathlib import Path
import httpx

# Read .env the same way the app does
env = Path(".env")
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.split(" #")[0].strip().strip('"').strip("'"))

key = os.getenv("GEMINI_API_KEY", "")
model = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")
root = "https://generativelanguage.googleapis.com/v1beta"

if not key:
    sys.exit("GEMINI_API_KEY is empty. Add it to .env (no quotes, no spaces) and run again.")
print(f"Key found ({len(key)} characters). Model: {model}")

t0 = time.time()
try:
    r = httpx.post(
        f"{root}/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json={"contents": [{"role": "user", "parts": [{"text": "Reply with exactly: GEMINI OK"}]}]},
        timeout=60,
    )
except httpx.HTTPError as e:
    sys.exit(f"FAILED: could not reach Google ({type(e).__name__}). Check your internet or firewall.")

print(f"HTTP {r.status_code} in {int((time.time() - t0) * 1000)} ms")
if r.status_code == 200:
    data = r.json()
    parts = data["candidates"][0]["content"]["parts"]
    print("Model reply:", "".join(p.get("text", "") for p in parts if not p.get("thought")).strip())
    print("API-reported model:", data.get("modelVersion"))
    print("SUCCESS: Gemini works.")
else:
    try:
        print("Error from Google:", r.json()["error"]["message"])
    except Exception:
        print(r.text[:300])
    if r.status_code == 404:
        m = httpx.get(f"{root}/models", headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
        if m.status_code == 200:
            names = [x["name"].removeprefix("models/") for x in m.json().get("models", [])]
            print("Models your key CAN use (gemma/gemini):")
            for n in names:
                if "gemma" in n or "gemini" in n:
                    print("  ", n)
            print("Set GEMINI_MODEL in .env to one of these.")
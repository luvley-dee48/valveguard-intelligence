#!/usr/bin/env bash
# One-command start for Linux / WSL / Mac:  bash run.sh
set -e
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or newer is required (you have %s)" % sys.version.split()[0]'
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Open http://localhost:8000  (Ctrl+C to stop)"
exec uvicorn app.main:app --reload

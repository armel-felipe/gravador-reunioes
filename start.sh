#!/usr/bin/env bash
# Sobe o servidor local de captura em 127.0.0.1:8765
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r server/requirements.txt
fi

exec .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8765

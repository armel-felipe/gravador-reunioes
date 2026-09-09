#!/usr/bin/env bash
# Sobe o servidor local de captura em 127.0.0.1:8765
set -e
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg não encontrado — instale com: brew install ffmpeg" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r server/requirements.txt
  echo "Instalando dependências de processamento (pode demorar)..."
  .venv/bin/pip install -q -r scripts/requirements.txt
fi

exec .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8765

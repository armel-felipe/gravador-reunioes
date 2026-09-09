"""Servidor local de captura — recebe áudio da extensão e salva em 99_material/audio."""
import base64
import json
import re
from datetime import datetime
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.audio_store import AudioStore

ROOT = Path(__file__).resolve().parent.parent
NOME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ORIGENS_PERMITIDAS = ("chrome-extension://", "http://localhost", "http://127.0.0.1")


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


app = FastAPI()
store = AudioStore(load_config()["caminhos"]["audio_dir"])
active_session = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global active_session
    origin = ws.headers.get("origin", "")
    if not origin or not origin.startswith(ORIGENS_PERMITIDAS):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "start":
                nome = msg.get("nome", "reuniao")
                if not NOME_RE.match(nome):
                    await ws.send_text(json.dumps({"type": "error", "message": "nome inválido"}))
                    await ws.close(code=1008)
                    return
                sample_rate = msg.get("sample_rate", 48000)
                now = datetime.now()
                session_id = now.strftime("%Y_%m_%d_%H_%M") + "_" + nome
                store.start_session(session_id, nome, sample_rate)
                active_session = session_id
                await ws.send_text(json.dumps({"type": "started", "session_id": session_id}))
            elif msg.get("type") == "audio":
                channel = msg.get("channel", "tab")
                chunk = base64.b64decode(msg["data"])
                store.append(channel, chunk)
            elif msg.get("type") == "end":
                wav = store.finish()
                active_session = None
                await ws.send_text(json.dumps({"type": "ended", "wav": wav}))
                break
    except WebSocketDisconnect:
        # Gravação interrompida: salva o que chegou
        if active_session:
            try:
                store.finish()
            except Exception:
                pass
            active_session = None


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)

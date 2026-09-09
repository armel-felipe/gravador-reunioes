"""Servidor local de captura — recebe áudio da extensão e salva em 99_material/audio."""
import base64
import json
from datetime import datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.audio_store import AudioStore

app = FastAPI()
store = AudioStore("99_material/audio")
active_session = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global active_session
    await ws.accept()
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "start":
                nome = msg.get("nome", "reuniao")
                now = datetime.now()
                session_id = now.strftime("%Y_%m_%d_%H_%M") + "_" + nome
                store.start_session(session_id, nome)
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

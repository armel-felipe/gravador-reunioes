"""Servidor local de captura — recebe áudio da extensão e salva em 99_material/audio."""
import base64
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from server.audio_store import AudioStore

ROOT = Path(__file__).resolve().parent.parent
# Nome digitado no popup: aceita letras, números, espaços, hífens, underscores e acentos.
# Apenas caracteres de controle e separadores de caminho são proibidos (segurança).
NOME_RE = re.compile(r"^[^/\\\x00-\x1f]{1,80}$")


def sanitizar_nome_arquivo(nome: str) -> str:
    """Converte o nome digitado em um sufixo seguro para nome de arquivo."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_") or "reuniao"


def origin_permitida(origin: str) -> bool:
    if not origin:
        return False
    if origin.startswith("chrome-extension://"):
        return True
    host = urlsplit(origin).hostname
    return host in ("localhost", "127.0.0.1")


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


app = FastAPI()
# O AudioStore cria 99_material/audio/<session_id>/ com bruto/ e o wav mixado.
AUDIO_DIR = Path(load_config()["caminhos"]["material_dir"]) / "audio"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin", "")
    if not origin_permitida(origin):
        await ws.close(code=1008)
        return
    await ws.accept()
    # Cada conexão tem seu próprio store — conexões simultâneas não interferem.
    store = AudioStore(AUDIO_DIR)
    started = False
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
                if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
                    await ws.send_text(json.dumps({"type": "error", "message": "sample_rate inválido"}))
                    await ws.close(code=1008)
                    return
                now = datetime.now()
                session_id = now.strftime("%Y_%m_%d_%H_%M") + "_" + sanitizar_nome_arquivo(nome)
                store.start_session(session_id, nome, sample_rate)
                started = True
                await ws.send_text(json.dumps({"type": "started", "session_id": session_id}))
            elif msg.get("type") == "audio":
                if not started:
                    await ws.send_text(json.dumps({"type": "error", "message": "sessão não iniciada"}))
                    continue
                channel = msg.get("channel", "tab")
                chunk = base64.b64decode(msg["data"])
                store.append(channel, chunk)
            elif msg.get("type") == "end":
                if not started:
                    await ws.send_text(json.dumps({"type": "error", "message": "sessão não iniciada"}))
                    continue
                wav = store.finish()
                started = False
                await ws.send_text(json.dumps({"type": "ended", "wav": wav}))
                break
    except WebSocketDisconnect:
        # Gravação interrompida: salva o que chegou (só se ainda não finalizou)
        if started:
            try:
                store.finish()
            except Exception:
                pass


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)

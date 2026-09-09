# Gravador de Reuniões — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o sistema completo de gravação de reuniões no navegador com transcrição (Whisper), diarização (pyannote) e notas (Ollama), orquestrado de forma agêntica pelo OpenWork.

**Architecture:** Extensão Chrome (MV3) captura áudio da aba + microfone e transmite via WebSocket para um servidor local FastAPI (só captura, não processa). O processamento é feito por scripts Python modulares (transcrever → diarizar → alinhar → notas) disparados por skills do OpenWork. Material separado do código em `99_material/`.

**Tech Stack:** Chrome Extension MV3 (JS), Python 3.11+, FastAPI + websockets, faster-whisper, pyannote.audio, ffmpeg, Ollama (local ou cloud), OpenWork skills.

## Global Constraints

- Estrutura: código em `extension/`, `server/`, `scripts/`, `.opencode/skills/`; material em `99_material/` (audio/, transcricoes/, notas/).
- Nomeação de arquivos: `YYYY_MM_DD_HH_MM_<nome>.webm` / `.wav` / `.md` (data/hora local no momento de gravar).
- Servidor escuta somente em `127.0.0.1:8765`.
- Áudios com mais de 30 dias são apagados; transcrições e notas são mantidas.
- Modelos configuráveis via `config.yaml` (Whisper: `large-v3` default; Ollama: local ou cloud).
- Tudo em pt-BR (UI do popup, prompts, saídas).
- ffmpeg é dependência de sistema (assumir instalado; verificar no Task 2).

---

### Task 1: Estrutura do projeto + config.yaml

**Files:**
- Create: `config.yaml`
- Create: `.gitignore`
- Create: `99_material/audio/bruto/.gitkeep`
- Create: `99_material/transcricoes/_tmp/.gitkeep`
- Create: `99_material/notas/.gitkeep`

**Interfaces:**
- Consumes: nada.
- Produces: `config.yaml` com a estrutura que todos os scripts leem (função `load_config()` definida no Task 4).

- [ ] **Step 1: Criar a estrutura de diretórios**

```bash
mkdir -p extension server scripts .opencode/skills 99_material/audio/bruto 99_material/transcricoes/_tmp 99_material/notas
```

- [ ] **Step 2: Criar `config.yaml`**

```yaml
# Configuração central do gravador de reuniões
whisper:
  model: "large-v3"        # large-v3 | medium (trocar se lento)
  device: "auto"           # auto | cpu | cuda | mps
  compute_type: "auto"     # auto | int8 | float16

diarizacao:
  model: "pyannote/speaker-diarization-3.1"
  min_speakers: null       # null = automático
  max_speakers: null

ollama:
  provider: "local"        # local | cloud
  local_model: "qwen3.6:35b-mlx"
  cloud_model: "qwen3.6:35b-mlx"
  cloud_base_url: "https://ollama.com/api"   # preencher com a URL real da API
  cloud_api_key_env: "LPR_BZ685_OLLAMA_API_KEY"  # nome da env var com a chave

caminhos:
  audio_dir: "99_material/audio"
  transcricoes_dir: "99_material/transcricoes"
  notas_dir: "99_material/notas"
  tmp_dir: "99_material/transcricoes/_tmp"

limpeza:
  dias_retencao_audio: 30
```

- [ ] **Step 3: Criar `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.DS_Store
99_material/audio/*.wav
99_material/audio/*.webm
99_material/audio/bruto/*
!99_material/audio/bruto/.gitkeep
99_material/transcricoes/*.md
99_material/transcricoes/_tmp/*
!99_material/transcricoes/_tmp/.gitkeep
99_material/notas/*.md
```

- [ ] **Step 4: Criar os `.gitkeep`**

```bash
touch 99_material/audio/bruto/.gitkeep 99_material/transcricoes/_tmp/.gitkeep 99_material/notas/.gitkeep
```

- [ ] **Step 5: Verificar estrutura**

Run: `find . -not -path './.git*' -not -name '.DS_Store' | sort`
Expected: todos os diretórios e arquivos acima listados.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: estrutura do projeto e config central"
```

---

### Task 2: Servidor de captura (FastAPI + WebSocket)

**Files:**
- Create: `server/__init__.py`
- Create: `server/main.py`
- Create: `server/audio_store.py`
- Create: `server/requirements.txt`
- Create: `start.sh`
- Test: `server/test_audio_store.py`

**Interfaces:**
- Consumes: `config.yaml` (caminhos).
- Produces:
  - `GET /health` → `{"status": "ok"}`
  - `WS /ws` — mensagens JSON `{"channel": "tab"|"mic", "data": "<base64 audio>"}`; ao final, mensagem `{"type": "end"}`.
  - `audio_store.AudioStore` com métodos `start_session(session_id, nome)`, `append(channel, chunk_bytes)`, `finish()` → caminho do `.wav` mixado.
  - `start.sh` sobe o servidor em `127.0.0.1:8765`.

- [ ] **Step 1: Verificar ffmpeg**

Run: `ffmpeg -version | head -1`
Expected: `ffmpeg version ...` (se não existir: `brew install ffmpeg` antes de continuar).

- [ ] **Step 2: Escrever o teste que falha**

`server/test_audio_store.py`:

```python
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from audio_store import AudioStore


def test_start_append_finish_creates_mixed_wav():
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioStore(base_dir=tmp)
        session_id = "2026_09_09_14_30_reuniao"
        store.start_session(session_id, "reuniao")
        # 0.5s de silêncio em cada canal (WAV PCM 16kHz mono 16-bit)
        chunk = b"\x00\x00" * 8000
        store.append("tab", chunk)
        store.append("mic", chunk)
        wav_path = store.finish()
        assert wav_path.endswith(".wav")
        assert os.path.exists(wav_path)
        assert os.path.getsize(wav_path) > 100
        # brutos salvos
        assert os.path.exists(os.path.join(tmp, "bruto", f"{session_id}_tab.webm"))
        assert os.path.exists(os.path.join(tmp, "bruto", f"{session_id}_mic.webm"))
```

- [ ] **Step 3: Rodar o teste para ver falhar**

Run: `python -m pytest server/test_audio_store.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'audio_store'`.

- [ ] **Step 4: Implementar `server/audio_store.py`**

```python
"""Armazena chunks de áudio recebidos e gera o WAV mixado final."""
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


class AudioStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.bruto_dir = self.base_dir / "bruto"
        self.bruto_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = None
        self._tab_path = None
        self._mic_path = None
        self._tab_fh = None
        self._mic_fh = None

    def start_session(self, session_id: str, nome: str):
        self.session_id = session_id
        self._tab_path = self.bruto_dir / f"{session_id}_tab.webm"
        self._mic_path = self.bruto_dir / f"{session_id}_mic.webm"
        self._tab_fh = open(self._tab_path, "wb")
        self._mic_fh = open(self._mic_path, "wb")

    def append(self, channel: str, chunk: bytes):
        fh = self._tab_fh if channel == "tab" else self._mic_fh
        fh.write(chunk)

    def finish(self) -> str:
        self._tab_fh.close()
        self._mic_fh.close()
        wav_path = self.base_dir / f"{self.session_id}.wav"
        # Mixa os dois canais em um WAV 16kHz mono
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self._tab_path),
            "-i", str(self._mic_path),
            "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:normalize=0,aresample=16000,pan=mono|c0=0.5*c0+0.5*c1",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return str(wav_path)
```

- [ ] **Step 5: Rodar o teste para passar**

Run: `python -m pytest server/test_audio_store.py -v`
Expected: PASS.

- [ ] **Step 6: Implementar `server/main.py`**

```python
"""Servidor local de captura — recebe áudio da extensão e salva em 99_material/audio."""
import base64
import json
from datetime import datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from audio_store import AudioStore

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
```

- [ ] **Step 7: Criar `server/requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
websockets==12.*
pytest==8.*
```

- [ ] **Step 8: Criar `start.sh`**

```bash
#!/usr/bin/env bash
# Sobe o servidor local de captura em 127.0.0.1:8765
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r server/requirements.txt
fi

exec .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

```bash
chmod +x start.sh
```

- [ ] **Step 9: Testar o servidor de ponta a ponta**

```bash
./start.sh &
sleep 3
curl -s http://127.0.0.1:8765/health
```

Expected: `{"status":"ok"}`. Depois mate o servidor (`kill %1`).

- [ ] **Step 10: Commit**

```bash
git add server/ start.sh
git commit -m "feat: servidor local de captura com mixagem de áudio"
```

---

### Task 3: Extensão Chrome (MV3)

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/popup.html`
- Create: `extension/popup.js`
- Create: `extension/background.js`
- Create: `extension/icons/icon16.png`, `icon48.png`, `icon128.png` (gerar com script)

**Interfaces:**
- Consumes: servidor `ws://127.0.0.1:8765/ws` e `http://127.0.0.1:8765/health`.
- Produces: popup com campo nome + botão Gravar/Parar; gravação em duas capturas (tab + mic) transmitidas ao servidor.

- [ ] **Step 1: Criar `extension/manifest.json`**

```json
{
  "manifest_version": 3,
  "name": "Gravador de Reuniões",
  "version": "0.1.0",
  "description": "Grava o áudio da aba + microfone e envia para o servidor local de transcrição.",
  "permissions": ["tabCapture", "activeTab", "storage"],
  "host_permissions": ["http://127.0.0.1:8765/*", "ws://127.0.0.1:8765/*"],
  "action": {
    "default_popup": "popup.html",
    "default_title": "Gravador de Reuniões"
  },
  "background": {
    "service_worker": "background.js"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

- [ ] **Step 2: Criar `extension/popup.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: system-ui, sans-serif; width: 260px; padding: 12px; }
    input { width: 100%; box-sizing: border-box; padding: 6px; margin-bottom: 8px; }
    button { width: 100%; padding: 8px; font-size: 14px; cursor: pointer; }
    #status { margin-top: 8px; font-size: 12px; color: #555; }
    #timer { font-size: 18px; font-weight: bold; text-align: center; margin: 8px 0; }
  </style>
</head>
<body>
  <h3 style="margin:0 0 8px">Gravador de Reuniões</h3>
  <input id="nome" type="text" placeholder="Nome da reunião (ex.: orcamento_ana)">
  <div id="timer" hidden>00:00</div>
  <button id="toggle">Gravar</button>
  <div id="status"></div>
  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 3: Criar `extension/popup.js`**

```js
const nomeInput = document.getElementById("nome");
const toggleBtn = document.getElementById("toggle");
const statusDiv = document.getElementById("status");
const timerDiv = document.getElementById("timer");

let recording = false;
let timerInterval = null;
let seconds = 0;

async function serverOnline() {
  try {
    const r = await fetch("http://127.0.0.1:8765/health");
    return r.ok;
  } catch {
    return false;
  }
}

function updateUI() {
  toggleBtn.textContent = recording ? "Parar" : "Gravar";
  timerDiv.hidden = !recording;
  nomeInput.disabled = recording;
}

function tick() {
  seconds++;
  const m = String(Math.floor(seconds / 60)).padStart(2, "0");
  const s = String(seconds % 60).padStart(2, "0");
  timerDiv.textContent = `${m}:${s}`;
}

toggleBtn.addEventListener("click", async () => {
  if (!recording) {
    const nome = nomeInput.value.trim();
    if (!nome) {
      statusDiv.textContent = "Digite o nome da reunião.";
      return;
    }
    if (!(await serverOnline())) {
      statusDiv.textContent = "Servidor offline — rode ./start.sh";
      return;
    }
    const resp = await chrome.runtime.sendMessage({ type: "start", nome });
    if (resp && resp.ok) {
      recording = true;
      seconds = 0;
      timerInterval = setInterval(tick, 1000);
      statusDiv.textContent = "Gravando…";
    } else {
      statusDiv.textContent = "Erro ao iniciar gravação.";
    }
  } else {
    await chrome.runtime.sendMessage({ type: "stop" });
    recording = false;
    clearInterval(timerInterval);
    statusDiv.textContent = "Gravação salva. Processe no chat do OpenWork.";
  }
  updateUI();
});

// Restaura estado se o popup foi fechado e reaberto
chrome.runtime.sendMessage({ type: "getState" }, (resp) => {
  if (resp && resp.recording) {
    recording = true;
    updateUI();
    statusDiv.textContent = "Gravando…";
  }
});
```

- [ ] **Step 4: Criar `extension/background.js`**

```js
let state = { recording: false, nome: null, ws: null, tabStream: null, micStream: null };

function connectWs() {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket("ws://127.0.0.1:8765/ws");
    ws.onopen = () => resolve(ws);
    ws.onerror = () => reject(new Error("ws error"));
    state.ws = ws;
  });
}

function sendAudio(ws, channel, stream) {
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  source.connect(processor);
  processor.connect(ctx.destination);
  processor.onaudioprocess = (e) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const buf = e.inputBuffer.getChannelData(0);
    const pcm = new Int16Array(buf.length);
    for (let i = 0; i < buf.length; i++) pcm[i] = Math.max(-1, Math.min(1, buf[i])) * 32767;
    ws.send(JSON.stringify({
      type: "audio",
      channel,
      data: btoa(String.fromCharCode(...new Uint8Array(pcm.buffer)))
    }));
  };
  return processor;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "start") {
    (async () => {
      const ws = await connectWs();
      ws.send(JSON.stringify({ type: "start", nome: msg.nome }));
      const [tabStream] = await chrome.tabCapture.getMediaStreamId ? [] : [];
      // tabCapture: captura a aba ativa
      const tabId = (await chrome.tabs.query({ active: true, currentWindow: true }))[0].id;
      const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
      const tabStream2 = await navigator.mediaDevices.getUserMedia({
        audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } }
      });
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.tabStream = tabStream2;
      state.micStream = micStream;
      sendAudio(ws, "tab", tabStream2);
      sendAudio(ws, "mic", micStream);
      state.recording = true;
      state.nome = msg.nome;
      sendResponse({ ok: true });
    })().catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }

  if (msg.type === "stop") {
    if (state.ws) {
      state.ws.send(JSON.stringify({ type: "end" }));
      state.ws.close();
    }
    if (state.tabStream) state.tabStream.getTracks().forEach((t) => t.stop());
    if (state.micStream) state.micStream.getTracks().forEach((t) => t.stop());
    state.recording = false;
    state.nome = null;
    sendResponse({ ok: true });
    return true;
  }

  if (msg.type === "getState") {
    sendResponse({ recording: state.recording });
  }
});
```

- [ ] **Step 5: Gerar ícones**

```bash
mkdir -p extension/icons
python3 -c "
import struct, zlib
def png(path, size):
    # PNG 1x1 vermelho simples (placeholder)
    raw = b''.join(b'\x00' + b'\xff\x00\x00' * size * size)
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    open(path, 'wb').write(data)
for s in (16, 48, 128):
    png(f'extension/icons/icon{s}.png', s)
"
```

- [ ] **Step 6: Teste manual — carregar a extensão**

1. Abra `chrome://extensions`, ative "Modo do desenvolvedor", clique "Carregar sem compactação" e selecione `extension/`.
2. Rode `./start.sh` (servidor de pé).
3. Abra um vídeo do YouTube, clique no ícone da extensão, digite `teste_30s`, clique **Gravar**, espere ~30s, clique **Parar**.
4. Verifique: `99_material/audio/` contém `YYYY_MM_DD_HH_MM_teste_30s.wav` e `bruto/` contém os dois `.webm`.

Expected: arquivos presentes com o nome correto.

- [ ] **Step 7: Commit**

```bash
git add extension/
git commit -m "feat: extensão Chrome com captura de aba + microfone"
```

---

### Task 4: Scripts de transcrição e diarização (01, 02, 03)

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/common.py` (load_config, caminhos)
- Create: `scripts/01_transcrever.py`
- Create: `scripts/02_diarizar.py`
- Create: `scripts/03_alinhar.py`
- Create: `scripts/requirements.txt`
- Test: `scripts/test_alinhar.py`

**Interfaces:**
- Consumes: `config.yaml`; `99_material/audio/*.wav`.
- Produces:
  - `common.load_config() -> dict`
  - `common.audio_paths(nome_base) -> dict` com chaves `wav`, `transcricao_json`, `diarizacao_json`, `transcricao_md`
  - `01_transcrever.py <nome_base>` → `99_material/transcricoes/_tmp/<nome_base>_transcricao.json` (lista de `{start, end, text}`)
  - `02_diarizar.py <nome_base>` → `99_material/transcricoes/_tmp/<nome_base>_diarizacao.json` (lista de `{start, end, speaker}`)
  - `03_alinhar.py <nome_base>` → `99_material/transcricoes/<nome_base>.md` (falas diarizadas)

- [ ] **Step 1: Escrever o teste que falha**

`scripts/test_alinhar.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alinhar import alinhar_falas


def test_alinhar_falas_basico():
    transcricao = [
        {"start": 0.0, "end": 2.0, "text": "Bom dia"},
        {"start": 2.5, "end": 4.0, "text": "Vamos começar"},
    ]
    diarizacao = [
        {"start": 0.0, "end": 3.0, "speaker": "Falante 1"},
        {"start": 3.0, "end": 5.0, "speaker": "Falante 2"},
    ]
    falas = alinhar_falas(transcricao, diarizacao)
    assert falas[0]["speaker"] == "Falante 1"
    assert falas[1]["speaker"] == "Falante 2"


def test_alinhar_falas_sem_sobreposicao():
    transcricao = [{"start": 10.0, "end": 11.0, "text": "oi"}]
    diarizacao = [{"start": 0.0, "end": 5.0, "speaker": "Falante 1"}]
    falas = alinhar_falas(transcricao, diarizacao)
    assert falas[0]["speaker"] == "Desconhecido"
```

- [ ] **Step 2: Rodar o teste para ver falhar**

Run: `python -m pytest scripts/test_alinhar.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'alinhar'`.

- [ ] **Step 3: Implementar `scripts/common.py`**

```python
"""Funções compartilhadas: config e caminhos."""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def audio_paths(nome_base: str) -> dict:
    cfg = load_config()
    audio = Path(cfg["caminhos"]["audio_dir"])
    trans = Path(cfg["caminhos"]["transcricoes_dir"])
    tmp = Path(cfg["caminhos"]["tmp_dir"])
    return {
        "wav": audio / f"{nome_base}.wav",
        "transcricao_json": tmp / f"{nome_base}_transcricao.json",
        "diarizacao_json": tmp / f"{nome_base}_diarizacao.json",
        "transcricao_md": trans / f"{nome_base}.md",
    }
```

- [ ] **Step 4: Implementar `scripts/01_transcrever.py`**

```python
"""Transcreve o WAV com faster-whisper. Uso: python 01_transcrever.py <nome_base>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths
from faster_whisper import WhisperModel


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    model = WhisperModel(
        cfg["whisper"]["model"],
        device=cfg["whisper"]["device"],
        compute_type=cfg["whisper"]["compute_type"],
    )
    segments, _ = model.transcribe(str(paths["wav"]), language="pt")
    resultado = [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segments
    ]
    paths["transcricao_json"].parent.mkdir(parents=True, exist_ok=True)
    with open(paths["transcricao_json"], "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Transcrição: {len(resultado)} falas → {paths['transcricao_json']}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 5: Implementar `scripts/02_diarizar.py`**

```python
"""Diarização com pyannote. Uso: python 02_diarizar.py <nome_base>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths
from pyannote.audio import Pipeline


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    pipeline = Pipeline.from_pretrained(
        cfg["diarizacao"]["model"],
        use_auth_token=Path.home() / ".cache/huggingface/token",
    )
    kwargs = {}
    if cfg["diarizacao"]["min_speakers"]:
        kwargs["min_speakers"] = cfg["diarizacao"]["min_speakers"]
    if cfg["diarizacao"]["max_speakers"]:
        kwargs["max_speakers"] = cfg["diarizacao"]["max_speakers"]
    diarization = pipeline(str(paths["wav"]), **kwargs)
    resultado = [
        {"start": round(turn.start, 2), "end": round(turn.end, 2), "speaker": speaker}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    with open(paths["diarizacao_json"], "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Diarização: {len(resultado)} segmentos → {paths['diarizacao_json']}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 6: Implementar `scripts/03_alinhar.py`**

```python
"""Cruza transcrição com diarização. Uso: python 03_alinhar.py <nome_base>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import audio_paths


def alinhar_falas(transcricao: list, diarizacao: list) -> list:
    falas = []
    for fala in transcricao:
        speaker = "Desconhecido"
        melhor_sobreposicao = 0.0
        for seg in diarizacao:
            inicio = max(fala["start"], seg["start"])
            fim = min(fala["end"], seg["end"])
            sobreposicao = max(0.0, fim - inicio)
            if sobreposicao > melhor_sobreposicao:
                melhor_sobreposicao = sobreposicao
                speaker = seg["speaker"]
        falas.append({**fala, "speaker": speaker})
    return falas


def main(nome_base: str):
    paths = audio_paths(nome_base)
    with open(paths["transcricao_json"], encoding="utf-8") as f:
        transcricao = json.load(f)
    with open(paths["diarizacao_json"], encoding="utf-8") as f:
        diarizacao = json.load(f)
    falas = alinhar_falas(transcricao, diarizacao)
    linhas = []
    for f in falas:
        t = f"{int(f['start']//60):02d}:{int(f['start']%60):02d}"
        linhas.append(f"**[{t}] {f['speaker']}:** {f['text']}")
    paths["transcricao_md"].parent.mkdir(parents=True, exist_ok=True)
    with open(paths["transcricao_md"], "w", encoding="utf-8") as f:
        f.write(f"# Transcrição — {nome_base}\n\n" + "\n\n".join(linhas) + "\n")
    print(f"Transcrição diarizada → {paths['transcricao_md']}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 7: Rodar o teste para passar**

Run: `python -m pytest scripts/test_alinhar.py -v`
Expected: PASS (2 testes).

- [ ] **Step 8: Criar `scripts/requirements.txt`**

```
faster-whisper==1.0.*
pyannote.audio==3.1.*
pyyaml==6.*
pytest==8.*
```

- [ ] **Step 9: Teste de integração — transcrição real**

```bash
# Usa o WAV de teste do Task 2 (ou grava 30s com a extensão)
.venv/bin/python scripts/01_transcrever.py 2026_09_09_14_30_teste_30s
.venv/bin/python scripts/02_diarizar.py 2026_09_09_14_30_teste_30s
.venv/bin/python scripts/03_alinhar.py 2026_09_09_14_30_teste_30s
```

Expected: JSONs em `_tmp/` e `.md` em `transcricoes/` com falas rotuladas. (Se `02_diarizar.py` falhar por token HF, seguir o Task 5 antes.)

- [ ] **Step 10: Commit**

```bash
git add scripts/
git commit -m "feat: pipeline de transcrição e diarização"
```

---

### Task 5: Script de notas (04) + integração Ollama

**Files:**
- Create: `scripts/04_notas.py`
- Test: `scripts/test_notas.py`

**Interfaces:**
- Consumes: `99_material/transcricoes/<nome_base>.md`; `config.yaml` (ollama).
- Produces: `99_material/notas/<nome_base>.md` com resumo executivo, tópicos, decisões e plano de ação.

- [ ] **Step 1: Escrever o teste que falha**

`scripts/test_notas.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notas import montar_prompt


def test_montar_prompt_inclui_transcricao():
    prompt = montar_prompt("transcrição de teste")
    assert "transcrição de teste" in prompt
    assert "resumo executivo" in prompt.lower()
    assert "plano de ação" in prompt.lower()
```

- [ ] **Step 2: Rodar o teste para ver falhar**

Run: `python -m pytest scripts/test_notas.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'notas'`.

- [ ] **Step 3: Implementar `scripts/04_notas.py`**

```python
"""Gera notas (resumo + plano de ação) via Ollama. Uso: python 04_notas.py <nome_base>"""
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths

PROMPT = """Você é um assistente que transforma transcrições de reuniões em notas estruturadas em português.

Transcrição:
{transcricao}

Gere:
1. **Resumo executivo** (máx. 150 palavras)
2. **Tópicos principais** (lista)
3. **Decisões tomadas** (lista; se não houver, diga "Nenhuma decisão explícita")
4. **Plano de ação** (tabela: Ação | Responsável | Prazo — use "—" quando não citado)

Formato: Markdown limpo, sem introdução nem conclusão."""


def montar_prompt(transcricao: str) -> str:
    return PROMPT.format(transcricao=transcricao)


def chamar_ollama(cfg: dict, prompt: str) -> str:
    provider = cfg["ollama"]["provider"]
    if provider == "local":
        url = "http://localhost:11434/api/generate"
        model = cfg["ollama"]["local_model"]
        payload = {"model": model, "prompt": prompt, "stream": False}
    else:
        url = cfg["ollama"]["cloud_base_url"].rstrip("/") + "/generate"
        model = cfg["ollama"]["cloud_model"]
        api_key = os.environ.get(cfg["ollama"]["cloud_api_key_env"], "")
        payload = {"model": model, "prompt": prompt, "stream": False}
        headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(url, json=payload, headers=headers if provider == "cloud" else {}, timeout=600)
    resp.raise_for_status()
    return resp.json()["response"]


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    transcricao = paths["transcricao_md"].read_text(encoding="utf-8")
    prompt = montar_prompt(transcricao)
    texto = chamar_ollama(cfg, prompt)
    paths["notas_dir"] = Path(cfg["caminhos"]["notas_dir"])
    paths["notas_dir"].mkdir(parents=True, exist_ok=True)
    destino = paths["notas_dir"] / f"{nome_base}.md"
    destino.write_text(f"# Notas — {nome_base}\n\n{texto}\n", encoding="utf-8")
    print(f"Notas → {destino}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 4: Rodar o teste para passar**

Run: `python -m pytest scripts/test_notas.py -v`
Expected: PASS.

- [ ] **Step 5: Teste de integração com Ollama local**

```bash
ollama list | grep qwen3.6
.venv/bin/python scripts/04_notas.py 2026_09_09_14_30_teste_30s
```

Expected: `99_material/notas/2026_09_09_14_30_teste_30s.md` criado com as 4 seções. (Se o Ollama local estiver parado, o script falha com erro claro — ok.)

- [ ] **Step 6: Commit**

```bash
git add scripts/04_notas.py scripts/test_notas.py
git commit -m "feat: geração de notas via Ollama"
```

---

### Task 6: Skills do OpenWork + automação de limpeza

**Files:**
- Create: `.opencode/skills/processar-gravacao/SKILL.md`
- Create: `.opencode/skills/limpar-material/SKILL.md`
- Create: `scripts/05_limpar.py`
- Test: `scripts/test_limpar.py`

**Interfaces:**
- Consumes: scripts 01–04; `config.yaml` (limpeza.dias_retencao_audio).
- Produces: skills acionáveis no chat; `scripts/05_limpar.py` apaga áudios com mais de 30 dias.

- [ ] **Step 1: Escrever o teste que falha**

`scripts/test_limpar.py`:

```python
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from limpar import limpar_audios_antigos


def test_limpar_apaga_so_antigos():
    with tempfile.TemporaryDirectory() as tmp:
        antigo = Path(tmp) / "2020_01_01_10_00_velho.wav"
        novo = Path(tmp) / "2026_09_09_10_00_novo.wav"
        antigo.write_bytes(b"x")
        novo.write_bytes(b"x")
        limpar_audios_antigos(tmp, dias=30)
        assert not antigo.exists()
        assert novo.exists()
```

- [ ] **Step 2: Rodar o teste para ver falhar**

Run: `python -m pytest scripts/test_limpar.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'limpar'`.

- [ ] **Step 3: Implementar `scripts/05_limpar.py`**

```python
"""Apaga áudios com mais de N dias. Uso: python 05_limpar.py"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config


def limpar_audios_antigos(audio_dir: str, dias: int) -> list:
    """Apaga .wav e .webm com data de modificação > dias. Retorna os apagados."""
    limite = datetime.now() - timedelta(days=dias)
    apagados = []
    for p in Path(audio_dir).glob("*.wav"):
        if datetime.fromtimestamp(p.stat().st_mtime) < limite:
            p.unlink()
            apagados.append(str(p))
    for p in Path(audio_dir).glob("*.webm"):
        if datetime.fromtimestamp(p.stat().st_mtime) < limite:
            p.unlink()
            apagados.append(str(p))
    return apagados


def main():
    cfg = load_config()
    apagados = limpar_audios_antigos(cfg["caminhos"]["audio_dir"], cfg["limpeza"]["dias_retencao_audio"])
    for a in apagados:
        print(f"Apagado: {a}")
    print(f"Total: {len(apagados)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar o teste para passar**

Run: `python -m pytest scripts/test_limpar.py -v`
Expected: PASS.

- [ ] **Step 5: Criar `.opencode/skills/processar-gravacao/SKILL.md`**

```markdown
---
name: processar-gravacao
description: Processa uma gravação de reunião: transcreve (Whisper), diariza vozes (pyannote) e gera notas (Ollama). Acionar quando o usuário pedir "processa a gravação", "processa a última gravação", "gera notas da reunião" ou similar.
---

# Processar Gravação

## Quando usar
Quando o usuário pedir para processar uma gravação de reunião/aula capturada pela extensão.

## Passos

1. **Identificar o áudio:**
   - Se o usuário deu um nome, use `99_material/audio/<nome>.wav`.
   - Se pediu "a última", liste `99_material/audio/*.wav` e use o mais recente (por mtime).
   - Se não houver áudio, avise e encerre.

2. **Rodar o pipeline** (da raiz do projeto, com o venv):
   ```bash
   .venv/bin/python scripts/01_transcrever.py <nome_base>
   .venv/bin/python scripts/02_diarizar.py <nome_base>
   .venv/bin/python scripts/03_alinhar.py <nome_base>
   .venv/bin/python scripts/04_notas.py <nome_base>
   ```
   - Inspecione cada saída intermediária em `99_material/transcricoes/_tmp/` antes de seguir.
   - Se o usuário pediu outro modelo ("usa o gemma4"), edite `config.yaml` (ollama.local_model) antes do passo 04 e restaure depois.

3. **Verificar qualidade:**
   - Se a diarização tiver muitos rótulos ou falas cruzadas, ajuste `config.yaml` (diarizacao.min_speakers/max_speakers) e re-rode o passo 02 e 03.
   - Se o Whisper estiver lento, troque `whisper.model` para `medium` e re-rode.

4. **Entregar:** mostre ao usuário o caminho da transcrição e das notas, e um resumo de 3-5 linhas do conteúdo.
```

- [ ] **Step 6: Criar `.opencode/skills/limpar-material/SKILL.md`**

```markdown
---
name: limpar-material
description: Apaga áudios com mais de 30 dias de 99_material/audio, mantendo transcrições e notas. Acionar quando o usuário pedir "limpa o material", "limpa os áudios antigos" ou similar.
---

# Limpar Material

## Quando usar
Quando o usuário pedir para limpar o material, ou via automação diária.

## Passos

1. Rodar da raiz do projeto:
   ```bash
   .venv/bin/python scripts/05_limpar.py
   ```

2. Reportar quantos arquivos foram apagados e quanto espaço foi liberado (`du -sh 99_material/audio` antes/depois).
```

- [ ] **Step 7: Teste manual das skills**

1. No chat: "processa a gravação de teste" → a skill roda o pipeline completo.
2. No chat: "limpa o material" → a skill roda a limpeza.

Expected: pipeline completo gera transcrição + notas; limpeza reporta 0 (nada antigo).

- [ ] **Step 8: Commit**

```bash
git add .opencode/skills/ scripts/05_limpar.py scripts/test_limpar.py
git commit -m "feat: skills do OpenWork e limpeza de material"
```

---

### Task 7: Automação diária de limpeza + README

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: skill `limpar-material`.
- Produces: automação diária 08:00 America/Sao_Paulo; README com instruções de uso.

- [ ] **Step 1: Criar `README.md`**

```markdown
# Gravador de Reuniões

Grava o áudio de reuniões/videoaulas no navegador (Meet, Teams web, Zoom web, YouTube), transcreve com Whisper, diariza vozes com pyannote e gera notas com Ollama — tudo local, orquestrado pelo OpenWork.

## Estrutura

```
extension/   → extensão Chrome (MV3)
server/      → servidor local de captura (FastAPI, 127.0.0.1:8765)
scripts/     → pipeline: 01 transcrever, 02 diarizar, 03 alinhar, 04 notas, 05 limpar
.opencode/skills/ → skills processar-gravacao e limpar-material
99_material/ → áudios, transcrições e notas (separado do código)
```

## Uso

1. **Subir o servidor:** `./start.sh`
2. **Carregar a extensão:** `chrome://extensions` → Modo desenvolvedor → "Carregar sem compactação" → pasta `extension/`
3. **Gravar:** abra a reunião, clique no ícone, digite o nome, clique **Gravar**; clique **Parar** ao final.
4. **Processar:** no chat do OpenWork, peça "processa a gravação de hoje".
5. **Limpar:** a automação diária apaga áudios com mais de 30 dias (ou peça "limpa o material").

## Configuração

- `config.yaml`: modelo do Whisper, modelo do Ollama (local/cloud), caminhos, retenção.
- Diarização exige token do HuggingFace (uma vez): criar conta em huggingface.co, aceitar os termos de `pyannote/speaker-diarization-3.1` e salvar o token em `~/.cache/huggingface/token`.

## Dependências

- Python 3.11+, ffmpeg, Ollama (local ou cloud com API key).
```

- [ ] **Step 2: Criar a automação diária**

No chat do OpenWork, pedir: "cria uma automação diária às 08:00 (America/Sao_Paulo) que roda a skill limpar-material neste workspace".

Expected: automação criada e listada em Automations.

- [ ] **Step 3: Teste final de ponta a ponta**

1. `./start.sh` → servidor de pé.
2. Gravar 30s de um vídeo do YouTube com a extensão.
3. No chat: "processa a gravação" → transcrição diarizada + notas geradas.
4. Verificar `99_material/` completo (audio, transcricoes, notas).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README com instruções de uso"
```

---

## Self-Review

- **Spec coverage:** Seção 2 (estrutura) → Task 1; Seção 3-4 (extensão/servidor) → Tasks 2-3; Seção 5 (pipeline) → Tasks 4-5; Seção 6 (skills/automação) → Tasks 6-7; Seção 7 (erros) → coberto nos passos de verificação das skills e testes; Seção 8 (testes) → passos de teste de cada task; Seção 9 (fora do escopo) → nada implementado.
- **Placeholder scan:** sem TBD/TODO; todo passo tem código ou comando concreto.
- **Type consistency:** `load_config()` e `audio_paths()` definidos no Task 4 e usados nos Tasks 5-6; `alinhar_falas()` definido no Task 4 e testado; `limpar_audios_antigos()` definido no Task 6 e testado; `montar_prompt()` definido no Task 5 e testado.

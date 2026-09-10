# 🗺️ Mapa do Projeto — Gravador de Reuniões

Este documento descreve **todos os scripts, skills e arquivos de configuração** do projeto e para que servem.

---

## 🧩 Skills do OpenWork (acionáveis no chat)

As skills ficam em `.opencode/skills/` e são carregadas pelo agente quando você pede algo no chat.

### `processar-gravacao`
**Acionada por:** "processa a gravação de hoje", "processa a última gravação", "processa <nome>", "gera notas da reunião"

**O que faz:**
1. Localiza o evento em `99_material/<evento>/audio/` (o mais recente, ou o nome que você deu)
2. Roda o pipeline completo em sequência: `01_transcrever.py` → `02_diarizar.py` → `03_alinhar.py` → `04_notas.py`
3. Inspeciona cada saída intermediária (em `99_material/<evento>/transcricoes/_tmp/`) antes de seguir
4. Se a diarização vier ruim (rótulos demais, falas cruzadas), ajusta `min_speakers`/`max_speakers` no `config.yaml` e re-roda
5. Se o Whisper estiver lento, troca para `medium` e re-roda
6. Salva a transcrição diarizada e as notas, e mostra um resumo do que foi gerado

**Modelo:** usa o `ollama.local_model`/`ollama.cloud_model` do `config.yaml`. Você pode trocar na hora: *"usa o gemma4 desta vez"*.

---

### `limpar-material`
**Acionada por:** "limpa o material", "limpa os áudios antigos" — ou pela automação diária (08:00)

**O que faz:**
1. Roda `05_limpar.py`
2. Apaga a pasta `audio/` de eventos com mais de `limpeza.dias_retencao_audio` dias (padrão: 30)
3. **Mantém** transcrições e notas de cada evento
4. Reporta quantos arquivos foram apagados e o espaço liberado

---

## 🐍 Scripts do pipeline (`scripts/`)

> **Estrutura:** cada gravação é um evento — `99_material/<evento>/` com `audio/`, `transcricoes/` e `notas/`. O `<nome_base>` é o nome do evento (`YYYY_MM_DD_HH_MM_<nome>`).

### `01_transcrever.py` — Transcrição (Whisper)
- **Entrada:** `99_material/<evento>/audio/<evento>.wav`
- **Saída:** `99_material/<evento>/transcricoes/_tmp/<evento>_transcricao.json` (lista de `{start, end, text}`)
- **Tecnologia:** faster-whisper (local, Apple Silicon), modelo `large-v3` (configurável)
- **Uso:** `.venv/bin/python scripts/01_transcrever.py <nome_base>`

### `02_diarizar.py` — Diarização de vozes (pyannote)
- **Entrada:** `99_material/<evento>/audio/<evento>.wav`
- **Saída:** `99_material/<evento>/transcricoes/_tmp/<evento>_diarizacao.json` (lista de `{start, end, speaker}`)
- **Tecnologia:** pyannote.audio (`speaker-diarization-3.1`), token do HuggingFace lido do `.env`
- **Uso:** `.venv/bin/python scripts/02_diarizar.py <nome_base>`
- **Nota:** na 1ª execução baixa os modelos (~1GB, uma única vez)

### `03_alinhar.py` — Alinhamento (transcrição × diarização)
- **Entrada:** os dois JSONs acima
- **Saída:** `99_material/<evento>/transcricoes/<evento>.md` (falas diarizadas com timestamps)
- **Lógica:** cada fala do Whisper recebe o rótulo do segmento de diarização que cobre o intervalo (sobreposição máxima)
- **Uso:** `.venv/bin/python scripts/03_alinhar.py <nome_base>`

### `04_notas.py` — Geração de notas (Ollama)
- **Entrada:** `99_material/<evento>/transcricoes/<evento>.md`
- **Saída:** `99_material/<evento>/notas/<evento>.md` (resumo executivo, tópicos, decisões, plano de ação)
- **Tecnologia:** Ollama local (`http://localhost:11434`) ou cloud (OpenAI-compatible `/v1/chat/completions`), conforme `config.yaml`
- **Uso:** `.venv/bin/python scripts/04_notas.py <nome_base>`

### `05_limpar.py` — Limpeza de áudios antigos
- **Entrada:** `99_material/` (eventos com `audio/`)
- **Saída:** pasta `audio/` de eventos com mais de `limpeza.dias_retencao_audio` dias apagada (transcrições e notas mantidas)
- **Uso:** `.venv/bin/python scripts/05_limpar.py`

---

## 🧩 Módulos de apoio (`scripts/`)

| Arquivo | Função |
|---|---|
| `common.py` | `load_config()` (lê `config.yaml`) e `audio_paths(nome_base)` (caminhos padronizados) |
| `alinhar.py` | Lógica pura de alinhamento (testável, usada pelo `03_alinhar.py`) |
| `notas.py` | Lógica de prompt e chamada ao Ollama (testável, usada pelo `04_notas.py`) |
| `limpar.py` | Lógica pura de limpeza (testável, usada pelo `05_limpar.py`) |
| `test_alinhar.py` | Testes do alinhamento |
| `test_notas.py` | Testes do prompt de notas |
| `test_limpar.py` | Testes da limpeza |
| `requirements.txt` | Dependências do pipeline (faster-whisper, pyannote, huggingface_hub, numpy, pyyaml, pytest) |

---

## 🌐 Servidor local (`server/`)

| Arquivo | Função |
|---|---|
| `main.py` | API FastAPI: `GET /health` e WebSocket `/ws`. Recebe áudio da extensão (canais `tab` e `mic`), valida Origin e nome, salva e mixa. Escuta só em `127.0.0.1:8765` |
| `audio_store.py` | `AudioStore`: salva os brutos (`.pcm` de cada canal em `bruto/`) e mixa em `.wav` 16kHz mono via ffmpeg |
| `test_audio_store.py` | Teste do fluxo de armazenamento + mixagem |
| `requirements.txt` | Dependências do servidor (fastapi, uvicorn, websockets, pytest) |

---

## 🧩 Extensão Chrome (`extension/`)

| Arquivo | Função |
|---|---|
| `manifest.json` | Manifesto MV3: permissões (`tabCapture`, `offscreen`, `storage`, `scripting`), host permissões para `127.0.0.1:8765` e `<all_urls>` |
| `popup.html` / `popup.js` | Interface: campo nome + botão Gravar/Parar + timer. Checa se o servidor está online antes de gravar |
| `background.js` | Service worker: cria/gerencia o offscreen document, obtém o `streamId` da aba, repassa mensagens, persiste estado em `chrome.storage.session` |
| `offscreen.html` / `offscreen.js` | Página oculta que de fato captura (única com acesso a `mediaDevices`/`AudioContext`): captura aba + microfone, usa `AudioWorkletNode` (API moderna) e envia PCM16 via WebSocket |
| `worklet.js` | Processador de áudio (AudioWorklet): converte Float32 → PCM16 (acumulando 4096 samples) em thread própria e envia ao offscreen via `port.postMessage()` |
| `toaster-content.js` | Content script: injeta o controle flutuante (toast) na página — ponto vermelho, timer e botão Parar no canto inferior direito |
| `icons/` | Ícones 16/48/128 |

**Fluxo de mensagens:** popup → `chrome.runtime.sendMessage` → background (service worker) → offscreen document → WebSocket → servidor.

---

## ⚙️ Configuração e infraestrutura

| Arquivo | Função |
|---|---|
| `config.yaml` | Configuração central: modelo do Whisper, diarização, Ollama (local/cloud), caminhos, retenção de áudio |
| `.env` (não versionado) | Token do HuggingFace (`HUGGINGFACE_TOKEN=`) — copie de `.env.example` |
| `.env.example` | Modelo do `.env` com instruções |
| `start.sh` | Sobe o servidor: cria o venv na 1ª vez, instala dependências (server + scripts), inicia uvicorn em `127.0.0.1:8765` |
| `.gitignore` | Ignora `.env`, `.venv`, `99_material/` (conteúdo gerado) |
| `99_material/` | Material gerado: um diretório por evento (`<evento>/audio/` com `bruto/`, `transcricoes/` com `_tmp/`, `notas/`) |

---

## 🔄 Fluxo completo (visão geral)

```
[Chrome] extensão captura aba + mic
    │  WebSocket (PCM16, canais tab/mic)
    ▼
[Servidor] 127.0.0.1:8765 → salva brutos → mixa em .wav 16kHz mono
    │
    ▼
[Chat OpenWork] "processa a gravação de hoje" → skill processar-gravacao
    │
    ├─ 01_transcrever.py  → transcricao.json (timestamps)
    ├─ 02_diarizar.py     → diarizacao.json (Falante 1, 2...)
    ├─ 03_alinhar.py      → <evento>/transcricoes/<evento>.md (diarizado)
    └─ 04_notas.py        → <evento>/notas/<evento>.md (resumo + plano de ação)
    │
    ▼
[Automação diária 08:00] skill limpar-material → apaga áudios > 30 dias
```

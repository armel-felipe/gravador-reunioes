# 🗺️ Mapa do Projeto — Gravador de Reuniões

Este documento descreve **todos os scripts, skills e arquivos de configuração** do projeto e para que servem.

---

## 🧩 Skills do OpenWork (acionáveis no chat)

As skills ficam em `.opencode/skills/` e são carregadas pelo agente quando você pede algo no chat.
A fonte canônica de manutenção é `.opencode/skills/{skill}/SKILL.md` — a governança e a regra de execução estão em `AGENTS.md`.

### `processar-gravacao`
**Acionada por:** "processa a gravação de hoje", "processa a última gravação", "processa <nome>", "gera notas da reunião"

**O que faz:**
1. Localiza o evento em `99_material/<evento>/audio/` (o mais recente, ou o nome que você deu)
2. Inicia um job local one-shot via `07_processar.py`; a resposta do chat retorna sem esperar o pipeline longo
3. O worker roda em sequência: `01_transcrever.py` → `02_diarizar.py` → `fundir.py` → `03_alinhar.py` → `04_notas.py`
4. Persiste status e logs por evento, valida saídas e pode retomar após falha sem repetir etapas concluídas
5. Para todas as pendentes, cria um snapshot e processa eventos sequencialmente; não instala agenda recorrente
6. Consulte jobs com `status`; retome com `resume --job-id`, `resume --evento` ou `resume --pendentes`
7. Só informa conclusão após notas finais estarem gravadas e validadas

**Modelo:** usa o perfil selecionado em `llm.active` no `config.yaml`. O padrão é `llama-cpp` (`http://100.87.71.48:18080/v1`, `qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-compact`). Um ID pedido explicitamente vai como override por job, sem alterar `config.yaml`. Os outros perfis disponíveis são `ollama-local`, `ollama-cloud`, `llm-studio` e `openrouter`.

**Qualidade do prompt:** local e Cloud recebem o mesmo prompt. A geração deve preservar nomes, empresas, números, datas, decisões, responsáveis e prazos, sem inventar informações, com saída concisa.

---

### `limpar-material`
**Acionada por:** "limpa o material", "limpa os áudios antigos" — ou pela automação diária (08:00)

**O que faz:**
1. Roda `05_limpar.py`
2. Apaga a pasta `audio/` de eventos com mais de `limpeza.dias_retencao_audio` dias (padrão: 30)
3. **Mantém** transcrições e notas de cada evento
4. Reporta quantos arquivos foram apagados e o espaço liberado

---

### `subir-servidor`
**Acionada por:** "sobe o servidor", "inicia o servidor", "liga o gravador", "para o servidor", "desliga o gravador"

**O que faz:**
1. Checa se já está no ar (`curl http://127.0.0.1:8765/health`) e evita subir duplicado
2. Sobe o `./start.sh` **desacoplado da sessão** via `launchctl submit` (job `com.armel.gravador-servidor`) — sobrevive ao fechamento do terminal/app
3. Confirma que o `/health` responde `{"status":"ok"}` e informa PID e log (`/tmp/gravador_server.log`)
4. **Parar:** checa se está no ar, remove o job com `launchctl remove com.armel.gravador-servidor` e confirma que o job sumiu do `launchctl` e a porta parou de responder

O popup da extensão também controla o mesmo job depois que o host Native Messaging é instalado. O desligamento pede confirmação e encerra uma gravação ativa antes de remover o job.

---

## 🐍 Scripts do pipeline (`scripts/`)

> **Estrutura:** cada gravação é um evento — `99_material/<evento>/` com `audio/`, `transcricoes/` e `notas/`. O `<nome_base>` é o nome do evento (`YYYY_MM_DD_HH_MM_<nome>`).

### `01_transcrever.py` — Transcrição (Whisper)
- **Entrada:** `99_material/<evento>/audio/<evento>.wav`
- **Saída:** `99_material/<evento>/transcricoes/_tmp/<evento>_transcricao.json` (lista de `{start, end, text}`)
- **Tecnologia:** faster-whisper (local, Apple Silicon), modelo `turbo` (large-v3-turbo, ~1,6 GB baixado na 1ª execução; configurável via `whisper.model`)
- **Uso:** `.venv/bin/python scripts/01_transcrever.py <nome_base>`

### `02_diarizar.py` — Diarização de vozes (pyannote)
- **Entrada:** `99_material/<evento>/audio/<evento>.wav`
- **Saída:** `99_material/<evento>/transcricoes/_tmp/<evento>_diarizacao.json` (lista de `{start, end, speaker}`)
- **Tecnologia:** pyannote.audio (`speaker-diarization-3.1`), token do HuggingFace lido do `.env`
- **Uso:** `.venv/bin/python scripts/02_diarizar.py <nome_base>`
- **Nota:** na 1ª execução baixa os modelos (~1GB, uma única vez)

### `fundir.py` — Fusão de speakers (embeddings de voz)
- **Entrada:** `99_material/<evento>/transcricoes/_tmp/<evento>_diarizacao.json`
- **Saída:** o mesmo JSON com os rótulos remapeados (ex.: 5 "Falantes" → 3)
- **Lógica:** extrai o embedding médio de voz de cada speaker (até 20 segmentos mais longos, pyannote) e funde dois speakers apenas quando a similaridade cosine é ≥ limiar — configurável em `diarizacao.limiar_fusao` do `config.yaml` (default do código: 0,85) — sem heurística de duração/vizinhança. Speakers sem embedding (só falas < 0,5s) ficam com o próprio rótulo, sem quebrar
- **Uso:** `.venv/bin/python scripts/fundir.py <nome_base>`

### `03_alinhar.py` — Alinhamento (transcrição × diarização)
- **Entrada:** os dois JSONs acima
- **Saída:** `99_material/<evento>/transcricoes/<evento>.md` (falas diarizadas com timestamps)
- **Lógica:** cada fala do Whisper recebe o rótulo do segmento de diarização que cobre o intervalo (sobreposição máxima)
- **Uso:** `.venv/bin/python scripts/03_alinhar.py <nome_base>`

### `04_notas.py` — Geração de notas (LLM)
- **Entrada:** `99_material/<evento>/transcricoes/<evento>.md`
- **Saída:** `99_material/<evento>/notas/<evento>.md` (resumo executivo, tópicos, decisões, plano de ação)
- **Tecnologia:** o perfil `llm.active` seleciona entre llama.cpp, LM Studio, Ollama local, Ollama Cloud e OpenRouter; cada perfil define sua própria URL, modelo e autenticação. O padrão é llama.cpp com `qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-compact`.
- **Uso:** `.venv/bin/python scripts/04_notas.py <nome_base> [--modelo <ID>]` (override apenas nesta execução)

### `05_limpar.py` — Limpeza de áudios antigos
- **Entrada:** `99_material/` (eventos com `audio/`)
- **Saída:** pasta `audio/` de eventos com mais de `limpeza.dias_retencao_audio` dias apagada (transcrições e notas mantidas)
- **Uso:** `.venv/bin/python scripts/05_limpar.py`

### `06_pendentes.py` — Lista de pendentes
- **Entrada:** `99_material/`
- **Saída:** eventos com áudio mas **sem** `notas/<evento>.md` (o arquivo de notas é o marcador de "processado")
- **Uso:** `.venv/bin/python scripts/06_pendentes.py`

### `07_processar.py` — Jobs locais sob demanda
- **Entrada:** `start --evento <nome_base>` ou `start --pendentes` (snapshot atual)
- **Saída:** job ID imediato; manifesto em `99_material/.processamento/jobs/`, estado e log em cada evento
- **Lógica:** submete um worker one-shot via `launchctl`; não depende do tempo limite do chat. `status` lista jobs recentes; `resume` retoma etapas ausentes usando saídas válidas. Repouso do Mac pausa o job.
- **Uso:** `.venv/bin/python scripts/07_processar.py start --evento <nome_base>`; `status`; `resume --job-id <job_id>`

---

## 🧩 Módulos de apoio (`scripts/`)

| Arquivo | Função |
|---|---|
| `common.py` | `load_config()` (lê `config.yaml`) e `audio_paths(nome_base)` (caminhos padronizados) |
| `alinhar.py` | Lógica pura de alinhamento (testável, usada pelo `03_alinhar.py`) |
| `notas.py` | Lógica de prompt e chamada ao Ollama (testável, usada pelo `04_notas.py`) |
| `limpar.py` | Lógica pura de limpeza (testável, usada pelo `05_limpar.py`) |
| `pendentes.py` | Lógica de listagem de pendentes (testável, usada pelo `06_pendentes.py`) |
| `processamento.py` | Manifestos, locks por evento, validação de etapas, logs e worker sequencial dos jobs locais |
| `test_processamento.py` | Testes de persistência, retomada, lotes, status e submissão do launchd |
| `test_alinhar.py` | Testes do alinhamento |
| `test_notas.py` | Testes do prompt de notas |
| `test_limpar.py` | Testes da limpeza |
| `test_pendentes.py` | Testes da listagem de pendentes |
| `test_fundir.py` | Testes da fusão de speakers (inclui regressão do `KeyError` de speaker sem embedding) |
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
| `manifest.json` | Manifesto MV3 com captura, offscreen, armazenamento, scripting e `nativeMessaging` |
| `popup.html` / `popup.js` | Estado do servidor, ligar/desligar com confirmação e gravação |
| `server-control.js` | Estados e polling do health check |
| `background.js` | Coordena gravação, parada segura e mensagens Native Messaging |
| `offscreen.html` / `offscreen.js` | Página oculta que de fato captura (única com acesso a `mediaDevices`/`AudioContext`): captura aba + microfone, usa `AudioWorkletNode` (API moderna) e envia PCM16 via WebSocket |
| `worklet.js` | Processador de áudio (AudioWorklet): converte Float32 → PCM16 (acumulando 4096 samples) em thread própria e envia ao offscreen via `port.postMessage()` |
| `toaster-content.js` | Content script: injeta o controle flutuante (toast) na página — ponto vermelho, timer e botão Parar no canto inferior direito |
| `icons/` | Ícones 16/48/128 |

**Fluxo de mensagens:** popup → `chrome.runtime.sendMessage` → background (service worker) → offscreen document → WebSocket → servidor.

---

## ⚙️ Configuração e infraestrutura

| Arquivo | Função |
|---|---|
| `AGENTS.md` | Porta de entrada para agentes: governança das skills, regra de execução, servidor local e regras críticas |
| `config.yaml` | Configuração central: modelo do Whisper, diarização, Ollama (local/cloud), caminhos, retenção de áudio |
| `.env` (não versionado) | Token do HuggingFace (`HUGGINGFACE_TOKEN=`) — copie de `.env.example` |
| `.env.example` | Modelo do `.env` com instruções |
| `.opencode/skills/` | Skills operacionais acionáveis no chat (`subir-servidor`, `processar-gravacao`, `limpar-material`) |
| `start.sh` | Sobe o servidor: cria o venv na 1ª vez, instala dependências (server + scripts), inicia uvicorn em `127.0.0.1:8765` |
| `native_host/server_control.py` | Host Native Messaging: aceita somente `status`, `start` e `stop`, usando health check e `launchctl` |
| `native_host/install_native_host.sh` | Registra o host no Chrome para o usuário atual |
| `.gitignore` | Ignora `.env`, `.venv`, `99_material/` (conteúdo gerado) |
| `99_material/` | Material gerado: um diretório por evento (`<evento>/audio/` com `bruto/`, `transcricoes/` com `_tmp/`, `notas/`) |

---

## 🔄 Fluxo completo (visão geral)

```
[Chat] "sobe o servidor" / "para o servidor" → skill subir-servidor → ./start.sh / launchctl remove (launchd, 127.0.0.1:8765)
    │
    ▼
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
    ├─ fundir.py          → funde speakers por similaridade de voz
    ├─ 03_alinhar.py      → <evento>/transcricoes/<evento>.md (diarizado)
    └─ 04_notas.py        → <evento>/notas/<evento>.md (resumo + plano de ação)
    │
    ▼
[Automação diária 08:00] skill limpar-material → apaga áudios > 30 dias
```

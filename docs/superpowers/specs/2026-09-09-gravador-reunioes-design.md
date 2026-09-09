# Design — Gravador de Reuniões com Transcrição e Notas (Chrome + OpenWork)

**Data:** 2026-09-09
**Status:** Aprovado pelo usuário

## 1. Visão geral

Extensão do Chrome que grava o áudio de reuniões/videoaulas no navegador (Google Meet, Teams web, Zoom web, YouTube etc.), combinado com o microfone local do usuário. O processamento — transcrição (Whisper), diarização de vozes (pyannote) e geração de notas (LLM via Ollama local ou cloud) — é orquestrado de forma **agêntica pelo OpenWork**, disparado por skills no chat, e não por um pipeline automático no servidor.

**Uso:** pessoal, 100% local (exceto opção de LLM via Ollama cloud com API key).
**Plataforma:** macOS (Apple Silicon), navegador Chrome.

## 2. Estrutura de pastas

```
projeto/
├── extension/          ← código da extensão Chrome (Manifest V3)
├── server/             ← servidor local de captura (Python/FastAPI)
├── scripts/             ← pipeline de processamento (whisper, diarização, notas)
├── .opencode/skills/    ← skills do OpenWork (processar-gravacao, limpar-material)
├── config.yaml         ← configuração central (modelos, caminhos)
├── start.sh            ← sobe o servidor local
└── 99_material/        ← só material, nada de código (pasta ordena no fim do Finder)
    ├── audio/
    │   ├── bruto/      ← webm separados (tab + mic)
    │   └── YYYY_MM_DD_HH_MM_<nome>.wav   ← mixado, pronto para processar
    ├── transcricoes/
    │   ├── _tmp/       ← intermediários do pipeline (idempotência)
    │   └── YYYY_MM_DD_HH_MM_<nome>.md    ← falas diarizadas com timestamps
    └── notas/
        └── YYYY_MM_DD_HH_MM_<nome>.md    ← resumo + plano de ação
```

- A subpasta de material começa com `99_` para ordenar no fim do Finder e facilitar a limpeza.
- Código e material são totalmente separados.

## 3. Extensão Chrome (Manifest V3)

**Popup:**
- Campo "Nome da reunião" (obrigatório antes de gravar).
- Botão **Gravar/Parar** com timer de duração.
- Estado persistente: fechar o popup não interrompe a gravação (service worker mantém a captura).
- Se o servidor estiver offline (`/health`), avisa "Servidor offline — rode `./start.sh`" e não grava.

**Captura (opção B aprovada):**
- Ao clicar Gravar, inicia **duas capturas em paralelo**:
  1. `tabCapture` → áudio da aba ativa (participantes remotos, vídeo).
  2. `getUserMedia` → microfone local do usuário.
- Transmite os dois streams em tempo real via WebSocket para `ws://127.0.0.1:8765`, cada um em canal próprio (tags `tab` e `mic`).
- Ao clicar Parar, encerra capturas e fecha a conexão.

**Nomeação do arquivo:** `YYYY_MM_DD_HH_MM_<nome>.webm` (data/hora local no momento de gravar + nome digitado no popup).

## 4. Servidor local de captura (Python/FastAPI)

- Escuta **somente em `127.0.0.1:8765`** — nada exposto à rede.
- Recebe chunks de áudio via WebSocket (canais `tab` e `mic`).
- Salva os brutos em `99_material/audio/bruto/` (`..._tab.webm` e `..._mic.webm`).
- Converte e **mixa** os dois em um único `.wav` 16kHz mono (formato ideal para Whisper), com ganho balanceado entre os canais.
- `start.sh` sobe o servidor com um comando.
- **Não processa nada** — é apenas o funil de captura.

## 5. Pipeline de processamento (scripts modulares)

Cada script tem entrada/saída clara e é idempotente (re-rodar não corrompe nada).

```
99_material/audio/YYYY_MM_DD_HH_MM_<nome>.wav
        │
        ▼
01_transcrever.py   → faster-whisper (local, Apple Silicon)
        │            → saída: transcrição com timestamps (JSON)
        ▼
02_diarizar.py      → pyannote.audio (local)
        │            → saída: segmentos de fala com rótulos (Falante 1, Falante 2…)
        ▼
03_alinhar.py       → cruza timestamps do Whisper com segmentos da diarização
        │            → saída: transcrição diarizada em .md
        ▼
04_notas.py         → envia a transcrição para o LLM (Ollama local ou cloud)
                     → saída: resumo + plano de ação + decisões (.md)
```

**Decisões técnicas:**
- **Whisper:** `faster-whisper` com modelo `large-v3` (melhor qualidade em pt-BR); trocável para `medium` via `config.yaml` sem tocar em código.
- **Diarização:** `pyannote.audio` (`speaker-diarization-3.1`). Requer token gratuito do HuggingFace (criar conta + aceitar termos, ~2 min) para baixar modelos uma única vez (~1GB). Depois, tudo local.
- **Alinhamento:** sobreposição de intervalos — cada fala do Whisper recebe o rótulo do segmento de diarização que cobre o intervalo. A voz do usuário entra como "Falante" normal (label "Você" fica para a evolução C — mapa de vozes).
- **Notas:** `04_notas.py` lê `config.yaml` para escolher o modelo — local (`qwen3.6:35b-mlx`, `gemma4:26b-mlx`, etc.) ou Ollama cloud (via API key). Prompt gera: resumo executivo, tópicos, decisões, plano de ação com responsáveis/prazos quando citados.
- **Config central:** `config.yaml` define modelo do Whisper, modelo do Ollama (local/cloud), caminhos. Troca de modelo sem tocar em código.

## 6. Camada agêntica (OpenWork)

**Skills locais do projeto (`.opencode/skills/`):**

1. **`processar-gravacao`** — acionada por *"processa a gravação de hoje"* / *"processa a última gravação"*:
   - Localiza o áudio indicado em `99_material/audio/`.
   - Roda os scripts 01→04 em sequência, inspecionando saídas intermediárias.
   - Se a diarização vier ruim (rótulos demais, falas cruzadas), ajusta parâmetros (`min_speakers`/`max_speakers`) e re-roda.
   - Salva transcrição e notas; mostra resumo do que foi gerado.
   - Usa o modelo do `config.yaml`; troca sob demanda no chat (*"usa o gemma4 desta vez"*).

2. **`limpar-material`** — apaga áudios com mais de 30 dias (mantendo transcrições e notas). Roda manualmente ou via automação.

**Automação:** automação diária do OpenWork (08:00, America/Sao_Paulo) executa `limpar-material`.

**Fluxo do dia a dia:**
1. `./start.sh` → servidor de pé.
2. Reunião → clica Gravar (nome) → clica Parar.
3. No chat: *"processa a gravação de ontem"* → agente faz tudo.
4. Limpeza: skill manual ou automação diária.

## 7. Tratamento de erros

| Cenário | Comportamento |
|---|---|
| Servidor offline ao clicar Gravar | Popup avisa e não grava |
| Gravação interrompida (aba fechada, navegador caiu) | O que chegou ao servidor é salvo; arquivo parcial processável |
| Whisper lento / sem memória | Troca `large-v3` → `medium` via config |
| Diarização ruim | Skill re-roda com `min_speakers`/`max_speakers` ajustados |
| LLM offline (Ollama parado) | Skill avisa e oferece trocar para Ollama cloud (ou vice-versa) |
| Falha no meio do pipeline | Scripts idempotentes; intermediários em `transcricoes/_tmp/` |

## 8. Testes

1. **Servidor:** `start.sh` sobe; `curl http://127.0.0.1:8765/health` responde.
2. **Extensão:** gravar 30s de vídeo do YouTube → `.wav` aparece com nome correto.
3. **Whisper:** `01_transcrever.py` num áudio de teste → JSON com timestamps.
4. **Diarização:** `02_diarizar.py` → segmentos com rótulos.
5. **Pipeline completo:** gravação real → transcrição diarizada + notas legíveis.
6. **Limpeza:** áudio com data antiga (touch) → skill apaga só o que tem +30 dias.

## 9. Fora do escopo (YAGNI — evolução futura sem refazer nada)

- Mapa de vozes (voz → nome real) — evolução C.
- Detecção automática de início de reunião.
- Interface web para revisar/editar transcrições.
- Apps desktop (Teams/Zoom instalados) — navegador apenas.

## 10. Dependências externas

- **HuggingFace token gratuito** (única dependência): para baixar os modelos de diarização do pyannote (~1GB, uma única vez).
- **Ollama** (local ou cloud com API key) para geração de notas.
- **ffmpeg** para conversão/mixagem de áudio.

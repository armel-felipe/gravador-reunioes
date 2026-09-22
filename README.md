# Gravador de Reuniões

Grava o áudio de reuniões e videoaulas no navegador (Google Meet, Teams web, Zoom web, YouTube), transcreve com **Whisper**, separa as vozes com **diarização (pyannote)** e gera **notas, resumo e plano de ação** com **Ollama** — localmente por padrão, com opção de Ollama Cloud, orquestrado pelo OpenWork.

> **Como funciona:** a extensão do Chrome captura o áudio da aba + seu microfone e envia para um servidor local. O processamento (transcrição → diarização → notas) é disparado por você no chat do OpenWork, usando skills e scripts — não é um pipeline automático.

---

## ✨ Funcionalidades

- 🎙️ **Gravação no navegador** — captura o áudio da aba (participantes, vídeo) + seu microfone, mixados em um único arquivo
- 📝 **Transcrição** — Whisper (faster-whisper, local) com timestamps
- 👥 **Diarização de vozes** — pyannote separa os falantes automaticamente ("Falante 1", "Falante 2"...)
- 📋 **Notas automáticas** — resumo executivo, tópicos, decisões e plano de ação gerados por LLM (Ollama local ou cloud)
- 🗂️ **Material organizado** — áudios, transcrições e notas separados do código, em `99_material/` (ordena no fim do Finder)
- 🧹 **Limpeza automática** — áudios com mais de 30 dias são apagados (mantendo transcrições e notas)
- 🔒 **100% local** — exceto a opção de usar Ollama cloud (com sua API key)

---

## 📁 Estrutura do projeto

```
projeto/
├── extension/              ← extensão Chrome (Manifest V3)
│   ├── manifest.json       ← configuração da extensão
│   ├── popup.html/js       ← interface Gravar/Parar
│   ├── background.js       ← service worker (gerencia captura)
│   ├── offscreen.html/js   ← página oculta que captura o áudio
│   └── icons/              ← ícones da extensão
├── server/                 ← servidor local de captura (Python/FastAPI)
│   ├── main.py             ← API + WebSocket (127.0.0.1:8765)
│   ├── audio_store.py      ← salva áudio bruto e mixa em .wav
│   └── requirements.txt   ← dependências do servidor
├── scripts/                ← pipeline de processamento
│   ├── 01_transcrever.py   ← Whisper: áudio → transcrição com timestamps
│   ├── 02_diarizar.py      ← pyannote: áudio → segmentos de fala por voz
│   ├── 03_alinhar.py       ← cruza transcrição + diarização → .md diarizado
│   ├── 04_notas.py         ← Ollama: transcrição → resumo + plano de ação
│   ├── 05_limpar.py        ← apaga áudios com mais de 30 dias
│   ├── 06_pendentes.py     ← lista eventos com áudio mas sem notas (pendentes)
│   ├── common.py           ← config + caminhos compartilhados
│   ├── alinhar.py          ← lógica de alinhamento (testável)
│   ├── notas.py            ← lógica de notas (testável)
│   ├── limpar.py           ← lógica de limpeza (testável)
│   └── requirements.txt     ← dependências do pipeline
├── .opencode/skills/       ← skills do OpenWork (acionáveis no chat)
│   ├── subir-servidor/     ← "sobe o servidor"
│   ├── processar-gravacao/ ← "processa a gravação de hoje"
│   └── limpar-material/    ← "limpa o material"
├── config.yaml             ← configuração central (modelos, caminhos, retenção)
├── .env.example            ← modelo do .env (token HuggingFace)
├── start.sh                ← sobe o servidor local
└── 99_material/            ← material gerado (separado do código)
    └── YYYY_MM_DD_HH_MM_<nome>/   ← um diretório por gravação (evento)
        ├── audio/
        │   ├── YYYY_MM_DD_HH_MM_<nome>.wav  ← mixado, pronto para processar
        │   └── bruto/      ← gravações brutas (tab + mic separados)
        ├── transcricoes/   ← transcrições diarizadas (.md) + _tmp/
        └── notas/          ← resumos + planos de ação (.md)
```

---

## 🚀 Instalação (em qualquer computador)

### Pré-requisitos

| Dependência | Onde conseguir | Por quê |
|---|---|---|
| **macOS** (Apple Silicon recomendado) | — | Whisper e pyannote rodam melhor com Metal |
| **Python 3.11+** | `brew install python@3.11` | Scripts e servidor |
| **ffmpeg** | `brew install ffmpeg` | Conversão e mixagem de áudio |
| **Chrome** | google.com/chrome | Extensão (Manifest V3) |
| **Ollama** | ollama.com | Geração de notas (local) |
| **Conta HuggingFace** | huggingface.co | Token para baixar modelos de diarização (grátis) |
| **OpenWork Desktop** (ou OpenCode CLI) | openworklabs.com | Orquestração agêntica: skills, processamento e automações |

> **Sobre o OpenWork/OpenCode:** o processamento (transcrição → diarização → notas) é orquestrado pelo **agente** — as skills `subir-servidor`, `processar-gravacao` e `limpar-material` vivem em `.opencode/skills/` e são executadas pelo OpenWork Desktop (ou OpenCode CLI) com acesso a este workspace. **A automação de limpeza (08:00) roda apenas com o OpenWork Desktop aberto e conectado** — o processamento é local (Whisper/pyannote), então não há runner cloud. Se o app estiver fechado no horário, basta pedir *"limpa o material"* no chat. O processamento de gravações é **manual** (pedido no chat) — a automação de lote diário (02:00) foi desativada porque o limite de 15 min por execução não comporta a transcrição local (ver seção *Processamento*).

### Passo a passo

```bash
# 1. Clonar o repositório
git clone https://github.com/armel-felipe/gravador-reunioes.git
cd gravador-reunioes

# 2. Criar o .env com o token do HuggingFace
cp .env.example .env
# → edite o .env e troque hf_cole_seu_token_aqui pelo seu token real
#   (crie em https://huggingface.co/settings/tokens, tipo Read)
#   IMPORTANTE: aceite os termos dos modelos antes:
#   https://huggingface.co/pyannote/speaker-diarization-3.1
#   https://huggingface.co/pyannote/segmentation-3.0

# 3. Subir o servidor local (cria o venv e instala as dependências na 1ª vez)
./start.sh
# → deve imprimir algo como "Uvicorn running on http://127.0.0.1:8765"
# → deixe este terminal aberto enquanto for gravar

# 4. Carregar a extensão no Chrome
#    a) Abra chrome://extensions
#    b) Ative o "Modo do desenvolvedor" (canto superior direito)
#    c) Clique em "Carregar sem compactação" (Load unpacked)
#    d) Selecione a pasta extension/ do projeto
#    e) Fixe o ícone "Gravador de Reuniões" na barra (quebra-cabeça 🧩 → pin)

# 5. Verificar que está tudo de pé
curl http://127.0.0.1:8765/health
# → {"status":"ok"}
```

> **Nota sobre o Ollama:** o `config.yaml` usa `provider: local` por padrão, com o modelo `gemma4:26b-mlx`. Para usar outro modelo local, rode `ollama pull <modelo>` e ajuste `ollama.local_model`. Para usar **Ollama Cloud**, mude `provider` para `cloud`, configure `cloud_model` e defina a variável indicada em `ollama.cloud_api_key_env` no `.env`. Nesse modo, o conteúdo da transcrição é enviado ao endpoint configurado em `cloud_base_url`.

---

## 🎯 Uso no dia a dia

### 1. Gravar uma reunião/aula

1. Rode `./start.sh` (se ainda não estiver rodando)
2. Abra a reunião/videoaula no Chrome (Meet, Teams web, Zoom web, YouTube...)
3. Clique no ícone da extensão → digite o **nome** (ex.: `reuniao_orcamento_ana`) → **Gravar**
4. O Chrome pede permissão de **microfone** — aceite (é para capturar sua voz junto)
5. Ao final, clique em **Parar** → "Gravação salva"

O arquivo é salvo como `99_material/2026_09_09_14_30_reuniao_orcamento_ana/audio/2026_09_09_14_30_reuniao_orcamento_ana.wav` (data/hora + nome, agrupado por evento).

### 2. Processar (transcrever + diarizar + notas)

No chat do OpenWork, peça:

> **"processa a gravação de hoje"** (ou "processa a última gravação", ou "processa <nome>", ou "processa as pendentes")

O agente roda o pipeline completo e salva, dentro da pasta do evento:
- `99_material/<evento>/transcricoes/<nome>.md` — falas diarizadas com timestamps
- `99_material/<evento>/notas/<nome>.md` — resumo executivo, tópicos, decisões, plano de ação

**Geração de notas com map-reduce:** reuniões longas são divididas em **blocos de ~10 min com 2 min de sobreposição** — cada bloco é resumido separadamente (map) e os resumos são consolidados no documento final (reduce). Isso reduz o tempo de processamento em **~87%** (26 min → 3,5 min numa reunião de 39 min) e **melhora a qualidade** (o modelo não perde detalhes do meio da reunião). Reuniões curtas (≤ 10 min) usam o prompt único direto, sem overhead.

O mesmo prompt é usado nos modelos local e Cloud. Ele exige preservar nomes, empresas, números, datas, decisões, responsáveis e prazos, sem inventar informações, mantendo a saída concisa.

Você também pode pedir para trocar o modelo na hora: *"usa o gemma4 desta vez"*.

### 3. Processamento (manual)

- **O processamento é manual:** peça *"processa a gravação de hoje"*, *"processa a última gravação"*, *"processa <nome>"* ou *"processa as pendentes"* no chat do OpenWork.
- **Marcador de processado:** um evento é considerado processado quando tem `notas/<evento>.md`. Eventos já processados são **pulados**; falhas no meio do pipeline são **retentadas** na próxima execução.
- **Para listar os pendentes manualmente:** `.venv/bin/python scripts/06_pendentes.py`
- ⚠️ **Automação desativada:** a automação diária de processamento (02:00) foi **desativada** — o limite de 15 min por execução do OpenWork não comporta a transcrição local (Whisper `medium` roda a ~0,5x tempo real em CPU; um áudio de 27 min leva ~13 min só na transcrição). O processamento é feito sob demanda no chat.

### 4. Limpar material antigo

- **Manual:** peça *"limpa o material"* no chat
- **Automático:** a automação diária (08:00) apaga áudios com mais de 30 dias, mantendo transcrições e notas

---

## 🤖 Fluxo atual (automações)

| Horário | Automação | O que faz |
|---|---|---|
| **08:00** | Limpeza de material | Apaga a pasta `audio/` de eventos com mais de 30 dias, mantendo transcrições e notas |

> **Processamento de gravações:** manual, sob demanda no chat (a automação de lote diário das 02:00 foi desativada — ver seção *Processamento*).

**Fluxo do dia a dia:**
1. `./start.sh` → servidor de pé
2. Gravar reuniões/aulas durante o dia (extensão + toaster)
3. Pedir *"processa as pendentes"* no chat (ou processar cada gravação individualmente)
4. **08:00** — limpeza automática dos áudios antigos
5. As notas ficam em `99_material/<evento>/notas/`

> ⚠️ **Importante:** a automação de limpeza roda apenas com o **OpenWork Desktop aberto e conectado** (o processamento é local). Se o app estiver fechado no horário, a execução é perdida — mas você pode pedir *"limpa o material"* no chat a qualquer momento.

---

## 📦 Dependências de runtime

| Componente | Dependência | Versão | Onde |
|---|---|---|---|
| **Servidor** | Python | 3.11+ | `server/requirements.txt` (fastapi, uvicorn, websockets) |
| **Pipeline** | faster-whisper | 1.0.* | `scripts/requirements.txt` |
| **Pipeline** | pyannote.audio | 3.4.* | `scripts/requirements.txt` |
| **Pipeline** | huggingface_hub | 0.26.* | `scripts/requirements.txt` (compatível com pyannote 3.4) |
| **Pipeline** | numpy | 1.26.* | `scripts/requirements.txt` (compatível com pyannote) |
| **Pipeline** | requests | — | `scripts/requirements.txt` |
| **Sistema** | ffmpeg | 8.x (brew) | `brew install ffmpeg` |
| **Sistema** | Ollama | — | `ollama.com` (modelos locais ou cloud) |
| **Sistema** | Chrome | — | Extensão MV3 |
| **Sistema** | HuggingFace token | — | `.env` (`HUGGINGFACE_TOKEN=`) |
| **Orquestração** | OpenWork Desktop / OpenCode CLI | — | Skills + automações (ver nota acima) |

**Modelos do Ollama (locais, `ollama list`):** `qwen3.6:35b-mlx`, `gemma4:26b-mlx`, `qwen3.8:27b-mlx`, `nemotron-3.5-lightning:30b-a3b`, `ornith-1.5:35b` — selecione em `config.yaml` (um descomentado por vez).

**Modelos do Whisper:** `medium` (padrão atual, mais rápido e estável) ou `large-v3` (melhor qualidade, ~2x mais lento) — em `config.yaml`.

---

## ⚙️ Configuração (`config.yaml`)

| Chave | Descrição | Padrão |
|---|---|---|
| `whisper.model` | Modelo do Whisper (`medium` mais rápido e estável, `large-v3` melhor qualidade) | `medium` |
| `diarizacao.min_speakers` / `max_speakers` | Limites de falantes (null = automático) | `null` |
| `ollama.provider` | `local` ou `cloud` | `local` |
| `ollama.local_model` | Modelo local do Ollama | `gemma4:26b-mlx` |
| `ollama.cloud_model` | Modelo na nuvem | `glm-5.3-flash:cloud` |
| `ollama.cloud_base_url` | URL base da API Cloud (sem `/v1`) | `https://ollama.com` |
| `ollama.cloud_api_key_env` | Nome da env var com a API key | `LPR_BZ685_OLLAMA_API_KEY` |
| `limpeza.dias_retencao_audio` | Dias de retenção dos áudios | `30` |

---

## 🧪 Testes

```bash
.venv/bin/python -m pytest scripts/ server/ -v
```

Cobre: alinhamento de falas, geração de prompt de notas, limpeza de áudios antigos, listagem de pendentes e o fluxo de armazenamento/mixagem do servidor.

---

## 🔧 Troubleshooting

| Problema | Solução |
|---|---|
| Popup diz "Servidor offline" | Rode `./start.sh` — ou peça *"sobe o servidor"* no chat |
| Diarização falha com erro de token | Confira o `.env` (HUGGINGFACE_TOKEN) e se aceitou os termos dos 2 modelos |
| Whisper muito lento | Troque `whisper.model` para `medium` no `config.yaml` |
| Notas falham (Ollama parado) | Rode `ollama serve` ou peça para usar Ollama cloud |
| Diarização com rótulos demais | Ajuste `diarizacao.min_speakers`/`max_speakers` no `config.yaml` |
| Gravação interrompida (aba fechada) | O que chegou ao servidor é salvo mesmo assim — processe o arquivo parcial |

---

## 🗺️ Mapa do projeto

Veja [mapa.md](mapa.md) para a descrição detalhada de todas as skills e scripts.

---

## 🔮 Evoluções futuras (fora do escopo atual)

- **Mapa de vozes** — gravar 10s de cada pessoa e rotular com nomes reais ("voz da Ana")
- Detecção automática de início de reunião
- Interface web para revisar/editar transcrições
- Suporte a apps desktop (Teams/Zoom instalados)

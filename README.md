# Gravador de Reuniões

Grava o áudio de reuniões e videoaulas no navegador (Google Meet, Teams web, Zoom web, YouTube), transcreve com **Whisper**, separa as vozes com **diarização (pyannote)** e gera **notas, resumo e plano de ação** com **Ollama** — tudo local, orquestrado pelo OpenWork.

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
│   ├── common.py           ← config + caminhos compartilhados
│   ├── alinhar.py          ← lógica de alinhamento (testável)
│   ├── notas.py            ← lógica de notas (testável)
│   ├── limpar.py           ← lógica de limpeza (testável)
│   └── requirements.txt     ← dependências do pipeline
├── .opencode/skills/       ← skills do OpenWork (acionáveis no chat)
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

> **Nota sobre o Ollama:** o `config.yaml` usa `provider: local` por padrão (modelo `qwen3.6:35b-mlx`). Para usar outro modelo local, rode `ollama pull <modelo>` e ajuste `ollama.local_model` no `config.yaml`. Para usar **Ollama cloud**, mude `provider: cloud`, preencha `cloud_base_url` e defina a env var com sua API key (o nome da variável está em `ollama.cloud_api_key_env`).

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

> **"processa a gravação de hoje"** (ou "processa a última gravação", ou "processa <nome>")

O agente roda o pipeline completo e salva, dentro da pasta do evento:
- `99_material/<evento>/transcricoes/<nome>.md` — falas diarizadas com timestamps
- `99_material/<evento>/notas/<nome>.md` — resumo executivo, tópicos, decisões, plano de ação

Você também pode pedir para trocar o modelo na hora: *"usa o gemma4 desta vez"*.

### 3. Limpar material antigo

- **Manual:** peça *"limpa o material"* no chat
- **Automático:** a automação diária (08:00) apaga áudios com mais de 30 dias, mantendo transcrições e notas

---

## ⚙️ Configuração (`config.yaml`)

| Chave | Descrição | Padrão |
|---|---|---|
| `whisper.model` | Modelo do Whisper (`large-v3` melhor qualidade, `medium` mais rápido) | `large-v3` |
| `diarizacao.min_speakers` / `max_speakers` | Limites de falantes (null = automático) | `null` |
| `ollama.provider` | `local` ou `cloud` | `local` |
| `ollama.local_model` | Modelo local do Ollama | `qwen3.6:35b-mlx` |
| `ollama.cloud_model` | Modelo na nuvem | `qwen3.6:35b-mlx` |
| `ollama.cloud_base_url` | URL base da API cloud (sem `/v1`) | `https://ollama.com/api` |
| `ollama.cloud_api_key_env` | Nome da env var com a API key | `LPR_BZ685_OLLAMA_API_KEY` |
| `limpeza.dias_retencao_audio` | Dias de retenção dos áudios | `30` |

---

## 🧪 Testes

```bash
.venv/bin/python -m pytest scripts/ server/ -v
```

Cobre: alinhamento de falas, geração de prompt de notas, limpeza de áudios antigos e o fluxo de armazenamento/mixagem do servidor.

---

## 🔧 Troubleshooting

| Problema | Solução |
|---|---|
| Popup diz "Servidor offline" | Rode `./start.sh` e tente de novo |
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

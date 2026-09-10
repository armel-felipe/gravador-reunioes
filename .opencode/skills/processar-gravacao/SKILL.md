---
name: processar-gravacao
description: "Processa uma gravação de reunião: transcreve (Whisper), diariza vozes (pyannote) e gera notas (Ollama). Acionar quando o usuário pedir \"processa a gravação\", \"processa a última gravação\", \"gera notas da reunião\" ou similar."
---

# Processar Gravação

## Quando usar
Quando o usuário pedir para processar uma gravação de reunião/aula capturada pela extensão.

## Passos

1. **Identificar o áudio:**
   - Cada gravação é um evento: `99_material/<nome_base>/audio/<nome_base>.wav` (nome_base = `YYYY_MM_DD_HH_MM_<nome>`).
   - Se o usuário deu um nome, use `99_material/audio/<nome_base>/<nome_base>.wav` — na prática, procure o evento em `99_material/` cujo nome contenha o que o usuário citou.
   - Se pediu "a última", liste os eventos `99_material/*/audio/*.wav` e use o mais recente (por mtime).
   - Se não houver áudio, avise e encerre.

2. **Rodar o pipeline** (da raiz do projeto, com o venv):
   ```bash
   .venv/bin/python scripts/01_transcrever.py <nome_base>
   .venv/bin/python scripts/02_diarizar.py <nome_base>
   .venv/bin/python scripts/03_alinhar.py <nome_base>
   .venv/bin/python scripts/04_notas.py <nome_base>
   ```
   - Inspecione cada saída intermediária em `99_material/<nome_base>/transcricoes/_tmp/` antes de seguir.
   - Se o usuário pediu outro modelo ("usa o gemma4"), edite `config.yaml` (ollama.local_model) antes do passo 04 e restaure depois.

3. **Verificar qualidade:**
   - Se a diarização tiver muitos rótulos ou falas cruzadas, ajuste `config.yaml` (diarizacao.min_speakers/max_speakers) e re-rode o passo 02 e 03.
   - Se o Whisper estiver lento, troque `whisper.model` para `medium` e re-rode.

4. **Entregar:** mostre ao usuário o caminho da transcrição e das notas, e um resumo de 3-5 linhas do conteúdo.

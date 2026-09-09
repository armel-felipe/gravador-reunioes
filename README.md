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

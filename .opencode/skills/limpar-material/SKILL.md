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

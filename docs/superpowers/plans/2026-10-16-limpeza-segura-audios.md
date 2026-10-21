# Limpeza Segura de Áudios Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a limpeza remover áudio antigo somente de eventos que tenham a nota final de processamento.

**Architecture:** Manter a função `limpar_audios_antigos(material_dir, dias)` e adicionar uma guarda local baseada em `notas/<evento>.md` antes da remoção. O teste unitário existente será ampliado com um evento antigo sem nota.

**Tech Stack:** Python 3, pytest, pathlib.

## Global Constraints

- O marcador oficial de processado é `notas/<evento>.md`.
- Transcrições e notas devem permanecer intactas.
- Não alterar `config.yaml` nem apagar material adicional.
- Não criar commit nesta execução.

### Task 1: Proteger a limpeza por nota final

**Files:**
- Modify: `scripts/test_limpar.py`
- Modify: `scripts/limpar.py`

**Interfaces:**
- Consumes: `limpar_audios_antigos(material_dir: str, dias: int) -> list`.
- Produces: a função que só retorna/apaga arquivos de eventos antigos com `notas/<evento>.md`.

- [ ] **Step 1: Write the failing test**

Adicionar `test_limpar_preserva_audio_antigo_sem_nota`, criando um evento WAV com 40 dias e afirmando que o áudio continua e a lista de apagados é vazia.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest scripts/test_limpar.py::test_limpar_preserva_audio_antigo_sem_nota -v`

Expected: FAIL porque a implementação atual apaga o áudio antigo mesmo sem nota.

- [ ] **Step 3: Write minimal implementation**

Antes de calcular/remover o áudio do evento, ignorar o evento quando `evento / "notas" / f"{evento.name}.md"` não existir.

- [ ] **Step 4: Run focused and full tests**

Run: `.venv/bin/python -m pytest scripts/test_limpar.py -v`

Expected: 3 passed.

Run: `.venv/bin/python -m pytest scripts/ server/ native_host/ -v`

Expected: all collected tests pass.

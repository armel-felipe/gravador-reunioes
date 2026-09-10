# 🗺️ Roadmap — Gravador de Reuniões

Registro de mudanças planejadas, em andamento e concluídas do projeto.
Cada task tem um **ID único**, **prioridade** e **status** rastreável.

## Legenda

- **Prioridade:** 🔴 Alta | 🟡 Média | 🟢 Baixa
- **Status:** 📋 Planejada | 🔨 Em andamento | ✅ Concluída | ❌ Cancelada

---

## Tasks

### R-006 — Processamento automático pós-gravação (lote diário)
- **Prioridade:** 🟡 Média
- **Status:** 🔨 Em andamento
- **Criada em:** 2026-09-10
- **Motivo:** Hoje o processamento é manual ("processa a gravação" no chat). Automatizar em lote diário, preservando a camada agêntica.
- **Escopo:**
  - Script `06_pendentes.py` — lista eventos com áudio mas sem notas (marcador de processado = `notas/<evento>.md`) ✅
  - Skill `processar-gravacao` atualizada para processar pendentes em lote ✅
  - Automação diária (horário a definir) que roda a skill com "processa as pendentes"
- **Limitações conhecidas:**
  - Automação Desktop roda apenas com o OpenWork aberto e conectado
  - Processamento é local (Whisper/pyannote) — não há runner cloud
  - Reprocessamento: eventos sem notas são retentados automaticamente; eventos com notas são pulados
- **Critérios de aceite:** automação diária processa só os pendentes; eventos já processados são pulados.

---

### R-001 — Migrar captura de áudio para AudioWorkletNode
- **Prioridade:** 🟡 Média
- **Status:** ✅ Concluída
- **Criada em:** 2026-09-09
- **Concluída em:** 2026-09-09
- **Motivo:** O `ScriptProcessorNode` (usado em `extension/offscreen.js`) está **deprecado** no Chrome. Funciona hoje, mas será removido no futuro — a extensão quebraria silenciosamente. A API moderna (`AudioWorkletNode`) roda em thread própria de áudio, com latência menor e sem glitches.
- **Escopo:**
  - Criar `extension/worklet.js` — processador de áudio (PCM16) em módulo separado
  - Atualizar `extension/offscreen.js` — carregar o worklet via `audioWorklet.addModule()` e usar `AudioWorkletNode` no lugar de `createScriptProcessor()`
  - Manter o protocolo com o servidor **inalterado** (PCM16 + canais `tab`/`mic`)
  - Manter o monitoramento: aba com volume 1.0, mic com volume 0
- **Critérios de aceite:**
  - Sem aviso de deprecação no `chrome://extensions`
  - Gravação continua funcionando (aba + mic, ou só aba)
  - Testes do projeto continuam passando
- **Notas:** o worklet não tem acesso ao `ws` (escopo do módulo) — a comunicação do áudio processado para o `offscreen.js` é via `port.postMessage()`. Implementado e validado (sintaxe OK, 7/7 testes passando). Falta confirmação manual no Chrome (gravação real).

---

### R-002 — Mapa de vozes (voz → nome real)
- **Prioridade:** 🟢 Baixa
- **Status:** 📋 Planejada
- **Criada em:** 2026-09-09 (design aprovado, evolução C)
- **Motivo:** A diarização rotula "Falante 1, Falante 2..." — sem nomes reais. A evolução C do design: gravar ~10s de cada pessoa uma vez e mapear voz → nome.
- **Escopo (alto nível):**
  - Captura de amostras de voz (10s por pessoa)
  - Extração de embeddings de voz (ex.: pyannote embedding)
  - Mapeamento voz → nome aplicado na diarização
- **Status:** aguardando R-001 e uso real do sistema.

---

### R-003 — Detecção automática de início de reunião
- **Prioridade:** 🟢 Baixa
- **Status:** 📋 Planejada
- **Criada em:** 2026-09-09 (design aprovado, fora do escopo inicial)
- **Motivo:** Nunca esquecer de apertar Gravar — a extensão detecta entrada em reunião (Meet/Teams/Zoom web) e pergunta se quer gravar.
- **Escopo (alto nível):** observação de URL/aba + notificação no popup.

---

### R-004 — Interface web para revisar/editar transcrições
- **Prioridade:** 🟢 Baixa
- **Status:** 📋 Planejada
- **Criada em:** 2026-09-09 (design aprovado, fora do escopo inicial)
- **Motivo:** Corrigir nomes e erros de transcrição antes de gerar notas.
- **Escopo (alto nível):** página local (FastAPI) listando gravações + editor de transcrição.

---

### R-005 — Suporte a apps desktop (Teams/Zoom instalados)
- **Prioridade:** 🟢 Baixa
- **Status:** 📋 Planejada
- **Criada em:** 2026-09-09 (design aprovado, fora do escopo inicial)
- **Motivo:** Extensões não capturam áudio de apps desktop. Exigiria dispositivo virtual (BlackHole) + recorder local.
- **Escopo (alto nível):** recorder local + integração com o servidor.

---

## Histórico de mudanças

| Data | Task | Ação |
|---|---|---|
| 2026-09-10 | R-006 | Criada (processamento automático em lote diário) |
| 2026-09-09 | R-001 | Criada e iniciada (migração AudioWorklet) |
| 2026-09-09 | R-001 | ✅ Concluída (implementada, validada; aguarda confirmação manual no Chrome) |
| 2026-09-09 | R-002 | Criada (evolução C do design) |
| 2026-09-09 | R-003 | Criada (fora do escopo inicial) |
| 2026-09-09 | R-004 | Criada (fora do escopo inicial) |
| 2026-09-09 | R-005 | Criada (fora do escopo inicial) |

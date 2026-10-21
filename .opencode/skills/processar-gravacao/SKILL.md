---
name: processar-gravacao
description: "Processa uma gravação de reunião: transcreve (Whisper), diariza vozes (pyannote) e gera notas com o perfil LLM configurado. Acionar quando o usuário pedir \"processa a gravação\", \"processa a última gravação\", \"gera notas da reunião\" ou similar."
---

# Processar Gravação

## Quando usar
Quando o usuário pedir para processar uma gravação de reunião/aula capturada pela extensão, incluindo uma gravação específica, a última gravação ou todas as pendentes. A execução é sempre iniciada sob demanda.

## Passos

0. **Definir o alvo:**
   - Para "processa as pendentes" / "processa tudo", inicie o snapshot atual com `start --pendentes`; o worker processa um evento por vez.
   - Para um evento específico, use o nome-base fornecido ou identifique-o em `99_material/`; para a última gravação, escolha o WAV mais recente por mtime.
   - Se o pedido for apenas listar pendências, use `.venv/bin/python scripts/06_pendentes.py` e não inicie um job.
   - Se não houver pendências/áudio, informe e encerre.

1. **Identificar o áudio:**
   - Cada gravação é um evento: `99_material/<nome_base>/audio/<nome_base>.wav` (nome_base = `YYYY_MM_DD_HH_MM_<nome>`).
   - Se o usuário deu um nome, procure o evento em `99_material/` cujo nome contenha o que o usuário citou (ex.: "aula" → `99_material/2026_09_09_22_59_aula_python/`).
   - Se pediu "a última", liste os eventos `99_material/*/audio/*.wav` e use o mais recente (por mtime).
   - Se não houver áudio, avise e encerre.

2. **Iniciar o processamento local desacoplado** (da raiz do projeto):
   ```bash
   .venv/bin/python scripts/07_processar.py start --evento <nome_base>
   # ou para o conjunto pendente atual:
   .venv/bin/python scripts/07_processar.py start --pendentes
   ```
   - A confirmação devolve o `job_id`; o comando não espera Whisper, pyannote ou o LLM terminarem. O worker local continua após o fim da chamada do chat ou o fechamento do OpenWork.
   - Para consultar o status numa conversa atual ou futura, rode `.venv/bin/python scripts/07_processar.py status` (sem job ID lista jobs recentes) ou acrescente `--job-id <job_id>`.
   - Para retomar um job interrompido, use `resume --job-id <job_id>`, `resume --evento <nome_base>` ou `resume --pendentes`. Saídas válidas e checkpoints existentes são reutilizados.
   - Se o Mac dormir, o job pausa e continua quando o computador acordar. Não há cron nem agendamento recorrente.
   - O padrão de notas é o perfil `llm.active: llama-cpp` em `config.yaml`, com modelo `qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-compact` no endpoint `http://100.87.71.48:18080/v1`.
   - Se o usuário pedir outro modelo para esta execução, inicie com `--modelo <ID-exato>`; o override fica no job e só altera a configuração em memória do subprocesso de notas. Nunca edite `config.yaml` para o job.

3. **Acompanhar e validar:**
   - Em resposta imediata ao start, diga que o job foi iniciado localmente, informe o `job_id` e o comando de status; não diga que a transcrição/notas já terminaram.
   - Quando o usuário voltar ou pedir status, leia o manifesto do job. Se estiver `queued`/`running`, informe o estágio atual; se estiver `interrupted`/`failed`, explique a falha e ofereça retomar.
   - Só quando o estado for `completed`, valide os arquivos em `99_material/<nome_base>/transcricoes/` e `notas/`, abra as notas e entregue seus caminhos e resumo de 3–5 linhas.
   - Em lote, reporte os eventos concluídos e os que falharam; não marque o lote como totalmente concluído quando houver falhas.

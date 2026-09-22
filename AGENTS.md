# AGENTS.md — Gravador de Reuniões

Porta de entrada operacional para agentes neste workspace. Mantenha este arquivo curto: o detalhe fica em `README.md` (visão geral e uso), `mapa.md` (scripts, skills e arquivos) e `ROADMAP.md` (mudanças).

## O projeto em uma linha

Captura o áudio de reuniões e videoaulas pelo Chrome (aba + microfone), transcreve com Whisper, separa as vozes com pyannote e gera notas com Ollama — tudo local, em `99_material/<evento>/`.

## Onde encontrar contexto

- Visão geral, instalação e uso: `README.md`
- Scripts, skills e arquivos, um por um: `mapa.md`
- Mudanças planejadas, em andamento e concluídas: `ROADMAP.md`
- Skills operacionais: `.opencode/skills/*/SKILL.md`

## Governança das skills

Fonte canônica de manutenção: `.opencode/skills/{skill}/SKILL.md`.

- Para criar, corrigir, refatorar ou revisar uma skill, editar sempre `.opencode/skills/{skill}/SKILL.md`
- Nunca criar uma pasta paralela de skills fora de `.opencode/skills/`
- Ao citar uma skill em respostas, revisões ou instruções, usar o caminho canônico `.opencode/skills/{skill}/SKILL.md`

## Regra de execução obrigatória

Antes de executar qualquer skill, ler o `SKILL.md` correspondente em `.opencode/skills/{skill}/SKILL.md`. Nunca executar de memória.

Ler a skill não conta como execução. A execução só está concluída quando:

- os scripts e comandos obrigatórios foram realmente executados
- os artefatos exigidos foram persistidos nos caminhos corretos
- as validações finais foram rodadas
- a resposta final estiver consistente com o estado salvo em disco

Se algum passo não puder ser executado, declarar explicitamente que a execução foi parcial ou bloqueada, informar qual passo faltou e nunca apresentar a skill como concluída.

## Servidor local de captura

O servidor (`server/main.py`) escuta só em `127.0.0.1:8765` e é pré-requisito para gravar.

- Subir: skill `subir-servidor` (ou `./start.sh`), sempre **desacoplado** via `launchctl submit` (job `com.armel.gravador-servidor`)
- Não rodar `./start.sh` em primeiro plano nem com `&` simples: o processo morre junto com a sessão
- Conferir: `curl -s http://127.0.0.1:8765/health` → `{"status":"ok"}`
- Log: `/tmp/gravador_server.log`
- Parar: `launchctl remove com.armel.gravador-servidor`

## Regras críticas

- Rode os comandos documentados a partir da raiz do projeto.
- Nunca leia, exponha, edite ou versione `.env` (token do HuggingFace). Use `.env.example` como referência.
- `99_material/` é material gerado: não apagar, mover ou reorganizar sem pedido explícito.
- `config.yaml` é a configuração central (modelo do Whisper, limites de diarização, provider/modelo do Ollama, retenção de áudio). Prefira ajustá-lo a fixar valores no código.
- O processamento de gravações é manual, sob demanda no chat — não existe automação de transcrição (a de limpeza roda às 08:00).
- Testes: `.venv/bin/python -m pytest scripts/ server/ -v`
- Abrir a porta 8765 é bloqueado pelo sandbox: subir o servidor exige execução fora do sandbox.

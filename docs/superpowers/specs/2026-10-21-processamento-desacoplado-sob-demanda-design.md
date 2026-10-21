# Especificação: processamento desacoplado sob demanda

**Status:** proposta para revisão do usuário
**Data:** 2026-10-21

## Objetivo

Permitir que uma solicitação explícita de processamento continue no computador local mesmo depois de a resposta do chat terminar ou atingir seu limite de execução. O uso permanece sob demanda: uma gravação individual ou todas as gravações pendentes, em sequência. Não haverá cron nem processamento agendado.

## Contexto atual

- O pipeline atual é orquestrado em sequência pela skill `processar-gravacao` e pelos scripts de transcrição, diarização, fusão, alinhamento e notas.
- Uma execução síncrona no chat pode expirar antes de concluir gravações longas.
- A transcrição e a diarização salvam seus JSONs somente ao fim da respectiva etapa; checkpoints de map-reduce já permitem reutilizar resumos de blocos na geração de notas.
- O evento só deixa de ser considerado pendente quando existe `notas/<evento>.md`.
- O repositório já prevê execução local desacoplada via `launchd` para tarefas, mas a proposta aqui é iniciar jobs apenas em resposta a pedidos explícitos, não por horário.

## Comportamento proposto

1. Ao receber pedido para processar um evento ou “todas as pendentes”, validar os eventos e iniciar um job local desacoplado, sem aguardar todo o pipeline na chamada do chat.
2. Cada job processa os estágios na ordem atual: transcrever → diarizar → fundir → alinhar → notas.
3. Para “todas as pendentes”, processar um evento por vez e continuar para os seguintes mesmo que um evento falhe; apresentar o resultado por evento.
4. Persistir estado legível por máquina e log por evento, sob a pasta desse evento em `99_material/`, sem mover ou apagar áudio, transcrição ou notas existentes.
5. Registrar início, estágio atual, estágios concluídos, último erro, horários e estado terminal (`concluído` ou `falhou`). Atualizar o estado de forma atômica para evitar arquivos de estado truncados. Se o usuário pedir um modelo alternativo, registrar a escolha somente no manifesto do job e aplicá-la em memória no subprocesso de notas, sem editar `config.yaml`.
6. Se o chat encerrar ou expirar, o job continua. Uma nova solicitação pode consultar o estado e retomar uma falha a partir do último estágio concluído. Não duplicar um job já ativo para o mesmo evento.
7. Reutilizar os checkpoints já existentes de map-reduce. Saídas de transcrição/diarização/alinhamento concluídas também devem servir como marcadores de etapa, desde que sua existência e integridade mínima sejam verificadas antes de pular a etapa.
8. Considerar o processamento concluído somente após a nota final estar gravada e validada. O marcador de notas atual permanece compatível com `06_pendentes.py`.

## Interface operacional

- A skill continua sendo a interface em linguagem natural para pedidos individuais ou em lote.
- Um script orquestrador local será o ponto único de entrada para iniciar ou retomar o pipeline; scripts atuais por estágio continuam sendo usados.
- O início retorna rapidamente uma confirmação com o(s) identificador(es) do job e informa que o processamento segue localmente.
- A skill deve conseguir consultar o estado/logs e informar se o job está rodando, terminou ou falhou. Uma nova mensagem como “status do processamento” deve permitir essa consulta sem relançar o trabalho.
- Se uma gravação falhar em lote, registrar a falha e seguir para a próxima; ao final, informar quais terminaram e quais exigem retomada.

## Execução local e limites

- Usar um job one-shot de `launchd` por evento ou por lote, com identificadores únicos e sem agenda recorrente.
- Não depender da sessão do shell/chat para manter o processo vivo.
- O processamento continua após o chat encerrar, desde que a sessão do usuário no macOS permaneça disponível. Se o Mac dormir, o job pausa e prossegue quando o computador acordar; não impedir o repouso nem pedir wake automático.
- Não instalar daemon permanente, cron, automação diária ou runner remoto como parte desta mudança.

## Segurança e recuperação

- Não ler, registrar ou copiar o conteúdo de `.env`; o subprocesso recebe o ambiente local necessário conforme a configuração já existente.
- Não colocar segredos em argumentos de linha de comando, estado ou logs.
- Uma seleção explícita de modelo é um identificador não secreto; validar que não está vazio, não contém caracteres de controle e tem no máximo 256 caracteres, sem alterar a configuração persistida.
- Aplicar lock por evento para impedir execuções concorrentes e liberar locks obsoletos após comprovar que não há processo ativo.
- Preservar logs para diagnóstico e evitar logar conteúdo sensível do ambiente.
- Falhas não devem criar nota final parcial nem fazer um evento parecer concluído. Escritas finais devem ser atômicas quando aplicável.
- Retomada deve ser idempotente: reutilizar saídas válidas de etapas concluídas e repetir somente a etapa incompleta/falha.

## Não objetivos

- Processar gravações automaticamente em horário fixo.
- Impedir que o Mac durma, acordá-lo ou garantir processamento enquanto desligado.
- Alterar modelos/configurações centrais do pipeline como parte do job.
- Refatorar os algoritmos de Whisper, pyannote, fusão ou map-reduce além do necessário para orquestração, estado e retomada.
- Enviar notificações externas; a conclusão será consultável e reportada no chat quando houver nova interação.

## Validação e critérios de aceite

1. Iniciar um evento de teste retorna rapidamente e o processo continua após o encerramento da chamada que o iniciou.
2. Um job concluído deixa transcrição, diarização/alinhamento, notas e estado final coerentes; `06_pendentes.py` não lista o evento.
3. Um job interrompido após um estágio pode ser retomado sem repetir etapas válidas já concluídas.
4. Duas solicitações concorrentes para o mesmo evento não executam o pipeline em paralelo.
5. Em lote, eventos são processados em sequência; falha em um deles não impede os demais, e o relatório final diferencia sucesso e falha.
6. Estado e logs permitem consultar andamento, último estágio e erro sem abrir o processo em primeiro plano.
7. Testes existentes continuam passando e novos testes cobrem retomada, concorrência, falha por etapa e resultados em lote.

## Decisões para confirmar na revisão

- Proposta usa `launchd` one-shot para obter persistência no macOS, sem agendamento recorrente.
- Estado/logs ficam em cada diretório de evento dentro de `99_material/`; devem ser arquivos operacionais ocultos ou em subdiretório dedicado, sem reorganizar material existente.
- O pedido de “todas as pendentes” significa uma fila sequencial criada naquele momento; novas gravações criadas depois não entram automaticamente nessa fila.

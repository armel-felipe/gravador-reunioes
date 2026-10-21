# Controle automático do servidor pelo complemento do Chrome

**Data:** 2026-10-07
**Status:** Design aprovado para especificação de implementação

## Contexto

O complemento Chrome já consulta `http://127.0.0.1:8765/health` antes de iniciar uma gravação. Quando o servidor está parado, o popup apenas orienta o usuário a executar `./start.sh`. O projeto já define o ciclo operacional do servidor por meio do job `launchctl` `com.armel.gravador-servidor`, iniciado com `launchctl submit` e parado com `launchctl remove`.

O objetivo é permitir que o usuário controle esse ciclo diretamente pelo complemento, mantendo a execução desacoplada da sessão do Terminal e sem expor execução arbitrária de comandos ao Chrome.

## Objetivos

- Mostrar no popup se o servidor está online ou offline.
- Permitir ligar o servidor automaticamente pelo botão do complemento.
- Permitir desligar o servidor automaticamente pelo botão do complemento.
- Pedir confirmação antes de desligar.
- Se houver gravação ativa, encerrar a gravação e aguardar a confirmação `ended` do servidor antes de desligá-lo.
- Confirmar cada transição consultando `/health` e informar falhas sem exibir sucesso falso.
- Documentar a instalação da ponte local e cobrir o comportamento com testes.

## Fora de escopo

- Alterar o protocolo de áudio ou o endpoint WebSocket `/ws`.
- Automatizar o processamento de transcrições, diarização ou notas.
- Criar um daemon HTTP permanente adicional.
- Aceitar comandos shell genéricos enviados pela extensão.
- Alterar a retenção ou a organização de `99_material/`.

## Abordagens consideradas

### Native Messaging — escolhida

A extensão conversa com um host local registrado no Chrome. O host implementa somente `status`, `start` e `stop`, chamando os comandos controlados de `launchctl` e fazendo as verificações de saúde necessárias.

Vantagens: integra-se ao fluxo já existente, não exige outro processo permanente e mantém a superfície de comando pequena. Exige uma instalação inicial do manifesto do host e um caminho absoluto para o projeto.

### Daemon HTTP auxiliar

Um processo adicional sempre ativo receberia requisições locais para iniciar e parar o servidor.

Foi descartado porque introduz outro serviço permanente, aumenta a superfície de segurança e torna o controle mais complexo do que o job `launchd` já existente.

### Terminal/AppleScript

A extensão poderia abrir o Terminal e executar comandos.

Foi descartado porque depende de estado e permissões do aplicativo Terminal, não oferece uma confirmação confiável do estado do servidor e não é adequado para uma interface de controle consistente.

## Arquitetura

### Popup

O popup terá um estado visual de servidor com os estados `Verificando`, `Offline`, `Ligando`, `Online`, `Desligando` e `Erro`. O botão de gravação ficará desabilitado enquanto o servidor não estiver confirmado como online.

Quando o servidor estiver offline, o botão principal será `Ligar servidor`. Durante a inicialização, ele mudará para `Ligando...` e fará polling limitado de `/health`. Quando estiver online, o controle será `Desligar servidor`.

Ao clicar em `Desligar servidor`, o popup abrirá uma confirmação explícita. A confirmação informará que uma gravação ativa será encerrada antes do desligamento quando aplicável.

### Background service worker

O service worker continuará sendo o ponto de coordenação da gravação. Ele receberá do popup a solicitação de desligamento e:

1. Consultará o estado de gravação.
2. Se houver gravação, enviará a mensagem de parada ao offscreen e aguardará a resposta depois do handshake `ended`.
3. Só após a parada terminar com sucesso solicitará `stop` ao host Native Messaging.
4. Informará ao popup o resultado final e o estado confirmado pelo `/health`.

O desligamento deve ser idempotente: se o servidor já estiver parado, o resultado será tratado como sucesso; se o job não existir, não haverá erro apresentado como falha.

### Host Native Messaging

Será criado um host local com protocolo JSON compatível com Native Messaging. Ele aceitará somente:

- `status`: consulta `/health` e retorna `online` ou `offline`.
- `start`: consulta primeiro `/health`; se estiver offline, executa o `launchctl submit` documentado para `com.armel.gravador-servidor` e aguarda o `/health` responder.
- `stop`: remove `com.armel.gravador-servidor` e confirma que o job e o `/health` deixaram de responder.

O host não interpretará campos como comandos, caminhos ou argumentos vindos da extensão. O caminho da raiz do projeto, o nome do job, a porta e o log serão valores fixos/configurados durante a instalação.

Será fornecido um script de instalação que registra o manifesto do host Native Messaging para o Chrome, usando o caminho absoluto do projeto e a origem da extensão. Caso a ponte não esteja instalada ou não possa ser conectada, o popup exibirá uma mensagem orientando a instalação.

## Fluxos principais

### Ligar

`popup → host.start → /health inicial → launchctl submit → polling /health → host responde → popup Online`.

Se `/health` não responder dentro do limite, o popup mostrará erro e poderá tentar novamente. O log previsto continuará sendo `/tmp/gravador_server.log`.

### Desligar sem gravação

`popup → confirmação → host.stop → launchctl remove → confirmação de job/porta → popup Offline`.

### Desligar com gravação

`popup → confirmação → background stop → offscreen envia end → servidor responde ended → tracks e offscreen são liberados → host.stop → popup Offline`.

Se o handshake não confirmar `ended`, a extensão não deve declarar que o arquivo foi salvo. O comportamento de recuperação existente — fechamento da conexão e salvamento parcial pelo servidor — será preservado e o popup informará que o desligamento não foi concluído com confirmação plena.

## Tratamento de erros

- Host ausente: informar que a ponte local precisa ser instalada.
- Servidor já online ao ligar: não criar segundo processo; tratar como sucesso.
- Job ausente ao desligar: confirmar o estado real e tratar como já desligado.
- Falha no `launchctl`: mostrar erro retornado e manter o servidor como estado desconhecido até nova consulta.
- Timeout de inicialização: não habilitar gravação; oferecer nova tentativa.
- Falha ao encerrar gravação: não executar o desligamento automático sem informar claramente a falha; preservar o áudio parcial conforme o fluxo atual.
- Popup fechado durante a operação: o service worker deve manter a operação e o próximo popup deve consultar o estado real novamente.

## Testes e critérios de aceitação

O trabalho será considerado concluído quando:

- O host tiver testes para `status`, `start`, `stop`, operação idempotente e operação desconhecida.
- A extensão tiver testes para as transições de estado e mensagens de erro.
- Houver teste cobrindo desligamento sem gravação.
- Houver teste cobrindo desligamento com gravação e verificando a ordem `ended` antes de `stop`.
- O fluxo atual de gravação e os testes existentes continuarem passando.
- A instalação documentada permitir conectar o popup ao host sem configuração manual adicional além da instalação prevista.
- O popup nunca habilitar `Gravar` antes da confirmação de `/health`.
- O servidor não for deixado ligado quando o usuário confirmar desligamento, salvo falha explicitamente reportada.

## Arquivos previstos

- `extension/popup.html` e `extension/popup.js`: indicador, botões, confirmação e estados.
- `extension/background.js`: coordenação da parada antes do desligamento.
- Novo módulo de controle do servidor na extensão, para facilitar testes.
- Novo diretório ou módulo do host Native Messaging e seu manifesto.
- Script de instalação do host.
- Testes Node do popup/controlador e testes do host.
- `README.md`, `mapa.md` e `AGENTS.md`: instalação, uso, segurança e troubleshooting.

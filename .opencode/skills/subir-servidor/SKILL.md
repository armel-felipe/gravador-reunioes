---
name: subir-servidor
description: "Sobe ou para o servidor local de captura do Gravador de Reuniões (./start.sh em 127.0.0.1:8765). Acionar quando o usuário pedir \"sobe o servidor\", \"inicia o servidor\", \"liga o gravador\", \"para o servidor\", \"desliga o gravador\", \"servidor está no ar?\" ou similar."
---

# Subir / Parar Servidor

## Quando usar
Quando o usuário pedir para subir, iniciar, ligar, parar, desligar ou verificar o servidor de captura de áudio do projeto.

## Antes de subir
Cheque se já está no ar:

```bash
curl -s -m 5 http://127.0.0.1:8765/health
```

Se responder `{"status":"ok"}`, o servidor já está de pé — apenas confirme ao usuário e encerre.

**Atenção ao sandbox:** dentro do sandbox o `curl` para `127.0.0.1` pode falhar (exit 7) mesmo com o servidor no ar. Se o resultado parecer contraditório com o `launchctl list`, repita a checagem fora do sandbox antes de decidir.

## Passos para subir

1. **Subir desacoplado da sessão.** Rodar da raiz do projeto:

   ```bash
   launchctl submit -l com.armel.gravador-servidor -- /bin/bash -lc 'cd "<raiz do projeto>" && exec ./start.sh >> /tmp/gravador_server.log 2>&1'
   ```

   Não rode `./start.sh` em primeiro plano nem com `&` simples: o processo morre quando a sessão/terminal termina (foi o que já aconteceu aqui). O `launchctl submit` entrega o processo ao launchd, que o mantém vivo fora da sessão.

2. **Confirmar que respondeu.** Aguarde ~5s e cheque de novo:

   ```bash
   curl -s -m 5 http://127.0.0.1:8765/health
   ```

   Se não responder, leia `/tmp/gravador_server.log` e reporte o erro.

3. **Reportar** o PID (`launchctl list | grep gravador-servidor`) e que o log fica em `/tmp/gravador_server.log`.

## Passos para parar

1. **Cheque se está no ar:**

   ```bash
   launchctl list | grep gravador-servidor
   curl -s -m 5 http://127.0.0.1:8765/health
   ```

   Se o job não aparecer no `launchctl` e o `/health` não responder, o servidor já está parado — apenas confirme ao usuário e encerre.

2. **Remover o job do launchd:**

   ```bash
   launchctl remove com.armel.gravador-servidor
   ```

3. **Confirmar que parou.** Aguarde ~2s e cheque de novo:

   ```bash
   launchctl list | grep gravador-servidor
   curl -s -m 5 http://127.0.0.1:8765/health
   ```

   O `grep` não deve encontrar o job (exit 1) e o `/health` deve falhar (porta fechada). Se o `/health` ainda responder, repita a checagem fora do sandbox antes de concluir.

4. **Reportar** que o servidor foi parado e que, para voltar, basta pedir de novo para subir.

## Notas

- **Permissão:** abrir a porta 8765 é bloqueado pelo sandbox — subir o servidor exige execução fora do sandbox; a checagem do `/health` também pode precisar.
- **Duração:** o job vive até logout ou reboot; não reinicia sozinho depois. Basta pedir de novo para subir.
- **Primeira execução:** `./start.sh` cria o `.venv` e instala as dependências — pode demorar alguns minutos.
- **Porta ocupada:** se o `/health` já responde, não suba outro processo (o novo morreria por conflito de porta).

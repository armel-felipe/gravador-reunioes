---
name: subir-servidor
description: "Sobe o servidor local de captura do Gravador de Reuniões (./start.sh em 127.0.0.1:8765). Acionar quando o usuário pedir \"sobe o servidor\", \"inicia o servidor\", \"liga o gravador\", \"servidor está no ar?\" ou similar."
---

# Subir Servidor

## Quando usar
Quando o usuário pedir para subir, iniciar, ligar ou verificar o servidor de captura de áudio do projeto.

## Antes de subir
Cheque se já está no ar:

```bash
curl -s -m 5 http://127.0.0.1:8765/health
```

Se responder `{"status":"ok"}`, o servidor já está de pé — apenas confirme ao usuário e encerre.

## Passos

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

## Notas

- **Permissão:** abrir a porta 8765 é bloqueado pelo sandbox — rode o comando com permissão elevada (fora do sandbox).
- **Parar:** `launchctl remove com.armel.gravador-servidor`
- **Duração:** o job vive até logout ou reboot; não reinicia sozinho depois. Basta pedir de novo para subir.
- **Primeira execução:** `./start.sh` cria o `.venv` e instala as dependências — pode demorar alguns minutos.
- **Porta ocupada:** se o `/health` já responde, não suba outro processo (o novo morreria por conflito de porta).

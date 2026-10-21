# Controle automático do servidor pela extensão — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir ligar, consultar e desligar o servidor local diretamente pelo popup da extensão Chrome, encerrando uma gravação ativa antes do desligamento confirmado.

**Architecture:** A extensão MV3 usará `chrome.runtime.sendNativeMessage` para conversar com um host local restrito às ações `status`, `start` e `stop`. O host chamará somente os comandos fixos do job `com.armel.gravador-servidor` e verificará `http://127.0.0.1:8765/health`; o service worker continuará coordenando a parada segura do offscreen antes de pedir `stop` ao host.

**Tech Stack:** Chrome Manifest V3, JavaScript sem framework, Native Messaging JSON, Python 3 stdlib para o host, `launchctl`, Node `node:test`, `pytest`.

## Global Constraints

- O servidor deve continuar escutando somente em `127.0.0.1:8765`.
- O job deve continuar sendo `com.armel.gravador-servidor`.
- O start deve continuar desacoplado via `launchctl submit` e `./start.sh`.
- O host não pode executar comandos arbitrários enviados pela extensão.
- O desligamento com gravação deve aguardar a confirmação `ended` antes de remover o job.
- Não ler, editar ou versionar `.env`.
- Não apagar, mover ou reorganizar `99_material/`.
- Testes existentes devem continuar passando: `.venv/bin/python -m pytest scripts/ server/ -v` e testes Node da extensão.

## File Map

- Create `native_host/server_control.py`: protocolo Native Messaging e controlador restrito do servidor.
- Create `native_host/test_server_control.py`: testes unitários do controlador e protocolo.
- Create `native_host/install_native_host.sh`: registro do host para o Chrome do usuário atual.
- Modify `extension/manifest.json`: permissão `nativeMessaging`.
- Modify `extension/popup.html`: status do servidor, controle ligar/desligar e confirmação.
- Modify `extension/popup.js`: máquina de estados do servidor e ações do popup.
- Modify `extension/background.js`: mensagens de status/start/stop e parada segura antes do stop do host.
- Create `extension/server-control.js`: funções puras de estado/polling testáveis pelo Node.
- Create `extension/server-control.test.js`: testes do controlador de estado e polling.
- Modify `extension/background-start.test.js` and `extension/background-stop.test.js`: mocks e ordem das mensagens do novo fluxo.
- Modify `README.md`, `mapa.md`, `AGENTS.md`: instalação, uso, troubleshooting e governança operacional.

### Task 1: Criar controlador Python do servidor e protocolo Native Messaging

**Files:**
- Create: `native_host/server_control.py`
- Test: `native_host/test_server_control.py`

**Interfaces:**
- Consumes: ações JSON `{ "action": "status" | "start" | "stop" }` pelo stdin Native Messaging.
- Produces: respostas JSON `{ "ok": true, "action": ..., "online": bool }` ou `{ "ok": false, "error": string }`.

- [ ] **Step 1: Escrever testes de unidade para saúde, start, stop e ação inválida**

  Testar `ServerController.handle(action)` com funções injetadas de health e subprocesso. Verificar que `start` não chama `launchctl` quando o servidor já está online; que `stop` é idempotente; e que ação desconhecida retorna erro sem executar subprocesso.

- [ ] **Step 2: Rodar os testes para confirmar a falha**

  Run: `python3 -m pytest native_host/test_server_control.py -q`

  Expected: FAIL porque `native_host/server_control.py` ainda não existe.

- [ ] **Step 3: Implementar o controlador sem shell arbitrário**

  Implementar `ServerController` com `health_url`, `project_root`, `job_label` e `log_path` fixos/configurados pelo próprio host. Usar `urllib.request.urlopen` para health e `subprocess.run` com listas de argumentos para `launchctl`; o único comando shell permitido será o script fixo `/bin/bash -lc 'cd <raiz fixa> && exec ./start.sh >> /tmp/gravador_server.log 2>&1'` montado internamente pelo instalador/controlador, nunca recebido da extensão.

- [ ] **Step 4: Implementar framing Native Messaging**

  Ler quatro bytes little-endian, depois exatamente o payload JSON; responder com quatro bytes de comprimento e JSON UTF-8. Processar mensagens até EOF, ignorar qualquer ação fora de `status`, `start` e `stop`, e escrever diagnósticos somente em stderr.

- [ ] **Step 5: Rodar os testes para confirmar a passagem**

  Run: `python3 -m pytest native_host/test_server_control.py -q`

  Expected: todos os testes PASS.

- [ ] **Step 6: Commitar o componente isolado**

  Run: `git add native_host/server_control.py native_host/test_server_control.py && git commit -m "feat: add native server controller"`

### Task 2: Registrar e instalar o host Native Messaging

**Files:**
- Create: `native_host/install_native_host.sh`
- Modify: `extension/manifest.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: raiz atual do projeto e `EXTENSION_ID` opcional.
- Produces: manifesto `com.armel.gravador.server.json` em `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/` apontando para o host executável.

- [ ] **Step 1: Escrever teste estático do instalador**

  Verificar com `bash -n native_host/install_native_host.sh` que o script é sintaticamente válido e com `rg` que o manifesto gerado contém `name`, `type: stdio`, `path` absoluto e `allowed_origins` para `chrome-extension://${EXTENSION_ID}`.

- [ ] **Step 2: Implementar o instalador**

  Criar um wrapper executável absoluto que invoque `python3 <raiz>/native_host/server_control.py`, criar o diretório NativeMessagingHosts, exigir `EXTENSION_ID` quando não for fornecido, escrever o manifesto com um arquivo temporário no mesmo diretório e mover o arquivo para o destino. Não tocar em `.env`.

- [ ] **Step 3: Adicionar `nativeMessaging` ao Manifest V3**

  Manter permissões existentes e adicionar somente `nativeMessaging`. Não ampliar `host_permissions` além das permissões já usadas.

- [ ] **Step 4: Documentar instalação e diagnóstico**

  Documentar carregar a extensão, obter o ID em `chrome://extensions`, executar `EXTENSION_ID=<id> ./native_host/install_native_host.sh`, recarregar a extensão e testar `Ligar servidor`. Documentar o log `/tmp/gravador_server.log` e a mensagem de host ausente.

- [ ] **Step 5: Validar o instalador sem escrever fora do destino real**

  Run: `bash -n native_host/install_native_host.sh`

  Expected: exit 0. Fazer o teste de geração usando um diretório temporário explicitamente fornecido pelo script/teste, sem alterar o manifesto real do Chrome durante o teste automatizado.

- [ ] **Step 6: Commitar instalação e manifesto**

  Run: `git add native_host/install_native_host.sh extension/manifest.json README.md && git commit -m "feat: register chrome native messaging host"`

### Task 3: Integrar o host ao service worker

**Files:**
- Modify: `extension/background.js`
- Modify: `extension/background-start.test.js`
- Modify: `extension/background-stop.test.js`

**Interfaces:**
- Consumes: mensagens popup `{ type: "server:status" | "server:start" | "server:stop" }`.
- Produces: respostas `{ ok, online, error? }`; `server:stop` só chama Native Messaging depois de `offscreen:stop` concluir.

- [ ] **Step 1: Adicionar testes de mensagens Native Messaging**

  Mockar `chrome.runtime.sendNativeMessage` e verificar que status usa `{ action: "status" }`, start usa `{ action: "start" }` e stop usa `{ action: "stop" }`.

- [ ] **Step 2: Adicionar teste de ordem para gravação ativa**

  Fazer o mock do offscreen resolver depois de registrar `ended`, fazer o mock Native Messaging registrar `stop`, e afirmar que `stop` ocorre depois da resposta do offscreen.

- [ ] **Step 3: Rodar os testes para confirmar a falha**

  Run: `node --test extension/background-start.test.js extension/background-stop.test.js`

  Expected: FAIL nos testes novos porque os handlers ainda não existem.

- [ ] **Step 4: Implementar `sendNativeServerCommand` e handlers**

  Adicionar no service worker uma função que chama `chrome.runtime.sendNativeMessage("com.armel.gravador.server", { action })`, normaliza host ausente/erro e retorna resposta serializável. Adicionar handlers para status/start/stop; no stop, aguardar a parada existente antes de chamar o host.

- [ ] **Step 5: Rodar os testes da extensão**

  Run: `node --test extension/*.test.js`

  Expected: todos os testes PASS.

- [ ] **Step 6: Commitar integração do service worker**

  Run: `git add extension/background.js extension/background-start.test.js extension/background-stop.test.js && git commit -m "feat: control server from extension background"`

### Task 4: Implementar estado e interface do popup

**Files:**
- Create: `extension/server-control.js`
- Create: `extension/server-control.test.js`
- Modify: `extension/popup.html`
- Modify: `extension/popup.js`

**Interfaces:**
- Consumes: respostas do service worker para status/start/stop e estado de gravação atual.
- Produces: estados visuais `Verificando`, `Offline`, `Ligando`, `Online`, `Desligando` e `Erro`; botão de gravação habilitado somente em `Online`.

- [ ] **Step 1: Escrever testes do controlador de estado**

  Testar `nextServerState` e `aguardarServidorOnline` para offline, online, timeout e erro do host. O polling deve ter limite de tentativas e atraso injetável para ser determinístico.

- [ ] **Step 2: Rodar testes para confirmar a falha**

  Run: `node --test extension/server-control.test.js`

  Expected: FAIL porque o módulo ainda não existe.

- [ ] **Step 3: Implementar controlador pequeno e testável**

  Exportar funções sem DOM para mapear respostas a estados e aguardar `server:status` positivo; manter toda a comunicação Chrome em callbacks passados pelo popup.

- [ ] **Step 4: Adicionar markup da interface**

  Adicionar `#serverStatus`, `#serverToggle` e um `<dialog id="serverConfirm">` com botões Cancelar/Confirmar. Manter o botão `Gravar`, timer, campo de nome e controle de microfone existentes.

- [ ] **Step 5: Integrar o popup**

  Ao abrir, consultar status. Offline mostra `Ligar servidor`; online mostra `Desligar servidor`. Ligar chama `server:start`, aguarda health confirmado e só então habilita Gravar. Desligar abre confirmação; ao confirmar chama `server:stop`, com o background cuidando da parada da gravação. Reabrir o popup deve sempre consultar o estado real, sem depender somente de estado em memória.

- [ ] **Step 6: Validar testes da extensão e lint sintático**

  Run: `node --test extension/*.test.js`

  Expected: todos os testes PASS. Run: `node --check extension/popup.js && node --check extension/server-control.js`.

- [ ] **Step 7: Commitar interface e controlador**

  Run: `git add extension/server-control.js extension/server-control.test.js extension/popup.html extension/popup.js && git commit -m "feat: add server controls to popup"`

### Task 5: Atualizar mapa operacional e executar verificação completa

**Files:**
- Modify: `README.md`
- Modify: `mapa.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: comportamento final implementado nas Tasks 1–4.
- Produces: instruções reproduzíveis de instalação, uso, falhas e limites de segurança.

- [ ] **Step 1: Atualizar documentação operacional**

  Explicar o botão de ligar/desligar, a confirmação, o encerramento prévio da gravação, a instalação Native Messaging e o caminho do log. Manter explícito que o processamento das gravações continua manual no chat.

- [ ] **Step 2: Verificar que os arquivos documentados existem**

  Run: `rg -n "native_host|nativeMessaging|Ligar servidor|Desligar servidor|com.armel.gravador-servidor" README.md mapa.md AGENTS.md extension native_host`

  Expected: referências presentes e sem caminhos inexistentes.

- [ ] **Step 3: Rodar a suíte JavaScript**

  Run: `node --test extension/*.test.js`

  Expected: PASS.

- [ ] **Step 4: Rodar a suíte Python documentada**

  Run: `.venv/bin/python -m pytest scripts/ server/ native_host/ -v`

  Expected: PASS; se `.venv` não existir, reportar a limitação sem instalar dependências automaticamente.

- [ ] **Step 5: Fazer revisão final de diff**

  Run: `git diff --check && git status --short`

  Expected: sem erros de whitespace; somente arquivos da feature e alterações previamente existentes aparecem no status.

- [ ] **Step 6: Commitar documentação e verificação**

  Run: `git add README.md mapa.md AGENTS.md && git commit -m "docs: document extension server controls"`

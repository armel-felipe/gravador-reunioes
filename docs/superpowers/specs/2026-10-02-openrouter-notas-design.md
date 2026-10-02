# Design — OpenRouter como provedor de geração de notas

**Data:** 2026-10-02
**Status:** Aprovado pelo usuário
**Task relacionada:** R-010

## 1. Objetivo

Permitir que a geração de notas (`scripts/04_notas.py`) use, além do Ollama local e cloud, um modelo servido pelo OpenRouter — inicialmente o **`xiaomi/mimo-v2.6-flash`**.

Duas formas de escolha, ambas suportadas:

1. **Padrão no `config.yaml`** — o provedor corrente fica salvo no arquivo.
2. **Pedido na conversa** — ex.: *"gera as notas dessa reunião com o modelo do OpenRouter"*. A skill **edita o `config.yaml` primeiro e depois roda** o passo de notas. O ajuste **persiste** até o usuário pedir outra coisa ou editar o arquivo por conta própria.

## 2. Contexto atual

- `config.yaml` → seção `ollama` com `provider: local | cloud`.
- `scripts/notas.py` → `chamar_ollama(cfg, prompt)` decide endpoint/payload conforme o provider; `gerar_notas_map_reduce()` monta os prompts (bloco único ou map-reduce) e chama essa função.
- O caminho `cloud` já fala o protocolo OpenAI (`POST {base}/v1/chat/completions`, `Authorization: Bearer <chave>`, resposta em `choices[0].message.content`) — exatamente o mesmo formato do OpenRouter. A mudança é, portanto, pequena: um novo provedor no despacho.
- A skill `processar-gravacao` hoje troca o modelo no `config.yaml`, roda e **restaura** o valor anterior. Esse comportamento muda: o ajuste passa a persistir.

## 3. Configuração (`config.yaml`)

Seção nova no topo, com o seletor, e um bloco para o OpenRouter:

```yaml
notas:
  provider: "ollama"        # ollama | openrouter

ollama:
  provider: "local"         # local | cloud  (inalterado)
  local_model: "qwen3.6:35b-a3b-q4_K_M"
  cloud_model: "glm-5.3-flash:cloud"
  cloud_base_url: "https://ollama.com"
  cloud_api_key_env: "LPR_BZ685_OLLAMA_API_KEY"

openrouter:
  model: "xiaomi/mimo-v2.6-flash"
  base_url: "https://openrouter.ai/api"    # base SEM /v1; o código acrescenta /v1/chat/completions
  api_key_env: "OPENROUTER_API_KEY"
  reasoning: false          # false desliga o modo de raciocínio; true usa o padrão do provedor
```

Semântica:

- **`notas.provider`** — `ollama` (padrão quando a seção `notas` não existir, para não quebrar config antigo) ou `openrouter`.
- **`openrouter.base_url`** — segue a mesma convenção do `ollama.cloud_base_url`: guardada **sem** `/v1`; o código acrescenta `/v1/chat/completions`.
- **`openrouter.api_key_env`** — contém apenas o **nome** da variável de ambiente com a chave. A chave em si fica no `.env`, que não é lido, editado nem versionado (regra do `AGENTS.md`).
- **`openrouter.reasoning`** — `false` envia `"reasoning": {"enabled": false}` no payload (recomendado para o MiMo-V2.6-Flash: modelo de raciocínio, que com o "pensamento" ligado pode demorar muito ou devolver conteúdo vazio); `true` omite o campo e deixa o comportamento padrão do provedor.

`.env.example` ganha a linha comentada da chave nova (sem valor real):

```
# Chave do OpenRouter (criar em https://openrouter.ai/keys)
# Necessária apenas quando notas.provider = openrouter
OPENROUTER_API_KEY=
```

## 4. Código (`scripts/notas.py`)

### 4.1 Despacho por provedor

`chamar_ollama()` deixa de existir como tal e passa a ser `chamar_modelo(cfg, prompt)`, que despacha pelo `notas.provider`:

| `notas.provider` | Chamada | Modelo | Autenticação |
|---|---|---|---|
| `ollama` (ou seção ausente) | `POST http://localhost:11434/api/generate` | `ollama.local_model` | nenhuma |
| `ollama` com `ollama.provider: cloud` | `POST {ollama.cloud_base_url}/v1/chat/completions` | `ollama.cloud_model` | Bearer `ollama.cloud_api_key_env` |
| `openrouter` | `POST {openrouter.base_url}/v1/chat/completions` | `openrouter.model` | Bearer `openrouter.api_key_env` |

O comportamento do Ollama local e cloud **não muda** — mesma URL, payload e modelo de hoje.

### 4.2 Seams testáveis

Para permitir teste sem rede nem gasto de créditos, a montagem da requisição fica separada do envio:

- **`montar_requisicao(cfg, prompt) -> (url, payload, headers, formato)`** — função pura; decide URL, payload, cabeçalhos e o **formato da resposta** (`ollama` para o Ollama local; `openai` para o Ollama Cloud e o OpenRouter); valida o provedor e a presença da chave.
- **`extrair_texto(formato, dados) -> str`** — extrai o texto conforme o formato: `response` no formato `ollama`; `choices[0].message.content` no formato `openai` (Ollama Cloud e OpenRouter).
- **`chamar_modelo(cfg, prompt) -> str`** — usa as duas acima, faz o `POST` com `requests` (timeout de 600 s, como hoje) e devolve o texto.

O map-reduce, os prompts e `gerar_notas_map_reduce()` permanecem inalterados, apenas trocando `chamar_ollama` por `chamar_modelo`.

### 4.3 Tratamento de erros

Os erros passam a ser explícitos, antes e depois da chamada:

| Situação | Mensagem |
|---|---|
| `notas.provider` desconhecido | `provider inválido: 'X' (use 'ollama' ou 'openrouter')` |
| `provider = openrouter` e `openrouter.model` vazio | `modelo do OpenRouter não configurado — defina openrouter.model no config.yaml` |
| Variável de ambiente da chave ausente/vazia | `API key não configurada — defina a env var <NOME>` |
| HTTP 4xx/5xx (chave inválida, sem créditos, modelo inexistente) | erro com o status e o **corpo da resposta** da API (hoje o motivo é engolido pelo `raise_for_status()`) |
| Resposta válida, mas sem texto e com `reasoning` preenchido | mensagem explicando que o modelo gastou o limite no raciocínio e sugerindo `openrouter.reasoning: false` |

Não há **fallback automático** entre provedores: se o escolhido falhar, o erro sobe claro e nenhuma nota é gravada (o script só escreve o arquivo no final).

## 5. Skill `processar-gravacao`

O passo 2 da skill passa a descrever:

- O provedor padrão vem de `notas.provider` no `config.yaml`.
- Um pedido no chat do tipo *"usa o OpenRouter"* ou *"usa o `<modelo>`"* implica: **editar o `config.yaml` (o ajuste permanece)** e só então rodar `04_notas.py`.
- A instrução antiga de *"restaure depois"* é removida.

## 6. Documentação

- **`README.md`** — visão geral e características; tabela de dependências (OpenRouter como opção de nuvem); tabela do `config.yaml` (`notas.provider` e as chaves `openrouter.*`); nota sobre trocar o provedor/modelo no chat; troubleshooting (erro de chave, sem créditos).
- **`mapa.md`** — descrição do `04_notas.py` e a linha "Modelo" da skill `processar-gravacao`.
- **`ROADMAP.md`** — nova entrada **R-010**.
- **`.env.example`** — linha comentada do `OPENROUTER_API_KEY`.

## 7. Testes

Testes novos em `scripts/test_notas.py`, **sem rede e sem chave real** (usam `monkeypatch`/`os.environ`):

1. `notas.provider` ausente ou `ollama` → comportamento atual (local e cloud): URL, modelo e presença/ausência de `Authorization`.
2. `provider: openrouter` → URL `https://openrouter.ai/api/v1/chat/completions`, modelo `xiaomi/mimo-v2.6-flash`, cabeçalho `Authorization: Bearer <chave>` e `"reasoning": {"enabled": false}`.
3. `provider: openrouter` com `reasoning: true` → payload **sem** a chave `reasoning`.
4. `provider` inválido → erro com mensagem clara.
5. `provider: openrouter` sem a variável de ambiente → erro citando o nome da variável.
6. `extrair_texto` para os dois formatos de resposta (`ollama` e `openai`).

Depois, rodar a suíte completa do projeto:

```bash
.venv/bin/python -m pytest scripts/ server/ -v
```

**Verificação real (opcional, manual):** rodar `04_notas.py` uma vez em um evento já transcrito com `provider: openrouter`, para confirmar a geração de ponta a ponta. Consome créditos do OpenRouter e depende da chave no `.env`; só será feito com autorização explícita.

## 8. Fora do escopo

- Fallback automático entre provedores (ex.: OpenRouter falhou → Ollama).
- Flag de linha de comando para escolher o modelo (o fluxo aprovado é via `config.yaml`).
- Outros provedores além de local, Ollama Cloud e OpenRouter.
- Streaming de resposta, controle de custo/`max_tokens` e cabeçalhos opcionais de atribuição do OpenRouter (`HTTP-Referer`, `X-Title`).
- Alterar prompts, qualidade ou o esquema de map-reduce.

## 9. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Modelo de raciocínio devolve resposta vazia ou demora demais | `openrouter.reasoning: false` por padrão + erro claro se o texto vier vazio |
| Erro de API sem explicação (chave, créditos, modelo) | Mensagem passa a incluir o corpo da resposta da API |
| Chave vazada em versionamento | Apenas o **nome** da env var vai para o `config.yaml`; a chave fica no `.env` (ignorado pelo git) |
| Quebra de config antigo | Se a seção `notas` não existir, o código assume `ollama` |

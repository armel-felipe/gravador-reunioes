# Teste OpenRouter Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar um notebook Jupyter simples para testar a chave, o endpoint e o modelo OpenRouter configurados no projeto e iniciar um chat via `input()`.

**Architecture:** O notebook lerá `config.yaml` e `.env` a partir da raiz do projeto, selecionará o perfil `openrouter` sem alterar a configuração persistida e fará chamadas OpenAI-compatible diretamente com `requests`. A chave será usada somente no header Authorization e nunca será impressa.

**Tech Stack:** Jupyter Notebook, Python, `python-dotenv`, PyYAML e `requests` já usados pelo projeto.

## Global Constraints

- Nunca ler, expor, editar ou versionar o conteúdo de `.env`.
- Não alterar `config.yaml` para executar o teste.
- O modelo inicial deve vir de `llm.providers.openrouter.model`.
- O usuário pode substituir o modelo em uma variável do notebook.
- O chat deve ser feito por `input()`, sem dependência de widgets.
- As chamadas devem usar o endpoint derivado do perfil, sem fixar uma chave no código.

---

### Task 1: Criar notebook de diagnóstico e chat

**Files:**
- Create: `notebooks/teste_openrouter_chat.ipynb`

**Interfaces:**
- Consome: `config.yaml`, `.env`, `llm.providers.openrouter` e `OPENROUTER_API_KEY`.
- Produz: célula de teste de conexão e função `chat_openrouter(mensagens, modelo=None)`.

- [ ] **Step 1: Criar células com carregamento seguro**

Criar células Markdown e Python que carreguem a configuração, usem `load_dotenv(ROOT / ".env")`, leiam a variável definida por `api_key_env`, validem sua presença e exponham apenas o endpoint e o modelo, nunca a chave.

- [ ] **Step 2: Implementar a chamada OpenAI-compatible**

Adicionar `chat_openrouter(mensagens, modelo=None, timeout=60)`, usando `POST {base_url}/chat/completions`, o modelo selecionado, `stream: false`, `max_tokens` do perfil e `Authorization: Bearer <chave>`. A função deve retornar conteúdo e duração; erros devem mostrar somente status e detalhe da API.

- [ ] **Step 3: Adicionar teste mínimo e loop de chat**

Enviar `Responda exatamente: OPENROUTER_OK`, mostrar o status/tempo/modelo e iniciar um loop `input()` com histórico em memória. `/sair`, `/exit` e `sair` encerram o chat.

- [ ] **Step 4: Validar estrutura do notebook sem chamar a API**

Executar um verificador JSON e confirmar que o arquivo contém as células esperadas, que não contém uma chave hardcoded e que o código compila.

- [ ] **Step 5: Validar execução do carregamento sem exibir segredo**

Executar as células de preparação em processo controlado, usando a chave real somente na memória, e confirmar que endpoint e modelo são carregados sem imprimir o valor da chave.

- [ ] **Step 6: Documentar uso no notebook**

Incluir Markdown com:

```bash
.venv/bin/jupyter notebook notebooks/teste_openrouter_chat.ipynb
```

- [ ] **Step 7: Verificar mudanças**

Executar `git diff --check`; esperado: nenhum erro de whitespace.

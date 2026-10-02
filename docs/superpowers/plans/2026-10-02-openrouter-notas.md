# OpenRouter na Geração de Notas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que a geração de notas use, além do Ollama local e cloud, um modelo do OpenRouter — escolhido no `config.yaml` ou por pedido no chat, com o ajuste persistindo no arquivo.

**Architecture:** Um seletor `notas.provider` (`ollama` | `openrouter`) decide o caminho. Em `scripts/notas.py`, `montar_requisicao()` monta URL/payload/cabeçalhos/formato (função pura, testável sem rede) e `chamar_modelo()` envia o POST e trata os erros. O Ollama local e cloud continuam com o comportamento atual; o OpenRouter entra como mais um cliente do protocolo OpenAI. Prompts e map-reduce não mudam.

**Tech Stack:** Python 3.11+, `requests`, `python-dotenv`, `PyYAML`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-02-openrouter-notas-design.md`

## Global Constraints

- Rodar sempre da raiz do projeto, com o venv: `.venv/bin/python`.
- **Nunca ler, expor, editar ou versionar o `.env`.** A chave fica no `.env`; no `config.yaml` vai apenas o **nome** da variável de ambiente (`openrouter.api_key_env`). Usar `.env.example` como referência.
- `openrouter.base_url` é guardada **sem** `/v1`; o código acrescenta `/v1/chat/completions`.
- Timeout das chamadas HTTP: 600 s (igual ao atual).
- `notas.provider` ausente ⇒ assume `ollama` (não quebrar config antigo).
- Provedor inválido, chave ausente e modelo vazio ⇒ `RuntimeError` com mensagem clara; **sem fallback automático** entre provedores.
- Prompts, `REGRAS_QUALIDADE` e o esquema de map-reduce permanecem **inalterados**.
- Tudo em pt-BR (mensagens de erro, docs, comentários).
- Suíte de testes do projeto: `.venv/bin/python -m pytest scripts/ server/ -v`.

---

## File Structure

| Arquivo | Responsabilidade nesta mudança |
|---|---|
| `config.yaml` | Ganha a seção `notas` (seletor) e o bloco `openrouter` |
| `.env.example` | Ganha a linha comentada da chave `OPENROUTER_API_KEY` |
| `scripts/notas.py` | Ganha `montar_requisicao()`, `extrair_texto()` e `chamar_modelo()`; `chamar_ollama()` sai de cena |
| `scripts/test_notas.py` | Testes novos, sem rede e sem chave real |
| `.opencode/skills/processar-gravacao/SKILL.md` | Troca no chat edita o `config.yaml` e persiste |
| `README.md`, `mapa.md`, `ROADMAP.md` | Documentação e registro da task R-010 |

---

### Task 1: Configuração (`config.yaml` + `.env.example`)

**Files:**
- Modify: `config.yaml`
- Modify: `.env.example`
- Test: `scripts/test_notas.py`

**Interfaces:**
- Consumes: `common.load_config()` (já existe).
- Produces: chaves `notas.provider`, `openrouter.{model,base_url,api_key_env,reasoning}` no `config.yaml`, consumidas pelas Tasks 2 e 3.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente `from common import load_config` aos imports do topo de `scripts/test_notas.py` e, ao final do arquivo:

```python
def test_config_tem_seletor_e_bloco_openrouter():
    cfg = load_config()
    assert cfg["notas"]["provider"] in ("ollama", "openrouter")
    assert cfg["openrouter"]["model"] == "xiaomi/mimo-v2.6-flash"
    assert cfg["openrouter"]["base_url"] == "https://openrouter.ai/api"
    assert cfg["openrouter"]["api_key_env"] == "OPENROUTER_API_KEY"
    assert cfg["openrouter"]["reasoning"] is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest scripts/test_notas.py::test_config_tem_seletor_e_bloco_openrouter -v`
Expected: FAIL com `KeyError: 'notas'`.

- [ ] **Step 3: Editar `config.yaml`**

No topo do arquivo, antes de `whisper:`, insira:

```yaml
# Qual provedor gera as notas: ollama (local/cloud) ou openrouter
notas:
  provider: "ollama"        # ollama | openrouter
```

E, logo depois do bloco `ollama:` (antes de `caminhos:`), insira:

```yaml
openrouter:
  model: "xiaomi/mimo-v2.6-flash"          # id do modelo no OpenRouter
  base_url: "https://openrouter.ai/api"    # base SEM /v1; o código adiciona /v1/chat/completions
  api_key_env: "OPENROUTER_API_KEY"        # nome da env var com a chave (a chave fica no .env)
  reasoning: false                         # false desliga o modo raciocínio (recomendado para notas)
```

- [ ] **Step 4: Atualizar `.env.example`**

Acrescente ao final do arquivo:

```
# Chave do OpenRouter (criar em https://openrouter.ai/keys)
# Necessária apenas quando notas.provider = openrouter no config.yaml
OPENROUTER_API_KEY=
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/python -m pytest scripts/test_notas.py::test_config_tem_seletor_e_bloco_openrouter -v`
Expected: PASS.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest scripts/ server/ -v`
Expected: todos os testes passando (as chaves novas ainda não são usadas por código).

- [ ] **Step 7: Commit**

```bash
git add config.yaml .env.example scripts/test_notas.py
git commit -m "feat(config): secao notas e bloco openrouter"
```

---

### Task 2: `montar_requisicao()` — despacho por provedor (função pura)

**Files:**
- Modify: `scripts/notas.py` (acrescenta funções logo antes de `def chamar_ollama`, hoje na linha 147)
- Test: `scripts/test_notas.py`

**Interfaces:**
- Consumes: `config.yaml` da Task 1.
- Produces:
  - `montar_requisicao(cfg: dict, prompt: str) -> (url: str, payload: dict, headers: dict, formato: str)`
  - `formato` é `"ollama"` (resposta no campo `response`) ou `"openai"` (resposta em `choices[0].message.content`).

> Nesta task, `chamar_ollama` **continua existindo** — o pipeline segue funcionando e a suíte fica verde. A substituição acontece na Task 3.

- [ ] **Step 1: Escrever os testes que falham**

Em `scripts/test_notas.py`, troque a linha de import de `notas` por:

```python
from notas import (
    dividir_em_blocos,
    montar_prompt,
    montar_prompt_map,
    montar_prompt_reduce,
    montar_requisicao,
)
```

Acrescente `import pytest` no topo e, ao final do arquivo:

```python
CFG = {
    "notas": {"provider": "ollama"},
    "ollama": {
        "provider": "local",
        "local_model": "qwen3.6:35b-a3b-q4_K_M",
        "cloud_model": "glm-5.3-flash:cloud",
        "cloud_base_url": "https://ollama.com",
        "cloud_api_key_env": "OLLAMA_KEY_TESTE",
    },
    "openrouter": {
        "model": "xiaomi/mimo-v2.6-flash",
        "base_url": "https://openrouter.ai/api",
        "api_key_env": "OPENROUTER_KEY_TESTE",
        "reasoning": False,
    },
}


def test_requisicao_ollama_local():
    url, payload, headers, formato = montar_requisicao(CFG, "prompt de teste")
    assert url == "http://localhost:11434/api/generate"
    assert payload["model"] == "qwen3.6:35b-a3b-q4_K_M"
    assert payload["prompt"] == "prompt de teste"
    assert payload["stream"] is False
    assert headers == {}
    assert formato == "ollama"


def test_requisicao_ollama_cloud(monkeypatch):
    monkeypatch.setenv("OLLAMA_KEY_TESTE", "chave-ollama")
    cfg = {**CFG, "ollama": {**CFG["ollama"], "provider": "cloud"}}
    url, payload, headers, formato = montar_requisicao(cfg, "prompt de teste")
    assert url == "https://ollama.com/v1/chat/completions"
    assert payload["model"] == "glm-5.3-flash:cloud"
    assert payload["messages"] == [{"role": "user", "content": "prompt de teste"}]
    assert headers["Authorization"] == "Bearer chave-ollama"
    assert formato == "openai"


def test_requisicao_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TESTE", "chave-openrouter")
    cfg = {**CFG, "notas": {"provider": "openrouter"}}
    url, payload, headers, formato = montar_requisicao(cfg, "prompt de teste")
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert payload["model"] == "xiaomi/mimo-v2.6-flash"
    assert payload["messages"] == [{"role": "user", "content": "prompt de teste"}]
    assert payload["reasoning"] == {"enabled": False}
    assert headers["Authorization"] == "Bearer chave-openrouter"
    assert formato == "openai"


def test_requisicao_openrouter_com_raciocinio_ligado(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TESTE", "chave-openrouter")
    cfg = {
        **CFG,
        "notas": {"provider": "openrouter"},
        "openrouter": {**CFG["openrouter"], "reasoning": True},
    }
    _, payload, _, _ = montar_requisicao(cfg, "prompt")
    assert "reasoning" not in payload


def test_secao_notas_ausente_assume_ollama():
    cfg = {chave: valor for chave, valor in CFG.items() if chave != "notas"}
    url, _, _, formato = montar_requisicao(cfg, "prompt")
    assert url == "http://localhost:11434/api/generate"
    assert formato == "ollama"


def test_provider_invalido_gera_erro():
    cfg = {**CFG, "notas": {"provider": "gemini"}}
    with pytest.raises(RuntimeError, match="provider inválido"):
        montar_requisicao(cfg, "prompt")


def test_openrouter_sem_chave_gera_erro_citando_variavel(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEY_TESTE", raising=False)
    cfg = {**CFG, "notas": {"provider": "openrouter"}}
    with pytest.raises(RuntimeError, match="OPENROUTER_KEY_TESTE"):
        montar_requisicao(cfg, "prompt")


def test_openrouter_modelo_vazio_gera_erro(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TESTE", "chave")
    cfg = {
        **CFG,
        "notas": {"provider": "openrouter"},
        "openrouter": {**CFG["openrouter"], "model": "   "},
    }
    with pytest.raises(RuntimeError, match="openrouter.model"):
        montar_requisicao(cfg, "prompt")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest scripts/test_notas.py -k "requisicao or secao_notas or provider_invalido" -v`
Expected: FAIL com `ImportError: cannot import name 'montar_requisicao'`.

- [ ] **Step 3: Implementar o despacho**

Em `scripts/notas.py`, **acrescente** logo antes de `def chamar_ollama`:

```python
def _obrigatorio(secao: dict, chave: str, caminho: str) -> str:
    """Lê uma chave obrigatória da configuração, com erro claro se estiver vazia."""
    valor = str(secao.get(chave, "") or "").strip()
    if not valor:
        raise RuntimeError(f"{caminho} não configurado — defina {caminho} no config.yaml")
    return valor


def _ler_chave(env_name: str, caminho_config: str) -> str:
    """Lê a API key da env var indicada; o erro aponta os dois lados a ajustar."""
    api_key = os.environ.get(env_name, "")
    if not api_key:
        raise RuntimeError(
            f"API key não configurada — defina a env var {env_name} no .env "
            f"(ou ajuste {caminho_config} no config.yaml para o nome da variável que você usa)"
        )
    return api_key


def montar_requisicao(cfg: dict, prompt: str):
    """Monta (url, payload, headers, formato) para o provedor de notas.

    Função pura: não faz rede e não lê o .env (só o os.environ). É o único
    ponto onde a escolha do provedor é decidida. `formato` indica como ler a
    resposta: "ollama" → campo `response`; "openai" → `choices[0].message.content`.
    """
    provider = (cfg.get("notas") or {}).get("provider", "ollama") or "ollama"

    if provider == "ollama":
        secao = cfg["ollama"]
        modo = secao.get("provider", "local")
        if modo == "local":
            modelo = _obrigatorio(secao, "local_model", "ollama.local_model")
            payload = {"model": modelo, "prompt": prompt, "stream": False}
            return "http://localhost:11434/api/generate", payload, {}, "ollama"
        if modo == "cloud":
            base_url = _obrigatorio(secao, "cloud_base_url", "ollama.cloud_base_url").rstrip("/")
            modelo = _obrigatorio(secao, "cloud_model", "ollama.cloud_model")
            env_name = _obrigatorio(secao, "cloud_api_key_env", "ollama.cloud_api_key_env")
            headers = {"Authorization": f"Bearer {_ler_chave(env_name, 'ollama.cloud_api_key_env')}"}
            payload = {
                "model": modelo,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            return f"{base_url}/v1/chat/completions", payload, headers, "openai"
        raise RuntimeError(f"provider inválido: {modo!r} (use 'local' ou 'cloud')")

    if provider == "openrouter":
        secao = cfg["openrouter"]
        base_url = _obrigatorio(secao, "base_url", "openrouter.base_url").rstrip("/")
        modelo = _obrigatorio(secao, "model", "openrouter.model")
        env_name = _obrigatorio(secao, "api_key_env", "openrouter.api_key_env")
        headers = {"Authorization": f"Bearer {_ler_chave(env_name, 'openrouter.api_key_env')}"}
        payload = {
            "model": modelo,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if not secao.get("reasoning", False):
            payload["reasoning"] = {"enabled": False}
        return f"{base_url}/v1/chat/completions", payload, headers, "openai"

    raise RuntimeError(f"provider inválido: {provider!r} (use 'ollama' ou 'openrouter')")
```

- [ ] **Step 4: Rodar os testes da task**

Run: `.venv/bin/python -m pytest scripts/test_notas.py -k "requisicao or secao_notas or provider_invalido" -v`
Expected: PASS (8 testes novos).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest scripts/ server/ -v`
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add scripts/notas.py scripts/test_notas.py
git commit -m "feat(notas): despacho por provedor em montar_requisicao"
```

---

### Task 3: `extrair_texto()`, `chamar_modelo()` e fim do `chamar_ollama`

**Files:**
- Modify: `scripts/notas.py`
- Modify: `scripts/04_notas.py` (docstring)
- Test: `scripts/test_notas.py`

**Interfaces:**
- Consumes: `montar_requisicao()` (Task 2).
- Produces:
  - `extrair_texto(formato: str, dados: dict) -> str`
  - `_descrever_erro_api(resp) -> str`
  - `chamar_modelo(cfg: dict, prompt: str) -> str`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente `chamar_modelo`, `extrair_texto` e `gerar_notas_map_reduce` ao import de `notas` em `scripts/test_notas.py` e, ao final do arquivo:

```python
def test_extrair_texto_nos_dois_formatos():
    assert extrair_texto("ollama", {"response": "texto local"}) == "texto local"
    dados = {"choices": [{"message": {"content": "texto openai"}}]}
    assert extrair_texto("openai", dados) == "texto openai"


def test_extrair_texto_ausente_devolve_vazio():
    dados = {"choices": [{"message": {"reasoning": "pensou muito"}}]}
    assert extrair_texto("openai", dados) == ""


def test_chamar_modelo_erro_http_inclui_corpo(monkeypatch):
    class RespostaFalsa:
        status_code = 401
        text = '{"error": {"message": "No auth credentials found"}}'

        def json(self):
            raise AssertionError("não deve tentar ler JSON quando o status é de erro")

    monkeypatch.setattr("notas.requests.post", lambda *a, **k: RespostaFalsa())
    with pytest.raises(RuntimeError, match="No auth credentials found"):
        chamar_modelo(CFG, "prompt")


def test_chamar_modelo_devolve_texto(monkeypatch):
    class RespostaFalsa:
        status_code = 200
        text = ""

        def json(self):
            return {"response": "notas geradas"}

    monkeypatch.setattr("notas.requests.post", lambda *a, **k: RespostaFalsa())
    assert chamar_modelo(CFG, "prompt") == "notas geradas"


def test_chamar_modelo_resposta_vazia_por_raciocinio(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TESTE", "chave")

    class RespostaFalsa:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "", "reasoning": "pensou muito"}}]}

    monkeypatch.setattr("notas.requests.post", lambda *a, **k: RespostaFalsa())
    cfg = {**CFG, "notas": {"provider": "openrouter"}}
    with pytest.raises(RuntimeError, match="raciocínio"):
        chamar_modelo(cfg, "prompt")


def test_gerar_notas_usa_chamar_modelo(monkeypatch):
    chamadas = []

    def falso(cfg, prompt):
        chamadas.append(prompt)
        return "notas"

    monkeypatch.setattr("notas.chamar_modelo", falso)
    transcricao = "**[00:00:00] SPEAKER_00:** fala curta"
    assert gerar_notas_map_reduce(CFG, transcricao) == "notas"
    assert len(chamadas) == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest scripts/test_notas.py -k "extrair_texto or chamar_modelo" -v`
Expected: FAIL com `ImportError: cannot import name 'chamar_modelo'`.

- [ ] **Step 3: Implementar a chamada e a extração**

Em `scripts/notas.py`, logo **abaixo** de `montar_requisicao`, acrescente:

```python
def extrair_texto(formato: str, dados: dict) -> str:
    """Extrai o texto da resposta; devolve "" quando o provedor não mandou texto."""
    if formato == "ollama":
        return str(dados.get("response") or "")
    if formato == "openai":
        try:
            return str(dados["choices"][0]["message"].get("content") or "")
        except (KeyError, IndexError, TypeError):
            return ""
    raise RuntimeError(f"formato de resposta desconhecido: {formato!r}")


def _descrever_erro_api(resp) -> str:
    """Descreve um erro HTTP incluindo o corpo (chave, créditos, modelo inexistente)."""
    corpo = (getattr(resp, "text", "") or "").strip().replace("\n", " ")
    if len(corpo) > 500:
        corpo = corpo[:500] + "…"
    return f"HTTP {resp.status_code} — {corpo}" if corpo else f"HTTP {resp.status_code} (sem corpo)"


def chamar_modelo(cfg: dict, prompt: str) -> str:
    """Chama o provedor configurado e devolve o texto gerado."""
    url, payload, headers, formato = montar_requisicao(cfg, prompt)
    resp = requests.post(url, json=payload, headers=headers, timeout=600)
    if resp.status_code >= 400:
        raise RuntimeError(f"Falha ao chamar o modelo ({url}): {_descrever_erro_api(resp)}")
    try:
        dados = resp.json()
    except ValueError:
        raise RuntimeError(f"Resposta não é JSON válido ({url}): {resp.text[:200]!r}")
    texto = extrair_texto(formato, dados)
    if not texto.strip():
        dica = ""
        try:
            if dados["choices"][0]["message"].get("reasoning"):
                dica = " — o modelo gastou a resposta em raciocínio; use openrouter.reasoning: false"
        except (KeyError, IndexError, TypeError):
            pass
        raise RuntimeError(f"O modelo devolveu resposta vazia ({url}){dica}")
    return texto
```

- [ ] **Step 4: Remover a função antiga e religar o pipeline**

1. Em `scripts/notas.py`, **apague** a função `chamar_ollama` inteira.
2. Dentro de `gerar_notas_map_reduce`, troque as 3 chamadas `chamar_ollama(cfg, ...)` por `chamar_modelo(cfg, ...)`.
3. Em `scripts/notas.py`, linha 1, troque `via Ollama, com map-reduce` por `via Ollama (local/cloud) ou OpenRouter, com map-reduce`.
4. Em `scripts/04_notas.py`, linha 1, troque `via Ollama.` por `via Ollama ou OpenRouter.`

Confirme que não sobrou referência à função antiga:

Run: `grep -rn "chamar_ollama" scripts/ server/ .opencode/skills/`
Expected: nenhuma saída (código de saída 1).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest scripts/ server/ -v`
Expected: todos os testes passando.

- [ ] **Step 6: Commit**

```bash
git add scripts/notas.py scripts/04_notas.py scripts/test_notas.py
git commit -m "feat(notas): chamar_modelo com OpenRouter e erros claros"
```

---

### Task 4: Skill `processar-gravacao` — troca persistente

**Files:**
- Modify: `.opencode/skills/processar-gravacao/SKILL.md`

**Interfaces:**
- Consumes: nada (documentação operacional).
- Produces: regra que o agente segue ao receber um pedido de troca no chat.

- [ ] **Step 1: Substituir a linha do passo 2**

Em `.opencode/skills/processar-gravacao/SKILL.md`, substitua:

```
   - Se o usuário pediu outro modelo ("usa o gemma4"), edite `config.yaml` (ollama.local_model) antes do passo 04 e restaure depois.
```

por:

```
   - O provedor das notas vem de `notas.provider` no `config.yaml`: `ollama` (com `ollama.provider: local | cloud`) ou `openrouter`.
   - Se o usuário pedir outro provedor/modelo ("usa o OpenRouter", "usa o gemma4"), edite o `config.yaml` **antes** do passo 04 e **mantenha o ajuste** — não restaure o valor anterior. A escolha passa a valer para os próximos processamentos até o usuário pedir outra coisa ou editar o arquivo.
   - No OpenRouter, o modelo fica em `openrouter.model` e a chave na env var indicada em `openrouter.api_key_env` (nunca escreva a chave no `config.yaml`).
```

- [ ] **Step 2: Verificar e commitar**

Run: `grep -n "mantenha o ajuste" .opencode/skills/processar-gravacao/SKILL.md`
Expected: uma linha encontrada.

```bash
git add .opencode/skills/processar-gravacao/SKILL.md
git commit -m "docs(skill): troca de modelo/provedor persiste no config"
```

---

### Task 5: Documentação (`README.md`, `mapa.md`, `ROADMAP.md`)

**Files:**
- Modify: `README.md`
- Modify: `mapa.md`
- Modify: `ROADMAP.md`

**Interfaces:**
- Consumes: nada (só documentação).
- Produces: documentação do usuário e registro do R-010.

- [ ] **Step 1: Ajustar a visão geral e as funcionalidades do `README.md`**

Substitua a linha 3:

```
gera **notas, resumo e plano de ação** com **Ollama** — localmente por padrão, com opção de Ollama Cloud, orquestrado pelo OpenWork.
```

por:

```
gera **notas, resumo e plano de ação** com **Ollama** (local ou cloud) ou com um modelo do **OpenRouter**, orquestrado pelo OpenWork.
```

Substitua, no bullet de notas, `(Ollama local ou cloud)` por `(Ollama local, Ollama Cloud ou OpenRouter)`.

Substitua, no bullet de privacidade:

```
- 🔒 **100% local** — exceto a opção de usar Ollama cloud (com sua API key)
```

por:

```
- 🔒 **100% local** — exceto as opções de nuvem (Ollama Cloud ou OpenRouter), cada uma com a sua API key
```

Substitua, na árvore do projeto:

```
│   ├── 04_notas.py         ← Ollama: transcrição → resumo + plano de ação
```

por:

```
│   ├── 04_notas.py         ← LLM (Ollama/OpenRouter): transcrição → resumo + plano de ação
```

- [ ] **Step 2: Ajustar as tabelas do `README.md`**

Na tabela de requisitos, substitua:

```
| **Ollama** | ollama.com | Geração de notas (local) |
```

por:

```
| **Ollama** | ollama.com | Geração de notas (local ou cloud) |
| **OpenRouter** (opcional) | openrouter.ai | Geração de notas na nuvem via API key |
```

Logo **depois** do parágrafo que começa com `> **Nota sobre o Ollama:**`, acrescente:

```
>
> **Nota sobre o OpenRouter:** para gerar as notas com um modelo do OpenRouter, coloque a chave no `.env` (`OPENROUTER_API_KEY=seu_token`) e mude `notas.provider` para `openrouter` no `config.yaml`. O modelo vem de `openrouter.model` (padrão: `xiaomi/mimo-v2.6-flash`). Nesse modo, o conteúdo da transcrição é enviado ao OpenRouter.
>
> **Trocar na hora, pelo chat:** peça *"usa o OpenRouter"* ou *"usa o modelo X"*; o agente edita o `config.yaml` e o ajuste **permanece** até você pedir outra coisa. Para voltar ao padrão, peça *"volta a usar o Ollama local"*.
```

Na tabela de configuração (`## ⚙️ Configuração (config.yaml)`), acrescente abaixo da linha de `ollama.cloud_api_key_env`:

```
| `notas.provider` | Provedor das notas: `ollama` ou `openrouter` | `ollama` |
| `openrouter.model` | Modelo do OpenRouter | `xiaomi/mimo-v2.6-flash` |
| `openrouter.base_url` | URL base da API (sem `/v1`) | `https://openrouter.ai/api` |
| `openrouter.api_key_env` | Nome da env var com a chave | `OPENROUTER_API_KEY` |
| `openrouter.reasoning` | `false` desliga o modo raciocínio | `false` |
```

Na tabela de troubleshooting, acrescente:

```
| Notas falham com 401/402 no OpenRouter | Confira `OPENROUTER_API_KEY` no `.env` e os créditos na conta OpenRouter |
| Notas vazias com o MiMo | Deixe `openrouter.reasoning: false` no `config.yaml` |
```

- [ ] **Step 3: Atualizar o `mapa.md`**

Substitua, na seção da skill `processar-gravacao`:

```
**Modelo:** usa o `ollama.local_model`/`ollama.cloud_model` do `config.yaml`. Você pode trocar na hora: *"usa o gemma4 desta vez"*.
```

por:

```
**Modelo:** usa o provedor de `notas.provider` do `config.yaml` — Ollama (`ollama.local_model`/`ollama.cloud_model`) ou OpenRouter (`openrouter.model`). Você pode trocar na hora: *"usa o gemma4 desta vez"* ou *"usa o OpenRouter"* — e o ajuste fica salvo no `config.yaml`.
```

Substitua, na seção `04_notas.py`:

```
### `04_notas.py` — Geração de notas (Ollama)
```

por:

```
### `04_notas.py` — Geração de notas (Ollama ou OpenRouter)
```

E:

```
- **Tecnologia:** Ollama local (`http://localhost:11434`) ou cloud (OpenAI-compatible `/v1/chat/completions`), conforme `config.yaml`
```

por:

```
- **Tecnologia:** Ollama local (`http://localhost:11434`), Ollama cloud ou OpenRouter (ambos OpenAI-compatible `/v1/chat/completions`), conforme `notas.provider` no `config.yaml`
```

Na tabela de configuração, substitua a descrição do `config.yaml` por:

```
| `config.yaml` | Configuração central: modelo do Whisper, diarização, provedor das notas (Ollama local/cloud ou OpenRouter), caminhos, retenção de áudio |
```

- [ ] **Step 4: Adicionar o R-010 ao `ROADMAP.md`**

No topo da seção `## Tasks`, **antes** de `### R-009`, insira:

```
### R-010 — OpenRouter como provedor de geração de notas
- **Prioridade:** 🟡 Média
- **Status:** ✅ Concluída
- **Criada em:** 2026-10-02
- **Concluída em:** 2026-10-02
- **Motivo:** Poder gerar as notas com um modelo do OpenRouter (`xiaomi/mimo-v2.6-flash`), além do Ollama local e cloud, escolhendo no `config.yaml` ou pedindo na conversa.
- **Implementação:** seletor `notas.provider` (`ollama` | `openrouter`) + bloco `openrouter` no `config.yaml`; despacho por provedor em `scripts/notas.py` (`montar_requisicao`/`chamar_modelo`), com erro claro para chave ausente, modelo vazio e falha da API (inclui o corpo da resposta); `reasoning: false` desliga o modo raciocínio do MiMo.
- **Skill:** troca no chat edita o `config.yaml` e **persiste** (não restaura mais o valor anterior).
- **Design:** `docs/superpowers/specs/2026-10-02-openrouter-notas-design.md`
- **Validação:** <N> testes passando; verificação real com o OpenRouter: <pendente/feita>.
```

Substitua `<N>` pelo número real de testes que passaram e `<pendente/feita>` pelo estado da verificação real (a Task 6 é opcional).

- [ ] **Step 5: Verificar e commitar**

Run: `.venv/bin/python -m pytest scripts/ server/ -v`
Expected: todos os testes passando (nenhuma mudança de código nesta task).

Run: `grep -c "OpenRouter" README.md mapa.md ROADMAP.md`
Expected: contagem maior que zero nos três arquivos.

```bash
git add README.md mapa.md ROADMAP.md
git commit -m "docs: OpenRouter como provedor de notas (R-010)"
```

---

### Task 6 (opcional, verificação real): Gerar notas de verdade via OpenRouter

**Files:** nenhum (só execução). **Requer autorização explícita do usuário** — consome créditos do OpenRouter.

**Interfaces:**
- Consumes: tudo acima.
- Produces: confirmação de que a chamada real ao OpenRouter funciona ponta a ponta.

- [ ] **Step 1: Escolher um evento já transcrito**

Run: `ls -1 "99_material" | tail -5`
Expected: lista de eventos existentes, para reaproveitar uma transcrição já pronta (sem reprocessar áudio).

- [ ] **Step 2: Trocar para o OpenRouter no `config.yaml`**

Alterar `notas.provider` para `openrouter` (a alteração persiste, conforme a regra aprovada).

- [ ] **Step 3: Gerar as notas**

Run: `.venv/bin/python scripts/04_notas.py <nome_base>`
Expected: `Notas → 99_material/<nome_base>/notas/<nome_base>.md` e o arquivo com resumo, tópicos, decisões e plano de ação.

- [ ] **Step 4: Conferir e registrar**

Abrir o `.md` gerado, conferir a estrutura e registrar o resultado na entrada R-010 do `ROADMAP.md`.

---

## Notas de execução

- **Ordem:** a Task 2 acrescenta o despacho sem remover nada (suíte verde); a Task 3 remove `chamar_ollama` e religa o pipeline.
- **Sem rede nos testes:** os testes de HTTP substituem `notas.requests.post`; nenhuma chave real é necessária.
- **`.env`:** nunca lido nem editado. Se o nome da variável do usuário não for `OPENROUTER_API_KEY`, ajusta-se apenas `openrouter.api_key_env` no `config.yaml`.

## Self-Review

**1. Cobertura do spec:** configuração → Task 1; despacho por provedor → Task 2; seams testáveis → Tasks 2 e 3; erros claros → Task 3; skill persiste → Task 4; README/mapa/ROADMAP → Task 5; verificação real → Task 6. Sem lacunas.

**2. Placeholders:** o único `<N>` está no texto do R-010 e é explicitamente substituído no Step 5 da Task 5 pelo número real de testes. Nenhum passo de código tem "implementar depois".

**3. Consistência de tipos:** `montar_requisicao(cfg, prompt) -> (url, payload, headers, formato)` é definida na Task 2 e consumida exatamente assim por `chamar_modelo` na Task 3; `extrair_texto(formato, dados)` é definida e usada com os mesmos nomes na Task 3; os testes importam esses nomes exatos.

# Perfil llama.cpp para notas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usar o endpoint llama.cpp compatível com OpenAI como provedor padrão de notas, com o Gemma selecionado inicialmente e suporte a troca sob demanda para os dois Qwen informados.

**Architecture:** Reutilizar o ramo `type: openai` de `scripts/notas.py`; declarar o perfil `llama-cpp` e seu modelo inicial no `config.yaml`; documentar os três IDs para troca solicitada pelo usuário. Não alterar prompts, map-reduce, checkpoints nem o protocolo HTTP.

**Tech Stack:** Python 3.11+, PyYAML, requests, pytest, configuração YAML e documentação Markdown.

## Global Constraints

- Endpoint base: `http://100.87.71.48:18080/v1`; a chamada existente acrescenta `/chat/completions`.
- Modelo padrão: `gemma-4-26b-a4b-it-q4_k_m`.
- Modelos alternativos: `qwen3.5-35b-a3b-q4_k_m` e `qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-compact`.
- Usar `type: openai` e não adicionar autenticação sem evidência de necessidade.
- Preservar prompts, map-reduce, checkpoints e demais provedores; sem fallback silencioso ou descoberta automática de modelos.
- Não sobrescrever mudanças preexistentes no workspace: `config.yaml`, `README.md`, `mapa.md`, `scripts/notas.py` e `scripts/test_notas.py` já aparecem modificados no estado inicial. Antes de editar qualquer um, revisar seu diff e integrar apenas as mudanças necessárias, sem descartar trabalho existente.
- Não tocar em `.env` nem em `99_material/`.

---

## File Map

- `scripts/test_notas.py` — teste de contrato do perfil com URL completa e payload encaminhado ao endpoint OpenAI-compatível; resposta HTTP sempre simulada.
- `config.yaml` — perfil `llama-cpp` e seleção ativa padrão.
- `README.md` — seleção do perfil padrão, endpoint/modelo e instrução de troca sob demanda.
- `mapa.md` — lista de perfis disponíveis e comportamento do perfil de notas.
- `scripts/notas.py` — manter inalterado, a menos que a inspeção revele que a troca sob demanda não consegue selecionar `model` por execução; só nesse caso, propor alteração mínima e adicionar teste específico antes de implementação.

### Task 1: Cobrir a chamada OpenAI-compatível do perfil llama.cpp

**Files:**
- Modify: `scripts/test_notas.py`
- Test: `scripts/test_notas.py`

**Interfaces:**
- Consome `chamar_ollama(cfg, prompt)` existente.
- Produz uma asserção de contrato verificando URL, `model`, mensagens e ausência de autorização quando o perfil não define `api_key_env`.

- [ ] **Step 1: Inspecionar o diff preexistente e os testes de provider**

Run: `git diff -- scripts/test_notas.py scripts/notas.py`
Expected: identificar e preservar mudanças locais existentes; localizar o padrão de `monkeypatch` para `requests.post`.

- [ ] **Step 2: Adicionar teste de regressão com configuração llama.cpp e resposta simulada**

Adicionar em `scripts/test_notas.py`, adaptando o estilo já existente:

```python
def test_llama_cpp_usa_endpoint_openai_compativel(monkeypatch):
    chamadas = []

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "notas llama.cpp"}}]}

    def fake_post(url, json, headers, timeout):
        chamadas.append((url, json, headers, timeout))
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    cfg = {
        "llm": {
            "active": "llama-cpp",
            "providers": {
                "llama-cpp": {
                    "type": "openai",
                    "base_url": "http://100.87.71.48:18080/v1",
                    "model": "gemma-4-26b-a4b-it-q4_k_m",
                }
            },
        }
    }

    assert chamar_ollama(cfg, "resuma isto") == "notas llama.cpp"
    assert len(chamadas) == 1
    url, payload, headers, timeout = chamadas[0]
    assert url == "http://100.87.71.48:18080/v1/chat/completions"
    assert payload["model"] == "gemma-4-26b-a4b-it-q4_k_m"
    assert payload["messages"] == [{"role": "user", "content": "resuma isto"}]
    assert headers == {}
    assert timeout == 600
```

- [ ] **Step 3: Executar o teste e confirmar o comportamento esperado**

Run: `.venv/bin/python -m pytest scripts/test_notas.py::test_llama_cpp_usa_endpoint_openai_compativel -q`
Expected: PASS, pois o perfil usa o caminho existente `type: openai`.

### Task 2: Ativar e documentar o perfil llama.cpp

**Files:**
- Modify: `config.yaml`
- Modify: `README.md`
- Modify: `mapa.md`

**Interfaces:**
- Config fornece `llm.active: llama-cpp` e perfil com `type`, `base_url`, `model`.
- Documentação explica que a seleção de outro modelo ocorre quando o usuário pede a troca, usando o ID exato.

- [ ] **Step 1: Revisar diffs locais antes de editar os arquivos de configuração e documentação**

Run: `git diff -- config.yaml README.md mapa.md`
Expected: mudanças preexistentes identificadas e preservadas durante a edição.

- [ ] **Step 2: Configurar o perfil ativo e manter os perfis atuais**

Em `config.yaml`, ajustar o comentário de perfis disponíveis e ativar `llama-cpp`. Acrescentar o perfil sem apagar os perfis existentes:

```yaml
llm:
  active: "llama-cpp"

  providers:
    llama-cpp:
      # llama.cpp server expõe uma API compatível com OpenAI em /v1.
      type: "openai"
      base_url: "http://100.87.71.48:18080/v1"
      model: "gemma-4-26b-a4b-it-q4_k_m"
```

Expected: YAML permanece válido; nenhum provider anterior é removido ou alterado.

- [ ] **Step 3: Atualizar instruções de modelos no README**

Atualizar a lista de perfis e instruções de uso em `README.md`, informando:
- o perfil padrão `llama-cpp`, URL base e Gemma ativo;
- os dois IDs Qwen alternativos, escritos exatamente como fornecidos;
- que o usuário pode pedir a troca do modelo na solicitação de processamento;
- que a URL base usa o endpoint OpenAI-compatível existente.

Expected: instruções antigas que dizem que `llm-studio` é o padrão são corrigidas, sem alterar trechos não relacionados.

- [ ] **Step 4: Atualizar o mapa de perfis e do script de notas**

Em `mapa.md`, atualizar a descrição de `processar-gravacao` e `04_notas.py` para incluir `llama-cpp` como padrão, os modelos alternativos e a troca sob demanda.

Expected: o mapa não lista os perfis antigos como lista completa sem `llama-cpp`.

- [ ] **Step 5: Verificar sintaxe YAML e conteúdo de configuração**

Run:

```bash
.venv/bin/python -c 'import yaml; c=yaml.safe_load(open("config.yaml", encoding="utf-8")); assert c["llm"]["active"] == "llama-cpp"; p=c["llm"]["providers"]["llama-cpp"]; assert p == {"type": "openai", "base_url": "http://100.87.71.48:18080/v1", "model": "gemma-4-26b-a4b-it-q4_k_m"}'
```

Expected: exit code 0.

### Task 3: Verificar troca de modelo e suíte Python

**Files:**
- Modify: `scripts/test_notas.py` only if inspection in Task 1 found no test for per-call model override.
- Test: `scripts/test_notas.py`, depois diretórios de testes documentados.

**Interfaces:**
- A troca sob demanda precisa encaminhar exatamente o `model` escolhido naquela execução.
- Não alterar configuração persistente nem a lógica de produção sem necessidade demonstrada por teste.

- [ ] **Step 1: Verificar se o fluxo existente aceita override de modelo por execução**

Inspecionar `scripts/04_notas.py`, `scripts/notas.py` e os comandos descritos em `.opencode/skills/processar-gravacao/SKILL.md`; não executar a skill nem o pipeline de gravação durante esta implementação.

Expected: localizar o caminho real usado pelo agente para passar uma troca de modelo. Se a seleção hoje for feita alterando `config.yaml` antes de uma execução, registrar isso na documentação e manter comportamento; não inventar API de override.

- [ ] **Step 2: Se necessário, adicionar teste para encaminhar o ID solicitado**

Adicionar um teste que configure o perfil `llama-cpp` com `model` igual a cada nome alternativo, chame `chamar_ollama` e verifique que o payload encaminha exatamente o ID configurado. A chamada HTTP deve ser simulada como na Task 1.

Expected: os dois IDs alternativos chegam sem normalização, sufixos ou alteração de caixa.

- [ ] **Step 3: Executar testes de notas**

Run: `.venv/bin/python -m pytest scripts/test_notas.py -v`
Expected: todos os testes de notas passam.

- [ ] **Step 4: Executar a suíte Python documentada**

Run: `.venv/bin/python -m pytest scripts/ server/ native_host/ -v`
Expected: suíte passa; se falhar por ambiente ou dependência preexistente, reportar a saída real e não declarar validação completa.

- [ ] **Step 5: Revisar o diff final do escopo**

Run: `git diff -- config.yaml README.md mapa.md scripts/notas.py scripts/test_notas.py`
Expected: alterações limitadas ao perfil, documentação e cobertura de teste; alterações locais preexistentes preservadas. Não incluir `99_material/`, `.env` ou arquivos fora do escopo.

## Self-review

- Configuração, seleção padrão, endpoint e modelo Gemma cobertos na Task 2.
- IDs alternativos e encaminhamento exato cobertos na Task 3 sem assumir descoberta automática.
- Endpoint e payload OpenAI-compatíveis cobertos por teste simulado na Task 1.
- Documentação do README e mapa coberta na Task 2.
- Preservação de providers, prompts, map-reduce, checkpoints e alterações locais explicitada nas restrições e passos.
- Nenhuma chamada real ao host llama.cpp necessária para validação automatizada.

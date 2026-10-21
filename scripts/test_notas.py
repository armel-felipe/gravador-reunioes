import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from notas import (
    _write_notes_atomic,
    chamar_ollama,
    dividir_em_blocos,
    gerar_notas_map_reduce,
    main,
    montar_prompt,
    montar_prompt_map,
    montar_prompt_reduce,
)


def test_montar_prompt_inclui_transcricao():
    prompt = montar_prompt("transcrição de teste")
    assert "transcrição de teste" in prompt
    assert "resumo executivo" in prompt.lower()
    assert "plano de ação" in prompt.lower()


def test_montar_prompt_map_inclui_trecho_e_indices():
    prompt = montar_prompt_map("trecho de teste", 2, 5)
    assert "trecho de teste" in prompt
    assert "parte 2 de 5" in prompt


def test_montar_prompt_reduce_inclui_resumos():
    prompt = montar_prompt_reduce("resumo 1\n\nresumo 2")
    assert "resumo 1" in prompt
    assert "resumo 2" in prompt
    assert "consolida" in prompt.lower()


def test_prompts_preservam_fatos_e_evitem_invencoes():
    prompts = [
        montar_prompt("transcrição"),
        montar_prompt_map("trecho", 1, 2),
        montar_prompt_reduce("resumo"),
    ]
    for prompt in prompts:
        assert "Preserve nomes, empresas, números, datas e decisões" in prompt
        assert "Não invente informações" in prompt


def test_prompts_exigem_contexto_e_rastreabilidade():
    prompts = [
        montar_prompt("transcrição"),
        montar_prompt_map("trecho", 1, 2),
        montar_prompt_reduce("resumo"),
    ]
    for prompt in prompts:
        assert "contexto suficiente" in prompt.lower()
        assert "somente quando estiverem explicitamente" in prompt.lower()
        assert "não corrija" in prompt.lower()


def test_dividir_em_blocos_curto_retorna_um_bloco():
    transcricao = "**[00:00:00] SPEAKER_00:** fala curta"
    blocos = dividir_em_blocos(transcricao, bloco_min=10, overlap_min=2)
    assert len(blocos) == 1
    assert "fala curta" in blocos[0]


def test_dividir_em_blocos_longo_cria_varios_com_overlap():
    # 25 min de falas (1 fala por minuto)
    linhas = []
    for minuto in range(25):
        linhas.append(f"**[00:{minuto:02d}:00] SPEAKER_00:** fala do minuto {minuto}")
    transcricao = "\n".join(linhas)
    blocos = dividir_em_blocos(transcricao, bloco_min=10, overlap_min=2)
    # 25 min com blocos de 10 e overlap de 2: blocos [0-10], [8-18], [16-26] → 3 blocos
    assert len(blocos) == 3
    # Overlap: a fala do minuto 8 aparece no bloco 1 e no bloco 2
    assert "fala do minuto 8" in blocos[0]
    assert "fala do minuto 8" in blocos[1]
    # Última fala no último bloco
    assert "fala do minuto 24" in blocos[-1]


def test_dividir_em_blocos_vazio():
    assert dividir_em_blocos("") == []


def test_chamar_lmstudio_usa_api_openai_compatível(monkeypatch):
    chamadas = {}

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "notas geradas"}}]}

    def fake_post(url, json, headers, timeout):
        chamadas.update(url=url, json=json, headers=headers, timeout=timeout)
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    cfg = {"llm": {"active": "llm-studio", "providers": {"llm-studio": {
        "type": "openai", "base_url": "http://localhost:1234/v1", "model": "qwen3.5-35b-a3b"
    }}}}

    assert chamar_ollama(cfg, "resuma isto") == "notas geradas"
    assert chamadas["url"] == "http://localhost:1234/v1/chat/completions"
    assert chamadas["json"] == {
        "model": "qwen3.5-35b-a3b",
        "messages": [{"role": "user", "content": "resuma isto"}],
        "stream": False,
    }
    assert chamadas["headers"] == {}


def test_llama_cpp_usa_endpoint_openai_compatível(monkeypatch):
    chamadas = {}

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "notas llama.cpp"}}]}

    def fake_post(url, json, headers, timeout):
        chamadas.update(url=url, json=json, headers=headers, timeout=timeout)
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    cfg = {"llm": {"active": "llama-cpp", "providers": {"llama-cpp": {
        "type": "openai",
        "base_url": "http://100.87.71.48:18080/v1",
        "model": "gemma-4-26b-a4b-it-q4_k_m",
    }}}}

    assert chamar_ollama(cfg, "resuma isto") == "notas llama.cpp"
    assert chamadas["url"] == "http://100.87.71.48:18080/v1/chat/completions"
    assert chamadas["json"]["model"] == "gemma-4-26b-a4b-it-q4_k_m"
    assert chamadas["json"]["messages"] == [
        {"role": "user", "content": "resuma isto"}
    ]
    assert chamadas["headers"] == {}
    assert chamadas["timeout"] == 600


def test_config_define_llama_cpp_com_qwen36_como_padrao():
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    with config_path.open(encoding="utf-8") as arquivo:
        cfg = yaml.safe_load(arquivo)

    assert cfg["llm"]["active"] == "llama-cpp"
    assert cfg["llm"]["providers"]["llama-cpp"] == {
        "type": "openai",
        "base_url": "http://100.87.71.48:18080/v1",
        "model": "qwen3.6-35b-a3b-uncensored-heretic-native-mtp-preserved-apex-i-compact",
    }


def test_llama_cpp_encaminha_ids_alternativos_sem_alterar(monkeypatch):
    modelos_enviados = []

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "notas"}}]}

    def fake_post(url, json, headers, timeout):
        modelos_enviados.append(json["model"])
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    alternativos = [
        "gemma-4-26b-a4b-it-q4_k_m",
        "qwen3.5-35b-a3b-q4_k_m",
    ]
    cfg = {"llm": {"active": "llama-cpp", "providers": {"llama-cpp": {
        "type": "openai",
        "base_url": "http://100.87.71.48:18080/v1",
        "model": "",
    }}}}

    for model in alternativos:
        cfg["llm"]["providers"]["llama-cpp"]["model"] = model
        assert chamar_ollama(cfg, "resuma isto") == "notas"

    assert modelos_enviados == alternativos


def test_chamar_cloud_limita_tokens_da_resposta(monkeypatch):
    chamadas = {}

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "notas geradas"}}]}

    def fake_post(url, json, headers, timeout):
        chamadas.update(url=url, json=json, headers=headers, timeout=timeout)
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    monkeypatch.setenv("TEST_OLLAMA_KEY", "chave-de-teste")
    cfg = {
        "llm": {"active": "ollama-cloud", "providers": {"ollama-cloud": {
            "type": "openai", "base_url": "https://ollama.com/v1",
            "model": "glm-5.3-flash:cloud", "api_key_env": "TEST_OLLAMA_KEY",
            "max_tokens": 4096, "reasoning_effort": "low"
        }}}
    }

    assert chamar_ollama(cfg, "resuma isto") == "notas geradas"
    assert chamadas["json"]["max_tokens"] == 4096
    assert chamadas["json"]["reasoning_effort"] == "low"


def test_chamar_cloud_repete_quando_resposta_vazia(monkeypatch):
    respostas = iter([
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": "notas após retry"}}]},
    ])
    chamadas = {"total": 0}

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return next(respostas)

    def fake_post(url, json, headers, timeout):
        chamadas["total"] += 1
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    monkeypatch.setenv("TEST_OLLAMA_KEY", "chave-de-teste")
    cfg = {
        "llm": {"active": "ollama-cloud", "providers": {"ollama-cloud": {
            "type": "openai", "base_url": "https://ollama.com/v1",
            "model": "glm-5.3-flash:cloud", "api_key_env": "TEST_OLLAMA_KEY", "retries": 3
        }}}
    }

    assert chamar_ollama(cfg, "resuma isto") == "notas após retry"
    assert chamadas["total"] == 2


def test_chamar_openrouter_usa_api_openai_compatível(monkeypatch):
    chamadas = {}

    class Resposta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "notas do openrouter"}}]}

    def fake_post(url, json, headers, timeout):
        chamadas.update(url=url, json=json, headers=headers, timeout=timeout)
        return Resposta()

    monkeypatch.setattr("notas.requests.post", fake_post)
    monkeypatch.setenv("TEST_OPENROUTER_KEY", "chave-de-teste")
    cfg = {
        "llm": {"active": "openrouter", "providers": {"openrouter": {
            "type": "openai", "base_url": "https://openrouter.ai/api/v1",
            "model": "openai/gpt-4o-mini", "api_key_env": "TEST_OPENROUTER_KEY",
            "max_tokens": 2048
        }}}
    }

    assert chamar_ollama(cfg, "resuma isto") == "notas do openrouter"
    assert chamadas["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert chamadas["json"]["model"] == "openai/gpt-4o-mini"
    assert chamadas["json"]["max_tokens"] == 2048
    assert chamadas["headers"] == {"Authorization": "Bearer chave-de-teste"}


def test_map_reduce_reaproveita_checkpoints_e_processa_so_faltantes(tmp_path, monkeypatch):
    linhas = [
        f"**[00:{minuto:02d}:00] SPEAKER_00:** fala do minuto {minuto}"
        for minuto in range(25)
    ]
    transcricao = "\n".join(linhas)
    checkpoint_dir = tmp_path / "_tmp"
    checkpoint_dir.mkdir()

    cfg = {"llm": {"active": "ollama-cloud", "providers": {"ollama-cloud": {
        "type": "openai", "model": "glm-5.3-flash:cloud"
    }}}}
    blocos = dividir_em_blocos(transcricao, bloco_min=10, overlap_min=2)
    # O primeiro mapa já foi concluído em uma execução anterior.
    chamadas = []
    monkeypatch.setattr(
        "notas.chamar_ollama",
        lambda cfg, prompt: chamadas.append(prompt) or "resumo novo",
    )
    # O nome do checkpoint é descoberto pela primeira execução; aqui simulamos
    # um checkpoint por meio do diretório padrão após a chamada de preparação.
    gerar_notas_map_reduce(cfg, transcricao, checkpoint_dir=checkpoint_dir)
    assert len(chamadas) == len(blocos) + 3

    chamadas.clear()
    checkpoints = sorted(checkpoint_dir.glob("*/map_01.md"))
    assert len(checkpoints) == 1
    checkpoints[0].write_text("resumo já salvo", encoding="utf-8")
    checkpoint_map_02 = checkpoints[0].with_name("map_02.md")
    checkpoint_map_02.write_text("", encoding="utf-8")
    for checkpoint_reduce in checkpoints[0].parent.glob("reduce_*.md"):
        checkpoint_reduce.unlink()
    gerar_notas_map_reduce(cfg, transcricao, checkpoint_dir=checkpoint_dir)
    assert len(chamadas) == 4  # mapa 2 ausente + 3 reduções


def test_map_reduce_divide_reduce_grande_em_grupos(monkeypatch):
    linhas = [
        f"**[00:{minuto:02d}:00] SPEAKER_00:** fala do minuto {minuto}"
        for minuto in range(40)
    ]
    transcricao = "\n".join(linhas)
    cfg = {"llm": {"active": "llm-studio", "providers": {"llm-studio": {
        "type": "openai", "model": "qwen3.5-35b-a3b"
    }}}}
    chamadas = []
    monkeypatch.setattr(
        "notas.chamar_ollama",
        lambda cfg, prompt: chamadas.append(prompt) or "resumo",
    )

    gerar_notas_map_reduce(cfg, transcricao)

    # 5 mapas + 3 reduções do primeiro nível + 2 do segundo + 1 final.
    assert len(chamadas) == 11


def test_write_notes_atomic_rejects_empty_text_and_preserves_existing_file(tmp_path):
    destination = tmp_path / "notas.md"
    destination.write_text("versão anterior", encoding="utf-8")

    import pytest

    with pytest.raises(ValueError, match="notas vazias"):
        _write_notes_atomic(destination, "  \n")
    assert destination.read_text(encoding="utf-8") == "versão anterior"


def test_write_notes_atomic_replaces_complete_text(tmp_path):
    destination = tmp_path / "notas.md"

    _write_notes_atomic(destination, "# notas\nconteúdo\n")

    assert destination.read_text(encoding="utf-8") == "# notas\nconteúdo\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_main_model_override_only_changes_in_memory_config(tmp_path, monkeypatch):
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    original_config = config_path.read_bytes()
    transcricao_path = tmp_path / "transcricao.md"
    notas_path = tmp_path / "notas.md"
    transcricao_path.write_text("transcrição de teste", encoding="utf-8")
    cfg = {
        "llm": {
            "active": "llama-cpp",
            "providers": {"llama-cpp": {"model": "modelo-padrao"}},
        }
    }
    monkeypatch.setattr("notas.load_config", lambda: cfg)
    monkeypatch.setattr(
        "notas.audio_paths",
        lambda _: {"transcricao_md": transcricao_path, "notas_md": notas_path},
    )
    modelos_usados = []
    monkeypatch.setattr(
        "notas.gerar_notas_map_reduce",
        lambda cfg, transcricao, checkpoint_dir: modelos_usados.append(cfg["llm"]["providers"]["llama-cpp"]["model"]) or "# Notas",
    )

    main("evento", model_override="gemma-4-26b-a4b-it-q4_k_m")

    assert modelos_usados == ["gemma-4-26b-a4b-it-q4_k_m"]
    assert config_path.read_bytes() == original_config
    assert notas_path.read_text(encoding="utf-8") == "# Notas — evento\n\n# Notas\n"


def test_main_rejects_control_characters_in_model_override(monkeypatch):
    monkeypatch.setattr(
        "notas.load_config",
        lambda: {"llm": {"active": "llama-cpp", "providers": {"llama-cpp": {"model": "padrao"}}}},
    )

    import pytest

    with pytest.raises(ValueError, match="identificador de modelo inválido"):
        main("evento", model_override="modelo\ninjetado")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notas import dividir_em_blocos, montar_prompt, montar_prompt_map, montar_prompt_reduce


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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notas import montar_prompt


def test_montar_prompt_inclui_transcricao():
    prompt = montar_prompt("transcrição de teste")
    assert "transcrição de teste" in prompt
    assert "resumo executivo" in prompt.lower()
    assert "plano de ação" in prompt.lower()

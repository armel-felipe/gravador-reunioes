"""Gera notas (resumo + plano de ação) via Ollama. Uso: python 04_notas.py <nome_base>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notas import main


if __name__ == "__main__":
    main(sys.argv[1])

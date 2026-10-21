"""Gera notas via LLM configurado. Uso: python 04_notas.py <nome_base>"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notas import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera notas para uma gravação.")
    parser.add_argument("nome_base")
    parser.add_argument("--modelo")
    args = parser.parse_args()
    main(args.nome_base, model_override=args.modelo)

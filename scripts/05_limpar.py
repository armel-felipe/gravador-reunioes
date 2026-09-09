"""Apaga áudios com mais de N dias. Uso: python 05_limpar.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from limpar import main


if __name__ == "__main__":
    main()

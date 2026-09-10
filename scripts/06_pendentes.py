"""Lista eventos com áudio mas sem notas (pendentes de processamento). Uso: python 06_pendentes.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pendentes import main

if __name__ == "__main__":
    main()

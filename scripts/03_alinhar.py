"""Cruza transcrição com diarização. Uso: python 03_alinhar.py <nome_base>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alinhar import alinhar_falas
from common import audio_paths


def main(nome_base: str):
    paths = audio_paths(nome_base)
    with open(paths["transcricao_json"], encoding="utf-8") as f:
        transcricao = json.load(f)
    with open(paths["diarizacao_json"], encoding="utf-8") as f:
        diarizacao = json.load(f)
    falas = alinhar_falas(transcricao, diarizacao)
    linhas = []
    for f in falas:
        t = f"{int(f['start']//60):02d}:{int(f['start']%60):02d}"
        linhas.append(f"**[{t}] {f['speaker']}:** {f['text']}")
    paths["transcricao_md"].parent.mkdir(parents=True, exist_ok=True)
    with open(paths["transcricao_md"], "w", encoding="utf-8") as f:
        f.write(f"# Transcrição — {nome_base}\n\n" + "\n\n".join(linhas) + "\n")
    print(f"Transcrição diarizada → {paths['transcricao_md']}")


if __name__ == "__main__":
    main(sys.argv[1])

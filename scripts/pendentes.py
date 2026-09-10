"""Lista eventos com áudio mas sem notas (pendentes de processamento). Uso: python 06_pendentes.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config


def eventos_pendentes(material_dir: str) -> list:
    """Eventos com áudio mixado (.wav) mas sem notas geradas (.md em notas/).

    Um evento é considerado PROCESSADO quando tem notas/<evento>.md
    (última etapa do pipeline). Sem o arquivo de notas, fica pendente —
    inclusive se o processamento falhou no meio (será retentado).
    """
    pendentes = []
    raiz = Path(material_dir)
    for evento in raiz.iterdir():
        if not evento.is_dir():
            continue
        audio_dir = evento / "audio"
        wavs = list(audio_dir.glob("*.wav")) if audio_dir.exists() else []
        if not wavs:
            continue
        notas_dir = evento / "notas"
        notas = list(notas_dir.glob("*.md")) if notas_dir.exists() else []
        if not notas:
            pendentes.append(evento.name)
    return sorted(pendentes)


def main():
    cfg = load_config()
    pendentes = eventos_pendentes(cfg["caminhos"]["material_dir"])
    for p in pendentes:
        print(p)
    print(f"Total: {len(pendentes)}")


if __name__ == "__main__":
    main()

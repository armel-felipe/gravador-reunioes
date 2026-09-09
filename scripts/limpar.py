"""Apaga áudios com mais de N dias. Uso: python 05_limpar.py"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config


def limpar_audios_antigos(audio_dir: str, dias: int) -> list:
    """Apaga .wav e .webm (incluindo bruto/) com data de modificação > dias. Retorna os apagados."""
    limite = datetime.now() - timedelta(days=dias)
    apagados = []
    alvos = list(Path(audio_dir).glob("*.wav")) + list(Path(audio_dir).glob("*.webm"))
    bruto_dir = Path(audio_dir) / "bruto"
    if bruto_dir.exists():
        alvos += list(bruto_dir.glob("*.webm"))
    for p in alvos:
        if datetime.fromtimestamp(p.stat().st_mtime) < limite:
            p.unlink()
            apagados.append(str(p))
    return apagados


def main():
    cfg = load_config()
    apagados = limpar_audios_antigos(cfg["caminhos"]["audio_dir"], cfg["limpeza"]["dias_retencao_audio"])
    for a in apagados:
        print(f"Apagado: {a}")
    print(f"Total: {len(apagados)}")


if __name__ == "__main__":
    main()

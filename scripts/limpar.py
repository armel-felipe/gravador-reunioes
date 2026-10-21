"""Apaga áudios com mais de N dias, mantendo transcrições e notas. Uso: python 05_limpar.py"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config


def limpar_audios_antigos(material_dir: str, dias: int) -> list:
    """Apaga a pasta audio/ de cada evento (99_material/<evento>/audio) cujo wav
    tenha data de modificação > dias. Mantém transcrições e notas do evento.
    Retorna os caminhos apagados."""
    limite = datetime.now() - timedelta(days=dias)
    apagados = []
    raiz = Path(material_dir)
    for evento in raiz.iterdir():
        if not evento.is_dir():
            continue
        audio_dir = evento / "audio"
        if not audio_dir.exists():
            continue
        if not (evento / "notas" / f"{evento.name}.md").exists():
            continue
        wavs = list(audio_dir.glob("*.wav"))
        if not wavs:
            continue
        # Usa o wav mais recente do evento como referência de idade
        mais_recente = max(wavs, key=lambda p: p.stat().st_mtime)
        if datetime.fromtimestamp(mais_recente.stat().st_mtime) < limite:
            for p in audio_dir.rglob("*"):
                if p.is_file():
                    p.unlink()
                    apagados.append(str(p))
            # remove diretórios vazios do áudio
            for d in sorted(audio_dir.rglob("*"), reverse=True):
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            if audio_dir.exists() and not any(audio_dir.iterdir()):
                audio_dir.rmdir()
    return apagados


def main():
    cfg = load_config()
    apagados = limpar_audios_antigos(cfg["caminhos"]["material_dir"], cfg["limpeza"]["dias_retencao_audio"])
    for a in apagados:
        print(f"Apagado: {a}")
    print(f"Total: {len(apagados)}")


if __name__ == "__main__":
    main()

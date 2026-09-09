"""Transcreve o WAV com faster-whisper. Uso: python 01_transcrever.py <nome_base>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths
from faster_whisper import WhisperModel


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    model = WhisperModel(
        cfg["whisper"]["model"],
        device=cfg["whisper"]["device"],
        compute_type=cfg["whisper"]["compute_type"],
    )
    segments, _ = model.transcribe(str(paths["wav"]), language="pt")
    resultado = [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segments
    ]
    paths["transcricao_json"].parent.mkdir(parents=True, exist_ok=True)
    with open(paths["transcricao_json"], "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Transcrição: {len(resultado)} falas → {paths['transcricao_json']}")


if __name__ == "__main__":
    main(sys.argv[1])

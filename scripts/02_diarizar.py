"""Diarização com pyannote. Uso: python 02_diarizar.py <nome_base>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths
from pyannote.audio import Pipeline


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    token_path = Path.home() / ".cache/huggingface/token"
    if not token_path.exists():
        print("ERRO: token do HuggingFace não encontrado em ~/.cache/huggingface/token")
        print("Crie uma conta em huggingface.co, aceite os termos de pyannote/speaker-diarization-3.1")
        print("e salve o token no arquivo ~/.cache/huggingface/token")
        sys.exit(1)
    token = token_path.read_text().strip()
    pipeline = Pipeline.from_pretrained(
        cfg["diarizacao"]["model"],
        use_auth_token=token,
    )
    kwargs = {}
    if cfg["diarizacao"]["min_speakers"]:
        kwargs["min_speakers"] = cfg["diarizacao"]["min_speakers"]
    if cfg["diarizacao"]["max_speakers"]:
        kwargs["max_speakers"] = cfg["diarizacao"]["max_speakers"]
    diarization = pipeline(str(paths["wav"]), **kwargs)
    resultado = [
        {"start": round(turn.start, 2), "end": round(turn.end, 2), "speaker": speaker}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    with open(paths["diarizacao_json"], "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"Diarização: {len(resultado)} segmentos → {paths['diarizacao_json']}")


if __name__ == "__main__":
    main(sys.argv[1])

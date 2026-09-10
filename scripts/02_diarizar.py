"""Diarização com pyannote. Uso: python 02_diarizar.py <nome_base>"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import load_config, audio_paths
from pyannote.audio import Pipeline

ROOT = Path(__file__).resolve().parent.parent


def carregar_token() -> str:
    """Lê o token do HuggingFace do .env do projeto (ou da env var)."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for linha in env_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha.startswith("HUGGINGFACE_TOKEN="):
                token = linha.split("=", 1)[1].strip().strip('"').strip("'")
                if token and token != "hf_cole_seu_token_aqui":
                    return token
    token = os.environ.get("HUGGINGFACE_TOKEN", "")
    if token:
        return token
    print("ERRO: token do HuggingFace não encontrado.")
    print("Crie o arquivo .env na raiz do projeto (copie de .env.example) e preencha HUGGINGFACE_TOKEN.")
    print("Token: https://huggingface.co/settings/tokens")
    sys.exit(1)


def main(nome_base: str):
    cfg = load_config()
    paths = audio_paths(nome_base)
    token = carregar_token()
    pipeline = Pipeline.from_pretrained(
        cfg["diarizacao"]["model"],
        token=token,
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

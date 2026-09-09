"""Funções compartilhadas: config e caminhos."""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def audio_paths(nome_base: str) -> dict:
    cfg = load_config()
    audio = Path(cfg["caminhos"]["audio_dir"])
    trans = Path(cfg["caminhos"]["transcricoes_dir"])
    tmp = Path(cfg["caminhos"]["tmp_dir"])
    return {
        "wav": audio / f"{nome_base}.wav",
        "transcricao_json": tmp / f"{nome_base}_transcricao.json",
        "diarizacao_json": tmp / f"{nome_base}_diarizacao.json",
        "transcricao_md": trans / f"{nome_base}.md",
    }

"""Funções compartilhadas: config e caminhos."""
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def evento_dir(nome_base: str) -> Path:
    """Diretório do evento: 99_material/<nome_base>/ (nome_base = YYYY_MM_DD_HH_MM_<nome>)."""
    cfg = load_config()
    return Path(cfg["caminhos"]["material_dir"]) / nome_base


def audio_paths(nome_base: str) -> dict:
    """Caminhos de um evento, agrupados por gravação:
    99_material/<nome_base>/{audio,transcricoes,notas}/
    """
    ev = evento_dir(nome_base)
    audio = ev / "audio"
    trans = ev / "transcricoes"
    tmp = trans / "_tmp"
    notas = ev / "notas"
    return {
        "evento": ev,
        "wav": audio / f"{nome_base}.wav",
        "transcricao_json": tmp / f"{nome_base}_transcricao.json",
        "diarizacao_json": tmp / f"{nome_base}_diarizacao.json",
        "transcricao_md": trans / f"{nome_base}.md",
        "notas_md": notas / f"{nome_base}.md",
    }

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

    Tolerante a renomeação da pasta do evento: se o .wav com o nome exato
    não existir, usa o primeiro *.wav encontrado em audio/ (o usuário pode
    renomear a pasta no Finder sem quebrar o processamento).
    """
    ev = evento_dir(nome_base)
    audio = ev / "audio"
    trans = ev / "transcricoes"
    tmp = trans / "_tmp"
    notas = ev / "notas"
    wav = audio / f"{nome_base}.wav"
    if not wav.exists() and audio.exists():
        candidatos = sorted(audio.glob("*.wav"))
        if candidatos:
            wav = candidatos[0]
    return {
        "evento": ev,
        "wav": wav,
        "transcricao_json": tmp / f"{nome_base}_transcricao.json",
        "diarizacao_json": tmp / f"{nome_base}_diarizacao.json",
        "diarizacao_fundida_json": tmp / f"{nome_base}_diarizacao_fundida.json",
        "transcricao_md": trans / f"{nome_base}.md",
        "notas_md": notas / f"{nome_base}.md",
    }

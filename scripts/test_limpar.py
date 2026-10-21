import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from limpar import limpar_audios_antigos


def _criar_evento(raiz: Path, nome: str, idade_dias: float) -> Path:
    """Cria 99_material/<nome>/audio/<nome>.wav com mtime de idade_dias atrás."""
    evento = raiz / nome
    audio = evento / "audio"
    audio.mkdir(parents=True)
    wav = audio / f"{nome}.wav"
    wav.write_bytes(b"x")
    t = time.time() - idade_dias * 86400
    os.utime(wav, (t, t))
    return evento


def test_limpar_apaga_so_antigos():
    with tempfile.TemporaryDirectory() as tmp:
        velho = _criar_evento(Path(tmp), "2020_01_01_10_00_velho", 40)
        notas = velho / "notas"
        notas.mkdir()
        (notas / "2020_01_01_10_00_velho.md").write_text("notas")
        _criar_evento(Path(tmp), "2026_09_09_10_00_novo", 1)
        apagados = limpar_audios_antigos(tmp, dias=30)
        assert not (Path(tmp) / "2020_01_01_10_00_velho" / "audio").exists()
        assert (Path(tmp) / "2026_09_09_10_00_novo" / "audio" / "2026_09_09_10_00_novo.wav").exists()
        assert len(apagados) == 1


def test_limpar_mantem_transcricoes_e_notas():
    with tempfile.TemporaryDirectory() as tmp:
        evento = _criar_evento(Path(tmp), "2020_01_01_10_00_velho", 40)
        trans = evento / "transcricoes"
        notas = evento / "notas"
        trans.mkdir()
        notas.mkdir()
        (trans / "2020_01_01_10_00_velho.md").write_text("transcrição")
        (notas / "2020_01_01_10_00_velho.md").write_text("notas")
        limpar_audios_antigos(tmp, dias=30)
        # áudio apagado, transcrições e notas mantidas
        assert not (evento / "audio").exists()
        assert (trans / "2020_01_01_10_00_velho.md").exists()
        assert (notas / "2020_01_01_10_00_velho.md").exists()


def test_limpar_preserva_audio_antigo_sem_nota():
    with tempfile.TemporaryDirectory() as tmp:
        evento = _criar_evento(Path(tmp), "2020_01_01_10_00_sem_nota", 40)
        audio = evento / "audio" / "2020_01_01_10_00_sem_nota.wav"

        apagados = limpar_audios_antigos(tmp, dias=30)

        assert audio.exists()
        assert apagados == []

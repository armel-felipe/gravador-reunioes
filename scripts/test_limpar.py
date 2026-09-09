import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from limpar import limpar_audios_antigos


def test_limpar_apaga_so_antigos():
    with tempfile.TemporaryDirectory() as tmp:
        antigo = Path(tmp) / "2020_01_01_10_00_velho.wav"
        novo = Path(tmp) / "2026_09_09_10_00_novo.wav"
        antigo.write_bytes(b"x")
        novo.write_bytes(b"x")
        t_antigo = time.time() - 40 * 86400
        os.utime(antigo, (t_antigo, t_antigo))
        limpar_audios_antigos(tmp, dias=30)
        assert not antigo.exists()
        assert novo.exists()


def test_limpar_apaga_webm_do_bruto():
    with tempfile.TemporaryDirectory() as tmp:
        bruto = Path(tmp) / "bruto"
        bruto.mkdir()
        antigo = bruto / "2020_01_01_10_00_velho.webm"
        novo = Path(tmp) / "2026_09_09_10_00_novo.webm"
        antigo.write_bytes(b"x")
        novo.write_bytes(b"x")
        t_antigo = time.time() - 40 * 86400
        os.utime(antigo, (t_antigo, t_antigo))
        apagados = limpar_audios_antigos(tmp, dias=30)
        assert not antigo.exists()
        assert novo.exists()
        assert len(apagados) == 1

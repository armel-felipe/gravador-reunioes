import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pendentes import eventos_pendentes


def _criar_evento(raiz: Path, nome: str, com_notas: bool = False) -> None:
    evento = raiz / nome
    audio = evento / "audio"
    audio.mkdir(parents=True)
    (audio / f"{nome}.wav").write_bytes(b"x")
    if com_notas:
        notas = evento / "notas"
        notas.mkdir()
        (notas / f"{nome}.md").write_text("notas")


def test_lista_so_pendentes():
    with tempfile.TemporaryDirectory() as tmp:
        _criar_evento(Path(tmp), "2026_09_09_10_00_processado", com_notas=True)
        _criar_evento(Path(tmp), "2026_09_09_11_00_pendente")
        _criar_evento(Path(tmp), "2026_09_09_12_00_falhou_no_meio")  # tem transcrição, sem notas
        (Path(tmp) / "2026_09_09_12_00_falhou_no_meio" / "transcricoes").mkdir()
        pendentes = eventos_pendentes(tmp)
        assert pendentes == ["2026_09_09_11_00_pendente", "2026_09_09_12_00_falhou_no_meio"]


def test_ignora_diretorios_sem_audio():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pasta_solta").mkdir()
        assert eventos_pendentes(tmp) == []

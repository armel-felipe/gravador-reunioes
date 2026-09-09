import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.audio_store import AudioStore


def _webm_silence(duration: float = 0.5) -> bytes:
    """Gera 0.5s de silêncio em WebM/Opus (mesmo codec da extensão)."""
    out = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
            "-t", str(duration), "-c:a", "libopus", "-f", "webm", "-",
        ],
        check=True, capture_output=True,
    )
    return out.stdout


def test_start_append_finish_creates_mixed_wav():
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioStore(base_dir=tmp)
        session_id = "2026_09_09_14_30_reuniao"
        store.start_session(session_id, "reuniao")
        # 0.5s de silêncio em cada canal (WebM/Opus)
        chunk = _webm_silence()
        store.append("tab", chunk)
        store.append("mic", chunk)
        wav_path = store.finish()
        assert wav_path.endswith(".wav")
        assert os.path.exists(wav_path)
        assert os.path.getsize(wav_path) > 100
        # brutos salvos
        assert os.path.exists(os.path.join(tmp, "bruto", f"{session_id}_tab.webm"))
        assert os.path.exists(os.path.join(tmp, "bruto", f"{session_id}_mic.webm"))

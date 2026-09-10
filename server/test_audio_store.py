import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.audio_store import AudioStore


def _pcm_silence(duration: float = 0.25, sample_rate: int = 16000) -> bytes:
    """Gera silêncio em PCM16 little-endian mono (mesmo formato da extensão)."""
    return b"\x00\x00" * int(duration * sample_rate)


def test_start_append_finish_creates_mixed_wav():
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioStore(base_dir=tmp)
        session_id = "2026_09_09_14_30_reuniao"
        store.start_session(session_id, "reuniao", sample_rate=16000)
        # 0.25s de silêncio em cada canal (PCM16 raw)
        chunk = _pcm_silence()
        store.append("tab", chunk)
        store.append("mic", chunk)
        wav_path = store.finish()
        assert wav_path.endswith(".wav")
        assert os.path.exists(wav_path)
        assert os.path.getsize(wav_path) > 100
        # Estrutura nova: tmp/<session_id>/audio/bruto/*.pcm e tmp/<session_id>/audio/<session_id>.wav
        assert os.path.exists(os.path.join(tmp, session_id, "audio", "bruto", f"{session_id}_tab.pcm"))
        assert os.path.exists(os.path.join(tmp, session_id, "audio", "bruto", f"{session_id}_mic.pcm"))
        # wav decodificável: pcm_s16le, 16000 Hz, mono
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels",
             "-of", "csv=p=0", wav_path],
            check=True, capture_output=True, text=True,
        )
        assert probe.stdout.strip() == "pcm_s16le,16000,1"


def test_append_canal_desconhecido_levanta_erro():
    with tempfile.TemporaryDirectory() as tmp:
        store = AudioStore(base_dir=tmp)
        store.start_session("2026_09_09_14_30_reuniao", "reuniao", sample_rate=16000)
        with pytest.raises(ValueError):
            store.append("outro", b"\x00\x00")

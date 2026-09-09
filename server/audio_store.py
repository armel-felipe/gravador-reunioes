"""Armazena chunks de áudio recebidos e gera o WAV mixado final."""
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


class AudioStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.bruto_dir = self.base_dir / "bruto"
        self.bruto_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = None
        self._tab_path = None
        self._mic_path = None
        self._tab_fh = None
        self._mic_fh = None

    def start_session(self, session_id: str, nome: str):
        self.session_id = session_id
        self._tab_path = self.bruto_dir / f"{session_id}_tab.webm"
        self._mic_path = self.bruto_dir / f"{session_id}_mic.webm"
        self._tab_fh = open(self._tab_path, "wb")
        self._mic_fh = open(self._mic_path, "wb")

    def append(self, channel: str, chunk: bytes):
        fh = self._tab_fh if channel == "tab" else self._mic_fh
        fh.write(chunk)

    def finish(self) -> str:
        self._tab_fh.close()
        self._mic_fh.close()
        wav_path = self.base_dir / f"{self.session_id}.wav"
        # Mixa os dois canais em um WAV 16kHz mono
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self._tab_path),
            "-i", str(self._mic_path),
            "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:normalize=0,aresample=16000,pan=mono|c0=0.5*c0+0.5*c1",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return str(wav_path)

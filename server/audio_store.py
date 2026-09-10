"""Armazena chunks de áudio recebidos e gera o WAV mixado final."""
import subprocess
from pathlib import Path


class AudioStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.bruto_dir = self.base_dir / "bruto"
        self.bruto_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = None
        self.sample_rate = 48000
        self._tab_path = None
        self._mic_path = None
        self._tab_fh = None
        self._mic_fh = None

    def start_session(self, session_id: str, nome: str, sample_rate: int = 48000):
        if self._tab_fh is not None:
            self._tab_fh.close()
        if self._mic_fh is not None:
            self._mic_fh.close()
        self.session_id = session_id
        self.sample_rate = int(sample_rate)
        self._tab_path = self.bruto_dir / f"{session_id}_tab.pcm"
        self._mic_path = self.bruto_dir / f"{session_id}_mic.pcm"
        self._tab_fh = open(self._tab_path, "wb")
        self._mic_fh = open(self._mic_path, "wb")

    def append(self, channel: str, chunk: bytes):
        if channel == "tab":
            fh = self._tab_fh
        elif channel == "mic":
            fh = self._mic_fh
        else:
            raise ValueError(f"canal desconhecido: {channel!r}")
        if fh is None:
            # Chunk chegou depois do end/finish (áudio ainda em voo) — ignora.
            return
        fh.write(chunk)

    def finish(self) -> str:
        if self.session_id is None:
            # finish() já foi chamado (ou nunca houve sessão) — nada a fazer
            return ""
        if self._tab_fh is not None:
            self._tab_fh.close()
        if self._mic_fh is not None:
            self._mic_fh.close()
        self._tab_fh = None
        self._mic_fh = None
        wav_path = self.base_dir / f"{self.session_id}.wav"
        # Se os brutos não existem (ex.: limpeza manual), não há o que mixar.
        if not self._tab_path.exists() and not self._mic_path.exists():
            self.session_id = None
            return str(wav_path)
        # Mixa os dois canais em um WAV mono no sample rate da sessão
        cmd = [
            "ffmpeg", "-y",
            "-f", "s16le", "-ar", str(self.sample_rate), "-ac", "1", "-i", str(self._tab_path),
            "-f", "s16le", "-ar", str(self.sample_rate), "-ac", "1", "-i", str(self._mic_path),
            "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:normalize=0,aresample=16000,pan=mono|c0=0.5*c0+0.5*c1",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_path),
        ]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"ffmpeg falhou ao mixar {self.session_id}: {r.stderr.decode(errors='replace')}"
            )
        self.session_id = None
        return str(wav_path)

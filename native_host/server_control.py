"""Native Messaging bridge for the local recording server."""

from __future__ import annotations

import json
import shlex
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import BinaryIO, Callable
from urllib.request import urlopen

JOB_LABEL = "com.armel.gravador-servidor"
HEALTH_URL = "http://127.0.0.1:8765/health"
LOG_PATH = "/tmp/gravador_server.log"
MAX_MESSAGE_BYTES = 1024 * 1024


def default_health_check(url: str = HEALTH_URL, timeout: float = 1.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


class ServerController:
    """Executes the three fixed server operations exposed to Chrome."""

    def __init__(
        self,
        project_root: Path,
        health_check: Callable[[], bool] | None = None,
        command_runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        start_attempts: int = 12,
        stop_attempts: int = 6,
    ) -> None:
        self.project_root = project_root.resolve()
        self.health_check = health_check or default_health_check
        self.command_runner = command_runner
        self.sleep = sleep
        self.start_attempts = start_attempts
        self.stop_attempts = stop_attempts

    def handle(self, action: str) -> dict:
        try:
            if action == "status":
                return {"ok": True, "action": "status", "online": self.health_check()}
            if action == "start":
                return self.start()
            if action == "stop":
                return self.stop()
            return {"ok": False, "error": f"ação não permitida: {action}"}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def start(self) -> dict:
        if self.health_check():
            return {"ok": True, "action": "start", "online": True, "already_online": True}

        command = [
            "/bin/launchctl",
            "submit",
            "-l",
            JOB_LABEL,
            "--",
            "/bin/bash",
            "-lc",
            f"cd {shlex.quote(str(self.project_root))} && exec ./start.sh >> {LOG_PATH} 2>&1",
        ]
        completed = self.command_runner(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "launchctl submit falhou").strip()
            raise RuntimeError(detail)

        if not self._wait_for(True, self.start_attempts):
            raise RuntimeError(f"servidor não respondeu em {HEALTH_URL}")
        return {"ok": True, "action": "start", "online": True}

    def stop(self) -> dict:
        if not self.health_check():
            return {"ok": True, "action": "stop", "online": False, "already_stopped": True}

        completed = self.command_runner(
            ["/bin/launchctl", "remove", JOB_LABEL],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 and "Could not find service" not in (completed.stderr or ""):
            detail = (completed.stderr or completed.stdout or "launchctl remove falhou").strip()
            raise RuntimeError(detail)

        if not self._wait_for(False, self.stop_attempts):
            raise RuntimeError(f"servidor ainda responde em {HEALTH_URL}")
        return {"ok": True, "action": "stop", "online": False}

    def _wait_for(self, expected: bool, attempts: int) -> bool:
        for attempt in range(attempts):
            if self.health_check() is expected:
                return True
            if attempt + 1 < attempts:
                self.sleep(0.5)
        return False


def _read_message(stream: BinaryIO) -> bytes | None:
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("cabeçalho Native Messaging incompleto")
    length = struct.unpack("<I", header)[0]
    if length > MAX_MESSAGE_BYTES:
        raise ValueError("mensagem Native Messaging muito grande")
    payload = stream.read(length)
    if len(payload) != length:
        raise ValueError("payload Native Messaging incompleto")
    return payload


def _write_message(stream: BinaryIO, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()


def run_native_message_loop(
    controller: ServerController,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
) -> None:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    while True:
        payload = _read_message(stdin)
        if payload is None:
            return
        try:
            request = json.loads(payload.decode("utf-8"))
            response = controller.handle(request.get("action"))
        except Exception as error:
            response = {"ok": False, "error": str(error)}
        _write_message(stdout, response)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    run_native_message_loop(ServerController(root))

"""Durable, on-demand orchestration for recording processing jobs."""

from __future__ import annotations

import fcntl
import json
import re
import shlex
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


STAGES = ("transcrever", "diarizar", "fundir", "alinhar", "notas")
_LOG_REDACTIONS = (
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\bhf_[A-Za-z0-9]{10,}\b"), "[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|token)\s*[:=]\s*)['\"]?[^\s,'\"]+"), r"\1[REDACTED]"),
)


class JobAlreadyRunning(RuntimeError):
    """Raised when an event is already locked by another worker."""


def validate_event_name(name: str) -> str:
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise ValueError("nome de evento inválido")
    if "/" in name or "\\" in name or Path(name).name != name:
        raise ValueError("nome de evento não pode conter caminho")
    return name


def validate_model_override(model: Optional[str]) -> Optional[str]:
    if model is None:
        return None
    if not isinstance(model, str) or not model.strip() or len(model) > 256:
        raise ValueError("identificador de modelo inválido")
    if any(ord(character) < 32 for character in model):
        raise ValueError("identificador de modelo contém caracteres de controle")
    return model


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _material_root(project_root: Path) -> Path:
    config_path = Path(project_root) / "config.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(f"config.yaml não encontrado em {project_root}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    configured = Path(config.get("caminhos", {}).get("material_dir", "99_material"))
    return configured if configured.is_absolute() else Path(project_root) / configured


def jobs_root(project_root: Path) -> Path:
    return _material_root(project_root) / ".processamento" / "jobs"


def event_state_path(project_root: Path, event: str) -> Path:
    return _material_root(project_root) / validate_event_name(event) / ".processamento" / "state.json"


def stage_output_path(project_root: Path, event: str, stage: str) -> Path:
    event_dir = _material_root(project_root) / validate_event_name(event)
    transcriptions = event_dir / "transcricoes"
    temporary = transcriptions / "_tmp"
    paths = {
        "transcrever": temporary / f"{event}_transcricao.json",
        "diarizar": temporary / f"{event}_diarizacao.json",
        "fundir": temporary / f"{event}_diarizacao_fundida.json",
        "alinhar": transcriptions / f"{event}.md",
        "notas": event_dir / "notas" / f"{event}.md",
    }
    try:
        return paths[stage]
    except KeyError as error:
        raise ValueError(f"etapa desconhecida: {stage}") from error


def _atomic_write_json(destination: Path, value: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def create_job(
    project_root: Path,
    events: list[str],
    model_override: Optional[str] = None,
) -> dict:
    model_override = validate_model_override(model_override)
    if not events:
        raise ValueError("nenhum evento para processar")
    names = [validate_event_name(event) for event in events]
    if len(set(names)) != len(names):
        raise ValueError("a lista de eventos contém duplicatas")
    material_root = _material_root(project_root)
    for event in names:
        event_dir = material_root / event
        audio_dir = event_dir / "audio"
        if not event_dir.is_dir() or not list(audio_dir.glob("*.wav")):
            raise ValueError(f"evento sem áudio WAV: {event}")

    now = _now()
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "events": names,
        "model_override": model_override,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "events_state": {
            event: {
                "status": "queued",
                "current_stage": None,
                "completed_stages": [],
                "started_at": None,
                "updated_at": now,
                "finished_at": None,
                "error": None,
            }
            for event in names
        },
    }
    _atomic_write_json(jobs_root(project_root) / f"{job_id}.json", job)
    return job


def load_job(project_root: Path, job_id: str) -> dict:
    if not job_id or any(char not in "0123456789abcdef" for char in job_id.lower()):
        raise ValueError("identificador de job inválido")
    path = jobs_root(project_root) / f"{job_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"job não encontrado: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_jobs(project_root: Path) -> list:
    root = jobs_root(project_root)
    if not root.exists():
        return []
    jobs = [json.loads(path.read_text(encoding="utf-8")) for path in root.glob("*.json")]
    return sorted(jobs, key=lambda job: job.get("created_at", ""), reverse=True)


def save_job(project_root: Path, job: dict) -> None:
    job["updated_at"] = _now()
    _atomic_write_json(jobs_root(project_root) / f"{job['job_id']}.json", job)


def get_job_status(project_root: Path, job_id: str) -> dict:
    return load_job(project_root, job_id)


def launch_job(project_root: Path, job_id: str, command_runner=subprocess.run) -> dict:
    project_root = Path(project_root).resolve()
    lock_path = _material_root(project_root) / ".processamento" / "submit.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            return _launch_job_locked(project_root, job_id, command_runner)
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def _launch_job_locked(project_root: Path, job_id: str, command_runner) -> dict:
    project_root = Path(project_root).resolve()
    job = load_job(project_root, job_id)
    for existing in list_jobs(project_root):
        if existing["job_id"] == job_id:
            continue
        if existing.get("status") not in {"queued", "running"}:
            continue
        overlapping = set(existing.get("events", [])) & set(job["events"])
        if not overlapping:
            continue
        label = existing.get("launch_label")
        active = False
        if label:
            check = command_runner(
                ["/bin/launchctl", "list", label],
                check=False,
                capture_output=True,
                text=True,
            )
            active = check.returncode == 0
        if active:
            job["status"] = "rejected"
            job["finished_at"] = _now()
            job["error"] = "evento já pertence a um job ativo"
            save_job(project_root, job)
            raise JobAlreadyRunning(f"já existe job ativo para: {', '.join(sorted(overlapping))}")
        existing["status"] = "interrupted"
        existing["finished_at"] = _now()
        existing["error"] = "job não está mais registrado no launchd; pode ser retomado"
        save_job(project_root, existing)

    label = f"com.armel.gravador-processamento.{job_id}"
    log_path = jobs_root(project_root) / f"{job_id}.log"
    worker = project_root / "scripts" / "07_processar.py"
    # Keep the venv's bin/python path; resolve() would follow its symlink out
    # of the virtual environment and could lose installed pipeline packages.
    python = Path(sys.executable).absolute()
    shell_command = (
        f"cd {shlex.quote(str(project_root))} && exec {shlex.quote(str(python))} "
        f"{shlex.quote(str(worker))} run --job-id {shlex.quote(job_id)} "
        f">> {shlex.quote(str(log_path))} 2>&1"
    )
    job["launch_label"] = label
    job["status"] = "queued"
    job["error"] = None
    save_job(project_root, job)
    completed = command_runner(
        ["/bin/launchctl", "submit", "-l", label, "--", "/bin/bash", "-lc", shell_command],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        job["status"] = "failed"
        job["finished_at"] = _now()
        job["error"] = "launchctl submit falhou"
        save_job(project_root, job)
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"launchctl submit falhou: {detail[:300]}")
    return job


def validate_stage_output(stage: str, output: Path) -> bool:
    if not output.is_file() or output.stat().st_size == 0:
        return False
    if stage in {"transcrever", "diarizar", "fundir"}:
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        return isinstance(data, list) and bool(data)
    if stage in {"alinhar", "notas"}:
        return bool(output.read_text(encoding="utf-8").strip())
    raise ValueError(f"etapa desconhecida: {stage}")


def _event_log_path(project_root: Path, event: str) -> Path:
    return event_state_path(project_root, event).with_name("processamento.log")


def _append_event_log(project_root: Path, event: str, stage: str, stdout: str, stderr: str) -> None:
    log_path = _event_log_path(project_root, event)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n[{_now()}] etapa={stage}\n")
        if stdout:
            safe_stdout = _sanitize_log_text(stdout)
            stream.write(safe_stdout)
            if not safe_stdout.endswith("\n"):
                stream.write("\n")
        if stderr:
            stream.write("[stderr]\n")
            safe_stderr = _sanitize_log_text(stderr)
            stream.write(safe_stderr)
            if not safe_stderr.endswith("\n"):
                stream.write("\n")


def _sanitize_log_text(text: str) -> str:
    for pattern, replacement in _LOG_REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _save_event_state(project_root: Path, job: dict, event: str, state: dict) -> None:
    state["updated_at"] = _now()
    job["events_state"][event] = state
    save_job(project_root, job)
    _atomic_write_json(event_state_path(project_root, event), state)


def _stage_scripts(project_root: Path) -> dict:
    scripts = Path(project_root) / "scripts"
    return {
        "transcrever": scripts / "01_transcrever.py",
        "diarizar": scripts / "02_diarizar.py",
        "fundir": scripts / "fundir.py",
        "alinhar": scripts / "03_alinhar.py",
        "notas": scripts / "04_notas.py",
    }


def run_job(project_root: Path, job_id: str, command_runner=subprocess.run) -> dict:
    project_root = Path(project_root).resolve()
    job = load_job(project_root, job_id)
    job["status"] = "running"
    save_job(project_root, job)
    stage_scripts = _stage_scripts(project_root)

    for event in job["events"]:
        state = job["events_state"][event]
        try:
            with event_lock(project_root, event):
                state["status"] = "running"
                state["started_at"] = state["started_at"] or _now()
                state["finished_at"] = None
                state["error"] = None
                _save_event_state(project_root, job, event, state)

                for stage in STAGES:
                    output = stage_output_path(project_root, event, stage)
                    if validate_stage_output(stage, output):
                        if stage not in state["completed_stages"]:
                            state["completed_stages"].append(stage)
                        state["current_stage"] = stage
                        _save_event_state(project_root, job, event, state)
                        continue

                    state["current_stage"] = stage
                    _save_event_state(project_root, job, event, state)
                    if output.exists():
                        output.unlink()
                    command = [sys.executable, str(stage_scripts[stage]), event]
                    if stage == "notas" and job.get("model_override"):
                        command.extend(["--modelo", job["model_override"]])
                    completed = command_runner(
                        command,
                        cwd=str(project_root),
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    stdout = completed.stdout or ""
                    stderr = completed.stderr or ""
                    _append_event_log(project_root, event, stage, stdout, stderr)
                    if completed.returncode != 0:
                        output.unlink(missing_ok=True)
                        raise RuntimeError(f"etapa {stage} terminou com código {completed.returncode}")
                    if not validate_stage_output(stage, output):
                        output.unlink(missing_ok=True)
                        raise RuntimeError(f"etapa {stage} terminou sem uma saída válida")
                    if stage not in state["completed_stages"]:
                        state["completed_stages"].append(stage)
                    _save_event_state(project_root, job, event, state)

                state["status"] = "completed"
                state["current_stage"] = None
                state["finished_at"] = _now()
                state["error"] = None
                _save_event_state(project_root, job, event, state)
        except Exception as error:
            state["status"] = "failed"
            state["finished_at"] = _now()
            state["error"] = str(error)[:500]
            _save_event_state(project_root, job, event, state)

    statuses = [state["status"] for state in job["events_state"].values()]
    job["status"] = "completed" if all(s == "completed" for s in statuses) else "completed_with_errors"
    job["finished_at"] = _now()
    save_job(project_root, job)
    return job


@contextmanager
def event_lock(project_root: Path, event: str):
    lock_path = event_state_path(project_root, event).with_name("worker.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise JobAlreadyRunning(f"evento já está sendo processado: {event}") from error
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

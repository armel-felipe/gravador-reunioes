import json
import os
import shlex
import sys
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from processamento import (
    JobAlreadyRunning,
    _append_event_log,
    create_job,
    event_lock,
    get_job_status,
    launch_job,
    run_job,
    stage_output_path,
    save_job,
    validate_event_name,
)
import importlib.util

CLI_SPEC = importlib.util.spec_from_file_location(
    "processar_cli", Path(__file__).with_name("07_processar.py")
)
processar_cli = importlib.util.module_from_spec(CLI_SPEC)
CLI_SPEC.loader.exec_module(processar_cli)


def project_with_event(tmp_path, name="2026_10_21_09_00_reuniao"):
    (tmp_path / "config.yaml").write_text(
        'caminhos:\n  material_dir: "99_material"\n',
        encoding="utf-8",
    )
    audio_dir = tmp_path / "99_material" / name / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / f"{name}.wav").write_bytes(b"fixture")
    return tmp_path


def test_create_job_persists_snapshot_and_model_override(tmp_path):
    project_with_event(tmp_path)
    job = create_job(
        tmp_path,
        ["2026_10_21_09_00_reuniao"],
        "gemma-4-26b-a4b-it-q4_k_m",
    )

    saved = json.loads(
        (tmp_path / "99_material/.processamento/jobs" / f"{job['job_id']}.json")
        .read_text(encoding="utf-8")
    )
    assert saved["events"] == ["2026_10_21_09_00_reuniao"]
    assert saved["model_override"] == "gemma-4-26b-a4b-it-q4_k_m"
    assert saved["status"] == "queued"
    assert saved["events_state"]["2026_10_21_09_00_reuniao"]["status"] == "queued"


@pytest.mark.parametrize("name", ["../outside", "nested/event", "", ".", ".."])
def test_event_names_cannot_escape_material_root(name):
    with pytest.raises(ValueError):
        validate_event_name(name)


def test_create_job_rejects_empty_event_list(tmp_path):
    project_with_event(tmp_path)
    with pytest.raises(ValueError):
        create_job(tmp_path, [])


def test_get_job_status_reads_manifest_without_side_effects(tmp_path):
    project_with_event(tmp_path)
    job = create_job(tmp_path, ["2026_10_21_09_00_reuniao"])
    manifest_path = tmp_path / "99_material/.processamento/jobs" / f"{job['job_id']}.json"
    before = manifest_path.read_bytes()

    result = get_job_status(tmp_path, job["job_id"])

    assert result["job_id"] == job["job_id"]
    assert manifest_path.read_bytes() == before


def test_event_lock_is_exclusive_and_released_after_exception(tmp_path):
    project_with_event(tmp_path)
    event = "2026_10_21_09_00_reuniao"

    with pytest.raises(RuntimeError, match="injected"):
        with event_lock(tmp_path, event):
            with pytest.raises(JobAlreadyRunning):
                with event_lock(tmp_path, event):
                    pass
            raise RuntimeError("injected")

    with event_lock(tmp_path, event):
        pass


def test_run_job_executes_pipeline_in_order_and_records_state(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    job = create_job(tmp_path, [event])
    calls = []
    script_stage = {
        "01_transcrever.py": "transcrever",
        "02_diarizar.py": "diarizar",
        "fundir.py": "fundir",
        "03_alinhar.py": "alinhar",
        "04_notas.py": "notas",
    }

    def fake_runner(command, **kwargs):
        stage = script_stage[Path(command[1]).name]
        calls.append(stage)
        output = stage_output_path(tmp_path, event, stage)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix == ".json":
            output.write_text('[{"text":"fala"}]', encoding="utf-8")
        else:
            output.write_text("# resultado\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = run_job(tmp_path, job["job_id"], command_runner=fake_runner)

    assert calls == ["transcrever", "diarizar", "fundir", "alinhar", "notas"]
    assert result["status"] == "completed"
    state = result["events_state"][event]
    assert state["status"] == "completed"
    assert state["completed_stages"] == ["transcrever", "diarizar", "fundir", "alinhar", "notas"]


def test_run_job_skips_valid_outputs_when_resuming(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    job = create_job(tmp_path, [event])
    for stage in ("transcrever", "diarizar", "fundir"):
        output = stage_output_path(tmp_path, event, stage)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('[{"segment":1}]', encoding="utf-8")
    calls = []
    script_stage = {"03_alinhar.py": "alinhar", "04_notas.py": "notas"}

    def fake_runner(command, **kwargs):
        stage = script_stage[Path(command[1]).name]
        calls.append(stage)
        output = stage_output_path(tmp_path, event, stage)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("# resultado\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = run_job(tmp_path, job["job_id"], command_runner=fake_runner)

    assert calls == ["alinhar", "notas"]
    assert result["status"] == "completed"


def test_run_job_continues_batch_after_event_failure(tmp_path):
    first = "2026_10_21_09_00_primeiro"
    second = "2026_10_21_10_00_segundo"
    project_with_event(tmp_path, first)
    audio_dir = tmp_path / "99_material" / second / "audio"
    audio_dir.mkdir(parents=True)
    (audio_dir / f"{second}.wav").write_bytes(b"fixture")
    job = create_job(tmp_path, [first, second])
    calls = []
    script_stage = {
        "01_transcrever.py": "transcrever",
        "02_diarizar.py": "diarizar",
        "fundir.py": "fundir",
        "03_alinhar.py": "alinhar",
        "04_notas.py": "notas",
    }

    def fake_runner(command, **kwargs):
        stage = script_stage[Path(command[1]).name]
        event = command[-1]
        calls.append((event, stage))
        if event == first and stage == "diarizar":
            return subprocess.CompletedProcess(command, 1, "", "falha de teste")
        output = stage_output_path(tmp_path, event, stage)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('[{"segment":1}]' if output.suffix == ".json" else "# resultado\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")

    result = run_job(tmp_path, job["job_id"], command_runner=fake_runner)

    assert result["events_state"][first]["status"] == "failed"
    assert result["events_state"][second]["status"] == "completed"
    assert result["status"] == "completed_with_errors"
    assert any(event == second for event, _ in calls)


def test_run_job_removes_output_from_failed_stage_before_resume(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    job = create_job(tmp_path, [event])

    def failed_after_writing(command, **kwargs):
        output = stage_output_path(tmp_path, event, "transcrever")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('[{"text":"parcial"}]', encoding="utf-8")
        return subprocess.CompletedProcess(command, 1, "", "falha")

    result = run_job(tmp_path, job["job_id"], command_runner=failed_after_writing)

    assert result["events_state"][event]["status"] == "failed"
    assert not stage_output_path(tmp_path, event, "transcrever").exists()


def test_launch_job_submits_unique_launchd_job_and_returns_immediately(tmp_path):
    project_root = tmp_path / "project with space"
    project_root.mkdir()
    project_with_event(project_root)
    job = create_job(project_root, ["2026_10_21_09_00_reuniao"])
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    result = launch_job(project_root, job["job_id"], command_runner=fake_runner)

    assert result["status"] == "queued"
    assert len(calls) == 1
    assert calls[0][:5] == [
        "/bin/launchctl",
        "submit",
        "-l",
        f"com.armel.gravador-processamento.{job['job_id']}",
        "--",
    ]
    assert "run --job-id" in calls[0][-1]
    assert shlex.quote(str(project_root.resolve())) in calls[0][-1]


def test_launch_job_failure_is_recorded(tmp_path):
    project_with_event(tmp_path)
    job = create_job(tmp_path, ["2026_10_21_09_00_reuniao"])

    def failed_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 71, "", "launch failed")

    with pytest.raises(RuntimeError, match="launchctl submit falhou"):
        launch_job(tmp_path, job["job_id"], command_runner=failed_runner)
    assert get_job_status(tmp_path, job["job_id"])["status"] == "failed"


def test_launch_job_rejects_duplicate_active_event(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    first = create_job(tmp_path, [event])
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        if command[1] == "list":
            return subprocess.CompletedProcess(command, 0, "pid\tstatus\tlabel", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    launch_job(tmp_path, first["job_id"], command_runner=fake_runner)
    second = create_job(tmp_path, [event])

    with pytest.raises(JobAlreadyRunning):
        launch_job(tmp_path, second["job_id"], command_runner=fake_runner)

    assert sum(command[1] == "submit" for command in calls) == 1
    assert get_job_status(tmp_path, second["job_id"])["status"] == "rejected"


def test_cli_start_event_returns_job_id_without_waiting(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    code = processar_cli.main(["start", "--evento", event], project_root=tmp_path, command_runner=fake_runner)

    assert code == 0
    assert len(calls) == 1
    assert calls[0][1] == "submit"


def test_cli_status_without_job_id_lists_jobs(tmp_path, capsys):
    project_with_event(tmp_path)
    job = create_job(tmp_path, ["2026_10_21_09_00_reuniao"])
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, "", "not loaded")

    code = processar_cli.main(["status"], project_root=tmp_path, command_runner=fake_runner)

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["jobs"][0]["job_id"] == job["job_id"]
    assert result["jobs"][0]["status"] == "queued"
    assert calls == []  # jobs without a launchd label need no state mutation/query


def test_cli_start_pending_snapshots_events_before_launch(tmp_path, monkeypatch):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    monkeypatch.setattr(processar_cli, "_pending_events", lambda _: [event])
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    code = processar_cli.main(["start", "--pendentes"], project_root=tmp_path, command_runner=fake_runner)

    assert code == 0
    saved_jobs = list((tmp_path / "99_material/.processamento/jobs").glob("*.json"))
    assert len(saved_jobs) == 1
    saved = json.loads(saved_jobs[0].read_text(encoding="utf-8"))
    assert saved["events"] == [event]
    assert sum(command[1] == "submit" for command in calls) == 1


def test_cli_status_reports_interrupted_job_without_known_job_id(tmp_path, monkeypatch, capsys):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    job = create_job(tmp_path, [event])
    job["status"] = "running"
    job["launch_label"] = f"com.armel.gravador-processamento.{job['job_id']}"
    from processamento import save_job

    save_job(tmp_path, job)

    def missing_job(command, **kwargs):
        return subprocess.CompletedProcess(command, 113, "", "not loaded")

    code = processar_cli.main(["status"], project_root=tmp_path, command_runner=missing_job)

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["jobs"][0]["status"] == "interrupted"
    assert "resume" in result["jobs"][0]["status_note"]


def test_cli_status_lists_active_jobs_before_recent_completed_jobs(tmp_path, capsys):
    event_one = "2026_10_21_09_00_ativo"
    event_two = "2026_10_21_10_00_concluido"
    project_with_event(tmp_path, event_one)
    second_audio = tmp_path / "99_material" / event_two / "audio"
    second_audio.mkdir(parents=True)
    (second_audio / f"{event_two}.wav").write_bytes(b"fixture")
    active = create_job(tmp_path, [event_one])
    active["status"] = "running"
    active["launch_label"] = f"com.armel.gravador-processamento.{active['job_id']}"
    completed = create_job(tmp_path, [event_two])
    completed["status"] = "completed"
    from processamento import save_job

    save_job(tmp_path, active)
    save_job(tmp_path, completed)

    def active_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "active", "")

    code = processar_cli.main(["status"], project_root=tmp_path, command_runner=active_runner)

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["jobs"][0]["job_id"] == active["job_id"]
    assert result["jobs"][0]["status"] == "running"


def test_cli_resume_by_event_reuses_latest_retryable_job(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    job = create_job(tmp_path, [event])
    job["status"] = "failed"
    job["error"] = "falha anterior"
    from processamento import save_job

    save_job(tmp_path, job)
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    code = processar_cli.main(["resume", "--evento", event], project_root=tmp_path, command_runner=fake_runner)

    assert code == 0
    assert len(list((tmp_path / "99_material/.processamento/jobs").glob("*.json"))) == 1
    assert sum(command[1] == "submit" for command in calls) == 1


def test_event_log_redacts_tokens(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)

    _append_event_log(
        tmp_path,
        event,
        "diarizar",
        "Authorization: Bearer abcdef123456",
        "HUGGINGFACE_TOKEN=hf_abcdefghijklmnop",
    )

    log = (tmp_path / "99_material" / event / ".processamento/processamento.log").read_text()
    assert "[REDACTED]" in log
    assert "abcdef123456" not in log
    assert "hf_abcdefghijklmnop" not in log


def test_parallel_submissions_for_same_event_create_only_one_launchd_job(tmp_path):
    event = "2026_10_21_09_00_reuniao"
    project_with_event(tmp_path, event)
    first = create_job(tmp_path, [event])
    second = create_job(tmp_path, [event])
    active_labels = set()
    submitted_labels = []
    guard = threading.Lock()

    def fake_runner(command, **kwargs):
        if command[1] == "list":
            with guard:
                active = command[2] in active_labels
            return subprocess.CompletedProcess(command, 0 if active else 113, "", "")
        with guard:
            submitted_labels.append(command[3])
            active_labels.add(command[3])
        time.sleep(0.1)
        return subprocess.CompletedProcess(command, 0, "", "")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(launch_job, tmp_path, job["job_id"], fake_runner)
            for job in (first, second)
        ]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except JobAlreadyRunning:
                outcomes.append("duplicate")

    assert len(submitted_labels) == 1
    assert outcomes.count("duplicate") == 1


@pytest.mark.skipif(os.environ.get("RUN_LAUNCHD_INTEGRATION") != "1", reason="requires explicit macOS launchd integration run")
def test_launchctl_worker_survives_return_from_submit(tmp_path):
    event = "2026_10_21_09_00_fixture"
    project_with_event(tmp_path, event)
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    marker = tmp_path / "worker-finished.txt"
    worker = scripts_dir / "07_processar.py"
    worker.write_text(
        "import json, pathlib, sys, time\n"
        "root = pathlib.Path(__file__).resolve().parent.parent\n"
        "job_id = sys.argv[sys.argv.index('--job-id') + 1]\n"
        "job = json.loads((root / '99_material/.processamento/jobs' / f'{job_id}.json').read_text())\n"
        "time.sleep(2)\n"
        "pathlib.Path(job['fixture_marker']).write_text('finished')\n",
        encoding="utf-8",
    )
    job = create_job(tmp_path, [event])
    job["fixture_marker"] = str(marker)
    save_job(tmp_path, job)
    label = f"com.armel.gravador-processamento.{job['job_id']}"

    try:
        launch_job(tmp_path, job["job_id"])
        assert not marker.exists()
        visible_status = processar_cli._effective_status(
            tmp_path,
            get_job_status(tmp_path, job["job_id"]),
            subprocess.run,
        )
        assert visible_status["status"] in {"queued", "running"}
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.2)
        assert marker.read_text(encoding="utf-8") == "finished"
    finally:
        subprocess.run(["/bin/launchctl", "remove", label], check=False, capture_output=True, text=True)

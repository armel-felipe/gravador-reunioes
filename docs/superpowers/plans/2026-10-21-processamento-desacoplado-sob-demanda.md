# Processamento Desacoplado Sob Demanda Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Process user-requested recordings in a durable local macOS job that outlives chat tool limits, records progress, and can resume safely without scheduling recurring work.

**Architecture:** Add a Python orchestration module and CLI. The CLI snapshots the requested event(s), saves a job manifest, and submits a one-shot `launchctl` job. The worker executes the existing stage scripts sequentially, persists atomic per-event state and logs, validates outputs before skipping completed stages, and supports status/resume commands. Update the canonical local skill and documentation to use this entry point.

**Tech Stack:** Python 3.9-compatible standard library (`json`, `subprocess`, `fcntl`, `pathlib`, `uuid`, `datetime`, `typing.Optional`), existing project scripts and pytest, macOS `launchctl submit`.

## Global Constraints

- Processing remains explicit and on demand; do not add cron, recurring launchd schedules, or an always-on daemon.
- Process pending events sequentially from a snapshot taken when the request starts.
- A sleeping Mac pauses the job; do not prevent sleep or request automatic wake.
- Never read, print, persist, or commit `.env` contents or other credentials.
- Keep audio, transcript, and notes under their existing `99_material/<event>/` paths; operational state may live in a hidden per-event subdirectory.
- Preserve existing script entry points and stage order: transcribe → diarize → merge speakers → align → notes.
- Only mark an event successful after its final notes file is non-empty and atomically written.
- Do not commit changes unless the user explicitly asks for a commit.

---

## File Map

- Create `scripts/processamento.py`: job manifest/state persistence, event validation, stage-output validation, per-event locking, sequential worker, and launchd command adapter.
- Create `scripts/07_processar.py`: CLI for `start`, `run`, `status`, and `resume`; keep orchestration policy in `processamento.py`.
- Create `scripts/test_processamento.py`: pytest coverage for pure orchestration, resume, queue behavior, locking, status, and launchd command construction using injected fakes.
- Modify `scripts/notas.py`: write final notes atomically so interruption cannot expose a truncated notes file as the processed marker.
- Modify `scripts/04_notas.py`: accept an optional per-job model ID and pass it to notes generation without editing `config.yaml`.
- Modify `.opencode/skills/processar-gravacao/SKILL.md`: use the CLI to start or resume jobs and explain status checks and pending batches.
- Modify `README.md`: document on-demand detached jobs, status/resume commands, and sleep behavior; remove the obsolete claim that the chat timeout is an unavoidable processing cutoff.
- Modify `mapa.md`: keep the script and skill inventory accurate for the new job entry point.
- Modify `ROADMAP.md`: record completion of on-demand background processing without reviving the canceled recurring automation.

## Job and State Interfaces

Use these stable interfaces throughout the tasks:

```python
STAGES = ("transcrever", "diarizar", "fundir", "alinhar", "notas")

def create_job(project_root: Path, events: list[str], model_override: Optional[str] = None) -> dict:
    """Persist and return {job_id, events, status, created_at, updated_at}."""

def run_job(project_root: Path, job_id: str, command_runner=subprocess.run) -> dict:
    """Run the saved event snapshot sequentially; return the final job manifest."""

def get_job_status(project_root: Path, job_id: str) -> dict:
    """Return the persisted job and per-event state without launching a process."""

def launch_job(project_root: Path, job_id: str, command_runner=subprocess.run) -> dict:
    """Submit one launchd one-shot worker and return immediately."""
```

Persist batch manifests under `99_material/.processamento/jobs/<job_id>.json`. Persist event state and append-only logs under `99_material/<event>/.processamento/`. Store only event names, stage/status, timestamps, process metadata needed for status, and sanitized error summaries. Use temporary files plus `Path.replace()` for atomic JSON state changes.

The CLI contract is:

```text
python scripts/07_processar.py start --evento <nome_base>
python scripts/07_processar.py start --pendentes
python scripts/07_processar.py start --evento <nome_base> --modelo <model-id>
python scripts/07_processar.py run --job-id <job_id>       # called by launchd
python scripts/07_processar.py status [--job-id <job_id>]
python scripts/07_processar.py resume (--job-id <job_id> | --evento <nome_base> | --pendentes)
```

`start --pendentes` snapshots `.venv/bin/python scripts/06_pendentes.py` results before creating the manifest. An optional `model_override` is stored in the job manifest and passed only to the notes subprocess; it is never written to `config.yaml`. Preserve the existing ability to use the exact model ID explicitly requested by the user; reject empty IDs, control characters, and IDs longer than 256 characters. `resume` may submit only jobs in `failed` or `interrupted` state; active jobs return their current job ID instead of launching duplicates.

When `status` has no job ID, list active jobs first and the most recent completed/failed jobs after them, so a new chat can discover an earlier job without retaining its ID. `resume --evento` finds the most recent non-completed job for that event; if none exists, it creates a new one-event job. `resume --pendentes` creates a new job from the current pending snapshot; validated outputs from earlier attempts are reused stage by stage.

## Implementation Tasks

### Task 1: Add atomic job and event state with tests

**Files:**
- Create: `scripts/processamento.py`
- Create: `scripts/test_processamento.py`

**Interfaces:**
- Produces `create_job(project_root: Path, events: list[str], model_override: Optional[str] = None) -> dict` and state helpers used by later tasks.
- A batch manifest has `job_id`, `events`, `status`, `created_at`, `updated_at`, and per-event outcomes.
- Per-event state has `status`, `current_stage`, `completed_stages`, `started_at`, `updated_at`, `finished_at`, and `error` (null unless failed).

- [ ] **Step 1: Write failing tests for safe event names and manifest creation.** Add these tests to `scripts/test_processamento.py`:

```python
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from processamento import create_job, validate_event_name


def test_create_job_persists_snapshot_and_model_override(tmp_path):
    job = create_job(tmp_path, ["2026_10_21_09_00_reuniao"], "gemma-4-26b-a4b-it-q4_k_m")
    saved = json.loads((tmp_path / "99_material/.processamento/jobs" / f"{job['job_id']}.json").read_text())
    assert saved["events"] == ["2026_10_21_09_00_reuniao"]
    assert saved["model_override"] == "gemma-4-26b-a4b-it-q4_k_m"
    assert saved["status"] == "queued"


@pytest.mark.parametrize("name", ["../outside", "nested/event", "", ".", ".."])
def test_event_names_cannot_escape_material_root(name):
    with pytest.raises(ValueError):
        validate_event_name(name)


def test_create_job_rejects_empty_event_list(tmp_path):
    with pytest.raises(ValueError):
        create_job(tmp_path, [])
```
- [ ] **Step 2: Run the focused tests and confirm failure.** Run `pytest scripts/test_processamento.py -q`; expected: import or missing-function failures for `create_job` and event validation.
- [ ] **Step 3: Implement manifest creation and atomic state writes.** Define `STAGES`, `validate_event_name`, `_atomic_write_json`, `create_job`, `load_job`, `save_job`, and `event_state_path`. Generate `job_id` with `uuid.uuid4().hex`; use timezone-aware ISO timestamps. Reject paths instead of normalizing them into allowed names. Atomic JSON persistence must use a temporary sibling file:

```python
def _atomic_write_json(destination: Path, value: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
```
- [ ] **Step 4: Add failing/pass tests for lock exclusivity and stale lock handling.** Use a temporary project root and two simultaneous lock attempts; assert the second attempt raises `JobAlreadyRunning`. Release the first lock and assert the next succeeds. Use `fcntl.flock` on macOS and keep the lock file in each event's hidden `.processamento` directory. The lock context must release automatically on exceptions:

```python
with event_lock(tmp_path, "2026_10_21_09_00_reuniao"):
    with pytest.raises(JobAlreadyRunning):
        with event_lock(tmp_path, "2026_10_21_09_00_reuniao"):
            pass
with event_lock(tmp_path, "2026_10_21_09_00_reuniao"):
    pass
```
- [ ] **Step 5: Run `pytest scripts/test_processamento.py -q`.** Expected: all state and locking tests pass without touching real `99_material` data.

### Task 2: Implement resumable sequential stage execution

**Files:**
- Modify: `scripts/processamento.py`
- Modify: `scripts/test_processamento.py`

**Interfaces:**
- Produces `run_job(project_root: Path, job_id: str, command_runner=subprocess.run) -> dict` and `validate_stage_output(stage: str, paths: dict) -> bool`.
- Uses `common.audio_paths(event)` and runs existing stage scripts using the current Python executable and project root as `cwd`.

- [ ] **Step 1: Write failing tests for stage order and output checks.** Inject a fake `command_runner` that records commands and creates the expected outputs. Assert the order `01_transcrever.py`, `02_diarizar.py`, `fundir.py`, `03_alinhar.py`, `04_notas.py`. Assert missing or empty outputs fail validation for JSON and Markdown stages. The injected runner must receive the complete argument vector and `cwd`, for example:

```python
def fake_runner(command, *, cwd, check, capture_output, text):
    calls.append((command, cwd))
    stage_by_script = {
        "01_transcrever.py": "transcrever",
        "02_diarizar.py": "diarizar",
        "fundir.py": "fundir",
        "03_alinhar.py": "alinhar",
        "04_notas.py": "notas",
    }
    create_expected_output(stage_by_script[Path(command[1]).name], command[-1])
    return subprocess.CompletedProcess(command, 0, "", "")
```
- [ ] **Step 2: Run the focused tests and confirm failure.** Run `pytest scripts/test_processamento.py -q`; expected: missing `run_job`/`validate_stage_output` failures.
- [ ] **Step 3: Implement the stage runner.** For each event acquire its lock, update state before each stage, invoke `[sys.executable, script_path, event]` with `cwd=project_root`, and validate the expected output after exit code 0. Output mapping: transcription JSON, diarization JSON, fused diarization JSON, aligned Markdown, and notes Markdown from `audio_paths`. JSON outputs must parse and be non-empty lists; Markdown outputs must be non-empty text. Record completed stages atomically and set event `completed` only after notes validation. When `model_override` is not null, append `--modelo <model-id>` to the notes stage arguments; all other stage commands remain unchanged.
- [ ] **Step 4: Add failing/pass tests for resuming and failure isolation.** Seed valid outputs for the first three stages and assert only alignment and notes execute. Make diarization fail for the first event in a two-event job and assert the first event is marked failed while the second still runs and can complete; assert the batch ends `completed_with_errors`:

```python
result = run_job(tmp_path, job["job_id"], command_runner=failing_diarization_runner)
assert result["events"][0]["status"] == "failed"
assert result["events"][1]["status"] == "completed"
assert result["status"] == "completed_with_errors"
```
- [ ] **Step 5: Run focused tests.** Run `pytest scripts/test_processamento.py -q`; expected: resume skips valid outputs, failed stages do not mark notes complete, and later batch events still run.

### Task 3: Make notes completion atomic

**Files:**
- Modify: `scripts/notas.py`
- Modify: `scripts/04_notas.py`
- Modify: `scripts/test_notas.py`

**Interfaces:**
- Preserve notes generation behavior and add `main(nome_base, model_override=None)`; a model override changes only the in-memory config for that one subprocess.

- [ ] **Step 1: Add a failing persistence test.** Extract a small `_write_notes_atomic(destination: Path, text: str)` helper; test that it leaves no destination for an empty result and replaces the destination only after the full content is written. Inject or monkeypatch `Path.replace` to raise and assert an existing notes file remains unchanged.
- [ ] **Step 2: Run `pytest scripts/test_notas.py -q`.** Expected: fail because `_write_notes_atomic` is not defined.
- [ ] **Step 3: Implement `_write_notes_atomic`.** Create the notes directory, write UTF-8 to a sibling temporary file, flush and `os.fsync` it, then `replace()` the destination. In a `finally` block remove a leftover temporary file. Have `main` reject empty model output before calling the helper:

```python
def _write_notes_atomic(destination: Path, text: str) -> None:
    if not text.strip():
        raise ValueError("notas vazias não podem marcar o evento como processado")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
```

- [ ] **Step 4: Preserve one-run model selection without changing global config.** Add an optional `--modelo` to `scripts/04_notas.py`; pass the value to `notas.main(nome_base, model_override=None)`. When supplied, set only `cfg["llm"]["providers"][cfg["llm"]["active"]]["model"]` in memory. Test that `config.yaml` bytes are unchanged and that empty IDs, IDs over 256 characters, and IDs containing control characters are rejected. The CLI parser shape is:

```python
parser = argparse.ArgumentParser()
parser.add_argument("nome_base")
parser.add_argument("--modelo", choices=ALLOWED_MODEL_IDS)
args = parser.parse_args(argv)
main(args.nome_base, model_override=args.modelo)
```
- [ ] **Step 5: Run `pytest scripts/test_notas.py -q`.** Expected: all prior note tests plus atomic-write and model-override tests pass; successful generation still writes the same Markdown structure.

### Task 4: Add launchd submission and the processing CLI

**Files:**
- Create: `scripts/07_processar.py`
- Modify: `scripts/processamento.py`
- Modify: `scripts/test_processamento.py`
- Modify: `scripts/04_notas.py`

**Interfaces:**
- `launch_job(project_root, job_id, command_runner)` launches `sys.executable <absolute scripts/07_processar.py> run --job-id <job_id>` through `/bin/launchctl submit` under a unique `com.armel.gravador-processamento.<job_id>` label.
- CLI `main(argv=None) -> int` implements `start`, `run`, `status`, and `resume` exactly as listed above; `start` accepts either `--evento` or `--pendentes`, with optional `--modelo`; `status` may omit a job ID; `resume` accepts a job ID, event, or current pending set.

- [ ] **Step 1: Write failing tests for CLI parsing and launchd submission.** Assert `start --evento` creates a one-event job; `start --pendentes` snapshots pending names via an injected event provider; `--modelo` is stored in the job; `status` is read-only; `resume` refuses active and successful jobs. Assert the submitted command includes a unique label, project-root-safe quoting, worker subcommand, and job ID, and does not wait for pipeline completion.
- [ ] **Step 2: Run `pytest scripts/test_processamento.py -q`.** Expected: fail because CLI and launchd functions are absent.
- [ ] **Step 3: Implement `launch_job` and CLI.** Use `subprocess.run` only to submit the launchd job, with `check=False` and captured output; raise a sanitized error on non-zero status. Redirect worker stdout/stderr to the batch log by launching a quoted `/bin/bash -lc` command, following the existing launchd pattern in `native_host/server_control.py`. Do not put environment values in the command. `run` loads the saved manifest and calls `run_job`; `status` reads persisted state; `resume` reuses the same job ID and event snapshot. Notes arguments carry the stored `model_override` only for that job; `scripts/04_notas.py` applies it in memory, leaving the tracked configuration untouched.
- [ ] **Step 4: Add tests for submission errors and duplicate active event jobs.** Fake launchctl non-zero status; assert the manifest records launch failure. Start a second job containing an already active event; assert the duplicate is rejected or reported as already active and no second submit occurs:

```python
result = controller.start_event("2026_10_21_09_00_reuniao")
duplicate = controller.start_event("2026_10_21_09_00_reuniao")
assert duplicate["status"] == "already_running"
assert len(fake_launchctl.submissions) == 1
```
- [ ] **Step 5: Run `pytest scripts/test_processamento.py -q`.** Expected: all CLI and job-launch tests pass without invoking real `launchctl`.

### Task 5: Integrate the local skill and user documentation

**Files:**
- Modify: `.opencode/skills/processar-gravacao/SKILL.md`
- Modify: `README.md`
- Modify: `mapa.md`
- Modify: `ROADMAP.md`

**Interfaces:**
- Skill commands use `.venv/bin/python scripts/07_processar.py ...`; direct stage-by-stage shell orchestration is removed from the normal request flow.

- [ ] **Step 1: Update skill instructions.** For a specific event, start a one-event job; for “todas as pendentes”, use `start --pendentes`. Explain the returned job ID, status query, and resume behavior. Preserve supported one-run model choices by passing `--modelo` at job start; never mutate global `config.yaml`. Keep quality review instructions for completed outputs.
- [ ] **Step 2: Update README and roadmap.** Document on-demand local background execution, sequential batch snapshot semantics, status/resume examples, sleep pause behavior, and the fact that this does not install recurring scheduling. Update the old 15-minute-limit text to explain that OpenWork chat execution is bypassed by the detached worker. Record a new completed roadmap item without changing R-006's canceled status or activating R-008's scheduled design.
- [ ] **Step 3: Validate documentation consistency.** Run `rg -n "15 min|15-minute|automação.*processamento|processamento.*automático" README.md ROADMAP.md AGENTS.md .opencode/skills/processar-gravacao/SKILL.md`; update outdated statements and retain only claims that describe an actual OpenWork-only path. Clarify the new CLI route.
- [ ] **Step 4: Run the complete required tests.** Run `.venv/bin/python -m pytest scripts/ server/ native_host/ -v` and `node --test extension/*.test.js`; expected: all existing and new tests pass.

### Task 6: Verify the real macOS detached lifecycle

**Files:**
- No code changes unless a test reveals a defect; report test evidence in the final review.

- [ ] **Step 1: Verify fast submit with a lightweight fixture job.** Use a temporary project root and a fake worker that writes a completion marker after a delay. Start it through the CLI, allow the initiating command to exit, and verify the marker appears and status changes from `queued/running` to `completed`.
- [ ] **Step 2: Verify resume and duplicate prevention with fixture jobs.** Force a fixture failure after one stage, resume the same job ID, and verify the completed stage is not repeated; submit a second start for the same active event and verify no duplicate process starts.
- [ ] **Step 3: Verify batch failure isolation.** Run a fixture batch with one intentional event failure followed by a successful event; verify the second completes and the final status reports both outcomes.
- [ ] **Step 4: Remove only temporary fixture data and report operational limits.** Confirm no recurring launchd job was installed. Document that sleep pauses processing and that a new chat request is needed to inspect the final job result.

## Plan Self-Review

- **Spec coverage:** Explicit on-demand start, pending snapshot/serial order, continuing after per-event failure, persisted state/logging, atomic writes, chat-independent execution, duplicate locks, resume from validated outputs, existing map-reduce checkpoints, `launchd` one-shot only, status query, sleep behavior, secret handling, and acceptance testing are assigned to Tasks 1–6.
- **Placeholder scan:** No TBD/TODO instructions remain; each task specifies files, behavior, test command, and expected result.
- **Interface consistency:** `create_job`, `run_job`, `get_job_status`, `launch_job`, `validate_stage_output`, `main(argv=None)` and the four CLI subcommands are defined once and reused consistently; status without an ID and resume by event/pending set are specified for fresh-chat discovery.
- **Scope check:** This is one bounded subsystem: durable, user-triggered orchestration of the existing local pipeline. It does not revive recurring automation or change transcription/diarization algorithms.

## Execution Handoff

When implementation begins, select one of the required execution sub-skills named in the header. Do not install or activate any recurring schedule.

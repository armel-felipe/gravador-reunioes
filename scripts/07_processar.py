"""Start, inspect, resume, or run a durable local processing job."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pendentes import eventos_pendentes
from processamento import (
    JobAlreadyRunning,
    _material_root,
    create_job,
    get_job_status,
    launch_job,
    list_jobs,
    load_job,
    run_job,
    save_job,
    validate_model_override,
)


ROOT = Path(__file__).resolve().parent.parent
def _pending_events(project_root):
    return eventos_pendentes(str(_material_root(project_root)))


def _submit(project_root, events, model_override, command_runner):
    job = create_job(project_root, events, model_override=model_override)
    launched = launch_job(project_root, job["job_id"], command_runner=command_runner)
    return {"job_id": launched["job_id"], "status": launched["status"], "events": events}


def _effective_status(project_root, job, command_runner):
    if job.get("status") not in {"queued", "running"} or not job.get("launch_label"):
        return job
    check = command_runner(
        ["/bin/launchctl", "list", job["launch_label"]],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        view = dict(job)
        view["status"] = "interrupted"
        view["status_note"] = "job não está registrado no launchd; use resume para retomá-lo"
        return view
    return job


def _resume_job(project_root, job_id, command_runner):
    job = get_job_status(project_root, job_id)
    if job["status"] == "completed":
        raise ValueError("o job já foi concluído")
    if job.get("launch_label") and job["status"] in {"queued", "running"}:
        check = command_runner(
            ["/bin/launchctl", "list", job["launch_label"]],
            check=False,
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return {"job_id": job_id, "status": "already_running", "events": job["events"]}
        job["status"] = "interrupted"
    job["status"] = "queued"
    job["error"] = None
    save_job(project_root, job)
    launched = launch_job(project_root, job_id, command_runner=command_runner)
    return {"job_id": job_id, "status": launched["status"], "events": job["events"]}


def build_parser():
    parser = argparse.ArgumentParser(description="Processa gravações sob demanda em segundo plano.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    start = subparsers.add_parser("start", help="inicia um job local desacoplado")
    start_target = start.add_mutually_exclusive_group(required=True)
    start_target.add_argument("--evento")
    start_target.add_argument("--pendentes", action="store_true")
    start.add_argument("--modelo")

    run = subparsers.add_parser("run", help=argparse.SUPPRESS)
    run.add_argument("--job-id", required=True)

    status = subparsers.add_parser("status", help="consulta jobs recentes ou um job específico")
    status.add_argument("--job-id")

    resume = subparsers.add_parser("resume", help="retoma um job ou eventos pendentes")
    resume_target = resume.add_mutually_exclusive_group(required=True)
    resume_target.add_argument("--job-id")
    resume_target.add_argument("--evento")
    resume_target.add_argument("--pendentes", action="store_true")

    return parser


def main(argv=None, project_root=None, command_runner=None):
    from subprocess import run as default_command_runner

    project_root = Path(project_root or ROOT).resolve()
    command_runner = command_runner or default_command_runner
    args = build_parser().parse_args(argv)
    try:
        if args.action == "run":
            job = run_job(project_root, args.job_id)
            return 0 if job["status"] == "completed" else 1

        if args.action == "start":
            model_override = validate_model_override(args.modelo)
            events = [args.evento] if args.evento else _pending_events(project_root)
            if not events:
                print(json.dumps({"status": "no_pending_events", "events": []}, ensure_ascii=False))
                return 0
            result = _submit(project_root, events, model_override, command_runner)
            print(json.dumps(result, ensure_ascii=False))
            return 0

        if args.action == "status":
            jobs = [get_job_status(project_root, args.job_id)] if args.job_id else list_jobs(project_root)
            result = [_effective_status(project_root, job, command_runner) for job in jobs]
            if not args.job_id:
                result.sort(key=lambda job: job.get("created_at", ""), reverse=True)
                result.sort(key=lambda job: 0 if job["status"] in {"queued", "running"} else 1)
                result = result[:20]
            print(json.dumps({"jobs": result}, ensure_ascii=False, indent=2))
            return 0

        if args.action == "resume":
            if args.job_id:
                result = _resume_job(project_root, args.job_id, command_runner)
            elif args.evento:
                previous = next(
                    (
                        job
                        for job in list_jobs(project_root)
                        if args.evento in job.get("events", [])
                        and job.get("status") != "completed"
                    ),
                    None,
                )
                if previous:
                    result = _resume_job(project_root, previous["job_id"], command_runner)
                else:
                    result = _submit(project_root, [args.evento], None, command_runner)
            else:
                events = [args.evento] if args.evento else _pending_events(project_root)
                if not events:
                    print(json.dumps({"status": "no_pending_events", "events": []}, ensure_ascii=False))
                    return 0
                result = _submit(project_root, events, None, command_runner)
            print(json.dumps(result, ensure_ascii=False))
            return 0
    except (FileNotFoundError, JobAlreadyRunning, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

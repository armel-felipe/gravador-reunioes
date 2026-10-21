import io
import json
import struct
import subprocess
import unittest
from pathlib import Path

from native_host.server_control import ServerController, run_native_message_loop


class ServerControllerTests(unittest.TestCase):
    def make_controller(self, health_values, subprocess_calls=None):
        calls = subprocess_calls if subprocess_calls is not None else []

        def health():
            value = health_values.pop(0) if len(health_values) > 1 else health_values[0]
            return value

        def run(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0)

        return ServerController(
            project_root=Path("/projeto"),
            health_check=health,
            command_runner=run,
            sleep=lambda _: None,
            start_attempts=2,
        ), calls

    def test_start_does_not_submit_when_server_is_online(self):
        controller, calls = self.make_controller([True])

        result = controller.handle("start")

        self.assertEqual(result, {"ok": True, "action": "start", "online": True, "already_online": True})
        self.assertEqual(calls, [])

    def test_start_submits_and_waits_until_health_is_online(self):
        controller, calls = self.make_controller([False, True])

        result = controller.handle("start")

        self.assertTrue(result["ok"])
        self.assertTrue(result["online"])
        self.assertEqual(calls[0][0][:3], ["/bin/launchctl", "submit", "-l"])
        self.assertIn("com.armel.gravador-servidor", calls[0][0])

    def test_start_quotes_project_root_with_spaces(self):
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0)

        controller = ServerController(
            project_root=Path("/projeto com espaço"),
            health_check=iter([False, True]).__next__,
            command_runner=run,
            sleep=lambda _: None,
            start_attempts=2,
        )

        controller.handle("start")

        self.assertIn("cd '/projeto com espaço'", calls[0][-1])

    def test_stop_is_idempotent_when_server_is_already_offline(self):
        controller, calls = self.make_controller([False])

        result = controller.handle("stop")

        self.assertEqual(result, {"ok": True, "action": "stop", "online": False, "already_stopped": True})
        self.assertEqual(calls, [])

    def test_unknown_action_never_runs_a_command(self):
        controller, calls = self.make_controller([False])

        result = controller.handle("restart")

        self.assertEqual(result["ok"], False)
        self.assertIn("ação", result["error"])
        self.assertEqual(calls, [])

    def test_native_message_loop_reads_and_writes_length_prefixed_json(self):
        request = json.dumps({"action": "status"}).encode()
        stdin = io.BytesIO(struct.pack("<I", len(request)) + request)
        stdout = io.BytesIO()
        controller, _ = self.make_controller([True])

        run_native_message_loop(controller, stdin=stdin, stdout=stdout)

        stdout.seek(0)
        length = struct.unpack("<I", stdout.read(4))[0]
        response = json.loads(stdout.read(length))
        self.assertEqual(response, {"ok": True, "action": "status", "online": True})


if __name__ == "__main__":
    unittest.main()

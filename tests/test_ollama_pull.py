from __future__ import annotations

import io
import subprocess
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from app.services import models as model_service


class _StreamingResponse:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self.closed = False

    def __iter__(self):
        return iter(self._lines)

    def close(self) -> None:
        self.closed = True


class _CliProcess:
    returncode = 0

    def communicate(self):
        return "pulled successfully\n", ""

    def poll(self):
        return self.returncode


class OllamaPullTests(unittest.TestCase):
    def setUp(self) -> None:
        with model_service.MODEL_PULL_LOCK:
            model_service.MODEL_PULLS.clear()
            model_service.MODEL_PULL_PROCS.clear()
            model_service.MODEL_PULL_STREAMS.clear()
            model_service.MODEL_PULL_CANCEL_EVENTS.clear()

    def _new_task(self, task_id: str = "task") -> None:
        with model_service.MODEL_PULL_LOCK:
            model_service.MODEL_PULLS[task_id] = {
                "task_id": task_id,
                "model": "qwen2.5vl:7b",
                "state": "pending",
                "message": "Запуск загрузки…",
            }
            model_service.MODEL_PULL_CANCEL_EVENTS[task_id] = __import__("threading").Event()

    def test_streaming_api_pull_reports_progress_and_completes(self) -> None:
        self._new_task()
        response = _StreamingResponse(
            [
                b'{"status":"pulling manifest"}\n',
                b'{"status":"pulling layer","total":100,"completed":25}\n',
                b'{"status":"success","total":100,"completed":100}\n',
            ]
        )
        with (
            patch.object(model_service, "urlopen", return_value=response) as urlopen,
            patch.object(
                model_service,
                "_ollama_cli_info",
                return_value={"path": "/opt/homebrew/bin/ollama", "version": "ollama version is 0.32.4", "error": None},
            ),
            patch.object(model_service.subprocess, "Popen") as popen,
        ):
            model_service._run_model_pull("task", "qwen2.5vl:7b")

        task = model_service.pull_status("task")
        self.assertEqual(task["transport"], "api")
        self.assertEqual(task["command"], "POST /api/pull")
        self.assertEqual(task["state"], "completed")
        self.assertEqual(task["percent"], 100.0)
        self.assertTrue(response.closed)
        self.assertTrue(urlopen.called)
        popen.assert_not_called()

    def test_api_not_supported_uses_cli_without_json_flag(self) -> None:
        self._new_task()
        unsupported_api = HTTPError(
            "http://127.0.0.1:11434/api/pull",
            404,
            "not found",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"not found"}'),
        )
        process = _CliProcess()
        with (
            patch.object(model_service, "urlopen", side_effect=unsupported_api),
            patch.object(
                model_service,
                "_ollama_cli_info",
                return_value={"path": "/opt/homebrew/bin/ollama", "version": "ollama version is 0.32.4", "error": None},
            ),
            patch.object(model_service.subprocess, "Popen", return_value=process) as popen,
        ):
            model_service._run_model_pull("task", "qwen2.5vl:7b")
        unsupported_api.close()

        command = popen.call_args.args[0]
        self.assertEqual(command, ["/opt/homebrew/bin/ollama", "pull", "qwen2.5vl:7b"])
        self.assertNotIn("--json", command)
        self.assertEqual(model_service.pull_status("task")["state"], "completed")

    def test_missing_binary_and_unavailable_server_reports_actionable_error(self) -> None:
        self._new_task()
        with (
            patch.object(model_service, "urlopen", side_effect=URLError("[Errno 61] Connection refused")),
            patch.object(
                model_service,
                "_ollama_cli_info",
                return_value={"path": None, "version": None, "error": "not found in PATH"},
            ),
        ):
            model_service._run_model_pull("task", "qwen2.5vl:7b")

        task = model_service.pull_status("task")
        self.assertEqual(task["state"], "error")
        self.assertIn("API недоступен", task["message"])
        self.assertIn("бинарник", task["message"])

    def test_cli_error_keeps_stderr_for_diagnostics(self) -> None:
        self._new_task()
        failed = _CliProcess()
        failed.returncode = 1
        failed.communicate = lambda: ("", "Error: registry unavailable")
        with patch.object(model_service.subprocess, "Popen", return_value=failed):
            model_service._run_cli_model_pull("task", "qwen2.5vl:7b", "/opt/homebrew/bin/ollama")

        task = model_service.pull_status("task")
        self.assertEqual(task["state"], "error")
        self.assertEqual(task["stderr"], "Error: registry unavailable")


if __name__ == "__main__":
    unittest.main()

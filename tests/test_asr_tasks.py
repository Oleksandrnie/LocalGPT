import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.apps.asr import tasks


class FakeProcess:
    def __init__(self, **kwargs):
        self.args = kwargs["args"]
        self.pid = None
        self.alive = False
        self.stubborn = False
        self.fail_start = False
        self.fail_after_start = False
        self.on_terminate = None
        self.terminate_calls = 0
        self.kill_calls = 0

    def start(self):
        if self.fail_start:
            raise RuntimeError("start failed")
        self.pid = 12345
        self.alive = True
        if self.fail_after_start:
            raise RuntimeError("partially started")

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        pass

    def terminate(self):
        self.terminate_calls += 1
        if self.on_terminate:
            self.on_terminate()
        if not self.stubborn:
            self.alive = False

    def kill(self):
        self.kill_calls += 1
        if not self.stubborn:
            self.alive = False


class AsrTasksTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.processes = []
        self.process_options = []
        self.monitors = []
        self.fail_monitor = False

        def make_process(**kwargs):
            process = FakeProcess(**kwargs)
            if self.process_options:
                for name, value in self.process_options.pop(0).items():
                    setattr(process, name, value)
            self.processes.append(process)
            return process

        def make_monitor(**kwargs):
            monitor = Mock()
            monitor.callback = lambda: kwargs["target"](*kwargs["args"])
            if self.fail_monitor:
                monitor.start.side_effect = RuntimeError("monitor failed")
            self.monitors.append(monitor)
            return monitor

        for name, value in (
            ("TASKS_DIR", self.tmp), ("_TASKS", {}),
            ("_QUEUE_PAUSE_COUNT", 0), ("_DISPATCHING", False),
            ("_PROCESS_CTX", SimpleNamespace(Process=make_process)),
        ):
            patcher = patch.object(tasks, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(tasks.threading, "Thread", side_effect=make_monitor)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start_task(self, name):
        path = self.tmp / name
        path.touch()
        return tasks.start_transcription_task(
            input_path=str(path), model="small", prompt_preset="auto",
            preferred_language="ru", source_name=name, profile_id=7,
            session_id="session", store_result=False, origin="test",
            beam_size=3, threads=2,
        )

    def finish(self, task, result=None, error=None):
        internal = tasks._TASKS[task["id"]]
        internal["_process"].alive = False
        if result is not None:
            tasks._atomic_write_json(internal["result_path"], result)
        if error is not None:
            tasks._atomic_write_json(internal["error_path"], error)
        return tasks.get_transcription_task(task["id"])

    def test_fifo_single_child_and_idempotent_monitor_poll(self):
        first, second, third = [self.start_task(name) for name in ("one", "two", "three")]
        self.assertEqual([first["state"], second["state"], third["state"]], ["running", "queued", "queued"])
        self.assertIsNone(second["pid"])
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(tasks.get_transcription_task(second["id"])["state"], "queued")
        self.assertTrue((self.tmp / "two").exists())
        self.assertEqual(self.processes[0].args[0:4], (str(self.tmp / "one"), "small", "auto", "ru"))
        self.assertEqual(self.processes[0].args[4:11], ("one", 7, "session", False, "test", 3, 2))
        self.assertEqual(self.finish(first, result={"text": "ok"})["state"], "completed")
        self.monitors[0].callback()
        tasks.get_transcription_task(first["id"])
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(Path(self.processes[1].args[0]).name, "two")
        self.finish(second, result={"text": "next"})
        self.assertEqual(len(self.processes), 3)
        self.assertEqual(Path(self.processes[2].args[0]).name, "three")

    def test_cancel_queued_cleans_input_without_process(self):
        first, second, third = [self.start_task(name) for name in ("one", "two", "three")]
        self.assertEqual(tasks.cancel_transcription_task(second["id"])["state"], "cancelled")
        self.assertFalse((self.tmp / "two").exists())
        self.assertEqual(len(self.processes), 1)
        tasks.cancel_transcription_task(second["id"])
        self.finish(first)
        self.assertEqual(Path(self.processes[1].args[0]).name, "three")
        self.assertEqual(tasks.get_transcription_task(third["id"])["state"], "running")

    def test_active_cancel_retains_slot_and_files_until_death(self):
        first, second = self.start_task("one"), self.start_task("two")
        self.processes[0].stubborn = True
        cancelled = tasks.cancel_transcription_task(first["id"])
        self.assertEqual(cancelled["state"], "cancelling")
        self.assertEqual(len(self.processes), 1)
        self.assertTrue((self.tmp / "one").exists())
        self.assertEqual((self.processes[0].terminate_calls, self.processes[0].kill_calls), (1, 1))
        self.processes[0].alive = False
        # Polling the queued task also reconciles the dead active task.
        self.assertEqual(tasks.get_transcription_task(second["id"])["state"], "running")
        self.assertEqual(tasks.get_transcription_task(first["id"])["state"], "cancelled")
        self.assertFalse((self.tmp / "one").exists())

    def test_results_are_not_finalized_while_child_is_alive(self):
        first = self.start_task("one")
        internal = tasks._TASKS[first["id"]]
        tasks._atomic_write_json(internal["result_path"], {"text": "ok"})
        with tasks._LOCK:
            tasks._finalize_task_locked(internal)
        self.assertEqual(tasks.get_transcription_task(first["id"])["state"], "running")
        self.assertTrue(Path(internal["result_path"]).exists())

    def test_error_and_resultless_exit_advance_queue_and_cleanup(self):
        first, second, third = [self.start_task(name) for name in ("one", "two", "three")]
        result = self.finish(first, error={"code": "empty_transcription", "message": "no speech"})
        self.assertEqual((result["state"], result["error_code"]), ("error", "empty_transcription"))
        result = self.finish(second)
        self.assertEqual((result["state"], result["error_code"]), ("error", "transcription_failed"))
        self.assertEqual(tasks.get_transcription_task(third["id"])["state"], "running")
        self.assertEqual(list(self.tmp.glob("*.json")), [])

    def test_process_constructor_start_and_monitor_failures_advance_fifo(self):
        for mode in ("constructor", "start", "partial_start", "monitor"):
            with self.subTest(mode=mode):
                first, second, third = [self.start_task(f"{mode}-{name}") for name in ("one", "two", "three")]
                if mode == "constructor":
                    original = tasks._PROCESS_CTX.Process
                    calls = [0]

                    def constructor(**kwargs):
                        calls[0] += 1
                        if calls[0] == 1:
                            raise RuntimeError("constructor failed")
                        return original(**kwargs)

                    patcher = patch.object(tasks._PROCESS_CTX, "Process", side_effect=constructor)
                    patcher.start()
                elif mode in {"start", "partial_start"}:
                    self.process_options.append({"fail_start" if mode == "start" else "fail_after_start": True})
                else:
                    # Only the next monitor fails, not the following task's monitor.
                    original = tasks.threading.Thread.side_effect
                    calls = [0]

                    def monitor(**kwargs):
                        item = original(**kwargs)
                        calls[0] += 1
                        if calls[0] == 1:
                            item.start.side_effect = RuntimeError("monitor failed")
                        return item

                    patcher = patch.object(tasks.threading, "Thread", side_effect=monitor)
                    patcher.start()
                try:
                    self.finish(first, result={"text": "ok"})
                finally:
                    if mode in {"constructor", "monitor"}:
                        patcher.stop()
                self.assertEqual(tasks.get_transcription_task(second["id"])["state"], "error")
                self.assertFalse((self.tmp / f"{mode}-two").exists())
                self.assertEqual(tasks.get_transcription_task(third["id"])["state"], "running")
                self.finish(third)

    def test_monitor_failure_with_surviving_child_keeps_slot(self):
        self.fail_monitor = True
        self.process_options.append({"stubborn": True})
        first = self.start_task("one")
        self.fail_monitor = False
        second = self.start_task("two")
        self.assertEqual(first["state"], "cancelling")
        self.assertEqual(second["state"], "queued")
        self.assertEqual(len(self.processes), 1)
        self.processes[0].alive = False
        self.assertEqual(tasks.get_transcription_task(first["id"])["state"], "error")
        self.assertEqual(tasks.get_transcription_task(second["id"])["state"], "running")

    def test_cancel_all_cancels_queued_before_stopping_active(self):
        first, second, third = [self.start_task(name) for name in ("one", "two", "three")]

        def while_stopping():
            self.assertFalse((self.tmp / "two").exists())
            self.assertFalse((self.tmp / "three").exists())
            self.processes[0].alive = False
            self.monitors[0].callback()
            self.assertEqual(len(self.processes), 1)

        self.processes[0].on_terminate = while_stopping
        self.assertEqual(tasks.cancel_all_tasks(), 3)
        self.assertEqual([tasks.get_transcription_task(item["id"])["state"] for item in (first, second, third)], ["cancelled"] * 3)
        self.assertEqual(len(self.processes), 1)
        self.assertEqual(tasks.cancel_all_tasks(), 0)
        self.assertEqual(self.start_task("later")["state"], "running")

    def test_unknown_task_contract(self):
        self.assertIsNone(tasks.get_transcription_task("missing"))
        self.assertIsNone(tasks.cancel_transcription_task("missing"))


if __name__ == "__main__":
    unittest.main()

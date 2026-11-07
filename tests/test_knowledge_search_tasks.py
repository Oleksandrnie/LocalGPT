from __future__ import annotations

import threading
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from backend.apps.chat import knowledge_search_tasks as tasks


class KnowledgeSearchTaskTests(unittest.TestCase):
    def tearDown(self):
        tasks.reset()
        self.assertFalse(tasks._TASKS)

    def join(self, task_id):
        tasks._TASKS[task_id]['thread'].join(3)
        self.assertFalse(tasks._TASKS[task_id]['thread'].is_alive())

    def test_total_capacity_bounds_workers_across_profiles(self):
        release = threading.Event()
        def work(check):
            self.assertTrue(release.wait(3))
            check()
            return {'reply': 'synthetic'}
        try:
            with patch.object(tasks, 'MAX_ACTIVE_TOTAL', 2):
                first = tasks.start(profile_id=1, session_id=None, work=work, persist=lambda result: result)
                second = tasks.start(profile_id=2, session_id=None, work=work, persist=lambda result: result)
                with self.assertRaises(HTTPException) as error:
                    tasks.start(profile_id=3, session_id=None, work=Mock(), persist=Mock())
                self.assertEqual(error.exception.status_code, 429)
                release.set()
                self.join(first['task_id'])
                self.join(second['task_id'])
        finally:
            release.set()

    def test_completed_results_expire_and_retention_is_bounded(self):
        with patch.object(tasks, 'MAX_RETAINED_TASKS', 2), patch.object(tasks, 'monotonic', return_value=0):
            records = []
            for _ in range(3):
                task = tasks.start(profile_id=1, session_id=None, work=lambda check: {}, persist=lambda result: result)
                self.join(task['task_id'])
                records.append(task['task_id'])
            self.assertEqual(len(tasks._TASKS), 2)
            with self.assertRaises(HTTPException):
                tasks.get(records[0], profile_id=1, session_id=None)
            self.assertEqual(tasks.get(records[-1], profile_id=1, session_id=None)['state'], 'completed')
        with patch.object(tasks, 'monotonic', return_value=tasks.RESULT_TTL_SECONDS + 1):
            with self.assertRaises(HTTPException) as missing:
                tasks.get(records[-1], profile_id=1, session_id=None)
            self.assertEqual(missing.exception.status_code, 404)
        self.assertFalse(tasks._TASKS)

    def test_unexpected_worker_failure_is_redacted(self):
        persist = Mock()
        task = tasks.start(profile_id=1, session_id=None,
                           work=Mock(side_effect=RuntimeError('PRIVATE_SYNTHETIC_FAILURE')), persist=persist)
        self.join(task['task_id'])
        result = tasks.get(task['task_id'], profile_id=1, session_id=None)
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['error']['status_code'], 500)
        self.assertNotIn('PRIVATE_SYNTHETIC', str(result))
        persist.assert_not_called()

    def test_reset_keeps_live_workers_counted_and_stops_late_persistence(self):
        entered, release = threading.Event(), threading.Event()
        persist = Mock()
        def work(check):
            entered.set()
            self.assertTrue(release.wait(3))
            return {'reply': 'synthetic'}
        try:
            task = tasks.start(profile_id=1, session_id=None, work=work, persist=persist)
            self.assertTrue(entered.wait(3))
            tasks.reset(join_timeout=0)
            self.assertIn(task['task_id'], tasks._TASKS)
            release.set()
            self.join(task['task_id'])
            self.assertEqual(tasks.get(task['task_id'], profile_id=1, session_id=None)['state'], 'cancelled')
            persist.assert_not_called()
            tasks.reset()
            self.assertFalse(tasks._TASKS)
        finally:
            release.set()


if __name__ == '__main__':
    unittest.main()

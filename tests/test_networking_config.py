from __future__ import annotations

import re
import unittest
from pathlib import Path

from app import config


class DefaultCorsOriginRegexTests(unittest.TestCase):
    def test_allows_local_and_private_lan_origins(self) -> None:
        pattern = re.compile(config.DEFAULT_CORS_ALLOW_ORIGIN_REGEX)

        for origin in (
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://192.168.1.20:8443",
            "https://10.0.0.15:8443",
            "https://172.16.0.4:8443",
            "https://printer.local:8443",
        ):
            with self.subTest(origin=origin):
                self.assertRegex(origin, pattern)

    def test_does_not_allow_shared_cgnat_or_public_origins_by_default(self) -> None:
        pattern = re.compile(config.DEFAULT_CORS_ALLOW_ORIGIN_REGEX)

        for origin in (
            "http://100.64.0.10:8000",
            "https://8.8.8.8:8443",
        ):
            with self.subTest(origin=origin):
                self.assertNotRegex(origin, pattern)

    def test_env_example_override_does_not_reintroduce_cgnat_origins(self) -> None:
        env_example = Path(config.PROJECT_ROOT, ".env.example").read_text(encoding="utf-8")
        cors_line = next(
            line for line in env_example.splitlines()
            if line.startswith("LOCALGPT_CORS_ALLOW_ORIGIN_REGEX=")
        )
        pattern = re.compile(cors_line.split("=", 1)[1])

        self.assertRegex("http://192.168.1.20:8000", pattern)
        self.assertNotRegex("http://100.64.0.10:8000", pattern)
        self.assertNotRegex("https://8.8.8.8:8443", pattern)


if __name__ == "__main__":
    unittest.main()

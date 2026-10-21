import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from backend.apps.asr import downloads


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeStreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self, chunk_size):
        yield b"model-data"


class FakeDownloadClient:
    instances = []

    def __init__(self, *, headers, **_kwargs):
        self.headers = headers
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, _url):
        return FakeResponse(
            {"sha": "revision", "siblings": [{"rfilename": "nested/model.bin", "size": 10}]}
        )

    def stream(self, *_args, **_kwargs):
        return FakeStreamResponse()


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def get(self, _url):
        return FakeResponse(self.payload)


class AsrDownloadSecurityTests(unittest.TestCase):
    def test_hf_token_is_limited_to_official_https_origin(self):
        with patch.dict(os.environ, {"HF_TOKEN": "unit-test-token"}):
            self.assertEqual(
                downloads._http_headers("https://huggingface.co")["Authorization"],
                "Bearer unit-test-token",
            )
            for endpoint in (
                "https://hf-mirror.com",
                "https://huggingface.co.evil.example",
                "https://huggingface.co@evil.example",
                "http://huggingface.co",
                "https://huggingface.co:8443",
            ):
                with self.subTest(endpoint=endpoint):
                    self.assertNotIn("Authorization", downloads._http_headers(endpoint))

    def test_huggingface_hub_disables_cached_auth_for_nonofficial_endpoints(self):
        with patch.dict(os.environ, {"HF_TOKEN": "unit-test-token"}):
            self.assertEqual(downloads._huggingface_hub_token("https://huggingface.co"), "unit-test-token")
            self.assertIs(downloads._huggingface_hub_token("https://hf-mirror.com"), False)

    def test_http_client_drops_authorization_on_cross_origin_redirect(self):
        seen = []

        def handle(request):
            seen.append((request.url.host, request.headers.get("Authorization")))
            if request.url.host == "huggingface.co":
                return httpx.Response(302, headers={"Location": "https://hf-mirror.com/file"}, request=request)
            return httpx.Response(200, request=request)

        with patch.dict(os.environ, {"HF_TOKEN": "unit-test-token"}):
            with httpx.Client(
                follow_redirects=True,
                headers=downloads._http_headers("https://huggingface.co"),
                transport=httpx.MockTransport(handle),
            ) as client:
                response = client.get("https://huggingface.co/file")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen[0], ("huggingface.co", "Bearer unit-test-token"))
        self.assertEqual(seen[1], ("hf-mirror.com", None))

    def test_direct_download_client_does_not_authenticate_to_mirror(self):
        FakeDownloadClient.instances = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"HF_TOKEN": "unit-test-token", "HF_TRUST_ENV": "0"}
        ), patch.object(downloads.httpx, "Client", FakeDownloadClient), patch.object(
            downloads, "local_model_dir", return_value=Path(temp_dir)
        ), patch.object(downloads, "repository_for_model", return_value="org/model"):
            downloads._download_from_endpoint("task", "model", "https://hf-mirror.com")

            self.assertEqual(FakeDownloadClient.instances[-1].headers, {"User-Agent": "LocalGPT-Whisper-Transcriber/1.0"})
            self.assertEqual((Path(temp_dir) / "nested" / "model.bin").read_bytes(), b"model-data")

    def test_remote_model_filename_must_be_a_safe_relative_path(self):
        self.assertEqual(downloads._validated_model_filename("nested/model.bin"), ("nested", "model.bin"))
        for filename in (
            "../outside.bin",
            "nested/../../outside.bin",
            "/tmp/outside.bin",
            r"nested\..\outside.bin",
            r"C:\outside.bin",
            "nested//model.bin",
            "nested/./model.bin",
            "nested/model?.bin",
        ):
            with self.subTest(filename=filename), self.assertRaises(downloads.PrepareModelError):
                downloads._validated_model_filename(filename)

    def test_remote_metadata_rejects_traversal_before_download(self):
        client = FakeClient({"siblings": [{"rfilename": "weights/../../outside.bin", "size": 12}]})
        with self.assertRaises(downloads.PrepareModelError) as raised:
            downloads._get_model_files(client, "https://huggingface.co", "org/model")
        self.assertEqual(raised.exception.code, "invalid_model_path")

    def test_model_destination_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            (root / "linked").symlink_to(Path(outside_dir), target_is_directory=True)
            with self.assertRaises(downloads.PrepareModelError) as raised:
                downloads._model_file_path(root, "linked/model.bin")
            self.assertEqual(raised.exception.code, "invalid_model_path")

    def test_hub_fallback_uses_unauthenticated_endpoint_and_validated_files(self):
        info = SimpleNamespace(sha="revision", siblings=[SimpleNamespace(rfilename="weights/model.bin")])
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"HF_TOKEN": "unit-test-token"}
        ), patch("huggingface_hub.HfApi") as api_class, patch(
            "huggingface_hub.snapshot_download"
        ) as snapshot_download, patch.object(downloads, "local_model_dir", return_value=Path(temp_dir)), patch.object(
            downloads, "repository_for_model", return_value="org/model"
        ):
            api_class.return_value.model_info.return_value = info

            downloads._download_via_hf_hub("task", "model", "https://hf-mirror.com")

        api_class.assert_called_once_with(endpoint="https://hf-mirror.com", token=False)
        self.assertIs(snapshot_download.call_args.kwargs["token"], False)
        self.assertEqual(snapshot_download.call_args.kwargs["allow_patterns"], ["weights/model.bin"])

    def test_hub_fallback_rejects_unvalidated_metadata_before_download(self):
        info = SimpleNamespace(sha="revision", siblings=[SimpleNamespace(rfilename="../outside.bin")])
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "huggingface_hub.HfApi"
        ) as api_class, patch("huggingface_hub.snapshot_download") as snapshot_download, patch.object(
            downloads, "local_model_dir", return_value=Path(temp_dir)
        ), patch.object(downloads, "repository_for_model", return_value="org/model"):
            api_class.return_value.model_info.return_value = info

            with self.assertRaises(downloads.PrepareModelError):
                downloads._download_via_hf_hub("task", "model", "https://huggingface.co")

        snapshot_download.assert_not_called()


if __name__ == "__main__":
    unittest.main()

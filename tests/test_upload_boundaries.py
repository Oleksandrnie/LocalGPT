from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from app.routes import criteria as criteria_routes
from app.services.upload_limits import UploadLimitExceeded, copy_limited
from backend.apps.asr import routes as asr_routes
from backend.apps.model_transfer import import_service
from backend.apps.model_transfer import router as model_transfer_router
from backend.apps.model_transfer.manifest import BundleValidationError
from backend.apps.ocr import service as ocr_service


class UploadBoundaryTests(unittest.TestCase):
    def test_copy_limited_accepts_exact_limit_and_rejects_one_extra_byte(self):
        destination = io.BytesIO()
        self.assertEqual(copy_limited(io.BytesIO(b"1234"), destination, max_bytes=4), 4)
        self.assertEqual(destination.getvalue(), b"1234")

        destination = io.BytesIO()
        with self.assertRaises(UploadLimitExceeded):
            copy_limited(io.BytesIO(b"12345"), destination, max_bytes=4)
        self.assertEqual(destination.getvalue(), b"")

    def test_asr_oversize_upload_removes_partial_temporary_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            real_named_temp_file = tempfile.NamedTemporaryFile
            with patch.object(asr_routes, "MAX_ASR_UPLOAD_BYTES", 3), patch.object(
                asr_routes.tempfile,
                "NamedTemporaryFile",
                side_effect=lambda **kwargs: real_named_temp_file(dir=temp_dir, **kwargs),
            ):
                with self.assertRaises(HTTPException) as ctx:
                    asr_routes._store_upload_temp(UploadFile(file=io.BytesIO(b"four"), filename="voice.wav"))
            self.assertEqual(ctx.exception.status_code, 413)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_ocr_oversize_upload_removes_partial_temporary_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            real_named_temp_file = tempfile.NamedTemporaryFile
            with patch.object(ocr_service, "MAX_OCR_UPLOAD_BYTES", 3), patch.object(
                ocr_service.tempfile,
                "NamedTemporaryFile",
                side_effect=lambda **kwargs: real_named_temp_file(dir=temp_dir, **kwargs),
            ):
                with self.assertRaises(HTTPException) as ctx:
                    ocr_service._store_temp_image(UploadFile(file=io.BytesIO(b"four"), filename="image.png"))
            self.assertEqual(ctx.exception.status_code, 413)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_invalid_ocr_language_cleans_staged_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            real_named_temp_file = tempfile.NamedTemporaryFile
            upload = UploadFile(file=io.BytesIO(b"image"), filename="image.png", headers={"content-type": "image/png"})
            with patch.object(
                ocr_service.tempfile,
                "NamedTemporaryFile",
                side_effect=lambda **kwargs: real_named_temp_file(dir=temp_dir, **kwargs),
            ), patch.object(ocr_service, "_ensure_tesseract", return_value="tesseract"), patch.object(
                ocr_service,
                "_resolve_requested_langs",
                side_effect=HTTPException(422, detail={"code": "invalid_language"}),
            ):
                with self.assertRaises(HTTPException):
                    ocr_service.extract_text_from_image(upload, lang="invalid")
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_criteria_oversize_upload_returns_413(self):
        with patch.object(criteria_routes, "MAX_CRITERIA_UPLOAD_BYTES", 3):
            with self.assertRaises(HTTPException) as ctx:
                criteria_routes.parse_criteria(
                    session_id="",
                    profile_id=0,
                    google_sheet_id="",
                    google_gid="",
                    raw_text="",
                    file=UploadFile(file=io.BytesIO(b"four"), filename="criteria.csv"),
                )
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertEqual(ctx.exception.detail["code"], "criteria_upload_too_large")


class ModelTransferUploadBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversize_archive_is_removed_and_returns_413(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            upload = UploadFile(file=io.BytesIO(b"four"), filename="models.localgpt-models")
            with patch.object(model_transfer_router, "upload_storage_dir", return_value=Path(temp_dir)), patch.object(
                model_transfer_router, "MAX_BUNDLE_BYTES", 3
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await model_transfer_router.inspect_import(upload)
            self.assertEqual(ctx.exception.status_code, 413)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    async def test_oversize_manifest_is_rejected_before_reading_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "oversize.localgpt-models"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("manifest.json", b"{" + b" " * 32 + b"}")
            with patch.object(import_service, "MAX_MANIFEST_BYTES", 8):
                with self.assertRaises(BundleValidationError) as ctx:
                    import_service.inspect_archive(archive)
            self.assertEqual(ctx.exception.code, "bundle_invalid")

    async def test_excessive_zip_entry_count_is_rejected_before_zipfile_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "too-many-entries.localgpt-models"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("manifest.json", b"{}")
                bundle.writestr("payload/model.bin", b"x")
            with patch.object(import_service, "MAX_BUNDLE_FILES", 0), patch.object(
                import_service.zipfile, "ZipFile"
            ) as open_zip:
                with self.assertRaises(BundleValidationError) as ctx:
                    import_service.inspect_archive(archive)
            self.assertEqual(ctx.exception.code, "bundle_invalid")
            open_zip.assert_not_called()


if __name__ == "__main__":
    unittest.main()

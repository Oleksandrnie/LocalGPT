from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from ..services.ocr import extract_text_from_image

router = APIRouter()


@router.post("/ocr/extract")
def extract_ocr_text(
    file: UploadFile = File(...),
    language: str = Form(default=""),
):
    return extract_text_from_image(file, lang=(language or "").strip() or None)

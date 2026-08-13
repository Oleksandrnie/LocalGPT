from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db
from ..services import criteria as criteria_service

router = APIRouter()


@router.post("/criteria/parse")
def parse_criteria(
    session_id: str = Form(default=""),
    profile_id: int = Form(default=0),
    google_sheet_id: str = Form(default=""),
    google_gid: str = Form(default=""),
    raw_text: str = Form(default=""),
    file: UploadFile | None = File(default=None),
):
    sid = (session_id or "").strip()
    criteria: list[str] | None = None
    source = None
    try:
        if file is not None:
            content = file.file.read()
            if not content:
                raise ValueError("empty_file")
            suffix = Path(file.filename or "").suffix.lower()
            if suffix == ".csv":
                criteria = criteria_service.parse_csv(criteria_service.decode_bytes(content))
                source = "file:csv"
            elif suffix in {".xlsx", ".xlsm"}:
                criteria = criteria_service.parse_xlsx(content)
                source = "file:xlsx"
            else:
                raise ValueError("unsupported_file")
        elif google_sheet_id.strip():
            sheet_id, gid = criteria_service.extract_sheet_id(google_sheet_id)
            csv_text = criteria_service.load_google_sheet_csv(sheet_id, gid or (google_gid.strip() or None))
            criteria = criteria_service.parse_csv(csv_text)
            source = "google_sheets"
        elif raw_text.strip():
            criteria = criteria_service.parse_text_block(raw_text)
            source = "text"
        else:
            raise ValueError("no_source")
    except ValueError as exc:
        code = str(exc)
        if code == "unsupported_file":
            raise HTTPException(
                status_code=422,
                detail={"code": "unsupported_file", "message": "Разрешены только CSV и XLSX"},
            ) from exc
        if code == "empty_file":
            raise HTTPException(
                status_code=422,
                detail={"code": "empty_file", "message": "Файл критериев пустой"},
            ) from exc
        if code == "google_sheet_id_required":
            raise HTTPException(
                status_code=422,
                detail={"code": "google_sheet_id_required", "message": "Укажите ID таблицы Google Sheets"},
            ) from exc
        raise HTTPException(
            status_code=400,
            detail={"code": "criteria_source_missing", "message": "Не указан источник критериев"},
        ) from exc
    except RuntimeError as exc:
        if str(exc) == "openpyxl_not_available":
            raise HTTPException(
                status_code=500,
                detail={"code": "openpyxl_missing", "message": "Установите зависимость openpyxl для чтения XLSX"},
            ) from exc
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "criteria_fetch_failed", "message": "Не удалось получить или обработать источник критериев."},
        ) from exc
    if not criteria:
        raise HTTPException(
            status_code=422,
            detail={"code": "criteria_not_found", "message": "Не удалось выделить критерии"},
        )
    if sid:
        session = db.get_session(sid)
        if not session:
            raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Сессия не найдена"})
        db.save_session_criteria(sid, criteria)
        profile_id = session["profile_id"]
    elif profile_id:
        profile = db.get_profile(profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="profile_not_found")
    return {
        "criteria": criteria,
        "count": len(criteria),
        "session_id": sid or None,
        "profile_id": profile_id or None,
        "source": source,
    }

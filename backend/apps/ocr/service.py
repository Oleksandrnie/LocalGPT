from __future__ import annotations

import csv
import io
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.services.upload_limits import UploadLimitExceeded, copy_limited


_WHITESPACE_RE = re.compile(r"[ \t]+")
_WORD_RE = re.compile(r"[\wА-Яа-яЁёЇїІіЄєҐґ'-]+", re.UNICODE)
_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁёЇїІіЄєҐґ+\-']+", re.UNICODE)
_DEFAULT_LANG = (os.getenv("OCR_DEFAULT_LANG") or "eng+deu+fra+spa+rus+ukr").strip() or "eng+deu+fra+spa+rus+ukr"
_DEFAULT_PSM = (os.getenv("OCR_DEFAULT_PSM") or "6").strip() or "6"
_DEFAULT_TSV_PSM = (os.getenv("OCR_TSV_PSM") or "11").strip() or "11"
_AUTO_CROP_ENABLED = (os.getenv("OCR_AUTO_CROP") or "1").strip().lower() not in {"0", "false", "no", "off"}
_AUTO_CROP_MIN_CONF = max(0.0, float((os.getenv("OCR_AUTO_CROP_MIN_CONF") or "25").strip() or "25"))
_AUTO_CROP_PADDING = max(12, int((os.getenv("OCR_AUTO_CROP_PADDING") or "36").strip() or "36"))
MAX_OCR_UPLOAD_BYTES = 20 * 1024 * 1024
_CHAT_HEADER_RE = re.compile(r"^(?:LOCALGPT|CHATGPT|ASSISTANT|ВЫ|YOU)\b.*\d{2}\.\d{2},\s*\d{2}:\d{2}$", re.IGNORECASE)
_TIME_ONLY_RE = re.compile(r"^\d{2}\.\d{2},\s*\d{2}:\d{2}$")
_UI_NOISE_LINES = {
    "скопировать",
    "copy",
    "копировать",
    "поделиться",
    "share",
    "онлайн",
    "online",
    "закрыть",
    "настройки",
    "диалоги",
    "новый чат",
    "lan url",
}


def _normalize_text(raw: str) -> str:
    lines = []
    for line in str(raw or "").splitlines():
        clean = _WHITESPACE_RE.sub(" ", line).strip()
        lines.append(clean)
    return "\n".join(line for line in lines if line).strip()


def _coerce_int(value: str | None) -> int:
    try:
        return int(float(str(value or "0").strip()))
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: str | None) -> float:
    try:
        return float(str(value or "0").strip())
    except (TypeError, ValueError):
        return 0.0


def _meaningful_char_count(text: str) -> int:
    return sum(len(word) for word in _WORD_RE.findall(str(text or "")))


def _text_profile(text: str) -> dict[str, int]:
    raw = str(text or "").strip()
    tokens = [token for token in _TOKEN_RE.findall(raw) if token]
    alpha_count = sum(1 for char in raw if char.isalpha())
    digit_count = sum(1 for char in raw if char.isdigit())
    alpha_tokens = 0
    long_alpha_tokens = 0
    numeric_tokens = 0
    short_tokens = 0

    for token in tokens:
        token_alpha_count = sum(1 for char in token if char.isalpha())
        if len(token) <= 2:
            short_tokens += 1
        if token_alpha_count:
            alpha_tokens += 1
            if token_alpha_count >= 3:
                long_alpha_tokens += 1
        else:
            numeric_tokens += 1

    return {
        "token_count": len(tokens),
        "alpha_count": alpha_count,
        "digit_count": digit_count,
        "alpha_tokens": alpha_tokens,
        "long_alpha_tokens": long_alpha_tokens,
        "numeric_tokens": numeric_tokens,
        "short_tokens": short_tokens,
    }


def _is_low_signal_ocr_line(text: str) -> bool:
    profile = _text_profile(text)
    if profile["token_count"] <= 0:
        return True
    if profile["long_alpha_tokens"] > 0:
        return False
    if profile["alpha_count"] <= 1 and profile["digit_count"] >= 1:
        return True
    if profile["digit_count"] >= 2 and profile["alpha_count"] <= 2:
        return True
    if profile["token_count"] >= 2 and profile["short_tokens"] >= max(2, profile["token_count"] - 1) and profile["alpha_count"] <= 2:
        return True
    if profile["digit_count"] >= 1 and profile["short_tokens"] >= max(4, profile["token_count"] - 1):
        return True
    if profile["numeric_tokens"] >= max(2, profile["token_count"] // 2) and profile["digit_count"] > profile["alpha_count"]:
        return True
    if profile["token_count"] >= 4 and profile["long_alpha_tokens"] == 0 and profile["digit_count"] >= profile["alpha_count"]:
        return True
    return False


def _is_ui_noise_line(text: str) -> bool:
    clean = str(text or "").strip()
    if not clean:
        return True

    lowered = clean.lower()
    if lowered in _UI_NOISE_LINES:
        return True
    if _TIME_ONLY_RE.match(clean):
        return True
    if _CHAT_HEADER_RE.match(clean):
        return True
    if lowered.startswith("модель "):
        return True
    if lowered.startswith("model "):
        return True
    return False


def _drop_ui_noise(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    rich_text_detected = any(
        _text_profile(line)["long_alpha_tokens"] > 0 or _meaningful_char_count(line) >= 10
        for line in lines
    )

    cleaned: list[str] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        if lowered in _UI_NOISE_LINES:
            continue
        if _TIME_ONLY_RE.match(line):
            continue
        if index == 0 and _CHAT_HEADER_RE.match(line) and len(lines) > 2:
            continue
        if lowered.startswith("модель ") or lowered.startswith("model "):
            continue
        if _meaningful_char_count(line) <= 1 and len(line) <= 3:
            continue
        if rich_text_detected and _is_low_signal_ocr_line(line):
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _list_tesseract_languages(tesseract_bin: str) -> set[str]:
    try:
        result = subprocess.run(
            [tesseract_bin, "--list-langs"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return set()

    if result.returncode != 0:
        return set()

    return {
        line.strip()
        for line in (result.stdout or "").splitlines()
        if line.strip() and not line.lower().startswith("list of available languages")
    }


def _resolve_requested_langs(tesseract_bin: str, selected_lang: str) -> str:
    available = _list_tesseract_languages(tesseract_bin)
    if not available:
        return selected_lang

    requested = [item.strip() for item in selected_lang.split("+") if item.strip()]
    supported = [item for item in requested if item in available]
    if supported:
        return "+".join(supported)
    if "eng" in available:
        return "eng"
    return selected_lang


def _run_tesseract(
    tesseract_bin: str,
    image_path: str,
    *,
    lang: str | None,
    psm: str,
    mode: str = "text",
) -> subprocess.CompletedProcess[str]:
    command = [tesseract_bin, image_path, "stdout"]
    if lang:
        command.extend(["-l", lang])
    command.extend(["--psm", str(psm or _DEFAULT_PSM)])
    if mode == "tsv":
        command.append("tsv")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_tsv_rows(raw_tsv: str) -> list[dict[str, int | float | str]]:
    rows: list[dict[str, int | float | str]] = []
    if not raw_tsv.strip():
        return rows

    reader = csv.DictReader(io.StringIO(raw_tsv), delimiter="\t")
    for row in reader:
        text = (row.get("text") or "").strip()
        left = _coerce_int(row.get("left"))
        top = _coerce_int(row.get("top"))
        width = _coerce_int(row.get("width"))
        height = _coerce_int(row.get("height"))
        rows.append(
            {
                "level": _coerce_int(row.get("level")),
                "block_num": _coerce_int(row.get("block_num")),
                "par_num": _coerce_int(row.get("par_num")),
                "line_num": _coerce_int(row.get("line_num")),
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "right": left + width,
                "bottom": top + height,
                "conf": _coerce_float(row.get("conf")),
                "text": text,
            }
        )
    return rows


def _extract_page_size(rows: list[dict[str, int | float | str]]) -> tuple[int, int]:
    for row in rows:
        if int(row.get("level") or 0) == 1:
            width = int(row.get("width") or 0)
            height = int(row.get("height") or 0)
            if width > 0 and height > 0:
                return width, height

    width = max((int(row.get("right") or 0) for row in rows), default=0)
    height = max((int(row.get("bottom") or 0) for row in rows), default=0)
    return width, height


def _build_candidate_lines(
    rows: list[dict[str, int | float | str]],
    *,
    min_conf: float,
) -> list[dict[str, int | float | str]]:
    groups: dict[tuple[int, int, int], list[dict[str, int | float | str]]] = {}
    order: list[tuple[int, int, int]] = []

    for row in rows:
        if int(row.get("level") or 0) != 5:
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        conf = float(row.get("conf") or 0.0)
        if conf >= 0 and conf < min_conf:
            continue

        key = (
            int(row.get("block_num") or 0),
            int(row.get("par_num") or 0),
            int(row.get("line_num") or 0),
        )
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    lines: list[dict[str, int | float | str]] = []
    for key in order:
        words = sorted(groups[key], key=lambda item: (int(item["left"]), int(item["top"])))
        text = " ".join(str(item.get("text") or "").strip() for item in words).strip()
        if not text or _is_ui_noise_line(text):
            continue
        if _is_low_signal_ocr_line(text):
            continue

        left = min(int(item["left"]) for item in words)
        top = min(int(item["top"]) for item in words)
        right = max(int(item["right"]) for item in words)
        bottom = max(int(item["bottom"]) for item in words)
        confidences = [float(item["conf"]) for item in words if float(item["conf"]) >= 0]
        profile = _text_profile(text)
        lines.append(
            {
                "text": text,
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": right - left,
                "height": bottom - top,
                "char_count": _meaningful_char_count(text),
                "alpha_count": profile["alpha_count"],
                "digit_count": profile["digit_count"],
                "token_count": profile["token_count"],
                "long_alpha_tokens": profile["long_alpha_tokens"],
                "mean_conf": (sum(confidences) / len(confidences)) if confidences else 0.0,
            }
        )

    return lines


def _cluster_score(
    cluster: list[dict[str, int | float | str]],
    *,
    page_width: int,
    page_height: int,
) -> float:
    if not cluster:
        return -1.0

    left = min(int(item["left"]) for item in cluster)
    top = min(int(item["top"]) for item in cluster)
    right = max(int(item["right"]) for item in cluster)
    bottom = max(int(item["bottom"]) for item in cluster)
    width = max(1, right - left)
    height = max(1, bottom - top)
    line_count = len(cluster)
    char_count = sum(int(item["char_count"]) for item in cluster)
    alpha_count = sum(int(item.get("alpha_count") or 0) for item in cluster)
    digit_count = sum(int(item.get("digit_count") or 0) for item in cluster)
    word_like_tokens = sum(int(item.get("long_alpha_tokens") or 0) for item in cluster)

    width_ratio = width / max(page_width, 1)
    height_ratio = height / max(page_height, 1)
    top_ratio = top / max(page_height, 1)

    score = float(char_count)
    score += float(alpha_count * 1.8)
    score += float(word_like_tokens * 34)
    score += float(line_count * 14)
    score += float(width_ratio * 150)
    score -= float(digit_count * 0.45)

    if word_like_tokens <= 0:
        score *= 0.2
    if alpha_count < 8:
        score *= 0.35
    if width_ratio < 0.22:
        score *= 0.45
    elif width_ratio < 0.34:
        score *= 0.78
    if height_ratio < 0.04:
        score *= 0.75
    if top_ratio < 0.07:
        score *= 0.85

    return score


def _select_auto_crop_region(raw_tsv: str) -> tuple[int, int, int, int] | None:
    rows = _parse_tsv_rows(raw_tsv)
    if not rows:
        return None

    page_width, page_height = _extract_page_size(rows)
    if page_width <= 0 or page_height <= 0:
        return None

    lines = _build_candidate_lines(rows, min_conf=_AUTO_CROP_MIN_CONF)
    if not lines:
        lines = _build_candidate_lines(rows, min_conf=0.0)
    if len(lines) < 2:
        return None

    lines = sorted(lines, key=lambda item: (int(item["top"]), int(item["left"])))
    median_height = statistics.median(max(1, int(item["height"])) for item in lines)
    gap_threshold = max(int(median_height * 1.8), 28)

    clusters: list[list[dict[str, int | float | str]]] = []
    current: list[dict[str, int | float | str]] = []
    previous_bottom = 0

    for line in lines:
        top = int(line["top"])
        if not current:
            current = [line]
            previous_bottom = int(line["bottom"])
            continue

        if top - previous_bottom <= gap_threshold:
            current.append(line)
            previous_bottom = max(previous_bottom, int(line["bottom"]))
            continue

        clusters.append(current)
        current = [line]
        previous_bottom = int(line["bottom"])

    if current:
        clusters.append(current)

    merged_clusters: list[list[dict[str, int | float | str]]] = []
    merge_gap_threshold = max(gap_threshold * 3, 140)

    for cluster in clusters:
        if not merged_clusters:
            merged_clusters.append(cluster)
            continue

        previous = merged_clusters[-1]
        prev_left = min(int(item["left"]) for item in previous)
        prev_right = max(int(item["right"]) for item in previous)
        prev_bottom = max(int(item["bottom"]) for item in previous)
        cluster_left = min(int(item["left"]) for item in cluster)
        cluster_right = max(int(item["right"]) for item in cluster)
        cluster_top = min(int(item["top"]) for item in cluster)

        gap = cluster_top - prev_bottom
        left_aligned = abs(cluster_left - prev_left) <= max(60, int(page_width * 0.05))
        right_aligned = abs(cluster_right - prev_right) <= max(120, int(page_width * 0.08))
        center_aligned = abs(((cluster_left + cluster_right) / 2) - ((prev_left + prev_right) / 2)) <= max(
            100,
            int(page_width * 0.08),
        )

        if gap <= merge_gap_threshold and (left_aligned or right_aligned or center_aligned):
            previous.extend(cluster)
            continue

        merged_clusters.append(cluster)

    clusters = merged_clusters

    best_cluster: list[dict[str, int | float | str]] | None = None
    best_score = -1.0

    for cluster in clusters:
        char_count = sum(int(item["char_count"]) for item in cluster)
        if char_count < 18:
            continue

        score = _cluster_score(cluster, page_width=page_width, page_height=page_height)
        if score > best_score:
            best_score = score
            best_cluster = cluster

    if not best_cluster:
        return None

    left = min(int(item["left"]) for item in best_cluster)
    top = min(int(item["top"]) for item in best_cluster)
    right = max(int(item["right"]) for item in best_cluster)
    bottom = max(int(item["bottom"]) for item in best_cluster)

    padding = min(_AUTO_CROP_PADDING, max(12, int(min(page_width, page_height) * 0.04)))
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(page_width, right + padding)
    bottom = min(page_height, bottom + padding)

    crop_width = right - left
    crop_height = bottom - top
    if crop_width <= 0 or crop_height <= 0:
        return None
    if crop_width * crop_height >= int(page_width * page_height * 0.94):
        return None

    return left, top, crop_width, crop_height


def _crop_image_to_region(source_path: str, bounds: tuple[int, int, int, int]) -> str | None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return None

    left, top, width, height = bounds
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
        output_path = tmp_file.name

    crop_filter = f"crop={width}:{height}:{left}:{top}"
    result = subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-loglevel",
            "error",
            "-i",
            source_path,
            "-vf",
            crop_filter,
            "-frames:v",
            "1",
            output_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        try:
            os.remove(output_path)
        except OSError:
            pass
        return None
    return output_path


def _text_quality_score(text: str) -> int:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return 0

    score = sum(_meaningful_char_count(line) for line in lines)
    score += str(text or "").count(".") * 2
    score += str(text or "").count("?") * 3
    score += str(text or "").count("!") * 2
    score += str(text or "").count('"') * 1
    return score


def _prefer_cropped_text(base_text: str, cropped_text: str) -> bool:
    if not cropped_text:
        return False
    if not base_text:
        return True

    base_score = _text_quality_score(base_text)
    cropped_score = _text_quality_score(cropped_text)
    if cropped_score >= int(base_score * 0.8):
        return True
    return len(cropped_text) >= int(len(base_text) * 0.7)


def _ensure_tesseract() -> str:
    binary = shutil.which("tesseract")
    if not binary:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ocr_engine_missing",
                "message": "Локальный OCR недоступен: tesseract не установлен.",
            },
        )
    return binary


def _store_temp_image(file: UploadFile) -> tuple[str, str]:
    filename = Path(file.filename or "image").name
    suffix = Path(filename).suffix or ".png"
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            temp_path = tmp_file.name
            copy_limited(file.file, tmp_file, max_bytes=MAX_OCR_UPLOAD_BYTES)
    except Exception as exc:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        if isinstance(exc, UploadLimitExceeded):
            raise HTTPException(
                status_code=413,
                detail={"code": "ocr_upload_too_large", "max_bytes": MAX_OCR_UPLOAD_BYTES},
            ) from exc
        raise
    assert temp_path is not None
    return temp_path, filename


def extract_text_from_image(file: UploadFile, *, lang: str | None = None) -> dict[str, str]:
    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ocr_invalid_file_type",
                "message": "OCR поддерживает только изображения.",
            },
        )

    tesseract_bin = _ensure_tesseract()
    temp_path, filename = _store_temp_image(file)
    selected_lang = (lang or _DEFAULT_LANG).strip() or _DEFAULT_LANG
    engine = "tesseract"
    cropped_temp_path: str | None = None

    try:
        resolved_lang = _resolve_requested_langs(tesseract_bin, selected_lang)
        primary = _run_tesseract(
            tesseract_bin,
            temp_path,
            lang=resolved_lang,
            psm=_DEFAULT_PSM,
        )
        stdout = (primary.stdout or "").strip()
        stderr = (primary.stderr or "").strip()

        if primary.returncode != 0 and resolved_lang:
            fallback = _run_tesseract(
                tesseract_bin,
                temp_path,
                lang=None,
                psm=_DEFAULT_PSM,
            )
            if fallback.returncode == 0:
                stdout = (fallback.stdout or "").strip()
                stderr = (fallback.stderr or "").strip()
                primary = fallback

        text = _drop_ui_noise(_normalize_text(stdout))

        if _AUTO_CROP_ENABLED:
            detection = _run_tesseract(
                tesseract_bin,
                temp_path,
                lang=resolved_lang,
                psm=_DEFAULT_TSV_PSM,
                mode="tsv",
            )
            if detection.returncode != 0 and resolved_lang:
                detection = _run_tesseract(
                    tesseract_bin,
                    temp_path,
                    lang=None,
                    psm=_DEFAULT_TSV_PSM,
                    mode="tsv",
                )

            crop_region = _select_auto_crop_region(detection.stdout or "")
            if crop_region:
                cropped_temp_path = _crop_image_to_region(temp_path, crop_region)
                if cropped_temp_path:
                    cropped = _run_tesseract(
                        tesseract_bin,
                        cropped_temp_path,
                        lang=resolved_lang,
                        psm=_DEFAULT_PSM,
                    )
                    if cropped.returncode != 0 and resolved_lang:
                        cropped = _run_tesseract(
                            tesseract_bin,
                            cropped_temp_path,
                            lang=None,
                            psm=_DEFAULT_PSM,
                        )
                    cropped_text = _drop_ui_noise(_normalize_text(cropped.stdout or ""))
                    if _prefer_cropped_text(text, cropped_text):
                        text = cropped_text
                        engine = "tesseract+autocrop"

        if primary.returncode != 0:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "ocr_failed",
                    "message": stderr or "Локальный OCR завершился ошибкой.",
                },
            )
        if not text:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "ocr_empty_result",
                    "message": "OCR не нашёл текст на изображении.",
                },
            )

        return {
            "text": text,
            "file_name": filename,
            "engine": engine,
            "language": resolved_lang,
        }
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        if cropped_temp_path:
            try:
                os.remove(cropped_temp_path)
            except OSError:
                pass

from __future__ import annotations

from typing import Any


def build_timeline(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Объединяет соседние сегменты одного говорящего в таймлайн."""
    timeline: list[dict[str, Any]] = []
    if not segments:
        return timeline

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start))
        speaker = (segment.get("speaker") or "unknown").strip().lower() or "unknown"

        if timeline and timeline[-1]["speaker"] == speaker and start <= timeline[-1]["end"] + 0.6:
            timeline[-1]["end"] = max(timeline[-1]["end"], end)
            timeline[-1]["text"] = (timeline[-1]["text"] + " " + text).strip()
        else:
            timeline.append(
                {
                    "speaker": speaker,
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )

    return timeline

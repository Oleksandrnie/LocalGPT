from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path


def probe_wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        if frame_rate <= 0:
            return 0.0
        duration = wav_file.getnframes() / float(frame_rate)
    return round(duration, 3)


def apply_speed_to_wav(input_path: Path, output_path: Path, speed: float) -> float:
    if not input_path.exists():
        raise FileNotFoundError("source_wav_not_found")

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg_missing")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")

    try:
        if abs(speed - 1.0) < 1e-6:
            shutil.copyfile(input_path, temp_output)
        else:
            cmd = [
                ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(input_path),
                "-filter:a",
                f"atempo={speed:.2f}",
                "-acodec",
                "pcm_s16le",
                str(temp_output),
            ]
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                error_message = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(error_message or "ffmpeg_failed")

        temp_output.replace(output_path)
        return probe_wav_duration(output_path)
    except Exception:
        try:
            temp_output.unlink()
        except OSError:
            pass
        raise

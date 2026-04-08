from __future__ import annotations

import subprocess
from pathlib import Path


def capture_positions() -> list[float]:
    return [index / 10 for index in range(1, 10)]


def probe_duration(ffprobe_bin: str, video_path: Path, timeout: float = 30.0) -> float:
    try:
        result = subprocess.run(
            [ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(f"ffprobe_error path={video_path} stderr={stderr}") from exc
    return float(result.stdout.strip())


def capture_frames(
    ffmpeg_bin: str,
    video_path: Path,
    duration: float,
    output_dir: Path,
    image_format: str,
    filename_prefix: str,
    timeout: float = 30.0,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for idx, ratio in enumerate(capture_positions(), start=1):
        timestamp = duration * ratio
        output = output_dir / f"{filename_prefix}_{idx:02d}.{image_format}"
        subprocess.run(
            [ffmpeg_bin, "-y", "-ss", str(timestamp), "-i", str(video_path), "-frames:v", "1", str(output)],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        files.append(output)
    return files

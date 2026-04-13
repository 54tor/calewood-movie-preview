from __future__ import annotations

import logging
import subprocess
from pathlib import Path

LOG = logging.getLogger("calewood_movie_preview.media")


def _stderr_tail(stderr: str, max_chars: int = 1600) -> str:
    cleaned = " ".join(stderr.strip().split())
    if len(cleaned) <= max_chars:
        return cleaned
    return f"...{cleaned[-max_chars:]}"


def evenly_spaced_positions(count: int) -> list[float]:
    if count <= 0:
        return []
    return [index / (count + 1) for index in range(1, count + 1)]


def capture_positions() -> list[float]:
    return evenly_spaced_positions(9)


def midpoint_positions(count: int) -> list[float]:
    return [0.5] * count


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
        stderr = _stderr_tail(exc.stderr or "")
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
    return capture_frames_at_positions(
        ffmpeg_bin,
        video_path,
        duration,
        output_dir,
        image_format,
        filename_prefix,
        capture_positions(),
        timeout,
    )


def capture_frames_at_positions(
    ffmpeg_bin: str,
    video_path: Path,
    duration: float,
    output_dir: Path,
    image_format: str,
    filename_prefix: str,
    positions: list[float],
    timeout: float = 30.0,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for idx, ratio in enumerate(positions, start=1):
        timestamp = duration * ratio
        output = output_dir / f"{filename_prefix}_{idx:02d}.{image_format}"
        _capture_single_frame_with_fallback(ffmpeg_bin, video_path, timestamp, output, timeout)
        files.append(output)
    return files


def _capture_single_frame_with_fallback(
    ffmpeg_bin: str,
    video_path: Path,
    timestamp: float,
    output: Path,
    timeout: float,
) -> None:
    attempts = _build_ffmpeg_attempts(ffmpeg_bin, video_path, timestamp, output)
    errors: list[str] = []
    for index, cmd in enumerate(attempts, start=1):
        output.unlink(missing_ok=True)
        result = subprocess.run(cmd, check=False, capture_output=True, timeout=timeout)
        if result.returncode == 0 and output.exists() and output.stat().st_size > 0:
            return
        if output.exists() and output.stat().st_size > 0:
            LOG.warning(
                "ffmpeg_nonzero_but_output_present path=%s attempt=%s returncode=%s",
                str(video_path),
                index,
                result.returncode,
            )
            return
        stderr_tail = _stderr_tail((result.stderr or b"").decode("utf-8", errors="replace"))
        errors.append(f"attempt={index} rc={result.returncode} stderr={stderr_tail}")
    raise RuntimeError(f"ffmpeg_error path={video_path} {' | '.join(errors)}")


def _build_ffmpeg_attempts(ffmpeg_bin: str, video_path: Path, timestamp: float, output: Path) -> list[list[str]]:
    base_output = ["-frames:v", "1", "-update", "1", str(output)]
    tolerant = ["-fflags", "+discardcorrupt", "-err_detect", "ignore_err"]
    return [
        [ffmpeg_bin, "-y", "-ss", str(timestamp), "-i", str(video_path), *base_output],
        [ffmpeg_bin, "-y", *tolerant, "-ss", str(timestamp), "-i", str(video_path), *base_output],
        [ffmpeg_bin, "-y", "-i", str(video_path), "-ss", str(timestamp), *base_output],
        [ffmpeg_bin, "-y", *tolerant, "-i", str(video_path), "-ss", str(timestamp), *base_output],
    ]

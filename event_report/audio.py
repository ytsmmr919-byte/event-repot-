"""音声の取り出しと変換。

ffmpegはimageio-ffmpegに同梱されたものを使うので、各PCへの個別インストールは不要。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


class AudioExtractionError(RuntimeError):
    pass


def extract_audio(video_path: Path, dest_path: Path) -> Path:
    """動画から文字起こし用のモノラル16kHz AAC音声を書き出す(1時間で約20MB)。"""
    return _run_ffmpeg(video_path, dest_path, ["-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "48k"])


def convert_to_mp3(source_path: Path, dest_path: Path) -> Path:
    """PlaudなどにそのままアップロードできるMP3にする(モノラル96kbps、1時間で約43MB)。"""
    return _run_ffmpeg(source_path, dest_path, ["-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k"])


def _run_ffmpeg(source_path: Path, dest_path: Path, audio_options: list[str]) -> Path:
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source_path),
        "-vn", *audio_options,
        str(dest_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        dest_path.unlink(missing_ok=True)
        raise AudioExtractionError("動画から音声を取り出せませんでした。音声の入っていない動画か、壊れたファイルの可能性があります。")
    return dest_path

"""動画から文字起こし用の音声を取り出す。

ffmpegはimageio-ffmpegに同梱されたものを使うので、各PCへの個別インストールは不要。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg


class AudioExtractionError(RuntimeError):
    pass


def extract_audio(video_path: Path, dest_path: Path) -> Path:
    """動画からモノラル16kHzのAAC音声を書き出す。

    1時間で約20MBになり、動画をそのまま送るより大幅にアップロードが軽くなる。
    """
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "48k",
        str(dest_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise AudioExtractionError("動画から音声を取り出せませんでした。音声の入っていない動画か、壊れたファイルの可能性があります。")
    return dest_path

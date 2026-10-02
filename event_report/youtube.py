"""YouTubeのURLの確認、タイトル取得、音声のダウンロード。"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import deno
import httpx
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from . import audio

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
OEMBED_URL = "https://www.youtube.com/oembed"
FORBIDDEN_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
MAX_NAME_LENGTH = 60


class YouTubeError(RuntimeError):
    pass


def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and parsed.hostname in YOUTUBE_HOSTS


def fetch_title(url: str) -> str:
    """動画のタイトルを取得する。非公開・削除済みの動画はここで分かる(文字起こしの課金前に止められる)。"""
    try:
        response = httpx.get(OEMBED_URL, params={"url": url, "format": "json"}, timeout=15, follow_redirects=True)
    except httpx.HTTPError as e:
        raise YouTubeError(f"YouTubeに接続できませんでした。インターネット接続を確認してください。({e})") from e
    if response.status_code in (401, 403):
        raise YouTubeError("この動画は「非公開」のため読み込めません。YouTubeで「限定公開」か「公開」に変更してください。")
    if response.status_code == 404 or response.status_code == 400:
        raise YouTubeError("動画が見つかりません。URLが正しいか、動画が削除されていないか確認してください。")
    response.raise_for_status()
    return response.json().get("title", "")


def to_folder_name(title: str) -> str:
    name = FORBIDDEN_FILENAME_CHARS.sub("_", title).strip(" .")
    return name[:MAX_NAME_LENGTH].strip() or "YouTube動画"


# yt-dlpのlive_status: 配信前・配信中・アーカイブ処理中は、まだ全編を取得できない
NOT_READY_STATUSES = {
    "is_upcoming": "この配信はまだ始まっていません。",
    "is_live": "この動画は配信中です。配信が終わってから実行してください。",
    "post_live": "配信のアーカイブをYouTubeが準備中です。しばらく(数十分〜)待ってから実行してください。",
}


def download_audio(url: str, dest_dir: Path) -> Path:
    """YouTubeの動画から音声だけを取り出し、「タイトル.mp3」としてdest_dirに保存する。"""
    with tempfile.TemporaryDirectory() as tmp:
        options = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(tmp) / "source.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _SilentLogger(),  # 英語のエラーは表示せず、_describe_download_errorで日本語にする
            "progress_hooks": [_print_progress],
            # YouTubeの取得にはJavaScript実行環境が必要。PyPI版のDenoを同梱して使う
            "js_runtimes": {"deno": {"path": deno.find_deno_bin()}},
        }
        with YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if info.get("live_status") in NOT_READY_STATUSES:
                    raise YouTubeError(NOT_READY_STATUSES[info["live_status"]])
                info = ydl.process_ie_result(info, download=True)
            except DownloadError as e:
                raise YouTubeError(_describe_download_error(str(e))) from e
            downloaded = Path(info["requested_downloads"][0]["filepath"])
        print("\n  MP3に変換中…")
        dest_path = _unique_path(dest_dir / f"{to_folder_name(info.get('title') or '')}.mp3")
        return audio.convert_to_mp3(downloaded, dest_path)


class _SilentLogger:
    def debug(self, msg: str) -> None:
        pass

    info = warning = error = debug


def _print_progress(status: dict) -> None:
    if status.get("status") != "downloading":
        return
    total = status.get("total_bytes") or status.get("total_bytes_estimate")
    done = status.get("downloaded_bytes") or 0
    if total:
        print(f"\r  ダウンロード中… {done * 100 // total}%", end="", flush=True)


def _describe_download_error(message: str) -> str:
    if "Private video" in message:
        return "この動画は「非公開」のため取得できません。YouTubeで「限定公開」か「公開」に変更してください。"
    if "Sign in to confirm" in message or "not a bot" in message:
        return "YouTubeから一時的にアクセスを制限されました。時間をおくか、別のネットワーク(会社/自宅)で試してください。"
    if "Video unavailable" in message or "removed" in message:
        return "動画が見つかりません。URLが正しいか、動画が削除されていないか確認してください。"
    if any(s in message for s in ("Unable to connect", "Tunnel connection failed", "getaddrinfo failed", "timed out", "Failed to resolve")):
        return "YouTubeに接続できませんでした。インターネット接続を確認してください。"
    detail = message.split("; please report this issue")[0]
    return f"YouTubeから音声を取得できませんでした。({detail})"


def _unique_path(path: Path) -> Path:
    """同名ファイルがあれば「名前 (2).mp3」のようにずらす。"""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate

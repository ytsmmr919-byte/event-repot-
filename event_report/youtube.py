"""YouTubeのURLの確認とタイトル取得。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

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

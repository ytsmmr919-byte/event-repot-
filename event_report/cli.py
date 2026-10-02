"""コマンドの入口。通常は各「…_Windows.bat」「…_Mac.command」のダブルクリックから呼ばれる。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

import anthropic
import httpx
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError

from . import config, youtube
from .pipeline import find_videos, process_url, process_video

Job = tuple[str, Callable[[], "Path | None"]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="event_report",
        description="動画を文字起こしし、「レポート出力」にイベントレポートを作成します。"
                    "引数なしで実行すると「動画フォルダ」の動画を処理します。",
    )
    parser.add_argument("--setup", action="store_true", help="初回セットアップ(フォルダ作成とAPIキーの登録)")
    parser.add_argument("--video", type=Path, help="指定した動画1本だけを処理する")
    parser.add_argument("--youtube", action="store_true", help="YouTubeのURLを対話的に入力して処理する")
    parser.add_argument("--youtube-audio", action="store_true", help="YouTubeのURLを対話的に入力し、音声(MP3)だけを保存する")
    parser.add_argument("--audio-url", help="指定したYouTubeのURLから音声(MP3)だけを保存する")
    parser.add_argument("--url", help="指定したYouTubeのURLを処理する")
    parser.add_argument("--name", help="--url と一緒に使う: レポートの名前(省略時はYouTubeのタイトル)")
    parser.add_argument("--force", action="store_true", help="作成済みのレポートも作り直す(文字起こしは再利用)")
    return parser


def ensure_folders() -> None:
    config.VIDEO_DIR.mkdir(exist_ok=True)
    config.REPORT_DIR.mkdir(exist_ok=True)
    config.AUDIO_DIR.mkdir(exist_ok=True)


def load_settings_interactively() -> config.Settings:
    try:
        return config.load_settings()
    except config.MissingKeysError as e:
        if not sys.stdin.isatty():
            raise
        print("APIキーが未登録です。管理者から共有されたキーを入力してください。")
        config.ask_and_save_keys(e.missing)
        return config.load_settings()


def describe_error(error: Exception) -> str:
    if isinstance(error, anthropic.AuthenticationError):
        return "Anthropic のAPIキーが正しくありません。.env の ANTHROPIC_API_KEY を確認してください。"
    if isinstance(error, anthropic.RateLimitError):
        return "Anthropic APIの利用上限に達しました。しばらく待ってから再実行してください。"
    if isinstance(error, anthropic.APIConnectionError):
        return "Anthropic APIに接続できませんでした。インターネット接続を確認してください。"
    if isinstance(error, anthropic.APIStatusError):
        return f"Anthropic APIでエラーが発生しました(status {error.status_code}): {error.message}"
    if isinstance(error, ElevenLabsApiError):
        if error.status_code == 401:
            return f"ElevenLabs のAPIキーが正しくないか、利用枠が不足しています。.env の ELEVENLABS_API_KEY と契約プランを確認してください。\n{error.body}"
        return f"ElevenLabs APIでエラーが発生しました(status {error.status_code}): {error.body}"
    if isinstance(error, youtube.YouTubeError):
        return str(error)
    if isinstance(error, httpx.HTTPError):
        return f"文字起こしサービスに接続できませんでした。インターネット接続を確認してください。({error})"
    return str(error)


def run_jobs(jobs: list[Job]) -> int:
    """1件失敗しても残りは処理を続ける。"""
    failures = 0
    for index, (label, job) in enumerate(jobs, start=1):
        print(f"\n({index}/{len(jobs)}) {label}")
        try:
            report_path = job()
        except Exception as e:
            failures += 1
            print(f"  × 失敗しました: {describe_error(e)}")
            continue
        if report_path:
            print(f"  ○ 完成: {report_path.relative_to(config.ROOT)}")

    print(f"\n完了しました(失敗 {failures} 件)。" if failures else "\nすべて完了しました。")
    return 1 if failures else 0


def video_jobs(settings: config.Settings, video: Path | None, force: bool) -> list[Job]:
    videos = [video] if video else find_videos(config.VIDEO_DIR)
    return [
        (v.name, lambda v=v: process_video(v, settings, config.REPORT_DIR, config.WRITING_GUIDE_PATH, force=force))
        for v in videos
    ]


def save_youtube_audio(urls: list[str]) -> int:
    """APIキー不要。URLの音声をMP3にして音声フォルダへ保存する。"""
    jobs: list[Job] = []
    for url in urls:
        if not youtube.is_youtube_url(url):
            print(f"× YouTubeのURLではないためスキップします: {url}")
            continue
        jobs.append((url, lambda url=url: youtube.download_audio(url, config.AUDIO_DIR)))
    if not jobs:
        print("\n処理できるURLがありませんでした。上のメッセージを確認してください。")
        return 1
    return run_jobs(jobs)


def ask_urls() -> list[str]:
    print("YouTubeの動画URLを貼り付けてEnterを押してください。")
    print("(複数ある場合は1行に1つずつ。全部入力したら、何も入力せずにEnter)")
    urls = []
    while url := input("URL: ").strip():
        urls.append(url)
    return urls


def youtube_jobs(settings: config.Settings, urls: list[str], name: str | None, interactive: bool, force: bool) -> list[Job]:
    """文字起こしを始める前に、全URLの確認と名前決めを済ませる(途中で入力待ちにならないように)。"""
    jobs: list[Job] = []
    for url in urls:
        if not youtube.is_youtube_url(url):
            print(f"× YouTubeのURLではないためスキップします: {url}")
            continue
        try:
            title = youtube.fetch_title(url)
        except youtube.YouTubeError as e:
            print(f"× {url}\n  {e}")
            continue
        report_name = youtube.to_folder_name(name or title)
        if interactive:
            print(f"\n「{title}」")
            entered = input(f"  レポートの名前(そのままEnterで「{report_name}」): ").strip()
            report_name = youtube.to_folder_name(entered) if entered else report_name
        jobs.append((
            f"{report_name}  ({url})",
            lambda url=url, report_name=report_name: process_url(
                url, report_name, settings, config.REPORT_DIR, config.WRITING_GUIDE_PATH, config.VIDEO_DIR, force=force,
            ),
        ))
    return jobs


def run(args: argparse.Namespace) -> int:
    ensure_folders()
    if args.youtube_audio or args.audio_url:
        urls = [args.audio_url] if args.audio_url else ask_urls()
        if not urls:
            print("URLが入力されなかったので終了します。")
            return 0
        return save_youtube_audio(urls)

    settings = load_settings_interactively()

    if args.youtube or args.url:
        interactive = not args.url
        urls = [args.url] if args.url else ask_urls()
        if not urls:
            print("URLが入力されなかったので終了します。")
            return 0
        jobs = youtube_jobs(settings, urls, args.name, interactive, args.force)
        if not jobs:
            print("\n処理できるURLがありませんでした。上のメッセージを確認してください。")
            return 1
    else:
        jobs = video_jobs(settings, args.video, args.force)
        if not jobs:
            print(f"「{config.VIDEO_DIR.name}」に動画がありません。動画を入れてから、もう一度実行してください。")
            return 0
    return run_jobs(jobs)


def setup() -> int:
    ensure_folders()
    try:
        config.load_settings()
    except config.MissingKeysError as e:
        print("レポート作成機能で使うAPIキーを登録します。")
        print("(YouTubeから音声を保存するだけなら不要です。その場合は何も入力せずにEnter)")
        config.ask_and_save_keys(e.missing, allow_skip=True)
    print("\nセットアップが完了しました。")
    print("YouTubeの音声を保存するには「4_YouTubeから音声を保存」をダブルクリックしてください。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return setup() if args.setup else run(args)
    except config.MissingKeysError as e:
        print(f"{e}\n「初回セットアップ」を実行するか、.env にキーを記入してください。")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n中断しました。")
        return 130

"""コマンドの入口。通常は「レポート作成」のダブルクリックから引数なしで呼ばれる。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic
import httpx
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError

from . import config
from .pipeline import find_videos, process_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="event_report",
        description="「動画フォルダ」の動画を文字起こしし、「レポート出力」にイベントレポートを作成します。",
    )
    parser.add_argument("--setup", action="store_true", help="初回セットアップ(フォルダ作成とAPIキーの登録)")
    parser.add_argument("--video", type=Path, help="指定した動画1本だけを処理する")
    parser.add_argument("--force", action="store_true", help="作成済みのレポートも作り直す(文字起こしは再利用)")
    return parser


def ensure_folders() -> None:
    config.VIDEO_DIR.mkdir(exist_ok=True)
    config.REPORT_DIR.mkdir(exist_ok=True)


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
    if isinstance(error, httpx.HTTPError):
        return f"文字起こしサービスに接続できませんでした。インターネット接続を確認してください。({error})"
    return str(error)


def run(video: Path | None, force: bool) -> int:
    ensure_folders()
    settings = load_settings_interactively()

    videos = [video] if video else find_videos(config.VIDEO_DIR)
    if not videos:
        print(f"「{config.VIDEO_DIR.name}」に動画がありません。動画を入れてから、もう一度実行してください。")
        return 0

    failures = 0
    for index, video_path in enumerate(videos, start=1):
        print(f"\n({index}/{len(videos)}) {video_path.name}")
        try:
            report_path = process_video(video_path, settings, config.REPORT_DIR, config.WRITING_GUIDE_PATH, force=force)
        except Exception as e:  # 1本失敗しても残りの動画は処理を続ける
            failures += 1
            print(f"  × 失敗しました: {describe_error(e)}")
            continue
        if report_path:
            print(f"  ○ 完成: {report_path.relative_to(config.ROOT)}")

    print(f"\n完了しました(失敗 {failures} 件)。" if failures else "\nすべて完了しました。")
    return 1 if failures else 0


def setup() -> int:
    ensure_folders()
    try:
        config.load_settings()
    except config.MissingKeysError as e:
        config.ask_and_save_keys(e.missing)
    print("\nセットアップが完了しました。")
    print(f"「{config.VIDEO_DIR.name}」に動画を入れて「レポート作成」をダブルクリックしてください。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return setup() if args.setup else run(args.video, args.force)
    except config.MissingKeysError as e:
        print(f"{e}\n「初回セットアップ」を実行するか、.env にキーを記入してください。")
        return 1
    except KeyboardInterrupt:
        print("\n中断しました。")
        return 130

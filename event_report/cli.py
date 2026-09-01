"""CLIエントリポイント。"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .pipeline import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="event_report",
        description="動画を文字起こしし、イベントレポート(Markdown)を生成します。",
    )
    parser.add_argument("--video", required=True, type=Path, help="動画ファイルのパス(通常はinput/配下)")
    parser.add_argument(
        "--prompt-template",
        type=Path,
        default=config.DEFAULT_PROMPT_TEMPLATE,
        help="レポートのトンマナを指定するプロンプトテンプレートファイル(省略時はデフォルトを使用)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=config.DEFAULT_OUTPUT_DIR,
        help="レポートの出力先ディレクトリ(省略時はoutput/)",
    )
    parser.add_argument("--title", type=str, default=None, help="レポートに記載するイベント名(省略時はファイル名)")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config.require_keys()
    run(
        video_path=args.video,
        prompt_template_path=args.prompt_template,
        output_dir=args.output_dir,
        title=args.title,
    )


if __name__ == "__main__":
    main()

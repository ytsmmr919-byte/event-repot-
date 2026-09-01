"""動画ファイル→文字起こし→イベントレポートの一連の処理をつなぐ。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .plaud_client import PlaudClient
from .report_generator import generate_report, render_prompt


def run(
    video_path: Path,
    prompt_template_path: Path,
    output_dir: Path,
    title: str | None = None,
) -> Path:
    if not video_path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")
    if not prompt_template_path.exists():
        raise FileNotFoundError(f"プロンプトテンプレートが見つかりません: {prompt_template_path}")

    report_title = title or video_path.stem

    print(f"[1/3] Plaud APIで文字起こし中... ({video_path.name})")
    client = PlaudClient()
    transcript = client.transcribe(video_path)

    print("[2/3] Claude APIでレポートを生成中...")
    prompt = render_prompt(prompt_template_path, transcript, report_title)
    report_markdown = generate_report(prompt)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{video_path.stem}_{timestamp}.md"
    output_path.write_text(report_markdown, encoding="utf-8")

    print(f"[3/3] レポートを保存しました: {output_path}")
    return output_path

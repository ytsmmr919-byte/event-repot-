"""動画1本ぶんの処理: 音声抽出 → 文字起こし → レポート作成 → 保存。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import audio, report, transcribe
from .config import Settings

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wmv", ".webm", ".mts", ".m2ts",
    ".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg",
}

REPORT_FILENAME = "レポート.md"
TRANSCRIPT_TEXT_FILENAME = "文字起こし.txt"
TRANSCRIPT_JSON_FILENAME = "transcript.json"


def read_text_file(path: Path) -> str:
    """スタッフが編集するテキストを読む。古いメモ帳のShift_JIS保存にも対応する。"""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp932", errors="replace")


def find_videos(video_dir: Path) -> list[Path]:
    return sorted(
        p for p in video_dir.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def process_video(
    video_path: Path,
    settings: Settings,
    report_root: Path,
    writing_guide_path: Path,
    force: bool = False,
) -> Path | None:
    """レポートを作成して保存先を返す。作成済みでスキップした場合はNone。"""
    out_dir = report_root / video_path.stem
    report_path = out_dir / REPORT_FILENAME
    if report_path.exists() and not force:
        print(f"  作成済みのためスキップ: {report_path.relative_to(report_root.parent)}")
        return None

    transcript_json = out_dir / TRANSCRIPT_JSON_FILENAME
    if transcript_json.exists():
        print("  [1/2] 前回の文字起こし結果を再利用します")
        transcript = transcribe.Transcript.load_json(transcript_json)
    else:
        print("  [1/2] 文字起こし中…(1時間の動画で数分かかります)")
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = audio.extract_audio(video_path, Path(tmp) / "audio.m4a")
            transcript = transcribe.transcribe(audio_path, settings.elevenlabs_api_key)
        if not transcript.segments:
            raise RuntimeError("音声から発言を検出できませんでした。")
        out_dir.mkdir(parents=True, exist_ok=True)
        transcript.save_json(transcript_json)
        (out_dir / TRANSCRIPT_TEXT_FILENAME).write_text(transcript.to_text() + "\n", encoding="utf-8")

    print("  [2/2] レポート作成中…")
    memo_path = video_path.with_suffix(".txt")
    event_memo = read_text_file(memo_path) if memo_path.exists() else ""
    user_message = report.build_user_message(
        transcript_text=transcript.to_text(),
        writing_guide=read_text_file(writing_guide_path),
        event_memo=event_memo,
        video_name=video_path.name,
    )
    report_text = report.generate_report(user_message, settings.anthropic_api_key, settings.claude_model)
    report_path.write_text(report_text, encoding="utf-8")
    return report_path

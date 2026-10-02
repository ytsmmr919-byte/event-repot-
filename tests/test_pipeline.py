import subprocess

import imageio_ffmpeg
import pytest

from event_report import pipeline
from event_report.config import Settings
from event_report.transcribe import Segment, Transcript

SETTINGS = Settings(elevenlabs_api_key="el-key", anthropic_api_key="an-key", claude_model="claude-opus-5-5")


@pytest.fixture
def workspace(tmp_path):
    video_dir = tmp_path / "動画フォルダ"
    report_dir = tmp_path / "レポート出力"
    video_dir.mkdir()
    report_dir.mkdir()
    guide = tmp_path / "レポートの書き方.md"
    guide.write_text("です・ます調で書く", encoding="utf-8")
    return video_dir, report_dir, guide


def make_video(path):
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5",
        "-f", "lavfi", "-i", "sine=frequency=440",
        "-t", "2", "-c:v", "libx264", "-c:a", "aac", str(path),
    ], check=True)
    return path


@pytest.fixture
def fakes(monkeypatch):
    calls = {"transcribe": [], "report": []}

    def fake_transcribe(audio_path, api_key):
        calls["transcribe"].append((audio_path.suffix, audio_path.stat().st_size, api_key))
        return Transcript(segments=[Segment("話者1", 0.0, 1.0, "本日はお集まりいただきありがとうございます。")])

    def fake_generate(user_message, api_key, model):
        calls["report"].append((user_message, api_key, model))
        return "# レポート\n"

    monkeypatch.setattr(pipeline.transcribe, "transcribe", fake_transcribe)
    monkeypatch.setattr(pipeline.report, "generate_report", fake_generate)
    return calls


def test_find_videos_filters_by_extension(workspace):
    video_dir, _, _ = workspace
    for name in ["b.MP4", "a.mov", "a.txt", ".hidden.mp4", "notes.docx"]:
        (video_dir / name).write_bytes(b"")

    assert [p.name for p in pipeline.find_videos(video_dir)] == ["a.mov", "b.MP4"]


def test_process_video_end_to_end_with_memo(workspace, fakes):
    video_dir, report_dir, guide = workspace
    video = make_video(video_dir / "春の交流会.mp4")
    # 古いメモ帳で保存されたShift_JISのメモも読める
    (video_dir / "春の交流会.txt").write_bytes("話者1は司会の田中さん".encode("cp932"))

    report_path = pipeline.process_video(video, SETTINGS, report_dir, guide)

    out_dir = report_dir / "春の交流会"
    assert report_path == out_dir / "レポート.md"
    assert report_path.read_text(encoding="utf-8") == "# レポート\n"
    assert (out_dir / "文字起こし.txt").read_text(encoding="utf-8") == "[00:00:00] 話者1: 本日はお集まりいただきありがとうございます。\n"
    assert (out_dir / "transcript.json").exists()

    [(suffix, size, el_key)] = fakes["transcribe"]
    assert (suffix, el_key) == (".m4a", "el-key")
    assert size > 0  # 実際にffmpegで音声が書き出されている

    [(message, an_key, model)] = fakes["report"]
    assert (an_key, model) == ("an-key", "claude-opus-5-5")
    assert "話者1は司会の田中さん" in message
    assert "です・ます調で書く" in message
    assert "本日はお集まりいただき" in message


def test_process_video_skips_existing_report_and_reuses_transcript_on_force(workspace, fakes):
    video_dir, report_dir, guide = workspace
    video = make_video(video_dir / "event.mp4")
    pipeline.process_video(video, SETTINGS, report_dir, guide)

    assert pipeline.process_video(video, SETTINGS, report_dir, guide) is None
    assert pipeline.process_video(video, SETTINGS, report_dir, guide, force=True) is not None
    assert len(fakes["transcribe"]) == 1  # 文字起こしは1回だけ(課金も1回)
    assert len(fakes["report"]) == 2


def test_process_video_without_audio_track_fails_clearly(workspace, fakes):
    video_dir, report_dir, guide = workspace
    video = video_dir / "silent.mp4"
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=160x120:rate=5", "-t", "1", "-c:v", "libx264", str(video),
    ], check=True)

    with pytest.raises(pipeline.audio.AudioExtractionError):
        pipeline.process_video(video, SETTINGS, report_dir, guide)
    assert fakes["transcribe"] == []


def test_process_url_uses_memo_named_after_report_and_url_label(workspace, monkeypatch):
    video_dir, report_dir, guide = workspace
    (video_dir / "春の交流会.txt").write_text("話者2は講演者の佐藤さん", encoding="utf-8")
    calls = {}

    def fake_transcribe_url(url, api_key):
        calls["transcribe"] = (url, api_key)
        return Transcript(segments=[Segment("話者1", 0.0, 1.0, "始めます。")])

    def fake_generate(user_message, api_key, model):
        calls["message"] = user_message
        return "# レポート\n"

    monkeypatch.setattr(pipeline.transcribe, "transcribe_url", fake_transcribe_url)
    monkeypatch.setattr(pipeline.report, "generate_report", fake_generate)

    report_path = pipeline.process_url("https://youtu.be/abc", "春の交流会", SETTINGS, report_dir, guide, video_dir)

    assert report_path == report_dir / "春の交流会" / "レポート.md"
    assert calls["transcribe"] == ("https://youtu.be/abc", "el-key")
    assert "話者2は講演者の佐藤さん" in calls["message"]
    assert "<video_file>https://youtu.be/abc</video_file>" in calls["message"]

from event_report.plaud_client import Segment, Transcript
from event_report.report_generator import render_prompt


def test_render_prompt_inserts_transcript_and_title(tmp_path):
    template = tmp_path / "template.md"
    template.write_text("# {{title}}\n\n{{transcript}}", encoding="utf-8")

    transcript = Transcript(
        segments=[Segment(speaker="Aさん", start_seconds=5, end_seconds=8, text="こんにちは")]
    )

    prompt = render_prompt(template, transcript, "テストイベント")

    assert "# テストイベント" in prompt
    assert "[00:00:05] Aさん: こんにちは" in prompt
    assert "{{title}}" not in prompt
    assert "{{transcript}}" not in prompt


def test_transcript_to_labeled_text_multiple_segments():
    transcript = Transcript(
        segments=[
            Segment(speaker="Aさん", start_seconds=0, end_seconds=3, text="よろしくお願いします"),
            Segment(speaker="Bさん", start_seconds=65, end_seconds=70, text="ありがとうございます"),
        ]
    )

    text = transcript.to_labeled_text()

    assert text.splitlines() == [
        "[00:00:00] Aさん: よろしくお願いします",
        "[00:01:05] Bさん: ありがとうございます",
    ]

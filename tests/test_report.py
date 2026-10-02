import json

import anthropic
import httpx2
import pytest

from event_report import report


def sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events).encode()


def stream_events(text, stop_reason="end_turn"):
    return [
        {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 1},
        }},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ]


@pytest.fixture
def fake_claude(monkeypatch):
    calls = []
    responses = []

    def handler(request):
        calls.append({"headers": request.headers, "body": json.loads(request.read())})
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse(responses.pop(0)))

    real_client = anthropic.Anthropic
    monkeypatch.setattr(report.anthropic, "Anthropic", lambda api_key: real_client(
        api_key=api_key,
        base_url="https://api.anthropic.com",
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    ))
    return calls, responses


def test_build_user_message_places_transcript_first_and_defaults_memo():
    message = report.build_user_message("[00:00:00] 話者1: こんにちは", "です・ます調で", "", "event.mp4")

    assert message.startswith("<transcript>\n[00:00:00] 話者1: こんにちは\n</transcript>")
    assert "<event_memo>\n(なし)\n</event_memo>" in message
    assert "<writing_guide>\nです・ます調で\n</writing_guide>" in message
    assert "<video_file>event.mp4</video_file>" in message


def test_generate_report_streams_with_fallback_and_returns_text(fake_claude):
    calls, responses = fake_claude
    responses.append(stream_events("# 報告\n本文"))

    text = report.generate_report("user message", "sk-test", "claude-opus-5-5")

    assert text == "# 報告\n本文\n"
    body = calls[0]["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["stream"] is True
    assert body["max_tokens"] == report.MAX_OUTPUT_TOKENS
    assert body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "high"}
    assert body["system"] == report.SYSTEM_PROMPT
    assert "server-side-fallback-2026-07-01" in calls[0]["headers"]["anthropic-beta"]
    assert calls[0]["headers"]["x-api-key"] == "sk-test"


def test_generate_report_marks_truncated_output(fake_claude):
    _, responses = fake_claude
    responses.append(stream_events("途中まで", stop_reason="max_tokens"))

    text = report.generate_report("m", "sk-test", "claude-opus-5-5")

    assert text.startswith("途中まで")
    assert "途中で切れています" in text


def test_generate_report_raises_on_refusal(fake_claude):
    _, responses = fake_claude
    responses.append(stream_events("", stop_reason="refusal"))

    with pytest.raises(report.ReportError):
        report.generate_report("m", "sk-test", "claude-opus-5-5")

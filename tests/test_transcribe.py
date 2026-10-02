import json
from types import SimpleNamespace

import httpx
from elevenlabs.client import ElevenLabs

from event_report import transcribe
from event_report.transcribe import Segment, Transcript, build_transcript


def word(text, start, end, speaker="speaker_0", type_="word"):
    return SimpleNamespace(text=text, start=start, end=end, speaker_id=speaker, type=type_)


def test_build_transcript_groups_by_speaker_and_relabels_in_order():
    words = [
        word("本日は", 0.0, 0.5, "speaker_3"),
        word("よろしく", 0.5, 1.0, "speaker_3"),
        word(" ", 1.0, 1.1, "speaker_3", "spacing"),
        word("お願いします。", 1.1, 2.0, "speaker_3"),
        word("はい。", 65.0, 66.0, "speaker_0"),
        word("(拍手)", 66.0, 67.0, "speaker_0", "audio_event"),
        word("続けます。", 70.0, 71.0, "speaker_3"),
    ]

    transcript = build_transcript(words)

    assert [(s.speaker, s.text) for s in transcript.segments] == [
        ("話者1", "本日はよろしく お願いします。"),
        ("話者2", "はい。"),
        ("話者1", "続けます。"),
    ]
    assert transcript.segments[0].start == 0.0
    assert transcript.segments[0].end == 2.0
    assert transcript.to_text().splitlines()[1] == "[00:01:05] 話者2: はい。"


def test_build_transcript_splits_long_monologue_at_sentence_end():
    sentence = "あ" * 299 + "。"
    words = [word(sentence, 0, 30), word("次の文", 30, 31), word("です。", 31, 32)]

    transcript = build_transcript(words)

    assert [s.text for s in transcript.segments] == [sentence, "次の文です。"]
    assert {s.speaker for s in transcript.segments} == {"話者1"}


def test_transcript_json_round_trip(tmp_path):
    original = Transcript(segments=[Segment("話者1", 1.5, 3.0, "こんにちは")])
    path = tmp_path / "t.json"

    original.save_json(path)

    assert Transcript.load_json(path) == original


def test_transcribe_sends_expected_request_and_parses_response(tmp_path, monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("xi-api-key")
        captured["body"] = request.read()
        return httpx.Response(200, json={
            "language_code": "jpn",
            "language_probability": 0.99,
            "text": "こんにちは。はい。",
            "words": [
                {"text": "こんにちは。", "start": 0.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0", "logprob": 0.0},
                {"text": "はい。", "start": 1.5, "end": 2.0, "type": "word", "speaker_id": "speaker_1", "logprob": 0.0},
            ],
        })

    real_client = ElevenLabs
    monkeypatch.setattr(
        transcribe, "ElevenLabs",
        lambda api_key, timeout: real_client(api_key=api_key, httpx_client=httpx.Client(transport=httpx.MockTransport(handler))),
    )
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"fake-audio")

    result = transcribe.transcribe(audio, "test-key")

    assert captured["url"].endswith("/v1/speech-to-text")
    assert captured["api_key"] == "test-key"
    body = captured["body"].decode("utf-8", errors="replace")
    for field, value in [("model_id", "scribe_v2"), ("language_code", "ja"), ("diarize", "true"), ("timestamps_granularity", "word")]:
        assert f'name="{field}"\r\n\r\n{value}' in body
    assert [(s.speaker, s.text) for s in result.segments] == [("話者1", "こんにちは。"), ("話者2", "はい。")]

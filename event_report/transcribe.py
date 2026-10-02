"""ElevenLabs Speech to Text (Scribe) による話者分離つき文字起こし。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from elevenlabs.client import ElevenLabs

TRANSCRIBE_MODEL = "scribe_v2"
# 1時間超の音声は処理に数分かかるため、SDK既定の240秒では足りない
REQUEST_TIMEOUT_SECONDS = 60 * 60

# 同じ話者の発言でも、この文字数を超えたら文の区切りで行を分ける(読みやすさのため)
MAX_SEGMENT_CHARS = 300
SENTENCE_ENDINGS = ("。", "？", "！", "?", "!")


@dataclass
class Segment:
    speaker: str
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    segments: list[Segment] = field(default_factory=list)

    def to_text(self) -> str:
        return "\n".join(f"[{format_timestamp(s.start)}] {s.speaker}: {s.text}" for s in self.segments)

    def save_json(self, path: Path) -> None:
        data = [asdict(s) for s in self.segments]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "Transcript":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(segments=[Segment(**item) for item in data])


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def transcribe(audio_path: Path, api_key: str) -> Transcript:
    client = ElevenLabs(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    with open(audio_path, "rb") as f:
        result = client.speech_to_text.convert(
            model_id=TRANSCRIBE_MODEL,
            file=f,
            language_code="ja",
            diarize=True,
            tag_audio_events=False,
            timestamps_granularity="word",
        )
    words = getattr(result, "words", None)
    if words is None:
        raise RuntimeError(f"文字起こし結果の形式が想定外です: {type(result).__name__}")
    return build_transcript(words)


def build_transcript(words: Iterable) -> Transcript:
    """単語単位の結果を、話者ごとのまとまり(セグメント)に組み立てる。

    speaker_id("speaker_0"など)は登場順に「話者1」「話者2」…へ置き換える。
    """
    labels: dict[str, str] = {}
    segments: list[Segment] = []
    current: Segment | None = None

    for word in words:
        if word.type == "audio_event":
            continue
        if word.type == "spacing":
            if current is not None:
                current.text += word.text
            continue

        if word.speaker_id:
            speaker = labels.setdefault(word.speaker_id, f"話者{len(labels) + 1}")
        else:
            speaker = current.speaker if current else "話者不明"

        start = word.start or 0.0
        end = word.end if word.end is not None else start
        needs_new_segment = (
            current is None
            or speaker != current.speaker
            or (len(current.text) >= MAX_SEGMENT_CHARS and current.text.rstrip().endswith(SENTENCE_ENDINGS))
        )
        if needs_new_segment:
            current = Segment(speaker=speaker, start=start, end=end, text="")
            segments.append(current)
        current.text += word.text
        current.end = end

    for segment in segments:
        segment.text = segment.text.strip()
    return Transcript(segments=[s for s in segments if s.text])

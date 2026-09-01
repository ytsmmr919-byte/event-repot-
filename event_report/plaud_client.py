"""Plaud Developer API (Transcription API) クライアント。

Plaudの開発者向けTranscription APIを呼び出し、話者分離済みの文字起こし結果を取得する。

NOTE(要確認): この実装を書いた時点では docs.plaud.ai / dev.plaud.ai への
ネットワークアクセスができず、正式なAPIリファレンスを直接参照できなかった。
そのため以下のエンドポイントパス・リクエスト/レスポンスのフィールド名は
一般的なREST APIの慣例に基づく暫定実装になっている。実際に利用する前に、
Plaud Developer Portal (https://docs.plaud.ai) のTranscription APIリファレンスと
突き合わせて、下記の定数と `_upload` / `_wait_for_completion` / `_parse_transcript`
の実装を実際の仕様に合わせて調整すること。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from . import config

# --- 要確認: 実際のPlaud APIエンドポイント仕様に合わせて調整すること ---
UPLOAD_ENDPOINT = "/v1/transcriptions"
STATUS_ENDPOINT = "/v1/transcriptions/{job_id}"
POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_SECONDS = 60 * 60 * 3  # 3時間(1時間超の動画の処理時間を見込む)


@dataclass
class Segment:
    speaker: str
    start_seconds: float
    end_seconds: float
    text: str


@dataclass
class Transcript:
    segments: list[Segment] = field(default_factory=list)

    def to_labeled_text(self) -> str:
        lines = [
            f"[{_format_timestamp(seg.start_seconds)}] {seg.speaker}: {seg.text}"
            for seg in self.segments
        ]
        return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class PlaudClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or config.PLAUD_API_KEY
        self.base_url = (base_url or config.PLAUD_API_BASE_URL).rstrip("/")
        if not self.api_key:
            raise RuntimeError("PLAUD_API_KEYが設定されていません。")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def transcribe(self, file_path: Path) -> Transcript:
        job_id = self._upload(file_path)
        result = self._wait_for_completion(job_id)
        return self._parse_transcript(result)

    def _upload(self, file_path: Path) -> str:
        url = f"{self.base_url}{UPLOAD_ENDPOINT}"
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            data = {"language": "ja", "diarization": "true"}
            response = requests.post(
                url, headers=self._headers(), files=files, data=data, timeout=300
            )
        response.raise_for_status()
        payload = response.json()
        job_id = payload.get("id") or payload.get("job_id")
        if not job_id:
            raise RuntimeError(f"Plaud APIのレスポンスからジョブIDを取得できませんでした: {payload}")
        return job_id

    def _wait_for_completion(self, job_id: str) -> dict:
        url = f"{self.base_url}{STATUS_ENDPOINT.format(job_id=job_id)}"
        elapsed = 0
        while elapsed < POLL_TIMEOUT_SECONDS:
            response = requests.get(url, headers=self._headers(), timeout=60)
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status")
            if status in ("completed", "done", "succeeded"):
                return payload
            if status in ("failed", "error"):
                raise RuntimeError(f"Plaud APIの文字起こしジョブが失敗しました: {payload}")
            time.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
        raise TimeoutError(f"Plaud APIの文字起こしジョブがタイムアウトしました(job_id={job_id})")

    def _parse_transcript(self, payload: dict) -> Transcript:
        raw_segments = payload.get("segments") or payload.get("transcript", {}).get("segments", [])
        segments = [
            Segment(
                speaker=raw.get("speaker") or raw.get("speaker_label") or "不明",
                start_seconds=float(raw.get("start", 0)),
                end_seconds=float(raw.get("end", 0)),
                text=raw.get("text", "").strip(),
            )
            for raw in raw_segments
        ]
        return Transcript(segments=segments)

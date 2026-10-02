"""フォルダ構成とAPIキーなどの設定。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv, set_key

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
VIDEO_DIR = ROOT / "動画フォルダ"
REPORT_DIR = ROOT / "レポート出力"
WRITING_GUIDE_PATH = ROOT / "レポートの書き方.md"

DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"

# .envのキー名 → 入力を促すときの説明
API_KEYS = {
    "ELEVENLABS_API_KEY": "ElevenLabs のAPIキー(文字起こし用)",
    "ANTHROPIC_API_KEY": "Anthropic のAPIキー(レポート作成用)",
}


class MissingKeysError(RuntimeError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"APIキーが設定されていません: {', '.join(missing)}")


@dataclass(frozen=True)
class Settings:
    elevenlabs_api_key: str
    anthropic_api_key: str
    claude_model: str


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)
    missing = [name for name in API_KEYS if not os.environ.get(name, "").strip()]
    if missing:
        raise MissingKeysError(missing)
    return Settings(
        elevenlabs_api_key=os.environ["ELEVENLABS_API_KEY"].strip(),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"].strip(),
        claude_model=os.environ.get("CLAUDE_MODEL", "").strip() or DEFAULT_CLAUDE_MODEL,
    )


def ask_and_save_keys(names: list[str]) -> None:
    """不足しているAPIキーを対話的に入力してもらい、.envに保存する。"""
    ENV_PATH.touch(exist_ok=True)
    for name in names:
        value = ""
        while not value:
            value = input(f"{API_KEYS[name]}を貼り付けてEnterを押してください: ").strip()
        set_key(str(ENV_PATH), name, value, quote_mode="never")
        os.environ[name] = value

"""環境変数ベースの設定値。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PLAUD_API_KEY = os.environ.get("PLAUD_API_KEY", "")
PLAUD_API_BASE_URL = os.environ.get("PLAUD_API_BASE_URL", "https://api.plaud.ai")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT_TEMPLATE = PROJECT_ROOT / "config" / "prompts" / "default_report_prompt.md"
DEFAULT_INPUT_DIR = PROJECT_ROOT / "input"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


def require_keys() -> None:
    missing = [
        name
        for name, value in (
            ("PLAUD_API_KEY", PLAUD_API_KEY),
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"必要な環境変数が設定されていません: {', '.join(missing)}。"
            ".envファイルを作成し、.env.exampleを参考に値を設定してください。"
        )

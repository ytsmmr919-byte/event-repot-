"""プロンプトテンプレートのレンダリングとClaude APIによるレポート生成。"""
from __future__ import annotations

from pathlib import Path

import anthropic

from . import config
from .plaud_client import Transcript

TRANSCRIPT_PLACEHOLDER = "{{transcript}}"
TITLE_PLACEHOLDER = "{{title}}"


def render_prompt(template_path: Path, transcript: Transcript, title: str) -> str:
    template_text = template_path.read_text(encoding="utf-8")
    prompt = template_text.replace(TRANSCRIPT_PLACEHOLDER, transcript.to_labeled_text())
    prompt = prompt.replace(TITLE_PLACEHOLDER, title)
    return prompt


def generate_report(prompt: str) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEYが設定されていません。")
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in message.content if block.type == "text")

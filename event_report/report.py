"""Claude API によるイベントレポートの作成。"""
from __future__ import annotations

import anthropic

MAX_OUTPUT_TOKENS = 64000

SYSTEM_PROMPT = """あなたはイベントの記録担当者です。イベントを録画した動画の文字起こし(話者分離済み)をもとに、イベントレポートを日本語のMarkdownで作成します。

- 出力はレポート本文のみとし、前置きや作成後のコメントは書かないでください。
- 文字起こしにない事実を補わないでください。文字起こしは音声認識の結果なので誤変換が含まれます。文脈から明らかな誤変換は正しい表記に直して構いませんが、確信の持てない固有名詞や数字は文字起こしのまま残してください。
- 「話者1」「話者2」などのラベルは音声から機械的に推定したもので、同じ人が別の話者に分かれていたり、別の人が同じ話者にまとめられていることがあります。イベント情報メモに名前や役割があればそれに置き換え、なければ発言内容から役割(司会、登壇者など)が明らかな場合に限り役割で呼んでください。
- 書き方・構成・トーンは<writing_guide>に従ってください。<event_memo>に指示がある場合はそちらを優先してください。"""


class ReportError(RuntimeError):
    pass


def build_user_message(transcript_text: str, writing_guide: str, event_memo: str, video_name: str) -> str:
    # 長い文字起こしを先に置き、指示を最後に置く
    return f"""<transcript>
{transcript_text}
</transcript>

<video_file>{video_name}</video_file>

<event_memo>
{event_memo.strip() or "(なし)"}
</event_memo>

<writing_guide>
{writing_guide.strip()}
</writing_guide>

上記の文字起こしをもとに、<writing_guide>に沿ってイベントレポートを作成してください。"""


def generate_report(user_message: str, api_key: str, model: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    # 入出力が長いのでストリーミングで受け取る(HTTPタイムアウト回避)。
    # 安全分類器による拒否時は、サーバー側で推奨モデルに自動で切り替えて再実行する。
    with client.beta.messages.stream(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise ReportError("Claudeがこの内容のレポート作成を断りました。文字起こしの内容を確認してください。")
    text = "".join(block.text for block in message.content if block.type == "text").strip()
    if not text:
        raise ReportError("Claudeから空のレポートが返されました。")
    if message.stop_reason == "max_tokens":
        text += "\n\n---\n※ 出力の上限に達したため、レポートが途中で切れています。"
    return text + "\n"

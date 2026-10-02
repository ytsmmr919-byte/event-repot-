# イベントレポート作成ツール

イベント動画を「動画フォルダ」に入れてダブルクリックすると、話者分離つきの文字起こしとイベントレポート(Markdown)を作成するツールです。スタッフ各自のPC(Windows / Mac)で動かす前提で作っています。

- スタッフ向けの手順は [`使い方.txt`](使い方.txt) を参照してください(配布zipにも同梱されます)
- このREADMEは管理者・開発者向けです

## 仕組み

```
動画フォルダ/春の交流会.mp4
   │ ① 音声を取り出す(同梱のffmpeg、モノラル16kHz・1時間で約20MB)
   ▼
ElevenLabs Speech to Text(Scribe v2)…日本語の文字起こし+話者分離
   │ ② 「話者1」「話者2」…ごとに発言をまとめる
   ▼
Claude API(claude-opus-5-5)…「レポートの書き方.md」+ 動画ごとのメモ(任意)に沿ってレポート化
   ▼
レポート出力/春の交流会/
   ├ レポート.md       イベントレポート
   ├ 文字起こし.txt    発言者・時刻つき全文
   └ transcript.json  文字起こしの保存(レポートの作り直し時に再利用)
```

## 使うAPIと選定理由

| 用途 | サービス | 理由 |
|---|---|---|
| 文字起こし | **ElevenLabs Speech to Text(Scribe v2)** | 日本語に対応し話者分離が標準機能(最大32人)。1ファイル3GB・10時間まで送れるので、1時間超の動画も分割不要。公式Python SDKあり |
| レポート作成 | **Anthropic Claude API(claude-opus-5-5)** | 長い文字起こしをまとめて渡せ(1Mトークン)、文体・構成の指示に沿った文章が書ける |

検討して見送ったもの:

- **Plaud API** — Transcription APIはPlaudデバイスとのバインド(Plaud Embedded SDK)が前提で、手元の動画ファイルを送る用途には使えないため
- **Google Cloud Speech-to-Text** — 長時間音声の話者分離にはCloud Storageのバケットやサービスアカウントの用意が必要で、スタッフPCで使うには準備が重いため
- **OpenAI(Whisper / gpt-4o-transcribe-diarize)** — 1ファイル25MBの上限があり、1時間超の動画は分割が必要。分割すると話者ラベルがファイルをまたいで一致しなくなるため
- **AssemblyAI** — 日本語の話者分離に対応しており有力な代替候補。ElevenLabsに問題があれば `event_report/transcribe.py` だけ差し替えれば移行できます

### 費用の目安(1時間の動画1本あたり)

- 文字起こし: 約 $0.22(ElevenLabs API 従量単価。契約プランにより異なるので[料金ページ](https://elevenlabs.io/pricing/api)で確認してください)
- レポート作成: 約 $0.3〜0.5(入力 約3万トークン × $4/100万 + 出力・思考 約1.5万トークン × $20/100万)

月15本でおおよそ $10〜15 程度です。レポートを作り直しても文字起こしは再利用されるため、追加費用はレポート作成分だけです。

## 管理者がやること

### 1. APIキーを用意する

- ElevenLabs: <https://elevenlabs.io/app/settings/api-keys> でAPIキーを発行(Speech to Textの権限が必要)
- Anthropic: <https://platform.claude.com/settings/keys> でAPIキーを発行

### 2. スタッフに配布する

```
uv run python tools/make_dist.py
```

`dist/イベントレポート作成ツール.zip` ができるので、スタッフに渡してください。スタッフは `使い方.txt` の手順で初回セットアップを行い、そこで2つのAPIキーを貼り付けます。

キーの入力も省きたい場合は、手元で一度初回セットアップをして `.env` を作ってから `--with-env` を付けて作ると、`.env` 入りのzipになります(zipの扱いに注意してください)。

### スタッフPCで初回セットアップがやること

1. [uv](https://docs.astral.sh/uv/)(Pythonの管理ツール)が無ければ公式インストーラで入れる
2. `uv sync` でPython 3.12と依存ライブラリを、このフォルダ内の `.venv` に入れる(PCにPythonが入っていなくてもよい)
3. APIキーを聞いて `.env` に保存する

インターネット接続(astral.sh・github.com・pypi.org、実行時は api.elevenlabs.io・api.anthropic.com)が必要です。

## カスタマイズ

- **全レポート共通の文体・構成**: `レポートの書き方.md` を編集
- **動画ごとの情報(話者名・イベント名・追加指示)**: 動画と同名の `.txt` を動画フォルダに置く
- **Claudeのモデル**: `.env` に `CLAUDE_MODEL=claude-sonnet-5-5` などと書くと変更できます(既定は `claude-opus-5-5`)
- **AIへの共通指示(誤変換の扱い、話者ラベルの扱いなど)**: `event_report/report.py` の `SYSTEM_PROMPT`

## 開発

```
uv sync          # 開発用(pytest含む)
uv run pytest    # テスト
uv run python -m event_report --help
```

| ファイル | 役割 |
|---|---|
| `event_report/cli.py` | 入口。動画フォルダの未処理動画を順に処理し、エラーをスタッフ向けの文言にする |
| `event_report/pipeline.py` | 動画1本の処理(スキップ判定、文字起こし再利用、保存) |
| `event_report/audio.py` | 同梱ffmpegでの音声抽出 |
| `event_report/transcribe.py` | ElevenLabs呼び出しと、単語→話者ごとの発言への組み立て |
| `event_report/report.py` | Claude呼び出し(ストリーミング、拒否時のサーバー側フォールバック) |
| `event_report/config.py` | フォルダ構成、`.env` の読み書き |
| `tools/make_dist.py` | 配布zipの作成 |

テストは外部APIを呼ばず、両SDKのHTTP層をモックに差し替えて、送信パラメータとレスポンス処理を検証しています。音声抽出は同梱ffmpegで実際に動画を生成・変換して確認しています。

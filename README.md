# イベント動画 文字起こし→レポート化ツール

アップロードした動画を文字起こし(話者分離つき)し、イベントレポート(Markdown)を自動生成する個人用CLIツールです。

## 構成

- 文字起こし: [Plaud Developer API](https://docs.plaud.ai)(Transcription API) — 動画ファイルを直接アップロードし、話者分離済みの文字起こしを取得
- レポート生成: Anthropic API(Claude)

## セットアップ

1. Python 3.10以上をインストール
2. 依存パッケージをインストール
   ```
   pip install -r requirements.txt
   ```
3. `.env.example` をコピーして `.env` を作成し、共有されているAPIキーを設定
   ```
   cp .env.example .env
   ```
   - `PLAUD_API_KEY`: Plaud Developer PortalのAPIキー
   - `ANTHROPIC_API_KEY`: Anthropic APIキー
   - `CLAUDE_MODEL`: レポート生成に使うモデル(未設定時は `claude-sonnet-5`)

## 使い方

1. 文字起こししたい動画を `input/` フォルダに配置する
2. コマンドを実行する
   ```
   python -m event_report --video input/イベント名.mp4
   ```
3. `output/` フォルダに `{動画名}_{実行日時}.md` の形式でレポートが生成される

### オプション

| オプション | 説明 |
|---|---|
| `--title` | レポートに記載するイベント名を明示指定(省略時は動画ファイル名) |
| `--prompt-template` | レポートのトンマナ(文体・構成)を指定するテンプレートファイルを差し替える(省略時は`config/prompts/default_report_prompt.md`) |
| `--output-dir` | レポートの出力先ディレクトリ(省略時は`output/`) |

## レポートのトンマナをカスタマイズする

`config/prompts/default_report_prompt.md` を直接編集することで、レポートの文体・見出し構成をカスタマイズできます。

イベント種別ごとに複数のトンマナを使い分けたい場合は、`config/prompts/` 配下に別テンプレートを追加し、実行時に指定してください。

```
python -m event_report --video input/イベント名.mp4 --prompt-template config/prompts/casual.md
```

テンプレート内の `{{title}}` はイベント名に、`{{transcript}}` は発言者ラベル・タイムスタンプ付きの文字起こしに置き換えられます。この2つのプレースホルダは残したまま、それ以外の指示文(トーン・見出し構成など)を自由に書き換えてください。

## テストの実行

```
pytest
```

## 既知の注意点

- `event_report/plaud_client.py` はPlaud Developer APIの正式なリファレンスと突き合わせて実装したものではなく、一般的なREST APIの慣例に基づく暫定実装です。実際に実行してエラーになる場合は、[Plaud Developer Portal](https://docs.plaud.ai) の最新のTranscription APIリファレンス(認証ヘッダー形式・エンドポイントパス・レスポンスのJSON構造)を確認し、同ファイル内の定数と `_upload` / `_wait_for_completion` / `_parse_transcript` を実際の仕様に合わせて修正してください。
- 1時間を超える動画はPlaud API側の処理に時間がかかる場合があります(ポーリングのタイムアウトは3時間に設定)。

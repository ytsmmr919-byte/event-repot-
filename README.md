# イベントレポート作成ツール

> **現在の運用(2026年10月〜)**: 配信の音声はツールを使わず、StreamYardから「Audio recording」(MP3)を直接ダウンロードしてPlaudで文字起こしします。手順は [`StreamYardからPlaudへの手順.txt`](StreamYardからPlaudへの手順.txt) を参照してください。
>
> このツールは、Windows 11の**スマート アプリ コントロール**が有効なPCでは動きません(署名のない起動ファイル・Python・ffmpeg・Denoがブロックされ、個別に許可する設定もありません)。使う場合は、スマート アプリ コントロールが無効なPCかMacで実行してください。

StreamYardで配信したイベントの動画から、話者分離つきの文字起こしとイベントレポート(Markdown)を作成するツールです。スタッフ各自のPC(Windows / Mac)で、ダブルクリックで動かす前提で作っています。

- **音声だけ欲しい(Plaudで文字起こしする)**: 「4_YouTubeから音声を保存」でURLを貼るだけ → 「音声フォルダ」にMP3。APIキー不要
- **レポートまで作る・YouTubeに配信した場合**: 「3_YouTubeから作成」でURLを貼るだけ(動画のダウンロード不要)
- **レポートまで作る・それ以外**: StreamYardから録画をダウンロードして「動画フォルダ」に入れ、「2_レポート作成」

## YouTubeから音声を保存(Plaud向け)

[yt-dlp](https://github.com/yt-dlp/yt-dlp) で音声トラックだけを取得し、同梱ffmpegでMP3(モノラル96kbps、1時間で約43MB)に変換して `音声フォルダ/(タイトル).mp3` に保存します。Plaud Webのインポートが対応する形式(MP3、500MBまで)に合わせています。

- **APIキー不要・費用なし**。初回セットアップでキーを聞かれても空Enterで飛ばせます
- 現在のYouTubeは取得にJavaScript実行環境が必要なため、PyPI版の [Deno](https://pypi.org/project/deno/) と `yt-dlp-ejs` を依存に入れて自動で使います(スタッフPCに別途インストール不要)
- YouTubeの仕様変更でyt-dlpは古いと動かなくなるため、`4_YouTubeから音声を保存` は**起動のたびにyt-dlpだけ最新版に更新**します(オフライン時はそのまま)
- 配信中・配信予定・アーカイブ準備中(`live_status` が `is_live` / `is_upcoming` / `post_live`)の動画はダウンロードせずに案内を出します
- YouTubeの利用規約は公式手段以外のダウンロードを認めていません。自社チャンネルの配信を対象に使ってください(公式の手段はYouTube Studioの「ダウンロード」です)

- スタッフ向けの手順は [`使い方.txt`](使い方.txt) を参照してください(配布zipにも同梱されます)
- このREADMEは管理者・開発者向けです

## 仕組み

```
動画フォルダ/春の交流会.mp4                YouTubeのURL(公開/限定公開)
   │ ① 音声を取り出す                          │ ① タイトル取得(非公開ならここで止める)
   │   (同梱ffmpeg・1時間で約20MB)            │   URLをそのままElevenLabsへ渡す
   ▼                                           ▼
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

## StreamYardとの連携について

StreamYardには公開APIがなく、Zapier連携のトリガーも配信の作成・更新などに限られるため、**StreamYardのストレージから録画を自動で取り出すことはできません**(2026年10月時点)。そこで次の2通りにしています。

1. **YouTubeにも配信する(推奨)** — 配信のアーカイブがYouTubeに残るので、ElevenLabsの `source_url` にYouTubeのURLを渡して文字起こしします。ダウンロードはElevenLabs側で行われるため、スタッフPCには動画が残りません。YouTubeの公開設定は「公開」か「限定公開」が必要です(「非公開」はElevenLabsから読めません)。処理前にYouTubeのoEmbedでタイトルを取得し、非公開・削除済みならその時点で止めるので、無駄な課金は発生しません
2. **ダウンロードして使う** — Facebook・LinkedInのみの配信や非公開にした場合は、StreamYardのライブラリから録画(音声のみで可)をダウンロードして「動画フォルダ」へ

将来、配信終了から完全自動でレポートを作りたい場合は、YouTubeチャンネルの新着(RSS)を定期的に確認してこのツールの `--url` を呼ぶ仕組みを、GitHub Actionsの定期実行などで追加できます。

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

インターネット接続(astral.sh・github.com・pypi.org、実行時は api.elevenlabs.io・api.anthropic.com・www.youtube.com・*.googlevideo.com、yt-dlpの更新に pypi.org)が必要です。

## カスタマイズ

- **全レポート共通の文体・構成**: `レポートの書き方.md` を編集
- **動画ごとの情報(話者名・イベント名・追加指示)**: レポート名(動画ファイル名、またはYouTubeで入力した名前)と同名の `.txt` を動画フォルダに置く
- **Claudeのモデル**: `.env` に `CLAUDE_MODEL=claude-sonnet-5-5` などと書くと変更できます(既定は `claude-opus-5-5`)
- **AIへの共通指示(誤変換の扱い、話者ラベルの扱いなど)**: `event_report/report.py` の `SYSTEM_PROMPT`

## 開発

```
uv sync          # 開発用(pytest含む)
uv run pytest    # テスト
uv run python -m event_report --help
uv run python -m event_report --url https://youtu.be/xxxx --name 春の交流会   # 対話なしでURLから作成
uv run python -m event_report --audio-url https://youtu.be/xxxx              # 対話なしで音声だけ保存
```

| ファイル | 役割 |
|---|---|
| `event_report/cli.py` | 入口。動画フォルダの未処理動画/入力されたYouTube URLを順に処理し、エラーをスタッフ向けの文言にする |
| `event_report/pipeline.py` | 1件の処理(スキップ判定、文字起こし再利用、保存)。動画ファイルとURLで共通 |
| `event_report/youtube.py` | YouTube URLの判定、oEmbedでのタイトル取得(非公開の検出)、yt-dlpでの音声ダウンロード |
| `event_report/audio.py` | 同梱ffmpegでの音声抽出・MP3変換 |
| `event_report/transcribe.py` | ElevenLabs呼び出し(ファイル/URL)と、単語→話者ごとの発言への組み立て |
| `event_report/report.py` | Claude呼び出し(ストリーミング、拒否時のサーバー側フォールバック) |
| `event_report/config.py` | フォルダ構成、`.env` の読み書き |
| `tools/make_dist.py` | 配布zipの作成 |

テストは外部APIを呼ばず、両SDKのHTTP層をモックに差し替えて、送信パラメータとレスポンス処理を検証しています。音声抽出は同梱ffmpegで実際に動画を生成・変換して確認しています。音声保存はローカルのHTTPサーバーから実際にyt-dlpでダウンロード→MP3変換まで通しています(YouTube固有の取得処理だけはテスト環境から到達できないため未検証)。

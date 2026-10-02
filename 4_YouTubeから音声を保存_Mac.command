#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "[エラー] セットアップが済んでいません。先に「1_初回セットアップ_Mac」を実行してください。"
  read -r -p "Enterキーで閉じます"
  exit 1
fi

# YouTubeの仕様変更に追従するため、yt-dlpだけ毎回最新にする(オフライン時は今のまま)
uv sync --no-dev -q --upgrade-package yt-dlp --upgrade-package yt-dlp-ejs >/dev/null 2>&1
uv run --no-dev python -m event_report --youtube-audio
read -r -p "Enterキーで閉じます"

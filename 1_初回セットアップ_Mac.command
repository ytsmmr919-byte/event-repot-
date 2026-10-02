#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv(Pythonの管理ツール)をインストールしています…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "[エラー] uvをインストールできませんでした。管理者に連絡してください。"
  read -r -p "Enterキーで閉じます"
  exit 1
fi

echo "Pythonと必要なライブラリをインストールしています(数分かかることがあります)…"
if ! uv sync --no-dev; then
  echo "[エラー] セットアップに失敗しました。インターネット接続を確認して、もう一度実行してください。"
  read -r -p "Enterキーで閉じます"
  exit 1
fi

uv run --no-dev python -m event_report --setup
read -r -p "Enterキーで閉じます"

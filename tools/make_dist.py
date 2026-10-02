"""スタッフ配布用のzipを作る。

    uv run python tools/make_dist.py            # APIキーなし(スタッフが初回セットアップで入力)
    uv run python tools/make_dist.py --with-env # .env(共通APIキー)を同梱

.commandファイルに実行権限を付けたままzipにするため、Mac/Windowsどちらでも展開後そのまま使える。
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_NAME = "イベントレポート作成ツール"

INCLUDE = [
    "1_初回セットアップ_Windows.bat",
    "1_初回セットアップ_Mac.command",
    "2_レポート作成_Windows.bat",
    "2_レポート作成_Mac.command",
    "使い方.txt",
    "レポートの書き方.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".env.example",
]
EMPTY_DIRS = ["動画フォルダ", "レポート出力"]


def build(with_env: bool) -> Path:
    files = [ROOT / name for name in INCLUDE]
    files += sorted((ROOT / "event_report").glob("*.py"))
    if with_env:
        env = ROOT / ".env"
        if not env.exists():
            raise SystemExit(".env がありません。先に初回セットアップでAPIキーを登録してください。")
        files.append(env)

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    zip_path = dist_dir / f"{DIST_NAME}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo.from_file(path, f"{DIST_NAME}/{path.relative_to(ROOT).as_posix()}")
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.suffix == ".command" else 0o644
            info.external_attr = (0o100000 | mode) << 16
            zf.writestr(info, path.read_bytes())
        for name in EMPTY_DIRS:
            zf.writestr(f"{DIST_NAME}/{name}/", b"")
    return zip_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-env", action="store_true", help=".env(APIキー)を同梱する")
    zip_path = build(parser.parse_args().with_env)
    print(f"作成しました: {zip_path}")

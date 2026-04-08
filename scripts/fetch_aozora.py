#!/usr/bin/env python3
"""
青空文庫からテキストを取得するスクリプト

aozorahack GitHub リポジトリのraw URLからテキストを取得する。
Shift_JIS → UTF-8 変換を自動で行う。

使い方:
  # 作品IDを指定（青空文庫の作品ページURLの数字）
  python3 fetch_aozora.py --work-id 789 --output-name soseki_kokoro

  # URLを直接指定
  python3 fetch_aozora.py --url "https://www.aozora.gr.jp/cards/000148/files/773_14560.html" --output-name soseki_kokoro

青空文庫テキストURL形式:
  https://www.aozora.gr.jp/cards/{作者ID}/files/{ファイル名}.txt
"""

import argparse
import re
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
REGION = "japan"


def fetch_aozora_text(url: str) -> str:
    """青空文庫のテキストファイルURLからテキストを取得する"""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    # Shift_JIS → UTF-8 変換
    try:
        text = resp.content.decode("shift_jis")
    except (UnicodeDecodeError, LookupError):
        try:
            text = resp.content.decode("cp932")
        except (UnicodeDecodeError, LookupError):
            text = resp.content.decode("utf-8", errors="replace")

    return text


def strip_aozora_metadata(text: str) -> str:
    """青空文庫の底本情報・ルビ記号・外字注釈を除去する"""
    # ルビ記号除去: 《》内のルビを削除
    text = re.sub(r"《[^》]*》", "", text)
    # 外字注釈除去: ［＃...］
    text = re.sub(r"［＃[^］]*］", "", text)
    # 底本情報（末尾の「底本：」以降を削除）
    m = re.search(r"\n底本：", text)
    if m:
        text = text[:m.start()]
    # 著作権表示行の除去
    text = re.sub(r"^-+\n.*著作権.*\n-+\n?", "", text, flags=re.MULTILINE | re.DOTALL)

    return text.strip()


def save_text(text: str, output_name: str) -> Path:
    out_dir = BASE_DIR / "logs" / REGION
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{output_name}.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"保存: {out_path} ({len(text):,} 文字)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="青空文庫からテキスト取得")
    parser.add_argument("--url",         required=True, help="青空文庫テキストファイルのURL（.txt）")
    parser.add_argument("--output-name", required=True, help="出力ファイル名（拡張子なし）")
    args = parser.parse_args()

    print(f"取得中: {args.url}")
    text = fetch_aozora_text(args.url)
    text = strip_aozora_metadata(text)
    save_text(text, args.output_name)


if __name__ == "__main__":
    main()

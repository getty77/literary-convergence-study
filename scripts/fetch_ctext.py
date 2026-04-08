#!/usr/bin/env python3
"""
ctext.org APIから中国古典テキストを取得するスクリプト

使い方:
  python3 fetch_ctext.py --book analects --output-name confucius_analects
  python3 fetch_ctext.py --book daodejing --output-name laozi_daodejing
  python3 fetch_ctext.py --book zhuangzi --output-name zhuangzi
  python3 fetch_ctext.py --book shiji --output-name sima_shiji
  python3 fetch_ctext.py --book shijing --output-name shijing

ctext.org 主要テキストID:
  analects      論語
  daodejing     道徳経
  zhuangzi      荘子
  shiji         史記
  shijing       詩経
  mencius       孟子
  xunzi         荀子
  sunzi         孫子兵法
"""

import argparse
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
REGION = "china"
CTEXT_API = "https://ctext.org/api.pl"


def fetch_ctext(book_id: str) -> str:
    """ctext.org APIからテキストを取得する"""
    params = {
        "if": "en",         # インターフェース言語（英語）
        "op": "gettext",
        "id": book_id,
        "format": "text",
    }
    resp = requests.get(CTEXT_API, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "result" not in data:
        raise ValueError(f"APIエラー: {data}")

    # テキストセクションを結合
    text_parts = []
    for item in data["result"]:
        if isinstance(item, dict) and "text" in item:
            text_parts.append(item["text"])
        elif isinstance(item, str):
            text_parts.append(item)

    return "\n\n".join(text_parts)


def save_text(text: str, output_name: str) -> Path:
    out_dir = BASE_DIR / "logs" / REGION
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{output_name}.txt"
    out_path.write_text(text, encoding="utf-8")
    print(f"保存: {out_path} ({len(text):,} 文字)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="ctext.org からテキスト取得")
    parser.add_argument("--book",        required=True, help="ctext.org book ID（例: analects）")
    parser.add_argument("--output-name", required=True, help="出力ファイル名（拡張子なし）")
    args = parser.parse_args()

    print(f"取得中: {args.book}")
    # ctext.orgはレート制限あり。1秒待機
    time.sleep(1)
    text = fetch_ctext(args.book)

    if not text.strip():
        print("警告: テキストが空でした。book IDを確認してください。")
        return

    save_text(text, args.output_name)


if __name__ == "__main__":
    main()

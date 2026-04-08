#!/usr/bin/env python3
"""
Gutendexからテキストを取得するスクリプト

使い方:
  python3 fetch_gutendex.py --search "homer iliad" --region europe --output-name homer_iliad
  python3 fetch_gutendex.py --id 2199 --region europe --output-name homer_iliad
"""

import argparse
import re
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
GUTENDEX_API = "https://gutendex.com/books/"
PG_TEXT_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"  # Gutendexが遅い場合の代替


def search_book(query: str):
    """Gutendexで作品を検索して最初のヒットを返す"""
    resp = requests.get(GUTENDEX_API, params={"search": query}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data["count"] == 0:
        return None
    return data["results"][0]


def get_book_by_id(book_id: int):
    """GutenbergのIDで作品を取得する"""
    resp = requests.get(f"{GUTENDEX_API}{book_id}/", timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def find_text_url(book: dict):
    """フォーマットリストからUTF-8テキストのURLを探す"""
    formats = book.get("formats", {})
    # 優先順位: plain text UTF-8 > plain text > HTML
    for key in ["text/plain; charset=utf-8", "text/plain", "text/html"]:
        if key in formats:
            return formats[key]
    return None


def strip_gutenberg_headers(text: str) -> str:
    """Project Gutenbergのヘッダー・フッターを除去する"""
    start_markers = [
        r"\*\*\* START OF THE PROJECT GUTENBERG",
        r"\*\*\* START OF THIS PROJECT GUTENBERG",
        r"START OF THE PROJECT GUTENBERG",
    ]
    end_markers = [
        r"\*\*\* END OF THE PROJECT GUTENBERG",
        r"\*\*\* END OF THIS PROJECT GUTENBERG",
        r"END OF THE PROJECT GUTENBERG",
    ]

    # ヘッダー除去
    for marker in start_markers:
        m = re.search(marker, text, re.IGNORECASE)
        if m:
            text = text[m.end():]
            # 最初の改行まで飛ばす
            text = text.lstrip("\r\n")
            break

    # フッター除去
    for marker in end_markers:
        m = re.search(marker, text, re.IGNORECASE)
        if m:
            text = text[:m.start()].rstrip()
            break

    return text.strip()


def download_and_save(book: dict, region: str, output_name: str) -> Path:
    """テキストをダウンロードしてlogsディレクトリに保存する"""
    url = find_text_url(book)
    if not url:
        raise ValueError(f"テキストURLが見つかりません: {book['title']}")

    print(f"ダウンロード中: {url}")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    # エンコーディング処理
    try:
        text = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        text = resp.content.decode("latin-1")

    text = strip_gutenberg_headers(text)

    out_dir = BASE_DIR / "logs" / region
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{output_name}.txt"
    out_path.write_text(text, encoding="utf-8")

    print(f"保存: {out_path} ({len(text):,} 文字)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Gutendexからテキスト取得")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", help="検索クエリ（例: 'homer iliad'）")
    group.add_argument("--id",     type=int, help="Gutenberg book ID")
    parser.add_argument("--region",      required=True, help="地域（europe/japan等）")
    parser.add_argument("--output-name", required=True, help="出力ファイル名（拡張子なし）")
    args = parser.parse_args()

    if args.search:
        book = search_book(args.search)
        if not book:
            print(f"見つかりませんでした: {args.search}")
            sys.exit(1)
        print(f"ヒット: {book['title']} / {', '.join(a['name'] for a in book['authors'])}")
    else:
        book = get_book_by_id(args.id)
        if not book:
            print(f"IDが見つかりません: {args.id}")
            sys.exit(1)

    download_and_save(book, args.region, args.output_name)


if __name__ == "__main__":
    main()

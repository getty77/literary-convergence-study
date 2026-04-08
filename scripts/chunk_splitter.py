#!/usr/bin/env python3
"""
長編テキストをチャンク分割する。

使い方:
  python3 chunk_splitter.py --region europe --work homer_odyssey
  python3 chunk_splitter.py --all          # 200k超の全作品を対象

出力: logs/{region}/.chunks/{work_key}/chunk_{n:02d}.txt
"""

import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"

CHUNK_SIZE = 200_000   # 1チャンクあたり200k文字
OVERLAP    =  20_000   # 前後チャンクとの重複量


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """段落境界を優先しながらテキストを分割する"""
    chunks = []
    start = 0
    total = len(text)

    while start < total:
        end = min(start + chunk_size, total)

        # 末尾でなければ段落境界（\n\n）を探して切る
        if end < total:
            boundary = text.rfind("\n\n", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary + 2  # \n\n の直後

        chunks.append(text[start:end])

        if end >= total:
            break
        start = end - overlap  # オーバーラップ分だけ戻る

    return chunks


def process_work(region: str, work_key: str) -> int:
    """1作品を分割して保存する。生成チャンク数を返す"""
    src = LOGS_DIR / region / f"{work_key}.txt"
    if not src.exists():
        print(f"[スキップ] テキストなし: {src}")
        return 0

    text = src.read_text(encoding="utf-8", errors="replace")
    if len(text) <= CHUNK_SIZE:
        print(f"[スキップ] 分割不要 ({len(text):,}字): {work_key}")
        return 0

    chunks = split_text(text, CHUNK_SIZE, OVERLAP)
    out_dir = LOGS_DIR / region / ".chunks" / work_key
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, chunk in enumerate(chunks, 1):
        out_path = out_dir / f"chunk_{i:02d}.txt"
        out_path.write_text(chunk, encoding="utf-8")

    print(f"[分割] {work_key}: {len(text):,}字 → {len(chunks)}チャンク")
    return len(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="")
    parser.add_argument("--work",   default="")
    parser.add_argument("--all",    action="store_true", help="200k超の全作品を対象")
    args = parser.parse_args()

    targets = []

    for region_dir in sorted(LOGS_DIR.iterdir()):
        if not region_dir.is_dir() or region_dir.name.startswith("_") or region_dir.name.startswith("."):
            continue
        region = region_dir.name
        if args.region and region != args.region:
            continue

        for txt in sorted(region_dir.glob("*.txt")):
            work_key = txt.stem
            if args.work and work_key != args.work:
                continue
            if args.all and txt.stat().st_size <= CHUNK_SIZE:
                continue
            targets.append((region, work_key))

    total_chunks = 0
    for region, work_key in targets:
        total_chunks += process_work(region, work_key)

    print(f"\n=== 完了 === {len(targets)}作品 / 合計{total_chunks}チャンク生成")


if __name__ == "__main__":
    main()

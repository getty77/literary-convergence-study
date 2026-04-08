#!/usr/bin/env python3
"""
チャンク別 _result.md を統合して1つの _result.md を生成する。

使い方:
  python3 merge_chunks.py --region europe --work homer_odyssey
  python3 merge_chunks.py --region europe  # リージョン内の全チャンク済み作品
"""

import os
import re
import time
import argparse
from pathlib import Path
from datetime import date

import anthropic

BASE_DIR       = Path(__file__).parent.parent
FRAGMENTS_DIR  = BASE_DIR / "fragments"

MODEL = "claude-sonnet-4-6"

MERGE_SYSTEM = """あなたは構造収束学ナレッジコンパイラです。
文学テキストを複数チャンクに分けて6ディストロ並列分析した結果群を受け取り、
1つの統合 _result.md を生成します。

## 基本フレーム

各チャンクの分析結果は「その文化圏のOSが記録したログ」の断片観測です。
統合後の _result.md は、そのOSの骨格（行動・判断・生存戦略・身心応答・社会機構・心理構造・超越応答）を
6ディストロで記述したものになります。

## 統合ルール

- 各ディストロについて、全チャンクのC-nエントリを読む
- 実質的に同一・類似の命題は1つに統合する（代表的な定式を残す）
- 別の構造として有効なものは別エントリとして保持する
- チャンク番号への言及は除去する
- C-nの番号は統合後に1から振り直す
- theory・tipsも同様に重複を統合する
- 統合後のcoreエントリはOSの骨格命題として成立する形式（「〜のとき〜が起きる」または「〜というOS構造を持つ」）に整える
- 3ディストロ以上で独立に同じ構造が出現した命題は、収束命題として優先的に保持する

## 出力フォーマット

以下のfrontmatterで始めること：

```
---
source: {WORK_KEY}
distro: 6-parallel
date: {TODAY}
pipeline_stage: full
region: {REGION}
pipeline_version: v3
chunks_merged: {CHUNK_COUNT}
---
```

以降は通常の _result.md フォーマット（## EK（経験知）〜 ## 宗教）で出力する。

## 判断ルール

- 苦悩・カタルシス・不条理などのフレームを前提にしない
- テキストから自然に出てきた構造のみを記述する
- 他の作品との比較は追加しない
"""


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    time.sleep(3)
    wait = 15
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            if attempt == 4:
                raise
            code = getattr(e, 'status_code', '?')
            print(f"    [{code}] API一時エラー。{wait}秒後にリトライ ({attempt+1}/5)...")
            time.sleep(wait)
            wait *= 2


def merge_work(client: anthropic.Anthropic, region: str, work_key: str, today: str) -> bool:
    chunks_dir = FRAGMENTS_DIR / region / ".chunks" / work_key
    if not chunks_dir.exists():
        print(f"[スキップ] チャンク結果なし: {work_key}")
        return False

    chunk_files = sorted(chunks_dir.glob("chunk_*_result.md"))
    if not chunk_files:
        print(f"[スキップ] チャンク結果なし: {work_key}")
        return False

    print(f"[統合] {work_key} ({len(chunk_files)}チャンク)...")

    # 全チャンクの内容を連結
    all_chunks = []
    for i, cf in enumerate(chunk_files, 1):
        content = cf.read_text(encoding="utf-8")
        all_chunks.append(f"=== チャンク {i}/{len(chunk_files)} ===\n{content}")

    user_prompt = f"""以下の{len(chunk_files)}チャンク分析結果を統合してください。

作品キー: {work_key}
リージョン: {region}
今日の日付: {today}

{''.join(chr(10) + c for c in all_chunks)}
"""

    system = MERGE_SYSTEM.replace("{WORK_KEY}", work_key) \
                         .replace("{TODAY}", today) \
                         .replace("{REGION}", region) \
                         .replace("{CHUNK_COUNT}", str(len(chunk_files)))

    result = call_claude(client, system, user_prompt)

    # markdown コードブロック除去
    result = re.sub(r'^```markdown\n', '', result, flags=re.MULTILINE)
    result = re.sub(r'^```\n?$', '', result, flags=re.MULTILINE)

    out_path = FRAGMENTS_DIR / region / f"{work_key}_result.md"
    out_path.write_text(result.strip() + "\n", encoding="utf-8")
    print(f"[保存] {out_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="")
    parser.add_argument("--work",   default="")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY が設定されていません")
        import sys; sys.exit(1)

    today  = date.today().isoformat()
    client = anthropic.Anthropic(api_key=api_key)

    success = skip = fail = 0

    for region_dir in sorted(FRAGMENTS_DIR.iterdir()):
        if not region_dir.is_dir() or region_dir.name.startswith("_"):
            continue
        region = region_dir.name
        if args.region and region != args.region:
            continue

        chunks_base = region_dir / ".chunks"
        if not chunks_base.exists():
            continue

        for work_dir in sorted(chunks_base.iterdir()):
            if not work_dir.is_dir():
                continue
            work_key = work_dir.name
            if args.work and work_key != args.work:
                continue

            try:
                if merge_work(client, region, work_key, today):
                    success += 1
                else:
                    skip += 1
            except Exception as e:
                print(f"[エラー] {work_key}: {e}")
                fail += 1

    print(f"\n=== 完了 === 成功:{success} / スキップ:{skip} / 失敗:{fail}")


if __name__ == "__main__":
    main()

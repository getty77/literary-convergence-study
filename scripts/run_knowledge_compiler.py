#!/usr/bin/env python3
"""
knowledge/literature/ 再コンパイルスクリプト（v2用）
fragments/{region}/{work}_result.md を読み込み、Anthropic Sonnetで
knowledge/literature/{work}.md を生成する。

使い方:
  python3 run_knowledge_compiler.py
  python3 run_knowledge_compiler.py --region japan
  python3 run_knowledge_compiler.py --work akutagawa_rashomon --region japan
  python3 run_knowledge_compiler.py --no-skip  # 既存ファイルも上書き
"""

import os
import sys
import re
import time
import argparse
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
OS_DIR = BASE_DIR.parent.parent
KNOWLEDGE_DIR = OS_DIR / "knowledge" / "literature"
FRAGMENTS_DIR = BASE_DIR / "fragments"

MODEL = "claude-sonnet-4-6"

SYSTEM = """あなたは構造収束学ナレッジコンパイラです。
文学作品の6ディストロ並列分析結果（_result.md）を読み込み、
knowledge/literature/ エントリを生成します。

## 出力フォーマット

```markdown
---
title: 作品タイトル（日本語または原語）
author: 著者名
year: 発表年（不明なら「—」）
region: リージョン名
source_distro: distros/literature-distro/fragments/{region}/{work}_result.md
distro_count: 6
ingested: YYYY-MM-DD
pipeline_version: v2
connections:
  - wiki/structural_convergence.md
---

# タイトル（著者、年）

## 収束観測

**収束命題**：（3ディストロ以上で独立して出現した構造を1文で記述）

| ディストロ | 観測したパターン |
|-----------|---------------|
| 経験知 | ... |
| 医療 | ... |
| 社会学 | ... |
| 精神分析 | ... |
| 文学分析 | ... |
| 宗教 | ... |

## 固有観測

各ディストロにしか出現しなかった命題があれば記述する。共通点に還元できない特異な観測。

## OS的含意

- 螺旋再帰線・位相境界面などのOS概念との接続（あれば）
- wiki/ 既存エントリとの関係（あれば）

## 関連

- [構造収束学](../../wiki/structural_convergence.md)
```

## 判断ルール

- 収束命題はテキストから自然に出てきた構造を記述する。苦悩・カタルシス・不条理などのフレームを前提にしない
- 苦悩が出てきていない作品で苦悩フレームを当てはめない
- 他の作品との比較セクションは追加しない
- pipeline_version: v2 を必ずfrontmatterに含める
- ingested日付は今日の日付を使う
- connections に happiness_resonance.md を自動追加しない（幸福との関連が実際にある場合のみ追加）
"""


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    time.sleep(3)
    wait = 15
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt == 4:
                raise
            print(f"    [429] レートリミット。{wait}秒後にリトライ ({attempt+1}/5)...")
            time.sleep(wait)
            wait *= 2


def get_work_meta(work_key: str, result_content: str) -> dict:
    """frontmatterからメタ情報を取得する"""
    meta = {"region": "unknown"}
    for line in result_content.split("\n"):
        if line.startswith("region:"):
            meta["region"] = line.split(":", 1)[1].strip()
            break
    return meta


def run_compiler_for_work(
    client: anthropic.Anthropic,
    work_key: str,
    region: str,
    result_path: Path,
    today: str,
) -> bool:
    """1作品分のknowledgeエントリを生成して保存する"""
    # 個別ディストロファイルはスキップ
    distro_suffixes = ["_ek", "_medical", "_sociology", "_psychoanalysis", "_literary", "_religion"]
    if any(work_key.endswith(s) for s in distro_suffixes):
        return False

    output_path = KNOWLEDGE_DIR / f"{work_key}.md"
    content = result_path.read_text(encoding="utf-8")

    rel_path = f"distros/literature-distro/fragments/{region}/{work_key}_result.md"

    user_prompt = f"""以下の_result.mdを読み込み、knowledge/literature エントリを生成してください。

作品キー: {work_key}
リージョン: {region}
ソースパス: {rel_path}
今日の日付: {today}

=== _result.md ===
{content[:8000]}
"""

    print(f"  [コンパイル] {work_key}...")
    result = call_claude(client, SYSTEM, user_prompt)

    # markdown コードブロックを除去
    result = re.sub(r'^```markdown\n', '', result, flags=re.MULTILINE)
    result = re.sub(r'^```\n?$', '', result, flags=re.MULTILINE)

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.strip() + "\n", encoding="utf-8")
    print(f"  [保存] {output_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="knowledge/literature/ 再コンパイル（v2）")
    parser.add_argument("--region", default="", help="対象リージョン（省略で全リージョン）")
    parser.add_argument("--work", default="", help="対象作品キー（省略で全作品）")
    parser.add_argument("--no-skip", action="store_true", help="既存ファイルも上書き")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    from datetime import date
    today = date.today().isoformat()

    client = anthropic.Anthropic(api_key=api_key)

    success = 0
    skip = 0
    fail = 0

    distro_suffixes = ["_ek", "_medical", "_sociology", "_psychoanalysis", "_literary", "_religion"]

    for region_dir in sorted(FRAGMENTS_DIR.iterdir()):
        if not region_dir.is_dir():
            continue
        region = region_dir.name
        if region.startswith("_"):
            continue
        if args.region and region != args.region:
            continue

        for result_file in sorted(region_dir.glob("*_result.md")):
            work_key = result_file.name.replace("_result.md", "")

            if any(work_key.endswith(s) for s in distro_suffixes):
                continue

            if args.work and work_key != args.work:
                continue

            output_path = KNOWLEDGE_DIR / f"{work_key}.md"
            if not args.no_skip and output_path.exists():
                print(f"[スキップ] {work_key}")
                skip += 1
                continue

            # v2のみ処理（pipeline_version: v2 を確認）
            content = result_file.read_text(encoding="utf-8")
            if "pipeline_version: v2" not in content[:500]:
                print(f"[スキップ] v2でない: {work_key}")
                skip += 1
                continue

            try:
                if run_compiler_for_work(client, work_key, region, result_file, today):
                    success += 1
                else:
                    skip += 1
            except Exception as e:
                print(f"[エラー] {work_key}: {e}")
                fail += 1

    print(f"\n=== 完了 === 成功:{success} / スキップ:{skip} / 失敗:{fail}")


if __name__ == "__main__":
    main()

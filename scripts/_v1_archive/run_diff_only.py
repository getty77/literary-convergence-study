#!/usr/bin/env python3
"""
DIFFのみ実行スクリプト（v2用）
Codexが生成した _result.md を読み込み、Anthropic Sonnetで DIFF を生成する。

使い方:
  python3 run_diff_only.py
  python3 run_diff_only.py --region japan
  python3 run_diff_only.py --work soseki_kokoro --region japan
  python3 run_diff_only.py --no-skip  # 既存DIFFも上書き
"""

import os
import sys
import re
import time
import argparse
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
DIFFS_DIR = BASE_DIR / "meta" / "diffs"
FRAGMENTS_DIR = BASE_DIR / "fragments"

DIFF_MODEL = "claude-sonnet-4-6"

DIFF_SYSTEM = """あなたはDIFFエージェントです。
6つのディストロ（EK/医療/社会学/精神分析/文学分析/宗教）のcore層を比較し、
収束命題と発散命題を抽出します。

収束命題: 複数ディストロで独立して出現した命題（言葉が違っても構造が同一）
発散命題: 特定ディストロにしか出ない命題

出力形式:

## コア収束命題（全ディストロまたは過半数で出現）
**Conv-N**: （命題タイトル）
- 命題: 「...」
- 収束ディストロ: EK / 医療 / ... （出現したもの）
- 収束率: N/6

## 部分収束命題（2〜3ディストロで出現）
**Partial-N**: （命題タイトル）
- 命題: 「...」
- 収束ディストロ: （出現したもの）

## レンズ固有命題
| ディストロ | 固有命題 |
|-----------|---------|
| EK | ... |
| 医療 | ... |
| 社会学 | ... |
| 精神分析 | ... |
| 文学分析 | ... |
| 宗教 | ... |

## 総評
- コア収束率: N/6
- 主な収束テーマ:
- 特徴的な発散点:

注意: 他の作品（特定の作家）との比較セクションは追加しないこと。この作品単独の構造を評価する。
"""


def extract_distro_sections(result_content: str) -> dict[str, str]:
    """_result.md から各ディストロのセクションを抽出する"""
    distro_map = {
        "EK（経験知）": "ek",
        "医療": "medical",
        "社会学": "sociology",
        "精神分析": "psychoanalysis",
        "文学分析": "literary",
        "宗教": "religion",
    }

    sections = {}
    current_distro = None
    current_lines = []

    for line in result_content.split("\n"):
        matched = False
        for header, key in distro_map.items():
            if line.strip() == f"## {header}":
                if current_distro:
                    sections[current_distro] = "\n".join(current_lines).strip()
                current_distro = key
                current_lines = []
                matched = True
                break
        if not matched and current_distro:
            current_lines.append(line)

    if current_distro:
        sections[current_distro] = "\n".join(current_lines).strip()

    return sections


def call_claude(client: anthropic.Anthropic, system: str, user: str) -> str:
    time.sleep(3)
    wait = 15
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=DIFF_MODEL,
                max_tokens=6000,
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


def run_diff_for_work(client: anthropic.Anthropic, work_key: str, region: str, result_path: Path) -> bool:
    """1作品分のDIFFを生成して保存する"""
    diff_path = DIFFS_DIR / f"{work_key}_6distro_diff.md"

    content = result_path.read_text(encoding="utf-8")
    sections = extract_distro_sections(content)

    if len(sections) < 3:
        print(f"  [警告] ディストロ抽出が不十分: {work_key} ({len(sections)}/6)")
        return False

    parts = []
    for distro_key, section_text in sections.items():
        parts.append(f"### {distro_key}\n{section_text}")
    combined = "\n\n---\n\n".join(parts)

    user_prompt = f"作品「{work_key}」の6ディストロ結果を比較してください:\n\n{combined}"

    print(f"  [DIFF生成] {work_key}...")
    diff_result = call_claude(client, DIFF_SYSTEM, user_prompt)

    DIFFS_DIR.mkdir(parents=True, exist_ok=True)
    header = f"---\nsource: {work_key}\ndistros: 6\nregion: {region}\npipeline_version: v2\n---\n\n"
    diff_path.write_text(header + diff_result + "\n", encoding="utf-8")
    print(f"  [保存] {diff_path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="DIFFのみ実行（v2）")
    parser.add_argument("--region", default="", help="対象リージョン（省略で全リージョン）")
    parser.add_argument("--work", default="", help="対象作品キー（省略で全作品）")
    parser.add_argument("--no-skip", action="store_true", help="既存DIFFも上書き")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    success = 0
    skip = 0
    fail = 0

    # fragments/ 以下の _result.md を収集
    for region_dir in sorted(FRAGMENTS_DIR.iterdir()):
        if not region_dir.is_dir():
            continue
        region = region_dir.name
        if region == "_archive":
            continue
        if args.region and region != args.region:
            continue

        for result_file in sorted(region_dir.glob("*_result.md")):
            work_key = result_file.name.replace("_result.md", "")

            # 個別ディストロファイル（{work}_{distro}_result.md）はスキップ
            distro_suffixes = ["_ek", "_medical", "_sociology", "_psychoanalysis", "_literary", "_religion"]
            if any(work_key.endswith(s) for s in distro_suffixes):
                continue

            if args.work and work_key != args.work:
                continue

            diff_path = DIFFS_DIR / f"{work_key}_6distro_diff.md"
            if not args.no_skip and diff_path.exists():
                print(f"[スキップ] {work_key}")
                skip += 1
                continue

            try:
                if run_diff_for_work(client, work_key, region, result_file):
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"[エラー] {work_key}: {e}")
                fail += 1

    print(f"\n=== 完了 === 成功:{success} / スキップ:{skip} / 失敗:{fail}")


if __name__ == "__main__":
    main()

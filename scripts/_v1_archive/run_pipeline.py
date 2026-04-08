#!/usr/bin/env python3
"""
世界文学パイプライン - メイン実行スクリプト

使い方:
  python3 run_pipeline.py --text logs/europe/homer_iliad.txt --work homer_iliad --region europe

処理フロー:
  1. テキストをバッチ分割
  2. 6ディストロ × Readerエージェント並列実行（Haiku）
  3. ディストロごとにMeetingエージェント（fragment統合）
  4. ディストロごとにDistillationエージェント（core/theory/tips振り分け）
  5. 6ディストロ横断DIFFエージェント（収束命題抽出）
"""

import os
import sys
import argparse
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DISTROS_DIR = BASE_DIR.parent

DISTRO_PERSONAS = {
    "ek":             DISTROS_DIR / "empty-kernel/core/ek-reading-persona.md",
    "medical":        DISTROS_DIR / "medical-distro/core/clinical-reading-persona.md",
    "sociology":      DISTROS_DIR / "sociology-distro/core/sociology-persona.md",
    "psychoanalysis": DISTROS_DIR / "psychoanalysis-distro/core/psychoanalysis-persona.md",
    "literary":       BASE_DIR / "core/literary-analysis-persona.md",
    "religion":       DISTROS_DIR / "religion-distro/core/religion-persona.md",
}

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
READER_MODEL  = "claude-haiku-4-5-20251001"   # Reader: Haiku（コスト最小）
MEETING_MODEL = "claude-haiku-4-5-20251001"    # Meeting: Haiku
DIFF_MODEL    = "claude-sonnet-4-6"            # DIFF: Sonnet（品質重視）
BATCH_CHARS   = 12000   # 1バッチあたりの文字数（≒3000〜4000トークン）
MAX_WORKERS   = 1       # 並列実行数（レートリミット対策で逐次処理）


# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────
def load_persona(distro_name: str) -> str:
    path = DISTRO_PERSONAS[distro_name]
    if not path.exists():
        raise FileNotFoundError(f"ペルソナファイルが見つかりません: {path}")
    return path.read_text(encoding="utf-8")


def split_into_batches(text: str, batch_chars: int = BATCH_CHARS) -> list[str]:
    """テキストを段落単位でバッチ分割する"""
    paragraphs = text.split("\n\n")
    batches = []
    current = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > batch_chars and current:
            batches.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)
    if current:
        batches.append("\n\n".join(current))
    return batches


def call_claude(client: anthropic.Anthropic, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Claude APIを呼び出す（事前スロットリング + 429時は指数バックオフでリトライ）"""
    # 事前スロットリング: 10,000トークン/分の制限に対して安全マージンを取る
    time.sleep(5)
    wait = 15  # 初回待機秒数
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt == 4:
                raise
            print(f"    [429] レートリミット。{wait}秒後にリトライ ({attempt+1}/5)...")
            time.sleep(wait)
            wait *= 2  # 15 → 30 → 60 → 120秒


# ─────────────────────────────────────────────
# Readerエージェント
# ─────────────────────────────────────────────
READER_SYSTEM_TEMPLATE = """{persona}

---

あなたはReaderエージェントです。
上記ペルソナの記述軸に従って、テキストバッチからfragment候補を抽出してください。

出力形式:
各候補を以下のフォーマットで出力してください:

**Fragment-N**:
- **観測**: （何が繰り返し出てきているか）
- **反復**: （場面の参照）
- **構造的有意性**: （なぜ重要か）
- **強さ**: 強い / 中程度 / 弱い

最後に必ず以下を出力してください:
**バッチサマリー**: （次バッチへ引き継ぐ重要パターン、200字以内）
"""

READER_USER_TEMPLATE = """
{prev_summary}

=== テキストバッチ {batch_num}/{total_batches} ===

{batch_text}
"""


def run_reader(client: anthropic.Anthropic, distro_name: str, batches: list[str]) -> tuple[str, list[str]]:
    """1ディストロ分のReader実行。全バッチのfragment候補リストを返す"""
    persona = load_persona(distro_name)
    system = READER_SYSTEM_TEMPLATE.format(persona=persona)

    all_fragments = []
    prev_summary = ""

    for i, batch in enumerate(batches):
        prev_block = f"【前バッチサマリー】\n{prev_summary}\n" if prev_summary else ""
        user = READER_USER_TEMPLATE.format(
            prev_summary=prev_block,
            batch_num=i + 1,
            total_batches=len(batches),
            batch_text=batch,
        )
        result = call_claude(client, READER_MODEL, system, user)
        all_fragments.append(result)

        # バッチサマリーを次バッチへ引き継ぐ
        for line in result.split("\n"):
            if line.startswith("**バッチサマリー**"):
                prev_summary = line.replace("**バッチサマリー**:", "").strip()
                break

    return distro_name, all_fragments


# ─────────────────────────────────────────────
# Meetingエージェント
# ─────────────────────────────────────────────
MEETING_SYSTEM = """あなたはMeetingエージェントです。
複数バッチのfragment候補を統合し、重複を除去・統合して最終的なfragmentリストを作成します。

判定基準:
- 昇格: 複数バッチで出現 or 単独でも構造的有意性が高い
- 却下: 内容が浅い、テキストの一時的言及のみ

出力形式:
## 昇格fragmentリスト
**F-N**: （内容）
- 観測: / 反復: / 構造的有意性: / 強さ:

## core候補
（強さ:強い かつ 反復が3回以上のもの）

## theory候補
（強さ:強い〜中程度 かつ 構造的有意性が高いもの）

## 却下リスト
（却下fragmentとその理由）
"""


def run_meeting(client: anthropic.Anthropic, distro_name: str, all_fragments: list[str]) -> str:
    """全バッチのfragment候補を統合する"""
    fragments_text = "\n\n---\n\n".join(
        f"### バッチ{i+1}\n{f}" for i, f in enumerate(all_fragments)
    )
    user = f"以下の全バッチfragment候補を統合してください:\n\n{fragments_text}"
    return call_claude(client, MEETING_MODEL, MEETING_SYSTEM, user, max_tokens=6000)


# ─────────────────────────────────────────────
# Distillationエージェント
# ─────────────────────────────────────────────
DISTILLATION_SYSTEM = """あなたはDistillationエージェントです。
Meeting結果のfragmentを core / theory / tips に振り分け、構造化します。

core: 最も収束力が高く、普遍性が疑われるもの（3〜5個）
  - 定式: 「〜のとき、〜が起きる」の形で命題化
theory: 条件付き・部分的な命題（複数）
tips: 具体的な観察手法・観測点（複数）

出力形式:

## core
**C-N**: （命題タイトル）
定式: 「...」

## theory
**T-N**: （命題）

## tips
**Tip-N**: （観察手法）
"""


def run_distillation(client: anthropic.Anthropic, distro_name: str, meeting_result: str) -> str:
    """Meeting結果をcore/theory/tipsに振り分ける"""
    user = f"以下のMeeting結果をcore/theory/tipsに振り分けてください:\n\n{meeting_result}"
    return call_claude(client, MEETING_MODEL, DISTILLATION_SYSTEM, user, max_tokens=4096)


# ─────────────────────────────────────────────
# DIFFエージェント
# ─────────────────────────────────────────────
DIFF_SYSTEM = """あなたはDIFFエージェントです。
6つのディストロ（EK/医療/社会学/精神分析/文学分析/宗教）のcore層を比較し、
収束命題と発散命題を抽出します。

収束命題: 複数ディストロで独立して出現した命題（言葉が違っても構造が同一）
発散命題: 特定ディストロにしか出ない命題

出力形式:

## コア収束命題（全ディストロまたは過半数で出現）
**Conv-N**: （命題）
- 収束ディストロ: EK / 医療 / ... （出現したもの）
- 収束率: N/6

## 部分収束命題（2〜3ディストロで出現）
**Partial-N**: （命題）
- 収束ディストロ: （出現したもの）

## レンズ固有命題
| ディストロ | 固有命題 |
|-----------|---------|
| EK | ... |
| 医療 | ... |
...

## 総評
- コア収束率: N/6
- 収束した命題の普遍性評価
"""


def run_diff(client: anthropic.Anthropic, work_name: str, distillation_results: dict[str, str]) -> str:
    """6ディストロのcore層を比較"""
    sections = []
    for distro, result in distillation_results.items():
        sections.append(f"### {distro}\n{result}")
    combined = "\n\n---\n\n".join(sections)
    user = f"作品「{work_name}」の6ディストロ結果を比較してください:\n\n{combined}"
    return call_claude(client, DIFF_MODEL, DIFF_SYSTEM, user, max_tokens=6000)


# ─────────────────────────────────────────────
# 保存
# ─────────────────────────────────────────────
def save_results(
    base_dir: Path,
    region: str,
    work_name: str,
    reader_results: dict[str, list[str]],
    meeting_results: dict[str, str],
    distillation_results: dict[str, str],
    diff_result: str,
):
    fragments_dir = base_dir / "fragments" / region
    diffs_dir = base_dir / "meta" / "diffs"
    fragments_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)

    # distroごとの結果を保存
    for distro in meeting_results:
        out_path = fragments_dir / f"{work_name}_{distro}_result.md"
        content = f"---\nsource: {work_name}\ndistro: {distro}\n---\n\n"
        content += "## Reader出力（全バッチ）\n\n"
        for i, r in enumerate(reader_results[distro]):
            content += f"### バッチ{i+1}\n{r}\n\n"
        content += "## Meeting結果\n\n" + meeting_results[distro] + "\n\n"
        content += "## Distillation結果\n\n" + distillation_results[distro] + "\n"
        out_path.write_text(content, encoding="utf-8")
        print(f"  保存: {out_path.name}")

    # DIFF結果を保存
    diff_path = diffs_dir / f"{work_name}_6distro_diff.md"
    diff_path.write_text(
        f"---\nsource: {work_name}\ndistros: 6\n---\n\n{diff_result}\n",
        encoding="utf-8",
    )
    print(f"  DIFF保存: {diff_path.name}")


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="世界文学パイプライン実行")
    parser.add_argument("--text",   required=True, help="テキストファイルのパス（logs/{region}/{work}.txt）")
    parser.add_argument("--work",   required=True, help="作品名（ファイル名に使用）")
    parser.add_argument("--region", required=True, help="地域（europe/japan/china/india/arabic/contemporary）")
    parser.add_argument("--distros", nargs="+",
                        default=list(DISTRO_PERSONAS.keys()),
                        help="使用するディストロ（デフォルト: 全6）")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY が設定されていません")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    text_path = Path(args.text)
    if not text_path.exists():
        print(f"エラー: テキストファイルが見つかりません: {text_path}")
        sys.exit(1)

    text = text_path.read_text(encoding="utf-8")
    batches = split_into_batches(text)
    print(f"作品: {args.work} | バッチ数: {len(batches)} | ディストロ: {args.distros}")

    # ── Step 1: Reader（並列）──────────────────
    print("\n[Step 1] Reader実行中...")
    reader_results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_reader, client, d, batches): d
            for d in args.distros
        }
        for future in as_completed(futures):
            distro = futures[future]
            try:
                name, fragments = future.result()
                reader_results[name] = fragments
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ {distro}: {e}")

    # ── Step 2: Meeting（並列）──────────────────
    print("\n[Step 2] Meeting実行中...")
    meeting_results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_meeting, client, d, reader_results[d]): d
            for d in reader_results
        }
        for future in as_completed(futures):
            distro = futures[future]
            try:
                meeting_results[distro] = future.result()
                print(f"  ✓ {distro}")
            except Exception as e:
                print(f"  ✗ {distro}: {e}")

    # ── Step 3: Distillation（並列）─────────────
    print("\n[Step 3] Distillation実行中...")
    distillation_results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_distillation, client, d, meeting_results[d]): d
            for d in meeting_results
        }
        for future in as_completed(futures):
            distro = futures[future]
            try:
                distillation_results[distro] = future.result()
                print(f"  ✓ {distro}")
            except Exception as e:
                print(f"  ✗ {distro}: {e}")

    # ── Step 4: DIFF────────────────────────────
    print("\n[Step 4] DIFF実行中...")
    diff_result = run_diff(client, args.work, distillation_results)
    print("  ✓ DIFF完了")

    # ── Step 5: 保存────────────────────────────
    print("\n[Step 5] 保存中...")
    save_results(
        BASE_DIR, args.region, args.work,
        reader_results, meeting_results, distillation_results, diff_result
    )

    print(f"\n完了: {args.work}")


if __name__ == "__main__":
    main()

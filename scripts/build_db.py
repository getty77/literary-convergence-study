#!/usr/bin/env python3
"""
fragments/{region}/{work}_result.md を読み込み、
db/works.json と db/observations.json を生成する。

使い方:
  python3 build_db.py
  python3 build_db.py --region europe
  python3 build_db.py --work homer_odyssey
"""

import json
import re
import argparse
from pathlib import Path
from datetime import date

BASE_DIR = Path(__file__).parent.parent
FRAGMENTS_DIR = BASE_DIR / "fragments"
DB_DIR = BASE_DIR / "db"

# セクションヘッダー名 → 正規化キー
DISTROS = {
    "EK（経験知）": "EK",
    "医療": "医療",
    "社会学": "社会学",
    "精神分析": "精神分析",
    "文学分析": "文学分析",
    "宗教": "宗教",
}

DISTRO_SUFFIX_SKIP = ["_ek", "_medical", "_sociology", "_psychoanalysis", "_literary", "_religion"]


def parse_frontmatter(text: str) -> dict:
    meta = {}
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta


def parse_distro_section(section_text: str, distro: str) -> dict:
    """1ディストロセクションから core/theory/tips を抽出する"""
    result = {"core": [], "theory": [], "tips": []}

    # core セクション
    core_match = re.search(r"### core\n(.*?)(?=###|\Z)", section_text, re.DOTALL)
    if core_match:
        core_text = core_match.group(1)
        # フォーマット1: **C-n**: title\n定式: formula（複数行）
        for m in re.finditer(
            r"\*\*C-(\d+)\*\*[：:]\s*(.+?)\n定式[：:]\s*「?(.+?)」?(?=\n\*\*C-|\n###|\Z)",
            core_text,
            re.DOTALL,
        ):
            result["core"].append({
                "id": f"C-{m.group(1)}",
                "title": m.group(2).strip(),
                "formula": m.group(3).strip(),
            })
        # フォーマット2: **C-n**: formula（単行、定式なし）
        if not result["core"]:
            for m in re.finditer(
                r"\*\*C-(\d+)\*\*[：:]\s*(.+?)(?=\n\*\*C-|\n###|\Z)",
                core_text,
                re.DOTALL,
            ):
                text = m.group(2).strip()
                result["core"].append({
                    "id": f"C-{m.group(1)}",
                    "title": text,
                    "formula": text,
                })

    # theory セクション
    theory_match = re.search(r"### theory\n(.*?)(?=###|\Z)", section_text, re.DOTALL)
    if theory_match:
        for m in re.finditer(r"T-(\d+)[：:]\s*(.+?)(?=\nT-|\n###|\Z)", theory_match.group(1), re.DOTALL):
            result["theory"].append({
                "id": f"T-{m.group(1)}",
                "text": m.group(2).strip(),
            })

    # tips セクション
    tips_match = re.search(r"### tips\n(.*?)(?=###|\Z)", section_text, re.DOTALL)
    if tips_match:
        for m in re.finditer(r"Tip-(\d+)[：:]\s*(.+?)(?=\nTip-|\n###|\Z)", tips_match.group(1), re.DOTALL):
            result["tips"].append({
                "id": f"Tip-{m.group(1)}",
                "text": m.group(2).strip(),
            })

    return result


def parse_result_file(path: Path):
    text = path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)

    if meta.get("pipeline_version") not in ("v2", "v3"):
        return None

    work_key = meta.get("source", path.stem.replace("_result", ""))
    region = meta.get("region", path.parent.name)

    distro_data = {}
    for header, key in DISTROS.items():
        # ディストロセクションを抽出（## {header}〜次の##まで）
        pattern = rf"## {re.escape(header)}\n(.*?)(?=\n## |\Z)"
        m = re.search(pattern, text, re.DOTALL)
        if m:
            distro_data[key] = parse_distro_section(m.group(1), key)
        else:
            distro_data[key] = {"core": [], "theory": [], "tips": []}

    return {
        "work_key": work_key,
        "region": region,
        "date": meta.get("date", ""),
        "pipeline_version": meta.get("pipeline_version", ""),
        "distros": distro_data,
    }


def build_works_json(parsed):
    works = []
    for p in parsed:
        core_counts = {d: len(p["distros"][d]["core"]) for d in DISTROS.values()}
        works.append({
            "work_key": p["work_key"],
            "region": p["region"],
            "date": p["date"],
            "core_count": core_counts,
            "total_core": sum(core_counts.values()),
        })
    return sorted(works, key=lambda x: (x["region"], x["work_key"]))


def build_observations_json(parsed):
    obs = []
    for p in parsed:
        for distro in DISTROS.values():
            for c in p["distros"][distro]["core"]:
                obs.append({
                    "work_key": p["work_key"],
                    "region": p["region"],
                    "distro": distro,
                    "obs_id": c["id"],
                    "title": c["title"],
                    "formula": c["formula"],
                })
    return obs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="")
    parser.add_argument("--work", default="")
    args = parser.parse_args()

    parsed = []
    errors = []

    for region_dir in sorted(FRAGMENTS_DIR.iterdir()):
        if not region_dir.is_dir():
            continue
        region = region_dir.name
        if region.startswith("_"):
            continue
        if args.region and region != args.region:
            continue

        for result_file in sorted(region_dir.glob("*_result.md")):
            work_key = result_file.stem.replace("_result", "")
            if any(work_key.endswith(s) for s in DISTRO_SUFFIX_SKIP):
                continue
            if args.work and work_key != args.work:
                continue

            try:
                data = parse_result_file(result_file)
                if data:
                    parsed.append(data)
                else:
                    print(f"[スキップ] v2でない: {work_key}")
            except Exception as e:
                print(f"[エラー] {work_key}: {e}")
                errors.append(work_key)

    works = build_works_json(parsed)
    observations = build_observations_json(parsed)

    DB_DIR.mkdir(exist_ok=True)

    (DB_DIR / "works.json").write_text(
        json.dumps(works, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DB_DIR / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n=== 完了 ===")
    print(f"  作品数: {len(works)}")
    print(f"  観測数 (core): {len(observations)}")
    print(f"  エラー: {len(errors)}")
    print(f"  出力: {DB_DIR}/")


if __name__ == "__main__":
    main()

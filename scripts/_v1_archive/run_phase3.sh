#!/usr/bin/env bash
# Phase 3 一括実行スクリプト
# Usage: bash run_phase3.sh
#
# 前提: ANTHROPIC_API_KEY が設定されていること
#   export ANTHROPIC_API_KEY="sk-ant-..."

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "エラー: ANTHROPIC_API_KEY が設定されていません"
  echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
  exit 1
fi

echo "=== Phase 3 パイプライン開始 ==="
echo ""

# ──────────────────────────────────────────────────────────────────
# Step 1: テキスト取得
# ──────────────────────────────────────────────────────────────────
echo "[テキスト取得] 開始..."

# 古代〜中世 / 西洋
python3 fetch_gutendex.py --search "homer iliad"      --region europe --output-name homer_iliad
python3 fetch_gutendex.py --search "homer odyssey"    --region europe --output-name homer_odyssey
python3 fetch_gutendex.py --search "sophocles oedipus" --region europe --output-name sophocles_oedipus
python3 fetch_gutendex.py --search "virgil aeneid"    --region europe --output-name virgil_aeneid
python3 fetch_gutendex.py --search "dante inferno"    --region europe --output-name dante_inferno

# 古代〜中世 / 中国
python3 fetch_ctext.py --book analects  --output-name confucius_analects
python3 fetch_ctext.py --book daodejing --output-name laozi_daodejing
python3 fetch_ctext.py --book zhuangzi  --output-name zhuangzi
python3 fetch_ctext.py --book shiji     --output-name sima_shiji
python3 fetch_ctext.py --book shijing   --output-name shijing

# 古代〜中世 / インド（GRETILはAPIなし。別途手動DLが必要）
echo "[インド] GRETILは手動DLが必要。logs/india/ にファイルを配置してください。"
echo "  対象: ramayana.txt / bhagavad_gita.txt / upanishad_brihadaranyaka.txt / panchatantra.txt / kalidasa_shakuntala.txt"

# 18世紀 / 西洋
python3 fetch_gutendex.py --search "voltaire candide"         --region europe --output-name voltaire_candide
python3 fetch_gutendex.py --search "defoe robinson crusoe"    --region europe --output-name defoe_robinson
python3 fetch_gutendex.py --search "swift gulliver"           --region europe --output-name swift_gulliver
python3 fetch_gutendex.py --search "goethe werther"           --region europe --output-name goethe_werther
python3 fetch_gutendex.py --search "rousseau confessions"     --region europe --output-name rousseau_confessions

# 18世紀 / 日本（青空文庫 - URLを直接指定）
python3 fetch_aozora.py --url "https://www.aozora.gr.jp/cards/000021/files/4367_ruby_15255.zip" --output-name ueda_ugetsu
# ※以下のURLは青空文庫のテキストファイルURL。事前に確認が必要
echo "[18世紀日本] 青空文庫URLを確認してから fetch_aozora.py を実行してください。"
echo "  対象: 好色一代男 / おくのほそ道 / 曽根崎心中 / 東海道中膝栗毛"

# 19世紀 / 西洋
python3 fetch_gutendex.py --search "dostoevsky crime punishment"  --region europe --output-name dostoevsky_crime
python3 fetch_gutendex.py --search "tolstoy anna karenina"        --region europe --output-name tolstoy_anna
python3 fetch_gutendex.py --search "flaubert madame bovary"       --region europe --output-name flaubert_bovary
python3 fetch_gutendex.py --search "dickens great expectations"   --region europe --output-name dickens_expectations
python3 fetch_gutendex.py --search "hugo les miserables"          --region europe --output-name hugo_miserables

# 19世紀 / 日本（青空文庫 URLは確認が必要）
echo "[19世紀日本] 青空文庫URLを確認してから実行してください。"
echo "  対象: 浮雲 / 当世書生気質 / たけくらべ / 五重塔 / 金色夜叉"

# 19世紀 / 中東（OpenITIから手動取得）
echo "[19世紀中東] OpenITIから手動取得が必要。logs/arabic/ にファイルを配置してください。"

# 20世紀初頭 / 西洋
echo "[20世紀西洋] 変身は取得済み。残り4作品を取得..."
python3 fetch_gutendex.py --search "proust swann"              --region europe --output-name proust_swann
python3 fetch_gutendex.py --search "joyce dubliners"           --region europe --output-name joyce_dubliners
python3 fetch_gutendex.py --search "woolf mrs dalloway"        --region europe --output-name woolf_dalloway
python3 fetch_gutendex.py --search "thomas mann magic mountain" --region europe --output-name mann_magic_mountain

# 20世紀初頭 / 日本（青空文庫）
echo "[20世紀日本] 青空文庫URLを確認してから実行してください。"
echo "  対象: こころ / 羅生門・藪の中 / 高瀬舟 / 銀河鉄道の夜 / 高野聖"

echo ""
echo "[テキスト取得] 自動取得完了。手動取得が必要なファイルを上記メッセージで確認してください。"

# ──────────────────────────────────────────────────────────────────
# Step 2: パイプライン実行
# ──────────────────────────────────────────────────────────────────
echo ""
echo "[パイプライン] 取得済みテキストを処理します..."

# テキストが存在するファイルのみ処理
LOGS_DIR="../logs"
WORK_DONE=0

for region_dir in "$LOGS_DIR"/*/; do
  region=$(basename "$region_dir")
  for txt_file in "$region_dir"*.txt; do
    [ -f "$txt_file" ] || continue
    work=$(basename "$txt_file" .txt)
    diff_file="../meta/diffs/${work}_6distro_diff.md"

    # DIFF済みはスキップ
    if [ -f "$diff_file" ]; then
      echo "  スキップ（処理済み）: $work"
      continue
    fi

    echo "  処理中: $work ($region)"
    python3 run_pipeline.py --text "$txt_file" --work "$work" --region "$region"
    WORK_DONE=$((WORK_DONE + 1))
    echo "  完了: $work"
  done
done

echo ""
echo "=== Phase 3 完了: ${WORK_DONE}作品処理 ==="

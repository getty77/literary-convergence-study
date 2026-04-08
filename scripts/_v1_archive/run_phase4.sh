#!/usr/bin/env bash
# Phase 4 一括実行スクリプト——関係性の苦悩補完
# Usage: bash run_phase4.sh
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

echo "=== Phase 4 パイプライン開始（関係性の苦悩補完）==="
echo ""

# ──────────────────────────────────────────────────────────────────
# Step 1: テキスト取得
# ──────────────────────────────────────────────────────────────────
echo "[テキスト取得] 開始..."

# 西洋 / Gutenberg（ID指定で確実に取得）
python3 fetch_gutendex.py --id 1342  --region europe --output-name austen_pride_prejudice
python3 fetch_gutendex.py --id 1260  --region europe --output-name bronte_c_jane_eyre
python3 fetch_gutendex.py --id 768   --region europe --output-name bronte_e_wuthering_heights
python3 fetch_gutendex.py --id 145   --region europe --output-name eliot_middlemarch
python3 fetch_gutendex.py --id 84    --region europe --output-name shelley_frankenstein
python3 fetch_gutendex.py --id 17162 --region europe --output-name rossetti_goblin_market
python3 fetch_gutendex.py --id 2626  --region europe --output-name browning_aurora_leigh

# 西洋 / Gutenberg（検索）
python3 fetch_gutendex.py --search "sappho poems"          --region europe --output-name sappho_poems
python3 fetch_gutendex.py --search "colette cheri"         --region europe --output-name colette_cheri

# 北米 / Gutenberg
python3 fetch_gutendex.py --id 160  --region contemporary --output-name chopin_awakening
python3 fetch_gutendex.py --id 284  --region contemporary --output-name wharton_house_of_mirth
python3 fetch_gutendex.py --id 1238 --region contemporary --output-name gilman_yellow_wallpaper

# アフリカ
python3 fetch_gutendex.py --id 1441 --region africa --output-name schreiner_african_farm

# ラテンアメリカ（スペイン語）
python3 fetch_gutendex.py --search "juana ines de la cruz" --region latin_america --output-name sor_juana_poemas

# 注意: 以下は Gutenberg 未収録または確認要
echo ""
echo "[要手動確認]"
echo "  #7  彼らの目は神を見ていた（Hurston, 1937）: Gutenberg未収録の可能性あり。手動でlogs/contemporary/hurston_their_eyes.txtに配置"
echo "  #8  燈台へ（Woolf, 1927）: Gutenberg収録状況を確認"
echo "  #12 シェリ（Colette）: フランス語版が見当たらない場合はスキップ"
echo "  #15 フアナ詩集: スペイン語版が取れない場合は英訳版で代替"
echo ""

# 日本 / 青空文庫（URLは要確認）
echo "[日本] 青空文庫のURLを確認してから以下を実行してください:"
echo "  枕草子（清少納言）:"
echo "    python3 fetch_aozora.py --url <URL> --output-name sei_makura_no_soshi"
echo "  みだれ髪（与謝野晶子）:"
echo "    python3 fetch_aozora.py --url <URL> --output-name yosano_midaregami"
echo "  恋愛論（与謝野晶子）:"
echo "    python3 fetch_aozora.py --url <URL> --output-name yosano_renairon"
echo ""

echo "[テキスト取得] 自動取得完了。手動取得が必要なファイルを上記で確認してください。"

# ──────────────────────────────────────────────────────────────────
# Step 2: パイプライン実行
# ──────────────────────────────────────────────────────────────────
echo ""
echo "[パイプライン] 取得済みテキストを処理します..."

LOGS_DIR="../logs"
WORK_DONE=0

for region_dir in "$LOGS_DIR"/*/; do
  region=$(basename "$region_dir")
  # _archiveはスキップ
  [ "$region" = "_archive" ] && continue
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
echo "=== Phase 4 完了: ${WORK_DONE}作品処理 ==="

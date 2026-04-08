#!/usr/bin/env bash
# run_codex_v2.sh — 文学ディストロ v2 パイプライン（Codex分析 + Anthropic DIFF）
#
# 使い方:
#   bash run_codex_v2.sh [--region europe] [--work homer_iliad] [--skip-existing]
#
# 前提:
#   - codex コマンドが PATH に通っていること（/Users/rac77/.npm-global/bin/codex）
#   - ANTHROPIC_API_KEY が設定されていること（DIFFステップ用）
#   - 作業ディレクトリ: distros/literature-distro/scripts/

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OS_DIR="$(cd "$BASE_DIR/../.." && pwd)"
CODEX_BIN="/Users/rac77/.npm-global/bin/codex"
PROMPT_TEMPLATE="$SCRIPT_DIR/codex_analysis_prompt.md"
LOG_FILE="$SCRIPT_DIR/run_codex_v2.log"

# オプション解析
TARGET_REGION=""
TARGET_WORK=""
SKIP_EXISTING=true
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) TARGET_REGION="$2"; shift 2 ;;
    --work) TARGET_WORK="$2"; shift 2 ;;
    --no-skip) SKIP_EXISTING=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "不明なオプション: $1"; exit 1 ;;
  esac
done

# ──────────────────────────────────────────────
# ログ関数
# ──────────────────────────────────────────────
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ──────────────────────────────────────────────
# 1作品分析関数（Codex）
# ──────────────────────────────────────────────
analyze_work() {
  local region="$1"
  local work_key="$2"
  local text_path="$BASE_DIR/logs/$region/$work_key.txt"
  local output_path="$BASE_DIR/fragments/$region/${work_key}_result.md"

  # テキストファイル存在確認
  if [ ! -f "$text_path" ]; then
    log "  [スキップ] テキストなし: $text_path"
    return 0
  fi

  # 既存チェック
  if [ "$SKIP_EXISTING" = true ] && [ -f "$output_path" ]; then
    log "  [スキップ] 既存: $work_key"
    return 0
  fi

  log "  [分析開始] $work_key ($region)"

  if [ "$DRY_RUN" = true ]; then
    log "  [DRY RUN] codex exec would run for: $work_key"
    return 0
  fi

  # プロンプト生成（テンプレート変数を置換・OS_DIR起点の相対パスを使用）
  local lit="distros/literature-distro"
  local prompt
  prompt=$(sed \
    -e "s|{{WORK_KEY}}|$work_key|g" \
    -e "s|{{TEXT_PATH}}|$lit/logs/$region/$work_key.txt|g" \
    -e "s|{{REGION}}|$region|g" \
    -e "s|{{OUTPUT_PATH}}|$lit/fragments/$region/${work_key}_result.md|g" \
    -e "s|{{WORK_TITLE}}|$work_key|g" \
    "$PROMPT_TEMPLATE")

  # Codex実行（作業ディレクトリをOS_DIRに設定してファイルアクセスを可能に）
  "$CODEX_BIN" exec \
    --sandbox workspace-write \
    -C "$OS_DIR" \
    "$prompt"

  if [ -f "$output_path" ]; then
    log "  [完了] $work_key → $output_path"
  else
    log "  [警告] 出力ファイルが生成されませんでした: $output_path"
  fi
}

# ──────────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────────
log "=== 文学ディストロ v2 パイプライン開始 ==="
log "  Codex: Reader/Meeting/Distillation"
log "  Anthropic: DIFF（別途 run_diff_only.py で実行）"
log ""

# 作品リスト収集
declare -a WORKS=()

for region_dir in "$BASE_DIR/logs"/*/; do
  region=$(basename "$region_dir")

  # _archive は除外
  [ "$region" = "_archive" ] && continue

  # リージョンフィルタ
  if [ -n "$TARGET_REGION" ] && [ "$region" != "$TARGET_REGION" ]; then
    continue
  fi

  for txt_file in "$region_dir"*.txt; do
    [ -f "$txt_file" ] || continue
    work_key=$(basename "$txt_file" .txt)

    # 作品フィルタ
    if [ -n "$TARGET_WORK" ] && [ "$work_key" != "$TARGET_WORK" ]; then
      continue
    fi

    WORKS+=("$region:$work_key")
  done
done

log "対象作品数: ${#WORKS[@]}"
log ""

# 逐次処理（レートリミット対策）
SUCCESS=0
SKIP=0
FAIL=0

for work_entry in "${WORKS[@]}"; do
  region="${work_entry%%:*}"
  work_key="${work_entry##*:}"

  text_path="$BASE_DIR/logs/$region/$work_key.txt"
  output_path="$BASE_DIR/fragments/$region/${work_key}_result.md"

  if [ "$SKIP_EXISTING" = true ] && [ -f "$output_path" ]; then
    log "[スキップ] $work_key"
    ((SKIP++)) || true
    continue
  fi

  if analyze_work "$region" "$work_key"; then
    ((SUCCESS++)) || true
  else
    log "[エラー] $work_key"
    ((FAIL++)) || true
  fi

  # Codexへの負荷軽減のため作品間に待機
  sleep 3
done

log ""
log "=== 完了 ==="
log "  成功: $SUCCESS / スキップ: $SKIP / 失敗: $FAIL"
log ""
log "次のステップ:"
log "  DIFF生成: python3 run_diff_only.py"
log "  メタ合成: python3 run_meta_synthesis.py"

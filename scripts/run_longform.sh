#!/usr/bin/env bash
# run_longform.sh — 長編テキストの全文分析パイプライン
#
# 使い方:
#   bash run_longform.sh --region europe --work homer_odyssey
#   bash run_longform.sh --all   # 200k超の全作品
#
# 前提:
#   - logs/{region}/{work_key}.txt に全文テキストが保存されていること
#   - codex コマンドが PATH に通っていること
#   - ANTHROPIC_API_KEY が設定されていること

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OS_DIR="$(cd "$BASE_DIR/../.." && pwd)"
CODEX_BIN="/Users/rac77/.npm-global/bin/codex"
PROMPT_TEMPLATE="$SCRIPT_DIR/codex_analysis_prompt.md"
LOG_FILE="$SCRIPT_DIR/run_longform.log"

TARGET_REGION=""
TARGET_WORK=""
ALL_MODE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) TARGET_REGION="$2"; shift 2 ;;
    --work)   TARGET_WORK="$2";   shift 2 ;;
    --all)    ALL_MODE=true;       shift ;;
    *) echo "不明なオプション: $1"; exit 1 ;;
  esac
done

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ──────────────────────────────────────────────
# Step 1: チャンク分割
# ──────────────────────────────────────────────
log "=== Step 1: チャンク分割 ==="

SPLIT_ARGS=""
[ -n "$TARGET_REGION" ] && SPLIT_ARGS="$SPLIT_ARGS --region $TARGET_REGION"
[ -n "$TARGET_WORK"   ] && SPLIT_ARGS="$SPLIT_ARGS --work $TARGET_WORK"
[ "$ALL_MODE" = true  ] && SPLIT_ARGS="$SPLIT_ARGS --all"

python3 "$SCRIPT_DIR/chunk_splitter.py" $SPLIT_ARGS | tee -a "$LOG_FILE"

# ──────────────────────────────────────────────
# Step 2: 各チャンクを codex で分析
# ──────────────────────────────────────────────
log "=== Step 2: チャンク分析（codex v2）==="

CHUNKS_FOUND=0

for region_dir in "$BASE_DIR/logs"/*/; do
  region=$(basename "$region_dir")
  [[ "$region" == _* ]] && continue
  [[ "$region" == .* ]] && continue
  [ -n "$TARGET_REGION" ] && [ "$region" != "$TARGET_REGION" ] && continue

  chunks_base="$region_dir/.chunks"
  [ ! -d "$chunks_base" ] && continue

  for work_dir in "$chunks_base"/*/; do
    [ ! -d "$work_dir" ] && continue
    work_key=$(basename "$work_dir")
    [ -n "$TARGET_WORK" ] && [ "$work_key" != "$TARGET_WORK" ] && continue

    out_base="$BASE_DIR/fragments/$region/.chunks/$work_key"
    mkdir -p "$out_base"

    for chunk_file in "$work_dir"chunk_*.txt; do
      [ -f "$chunk_file" ] || continue
      chunk_name=$(basename "$chunk_file" .txt)
      out_path="$out_base/${chunk_name}_result.md"

      # 既存チェック
      if [ -f "$out_path" ]; then
        log "  [スキップ] 既存: $work_key/$chunk_name"
        continue
      fi

      log "  [分析] $work_key/$chunk_name"
      CHUNKS_FOUND=$((CHUNKS_FOUND + 1))

      lit="distros/literature-distro"
      prompt=$(sed \
        -e "s|{{WORK_KEY}}|${work_key}_${chunk_name}|g" \
        -e "s|{{TEXT_PATH}}|$lit/logs/$region/.chunks/$work_key/${chunk_name}.txt|g" \
        -e "s|{{REGION}}|$region|g" \
        -e "s|{{OUTPUT_PATH}}|$lit/fragments/$region/.chunks/$work_key/${chunk_name}_result.md|g" \
        -e "s|{{WORK_TITLE}}|$work_key (${chunk_name})|g" \
        "$PROMPT_TEMPLATE")

      "$CODEX_BIN" exec \
        --sandbox workspace-write \
        -C "$OS_DIR" \
        "$prompt" | tee -a "$LOG_FILE"
    done
  done
done

log "チャンク分析完了 (${CHUNKS_FOUND}チャンク処理)"

# ──────────────────────────────────────────────
# Step 3: チャンク結果を統合
# ──────────────────────────────────────────────
log "=== Step 3: チャンク統合（Anthropic Sonnet）==="

MERGE_ARGS=""
[ -n "$TARGET_REGION" ] && MERGE_ARGS="$MERGE_ARGS --region $TARGET_REGION"
[ -n "$TARGET_WORK"   ] && MERGE_ARGS="$MERGE_ARGS --work $TARGET_WORK"

# APIキーをzshrcから直接取得（bash互換）
if [ -z "$ANTHROPIC_API_KEY" ]; then
  export ANTHROPIC_API_KEY=$(grep -o 'ANTHROPIC_API_KEY="[^"]*"' ~/.zshrc 2>/dev/null | tail -1 | cut -d'"' -f2)
fi
python3 "$SCRIPT_DIR/merge_chunks.py" $MERGE_ARGS | tee -a "$LOG_FILE"

log "=== 全工程完了 ==="

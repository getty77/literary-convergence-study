# literary-convergence-study

10文化圏の古典文学テキストから観測される行動骨格とその収束構造

**リポジトリ**: https://github.com/getty77/literary-convergence-study

---

## 概要

本研究は、紀元前2100年頃から19世紀までの10文化圏の古典文学テキストを対象に、
6視点の並列分析によって各文化圏の思考・行動の骨格構造を抽出する探索的記述研究です。

- **対象**: 著作権切れ（パブリックドメイン）テキスト10作品
- **分析視点**: 行動・身体・社会・心理・語り・超越の6視点
- **コア命題**: 545件
- **収束命題**: 40件（3文化圏以上で独立出現した構造）

LLM学習データからの補完は行っていません。全て実テキストを入力として使用しています。

---

## 対象作品

| 作品 | 文化圏 | 年代 |
|-----|--------|------|
| ギルガメッシュ叙事詩 | メソポタミア | 紀元前2100頃 |
| オデュッセイア | ギリシャ | 紀元前800頃 |
| 神曲 地獄篇 | 中世ヨーロッパ | 1308〜1320 |
| 罪と罰 | ロシア | 1866 |
| 源氏物語 | 日本 | 1008頃 |
| 論語 | 中国 | 紀元前400頃 |
| バガヴァッド・ギーター | インド | 紀元前200頃 |
| 千夜一夜物語 | アラビア | 8〜14世紀 |
| ポポル・ヴフ | マヤ | 1550頃 |
| ポリネシア神話集 | オセアニア | 1855記録 |

---

## ディレクトリ構成

```
├── corpus/           原典テキスト（PD）
├── fragments/        各作品の6視点分析結果
│   ├── {region}/
│   │   ├── {work}_result.md      統合分析結果
│   │   └── .chunks/              チャンク別分析結果
├── db/
│   ├── works.json                作品別コア命題数
│   └── observations.json         全545命題のフラットDB
├── scripts/          分析パイプライン
│   ├── chunk_splitter.py         全文チャンク分割
│   ├── run_longform.sh           長編用パイプライン
│   ├── merge_chunks.py           チャンク統合
│   ├── build_db.py               DBフラット化
│   └── codex_analysis_prompt.md  6視点分析プロンプト
└── meta/             研究手法・論文草稿
    ├── research_method_v3.md     実験手法定義
    ├── paper_draft_v1.md         論文草稿
    └── section4_convergence_raw.md  収束命題原データ
```

---

## 分析パイプライン

```
corpus/{region}/{work}.txt
    ↓ chunk_splitter.py（200k字/チャンク、20k字オーバーラップ）
corpus/{region}/.chunks/{work}/chunk_n.txt
    ↓ Codex（codex_analysis_prompt.md）
fragments/{region}/.chunks/{work}/chunk_n_result.md
    ↓ merge_chunks.py（Anthropic Claude Sonnet）
fragments/{region}/{work}_result.md
    ↓ build_db.py
db/works.json / db/observations.json
```

### 必要環境

```bash
pip install anthropic
npm install -g @openai/codex   # Codexが必要
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
```

### 実行例

```bash
# 単一作品（200k字以下）
codex exec -C . "scripts/codex_analysis_prompt.md の指示に従いgil..."

# 長編（200k字超）
bash scripts/run_longform.sh --region middle_east --work arabian_nights

# チャンク統合
python3 scripts/merge_chunks.py --region middle_east --work arabian_nights

# DB構築
python3 scripts/build_db.py
```

---

## 主要な収束命題

文化的接触が考えにくい組み合わせ（例: ギリシャ×マヤ×メソポタミア）で
独立出現した構造のうち、出現文化圏数が多いものを示します。

| 命題 | 出現文化圏数 |
|-----|------------|
| 行動停止 → 外部権威による再起動 | 6 |
| 役割逸脱の連鎖崩壊 | 6 |
| 身体が認知に先行して反応する | 6 |
| 周縁的他者の段階的編入 | 6 |
| 私的損傷の制度的拡大カスケード | 6 |

収束命題の全詳細は `meta/section4_convergence_raw.md` を参照してください。

---

## 研究上の限界

- 翻訳テキストには翻訳者の解釈が混入する
- N=10の探索的規模であり、命題の統計的検証は今後の課題
- 分析装置自体がLLMであり、訓練データのバイアスが構造抽出に影響する可能性がある
- 現存する「正典」は権力・制度による選別を経ている

---

## ライセンス

原典テキストはパブリックドメイン（著作権切れ）です。
分析結果・スクリプト・論文草稿は [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) で公開します。

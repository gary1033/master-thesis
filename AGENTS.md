# AGENTS.md

## 專案概述

碩論題目暫定：TestRefiner - Context-Aware LLM-Based Test Generation via Bidirectional Slicing and Iterative Refinement

基於 TestWeaver (ICSE 2026, Le et al.) 延伸，兩個核心研究方向：
1. **Bidirectional Slicing**：forward + backward slicing 提供完整上下游 context
2. **Iterative Feedback-Driven Refinement**：多輪回饋 + 失敗分類 + adaptive test selection

## 研究規範

### Benchmark & Baselines
- Benchmark: CodaMosa (CM) suite — 27 Python projects (from 34 candidates), 486 modules, ~100K+ LOC
- Baselines: TestWeaver, CoverUp, CodaMosa
- Metrics: line coverage, branch coverage, line+branch coverage, token cost, runtime

### LLM 策略
- 主實驗: DeepSeek V3.2 API ($0.28/$0.42 per M tokens)
- 開發 debug: 本地 Qwen2.5-Coder-7B (RTX 3060 Ti 8GB)
- 備援: MacBook M3 Air 16GB + Qwen2.5-Coder-14B
- API 設定: OpenAI-compatible, 設定 .env 中 OPENAI_API_KEY + OPENAI_BASE_URL

### 消融實驗配置（5 個）
1. TestRefiner（完整）
2. TestWeaver baseline
3. CoverUp baseline
4. w/o Forward Slicing（驗證方向一）
5. w/o Iterative Refinement（驗證方向二）

### Pilot 計畫
- Projects: PySnooper (4 modules), flutils (9 modules), typesystem (10 modules, CC>350)
- 5 configs x 3 projects, 預估 DeepSeek API 費用 $13-20

## 進度追蹤規則

**每次進行研究或實驗相關工作時，必須：**
1. 更新 Obsidian 的「實驗進度追蹤」筆記（日期 + 做了什麼 + 結果）
2. 如果有新的論文閱讀，更新碩論參考資料索引
3. 如果有新的發現或決策改變，更新對應的方向筆記
4. commit 前先確認 .gitignore 排除敏感檔案

## 實驗監控規則(on-demand 載入)

**觸發條件**(符合其一才載入 `C:\Projects\master-thesis\experimentrules.md`):
- 使用者要求「跑實驗 / 啟動 testweaver / ablate / TestRefiner pipeline」
- 使用者要求「回報進度 / 狀態 / coverage」
- Monitor task 發出 `<task-notification>` 事件

**觸發後的必要動作**:
1. 讀取 `experimentrules.md`
2. 依其中定義的格式產出回報(即時總覽表 + 每個 .py 檔一張 Phase 表 + 5 段解說)
3. 每次回報前執行 § 4 SOP 拿到真實 phase(不可只信 status.py)
4. 符合 § 5 條件時主動示警
5. 遵守 § 6:實驗預設 foreground 執行,不要盲目丟背景

**不要**在非實驗相關 turn 載入 experimentrules.md,避免 context 過大。

## Obsidian Vault 位置

- Vault: `C:\Users\gary1\OneDrive\桌面\obsidian\rui-lin\`
- 碩論筆記: `碩論參考資料/` 資料夾下
- 主要筆記:
  - `碩論研究路徑與大綱.md` — 總覽 MOC
  - `研究方向一：雙向切片 Bidirectional Slicing.md`
  - `研究方向二：迭代回饋精煉 Iterative Feedback Refinement.md`
  - `消融實驗設計.md`
  - `實驗進度追蹤.md`
  - `碩論研究方向思考角度.md` — 新穎性辯護
  - `Panta vs TestRefiner 競爭者分析.md`

## 目錄結構

```
Codex heartbeat/
├── AGENTS.md              ← 本檔案
├── .env                   ← API keys（不上傳 git）
├── .gitignore
├── TestWeaver/            ← TestWeaver 原版 repo
│   ├── scripts/
│   │   ├── testweaver.py  ← 主 pipeline
│   │   ├── ablate.py      ← 消融實驗
│   │   ├── data_utils.py  ← closest test selection
│   │   ├── utils/codetransform/
│   │   │   ├── slicing.py ← backward slicing（需擴展 forward）
│   │   │   ├── utils1.py  ← ExecutionOrderAnalyzer（SDG 建構）
│   │   │   └── next.py    ← execution in-lines
│   │   ├── get_conditional_line.py ← 控制流分析
│   │   └── prompt/        ← prompt templates
│   └── codamosa/replication/test-apps/ ← 27 個 benchmark projects
├── *.pdf                  ← 參考論文 PDF
└── TestRefiner/             ← 你的改進版本（待建立）
```

## Git Workflow

- Remote: git@github.com:gary1033/master-thesis.git
- 在 Windows (3060 Ti) 開發 → push → MacBook pull 跑實驗
- .gitignore 排除: __pycache__, .env, output/, *.pyc, node_modules/, .DS_Store
- TestWeaver/ 目錄: 作為 git submodule 管理
- codamosa test-apps/: 不上傳（太大），各機器獨立 clone

## 關鍵論文

- TestWeaver (ICSE 2026) — 基礎論文
- Panta (ICSE 2026) — 競爭者，迭代式混合分析
- CoverUp (2024) — baseline
- CodaMOSA (ICSE 2023) — benchmark + baseline
- LLMLOOP (ICSME 2025) — 迭代回饋支撐
- Cottontail (IEEE S&P 2026) — concolic + LLM
- HITS (2024), SymPrompt (2024), exLong (2025) — slicing / prompting 相關

## 時程

| 月份 | 工作 |
|------|------|
| 4月 | 環境設定 + 方向一實作 + pilot |
| 5月 | 方向二實作 + 整合測試 |
| 6月 | 調參 + pilot 完成 + 教授討論 |
| 7月 | 完整 27 projects 實驗 + 消融實驗 |
| 8月 | 數據分析 + PPT |
| 9月 | 論文撰寫 |

# TestRefiner

Context-Aware LLM-Based Test Generation via Bidirectional Slicing and Iterative Refinement.

延伸自 TestWeaver (ICSE 2026)，兩個方向：
1. **Bidirectional Slicing** — backward + forward slicing
2. **Iterative Feedback-Driven Refinement** — 多輪回饋 + 失敗分類 + adaptive test selection

## Structure

```
TestRefiner/
├── scripts/
│   ├── testrefiner.py           # 主 pipeline
│   ├── ablate.py                # 消融實驗 driver（5 configs）
│   ├── utils/
│   │   └── codetransform/
│   │       ├── slicing.py       # backward + forward slicing
│   │       └── sdg.py           # SDG 建構（forward edges）
│   ├── refinement/              # 方向二：迭代回饋
│   │   ├── loop.py              # 3-round iterative loop
│   │   ├── classify.py          # failure classification
│   │   ├── divergence.py        # divergence analysis
│   │   └── selection.py         # multi-signal adaptive selection
│   ├── prompt/                  # prompt templates
│   └── output/                  # 執行結果（gitignored）
├── tests/                       # 單元測試
└── docs/                        # 設計文件
```

## Setup

從專案根目錄執行：

```bash
cd C:/Projects/master-thesis
.venv/Scripts/activate   # or source .venv/Scripts/activate in bash
python TestRefiner/scripts/testrefiner.py ...
```

`.env` 位於 repo root（`master-thesis/.env`），需設定 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `MODEL_NAME`。

## Config 對照

| Config | Forward Slicing | Iterative | Failure Classify | Adaptive Select |
|--------|:---:|:---:|:---:|:---:|
| C1 TestRefiner (full) | ✅ | ✅ | ✅ | ✅ |
| C2 w/o Forward | ❌ | ✅ | ✅ | ✅ |
| C3 w/o Iterative | ✅ | ❌ | ❌ | ❌ |
| C4 w/o Failure Class | ✅ | ✅ | ❌ | ✅ |
| C5 TestWeaver baseline | ❌ | ❌ | ❌ | ❌ |

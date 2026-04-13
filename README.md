# WebWeaver — Master's Thesis Project

> 基於 [TestWeaver (ICSE 2026)](https://github.com/FSoft-AI4Code/TestWeaver) 延伸，研究如何提升 LLM-based test generation 的 code coverage。

## 研究概述

**題目**：WebWeaver - Context-Aware LLM-Based Test Generation via Bidirectional Slicing and Iterative Refinement

**兩個核心方向**：
1. **Bidirectional Slicing** — 在 TestWeaver 的 backward slicing 基礎上加入 forward slicing，讓 LLM 同時理解目標行的上游依賴（怎麼到達）和下游影響（到達後會發生什麼）
2. **Iterative Feedback-Driven Refinement** — 將 TestWeaver 的 single-shot Phase 3 改為多輪回饋，包含分歧點分析、失敗分類、adaptive test selection

---

## 環境設定（Setup）

### Step 1：Clone 本 repo（含 TestWeaver submodule）

```bash
# clone repo，--recurse-submodules 會自動把 TestWeaver submodule 一起拉下來
git clone --recurse-submodules git@github.com:gary1033/master-thesis.git
cd master-thesis
```

> **這一步做了什麼**：
> - 下載本 repo（包含 CLAUDE.md 研究規範、參考論文 PDF）
> - 自動 clone TestWeaver 原版程式碼（作為 git submodule 管理）
> - 自動 clone CodaMosa submodule 的**目錄結構**（但 test-apps 裡的 benchmark projects 需要 Step 4 另外下載）

如果 submodule 沒有自動初始化，手動執行：

```bash
git submodule update --init --recursive
```

### Step 2：安裝 Python 依賴

```bash
# 確認 Python 版本（需要 3.10+）
python --version

# 安裝 TestWeaver 的依賴
cd TestWeaver
pip install -r requirements.txt
cd ..
```

> **這一步做了什麼**：
> - 安裝 TestWeaver 需要的 Python 套件（openai, pytest, slipcover 等）
> - slipcover 是用來測量 code coverage 的工具

### Step 3：設定 LLM API

```bash
# 在 TestWeaver 目錄下建立 .env 檔案
cat > TestWeaver/.env << 'EOF'
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.deepseek.com/v1
EOF
```

> **這一步做了什麼**：
> - 設定 LLM API 的金鑰和端點
> - TestWeaver 使用 OpenAI-compatible 介面，**API 和本地模型的接口完全相同**，只需改 .env
> - 三種模式切換方式（只改 .env，程式碼不用動）：
>
> | 模式 | OPENAI_API_KEY | OPENAI_BASE_URL |
> |------|---------------|-----------------|
> | DeepSeek API | 你的 DeepSeek key | `https://api.deepseek.com/v1` |
> | 本地 Ollama | `ollama`（隨意填） | `http://localhost:11434/v1` |
> | OpenAI GPT | 你的 OpenAI key | `https://api.openai.com/v1` |
>
> - DeepSeek API：到 https://platform.deepseek.com/ 註冊取得 API key
> - 本地 Ollama：先安裝 [Ollama](https://ollama.com/)，再 `ollama pull qwen2.5-coder:7b`
>
> **注意**：除了 .env 外，還需要修改程式碼中 hardcoded 的 model name（`deepseek-v3-0324`）。
> 本地 Ollama 模型名稱格式為 `qwen2.5-coder:7b`。

#### 本地模型推薦

| 硬體 | 推薦模型 | 安裝指令 | HumanEval |
|------|---------|---------|-----------|
| RTX 3060 Ti 8GB | Qwen2.5-Coder-7B | `ollama pull qwen2.5-coder:7b` | ~72% |
| MacBook M3 Air 16GB | Qwen2.5-Coder-14B | `ollama pull qwen2.5-coder:14b` | ~85% |

### Step 4：下載 CodaMosa Benchmark Projects

CodaMosa 原始候選有 34 個 Python 專案，經篩選後最終 benchmark 為 **27 個 projects / 486 個 modules**。
篩選掉的 7 個（fastapi, keras, luigi, matplotlib, pandas, scrapy, spaCy）因 timeout、100% 初始覆蓋率等原因排除。
test-apps 目錄裡可能包含這 7 個，但實驗只使用下列 27 個。

```bash
cd TestWeaver/codamosa/replication/test-apps

# === Pilot 必須的 3 個 projects ===
# PySnooper：Python debugger 工具（4 modules，低複雜度，用來驗證系統能跑通）
git clone --depth 1 https://github.com/cool-RR/PySnooper.git PySnooper

# flutils：Python 工具函式庫（9 modules，中複雜度，主要觀察改善指標）
git clone --depth 1 https://github.com/ccarballolozano/flutils.git flutils

# typesystem：資料驗證框架（10 modules，CC>350 高複雜度，TestWeaver 論文 Figure 6 案例）
git clone --depth 1 https://github.com/encode/typesystem.git typesystem

# === 完整實驗需要的其餘 projects ===
git clone --depth 1 https://github.com/ansible/ansible.git ansible
git clone --depth 1 https://github.com/KmolYuan/apimd.git apimd
git clone --depth 1 https://github.com/psf/black.git black
git clone --depth 1 https://github.com/realpython/codetiming.git codetiming
git clone --depth 1 https://github.com/cookiecutter/cookiecutter.git cookiecutter
git clone --depth 1 https://github.com/lidatong/dataclasses-json.git dataclasses-json
git clone --depth 1 https://github.com/rr-/docstring_parser.git docstring_parser
git clone --depth 1 https://github.com/huzecong/flutes.git flutes
git clone --depth 1 https://github.com/httpie/cli.git httpie
git clone --depth 1 https://github.com/PyCQA/isort.git isort
git clone --depth 1 https://github.com/lk-geimfari/mimesis.git mimesis
git clone --depth 1 https://github.com/nvbn/py-backwards.git py-backwards
git clone --depth 1 https://github.com/antelk/pymonet.git pyMonet
git clone --depth 1 https://github.com/vst/pypara.git pypara
git clone --depth 1 https://github.com/python-semantic-release/python-semantic-release.git python-semantic-release
git clone --depth 1 https://github.com/daveoncode/python-string-utils.git python-string-utils
git clone --depth 1 https://github.com/jmervine/pytutils.git pytutils
git clone --depth 1 https://github.com/sanic-org/sanic.git sanic
git clone --depth 1 https://github.com/feluxe/sty.git sty
git clone --depth 1 https://github.com/nvbn/thefuck.git thefuck
git clone --depth 1 https://github.com/thonny/thonny.git thonny
git clone --depth 1 https://github.com/tornadoweb/tornado.git tornado
git clone --depth 1 https://github.com/tqdm/tqdm.git tqdm
git clone --depth 1 https://github.com/ytdl-org/youtube-dl.git youtube-dl

cd ../../../..
```

> **這一步做了什麼**：
> - `--depth 1` = 只下載最新版本（不下載完整歷史，節省空間和時間）
> - 這 27 個 project 是 CodaMosa (ICSE 2023) 定義的標準 benchmark
> - 所有 486 個測試 module 的對應關係記錄在 `codamosa/replication/scripts/modules_base_and_name.csv`
> - **注意**：這些 project 不會被推上 git（已在 .gitignore 排除），每台電腦需要獨立 clone

---

## 執行 TestWeaver（Baseline）

### 跑單一 module

```bash
cd TestWeaver/scripts
export PYTHONPATH=$(pwd)

# sample_id 對應 modules_base_and_name.csv 中的行號（0-indexed）
# 例如 id=21 對應 tqdm 的某個 module
export sample_id=21
python testweaver.py --test-index $sample_id
```

> **這一步做了什麼**：
> - 對指定的 module 執行 TestWeaver 的完整 3 階段 pipeline：
>   1. **Seed Generation** — 用 LLM 生成初始測試案例
>   2. **Slicing + Generation** — 對未覆蓋行做 backward slicing，再用 LLM 生成目標測試
>   3. **Feedback + Re-generation** — 找最近測試案例 + execution in-lines，讓 LLM 重試
> - 結果輸出到 `output/cm/` 目錄

### 跑消融實驗

```bash
cd TestWeaver/scripts
export PYTHONPATH=$(pwd)
export sample_id=21
python ablate.py --test-index $sample_id
```

> **這一步做了什麼**：
> - 對同一個 module 跑 5 種配置：
>   1. 有 slicing
>   2. 無 slicing
>   3. 無 execution in-lines
>   4. 無 closest test
>   5. 完整 TestWeaver
> - 用來比較各組件的貢獻

---

## 執行 CoverUp Baseline

```bash
# 需要 Docker
cd TestWeaver/scripts/baselines/coverup
docker load -i docker/coverup-runner.tar
python3 scripts/eval_coverup.py --config deepseek-v3 --suite cm --package tqdm
```

> **這一步做了什麼**：
> - 在 Docker 容器中跑 CoverUp（另一個 baseline 工具）
> - `--package tqdm` 指定只跑 tqdm 這個 project（可改成其他 project）
> - 結果輸出到 `scripts/baselines/coverup/output/`

---

## 目錄結構

```
master-thesis/
├── README.md              ← 本檔案
├── CLAUDE.md              ← Claude Code 研究規範（研究目標、實驗規範、進度追蹤規則）
├── .env                   ← API keys（不上傳 git）
├── .gitignore             ← 排除 __pycache__, .env, output/, test-apps/
├── *.pdf                  ← 23 篇參考論文
│
├── TestWeaver/            ← [git submodule] TestWeaver 原版程式碼
│   ├── scripts/
│   │   ├── testweaver.py  ← 主 pipeline（Phase 1-3）
│   │   ├── ablate.py      ← 消融實驗腳本
│   │   ├── data_utils.py  ← find_closest_test()（closest test 選擇）
│   │   ├── get_conditional_line.py  ← 控制流分析（哪些 if/while 控制目標行）
│   │   ├── utils/codetransform/
│   │   │   ├── slicing.py     ← backward_slicing()（需擴展 forward）
│   │   │   ├── utils1.py      ← ExecutionOrderAnalyzer（建構 SDG 程式相依圖）
│   │   │   └── next.py        ← execute_and_trace()（execution in-lines）
│   │   └── prompt/            ← LLM prompt templates
│   └── codamosa/replication/
│       ├── scripts/modules_base_and_name.csv  ← 486 個 module 的對應表
│       └── test-apps/     ← 27 個 benchmark projects（各機器獨立 clone）
│
└── WebWeaver/             ← [待建立] 你的改進版本
```

---

## 跨電腦工作流程

```
Windows (RTX 3060 Ti)          GitHub                    MacBook (M3 Air)
  開發 + debug            git push/pull              完整實驗 + pilot
  本地 7B 模型               ↕                       14B 模型 / API
       ↓                     ↕                            ↓
  修改程式碼 → push → pull → 跑 35 projects 實驗
```

**Windows 端**：
```bash
git add -A && git commit -m "update" && git push
```

**MacBook 端**：
```bash
git pull
# 如果是第一次，需要先跑 Step 4 clone benchmark projects
```

---

## 參考資料

- [TestWeaver 論文 (ICSE 2026)](https://github.com/FSoft-AI4Code/TestWeaver)
- [CodaMosa Benchmark (ICSE 2023)](https://github.com/plasma-umass/codamosa)
- [DeepSeek API](https://platform.deepseek.com/)
- [Ollama（本地 LLM）](https://ollama.com/)
- 研究筆記：見 Obsidian vault `碩論參考資料/` 資料夾

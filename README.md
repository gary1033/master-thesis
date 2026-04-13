# WebWeaver — Master's Thesis Project

> 基於 [TestWeaver (ICSE 2026)](https://github.com/FSoft-AI4Code/TestWeaver) 延伸，研究如何提升 LLM-based test generation 的 code coverage。

## 研究概述

**題目**：WebWeaver - Context-Aware LLM-Based Test Generation via Bidirectional Slicing and Iterative Refinement

**兩個核心方向**：
1. **Bidirectional Slicing** — 在 TestWeaver 的 backward slicing 基礎上加入 forward slicing，讓 LLM 同時理解目標行的上游依賴（怎麼到達）和下游影響（到達後會發生什麼）
2. **Iterative Feedback-Driven Refinement** — 將 TestWeaver 的 single-shot Phase 3 改為多輪回饋，包含分歧點分析、失敗分類、adaptive test selection

---

## 環境設定（Setup）

### Step 1：Clone 本 repo

<details>
<summary><b>Windows (Git Bash / PowerShell)</b></summary>

```bash
git clone --recurse-submodules git@github.com:gary1033/master-thesis.git
cd master-thesis

# 如果 submodule 沒有自動初始化
git submodule update --init --recursive
```

</details>

<details>
<summary><b>macOS (Terminal)</b></summary>

```bash
git clone --recurse-submodules git@github.com:gary1033/master-thesis.git
cd master-thesis

# 如果 submodule 沒有自動初始化
git submodule update --init --recursive
```

</details>

> **這一步做了什麼**：
> - 下載本 repo（包含 CLAUDE.md 研究規範、參考論文 PDF）
> - 自動 clone TestWeaver 原版程式碼（作為 git submodule 管理）
> - 自動 clone CodaMosa submodule 的**目錄結構**（但 test-apps 裡的 benchmark projects 需要 Step 4 另外下載）

---

### Step 2：安裝 Python 依賴

<details>
<summary><b>Windows</b></summary>

```powershell
# 確認 Python 版本（需要 3.10+）
python --version

# 安裝 TestWeaver 的依賴
cd TestWeaver
pip install -r requirements.txt
cd ..
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
# 確認 Python 版本（需要 3.10+）
python3 --version

# 建議使用 venv
python3 -m venv .venv
source .venv/bin/activate

# 安裝 TestWeaver 的依賴
cd TestWeaver
pip install -r requirements.txt
cd ..
```

</details>

> **這一步做了什麼**：
> - 安裝 TestWeaver 需要的 Python 套件（openai, pytest, slipcover 等）
> - slipcover 是用來測量 code coverage 的工具

---

### Step 3：安裝本地 LLM（Ollama + 開源模型）

#### 3a. 安裝 Ollama

<details>
<summary><b>Windows</b></summary>

```powershell
# 方法 1：官網下載安裝檔
# 到 https://ollama.com/download/windows 下載 OllamaSetup.exe 並安裝

# 方法 2：使用 winget
winget install Ollama.Ollama

# 安裝後，Ollama 會自動作為背景服務啟動
# 確認安裝成功：
ollama --version
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
# 方法 1：官網下載
# 到 https://ollama.com/download/mac 下載 Ollama.dmg 並安裝

# 方法 2：使用 Homebrew
brew install ollama

# 啟動 Ollama 服務（安裝後通常自動啟動）
ollama serve &

# 確認安裝成功：
ollama --version
```

</details>

#### 3b. 下載推薦模型

| 硬體 | 推薦模型 | 大小 | HumanEval | 安裝指令 |
|------|---------|------|-----------|---------|
| **RTX 3060 Ti 8GB** | Qwen2.5-Coder-7B | ~4.7GB | ~72% | `ollama pull qwen2.5-coder:7b` |
| **MacBook M3 Air 16GB** | Qwen2.5-Coder-14B | ~9GB | ~85% | `ollama pull qwen2.5-coder:14b` |

<details>
<summary><b>Windows (RTX 3060 Ti)</b></summary>

```powershell
# 下載 7B 模型（約 4.7GB，需要幾分鐘）
ollama pull qwen2.5-coder:7b

# 驗證模型已下載
ollama list

# 測試模型能不能跑（生成一個簡單的 pytest）
ollama run qwen2.5-coder:7b "Write a pytest test for a function that adds two numbers"
```

</details>

<details>
<summary><b>macOS (MacBook M3 Air)</b></summary>

```bash
# 下載 14B 模型（約 9GB，需要幾分鐘）
ollama pull qwen2.5-coder:14b

# 驗證模型已下載
ollama list

# 測試模型能不能跑
ollama run qwen2.5-coder:14b "Write a pytest test for a function that adds two numbers"
```

</details>

#### 3c. 確認 Ollama API 可用

```bash
# Ollama 啟動後會在 localhost:11434 提供 OpenAI-compatible API
curl http://localhost:11434/v1/models
```

---

### Step 4：設定 LLM 接口

TestWeaver 使用 OpenAI-compatible 接口，**API 和本地模型的接口完全相同**，只需改 `.env`。

#### 三種模式切換（只改 .env）

| 模式 | OPENAI_API_KEY | OPENAI_BASE_URL | model name |
|------|---------------|-----------------|------------|
| DeepSeek API | 你的 DeepSeek key | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 本地 Ollama | `ollama`（隨意填） | `http://localhost:11434/v1` | `qwen2.5-coder:7b` 或 `qwen2.5-coder:14b` |
| OpenAI GPT | 你的 OpenAI key | `https://api.openai.com/v1` | `gpt-4o` |

<details>
<summary><b>Windows</b></summary>

```powershell
# === 本地 Ollama 模式 ===
@"
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
"@ | Out-File -FilePath TestWeaver\.env -Encoding utf8

# === DeepSeek API 模式 ===
@"
OPENAI_API_KEY=sk-your-deepseek-key-here
OPENAI_BASE_URL=https://api.deepseek.com/v1
"@ | Out-File -FilePath TestWeaver\.env -Encoding utf8
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
# === 本地 Ollama 模式 ===
cat > TestWeaver/.env << 'EOF'
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
EOF

# === DeepSeek API 模式 ===
cat > TestWeaver/.env << 'EOF'
OPENAI_API_KEY=sk-your-deepseek-key-here
OPENAI_BASE_URL=https://api.deepseek.com/v1
EOF
```

</details>

> **注意**：除了 .env 外，還需要修改程式碼中 hardcoded 的 model name。
> TestWeaver 原始使用 `deepseek-v3-0324`，本地模型需改為 `qwen2.5-coder:7b`。
> 搜尋位置：`scripts/testweaver.py`、`scripts/ablate.py` 中所有 `model='deepseek-v3-0324'`。

---

### Step 5：下載 CodaMosa Benchmark Projects

> **關於 project 數量**：TestWeaver 論文提到「35 open-source Python projects」，這是引用 CodaMosa 論文的原始數字。
> 實際經過篩選（排除 timeout、100% 初始覆蓋率等），最終 benchmark 為 **27 個 projects / 486 個 modules**。
> test-apps 目錄可能包含額外的候選 projects（fastapi, keras, luigi 等），但實驗只使用這 27 個。

<details>
<summary><b>Windows / macOS（指令相同）</b></summary>

```bash
cd TestWeaver/codamosa/replication/test-apps

# === Pilot 必須的 3 個 projects ===
git clone --depth 1 https://github.com/cool-RR/PySnooper.git PySnooper
git clone --depth 1 https://github.com/ccarballolozano/flutils.git flutils
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

</details>

> **這一步做了什麼**：
> - `--depth 1` = 只下載最新版本（不下載完整歷史，節省空間和時間）
> - 這些 project 不會被推上 git（已在 .gitignore 排除），每台電腦需要獨立 clone
> - 所有 486 個測試 module 的對應關係記錄在 `codamosa/replication/scripts/modules_base_and_name.csv`

---

## 執行 TestWeaver（Baseline）

### 跑單一 module

<details>
<summary><b>Windows (Git Bash)</b></summary>

```bash
cd TestWeaver/scripts
export PYTHONPATH=$(pwd)
export sample_id=0   # 0 = PySnooper 的第一個 module (pysnooper.pycompat)
python testweaver.py --test-index $sample_id
```

</details>

<details>
<summary><b>macOS</b></summary>

```bash
cd TestWeaver/scripts
export PYTHONPATH=$(pwd)
export sample_id=0
python3 testweaver.py --test-index $sample_id
```

</details>

> **這一步做了什麼**：
> - `sample_id` 對應 `modules_base_and_name.csv` 中的行號（0-indexed）
> - 常用的 pilot module IDs：
>   - `0-3`：PySnooper（4 modules）
>   - `30-38`：flutils（9 modules）
> - 結果輸出到 `output/cm/` 目錄

### 跑消融實驗

<details>
<summary><b>Windows / macOS</b></summary>

```bash
cd TestWeaver/scripts
export PYTHONPATH=$(pwd)
export sample_id=0
python ablate.py --test-index $sample_id   # macOS: python3
```

</details>

---

## 目錄結構

```
master-thesis/
├── README.md              ← 本檔案
├── CLAUDE.md              ← Claude Code 研究規範
├── .env                   ← API keys（不上傳 git）
├── .gitignore
├── *.pdf                  ← 23 篇參考論文
│
├── TestWeaver/            ← [git submodule] TestWeaver 原版程式碼
│   ├── scripts/
│   │   ├── testweaver.py  ← 主 pipeline（Phase 1-3）
│   │   ├── ablate.py      ← 消融實驗腳本
│   │   ├── data_utils.py  ← find_closest_test()
│   │   ├── get_conditional_line.py  ← 控制流分析
│   │   ├── utils/codetransform/
│   │   │   ├── slicing.py     ← backward_slicing()（需擴展 forward）
│   │   │   ├── utils1.py      ← ExecutionOrderAnalyzer（SDG）
│   │   │   └── next.py        ← execute_and_trace()
│   │   └── prompt/            ← LLM prompt templates
│   └── codamosa/replication/
│       ├── scripts/modules_base_and_name.csv  ← 486 modules 對應表
│       └── test-apps/     ← 27 個 benchmark projects
│
└── WebWeaver/             ← [待建立] 改進版本
```

---

## 跨電腦工作流程

```
Windows (RTX 3060 Ti)          GitHub                    MacBook (M3 Air)
  開發 + debug            git push/pull              完整實驗 + pilot
  Ollama + 7B 模型           ↕                       Ollama + 14B 模型
       ↓                     ↕                            ↓
  修改程式碼 → push → pull → 跑 27 projects 實驗
```

<details>
<summary><b>Windows 推送</b></summary>

```powershell
cd C:\Projects\master-thesis
git add -A
git commit -m "update description"
git push
```

</details>

<details>
<summary><b>macOS 拉取</b></summary>

```bash
cd ~/Projects/master-thesis
git pull
# 第一次需要跑 Step 3 (Ollama) + Step 5 (benchmark projects)
```

</details>

---

## 參考資料

- [TestWeaver (ICSE 2026)](https://github.com/FSoft-AI4Code/TestWeaver) — 基礎論文
- [CodaMosa (ICSE 2023)](https://github.com/plasma-umass/codamosa) — Benchmark
- [DeepSeek API](https://platform.deepseek.com/) — 主實驗 LLM
- [Ollama](https://ollama.com/) — 本地 LLM runtime
- [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) — 推薦本地模型
- 研究筆記：見 Obsidian vault `碩論參考資料/` 資料夾

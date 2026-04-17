# experimentrules.md — 實驗監控與回報規範

> 本檔規範執行 TestWeaver / TestRefiner / ablate 實驗時的**回報格式、Phase 判讀 SOP、執行方式**。
> CLAUDE.md 只在實驗相關 turn 才載入本檔,避免日常 context 膨脹。

---

## § 1 status.py 功能與已知 bug

**解析來源**(`<project>` 替換成當前 project 名,例如 `pysnooper` / `flutils` / `typesystem`):

- `TestWeaver/scripts/logs/<project>_deepseek_*.log`(最新的 `*.log`)
- `TestWeaver/scripts/output/cm/<project>/*.jsonl`
- `TestWeaver/scripts/output/cm/<project>/<file>_phase{1,2,3}_coverage.json`

### 逐欄位說明 + bug 標記

| status.py 欄位 | 來源 | 可信度 |
|---|---|---|
| `Progress bar / files done` | `re.findall("Coverage result for (\S+):")` | ✅ 可信 |
| `AssertionError / ModuleNotFoundError / Traceback` 次數 | `text.count(...)` 字串計數 | ✅ 可信 |
| `Current phase` | **只看 `"Phase 3:" in text` / `"Saved phase 2" in text`** | 🔴 **buggy** — Phase 2→3 轉換常被誤判停留在 Phase 1 |
| `TEST N/M` | N = log 中 `TEST {N}---- FEEDBACK` 最大 line 號(**不是迭代次數**),M = `len(result_execute)` | ⚠️ N 是行號,容易誤讀為迭代次數 |
| `Phase1 Cov / Phase2 Cov` 表格欄 | 掃 `*_phase1_coverage.json` / `*_phase2_coverage.json` | ✅ 可信 |
| `Final Cov` 欄 | 排除 phase1 後掃 `*_coverage.json` 取最後一個 | ⚠️ 當 phase3 未存時會 fallback 到 phase2,欄名誤導 |
| `Retries` 欄 | 數 `feed_testing*.jsonl` 檔案數 | ✅ 可信 |
| `Status` [RUNNING/DONE] | `"Test generation algorithm completed" in text` | 🔴 **buggy** — 進程消失也會繼續顯示 RUNNING |

### 為何不修 status.py

> status.py 在 `TestWeaver/scripts/logs/` 下,雖是自己後加的輔助工具,但處於 submodule 內。
> 修它要不是 patch submodule(未來 upstream 更新會衝突),就是搬到 TestRefiner 下單獨維護。
> 目前 pilot 階段功能已夠用,**靠 § 4 的 SOP 繞過 bug 即可**;
> 待 TestRefiner 開始跑自己 pipeline 時再搬遷並重寫 phase 判讀(用 coverage JSON mtime 當 ground truth)。

---

## § 2 每次回報的標準格式(兩段式 + 多檔 Phase 表)

### 段一:即時指標總覽表(固定欄位)

| 指標 | 現在 | 上次 | Δ |
|---|:---:|:---:|:---:|
| Elapsed | X min | X min | +5.0 |
| Phase | 實際判讀(**不信 status.py 單一來源**,對照 JSON mtime) | — | — |
| Log size | KB | KB | +KB |
| Log last update | X min 前 | | ⚠️ if > 10 min |
| AssertionError | N | N | ΔN |
| ModuleNotFoundError | N | N | ΔN(0 ✅ if patch 生效) |
| Traceback | N | N | ΔN |

### 段二:每個 .py 檔分別一張 Phase 表

**規則**:

- 從 `TestWeaver/scripts/testweaver.py` 裡 `pkg[pkg_top]['files']` 或從 `<project>_modules.csv` 讀檔案清單
- **有幾個 .py 檔就要有幾張 Phase 表,不合併、不省略**
- 未開始的檔:用一行標註 `待` 即可,不畫空 Phase 表
- 已完成的檔:完整 3 行 Phase

**每檔格式**:

```
### <filename>.py

| Phase | Coverage | 完成時間 | Δ |
|---|:---:|:---:|:---:|
| Phase 1 | X% (c/t) | HH:MM(N min) | +N |
| Phase 2 | X% (c/t) | HH:MM(N min) | ΔN 或 0(Nth confirm) |
| Phase 3 | 進行中 TEST N / M missing 或 X% (c/t) | — | — |
```

---

## § 3 表格後的解說段(強制 5 小段)

1. **問題識別**(核心)
   - 當前最大的問題是什麼?(stall / 錯誤激增 / coverage 不動 / 進程消失)
   - 如果沒明顯問題,明確寫「無異常」
2. **模型行為與上次對比**(關鍵)
   - LLM 這 5 分鐘做了什麼?(retry 多少次、CoT 長不長、產出合法 test 嗎)
   - 與上一則回報相比有變化嗎?(變聰明 / 變懶 / 卡在同一行 / 換策略)
   - 若可從 log tail 看到 LLM output,引用 1-2 行最代表性的輸出
3. **觀察**(2–4 bullet)
   - log 增速、錯誤類型變化、phase 推進節奏、新錯誤類型
4. **ETA**
   - 基於近 10 分鐘推進速率(不是 status.py 線性外推)
   - 分層估:本檔剩餘 + 其他未開始檔估計
5. **可調整建議**
   - 例:「建議中斷做 X」/「考慮修 Y bug」/「繼續等 Z min」/「切換輪詢頻率」

---

## § 4 Phase 實際判讀 SOP(project-agnostic)

每次回報前,先跑(`<project>` 替換成當前跑的 project 名):

```bash
# 1. 看所有 coverage JSON 的 mtime,決定真實 phase 進度
ls -la TestWeaver/scripts/output/cm/<project>/*_coverage.json

# 2. 看 log 最後 30 行,確認在跑 LLM CoT / subprocess / stall
tail -30 TestWeaver/scripts/logs/<project>_deepseek_*.log
```

### 判讀規則

- 最新的 `<file>_phase{N}_coverage.json` mtime → 確認該檔已進到 Phase N+1
- log tail 若是 `<thinking>` 段落 → LLM CoT 中(正常慢)
- log tail 若是 `Traceback` 或 `SubprocessError` → 剛跑完一輪 subprocess
- log tail 若是 `TEST N---- FEEDBACK` → Phase 3 新一輪開始
- log last update > 10 min + 無新 error + 無新 JSON → stall 警訊

---

## § 5 主動示警觸發條件

| 條件 | 動作 |
|---|---|
| Log stale > 10 min | 提醒 stall 風險,建議查 tasklist |
| Phase 3 單行耗時 > 10 min | 建議考慮縮 `epoch=5` → `epoch=3` 或 skip |
| ModuleNotFoundError > 0 且 patch2 已套 | 提醒 patch 失效,要查 subprocess 環境 |
| 3 個 phase coverage 相同 | 標記為**方向二 motivation evidence**,建議記進 Obsidian |
| tasklist 無 python.exe 但 log 最近有寫入 | 校正 status,告知進程已死 |
| 出現新錯誤類型(不在 Assertion/NameError/ModuleNotFound 範圍) | 提示使用者,可能是新 bug |

---

## § 6 實驗執行規則

### 6.1 啟動前檢查(必做)

每次啟動實驗前,**必須依序確認**:

1. **確認 venv 已啟動**:
   ```bash
   # Windows
   C:\Projects\master-thesis\.venv\Scripts\activate
   # 驗證
   where python
   # 第一行必須是 C:\Projects\master-thesis\.venv\Scripts\python.exe
   # 若不是 → venv 未正確啟動,不要繼續
   ```

2. **設定 PYTHONPATH**:
   ```bash
   cd C:\Projects\master-thesis\TestWeaver\scripts
   set PYTHONPATH=%cd%
   ```

3. **設定編碼**(Windows 必要):
   ```bash
   set PYTHONIOENCODING=utf-8
   ```

4. **按 README 正確方式啟動**:
   ```bash
   python testweaver.py --test-index <sample_id>
   ```
   - 不要用 `.venv\Scripts\python.exe` 硬路徑(靠 activate 讓 `python` 指向 venv)
   - 不需要傳 positional package name 或 `--suite cm`(預設即 cm)

### 6.2 CodaMosa Project ID 對照表

| ID | Package | Files | 備註 |
|:---:|---|:---:|---|
| **0** | **pysnooper** | **4** | **Pilot ①** |
| 1 | ansible | 237 | 最大 project |
| 2 | apimd | 2 | |
| 3 | blib2to3 | 6 | black 子 package |
| 4 | codetiming | 1 | 最小 |
| 5 | cookiecutter | 5 | |
| 6 | dataclasses_json | 4 | |
| 7 | docstring_parser | 5 | |
| 8 | flutes | 3 | |
| **9** | **flutils** | **9** | **Pilot ②** |
| 10 | httpie | 19 | |
| 11 | isort | 2 | |
| 12 | py_backwards | 19 | |
| 13 | pymonet | 10 | |
| 14 | pypara | 6 | |
| 15 | semantic_release | 6 | |
| 16 | string_utils | 3 | |
| 17 | pytutils | 12 | |
| 18 | sty | 2 | |
| 19 | thonny | 3 | |
| 20 | tornado | 13 | |
| 21 | tqdm | 9 | README 範例 |
| **22** | **typesystem** | **10** | **Pilot ③** |
| 23 | youtube_dl | 35 | |

### 6.3 執行方式(Claude Bash 背景執行 + 使用者讀 log + Claude 監控)

**原則**:實驗跑在 Claude 的 Bash tool 背景(`run_in_background: true`),同時 tee 到 log 檔。使用者需要時自己 `tail -f` log 檔看即時輸出;Claude 用 CronCreate 定時讀 log + coverage JSON 回報。

**標準做法**:
1. Claude 用 Bash tool 啟動實驗,帶 `run_in_background: true`,命令尾端加 `2>&1 | tee <log_path>`
2. log 檔路徑固定在 `TestWeaver/scripts/logs/<project>_run.log`(UTF-8),使用者隨時可用 `tail -f` 或 `Get-Content -Wait` 查看
3. Claude 透過 BashOutput + Read log + coverage JSON 定時輪詢,依 § 2-3 格式回報

**啟動指令模板**(在 Git Bash / Bash tool 內執行):

```bash
cd /c/Projects/master-thesis && \
source .venv/Scripts/activate && \
cd TestWeaver/scripts && \
export PYTHONPATH=$(pwd) && \
export PYTHONIOENCODING=utf-8 && \
mkdir -p logs && \
python -u testweaver.py --test-index <ID> 2>&1 | tee logs/<project>_run.log
```

- `-u` 強制 unbuffered,避免 log 延遲
- `tee` 同時寫 log + 走 stdout(Bash tool 吞掉 stdout 沒關係,log 檔會有)
- `set -o pipefail` 非必要,但若想確保 python 失敗能感知到可加

**Claude 可以做的事**(新規則):
- 用 Bash tool + `run_in_background: true` 跑實驗
- 用 BashOutput 讀背景 shell 最新輸出(當 log 檔解碼有困難時備援)
- 用 Read/Grep 讀 log 檔做結構化分析

**Claude 仍然不要做的事**:
- 不要在**前景**用 Bash tool 跑實驗(10 min timeout 會中斷)
- 不要在啟動指令裡**省略 tee 寫 log**(使用者看不到 + Claude 輪詢沒檔案可讀)
- 不要在 Claude session 即將結束前啟動長實驗(背景 shell 會隨 session 消失,需改成使用者 terminal 模式 — 見 § 6.4)

**監控方式**:
- 使用者說「開始監控」或 Claude 啟動實驗後,Claude 自動 CronCreate 設定定時輪詢(預設 10 分鐘)
- 每次輪詢依 § 4 SOP 撈資料,依 § 2-3 格式回報

### 6.4 回退方案(使用者自行在 terminal 跑)

若 Claude session 不方便長時間保持活著,或需要跨機器協作,可回到原本做法:
1. Claude 提供啟動指令(同 § 6.3 模板,但改 PowerShell 語法)
2. 使用者在自己的 PowerShell / Git Bash 貼上執行
3. Claude 只負責監控(CronCreate + 讀 log + coverage JSON)

此時 Claude **不要**用 Bash tool 啟動實驗。

# 2026_ironman_test_ai

《AI 寫的測試，誰來測？》— 2026 iThome 鐵人賽系列的程式資產。

> 本 repo 的程式碼由 AI 產生，人設計 fault、定驗收標準、站閘門。文件由作者主導撰寫，AI 協助整理與查證。

## 這是什麼

一個 QA 把自己上線一年的退休試算工具翻出來驗屍，並且回答一個問題：**AI 寫的測試，誰來測？**

系列文章：<https://ithelp.ithome.com.tw/users/20103826/ironman/9466>

## 每天的 repo 長什麼樣

主分支會一路長到 Day 30。想看某一天當下的完整狀態，點該天的 tag，
那個網址永遠顯示那天的樣子——不會被之後的進度蓋掉。

| 天 | 文章 | 當天的 repo | 這天的異動 |
|---|---|---|---|
| Day 1 | [我的退休試算上線一年，我檢查過，它「沒問題」？](https://ithelp.ithome.com.tw/articles/10406889) | — | |
| Day 2 | [三招驗證法，為什麼一招都沒中？](https://ithelp.ithome.com.tw/articles/10407106) | — | |
| Day 3 | [四個缺陷的驗屍報告](https://ithelp.ithome.com.tw/articles/10407126) | — | |
| Day 4 | [那個 (1+r) 是怎麼來的](https://ithelp.ithome.com.tw/articles/10407397) | — | |
| Day 5 | [打造影子模型：抽取，還是重寫？](https://ithelp.ithome.com.tw/articles/10407729) | 見下方說明 | 寫了 `oracle/`、`shadow/`，但當天還沒有 commit |
| Day 6 | [500 組差分，第一次就掛了](https://ithelp.ithome.com.tw/articles/10407970) | [`day06`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day06) | repo 公開。`sut/`、`oracle/`、`shadow/`、`tests/test_differential.py` |
| Day 7 | [把錯的行為，正式寫進測試裡](https://ithelp.ithome.com.tw/articles/10408224) | [`day07`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day07) | `golden/` 加 `locks_defect` 標記；修好 `test_characterization.py` 的 `KeyError` |
| Day 8 | [規格考古：十個沒有人做過決定的地方](https://ithelp.ithome.com.tw/articles/10408401) | [`day08`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day08) | `spec/README.md` 與 `spec/RC-01`～`RC-10`，十個歧義現場（裁決欄留空） |
| Day 9 | [閘門一：替一年前的自己做決定](https://ithelp.ithome.com.tw/articles/10408713) | [`day09`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day09) | 十個 `RC-xx.md` 的裁決欄填滿；新增 `spec/PRD-v1.md`（十條條款 + RC→PRD 對照） |
| Day 10 | [把 PRD 餵給 AI 之前，先把及格線畫好](https://ithelp.ithome.com.tw/articles/10408985) | [`day10`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day10) | `generated/2026-09-09-day10-prd-to-cases/`：`manifest.yaml`、`prompt.md`、`input-prd.md`；首輪十份作廢的原始輸出與 `CONTAMINATED.md` |
| Day 11 | [RTM 沒抓到漏測，抓到的是我的規格書](https://ithelp.ithome.com.tw/articles/10409267) | [`day11`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day11) | 重跑的十份乾淨輸出（`run-a-1`～`5`、`run-B-01`～`05`）；`manifest.yaml` 補記執行環境 |
| Day 12 | [把「該有 `A_d−1`／`A_d`／`A_d+1`」寫成 40 行程式](https://ithelp.ithome.com.tw/articles/10409576) | [`day12`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day12) | `tools/bva_checker.py`（38 行邏輯 + 7 組 KAT）；`tools/case_extractor.py` 含凍結宣告；`tests/test_bva.py` 移除重複實作改為 import |
| Day 13 | [我刪掉一條規格，沒有人偷偷把它加回來](https://ithelp.ithome.com.tw/articles/10409818) | [`day13`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day13) | `generated/2026-09-11-spec-mutation/`：三臂突變 PRD、`del` 臂十份輸出、preflight 與 `manifest.yaml` |
| Day 14 | [十三條測試全綠，殺得掉的只有「乘以 −1」](https://ithelp.ithome.com.tw/articles/10410618) | [`day14`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day14) | `spec/PRD-v1.1.md`（三缺口裁決 + PRD-11）；`tools/test_mutator.py`（21 個變異體，M/N 分群）；`tools/prd_cost.py`（KAT 釘住 v1.0 已發表的六個數字） |
| Day 15 | [424 條案例，只有一小撮值得寫成 pytest](https://ithelp.ithome.com.tw/articles/10411282) | [`day15`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day15) | `spec/PRD-v1.2.md`（新增 PRD-12 圖表餘額保真）；`tools/verify_fixed.py`（三道事前驗收器 + 四個分支算子）；`shadow/calc_fixed.py`（隔離環境生成，不覆蓋 `calc.py`）；`golden/golden_set_v2.json`（v1 不刪不覆寫）；`generated/2026-09-15-prd-to-impl/` 與 `-v2/` 兩輪實驗 |
| Day 16 | [CI 全綠，但 AI 只寫了一句 assert result is not None](https://ithelp.ithome.com.tw/articles/10412225) | [`day16`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day16) | `tools/assert_inspector.py`（斷言八分類、判定以函式為單位、26 條 KAT）；`decisions.md` 新增閘門 3 門檻 `fidelity_ratio >= 0.8` 與量尺五個誤判的紀錄 |
| Day 17 | [行覆蓋率 100%，還是有十一種錯法穿過去](https://ithelp.ithome.com.tw/articles/10412277) | [`day17`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day17) | `tools/coverage_probe.py`（`sys.settrace` 自數覆蓋率，分母可切換含不含 class 宣告，`_assert_all_ran()` 拒絕在測試沒跑完時印出比值） |
| Day 18 | [誰來驗收驗收者：自建 Mutation Harness 與校準協議](https://ithelp.ithome.com.tw/articles/10412894) | [`day18`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day18) | `tools/harness.py`（鏡射整棵樹置換、片段唯一性、依 pytest 回傳碼判定、`_assert_baseline()`）；`tools/calibration_mutants.py`（必死 2／必活 2／必錯 1，人手寫） |
| Day 19 | [十四個變異體，八個有行號八個沒有](https://ithelp.ithome.com.tw/articles/10412938) | [`day19`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day19) | `tools/domain_mutants.py`（14 個領域變異體、逐項證據等級、`audit()` 自檢片段唯一性與變異後語法）；`tools/harness.py` 新增 `--domain` 正式模式 |
| Day 20 | [第一個變異分數 85.7%，而扣分的兩個都不是斷言的錯](https://ithelp.ithome.com.tw/articles/10414074) | [`day20`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day20) | `generated/2026-09-18-first-mutation-score/manifest.yaml`：預期跑之前封存、逐項判定、兩個存活的驗屍、golden v2 輸入空間的五個缺口 |
| Day 21 | [補完之後 100%，而那個從 Day 14 掛到現在的欄位還是 0](https://ithelp.ithome.com.tw/articles/10414576) | [`day21`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day21) | `generated/2026-09-21-mutation-feedback/`：反饋提示詞、雙向洩漏掃描、三輪產物與 preflight；`tools/harness.py` 的 `--domain` 可接多個測試檔 |
| Day 22 | [規格只給一句話，寫出來的測試殺掉 0 個變異體](https://ithelp.ithome.com.tw/articles/10415705) | [`day22`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day22) | `generated/2026-09-22-scripts-matrix/`：L1 vs PRD × 兩臺模型共 20 次生成、貼上檔由程式拼接並自檢、三道關的原始輸出；`tools/leak_scan.py`（雙向洩漏掃描，命中需簽名）；`tools/const_sampler.py`（AST 抽輸入數值，邊界判定沿用 Day 12 的 `bva_checker`）；`tools/harness.py` 新增 `--solo`；`assert_inspector.py` 拆出 `SKIPPED` 判定 |
| Day 23 | [它準確地打在邊界上，然後把期望寫反了](https://ithelp.ithome.com.tw/articles/10416285) | [`day23`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day23) | `tools/const_sampler.py`（AST 抽輸入數值、分年齡／金額／比率三群、整數偏好與邊界命中，邊界判定沿用 Day 12 的 `bva_checker`，8 條 KAT，抽到 0 個輸入即中止）；`generated/2026-09-23-boundary-goodhart/`：人工基準線先於 AI 腳本量測、逐格彙總 `rollup.py` 與四條限制 |
| Day 24 | [AI 寫下那個數字的時候，沒有人在旁邊](https://ithelp.ithome.com.tw/articles/10416809) | [`day24`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day24) | `tools/failure_classifier.py`（把測試失敗分成「期望值算錯」與「餵錯輸入」，11 條 KAT，兩道守衛：解析數與 pytest 自報數對帳、抽到 0 條即中止）；`generated/2026-09-24-oracle-problem/`：Day 22 十二份紅產物的逐條分類、去重前後兩個分母、原始 pytest 輸出 |

| Day 25 | 我寫了四條蛻變關係，三條是廢話 | [`day25`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day25) | `tests/test_metamorphic.py`（四條蛻變關係，不依賴任何期望值）；`tools/mr_audit.py`（拿 Day 19 的十四個變異體逐條驗收關係本身：殺 0 個即判為廢話，3 條 KAT，`-k` 選不到測試時中止）；`tools/harness.py` 的 `run_tests`／`evaluate` 新增 `extra_args`；`generated/2026-09-25-mr-audit/`：事前預測封存、逐條結果、MR-04 在 legacy 上抓到缺陷 A 的驗屍 |

Day 1–5 沒有 tag，因為 repo 是 Day 6 才建立的——補打只會指到當天並不存在的狀態。
**寧可留白，不要假的時間戳。**

### 讀 Day 5 的人要看哪裡

Day 5 講的 `oracle/calc.js` 與 Python 影子模型，最接近的快照是
[`day06`](https://github.com/eyelash500/2026_ironman_test_ai/tree/day06)，但有一個落差要先知道：

**`shadow/calc.py` 在那個快照裡已經是 Day 6 修好的版本。** Day 5 當下那一版的
`Params` 只有一個籠統的 `annual_income_after_retirement` 欄位，隔天被 500 組差分
當場打穿，才拆成勞保、勞退、其他收入三個來源。那一版從來沒有進過 git，
它唯一的紀錄是 Day 5、Day 6 兩篇文章裡的程式碼區塊。

`oracle/calc.js` 則從第一個 commit 起就沒有變過，Day 5 讀它是準的。

### 為什麼 `day06` 裡就有 Day 7 的東西

`golden/` 和 `test_characterization.py` 在 `day06` 就存在了，那是 Day 7 的交付物。
程式跑在文章前面一步。照實記著，不回頭修飾。

## 受測物

`sut/進階退休規劃試算.html` — 2025 年以 AI 協作流程做出、真實上線一年的退休試算工具，已驗出四個計算缺陷。

**這是 2026-09-03 的凍結快照。** 線上版預計於 Day 30（9/30）修復部署，屆時兩者會不同。以本 repo 的快照為準。

`sut/退休金缺口計算機-iron.html` — 對照組。2025 系列文章中示範的那一支，同一套流程、同一個模型的另一次生成。**四個缺陷一個都沒有**（見系列 Day 3）。

⚠️ 兩支工具皆有已知計算偏差，僅供技術研究，不構成任何投資或財務規劃建議。

## 目錄

| 路徑 | 內容 | 何時出現 |
|---|---|---|
| `sut/` | 受測物與對照組的凍結快照 | 已有 |
| `oracle/` | 從 HTML 抽出的純計算核心 | Day 5 |
| `shadow/` | Python 影子模型（獨立參照實作） | Day 5 |
| `tests/` | 差分測試、golden set、mutation harness | Day 6 起 |
| `decisions.md` | 五個閘門的決策紀錄，一行一筆 | 已有 |
| `generated/` | 每次 AI 呼叫的原始輸出與 manifest | 首次 API 呼叫後 |

**規則：哪天寫的東西，哪天才進 repo。** 不預先開空目錄。

## 為什麼有 `generated/`

系列的核心實驗是「AI 產的測試有多好」。任何分數都必須能回溯到產生它的那批輸出，否則只是印象。

- 原始輸出一個字都不改；要清理格式另存，不覆蓋
- 失敗的、被截斷的、看起來很蠢的都留著——刪掉就是選擇性報告
- `manifest.yaml` 在跑之前寫，不是跑完補

存檔換來的不是**可重現**（模型會改版，做不到），是**可查證**。

## 環境

```
uv run --python 3.12
```

## 授權

MIT（見 `LICENSE`）。受測物 HTML 為作者本人 2025 年作品，一併以 MIT 釋出。

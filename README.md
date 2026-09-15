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

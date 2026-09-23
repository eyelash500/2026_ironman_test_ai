# Day 22 生成程序

四格 × 5 輪 = **20 次生成**。每一輪都是全新對話。

| 格 | 模型 | 貼上檔 | 產物檔名 |
|---|---|---|---|
| A-L1 | Gemini 3.1 Pro Preview | `_paste/paste-l1.txt` | `run-A-L1-01` ～ `-05.txt` |
| A-PRD | Gemini 3.1 Pro Preview | `_paste/paste-prd.txt` | `run-A-PRD-01` ～ `-05.txt` |
| B-L1 | Gemini 3.8 Flash | `_paste/paste-l1.txt` | `run-B-L1-01` ～ `-05.txt` |
| B-PRD | Gemini 3.8 Flash | `_paste/paste-prd.txt` | `run-B-PRD-01` ～ `-05.txt` |

兩臺的版本號不在同一條軸上（Pro 與 Flash 各自編號），各取當前版。

## 每一輪的步驟

1. 開**全新對話**，六個工具開關全部關掉
2. **截圖右側設定面板**，存成 `preflight-<格>-0N.png`
3. 整份貼上該格的 `paste-*.txt`，不加任何補充說明
4. 產出原封不動存成 `run-<格>-0N.txt`（一個字都不改，要清格式另存）

**不要在正式對話裡問「你現在能用哪些工具」。** 那段問答會進入上下文。
依 Day 11-番外 立的做法，自我描述在**另開的丟棄用對話**裡問，
兩臺各問一次，存成 `preflight-discard.txt`。它只是輔助證據，截圖才是主要的。

## 貼上檔怎麼來的

不要手改 `_paste/` 底下的檔案。要改請改 `build_paste.py` 再重跑：

```bash
cd ~/Documents/source_code/ithome-18 && source venv/bin/activate
python3 generated/2026-09-22-scripts-matrix/build_paste.py
python3 tools/leak_scan.py generated/2026-09-22-scripts-matrix/leak_config.py
```

`build_paste.py` 會自檢「兩份挖掉規格區塊之後逐位元相同」，
`leak_scan.py` 會雙向掃描並在自檢五條 KAT 之後才開始掃。
**兩支都印綠字才准貼。**

## 跑完之後的驗收（三關，依序）

每一份先各自放到 `tests/test_ai_matrix.py` 再跑：

```bash
cd ~/Documents/source_code/ithome-18 && source venv/bin/activate

python3 tools/assert_inspector.py tests/test_ai_matrix.py     # 關 A：忠實性 >= 0.8
python3 -m pytest tests/test_ai_matrix.py -q                  # 關 B：基準線全綠
python3 tools/harness.py --domain tests/test_ai_matrix.py     # 關 C：14 個變異體
```

關 A 或關 B 不過的，**不進關 C，也不代改、不補跑**，在矩陣記「未達檢核」。
`--domain` 接多個測試檔的能力是 Day 21 加的，這裡直接用。

## 20 次要跑多久

單輪貼上到存檔約 2–3 分鐘，20 輪約一小時，驗收另計。
**分批跑沒關係，但同一格的五輪之間不要改任何設定。**
中途若模型版本字串變了，停下來記進 manifest，不要混著跑完。

## 跑 20 次之前先做這件事

`smoke.py` 是人手寫的兩條測試，不是產物，只用來證明三道關接得起來。
**開始生成之前先跑一次**，免得二十份都產完才發現關 C 的指令有問題：

```bash
cp generated/2026-09-22-scripts-matrix/smoke.py tests/test_ai_matrix.py
python3 tools/assert_inspector.py tests/test_ai_matrix.py   # 預期：忠實性 100%、PASS
python3 -m pytest tests/test_ai_matrix.py -q                # 預期：2 passed
python3 tools/harness.py --domain tests/test_ai_matrix.py   # 預期：基準線全綠、跑完 14 個
rm tests/test_ai_matrix.py
```

關 A 已在沙箱驗過（忠實性 100%、strict 1、contract 1）；關 B、C 要在你的 venv 跑。

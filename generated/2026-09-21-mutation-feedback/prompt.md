# Day 21 生成程序

貼上檔：`_paste/paste.txt`（11,924 字元，261 行，已過雙向洩漏掃描）

## 每一輪的步驟

1. 開**全新對話**，把六個工具開關全部關掉
2. **截圖右側設定面板**，存成 `preflight-0N.png` —— 這是這一輪的主要隔離證據
3. 在**同一個對話**裡，整份貼上 `_paste/paste.txt`，不加任何補充說明
4. 產出原封不動存成 `run-0N.py`（一個字都不改，要清格式另存）
5. 重複三次，每次都開新對話

**不要在正式對話裡問「你現在能用哪些工具」。** 那段問答會進入上下文，
讓模型知道有人在檢查它的環境。依 Day 11-番外 立的做法，
自我描述要在**另開的丟棄用對話**裡問，存成 `preflight-discard.txt`，
而且它只是輔助——[Day 15](../2026-09-15-prd-to-impl/manifest.yaml) 已經判定
模型自述不可單獨當隔離證據，截圖才是。

## 對照組

`control-human.py` 由作者自己寫，不經 AI。**先寫完再看三份 AI 產物**，
否則對照組會被汙染。

## 跑完之後的驗收（三關，依序）

```bash
cd ~/Documents/source_code/ithome-18 && source venv/bin/activate

# 每一份先各自放到 tests/test_feedback.py 再跑
python3 tools/assert_inspector.py tests/test_feedback.py   # 關 A：忠實性 >= 0.8
python3 -m pytest tests/test_feedback.py -q                # 關 B：基準線全綠
python3 tools/harness.py --domain-with-feedback            # 關 C：重跑 14 個變異體
```

關 C 的指令還沒實作，等前兩關的結果出來再補——**它要吃兩個測試檔**，
不是只吃 `test_golden_v2.py`。

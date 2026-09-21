`paste.txt` 是唯一輸入，整份貼給模型，不加任何補充說明。

內容：任務描述、四條硬約束、覆蓋率報告（五個行號）、
`shadow/calc_fixed.py` 全文、`tests/test_golden_v2.py` 全文。

**刻意不給**：變異測試的存在、M09／M14 的內容、任何「怎麼觸發」的提示。
掃描紀錄見上層 `manifest.yaml` 的 `leak_scan`。

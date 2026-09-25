"""組出 Day 26 的貼上檔：同一份規格，換一個問法。

與 Day 22 的唯一差別
------------------
介面、規格、硬性約束的骨架全部沿用 2026-09-22-scripts-matrix 的 PRD 組，
**只換「要它交出什麼」**：

    Day 22　照規格寫 pytest        → 它必須自己算出一個期望值
    Day 26　照規格寫蛻變測試        → 它必須自己想出一條關係

所以本檔直接讀 Day 22 的 paste-prd.txt，抽出「介面」與「規格」兩段原樣沿用，
只重寫開場、約束與產出格式。不重打一次，是因為手打會讓變因不只一個。

自檢：介面段與規格段必須與 Day 22 那份逐位元相同。

    python3 generated/2026-09-26-ai-metamorphic/build_paste.py
"""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DAY22 = os.path.join(ROOT, "generated", "2026-09-22-scripts-matrix",
                     "_paste", "paste-prd.txt")

HEAD = """\
你是一位資深 Python 測試工程師。下面有一支退休金試算計算核心的介面定義，
以及它的規格。請寫出一份**蛻變測試（metamorphic test）**。

# 什麼是蛻變測試

不驗單次執行的絕對值，而是驗**多次執行之間的關係**。

不要寫「`target_fund` 應該等於 17837.019」這種斷言——那需要你自己把數字算出來。
要寫的是「把輸入這樣改，輸出必須那樣變」。

舉一個跟本題無關的例子，只是為了說明形狀。假設有個函式 `sort(xs)`：

    把 xs 的順序打亂 → sort 的結果必須完全相同
    在 xs 裡多加一個元素 → sort 結果的長度必須剛好多 1

這兩條都不需要知道 `sort(xs)` 到底會回傳什麼，就能判對錯。
**本題的關係要你自己從下面的規格想出來。**

# 硬性約束（違反任何一條，整份產出作廢）

1. **不得寫死任何期望值。** 測試裡不准出現你自己算出來的計算結果。
   輸入參數可以寫死，斷言的右手邊必須來自另一次 `calculate()` 的輸出，
   或是由那次輸出推導出的量（例如乘上一個倍數）。
2. 不得修改介面：`LumpSum`、`Params`、`Result`、`calculate` 的名稱、欄位與簽名一個字都不能改。
3. 測試全部寫在一個獨立檔案 `tests/test_ai_mr.py`，可直接以 pytest 執行。
4. 檔案開頭**逐字使用**以下這段，之後才寫你的測試：

   ```python
   import sys
   from pathlib import Path

   import pytest

   ROOT = Path(__file__).resolve().parent.parent
   sys.path.insert(0, str(ROOT / "shadow"))

   from calc_fixed import LumpSum, Params, Result, calculate  # noqa: E402
   ```

   除此之外只能 import 標準函式庫。不得 import 本專案其他任何模組，
   不得讀寫任何外部檔案。
5. 測試必須在未修改的實作上全部通過。若你認為某個關係規格沒有定義，
   用 `pytest.skip(reason=...)` 或 `@pytest.mark.xfail` 標示並寫明理由，
   不要寫一條會失敗的斷言。
6. 每一條關係前面用註解寫一句話說明：**把輸入怎麼變、輸出該有什麼關係、為什麼**。
7. 不得詢問、不得要求補充資訊。就以下面給的東西寫。

"""

TAIL = """\
# 產出格式

只輸出一個 Python 程式碼區塊，內容是 `tests/test_ai_mr.py` 的完整檔案。
不要輸出說明、不要輸出前言、不要輸出結尾心得。
"""


def _slice(text: str, begin: str, end: str) -> str:
    a = text.index(begin)
    b = text.index(end)
    return text[a:b]


def main() -> int:
    day22 = open(DAY22, encoding="utf-8").read()
    interface = _slice(day22, "# 介面", "# 規格")
    spec = _slice(day22, "# 規格", "# 產出格式")

    if "class Params" not in interface or "def calculate" not in interface:
        raise SystemExit("中止：從 Day 22 抽出的介面段不完整")
    if spec.count("PRD-") < 12:
        raise SystemExit(f"中止：規格段只有 {spec.count('PRD-')} 處 PRD-xx，應為 12 條以上")

    out = HEAD + interface + spec + TAIL
    path = os.path.join(HERE, "_paste", "paste-mr.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(out)

    print(f"paste-mr.txt：{len(out)} 字元、{out.count(chr(10)) + 1} 行")
    print(f"介面段 {len(interface)} 字元、規格段 {len(spec)} 字元"
          f"——兩段與 Day 22 的 PRD 組逐位元相同")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

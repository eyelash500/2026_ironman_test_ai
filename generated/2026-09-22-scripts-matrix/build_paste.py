"""組出 L1 與 PRD 兩份貼上檔。

兩格的輸入**只准差在規格區塊**。手寫兩份檔案做不到這件事——
改了 A 忘了改 B，差異就從「規格細度」偷偷變成「指令用字」。
所以共用段只寫一次，由本檔拼接，並在最後自檢：
把兩份檔案的規格區塊挖掉之後，剩下的必須逐位元相同。

    python3 generated/2026-09-22-scripts-matrix/build_paste.py
"""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

MARK_BEGIN = "# 規格"
MARK_END = "# 產出格式"

HEAD = """\
你是一位資深 Python 測試工程師。下面有一支退休金試算計算核心的介面定義，
以及它的規格。請依規格寫出一份 pytest 測試。

# 硬性約束（違反任何一條，整份產出作廢）

1. 不得修改介面：`LumpSum`、`Params`、`Result`、`calculate` 的名稱、欄位與簽名一個字都不能改。
2. 測試全部寫在一個獨立檔案 `tests/test_ai_matrix.py`，可直接以 pytest 執行。
3. 檔案開頭**逐字使用**以下這段，之後才寫你的測試：

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
4. 測試必須在未修改的實作上全部通過。若你認為某個行為規格沒有定義，
   用 `pytest.skip(reason=...)` 或 `@pytest.mark.xfail` 標示並寫明理由，
   不要寫一條會失敗的斷言。
5. 不得詢問、不得要求補充資訊。就以下面給的東西寫。

# 介面

以下為 `shadow/calc_fixed.py` 的介面定義。**函式本體不提供**，
你看不到它怎麼算——測試要驗的是規格說它該算成什麼樣。

```python
{interface}
```

"""

TAIL = """\
# 產出格式

只輸出一個 Python 程式碼區塊，內容是 `tests/test_ai_matrix.py` 的完整檔案。
不要輸出說明、不要輸出前言、不要輸出結尾心得。
"""

SPEC_L1 = """\
# 規格

幫這支退休金試算的計算核心寫 pytest 測試。

"""


def _prd_clauses() -> str:
    """只取 PRD v1.2 的〈條款〉一節。

    其餘各節（改版說明、裁決紀錄、對照表、尚未涵蓋）滿是 Day 編號、
    「缺陷 A'」、legacy 與本系列的脈絡，整段貼出去等於把答案連同來歷一起送。
    條款表本身自足：四項裁決的結論都已寫進 PRD-01／05／10／12。
    """
    path = os.path.join(ROOT, "spec", "PRD-v1.2.md")
    lines = open(path, encoding="utf-8").read().split("\n")
    start = lines.index("## 條款")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## ") and i > start)

    # 只取表格本身。節末那句「v1.1 → v1.2：新增 PRD-12，其餘一字不動」
    # 會告訴模型有版本史、而且 PRD-12 是後來補的——等於在十二條裡標了重點。
    # 這一條是洩漏掃描抓出來的，不是事先想到的。
    body = "\n".join(ln for ln in lines[start + 1:end] if ln.startswith("|")).strip()
    if body.count("\n") + 1 != 14:          # 表頭 1 行 + 分隔 1 行 + 12 條
        raise SystemExit(f"中止：條款表擷取到 {body.count(chr(10)) + 1} 行，不是預期的 15 行")
    return f"# 規格\n\n以下為本計算核心的完整規格。\n\n{body}\n\n"


def _strip_spec(text: str) -> str:
    a = text.index(MARK_BEGIN)
    b = text.index(MARK_END)
    return text[:a] + text[b:]


def main() -> int:
    interface = open(os.path.join(HERE, "interface.py"), encoding="utf-8").read().strip()
    head = HEAD.format(interface=interface)

    out = {
        "paste-l1.txt": head + SPEC_L1 + TAIL,
        "paste-prd.txt": head + _prd_clauses() + TAIL,
    }

    stripped = {name: _strip_spec(text) for name, text in out.items()}
    a, b = stripped["paste-l1.txt"], stripped["paste-prd.txt"]
    if a != b:
        raise SystemExit("中止：兩份貼上檔挖掉規格區塊之後不相同，變因不只一個")

    paste_dir = os.path.join(HERE, "_paste")
    os.makedirs(paste_dir, exist_ok=True)
    for name, text in out.items():
        with open(os.path.join(paste_dir, name), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{name}：{len(text)} 字元、{text.count(chr(10)) + 1} 行")
    print(f"共用段逐位元相同（{len(a)} 字元），兩格只差在規格區塊。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

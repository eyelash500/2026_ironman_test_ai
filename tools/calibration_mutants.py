"""校準變異體：harness 的已知答案考卷。人手寫、人持有。

這一份不交給 AI 產
-----------------
`tools/harness.py` 是用來判定「測試有沒有抓到缺陷」的。
如果它自己的判定邏輯壞了，跑出來的每一個變異分數都是偽證。
所以在它接正式的領域變異體之前，先過這份考卷——
**答案先寫、跑完不改**，五條全部命中預期才准列裝。

三組各自在抓什麼
--------------
- **必死組**：破壞性變異，任何有斷言的測試套件都該報紅。
  判為 SURVIVED 代表 harness 根本沒跑到變異後的副本
  （最常見的成因：只置換單一檔案，而測試檔自己
  `sys.path.insert(0, ROOT / "shadow")` 把原檔搶回去了）。
- **必活組**：等價變異，語法改了、行為沒變。
  判為 KILLED 代表測試環境有殘留污染，或斷言脆弱到連改個註解都會紅。
- **必錯組**：語法錯誤。必須判 ERROR 而非 KILLED——
  這一條專門驗「非 0 即殺」的錯誤邏輯有沒有溜回來。
  語法錯被算成擊殺，那是編譯器的功勞，不是測試套件的。
"""

from __future__ import annotations

from harness import Mutant

# 受測基底：shadow/calc.py（Day 14 的 M 群也是打在這一支上）
REL_SOURCE = "shadow/calc.py"
REL_TESTS = "tests/test_checklist.py"


MUST_KILL: tuple[Mutant, ...] = (
    Mutant(
        id="CAL-K1",
        original="projected_savings = fv_current + fv_monthly",
        mutated="projected_savings = 0.0 * (fv_current + fv_monthly)",
        simulates="累積資產強制歸零：任何比對金額的斷言都必須紅",
    ),
    Mutant(
        id="CAL-K2",
        original="target_fund = target_for_expenses + total_lump_pv",
        mutated="target_fund = -1.0",
        simulates="目標金額換成定值：改動會擴散到 retirement_gap",
    ),
)

MUST_SURVIVE: tuple[Mutant, ...] = (
    Mutant(
        id="CAL-S1",
        original="@dataclass(frozen=True)\nclass Result:",
        mutated="@dataclass(frozen=True)\nclass Result:  # 校準用註解，行為不變",
        simulates="只改註解：任何測試都不該因此變紅",
    ),
    Mutant(
        id="CAL-S2",
        original="target_fund = target_for_expenses + total_lump_pv",
        mutated="target_fund = target_for_expenses + total_lump_pv + 0.0",
        simulates="加 0.0：語法變了，浮點結果逐位元相同",
    ),
)

MUST_ERROR: tuple[Mutant, ...] = (
    Mutant(
        id="CAL-E1",
        original="target_fund = target_for_expenses + total_lump_pv",
        mutated="target_fund = (target_for_expenses + total_lump_pv",
        simulates="少一個右括號：必須判 ERROR，不得算成擊殺",
    ),
)

# --- `--naive` 對照輪的預期（2026-09-17 寫下，跑之前）-------------------
# 失敗做法：只置換單一檔案，測試檔留在原專案，靠 PYTHONPATH 接。
#
#   必死組 CAL-K1／CAL-K2 → 預期雙雙變成 SURVIVED。
#     理由：test_checklist.py 第 5 行 `sys.path.insert(0, ROOT / "shadow")`
#     把本機原檔插在搜尋路徑最前面，PYTHONPATH 搶不過它，
#     測試 import 到的是未變異的 calc.py。
#   必活組 CAL-S1／CAL-S2 → 預期仍是 SURVIVED（但那是「碰巧對」，不是「驗到了」）。
#   必錯組 CAL-E1        → 預期變成 SURVIVED 而非 ERROR：
#     語法錯的副本根本沒被載入，pytest 全綠收場。
#
# 若 `--naive` 跑出來不是這樣，那是資料，不是意外——照實記錄，不回頭改這段。
# 猜中的話要問的是：我是不是在設計失敗做法時就把答案寫進去了。

# (組名, 變異體, 該組每一條的預期判定)
CALIBRATION: tuple[tuple[str, tuple[Mutant, ...], str], ...] = (
    ("必死組", MUST_KILL, "killed"),
    ("必活組", MUST_SURVIVE, "survived"),
    ("必錯組", MUST_ERROR, "error"),
)

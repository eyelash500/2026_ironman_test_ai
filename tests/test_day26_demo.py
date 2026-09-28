"""同一條測試，兩個實作：一綠一紅。

這份不是新測試，是一個示範
------------------------
底下那條關係**一個字都沒改**，原樣取自 Day 26 的產物
`generated/2026-09-26-ai-metamorphic/run-A-MR-01.txt`
的 `test_mr_charted_balances_veracity`。唯一的改動是把「哪一個實作」
變成參數，讓同一條測試同時跑 `calc_fixed`（修好的）與 `calc`（上線那版）。

十份產物**全部**寫了這條關係，是唯一一條 10/10 的。
它看起來是最紮實的那種：兩個輸出、逐項比對、直接對應 PRD-12。

它在兩邊的價值完全不同
--------------------
`shadow/calc_fixed.py`：

    balances_tuple = tuple(balances)        # 148
    ...
    balances_raw=balances_tuple,            # 154
    balances_charted=balances_tuple         # 156  ← 同一個物件

兩個欄位指向同一個 tuple。這條斷言在比較一個東西跟它自己，
**恆綠**——不管實作怎麼壞，它都不會紅。

`shadow/calc.py`（上線那版）：

    charted.append(max(0.0, remaining))     # 121  ← 遮羞布
    ...
    balances_raw=tuple(raw),                # 127
    balances_charted=tuple(charted),        # 128  ← 兩條各自累積的 list

兩個欄位是兩條路徑各自算出來的，而 `charted` 那條把負餘額夾成 0。
同一條斷言在這裡一秒就抓到。

所以
---
**值不值錢不在測試裡，在實作裡。而你從測試本身看不出來是哪一種。**

    python3 -m pytest tests/test_day26_demo.py -v

預期：`fixed` 綠、`legacy` 紅。
`legacy` 那邊紅在第二個斷言（`balances_charted == balances_raw`），
不是第一個——第一個（支出越高、期末餘額越低）在兩邊都成立。

一個容易略過的附帶條件
-------------------
AI 在這條測試裡把月支出設成 500,000，刻意讓餘額跌破零。
若輸入沒有走到負值，`max(0.0, remaining)` 就等於 `remaining`，
這條測試在 `legacy` 上**一樣是綠的**。
十份裡有兩份（run-B-MR-02、run-B-MR-05）沒有刻意壓負。

也就是說，要讓這條關係有價值需要兩個條件同時成立：
兩個輸出真的來自不同路徑，**而且**輸入走得到兩條路徑分歧的地方。
"""

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shadow import calc as legacy  # noqa: E402
from shadow import calc_fixed as fixed  # noqa: E402
from shadow.calc_fixed import Params  # noqa: E402

BOTH = pytest.mark.parametrize(
    "calculate", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"]
)


def get_base_params() -> Params:
    """原樣取自 run-A-MR-01.txt，未改動。"""
    return Params(
        current_age=30,
        retirement_age=65,
        life_expectancy=90,
        current_savings=1_000_000.0,
        monthly_investment=15_000.0,
        monthly_expense_today=50_000.0,
        annual_recurring_expense=100_000.0,
        labor_insurance_pension=0.0,
        labor_insurance_start_age=65,
        labor_pension_monthly=0.0,
        labor_pension_start_age=65,
        other_income=0.0,
        pre_retirement_return=0.06,
        post_retirement_return=0.04,
        inflation_rate=0.02,
        lump_sums=()
    )


# ↓↓↓ 以下整段原封不動取自 AI 的產物，只加了 @BOTH 這一行 ↓↓↓

# 把月支出設定極大以保證退休後餘額跌破零，進一步調高月支出會使最後一年的真實餘額
# (balances_raw[-1]) 變得更低；同時兩次結果的圖表軌跡 (balances_charted) 都必須
# 逐項等於真實軌跡，不得截斷 (PRD-03, PRD-12)。
@BOTH
def test_mr_charted_balances_veracity(calculate):
    p1 = dataclasses.replace(get_base_params(), monthly_expense_today=500_000.0)
    p2 = dataclasses.replace(p1, monthly_expense_today=1_000_000.0)
    res1 = calculate(p1)
    res2 = calculate(p2)

    assert res2.balances_raw[-1] < res1.balances_raw[-1]
    assert res1.balances_charted == res1.balances_raw
    assert res2.balances_charted == res2.balances_raw

# ↑↑↑ 原封不動結束 ↑↑↑


def test_the_two_fields_are_the_same_object_in_fixed():
    """把「恆綠」這件事釘死：在 calc_fixed 上，那兩個欄位是同一個物件。

    上面那條測試在 fixed 綠，有兩種可能的解釋：
      甲　實作是對的，所以沒截斷
      乙　那兩個欄位根本是同一個東西，比什麼都會綠
    這一條用 `is` 分辨。它綠，代表是乙。
    """
    res = fixed.calculate(get_base_params())
    assert res.balances_charted is res.balances_raw


def test_the_two_fields_are_separate_objects_in_legacy():
    """對照組：在 legacy 上它們是兩個各自算出來的 tuple，所以那條斷言有意義。"""
    res = legacy.calculate(get_base_params())
    assert res.balances_charted is not res.balances_raw

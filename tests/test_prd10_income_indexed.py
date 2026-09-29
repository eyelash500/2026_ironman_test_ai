"""PRD-10：退休後收入隨通膨調升——補上那一組從來沒有人餵過的輸入。

為什麼需要這條
------------
M14（退休後固定收入未隨通膨調升）從第一次量變異分數活到第二十八天。
不是斷言不夠嚴：golden v2 二十三組案例的 `other_income` 全部是 0，
零乘什麼都是零，拿掉通膨指數沒有任何一組會變。
規格早在 PRD-10 裁決過（2026-09-09），又改過一次基準年（2026-09-13），
決定做了兩次、寫了兩次，然後沒有任何一組測試輸入讓那個欄位非零。

這條關係怎麼來的
--------------
Day 25 逐條推過：齊次、單調、支出配置、自我一致，四類關係都碰不到 M14，
「要殺它需要一條關於通膨率與收入如何交互的關係」。
那條關係其實只有一句話：

    收入若隨通膨調升，它會抵銷一部分通膨對目標金額的影響。

所以：通膨率上升時，**有收入**的目標金額增幅，應該**小於沒有收入**的增幅。
M14 讓收入不隨通膨調升，兩個增幅就會完全相等——扣的是同一個常數。

這不需要知道目標金額是多少，只需要知道兩個差值的大小關係。

實測（沙箱預跑，正式數字以 pytest 為準）
----------------------------------
    calc_fixed：Δ有收入 14,621,896 < Δ無收入 18,277,370   成立
    注入 M14：  Δ有收入 18,277,370 = Δ無收入 18,277,370   不成立 → 殺掉

    python3 -m pytest tests/test_prd10_income_indexed.py -v
    python3 tools/mr_audit_batch.py tests/test_prd10_income_indexed.py
"""

import dataclasses
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shadow import calc_fixed as fixed  # noqa: E402
from shadow.calc_fixed import Params  # noqa: E402

# 收入設為非零，但遠低於支出，避免 PRD-09 的淨支出下限 max(0, ...) 介入。
BASE = Params(
    current_age=40,
    retirement_age=65,
    life_expectancy=85,
    current_savings=1_000_000.0,
    monthly_investment=10_000.0,
    monthly_expense_today=50_000.0,
    annual_recurring_expense=0.0,
    labor_insurance_pension=0.0,
    labor_insurance_start_age=65,
    labor_pension_monthly=0.0,
    labor_pension_start_age=65,
    other_income=10_000.0,
    pre_retirement_return=0.05,
    post_retirement_return=0.03,
    inflation_rate=0.02,
    lump_sums=(),
)


def _target(inflation: float, income: float) -> float:
    p = dataclasses.replace(BASE, inflation_rate=inflation, other_income=income)
    return fixed.calculate(p).target_fund


def test_prd10_indexed_income_offsets_part_of_inflation():
    """通膨率 2% → 4%：有收入時目標金額的增幅，必須小於沒有收入時的增幅。

    收入若隨通膨調升，通膨越高收入也越高，抵銷掉一部分支出的上漲。
    收入若固定不動（M14），兩種通膨率下扣的是同一個常數，增幅會相等。
    """
    delta_without_income = _target(0.04, 0.0) - _target(0.02, 0.0)
    delta_with_income = _target(0.04, 10_000.0) - _target(0.02, 10_000.0)

    assert delta_with_income < delta_without_income, (
        f"有收入的增幅 {delta_with_income:,.0f} 應小於無收入的增幅 "
        f"{delta_without_income:,.0f}；相等代表收入沒有隨通膨調升")


def test_prd10_income_actually_reduces_target():
    """前置：收入非零時目標金額確實變小。確認上一條不是在比較兩個一樣的東西。"""
    assert _target(0.02, 10_000.0) < _target(0.02, 0.0)

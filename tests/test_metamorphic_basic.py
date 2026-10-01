"""基礎蛻變測試套件：MR-01 (線性縮放) 與 MR-04 (單調性)。

驗證核心在無標準答案時，輸入變換與輸出響應是否符合嚴密的數學不變量。
支援 legacy.calculate 與 fixed.calculate 雙基底對照。
"""

import dataclasses
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shadow import calc as legacy  # noqa: E402
from shadow import calc_fixed as fixed  # noqa: E402
from shadow.calc import LumpSum, Params  # noqa: E402


def scale_money(p: Params, k: float) -> Params:
    """將所有金額類欄位同步放大 k 倍，年齡與比率類參數保持不變。"""
    scaled_lumps = tuple(
        dataclasses.replace(ls, amount=ls.amount * k) for ls in p.lump_sums
    )
    return dataclasses.replace(
        p,
        current_savings=p.current_savings * k,
        monthly_investment=p.monthly_investment * k,
        monthly_expense_today=p.monthly_expense_today * k,
        annual_recurring_expense=p.annual_recurring_expense * k,
        labor_insurance_pension=p.labor_insurance_pension * k,
        labor_pension_monthly=p.labor_pension_monthly * k,
        other_income=p.other_income * k,
        lump_sums=scaled_lumps,
    )


@pytest.fixture
def base_params() -> Params:
    """基準情境：35 歲、65 歲退休、壽命 85 歲，含基礎資產與開銷。"""
    return Params(
        current_age=35,
        retirement_age=65,
        life_expectancy=85,
        current_savings=500000.0,
        monthly_investment=15000.0,
        monthly_expense_today=30000.0,
        annual_recurring_expense=50000.0,
        labor_insurance_pension=18000.0,
        labor_insurance_start_age=65,
        labor_pension_monthly=12000.0,
        labor_pension_start_age=65,
        other_income=0.0,
        pre_retirement_return=0.06,
        post_retirement_return=0.04,
        inflation_rate=0.02,
        lump_sums=(LumpSum(age=70, amount=200000.0),),
    )


# ----------------------------------------------------------------------
# MR-01: Scale Invariance (線性尺度不變性)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("calc", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"])
@pytest.mark.parametrize("scale_factor", [0.5, 2.0, 10.0])
def test_mr01_scale_invariance(calc, base_params, scale_factor):
    """金額同乘 k，資產、目標金與缺口必須嚴格同乘 k (rel_tol=1e-9)。"""
    orig_res = calc(base_params)
    scaled_p = scale_money(base_params, scale_factor)
    scaled_res = calc(scaled_p)

    assert math.isclose(
        scaled_res.projected_savings,
        orig_res.projected_savings * scale_factor,
        rel_tol=1e-9,
    )
    assert math.isclose(
        scaled_res.target_fund,
        orig_res.target_fund * scale_factor,
        rel_tol=1e-9,
    )
    assert math.isclose(
        scaled_res.retirement_gap,
        orig_res.retirement_gap * scale_factor,
        rel_tol=1e-9,
    )


# ----------------------------------------------------------------------
# MR-04: Monotonicity (單調性公理群)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("calc", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"])
def test_mr04_savings_monotonicity(calc, base_params):
    """每月儲蓄增加 -> 累積資產不減、資金缺口不增。"""
    more_savings = dataclasses.replace(
        base_params, monthly_investment=base_params.monthly_investment + 5000.0
    )
    res_orig = calc(base_params)
    res_more = calc(more_savings)

    assert res_more.projected_savings >= res_orig.projected_savings
    assert res_more.retirement_gap <= res_orig.retirement_gap


@pytest.mark.parametrize("calc", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"])
def test_mr04_longer_life_never_lowers_target(calc, base_params):
    """壽命延長 -> 退休目標金額絕不減少。"""
    longer_life = dataclasses.replace(
        base_params, life_expectancy=base_params.life_expectancy + 5
    )
    assert calc(longer_life).target_fund >= calc(base_params).target_fund


@pytest.mark.parametrize("calc", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"])
def test_mr04_higher_expense_never_lowers_target(calc, base_params):
    """生活費用增加 -> 退休目標金額絕不減少。"""
    higher_expense = dataclasses.replace(
        base_params,
        monthly_expense_today=base_params.monthly_expense_today + 10000.0,
    )
    assert calc(higher_expense).target_fund >= calc(base_params).target_fund


@pytest.mark.parametrize("calc", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"])
def test_mr04_delayed_retirement_accumulates_more(calc, base_params):
    """延後退休 -> 累積期資產嚴格遞增 (在 S > 0 或 r > 0 條件下)。"""
    delayed = dataclasses.replace(
        base_params, retirement_age=base_params.retirement_age + 2
    )
    assert calc(delayed).projected_savings > calc(base_params).projected_savings

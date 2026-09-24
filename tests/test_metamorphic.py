"""四條蛻變關係：不需要知道正確答案，也能判對錯。

為什麼需要這種東西
----------------
Day 24 量到：AI 寫測試時，那個期望值的唯一來源是它自己的推導，
而要核算 `assert target_fund == 17837.019` 就得把二十一年一項一項算過——
成本跟自己重寫一條測試差不多。人核不動。

蛻變關係不問「答案是多少」，只問「輸入這樣變，輸出必須那樣變」。
底下四條，每一條都能在**完全不知道 target_fund 是多少**的情況下判對錯。

四條關係
-------
MR-01 線性齊次　所有金額 ×k　→　三個金額輸出也 ×k
MR-02 單調性　　月存↑／壽命↑／生活費↑／延後退休　→　方向固定
MR-03 支出配置　月支出與固定年支出互換、年總額不變　→　輸出逐位元相同
MR-04 自我一致　資金剛好等於目標金額　→　缺口為 0、期末餘額為 0

MR-03 的由來
-----------
原本規劃的是「六格支出重新分配、總計不變」，但那是受測物 HTML 的介面，
Python 這一層只有一個 `monthly_expense_today`。翻開實作才發現真正的不變量在這裡：

    expense_base_today = p.monthly_expense_today * 12 + p.annual_recurring_expense

**PRD-08 說兩者合併、共用同一組通膨指數**，所以只要年總額不變，
怎麼在「月支出」與「固定年支出」之間搬動都不該影響任何一個輸出。

寫出來不算完
-----------
一條關係可能是**廢話**——恆真、永遠不會紅、什麼都沒驗。
`tools/mr_audit.py` 拿 Day 19 的十四個領域變異體逐條驗收：
殺不掉任何變異體的關係，不列入。
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
from shadow.calc_fixed import LumpSum, Params  # noqa: E402

BOTH = pytest.mark.parametrize(
    "calc", [legacy.calculate, fixed.calculate], ids=["legacy", "fixed"]
)

MONEY_FIELDS = (
    "current_savings", "monthly_investment", "monthly_expense_today",
    "annual_recurring_expense", "labor_insurance_pension",
    "labor_pension_monthly", "other_income",
)


def scale_money(p: Params, k: float) -> Params:
    """所有金額欄位同乘 k，年齡與比率不動。"""
    return dataclasses.replace(
        p,
        lump_sums=tuple(dataclasses.replace(ls, amount=ls.amount * k) for ls in p.lump_sums),
        **{f: getattr(p, f) * k for f in MONEY_FIELDS},
    )


@pytest.fixture
def base() -> Params:
    """基準情境。`other_income` 刻意設為非零——Day 20 起它一直是 0，
    那條路徑因此從來沒被走過。"""
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
        other_income=5000.0,
        pre_retirement_return=0.06,
        post_retirement_return=0.04,
        inflation_rate=0.02,
        lump_sums=(LumpSum(age=70, amount=200000.0),),
    )


# ── MR-01 線性齊次 ────────────────────────────────────────────────
# 三個金額輸出都是輸入金額的一次齊次函式。年齡與比率不變，
# 所有金額同乘 k，結果必須剛好也乘 k——不必知道任何一次的值是多少。

@BOTH
@pytest.mark.parametrize("k", [0.5, 2.0, 10.0])
def test_mr01_money_is_homogeneous(calc, base, k):
    one = calc(base)
    two = calc(scale_money(base, k))
    for field in ("projected_savings", "target_fund", "retirement_gap"):
        assert math.isclose(getattr(two, field), getattr(one, field) * k, rel_tol=1e-9), field


# ── MR-02 單調性 ──────────────────────────────────────────────────
# 方向由領域常識決定，不需要任何數字：多存不會更窮，多活不會更便宜。

@BOTH
def test_mr02_more_saving_never_worse(calc, base):
    more = dataclasses.replace(base, monthly_investment=base.monthly_investment + 5000.0)
    assert calc(more).projected_savings >= calc(base).projected_savings
    assert calc(more).retirement_gap <= calc(base).retirement_gap


@BOTH
def test_mr02_longer_life_never_cheaper(calc, base):
    longer = dataclasses.replace(base, life_expectancy=base.life_expectancy + 5)
    assert calc(longer).target_fund >= calc(base).target_fund


@BOTH
def test_mr02_higher_expense_never_cheaper(calc, base):
    higher = dataclasses.replace(
        base, monthly_expense_today=base.monthly_expense_today + 10000.0)
    assert calc(higher).target_fund >= calc(base).target_fund


@BOTH
def test_mr02_more_income_never_costlier(calc, base):
    """退休後收入增加，需要自備的錢不會變多。"""
    richer = dataclasses.replace(base, other_income=base.other_income + 3000.0)
    assert calc(richer).target_fund <= calc(base).target_fund


# ── MR-03 支出配置不變 ────────────────────────────────────────────
# PRD-08：月支出與固定年支出合併、共用同一組通膨指數。
# 那麼年總額不變的前提下，錢記在哪一欄都不該影響結果。

@BOTH
@pytest.mark.parametrize("move", [12000.0, -36000.0])
def test_mr03_expense_split_is_invariant(calc, base, move):
    shifted = dataclasses.replace(
        base,
        monthly_expense_today=base.monthly_expense_today - move / 12.0,
        annual_recurring_expense=base.annual_recurring_expense + move,
    )
    one, two = calc(base), calc(shifted)
    assert two.target_fund == one.target_fund
    assert two.retirement_gap == one.retirement_gap
    assert two.balances_raw == one.balances_raw


# ── MR-04 自我一致性 ──────────────────────────────────────────────
# 把第一次執行的輸出，當成第二次執行的輸入：
# 報酬率與月存都設為 0 時，累積資產恆等於期初本金，
# 於是「期初本金 = 目標金額」就讓缺口歸零——而目標金額是多少，我們不必知道。

@BOTH
def test_mr04_funded_exactly_closes_the_gap(calc, base):
    flat = dataclasses.replace(base, monthly_investment=0.0, pre_retirement_return=0.0)
    target = calc(flat).target_fund

    funded = dataclasses.replace(flat, current_savings=target)
    res = calc(funded)

    assert math.isclose(res.projected_savings, target, rel_tol=1e-12)
    assert math.isclose(res.retirement_gap, 0.0, abs_tol=1e-6)
    assert math.isclose(res.balances_raw[-1], 0.0, abs_tol=1e-3)

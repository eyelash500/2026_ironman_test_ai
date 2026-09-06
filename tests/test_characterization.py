"""Characterization test：釘死受測物「現在」的行為。

這不是在測「它算得對不對」——**這裡面有好幾條斷言，鎖的正是已知的缺陷**。
目的是回歸防護：Day 30 修復時，任何行為改變都會讓對應的測試變紅，
我才分得出哪些是修好了、哪些是順手改壞了別的。

golden set v1 的組成見 golden/README.md。

    uv run --python 3.12 pytest tests/test_characterization.py -q
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc import LumpSum, Params, calculate  # noqa: E402

GOLDEN = json.loads((ROOT / "golden" / "golden_set_v1.json").read_text(encoding="utf-8"))
REL_TOL = 1e-12


def to_params(inp: dict) -> Params:
    return Params(
        current_age=inp["current_age"],
        retirement_age=inp["retirement_age"],
        life_expectancy=inp["life_expectancy"],
        current_savings=inp["current_savings"],
        monthly_investment=inp["monthly_investment"],
        monthly_expense_today=inp["monthly_expense_today"],
        annual_recurring_expense=inp.get("annual_recurring_expense", 0.0),
        labor_insurance_pension=inp.get("labor_insurance_pension", 0.0),
        labor_insurance_start_age=inp.get("labor_insurance_start_age", 0),
        labor_pension_monthly=inp.get("labor_pension_monthly", 0.0),
        labor_pension_start_age=inp.get("labor_pension_start_age", 0),
        other_income=inp.get("other_income", 0.0),
        pre_retirement_return=inp["pre_retirement_return"],
        post_retirement_return=inp["post_retirement_return"],
        inflation_rate=inp["inflation_rate"],
        lump_sums=tuple(LumpSum(**l) for l in inp.get("lump_sums", [])),
    )


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["id"])
def test_behavior_is_pinned(case):
    """每一組的輸出必須與 golden set 記錄的完全一致。"""
    r = calculate(to_params(case["input"]))
    exp = case["expected"]
    assert r.projected_savings == pytest.approx(exp["projected_savings"], rel=REL_TOL)
    assert r.target_fund == pytest.approx(exp["target_fund"], rel=REL_TOL)
    assert r.retirement_gap == pytest.approx(exp["retirement_gap"], rel=REL_TOL)
    assert r.balances_raw[-1] == pytest.approx(exp["final_balance_raw"], rel=REL_TOL)
    assert r.balances_charted[-1] == pytest.approx(exp["final_balance_charted"], rel=REL_TOL)


# --- 以下四條鎖的是缺陷本身。它們現在「通過」，代表缺陷還在。 ---

def test_defect_b_inverted_lifespan_yields_zero_target():
    """缺陷 B：壽命 <= 退休年齡 → 目標金額 0 → 畫面顯示沒有缺口。"""
    r = calculate(Params(current_age=42, retirement_age=65, life_expectancy=60,
                         current_savings=800_000, monthly_investment=19_391,
                         monthly_expense_today=30_000))
    assert r.target_fund == 0.0
    assert r.retirement_gap < 0        # 負缺口 → UI 顯示「沒有缺口」


def test_defect_c_ghost_expense_counted_but_never_charted():
    """缺陷 C：超過壽命的大筆支出，計入目標金額，卻不出現在圖表上。"""
    base = dict(current_age=42, retirement_age=65, life_expectancy=85,
                current_savings=800_000, monthly_investment=19_391,
                monthly_expense_today=30_000)
    without = calculate(Params(**base))
    with_ghost = calculate(Params(**base, lump_sums=(LumpSum(age=95, amount=2_000_000),)))

    assert with_ghost.target_fund > without.target_fund          # 有計入
    assert with_ghost.balances_raw == without.balances_raw       # 但圖上完全看不見


def test_defect_a_prime_clamp_hides_deficit():
    """缺陷 A'：真實餘額為負時，圖表資料被夾成 0。"""
    r = calculate(Params(current_age=42, retirement_age=65, life_expectancy=85,
                         current_savings=0, monthly_investment=0,
                         monthly_expense_today=30_000))
    assert r.balances_raw[-1] < 0
    assert r.balances_charted[-1] == 0.0


def test_defect_a_target_uses_ordinary_annuity():
    """缺陷 A：目標金額用期末年金；正確的期初值應為其 (1+r) 倍。"""
    p = Params(current_age=42, retirement_age=65, life_expectancy=85,
               current_savings=800_000, monthly_investment=19_391,
               monthly_expense_today=30_000, post_retirement_return=0.04,
               inflation_rate=0.02)
    r = calculate(p)

    # 手算期初版：折現指數少一期
    wy = p.retirement_age - p.current_age
    due = sum(
        p.monthly_expense_today * 12 * (1 + p.inflation_rate) ** (wy + i)
        / (1 + p.post_retirement_return) ** (i - 1)
        for i in range(1, p.life_expectancy - p.retirement_age + 1)
    )
    assert due / r.target_fund == pytest.approx(1 + p.post_retirement_return, rel=1e-12)

"""Golden Set v2 測試套件：以 PRD v1.2 基準真理驗收 shadow/calc_fixed.py。

23 組案例來源於 golden/golden_set_v2.json：
- 21 組數值完全鎖定（rel_tol = 1e-12）
- 2 組違反 PRD-04 年齡約束者必須拋出 ValueError
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc_fixed import LumpSum, Params, calculate  # noqa: E402

GOLDEN = json.loads((ROOT / "golden" / "golden_set_v2.json").read_text(encoding="utf-8"))
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
        pre_retirement_return=inp.get("pre_retirement_return", 0.08),
        post_retirement_return=inp.get("post_retirement_return", 0.04),
        inflation_rate=inp.get("inflation_rate", 0.02),
        lump_sums=tuple(LumpSum(**l) for l in inp.get("lump_sums", [])),
    )


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["id"])
def test_golden_v2_case(case):
    p = to_params(case["input"])
    exp = case["expected"]
    if exp is None:
        with pytest.raises(ValueError):
            calculate(p)
    else:
        r = calculate(p)
        assert r.projected_savings == pytest.approx(exp["projected_savings"], rel=REL_TOL)
        assert r.target_fund == pytest.approx(exp["target_fund"], rel=REL_TOL)
        assert r.retirement_gap == pytest.approx(exp["retirement_gap"], rel=REL_TOL)
        assert r.balances_raw[-1] == pytest.approx(exp["final_balance_raw"], rel=REL_TOL)
        assert r.balances_charted[-1] == pytest.approx(exp["final_balance_charted"], rel=REL_TOL)

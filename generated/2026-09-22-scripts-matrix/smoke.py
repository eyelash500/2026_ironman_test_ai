import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc_fixed import LumpSum, Params, Result, calculate  # noqa: E402


def _p(**kw):
    base = dict(current_age=30, retirement_age=65, life_expectancy=85,
                current_savings=0.0, monthly_investment=0.0,
                monthly_expense_today=30000.0)
    base.update(kw)
    return Params(**base)


def test_zero_return_is_linear():
    p = _p(current_savings=100.0, monthly_investment=10.0, pre_retirement_return=0.0)
    assert calculate(p).projected_savings == pytest.approx(100.0 + 10.0 * 35 * 12, rel=1e-12)


def test_negative_amount_rejected():
    with pytest.raises(ValueError, match="金額不得為負數"):
        calculate(_p(current_savings=-1.0))

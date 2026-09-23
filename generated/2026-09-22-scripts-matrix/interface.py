from dataclasses import dataclass, field


@dataclass(frozen=True)
class LumpSum:
    age: int                              # A_e
    amount: float


@dataclass(frozen=True)
class Params:
    current_age: int                      # A_c
    retirement_age: int                   # A_r
    life_expectancy: int                  # A_d
    current_savings: float
    monthly_investment: float
    monthly_expense_today: float
    annual_recurring_expense: float = 0.0

    labor_insurance_pension: float = 0.0
    labor_insurance_start_age: int = 0     # A_p
    labor_pension_monthly: float = 0.0
    labor_pension_start_age: int = 0       # A_p
    other_income: float = 0.0

    pre_retirement_return: float = 0.08    # r
    post_retirement_return: float = 0.04   # r_p
    inflation_rate: float = 0.02           # i
    lump_sums: tuple[LumpSum, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Result:
    projected_savings: float
    target_fund: float
    retirement_gap: float
    balances_raw: tuple[float, ...]
    balances_charted: tuple[float, ...]


def calculate(p: Params) -> Result:
    """本次任務不提供實作本體。"""
    ...

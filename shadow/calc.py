"""受測物「進階退休規劃試算」的 Python 影子模型。

逐行對應 sut/進階退休規劃試算.html 第 292-375 行，行號標於各段。
抽取規則見 oracle/calc.js 檔頭（Day 5 閘門 2 裁決：機械式抽取，不修正任何已知缺陷）。

本檔由 AI 產生。驗收器是 tests/test_differential.py——500 組隨機輸入對 oracle/calc.js
逐筆比對，全部相符才算通過。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LumpSum:
    """大筆支出：發生年齡與今日幣值金額。"""
    age: int
    amount: float


@dataclass(frozen=True)
class Params:
    current_age: int
    retirement_age: int
    life_expectancy: int
    current_savings: float
    monthly_investment: float
    monthly_expense_today: float
    annual_recurring_expense: float = 0.0

    # 退休後收入：三個來源，各自有起領年齡（對應 313-318 行）
    labor_insurance_pension: float = 0.0     # 勞保年金，月額
    labor_insurance_start_age: int = 0
    labor_pension_monthly: float = 0.0       # 勞退月領
    labor_pension_start_age: int = 0
    other_income: float = 0.0                # 其他收入，月額

    pre_retirement_return: float = 0.08
    post_retirement_return: float = 0.04
    inflation_rate: float = 0.02
    lump_sums: tuple[LumpSum, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Result:
    projected_savings: float
    target_fund: float
    retirement_gap: float
    balances_raw: tuple[float, ...]      # 逐年真實餘額（未夾 0）
    balances_charted: tuple[float, ...]  # 圖表看到的（374 行夾 0 後）


def _inflated_income(p: Params, age: int, years_from_now: int) -> float:
    """312-318 行：三個收入來源，各自判斷起領年齡。"""
    infl = (1 + p.inflation_rate) ** years_from_now
    income = p.other_income * 12 * infl
    if age >= p.labor_insurance_start_age:
        income += p.labor_insurance_pension * 12 * infl
    if age >= p.labor_pension_start_age:
        income += p.labor_pension_monthly * 12 * infl
    return income


def calculate(p: Params) -> Result:
    working_years = p.retirement_age - p.current_age          # 292
    retirement_years = p.life_expectancy - p.retirement_age   # 293 純減法，無防護

    # --- 295-299 累積期 ---
    fv_current = p.current_savings * (1 + p.pre_retirement_return) ** working_years
    monthly_rate = p.pre_retirement_return / 12                # 297 名目月利率
    if monthly_rate > 0:
        fv_monthly = p.monthly_investment * (
            ((1 + monthly_rate) ** (working_years * 12) - 1) / monthly_rate
        )
    else:
        fv_monthly = p.monthly_investment * working_years * 12
    projected_savings = fv_current + fv_monthly

    total_annual_expense_today = p.monthly_expense_today * 12 + p.annual_recurring_expense

    # --- 305-323 目標金額：期末年金折現 ---
    target_for_expenses = 0.0
    for i in range(1, retirement_years + 1):                   # 306 i 從 1 開始
        age = p.retirement_age + i
        years_from_now = working_years + i
        inflated = total_annual_expense_today * (1 + p.inflation_rate) ** years_from_now
        net = max(0.0, inflated - _inflated_income(p, age, years_from_now))   # 320
        target_for_expenses += net / (1 + p.post_retirement_return) ** i      # 321-322

    # --- 325-334 大筆支出：只檢查下界 ---
    total_lump_pv = 0.0
    for ls in p.lump_sums:
        if ls.age >= p.retirement_age:                         # 329 缺陷 C：無上界
            inflated = ls.amount * (1 + p.inflation_rate) ** (ls.age - p.current_age)
            total_lump_pv += inflated / (1 + p.post_retirement_return) ** (
                ls.age - p.retirement_age
            )

    target_fund = target_for_expenses + total_lump_pv           # 335

    # --- 347-375 提領期：期初扣款 ---
    remaining = projected_savings
    raw: list[float] = []
    charted: list[float] = []
    for i in range(1, retirement_years + 1):                    # 349
        age = p.retirement_age + i
        years_from_now = working_years + i
        inflated = total_annual_expense_today * (1 + p.inflation_rate) ** years_from_now
        net_expense = max(0.0, inflated - _inflated_income(p, age, years_from_now))   # 363

        lump_this_year = 0.0
        for ls in p.lump_sums:
            if ls.age == age:                                   # 367 只在迴圈走得到的年份才配對
                lump_this_year += ls.amount * (1 + p.inflation_rate) ** (
                    ls.age - p.current_age
                )

        remaining = (remaining - (net_expense + lump_this_year)) * (
            1 + p.post_retirement_return
        )                                                        # 372 先扣後滾
        raw.append(remaining)
        charted.append(max(0.0, remaining))                      # 374 遮羞布

    return Result(
        projected_savings=projected_savings,
        target_fund=target_fund,
        retirement_gap=target_fund - projected_savings,          # 380
        balances_raw=tuple(raw),
        balances_charted=tuple(charted),
    )

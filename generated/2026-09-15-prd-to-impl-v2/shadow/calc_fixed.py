
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LumpSum:
    age: int          # A_e，大筆支出發生年齡
    amount: float     # 今日幣值金額


@dataclass(frozen=True)
class Params:
    current_age: int                      # A_c
    retirement_age: int                   # A_r
    life_expectancy: int                  # A_d
    current_savings: float                # 期初本金
    monthly_investment: float             # 月存金額
    monthly_expense_today: float          # 退休後每月花費（今日幣值）
    annual_recurring_expense: float = 0.0 # 固定年支出（今日幣值）

    labor_insurance_pension: float = 0.0  # 勞保老年年金，月額
    labor_insurance_start_age: int = 0    # 勞保請領年齡 A_p
    labor_pension_monthly: float = 0.0    # 勞退月領，月額
    labor_pension_start_age: int = 0      # 勞退請領年齡 A_p
    other_income: float = 0.0             # 其他收入，月額

    pre_retirement_return: float = 0.08   # r
    post_retirement_return: float = 0.04  # r_p
    inflation_rate: float = 0.02          # i
    lump_sums: tuple[LumpSum, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Result:
    projected_savings: float              # 退休當下的累積資產
    target_fund: float                    # 退休當下所需的目標金額
    retirement_gap: float                 # target_fund - projected_savings
    balances_raw: tuple[float, ...]       # 逐年真實餘額
    balances_charted: tuple[float, ...]   # 供圖表使用的逐年餘額


def calculate(p: Params) -> Result:
    # PRD-04: 輸入校驗
    if not (p.current_age > 0 and p.current_age < p.retirement_age and p.retirement_age < p.life_expectancy):
        raise ValueError("年齡必須為正整數且 current_age < retirement_age < life_expectancy")
    
    if p.labor_insurance_start_age < 0 or p.labor_pension_start_age < 0:
        raise ValueError("請領年齡不得為負數")
        
    amounts = [
        p.current_savings,
        p.monthly_investment,
        p.monthly_expense_today,
        p.annual_recurring_expense,
        p.labor_insurance_pension,
        p.labor_pension_monthly,
        p.other_income
    ]
    if any(amt < 0 for amt in amounts):
        raise ValueError("金額不得為負數")
        
    for ls in p.lump_sums:
        if ls.age < 0:
            raise ValueError("大筆支出年齡不得為負數")
        if ls.amount < 0:
            raise ValueError("大筆支出金額不得為負數")
            
    # PRD-01: 累積期增值
    months = (p.retirement_age - p.current_age) * 12
    r_monthly = p.pre_retirement_return / 12.0
    
    if r_monthly == 0.0:
        projected_savings = p.current_savings + p.monthly_investment * months
    else:
        compounded_savings = p.current_savings * ((1.0 + r_monthly) ** months)
        accumulated_investment = p.monthly_investment * (((1.0 + r_monthly) ** months - 1.0) / r_monthly)
        projected_savings = compounded_savings + accumulated_investment
        
    net_expenses = []
    
    # PRD-02: 目標金額折現 (共 A_d - A_r + 1 年，第一期對應 A_r)
    for t in range(p.retirement_age, p.life_expectancy + 1):
        # PRD-08: 固定年支出與月支出合併計算
        expense_base_today = p.monthly_expense_today * 12 + p.annual_recurring_expense
        # PRD-02, PRD-08: 支出端通膨基準鎖現齡 A_c
        total_expense = expense_base_today * ((1.0 + p.inflation_rate) ** (t - p.current_age))
        
        # PRD-05: 大筆支出區間，通膨基準鎖 A_c
        for ls in p.lump_sums:
            if ls.age == t:
                total_expense += ls.amount * ((1.0 + p.inflation_rate) ** (t - p.current_age))
                
        total_income = 0.0
        
        # PRD-06, PRD-10: 勞保年金，通膨基準鎖 A_p
        if t >= p.labor_insurance_start_age and p.labor_insurance_start_age > 0:
            total_income += p.labor_insurance_pension * 12 * ((1.0 + p.inflation_rate) ** (t - p.labor_insurance_start_age))
            
        # PRD-07, PRD-10: 勞退月領，通膨基準鎖 A_p
        if t >= p.labor_pension_start_age and p.labor_pension_start_age > 0:
            total_income += p.labor_pension_monthly * 12 * ((1.0 + p.inflation_rate) ** (t - p.labor_pension_start_age))
            
        # PRD-10: 其他收入視為今日幣值，通膨基準鎖 A_c
        total_income += p.other_income * 12 * ((1.0 + p.inflation_rate) ** (t - p.current_age))
        
        # PRD-09: 淨支出下限 max(0, 支出 - 收入)
        net_exp = max(0.0, total_expense - total_income)
        net_expenses.append(net_exp)
        
    target_fund = 0.0
    balances = []
    current_balance = projected_savings
    
    for idx, net_exp in enumerate(net_expenses):
        # PRD-02: 目標金額折現
        target_fund += net_exp / ((1.0 + p.post_retirement_return) ** idx)
        
        # PRD-03: 提領餘額軌跡，期初扣款，禁止 Math.max(0, ...) 截斷
        balance_after_deduction = current_balance - net_exp
        current_balance = balance_after_deduction * (1.0 + p.post_retirement_return)
        balances.append(current_balance)
        
    balances_tuple = tuple(balances)
    
    return Result(
        projected_savings=projected_savings,
        target_fund=target_fund,
        retirement_gap=target_fund - projected_savings,
        balances_raw=balances_tuple,
        # PRD-12: 圖表餘額保真，必須逐項等於 balances_raw，不得下限截斷
        balances_charted=balances_tuple
    )

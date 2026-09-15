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


def calculate_retirement(params: Params) -> Result:
    # PRD-04: 輸入校驗
    if not (type(params.current_age) is int and type(params.retirement_age) is int and type(params.life_expectancy) is int):
        raise ValueError("A_c, A_r, A_d 必須為整數")
    
    if not (params.current_age > 0 and params.retirement_age > 0 and params.life_expectancy > 0):
        raise ValueError("A_c, A_r, A_d 必須為正整數")
        
    if not (params.current_age < params.retirement_age < params.life_expectancy):
        raise ValueError("必須滿足現齡 < 退休年齡 < 預期壽命 (A_c < A_r < A_d)")
        
    amounts = [
        params.current_savings, params.monthly_investment, params.monthly_expense_today,
        params.annual_recurring_expense, params.labor_insurance_pension,
        params.labor_pension_monthly, params.other_income
    ]
    if any(amt < 0 for amt in amounts):
        raise ValueError("所有金額參數必須非負")
        
    for ls in params.lump_sums:
        if ls.amount < 0:
            raise ValueError("大筆支出金額必須非負")

    # PRD-01: 累積期增值
    A_c = params.current_age
    A_r = params.retirement_age
    A_d = params.life_expectancy
    
    months = (A_r - A_c) * 12
    r_m = params.pre_retirement_return / 12.0
    
    if r_m == 0:
        projected_savings = params.current_savings + params.monthly_investment * months
    else:
        projected_savings = (params.current_savings * (1 + r_m)**months + 
                             params.monthly_investment * (((1 + r_m)**months - 1) / r_m))

    net_expenses_by_year = []
    
    # 退休後逐年計算 (t 從 A_r 到 A_d)
    for t in range(A_r, A_d + 1):
        
        # PRD-08: 固定年支出與月支出合併
        base_annual_expense = params.monthly_expense_today * 12 + params.annual_recurring_expense
        
        # PRD-02: 支出端通膨基準鎖現齡 A_c
        expense_t = base_annual_expense * (1 + params.inflation_rate)**(t - A_c)
        
        # PRD-05: 大筆支出區間 (僅 A_r <= A_e <= A_d 計入，通膨基準鎖 A_c)
        for ls in params.lump_sums:
            if ls.age == t and A_r <= ls.age <= A_d:
                expense_t += ls.amount * (1 + params.inflation_rate)**(t - A_c)
                
        income_t = 0.0
        
        # PRD-06, PRD-10: 勞保年金 (t >= A_p 計入，通膨鎖 A_p)
        if t >= params.labor_insurance_start_age:
            income_t += params.labor_insurance_pension * 12 * (1 + params.inflation_rate)**(t - params.labor_insurance_start_age)
            
        # PRD-07, PRD-10: 勞退月領 (t >= A_p 計入，通膨鎖 A_p)
        if t >= params.labor_pension_start_age:
            income_t += params.labor_pension_monthly * 12 * (1 + params.inflation_rate)**(t - params.labor_pension_start_age)
            
        # PRD-10: 其他收入 (通膨鎖 A_c)
        income_t += params.other_income * 12 * (1 + params.inflation_rate)**(t - A_c)
        
        # PRD-09: 淨支出下限 (max(0, 支出 - 收入)，盈餘不滾存)
        net_expense = max(0.0, expense_t - income_t)
        net_expenses_by_year.append(net_expense)

    # PRD-02: 目標金額折現 (期初年金)
    target_fund = 0.0
    r_p = params.post_retirement_return
    for i, net_exp in enumerate(net_expenses_by_year):
        target_fund += net_exp / ((1 + r_p) ** i)
        
    retirement_gap = target_fund - projected_savings

    # PRD-03: 提領餘額軌跡 (期初扣款)
    balances_raw_list = []
    current_balance = projected_savings
    
    for net_exp in net_expenses_by_year:
        # PRD-03: 禁止截斷真實餘額
        balances_raw_list.append(current_balance)
        current_balance = (current_balance - net_exp) * (1 + r_p)
        
    balances_raw = tuple(balances_raw_list)
    
    # GAP-1: balances_charted 供圖表使用的逐年餘額
    balances_charted = tuple(max(0.0, b) for b in balances_raw)

    return Result(
        projected_savings=projected_savings,
        target_fund=target_fund,
        retirement_gap=retirement_gap,
        balances_raw=balances_raw,
        balances_charted=balances_charted
    )
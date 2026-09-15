"""PRD v1.2 的實作。**尚未被證明正確**——第三幕與第四幕的全部工作就是在證明它。

與 `shadow/calc.py` 的分工
------------------------
`calc.py`      Characterization Model，忠實複製受測物現狀（含四個缺陷）。代表「它怎麼動」。
`calc_fixed.py` 照 PRD v1.2 寫的版本。代表「它該怎麼動」。

本檔由 AI 依規格獨立產生，嚴格未看 legacy。生成環境、提示詞、原始輸出與
三道驗收器的結果，見 `generated/2026-09-15-prd-to-impl-v2/`。
驗收器實作為 `tools/verify_fixed.py`，執行 `python3 tools/verify_fixed.py`。

已知限制
-------
- 單次生成（temperature = 1），非決定性。通過三道驗收器不等於這份規格穩定地可被實作。
- `balances_raw` 的語意與 legacy 不同：本檔記期末餘額，legacy 記期初扣款後滾存。
  故 golden v2 的 `final_balance_raw` 不可與 v1 直接比較。

模型自列的規格缺口（原樣保留，逐條尚未裁決）
  GAP: PRD-02 目標金額折現：規格未載明折現率為何。本實作採用退休後報酬率 `r_p` 作為折現率，將 `A_r` 至 `A_d` 區間各年度的「期初淨支出」折現至 `A_r` 年初。
  GAP: PRD-03 提領餘額軌跡：規格說明期初扣款，但未載明軌跡記錄的是期初或期末餘額。本實作記錄「期末餘額」，即每年 `(年初餘額 - 當年淨支出) * (1 + r_p)` 作為該年度的真實餘額。
  GAP: PRD-04 輸入校驗：規格要求「年齡為正整數」，但介面契約中 `labor_insurance_start_age` 等預設為 0。本實作強制要求 `current_age`、`retirement_age`、`life_expectancy` 為正整數且嚴格遞增；其餘年齡欄位（`A_p`, `A_e`）允許為非負整數（>= 0）。
  GAP: PRD-04 輸入校驗：規格要求「金額非負」，但未明列範圍。本實作定義所有本金、月存、支出、收入與 LumpSum 之金額欄位皆須 >= 0，而報酬率 (`r`, `r_p`) 與通膨率 (`i`) 允許為負。
  GAP: PRD-05 大筆支出區間：若有多筆大筆支出發生於同一年，規格未明示處理方式，本實作將於該年度直接加總計算。
"""


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

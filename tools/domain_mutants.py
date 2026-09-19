"""領域變異體清單：依金融業務規則人手設計的 14 個語意缺陷。

基底：`shadow/calc_fixed.py`（PRD v1.2 實作）。
由 `tools/harness.py` 載入並注入執行。

分層原則
--------
- 實證錯法：在受測物或同批工具裡 grep 得到位置，或第一幕驗屍時實測過。
- 推測錯法：精算邏輯上想得到的偏離、邊界漂移或自作聰明，目前沒有實際案例。

判準是「能不能指出它在真實程式碼裡的位置」。逐個的證據記在下方 `EVIDENCE`。

跨檔案的兩個實證（四個檔案互相對照，行號 2026-09-18 實地 grep）
--------------------------------------------------------
- 年報酬率 `/ 12` 直接當月利率：進階 297；目標導向 292、316、374；
  整合月複利 217、262、287 —— 3 檔 7 處。
- `Math.max(0, ...)` 抹平負值：5 處，但**不是同一個錯法**：
  - 淨支出截斷（PRD-09 裁決刻意保留的行為，不是缺陷）：
    進階 320、363；目標導向 274 —— 2 檔 3 處 → M05
  - 圖表／餘額夾 0（缺陷 A'，遮蔽赤字）：
    進階 374；對照組 438 —— 2 檔 2 處 → M02

  原本五處整組掛在缺陷 A' 名下，逐行讀完才拆開。
  **grep 數得出次數，數不出語意。**
"""

from __future__ import annotations

from harness import Mutant

REL_SOURCE = "shadow/calc_fixed.py"

DOMAIN_MUTANTS: tuple[Mutant, ...] = (
    # M01: 缺陷 A 原型：期初年金變期末年金
    Mutant(
        id="M01",
        original="target_fund += net_exp / ((1.0 + p.post_retirement_return) ** idx)",
        mutated="target_fund += net_exp / ((1.0 + p.post_retirement_return) ** (idx + 1))",
        simulates="ANNUITY_DUE_TO_ORD: 折現指數從 idx 改為 idx + 1，期初年金變期末年金，低估目標金額",
    ),

    # M02: 缺陷 A' 原型：餘額軌跡加回遮羞布
    Mutant(
        id="M02",
        original="balances.append(current_balance)",
        mutated="balances.append(max(0.0, current_balance))",
        simulates="DEFICIT_CLAMP_ON: 提領期餘額軌跡夾 0，遮蔽真實晚年赤字（2 檔 2 處；另外 3 處 max(0,…) 是 PRD-09 的淨支出截斷，歸 M05）",
    ),

    # M03: 偏離 PRD-01：名目月利率被「優雅地」改為有效月利率
    Mutant(
        id="M03",
        original="r_monthly = p.pre_retirement_return / 12.0",
        mutated="r_monthly = (1.0 + p.pre_retirement_return) ** (1.0 / 12.0) - 1.0",
        simulates="RATE_EFF_INSTEAD_OF_NOMINAL: 擅自改用有效月利率，測試若殺不死代表未鎖死名目定義",
    ),

    # M04: 挑戰 PRD-01：退回受測物本金年複利、月存月複利之混用狀態
    Mutant(
        id="M04",
        original="compounded_savings = p.current_savings * ((1.0 + r_monthly) ** months)",
        mutated="compounded_savings = p.current_savings * ((1.0 + p.pre_retirement_return) ** (p.retirement_age - p.current_age))",
        simulates="UNIFY_COMPOUND_FREQ: 本金退回年複利混用，測試是否能防範公式被擅自打破月複利裁決",
    ),

    # M05: 挑戰 PRD-09：允許提領期盈餘滾入資產
    Mutant(
        id="M05",
        original="net_exp = max(0.0, total_expense - total_income)",
        mutated="net_exp = total_expense - total_income",
        simulates="ALLOW_SURPLUS_CARRYOVER: 移除截斷，允許收入大於支出時產生負淨支出滾存",
    ),

    # M06: 缺陷 C 原型：身故後大筆支出幽靈扣款
    Mutant(
        id="M06",
        original="for t in range(p.retirement_age, p.life_expectancy + 1):",
        mutated="for t in range(p.retirement_age, max([p.life_expectancy] + [ls.age for ls in p.lump_sums]) + 1):",
        simulates="POST_MORTEM_EXPENSE: 移除大筆支出壽命上界檢查，身故後幽靈支出擴張提領期並影響目標金額",
    ),

    # M07: 修復缺陷 C 的常見二次事故：大筆支出條件寫成大於等於導致連年重複扣款
    Mutant(
        id="M07",
        original="if ls.age == t:",
        mutated="if t >= ls.age:",
        simulates="LUMP_MATCH_GE: 大筆支出年齡比對寫成 >=，導致後續年份連年重複扣款",
    ),

    # M08: 缺陷 B 原型：壽命小於等於退休年齡未擋
    Mutant(
        id="M08",
        original='if not (p.current_age > 0 and p.current_age < p.retirement_age and p.retirement_age < p.life_expectancy):\n        raise ValueError("年齡必須為正整數且 current_age < retirement_age < life_expectancy")',
        mutated='if not (p.current_age > 0 and p.current_age < p.retirement_age):\n        raise ValueError("年齡必須為正整數且 current_age < retirement_age")',
        simulates="LIFE_LE_RETIRE_PASS: 移除壽命大於退休年齡校驗，放行荒謬年齡輸入",
    ),

    # M09: 缺陷 D 原型：金額負值校驗失效
    Mutant(
        id="M09",
        original='if any(amt < 0 for amt in amounts):\n        raise ValueError("金額不得為負數")',
        mutated="pass  # 移除金額負值校驗",
        simulates="INPUT_SILENT_ZERO: 金額防呆失效，允許負值金額通過",
    ),

    # M10: 索引差一：通膨指數基準年偏移
    Mutant(
        id="M10",
        original="total_expense = expense_base_today * ((1.0 + p.inflation_rate) ** (t - p.current_age))",
        mutated="total_expense = expense_base_today * ((1.0 + p.inflation_rate) ** (t - p.current_age - 1))",
        simulates="INFLATION_BASE_OFF_BY_ONE: 通膨折現基準年少算一年，指數偏移",
    ),

    # M11: 邊界切換點偏移：退休初期餘額誤套用退休前報酬率
    Mutant(
        id="M11",
        original="current_balance = balance_after_deduction * (1.0 + p.post_retirement_return)",
        mutated="current_balance = balance_after_deduction * (1.0 + (p.pre_retirement_return if idx == 0 else p.post_retirement_return))",
        simulates="RETURN_SWITCH_OFF_BY_ONE: 跨越退休點前後報酬率切換點錯置，提領期初期誤套用退休前報酬率",
    ),

    # M12: 請領年齡邊界偏移：起領年齡條件從 >= 改為 >
    Mutant(
        id="M12",
        original="if t >= p.labor_insurance_start_age and p.labor_insurance_start_age > 0:",
        mutated="if t > p.labor_insurance_start_age and p.labor_insurance_start_age > 0:",
        simulates="INCOME_START_GT_GE: 起領年齡邊界嚴格化，首年年金金流漏計",
    ),

    # M13: 幣值混淆：大筆支出未計通膨
    Mutant(
        id="M13",
        original="total_expense += ls.amount * ((1.0 + p.inflation_rate) ** (t - p.current_age))",
        mutated="total_expense += ls.amount",
        simulates="LUMP_SUM_NO_INFLATION: 大筆支出以名目現值折算，忽略通膨平減",
    ),

    # M14: 違反 PRD-10：年金收入固定未抗通膨
    Mutant(
        id="M14",
        original="total_income += p.other_income * 12 * ((1.0 + p.inflation_rate) ** (t - p.current_age))",
        mutated="total_income += p.other_income * 12",
        simulates="INCOME_NOT_INDEXED: 退休後固定收入未隨通膨調升，實質購買力受損",
    ),
)


# 證據等級：實證（有跨檔行號或第一幕實測）／推測（設計出來的）
# 8 實證、6 推測。分子與分母出自同一個人，同一個盲區會同時出現在兩邊。
EVIDENCE: dict[str, str] = {
    "M01": "實證・第一幕實測（缺陷 A 驗屍）",
    "M02": "實證・2 檔 2 處（進階 374、對照組 438）",
    "M03": "實證・3 檔 7 處（`/12` 當月利率）；變異方向是「比規格更正確」",
    "M04": "推測・挑戰 PRD-01 的雙頻率裁決",
    "M05": "實證・2 檔 3 處（進階 320、363、目標導向 274）",
    "M06": "實證・第一幕實測（缺陷 C 驗屍）",
    "M07": "推測・修缺陷 C 的二次事故",
    "M08": "實證・自然實驗（對照組有防呆、受測物 isNaN/alert 各 0 次）",
    "M09": "實證・第一幕實測（缺陷 D 驗屍）",
    "M10": "推測・索引差一",
    "M11": "推測・報酬率切換點偏移",
    "M12": "推測・邊界嚴格化",
    "M13": "推測・幣值混淆（僅單檔提及，不足以稱跨檔）",
    "M14": "實證・退化型（進階 355 行已正確套用通膨，變異是把對的改壞）",
}


def audit() -> int:
    """交給引擎之前的兩道機械檢查：片段唯一性與變異後語法。"""
    import ast
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, REL_SOURCE), encoding="utf-8").read()

    problems: list[str] = []
    for m in DOMAIN_MUTANTS:
        hits = src.count(m.original)
        if hits != 1:
            problems.append(f"{m.id}：目標片段出現 {hits} 次，必須剛好 1 次")
            continue
        mutated = src.replace(m.original, m.mutated)
        if mutated == src:
            problems.append(f"{m.id}：置換後與原檔相同")
            continue
        try:
            ast.parse(mutated)
        except SyntaxError as exc:
            problems.append(f"{m.id}：變異後語法錯誤（第 {exc.lineno} 行）{exc.msg}")
    missing = [m.id for m in DOMAIN_MUTANTS if m.id not in EVIDENCE]
    if missing:
        problems.append(f"缺少證據等級：{'、'.join(missing)}")

    if problems:
        print(f"目錄不合格（{len(problems)} 項）：")
        for p in problems:
            print("  -", p)
        return 1
    n = len(DOMAIN_MUTANTS)
    emp = sum(1 for v in EVIDENCE.values() if v.startswith("實證"))
    print(f"片段唯一性：{n} / {n} 通過")
    print(f"變異後語法：{n} / {n} 可編譯")
    print(f"證據等級：實證 {emp}、推測 {n - emp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(audit())

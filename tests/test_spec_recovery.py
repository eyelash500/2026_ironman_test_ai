"""規格考古自動化分析測試 (test_spec_recovery.py)

本測試透過 Python AST (抽象語法樹) 與反射機制，自動化檢驗影子模型 `shadow/calc.py`
中所隱含的計算假設與十個未定歧義現場 (RC-01 至 RC-10)。
驗證「規格不是讀文件讀出來的，而是從程式碼結構中逆向提取出來的」。
"""

import ast
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CALC_PATH = ROOT / "shadow" / "calc.py"


@pytest.fixture(scope="module")
def calc_ast():
    """解析 shadow/calc.py 原始碼為 AST 樹。"""
    source = CALC_PATH.read_text(encoding="utf-8")
    return ast.parse(source)


@pytest.fixture(scope="module")
def calculate_func_node(calc_ast):
    """提取 calculate 函數的 AST 節點。"""
    for node in calc_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name == "calculate":
            return node
    pytest.fail("Could not find calculate() function in shadow/calc.py AST")


def test_params_dataclass_fields():
    """驗證 Params 資料類別完整包含 16 個參數欄位與型態註釋。"""
    import sys
    sys.path.insert(0, str(ROOT / "shadow"))
    from calc import Params

    sig = inspect.signature(Params)
    fields = list(sig.parameters.keys())
    expected_fields = [
        "current_age",
        "retirement_age",
        "life_expectancy",
        "current_savings",
        "monthly_investment",
        "monthly_expense_today",
        "annual_recurring_expense",
        "labor_insurance_pension",
        "labor_insurance_start_age",
        "labor_pension_monthly",
        "labor_pension_start_age",
        "other_income",
        "pre_retirement_return",
        "post_retirement_return",
        "inflation_rate",
        "lump_sums",
    ]
    for ef in expected_fields:
        assert ef in fields, f"Params missing field: {ef}"


def test_rc01_retirement_years_loop_starts_at_one(calculate_func_node):
    """RC-01 驗證：退休提領迴圈從 i=1 起算，退休當年（第 65 歲）不扣除生活費。"""
    found_loop = False
    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.For):
            # 檢查迴圈調用 range(1, retirement_years + 1)
            iter_call = node.iter
            if isinstance(iter_call, ast.Call) and getattr(iter_call.func, "id", None) == "range":
                args = iter_call.args
                if len(args) >= 2 and isinstance(args[0], ast.Constant) and args[0].value == 1:
                    found_loop = True
                    break
    assert found_loop, "RC-01: Expected for-loop over range(1, retirement_years + 1) starting at 1"


def test_rc02_discount_and_deduction_timing_asymmetry(calculate_func_node):
    """RC-02 驗證：目標金額採期末折現（/(1+r)**i），提領軌跡採期初扣款（(rem - exp)*(1+r)）。"""
    has_target_discount_division = False
    has_balance_post_multiplication = False

    for node in ast.walk(calculate_func_node):
        # 檢查 target_for_expenses += ... / (1 + p.post_retirement_return) ** i
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Div):
                has_target_discount_division = True

        # 檢查 remaining = (remaining - ...) * (1 + p.post_retirement_return)
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mult):
                if isinstance(node.value.left, ast.BinOp) and isinstance(node.value.left.op, ast.Sub):
                    has_balance_post_multiplication = True

    assert has_target_discount_division, "RC-02: Target fund must use ordinary annuity discounting (division)"
    assert has_balance_post_multiplication, "RC-02: Balances trajectory must use annuity due deduction (multiplication after subtraction)"


def test_rc03_nominal_monthly_rate_division(calculate_func_node):
    """RC-03 驗證：月利率採名目年化除以 12 (monthly_rate = pre_retirement_return / 12)。"""
    found_div_12 = False
    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "monthly_rate":
                    if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Div):
                        if isinstance(node.value.right, ast.Constant) and node.value.right.value == 12:
                            found_div_12 = True
    assert found_div_12, "RC-03: Expected monthly_rate = p.pre_retirement_return / 12"


def test_rc04_compounding_frequency_discrepancy(calculate_func_node):
    """RC-04 驗證：累積期已準備金採年複利 (** working_years)，每月儲蓄採月複利 (** (working_years * 12))。"""
    has_annual_fv = False
    has_monthly_fv = False

    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    if t.id == "fv_current":
                        # current_savings * (1 + r) ** working_years
                        if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Mult):
                            has_annual_fv = True
                    if t.id == "fv_monthly" or t.id == "fv_monthly_investments":
                        has_monthly_fv = True

    # 亦驗證 AST 中存在 working_years * 12 之乘法運算
    found_12_mult = any(
        isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult) and isinstance(n.right, ast.Constant) and n.right.value == 12
        for n in ast.walk(calculate_func_node)
    )
    assert has_annual_fv, "RC-04: fv_current should compound annually"
    assert found_12_mult, "RC-04: fv_monthly must use 12-month compounding exponent"


def test_rc05_net_expense_clamped_to_zero(calculate_func_node):
    """RC-05 驗證：淨生活費採 max(0.0, inflated - income)，超額收入被截斷不滾入資產。"""
    max_zero_count = 0
    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "max":
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0.0:
                max_zero_count += 1
    assert max_zero_count >= 2, f"RC-05: Expected at least 2 occurrences of max(0.0, ...), found {max_zero_count}"


def test_rc06_large_expense_lacks_upper_bound(calculate_func_node):
    """RC-06 驗證：大筆支出折現僅檢查 age >= retirement_age，完全缺失壽命上界判斷。"""
    has_lower_bound = False
    has_upper_bound = False

    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.If):
            test_node = node.test
            if isinstance(test_node, ast.Compare):
                # 檢查比較運算子
                for op in test_node.ops:
                    if isinstance(op, ast.GtE):
                        has_lower_bound = True
                    if isinstance(op, (ast.Lt, ast.LtE)):
                        has_upper_bound = True

    assert has_lower_bound, "RC-06: Expected ls.age >= p.retirement_age guard"
    assert not has_upper_bound, "RC-06: Unexpected upper bound check found; defect C requires lack of upper bound!"


def test_rc07_income_inflation_indexing(calc_ast):
    """RC-07 驗證：_inflated_income 函數將收入全額隨通膨指數化 (1+inflation_rate)**years_from_now。"""
    inflated_func = None
    for node in calc_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_inflated_income":
            inflated_func = node
            break
    assert inflated_func is not None, "RC-07: _inflated_income function must exist"

    has_infl_pow = False
    for n in ast.walk(inflated_func):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
            has_infl_pow = True
    assert has_infl_pow, "RC-07: Income should be compounded by inflation rate exponent"


def test_rc08_annual_recurring_expense_merged_today(calculate_func_node):
    """RC-08 驗證：每年固定支出與每月支出於今日幣值合併 (monthly_expense * 12 + annual_recurring)。"""
    found_merge = False
    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "total_annual_expense_today":
                    if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add):
                        found_merge = True
    assert found_merge, "RC-08: Expected total_annual_expense_today assignment merging monthly and recurring expenses"


def test_rc09_dual_rate_regime_switch(calculate_func_node):
    """RC-09 驗證：累積期使用 pre_retirement_return，退休提領期使用 post_retirement_return。"""
    found_pre = False
    found_post = False

    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.Attribute):
            if node.attr == "pre_retirement_return":
                found_pre = True
            elif node.attr == "post_retirement_return":
                found_post = True

    assert found_pre and found_post, "RC-09: Must use distinct pre- and post-retirement return attributes"


def test_rc10_unhandled_input_exceptions_in_core(calculate_func_node):
    """RC-10 驗證：計算核心完全未實作輸入校驗異常拋出 (無 raise ValueError / assert)，證實為 Tier 1 缺席規則。"""
    has_raise = False
    has_assert = False

    for node in ast.walk(calculate_func_node):
        if isinstance(node, ast.Raise):
            has_raise = True
        if isinstance(node, ast.Assert):
            has_assert = True

    assert not has_raise, "RC-10: Calculation engine should not raise exceptions (leaves validation to Tier 1)"
    assert not has_assert, "RC-10: Calculation engine should not use assertions for input validation"

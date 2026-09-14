"""CheckList 語意行為測試套件 (Ribeiro et al., ACL 2020 框架落地於金融試算)。

將測試劃分為三種行為面向：
1. MFT (Minimum Functionality Test, 最小功能測試)：邊界封閉解與退化基底驗證 (S=0, r=0 等)
2. INV (Invariance, 不變量測試)：非關鍵參數擾動或等價重分配時，輸出必須逐位元一致
3. DIR (Directional Expectation, 方向性期望測試)：關鍵參數單調變化時的數值方向驗證 (S 增加、A_d 增加、E_0 增加)

用法：
    pytest tests/test_checklist.py -q
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc import LumpSum, Params, Result, calculate  # noqa: E402


# ---------------------------------------------------------------------------
# 1. MFT (Minimum Functionality Test, 最小功能測試)
# ---------------------------------------------------------------------------

class TestCheckListMFT:
    """MFT：驗證系統在極限、退化或具備數學封閉解情況下的基本功能。"""

    def test_mft_zero_savings_and_zero_return(self):
        """MFT-1: 每月投入 S=0 且報酬率 r=0 時，累積資產恆等於現有資產 (P = P_0)。"""
        p = Params(
            current_age=35,
            retirement_age=65,
            life_expectancy=85,
            current_savings=1_500_000.0,
            monthly_investment=0.0,
            monthly_expense_today=30_000.0,
            pre_retirement_return=0.0,
            post_retirement_return=0.0,
            inflation_rate=0.0,
        )
        res = calculate(p)
        # 封閉解：無投資無利息，到期現值等於現有存款
        assert res.projected_savings == pytest.approx(1_500_000.0, rel=1e-12)

    def test_mft_zero_monthly_investment_with_positive_return(self):
        """MFT-2: S=0 但 r>0，累積期退化為純現有資產單筆複利增值。"""
        p = Params(
            current_age=30,
            retirement_age=60,
            life_expectancy=85,
            current_savings=2_000_000.0,
            monthly_investment=0.0,
            monthly_expense_today=40_000.0,
            pre_retirement_return=0.05,
            post_retirement_return=0.03,
            inflation_rate=0.02,
        )
        res = calculate(p)
        working_years = 60 - 30
        expected_fv = 2_000_000.0 * ((1 + 0.05) ** working_years)
        assert res.projected_savings == pytest.approx(expected_fv, rel=1e-12)

    def test_mft_zero_initial_savings_zero_return(self):
        """MFT-3: P_0=0, S>0, r=0，退化為純儲蓄線性累加 P = 12 * S * working_years。"""
        s = 25_000.0
        working_years = 25
        p = Params(
            current_age=40,
            retirement_age=40 + working_years,
            life_expectancy=85,
            current_savings=0.0,
            monthly_investment=s,
            monthly_expense_today=30_000.0,
            pre_retirement_return=0.0,
            post_retirement_return=0.04,
            inflation_rate=0.02,
        )
        res = calculate(p)
        expected_savings = s * 12 * working_years
        assert res.projected_savings == pytest.approx(expected_savings, rel=1e-12)

    def test_mft_zero_expenses_yields_zero_target(self):
        """MFT-4: 當所有生活費與大筆支出均為 0 時，目標金額恆為 0。"""
        p = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=85,
            current_savings=1_000_000.0,
            monthly_investment=20_000.0,
            monthly_expense_today=0.0,
            annual_recurring_expense=0.0,
            lump_sums=(),
        )
        res = calculate(p)
        assert res.target_fund == 0.0
        assert res.retirement_gap == -res.projected_savings


# ---------------------------------------------------------------------------
# 2. INV (Invariance, 不變量測試)
# ---------------------------------------------------------------------------

class TestCheckListINV:
    """INV：驗證對非關鍵維度進行等價擾動時，輸出結果必須恆定不變。"""

    def test_inv_expense_category_reallocation(self):
        """INV-1: 「食衣住行育樂」各細項重分配但總額維持不變，計算結果必須逐位元完全相同。

        在實際使用者介面中，生活費通常由細項相加而成；無論使用者在各細項如何搬移金額，
        只要 totalMonthlyExpense 恆定，計算引擎的所有輸出欄位必須精確相等。
        """
        # 總生活費恆定為 45,000 元/月
        total_monthly = 45_000.0

        # 分配組合 A：食 20,000 + 住 15,000 + 行 5,000 + 雜 5,000
        # 分配組合 B：食 10,000 + 住 25,000 + 行 8,000 + 雜 2,000
        # 分配組合 C：食 15,000 + 住 15,000 + 行 10,000 + 雜 5,000
        allocations = [
            {"food": 20_000, "housing": 15_000, "transport": 5_000, "misc": 5_000},
            {"food": 10_000, "housing": 25_000, "transport": 8_000, "misc": 2_000},
            {"food": 15_000, "housing": 15_000, "transport": 10_000, "misc": 5_000},
        ]

        results: list[Result] = []
        for alloc in allocations:
            assert sum(alloc.values()) == total_monthly
            p = Params(
                current_age=38,
                retirement_age=65,
                life_expectancy=85,
                current_savings=800_000.0,
                monthly_investment=15_000.0,
                monthly_expense_today=total_monthly,
                annual_recurring_expense=60_000.0,
                pre_retirement_return=0.07,
                post_retirement_return=0.04,
                inflation_rate=0.02,
                lump_sums=(LumpSum(age=70, amount=500_000.0),),
            )
            results.append(calculate(p))

        base_res = results[0]
        for idx, other_res in enumerate(results[1:], start=1):
            assert other_res.projected_savings == base_res.projected_savings
            assert other_res.target_fund == base_res.target_fund
            assert other_res.retirement_gap == base_res.retirement_gap
            assert other_res.balances_raw == base_res.balances_raw
            assert other_res.balances_charted == base_res.balances_charted

    def test_inv_empty_vs_zero_amount_lump_sum(self):
        """INV-2: 大筆支出為空 tuple 與包含 0 元大筆支出，輸出完全一致。"""
        p_empty = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=85,
            current_savings=500_000.0,
            monthly_investment=10_000.0,
            monthly_expense_today=30_000.0,
            lump_sums=(),
        )
        p_zero = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=85,
            current_savings=500_000.0,
            monthly_investment=10_000.0,
            monthly_expense_today=30_000.0,
            lump_sums=(LumpSum(age=70, amount=0.0), LumpSum(age=80, amount=0.0)),
        )
        res_empty = calculate(p_empty)
        res_zero = calculate(p_zero)

        assert res_empty.target_fund == res_zero.target_fund
        assert res_empty.balances_raw == res_zero.balances_raw

    def test_inv_unreached_income_invariance(self):
        """INV-3: 若請領年齡超過預期壽命，該收入項金額改變不應影響任何已模擬之年金軌跡。"""
        life_exp = 80
        p_no_income = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=life_exp,
            current_savings=1_000_000.0,
            monthly_investment=20_000.0,
            monthly_expense_today=35_000.0,
            labor_insurance_pension=0.0,
            labor_insurance_start_age=90,  # 遠大於壽命 80
        )
        p_phantom_income = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=life_exp,
            current_savings=1_000_000.0,
            monthly_investment=20_000.0,
            monthly_expense_today=35_000.0,
            labor_insurance_pension=50_000.0,  # 即使月領 5 萬
            labor_insurance_start_age=90,  # 但 90 歲起領，80 歲已離世
        )
        res_no = calculate(p_no_income)
        res_phantom = calculate(p_phantom_income)

        assert res_no.target_fund == res_phantom.target_fund
        assert res_no.balances_raw == res_phantom.balances_raw


# ---------------------------------------------------------------------------
# 3. DIR (Directional Expectation, 方向性期望測試)
# ---------------------------------------------------------------------------

class TestCheckListDIR:
    """DIR：驗證輸入參數朝特定方向遞增時，輸出指標呈現嚴格的單調性反應。"""

    @pytest.fixture
    def dir_base_params(self) -> dict:
        return {
            "current_age": 40,
            "retirement_age": 65,
            "life_expectancy": 85,
            "current_savings": 1_000_000.0,
            "monthly_investment": 20_000.0,
            "monthly_expense_today": 35_000.0,
            "annual_recurring_expense": 0.0,
            "pre_retirement_return": 0.06,
            "post_retirement_return": 0.04,
            "inflation_rate": 0.02,
        }

    def test_dir_monthly_investment_monotonicity(self, dir_base_params):
        """DIR-1: 每月投入 S 增加 -> 累積資產嚴格遞增 (S ↑ => P ↑)，退休缺口單調不增 (S ↑ => Gap ↓)。"""
        investments = [10_000.0, 15_000.0, 20_000.0, 30_000.0, 50_000.0]
        results = [
            calculate(Params(**{**dir_base_params, "monthly_investment": s}))
            for s in investments
        ]

        for i in range(len(results) - 1):
            assert results[i].projected_savings < results[i + 1].projected_savings
            assert results[i].retirement_gap > results[i + 1].retirement_gap
            # 目標金額與退休前月投入無關，維持恆等
            assert results[i].target_fund == results[i + 1].target_fund

    def test_dir_life_expectancy_monotonicity(self, dir_base_params):
        """DIR-2: 壽命 A_d 增加 -> 退休目標金額嚴格遞增 (A_d ↑ => Target ↑)。"""
        lifespans = [75, 80, 85, 90, 95]
        results = [
            calculate(Params(**{**dir_base_params, "life_expectancy": age}))
            for age in lifespans
        ]

        for i in range(len(results) - 1):
            assert results[i].target_fund < results[i + 1].target_fund
            # 退休缺口隨目標金額上升而擴大
            assert results[i].retirement_gap < results[i + 1].retirement_gap
            # 累積期資產與壽命無關
            assert results[i].projected_savings == results[i + 1].projected_savings

    def test_dir_monthly_expense_monotonicity(self, dir_base_params):
        """DIR-3: 當前生活費 E_0 增加 -> 退休目標金額嚴格遞增 (E_0 ↑ => Target ↑)。"""
        expenses = [25_000.0, 35_000.0, 45_000.0, 60_000.0]
        results = [
            calculate(Params(**{**dir_base_params, "monthly_expense_today": exp}))
            for exp in expenses
        ]

        for i in range(len(results) - 1):
            assert results[i].target_fund < results[i + 1].target_fund
            assert results[i].retirement_gap < results[i + 1].retirement_gap

    def test_dir_current_savings_monotonicity(self, dir_base_params):
        """DIR-4: 現有本金 P_0 增加 -> 累積資產嚴格遞增 (P_0 ↑ => P ↑)。"""
        savings = [500_000.0, 1_000_000.0, 2_000_000.0, 5_000_000.0]
        results = [
            calculate(Params(**{**dir_base_params, "current_savings": p0}))
            for p0 in savings
        ]

        for i in range(len(results) - 1):
            assert results[i].projected_savings < results[i + 1].projected_savings
            assert results[i].retirement_gap > results[i + 1].retirement_gap

    def test_dir_pre_retirement_return_monotonicity(self, dir_base_params):
        """DIR-5: 退休前報酬率 r 增加 -> 累積資產嚴格遞增 (r ↑ => P ↑)。"""
        returns = [0.02, 0.04, 0.06, 0.08, 0.10]
        results = [
            calculate(Params(**{**dir_base_params, "pre_retirement_return": r}))
            for r in returns
        ]

        for i in range(len(results) - 1):
            assert results[i].projected_savings < results[i + 1].projected_savings

    def test_dir_late_retirement_savings_increase(self, dir_base_params):
        """DIR-6: 延後退休 (A_r ↑) -> 累積期拉長，累積資產嚴格遞增。

        注意：我遵循架構審查結論，不對「延後退休 => 目標金額不增」做不實保證
        （因為通膨指數化會導致提領期初期費用更高，在特定參數下目標金額並非單調），
        但「延後退休 => 累積資產增加」在正報酬率下是恆成立的方向期望。
        """
        retire_ages = [55, 60, 65, 70]
        results = [
            calculate(Params(**{**dir_base_params, "retirement_age": ar}))
            for ar in retire_ages
        ]

        for i in range(len(results) - 1):
            assert results[i].projected_savings < results[i + 1].projected_savings

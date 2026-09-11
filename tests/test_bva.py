"""邊界值分析 (BVA) 測試套件：驗收檢核器，並用它測受測物的邊界。

檢核器本體不在這裡——它在 `tools/bva_checker.py`，本檔直接 import。
2026-09-10 之前這裡有一份自己的 `check_bva` 副本，兩份已經分歧
（本地版 tolerance=1e-5、工具版 1e-9），故移除本地副本。
兩份同樣的函式而沒有東西盯著它們是否一致，正是本系列在批判的事。

包含：
1. 檢核器的已知答案測試 (KAT) 自我驗收
2. shadow/calc.py 的 5 點邊界值深度測試
   (A_c vs A_r, A_r vs A_d, A_e vs A_d, r=0, expense=0, clamp 等)

用法：
    pytest tests/test_bva.py -q
"""

import math
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))
sys.path.insert(0, str(ROOT / "tools"))

from calc import LumpSum, Params, Result, calculate  # noqa: E402
from bva_checker import Case, Constraint, check_bva  # noqa: E402

# ---------------------------------------------------------------------------
# 2. 誰來驗收驗收者？KAT (Known-Answer Test) 自我驗證
# ---------------------------------------------------------------------------

class TestBVACheckerSelfVerification:
    """人手構造、預期結果確鑿無疑的已知答案測試集。"""

    def test_kat_checker_passes_on_perfect_boundary(self):
        """完美三點覆蓋：A_e = 84, 85, 86 (相對於 A_d = 85)。"""
        cases = [
            {"A_e": 84, "A_d": 85},  # off-below (-1)
            {"A_e": 85, "A_d": 85},  # on-point (0)
            {"A_e": 86, "A_d": 85},  # off-above (+1)
        ]
        result = check_bva(("A_e", "<=", "A_d"), cases)
        assert result["pass"] is True
        assert result["score"] == 1.0
        assert len(result["missing"]) == 0
        assert result["hit"]["on-point"] is True

    def test_kat_checker_fails_on_missing_on_point(self):
        """故意缺漏邊界點：給 75 與 95 (A_d = 85)，漏掉 84, 85, 86。"""
        cases = [
            {"A_e": 75, "A_d": 85},  # delta = -10
            {"A_e": 95, "A_d": 85},  # delta = +10
        ]
        result = check_bva(("A_e", "<=", "A_d"), cases)
        assert result["pass"] is False
        assert result["score"] == 0.0
        assert "on-point" in result["missing"]
        assert "off-below" in result["missing"]
        assert "off-above" in result["missing"]

    def test_kat_checker_partial_coverage(self):
        """只命中 on-point 與 off-below，缺少 off-above。"""
        cases = [
            {"A_e": 84, "A_d": 85},
            {"A_e": 85, "A_d": 85},
        ]
        result = check_bva(("A_e", "<=", "A_d"), cases)
        assert result["pass"] is False
        assert pytest.approx(result["score"], rel=1e-4) == 2 / 3
        assert result["missing"] == ["off-above"]

    def test_kat_checker_constant_boundary(self):
        """常數邊界檢核：利率 r >= 0.0，步長 0.01。"""
        cases = [
            {"r": -0.01},
            {"r": 0.0},
            {"r": 0.01},
        ]
        result = check_bva(("r", ">=", 0.0), cases, step=0.01)
        assert result["pass"] is True
        assert result["score"] == 1.0

    def test_kat_checker_five_point_mode(self):
        """5 點邊界分析模式驗證 (-2, -1, 0, +1, +2)。"""
        cases = [
            {"A_c": 63, "A_r": 65},  # -2
            {"A_c": 64, "A_r": 65},  # -1
            {"A_c": 65, "A_r": 65},  # 0
            {"A_c": 66, "A_r": 65},  # +1
            {"A_c": 67, "A_r": 65},  # +2
        ]
        result = check_bva(("A_c", "<", "A_r"), cases, step=1.0, mode="5-point")
        assert result["pass"] is True
        assert result["score"] == 1.0
        assert len(result["missing"]) == 0


# ---------------------------------------------------------------------------
# 3. 受測物 shadow/calc.py 的 5 點邊界值深度測試
# ---------------------------------------------------------------------------

class TestShadowModelBVA:
    """針對 shadow/calc.py 各關鍵數值與關係邊界的 5 點分析與行為驗證。"""

    @pytest.fixture
    def base_params_dict(self) -> dict[str, Any]:
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

    def test_bva_working_years_five_points(self, base_params_dict):
        """檢核現齡 A_c 與退休年齡 A_r 的 5 點邊界：A_c - A_r in {-2, -1, 0, 1, 2}。"""
        r_age = 65
        five_ages = [r_age - 2, r_age - 1, r_age, r_age + 1, r_age + 2]  # 63, 64, 65, 66, 67
        cases = [{"current_age": age, "retirement_age": r_age} for age in five_ages]

        # 檢核器確認測試案例具備 5 點
        bva_report = check_bva(("current_age", "<", "retirement_age"), cases, step=1.0, mode="5-point")
        assert bva_report["pass"] is True

        # 逐點驗證 shadow/calc.py 行為
        # 1. A_c = 64 (working_years = 1)
        p1 = Params(**{**base_params_dict, "current_age": 64, "retirement_age": 65})
        res1 = calculate(p1)
        assert res1.projected_savings > p1.current_savings

        # 2. A_c = 65 (working_years = 0, on-point)
        p0 = Params(**{**base_params_dict, "current_age": 65, "retirement_age": 65})
        res0 = calculate(p0)
        # working_years=0 時，複利指數為 0，本金不變，且月儲蓄期數為 0
        assert res0.projected_savings == pytest.approx(p0.current_savings, rel=1e-9)

        # 3. A_c = 66 (working_years = -1, off-1-above, 倒退年齡)
        p_neg = Params(**{**base_params_dict, "current_age": 66, "retirement_age": 65})
        res_neg = calculate(p_neg)
        # 負年數造成折現/複利倒轉，暴露未防呆邊界
        assert res_neg.projected_savings < p_neg.current_savings

    def test_bva_retirement_years_five_points_and_defect_b(self, base_params_dict):
        """檢核預期壽命 A_d 與退休年齡 A_r 的 5 點邊界：A_d - A_r in {-2, -1, 0, 1, 2}。"""
        r_age = 65
        five_lifes = [r_age - 2, r_age - 1, r_age, r_age + 1, r_age + 2]  # 63, 64, 65, 66, 67
        cases = [{"life_expectancy": life, "retirement_age": r_age} for life in five_lifes]

        bva_report = check_bva(("life_expectancy", ">", "retirement_age"), cases, step=1.0, mode="5-point")
        assert bva_report["pass"] is True

        # 行為驗證：
        # 當 A_d <= A_r 時 (retirement_years <= 0)，range(1, retirement_years + 1) 不執行
        for life in [63, 64, 65]:
            p = Params(**{**base_params_dict, "retirement_age": 65, "life_expectancy": life})
            res = calculate(p)
            assert res.target_fund == 0.0
            assert len(res.balances_raw) == 0
            # 這是 Defect B 的本質：負或零退休年數導致 target_fund = 0，缺口為負，畫面上誤判為「準備充足」
            assert res.retirement_gap <= 0

        # 當 A_d = 66 (retirement_years = 1)
        p_pos1 = Params(**{**base_params_dict, "retirement_age": 65, "life_expectancy": 66})
        res_pos1 = calculate(p_pos1)
        assert res_pos1.target_fund > 0.0
        assert len(res_pos1.balances_raw) == 1

        # 當 A_d = 67 (retirement_years = 2)
        p_pos2 = Params(**{**base_params_dict, "retirement_age": 65, "life_expectancy": 67})
        res_pos2 = calculate(p_pos2)
        assert res_pos2.target_fund > res_pos1.target_fund
        assert len(res_pos2.balances_raw) == 2

    def test_bva_lump_sum_age_vs_life_expectancy_defect_c(self, base_params_dict):
        """檢核大筆支出年齡 A_e 與壽命 A_d 的 5 點邊界：A_e - A_d in {-2, -1, 0, 1, 2}。"""
        d_age = 85
        five_ae = [d_age - 2, d_age - 1, d_age, d_age + 1, d_age + 2]  # 83, 84, 85, 86, 87
        cases = [{"A_e": ae, "A_d": d_age} for ae in five_ae]

        bva_report = check_bva(("A_e", "<=", "A_d"), cases, step=1.0, mode="5-point")
        assert bva_report["pass"] is True

        # 觀察 shadow/calc.py 在 A_e = 85 (on-point) vs A_e = 86 (off-1-above) 的行為
        # A_e = 85 (壽命當年)：目標金額計入，且第 85 歲之提領軌跡 balances_raw 有扣除該大筆支出
        p_on = Params(
            **{**base_params_dict, "life_expectancy": 85},
            lump_sums=(LumpSum(age=85, amount=1_000_000.0),),
        )
        res_on = calculate(p_on)

        p_none = Params(**{**base_params_dict, "life_expectancy": 85}, lump_sums=())
        res_none = calculate(p_none)

        assert res_on.target_fund > res_none.target_fund
        # 第 85 歲 balances_raw 必然因扣款而低於無大筆支出組
        assert res_on.balances_raw[-1] < res_none.balances_raw[-1]

        # A_e = 86 (超壽命大筆支出，Defect C 現場)：
        p_over = Params(
            **{**base_params_dict, "life_expectancy": 85},
            lump_sums=(LumpSum(age=86, amount=1_000_000.0),),
        )
        res_over = calculate(p_over)
        # 329 行只有 if ls.age >= p.retirement_age，無上界檢查 -> target_fund 仍然被增加！
        assert res_over.target_fund > res_none.target_fund
        # 但 349 行迴圈只走到 85 歲，367 行 if ls.age == age 永遠不配對 -> balances_raw 完全相同！
        assert res_over.balances_raw == res_none.balances_raw

    def test_bva_zero_return_rate_boundary(self, base_params_dict):
        """檢核報酬率 r = 0.0 的退化邊界 (線性累加分支)。"""
        # pre_retirement_return = 0.0 應走 75 行線性分支：fv_monthly = S * working_years * 12
        p_zero = Params(**{**base_params_dict, "pre_retirement_return": 0.0})
        res_zero = calculate(p_zero)

        expected_savings = (
            p_zero.current_savings
            + p_zero.monthly_investment * (p_zero.retirement_age - p_zero.current_age) * 12
        )
        assert res_zero.projected_savings == pytest.approx(expected_savings, rel=1e-9)

    def test_bva_zero_expense_boundary(self, base_params_dict):
        """檢核每月支出 E_0 = 0.0 的邊界。"""
        p_zero_exp = Params(
            **{**base_params_dict, "monthly_expense_today": 0.0, "annual_recurring_expense": 0.0},
            lump_sums=(),
        )
        res = calculate(p_zero_exp)
        assert res.target_fund == 0.0
        assert res.retirement_gap == -res.projected_savings

    def test_bva_deficit_clamp_boundary_defect_a_prime(self, base_params_dict):
        """檢核餘額轉負邊界處，balances_raw 與 balances_charted 的分流 (Defect A' 遮羞布)。"""
        # 設定零儲蓄、高支出，確保 85 歲帳戶透支
        p_deficit = Params(
            **{
                **base_params_dict,
                "current_savings": 0.0,
                "monthly_investment": 0.0,
                "monthly_expense_today": 50_000.0,
            }
        )
        res = calculate(p_deficit)
        # 真實餘額必須為負數 (赤字)
        assert res.balances_raw[-1] < 0.0
        # 圖表餘額被 374 行 Math.max(0, ...) 夾成 0.0
        assert res.balances_charted[-1] == 0.0

        # 反向對照：當資產充裕時，兩者必須完全相等
        p_surplus = Params(
            **{
                **base_params_dict,
                "current_savings": 50_000_000.0,
                "monthly_investment": 100_000.0,
                "monthly_expense_today": 20_000.0,
            }
        )
        res_surplus = calculate(p_surplus)
        assert res_surplus.balances_raw[-1] > 0.0
        assert res_surplus.balances_raw[-1] == pytest.approx(res_surplus.balances_charted[-1], rel=1e-9)

    def test_bva_net_expense_zero_clamp_boundary(self, base_params_dict):
        """檢核 320 行與 363 行 max(0.0, inflated - income) 的盈餘夾 0 邊界。"""
        # 收入遠大於支出：退休後每月有 20 萬其他收入，生活費僅 3 萬
        p_rich = Params(
            **{
                **base_params_dict,
                "monthly_expense_today": 30_000.0,
                "other_income": 200_000.0,
            },
            lump_sums=(),
        )
        res = calculate(p_rich)
        # 淨支出為 0，因此 target_for_expenses 應退化為 0.0
        assert res.target_fund == 0.0

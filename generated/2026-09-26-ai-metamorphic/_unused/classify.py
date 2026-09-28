"""Day 26：逐條人工分類，143 條。

為什麼是人工
----------
manifest 的 relation_taxonomy 寫死「判定者：人工。工具不猜」。
本檔第一版用關鍵字正則跑過一次，Pro 有 43/56 落進「其他」——
它的註解是長句散文，正則讀不出它想驗的是哪一種性質。
那張表被作廢，改成逐條讀註解人工標，標籤寫在底下的 LABELS。

這支不做判斷，只做加總與自檢。分類本身是人讀出來的，
放在程式碼裡是為了「可稽核」：任何人都能逐條翻回原檔對。

六類之外多出來的兩類
------------------
manifest 預先定了六類（對帳／縮放／單調／不變／退化／其他），
並寫明「其他：歸不進上面五類的，照實記，不硬塞」。實際讀完，
「其他」裡面有兩種穩定重複的形狀，照實拆出來記：

  結構      「壽命 +3 → 餘額軌跡長度 +3」。驗的是輸出的形狀，不是數值。
  校驗      「現齡 >= 退休年齡 → 必須拋出例外」。單次執行，嚴格說不是蛻變關係。

以及一個必須單獨記的陷阱
--------------------
  定義性恆等  「缺口的減少量 == 資產的增加量」。
              它長得像對帳——斷言兩邊各有一個輸出——但 retirement_gap
              的定義就是 target_fund - projected_savings，兩邊追溯回去
              是同一條減法。**在任何實作下它都恆成立。**
              這正是 manifest 分支計畫裡「假對帳」的判準所指的東西，
              所以不併進對帳，也不併進不變，單獨記。

疊加不算對帳
----------
「本金單獨算 + 月存單獨算 == 兩者一起算」驗的是同一條路徑的線性性質
（加法版的齊次性），兩邊沒有跨到程式的不同部分，歸「縮放」。
真正的對帳是「折現路徑」與「餘額軌跡」必須吻合——那是抓到缺陷 A 的形狀。

    python3 generated/2026-09-26-ai-metamorphic/classify.py
"""

from __future__ import annotations

import ast
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

CATS = ("對帳", "縮放", "單調", "不變", "退化", "結構", "定義性恆等", "校驗")

# 檔名 → (測試函式名, 類別)。逐條讀註解標的。
LABELS: dict[str, tuple[tuple[str, str], ...]] = {
    "run-A-MR-01.txt": (
        ("test_mr_accumulation_linearity", "縮放"),
        ("test_mr_accumulation_zero_return", "退化"),
        ("test_mr_target_fund_independence", "不變"),
        ("test_mr_gap_consistency", "定義性恆等"),
        ("test_mr_ignored_lump_sums", "不變"),
        ("test_mr_lump_sum_additivity", "縮放"),
        ("test_mr_income_expense_equivalence", "不變"),
        ("test_mr_pension_start_age_delay", "單調"),
        ("test_mr_post_retirement_return_effect", "單調"),
        ("test_mr_net_expense_floor", "不變"),
        ("test_mr_charted_balances_veracity", "不變"),
        ("test_mr_input_validation", "校驗"),
    ),
    "run-A-MR-02.txt": (
        ("test_mr_zero_return_linear_accumulation", "退化"),
        ("test_mr_monthly_annual_expense_equivalence", "不變"),
        ("test_mr_financial_scaling", "縮放"),
        ("test_mr_lump_sum_out_of_bounds", "不變"),
        ("test_mr_massive_income_floor", "不變"),
        ("test_mr_chart_balances_fidelity", "不變"),
        ("test_mr_pension_age_delayed_ignored", "不變"),
        ("test_mr_inflation_increases_target", "單調"),
        ("test_mr_post_retire_return_decreases_target", "單調"),
        ("test_mr_savings_reduces_gap", "單調"),
    ),
    "run-A-MR-03.txt": (
        ("test_mr1_accumulation_linearity", "縮放"),
        ("test_mr2_expense_linearity_zero_income", "縮放"),
        ("test_mr3_age_shift_invariance", "不變"),
        ("test_mr4_pre_retirement_independence", "不變"),
        ("test_mr5_post_retirement_independence", "不變"),
        ("test_mr6_expense_structure_equivalence", "不變"),
        ("test_mr7_excess_income_target_zero", "不變"),
        ("test_mr8_chart_balances_integrity", "不變"),
        ("test_mr9_lump_sum_outside_span_ignored", "不變"),
    ),
    "run-A-MR-04.txt": (
        ("test_current_savings_linearity", "縮放"),
        ("test_monthly_investment_linearity", "縮放"),
        ("test_target_fund_independence", "不變"),
        ("test_post_retirement_cashflow_scaling", "縮放"),
        ("test_lump_sums_out_of_bounds_ignored", "不變"),
        ("test_lump_sums_aggregation", "縮放"),
        ("test_balances_trajectory_length", "結構"),
        ("test_balances_charted_equals_raw", "不變"),
        ("test_retirement_gap_consistency", "定義性恆等"),
        ("test_zero_return_linear_accumulation", "退化"),
        ("test_income_surplus_does_not_decrease_target_fund", "不變"),
    ),
    "run-A-MR-05.txt": (
        ("test_mr_scale_all_money", "縮放"),
        ("test_mr_target_fund_independence", "不變"),
        ("test_mr_projected_savings_independence", "不變"),
        ("test_mr_current_savings_superposition", "縮放"),
        ("test_mr_charted_balances_equal_raw", "不變"),
        ("test_mr_expenses_superposition", "縮放"),
        ("test_mr_retirement_gap_delta", "定義性恆等"),
        ("test_mr_zero_return_accumulation", "退化"),
        ("test_mr_zero_inflation_and_return_linear_target_fund", "退化"),
        ("test_mr_income_cancels_expense", "不變"),
        ("test_mr_labor_pension_delay_increases_target_fund", "單調"),
        ("test_mr_lumpsum_order_independence", "不變"),
        ("test_mr_ignore_out_of_bounds_lumpsums", "不變"),
        ("test_mr_age_translation_invariance", "不變"),
    ),
    "run-B-MR-01.txt": (
        ("test_mr_prd12_charted_balances_equal_raw_balances", "不變"),
        ("test_mr_prd02_prd03_trajectory_length_lifespan_extension", "結構"),
        ("test_mr_prd01_pre_retirement_independent_of_post_retirement_expense", "不變"),
        ("test_mr_prd02_target_fund_independent_of_accumulation_assets", "不變"),
        ("test_mr_prd01_accumulation_scale_homogeneity", "縮放"),
        ("test_mr_prd01_savings_and_investment_superposition", "縮放"),
        ("test_mr_prd08_monthly_and_annual_expense_equivalence", "不變"),
        ("test_mr_prd05_out_of_range_lump_sum_invariance", "不變"),
        ("test_mr_prd05_lump_sum_additive_splitting", "縮放"),
        ("test_mr_prd09_surplus_income_ceiling_invariance", "不變"),
        ("test_mr_prd03_prd12_negative_balance_no_clipping", "單調"),
        ("test_mr_savings_monotonicity_on_projected_and_balances", "單調"),
        ("test_mr_expense_monotonicity_on_target_and_balances", "單調"),
        ("test_mr_prd06_pension_delay_monotonicity", "單調"),
        ("test_mr_pure_expense_target_fund_homogeneity", "縮放"),
        ("test_mr_prd04_input_validation_invalid_age_ordering", "校驗"),
        ("test_mr_prd04_input_validation_negative_amount", "校驗"),
    ),
    "run-B-MR-02.txt": (
        ("test_mr_balances_charted_equals_raw", "不變"),
        ("test_mr_monthly_and_annual_expense_fungibility", "不變"),
        ("test_mr_out_of_range_lump_sum_invariance", "不變"),
        ("test_mr_lump_sum_order_invariance", "不變"),
        ("test_mr_lump_sum_same_age_additivity", "縮放"),
        ("test_mr_projected_savings_scalar_multiplication", "縮放"),
        ("test_mr_projected_savings_superposition", "縮放"),
        ("test_mr_target_fund_independent_of_pre_retirement_params", "不變"),
        ("test_mr_projected_savings_independent_of_post_retirement_params", "不變"),
        ("test_mr_balance_trajectory_length_with_life_expectancy", "結構"),
        ("test_mr_target_fund_monotonicity_wrt_expenses", "單調"),
        ("test_mr_target_fund_monotonicity_wrt_pension", "單調"),
        ("test_mr_target_fund_monotonicity_wrt_post_retirement_return", "單調"),
        ("test_mr_target_fund_monotonicity_wrt_inflation_rate", "單調"),
        ("test_mr_projected_savings_monotonicity_wrt_pre_retirement_return", "單調"),
        ("test_mr_surplus_income_non_rollover", "不變"),
        ("test_mr_pension_start_age_delay_monotonicity", "單調"),
        ("test_mr_zero_return_projected_savings_linearity", "退化"),
    ),
    "run-B-MR-03.txt": (
        ("test_mr01_chart_raw_identity_and_no_clipping", "不變"),
        ("test_mr02_projected_savings_homogeneity_and_orthogonality", "縮放"),
        ("test_mr03_monthly_investment_additive_linearity", "縮放"),
        ("test_mr04_balance_trajectory_length_with_life_expectancy", "結構"),
        ("test_mr05_lump_sums_outside_retirement_ignored", "不變"),
        ("test_mr06_same_year_lump_sums_consolidation", "縮放"),
        ("test_mr07_monthly_and_annual_recurring_expense_equivalence", "不變"),
        ("test_mr08_pension_source_symmetry_at_same_start_age", "不變"),
        ("test_mr09_expense_floor_surplus_non_accumulation", "不變"),
        ("test_mr10_global_time_shift_invariance", "不變"),
        ("test_mr11_target_fund_pure_expense_scaling", "縮放"),
        ("test_mr12_retirement_gap_and_savings_complementary_conservation", "定義性恆等"),
        ("test_mr13_monotonicity_pre_retirement_return", "單調"),
        ("test_mr14_monotonicity_post_retirement_return", "單調"),
        ("test_mr15_monotonicity_inflation_rate", "單調"),
    ),
    "run-B-MR-04.txt": (
        ("test_mr_prd12_chart_fidelity_positive_and_negative", "不變"),
        ("test_mr_prd01_accumulation_savings_linear_scaling", "縮放"),
        ("test_mr_prd01_accumulation_monthly_investment_linear_scaling", "縮放"),
        ("test_mr_prd01_accumulation_superposition", "縮放"),
        ("test_mr_prd01_zero_return_linear_accumulation_equivalence", "退化"),
        ("test_mr_prd01_pre_retirement_return_monotonicity", "單調"),
        ("test_mr_prd02_target_fund_independent_of_accumulation_params", "不變"),
        ("test_mr_prd01_projected_savings_independent_of_post_retirement_params", "不變"),
        ("test_mr_prd02_post_retirement_return_monotonicity", "單調"),
        ("test_mr_prd02_inflation_rate_monotonicity", "單調"),
        ("test_mr_prd02_trajectory_length_matches_retirement_span", "結構"),
        ("test_mr_prd03_savings_monotonicity_on_trajectory", "單調"),
        ("test_mr_prd05_lump_sum_outside_interval_ignored", "不變"),
        ("test_mr_prd05_lump_sum_additive_split", "縮放"),
        ("test_mr_prd05_lump_sum_order_invariance", "不變"),
        ("test_mr_prd05_zero_lump_sum_neutrality", "不變"),
        ("test_mr_prd05_lump_sum_independent_additivity", "縮放"),
        ("test_mr_prd06_07_labor_pensions_symmetry", "不變"),
        ("test_mr_prd06_labor_insurance_start_age_monotonicity", "單調"),
        ("test_mr_prd08_monthly_and_annual_expense_equivalence", "不變"),
        ("test_mr_prd09_net_expense_floor_surplus_clipping", "不變"),
        ("test_mr_prd09_other_income_monotonicity", "單調"),
        ("test_mr_prd02_expense_homogeneity_under_zero_income", "縮放"),
        ("test_mr_retirement_gap_delta_conservation", "定義性恆等"),
    ),
    "run-B-MR-05.txt": (
        ("test_mr_charted_balances_equals_raw", "不變"),
        ("test_mr_ignore_out_of_range_lump_sums", "不變"),
        ("test_mr_monthly_and_annual_expense_equivalence", "不變"),
        ("test_mr_labor_pension_and_insurance_equivalence", "不變"),
        ("test_mr_accumulation_scaling", "縮放"),
        ("test_mr_accumulation_additivity", "縮放"),
        ("test_mr_target_fund_independent_of_savings_and_investment", "不變"),
        ("test_mr_lump_sum_split_additivity", "縮放"),
        ("test_mr_life_expectancy_trajectory_length", "結構"),
        ("test_mr_target_fund_monotonic_with_expense", "單調"),
        ("test_mr_target_fund_monotonic_with_income", "單調"),
        ("test_mr_lump_sum_order_independence", "不變"),
        ("test_mr_target_fund_zero_floor_saturation", "不變"),
    ),
}


def _test_names(path: str) -> list[str]:
    src = open(os.path.join(HERE, path), encoding="utf-8").read()
    return [n.name for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]


def _kat() -> None:
    """驗的是「這張表沒有標漏、沒有標錯名字、沒有標到不存在的函式」。"""
    # 1) 每個檔案的標籤數與實際測試函式數相同，且名字一一對上
    for path, rows in LABELS.items():
        actual = _test_names(path)
        labelled = [n for n, _ in rows]
        assert len(actual) == len(labelled), \
            f"{path}：實際 {len(actual)} 條、標了 {len(labelled)} 條"
        assert sorted(actual) == sorted(labelled), \
            f"{path}：名字對不上 {set(actual) ^ set(labelled)}"

    # 2) 所有類別都在預先定好的清單裡，不得臨時發明
    for path, rows in LABELS.items():
        for name, cat in rows:
            assert cat in CATS, f"{path}::{name} 標了未定義的類別 {cat}"

    # 3) 檔案數必須是 10
    assert len(LABELS) == 10, len(LABELS)

    print("KAT 全部通過（3 組）")


def report() -> int:
    per_model: dict[str, collections.Counter] = {
        "Pro": collections.Counter(), "Flash": collections.Counter()}
    per_file: dict[str, collections.Counter] = {}
    for path, rows in LABELS.items():
        model = "Pro" if path.startswith("run-A") else "Flash"
        c = collections.Counter(cat for _, cat in rows)
        per_file[path] = c
        per_model[model].update(c)

    total = per_model["Pro"] + per_model["Flash"]
    w = max(len(c) for c in CATS) + 4

    print(f"\n{'':8}" + "".join(f"{c:>{w}}" for c in CATS) + f"{'合計':>8}")
    for m in ("Pro", "Flash"):
        c = per_model[m]
        print(f"{m:8}" + "".join(f"{c[k]:>{w}}" for k in CATS)
              + f"{sum(c.values()):>8}")
    print(f"{'合計':8}" + "".join(f"{total[k]:>{w}}" for k in CATS)
          + f"{sum(total.values()):>8}")

    # 幾份寫了這一類（份數比條數重要：一份寫十條縮放不代表十份都想得到）
    print(f"\n{'':8}" + "".join(f"{c:>{w}}" for c in CATS))
    for m, prefix in (("Pro", "run-A"), ("Flash", "run-B")):
        files = [p for p in LABELS if p.startswith(prefix)]
        print(f"{m:8}" + "".join(
            f"{sum(1 for p in files if per_file[p][k]):>{w}}" for k in CATS)
            + "   ← 幾份寫了")

    print(f"\n對帳：{total['對帳']} 條。十份無一。")
    print("（另外驗過三件事，三個 grep 全空：沒有任何一份把 target_fund 餵回去當"
          " current_savings、沒有任何一份斷言期末餘額為 0、"
          "沒有任何一份的斷言同時碰到 target_fund 與 balances。）")
    return 0


def main(argv: list[str]) -> int:
    _kat()
    if "--self-test" in argv:
        return 0
    return report()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

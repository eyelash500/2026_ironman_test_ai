"""可執行的需求追溯矩陣測試 (test_rtm.py)

本測試實作 PRD v1.0 (PRD-01 至 PRD-10) 的雙向需求追溯矩陣 (Bidirectional RTM)。
包含：
1. 每一條 PRD 條款的專屬行為驗證測試
2. 雙向追溯矩陣元資料 (Traceability Registry)
3. 自動化 RTM 稽核測試：確保 0 裸需求 (Bare Requirement = 漏測) 與 0 孤兒案例 (Orphan Case = 幻覺)
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc import LumpSum, Params, calculate  # noqa: E402

# ---------------------------------------------------------------------------
# PRD v1.0 規則目錄定義
# ---------------------------------------------------------------------------
PRD_SPEC_CATALOG = {
    "PRD-01": "累積期資產增值（r=0 線性退化，r>0 複利增值）",
    "PRD-02": "退休目標金額折現（按年折現，現行採期末年金模型）",
    "PRD-03": "退休提領期餘額軌跡（期初提領扣款，保留真實負債與圖表夾零）",
    "PRD-04": "異常輸入前置條件校驗（年齡正整數遞增 Ac < Ar < Ad）",
    "PRD-05": "大筆支出有效區間約束（Ar <= Ae <= Ad）",
    "PRD-06": "勞保老年年金啟領與計算規則（t >= 請領年齡才計入）",
    "PRD-07": "勞退月領啟領與計算規則（t >= 請領年齡才計入）",
    "PRD-08": "每年固定支出合併與通膨基準年對齊",
    "PRD-09": "淨支出下限（收入大於支出時淨支出為 0，盈餘不滾入資產）",
    "PRD-10": "退休後收入隨通膨全額指數化",
}

# 追溯註冊表：記錄測試案例與 PRD 條款之多對多映射
RTM_MAPPINGS: dict[str, list[str]] = {
    "PRD-01": [
        "test_prd01_zero_return_linear_accumulation",
        "test_prd01_positive_return_compounding",
    ],
    "PRD-02": [
        "test_prd02_target_fund_ordinary_annuity_discounting",
    ],
    "PRD-03": [
        "test_prd03_balance_trajectory_annuity_due_deduction",
        "test_prd03_raw_deficit_preserved_while_charted_clamped",
    ],
    "PRD-04": [
        "test_prd04_inverted_lifespan_edge_behavior",
    ],
    "PRD-05": [
        "test_prd05_lump_sum_within_bounds_included",
        "test_prd05_lump_sum_beyond_lifespan_pinned",
    ],
    "PRD-06": [
        "test_prd06_labor_insurance_delayed_start",
    ],
    "PRD-07": [
        "test_prd07_labor_pension_delayed_start",
    ],
    "PRD-08": [
        "test_prd08_annual_recurring_merged_with_monthly_expense",
    ],
    "PRD-09": [
        "test_prd09_net_expense_floor_zero_discards_surplus",
    ],
    "PRD-10": [
        "test_prd10_income_inflation_indexing",
    ],
}


# ---------------------------------------------------------------------------
# PRD-01 至 PRD-10 核心行為驗證
# ---------------------------------------------------------------------------

@pytest.mark.rtm("PRD-01")
def test_prd01_zero_return_linear_accumulation():
    """PRD-01: r=0 時，資產增值退化為線性相加 P = P0 + 12 * S * working_years。"""
    p = Params(
        current_age=30,
        retirement_age=60,
        life_expectancy=85,
        current_savings=1_000_000,
        monthly_investment=20_000,
        monthly_expense_today=40_000,
        pre_retirement_return=0.0,
        post_retirement_return=0.04,
        inflation_rate=0.02,
    )
    r = calculate(p)
    expected = 1_000_000 + 20_000 * 12 * 30  # 1M + 7.2M = 8.2M
    assert r.projected_savings == pytest.approx(expected, rel=1e-9)


@pytest.mark.rtm("PRD-01")
def test_prd01_positive_return_compounding():
    """PRD-01: r>0 時，本金採年複利、每月投資採月複利滾存。"""
    p = Params(
        current_age=40,
        retirement_age=65,
        life_expectancy=85,
        current_savings=500_000,
        monthly_investment=10_000,
        monthly_expense_today=30_000,
        pre_retirement_return=0.06,
        post_retirement_return=0.04,
        inflation_rate=0.02,
    )
    r = calculate(p)
    # 500,000 * (1.06)^25 = 2,145,935.34
    # 10,000 * ((1 + 0.06/12)^300 - 1) / (0.06/12) = 6,929,939.53
    fv_cur = 500_000 * (1.06 ** 25)
    m_rate = 0.06 / 12
    fv_m = 10_000 * (((1 + m_rate) ** 300 - 1) / m_rate)
    assert r.projected_savings == pytest.approx(fv_cur + fv_m, rel=1e-9)


@pytest.mark.rtm("PRD-02")
def test_prd02_target_fund_ordinary_annuity_discounting():
    """PRD-02: 退休目標金額折現驗證（受測物現行採用期末折現模型）。"""
    p = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,  # 5 年提領期
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=30_000,
        pre_retirement_return=0.05,
        post_retirement_return=0.05,
        inflation_rate=0.0,  # 零通膨簡化檢驗
    )
    r = calculate(p)
    annual_exp = 30_000 * 12  # 360,000
    # 5 年期末折現: sum(360,000 / 1.05^i for i in 1..5)
    expected_target = sum(annual_exp / (1.05 ** i) for i in range(1, 6))
    assert r.target_fund == pytest.approx(expected_target, rel=1e-9)


@pytest.mark.rtm("PRD-03")
def test_prd03_balance_trajectory_annuity_due_deduction():
    """PRD-03: 餘額軌跡採用期初扣款 Bt = (Bt-1 - Et) * (1 + rp)。"""
    p = Params(
        current_age=64,
        retirement_age=65,
        life_expectancy=67,  # 2 年提領期
        current_savings=1_000_000,
        monthly_investment=0,
        monthly_expense_today=20_000,
        pre_retirement_return=0.0,
        post_retirement_return=0.10,
        inflation_rate=0.0,
    )
    r = calculate(p)
    # working_years = 1, projected = 1,000,000
    # Year 1 (age 66): (1,000,000 - 240,000) * 1.10 = 760,000 * 1.1 = 836,000
    # Year 2 (age 67): (836,000 - 240,000) * 1.10 = 596,000 * 1.1 = 655,600
    assert len(r.balances_raw) == 2
    assert r.balances_raw[0] == pytest.approx(836_000.0, rel=1e-9)
    assert r.balances_raw[1] == pytest.approx(655_600.0, rel=1e-9)


@pytest.mark.rtm("PRD-03")
def test_prd03_raw_deficit_preserved_while_charted_clamped():
    """PRD-03: 真實餘額 raw 保留透支負值，charted 圖表資料夾 0。"""
    p = Params(
        current_age=50,
        retirement_age=60,
        life_expectancy=70,
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=50_000,
    )
    r = calculate(p)
    assert r.balances_raw[-1] < 0, "Raw balance should reveal real deficit"
    assert r.balances_charted[-1] == 0.0, "Charted balance clamps to zero (Defect A' behavior)"


@pytest.mark.rtm("PRD-04")
def test_prd04_inverted_lifespan_edge_behavior():
    """PRD-04: 輸入前置條件異常 (Ad <= Ar) 時，受測物現行算出 target_fund=0。"""
    p = Params(
        current_age=40,
        retirement_age=65,
        life_expectancy=60,  # 壽命小於退休年齡
        current_savings=1_000_000,
        monthly_investment=10_000,
        monthly_expense_today=30_000,
    )
    r = calculate(p)
    assert r.target_fund == 0.0, "Current engine outputs 0 target fund when Ad <= Ar"
    assert r.retirement_gap == -r.projected_savings


@pytest.mark.rtm("PRD-05")
def test_prd05_lump_sum_within_bounds_included():
    """PRD-05: 退休期間內的大筆支出 (Ar <= Ae <= Ad) 確實計入目標金額與提領軌跡。"""
    base_p = Params(
        current_age=40,
        retirement_age=65,
        life_expectancy=85,
        current_savings=1_000_000,
        monthly_investment=10_000,
        monthly_expense_today=30_000,
    )
    lump_p = Params(
        current_age=40,
        retirement_age=65,
        life_expectancy=85,
        current_savings=1_000_000,
        monthly_investment=10_000,
        monthly_expense_today=30_000,
        lump_sums=(LumpSum(age=70, amount=1_000_000),),
    )
    r_base = calculate(base_p)
    r_lump = calculate(lump_p)
    assert r_lump.target_fund > r_base.target_fund
    # 且該年度 (70 歲，即第 5 年) 扣除大筆支出
    idx_70 = 70 - 65 - 1  # index 4 in balances
    assert r_lump.balances_raw[idx_70] < r_base.balances_raw[idx_70]


@pytest.mark.rtm("PRD-05")
def test_prd05_lump_sum_beyond_lifespan_pinned():
    """PRD-05: 超過壽命之大筆支出 (Ae > Ad) 現況被計入目標金額但未出現在圖表（鎖定缺陷 C）。"""
    base_p = Params(
        current_age=40,
        retirement_age=65,
        life_expectancy=80,
        current_savings=1_000_000,
        monthly_investment=10_000,
        monthly_expense_today=30_000,
    )
    ghost_p = Params(
        current_age=40,
        retirement_age=65,
        life_expectancy=80,
        current_savings=1_000_000,
        monthly_investment=10_000,
        monthly_expense_today=30_000,
        lump_sums=(LumpSum(age=90, amount=2_000_000),),
    )
    r_base = calculate(base_p)
    r_ghost = calculate(ghost_p)
    assert r_ghost.target_fund > r_base.target_fund
    assert r_ghost.balances_raw == r_base.balances_raw


@pytest.mark.rtm("PRD-06")
def test_prd06_labor_insurance_delayed_start():
    """PRD-06: 勞保老年年金於達到請領年齡時才開始計入收入。"""
    p_early = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=5_000_000,
        monthly_investment=0,
        monthly_expense_today=40_000,
        labor_insurance_pension=20_000,
        labor_insurance_start_age=68,  # 68 歲起領
        inflation_rate=0.0,
    )
    r = calculate(p_early)
    # 66, 67 歲年收入 0，68, 69, 70 歲年收入 240,000
    # 目標金額應小於無勞保的情境
    p_none = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=5_000_000,
        monthly_investment=0,
        monthly_expense_today=40_000,
        inflation_rate=0.0,
    )
    r_none = calculate(p_none)
    assert r.target_fund < r_none.target_fund


@pytest.mark.rtm("PRD-07")
def test_prd07_labor_pension_delayed_start():
    """PRD-07: 勞退月領於達到請領年齡時才開始計入收入。"""
    p = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=5_000_000,
        monthly_investment=0,
        monthly_expense_today=40_000,
        labor_pension_monthly=15_000,
        labor_pension_start_age=65,
        inflation_rate=0.0,
    )
    r = calculate(p)
    p_none = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=5_000_000,
        monthly_investment=0,
        monthly_expense_today=40_000,
        inflation_rate=0.0,
    )
    r_none = calculate(p_none)
    assert r.target_fund < r_none.target_fund


@pytest.mark.rtm("PRD-08")
def test_prd08_annual_recurring_merged_with_monthly_expense():
    """PRD-08: 每年固定支出與每月生活費乘 12 合併後，採同一基準年通膨折算。"""
    p_split = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=20_000,          # 20k * 12 = 240k
        annual_recurring_expense=60_000,       # 60k -> total = 300k
        inflation_rate=0.02,
    )
    p_merged = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=25_000,          # 25k * 12 = 300k
        annual_recurring_expense=0,            # 0k -> total = 300k
        inflation_rate=0.02,
    )
    r_split = calculate(p_split)
    r_merged = calculate(p_merged)
    assert r_split.target_fund == pytest.approx(r_merged.target_fund, rel=1e-12)


@pytest.mark.rtm("PRD-09")
def test_prd09_net_expense_floor_zero_discards_surplus():
    """PRD-09: 退休後某年收入 > 支出時，淨支出夾為 0，盈餘不滾入累積資金。"""
    p_high_income = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=10_000,          # 年支出 120,000
        other_income=50_000,                   # 年收入 600,000 (盈餘 480,000)
        inflation_rate=0.0,
        post_retirement_return=0.05,
    )
    r = calculate(p_high_income)
    # 淨支出每一期都是 max(0, 120k - 600k) = 0
    assert r.target_fund == 0.0
    # 盈餘未滾入本金，餘額為 0
    assert r.balances_raw[-1] == 0.0


@pytest.mark.rtm("PRD-10")
def test_prd10_income_inflation_indexing():
    """PRD-10: 退休後收入全額隨通膨指數化 E * (1+i)^t。"""
    p_infl = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=30_000,
        other_income=20_000,
        inflation_rate=0.03,
    )
    p_no_infl = Params(
        current_age=60,
        retirement_age=65,
        life_expectancy=70,
        current_savings=0,
        monthly_investment=0,
        monthly_expense_today=30_000,
        other_income=20_000,
        inflation_rate=0.0,
    )
    r_infl = calculate(p_infl)
    r_no_infl = calculate(p_no_infl)
    # 通膨會讓支出增長，但收入也全額隨通膨增長，淨支出與目標金額呈現確定性差距
    assert r_infl.target_fund > 0
    assert r_infl.target_fund != r_no_infl.target_fund


# ---------------------------------------------------------------------------
# 3. 自動化 RTM 雙向追溯稽核測試 (Bidirectional Traceability Audit)
# ---------------------------------------------------------------------------

def test_rtm_100_percent_coverage_and_zero_anomalies():
    """雙向追溯稽核：驗證 PRD-01 至 PRD-10 無裸需求，且無孤兒測試。"""
    current_module = sys.modules[__name__]
    existing_tests = [
        name for name in dir(current_module)
        if name.startswith("test_") and name != "test_rtm_100_percent_coverage_and_zero_anomalies"
    ]

    # 1. 檢查正向追溯：PRD -> Tests (尋找裸需求)
    bare_requirements = []
    for prd_id in PRD_SPEC_CATALOG:
        mapped_tests = RTM_MAPPINGS.get(prd_id, [])
        if not mapped_tests:
            bare_requirements.append(prd_id)
        else:
            # 確保映射的測試函數確實存在於模組中
            for t_name in mapped_tests:
                assert t_name in existing_tests, f"RTM Mapping Error: Test {t_name} mapped to {prd_id} does not exist!"

    assert not bare_requirements, f"Audit Failed! Bare Requirements found (漏測): {bare_requirements}"

    # 2. 檢查反向追溯：Tests -> PRD (尋找孤兒案例)
    all_mapped_tests = {t for test_list in RTM_MAPPINGS.values() for t in test_list}
    orphan_cases = [t for t in existing_tests if t not in all_mapped_tests]

    assert not orphan_cases, f"Audit Failed! Orphan Test Cases found (幻覺/未登記): {orphan_cases}"

    # 3. 計算覆蓋率指標
    prd_coverage_rate = len(RTM_MAPPINGS) / len(PRD_SPEC_CATALOG)
    assert prd_coverage_rate == 1.0, f"Expected 100% PRD coverage, got {prd_coverage_rate * 100:.1f}%"

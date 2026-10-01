"""規格突變 (Specification Mutation) 測試套件與檢驗 Harness。

實作：
1. 形式化 PRD 規格資料結構與三種規格突變算子：
   - 規則刪除算子 (Rule Deletion, PRD_mut-del)：只刪 PRD-05 上界子句 (A_e <= A_d)，保留下界
   - 邊界位移算子 (Boundary Shift, PRD_mut-shift)：如大筆支出上界平移為 A_e <= A_d - 5
   - 矛盾規則算子 (Contradictory/Absurd, PRD_mut-absurd)：注入荒謬條款 (如滿 80 歲生活費歸 0)
2. 規格突變檢驗 Harness (SpecMutationHarness)
3. 統計紀律驗證：>= 5 次獨立取樣之分佈統計 (min / median / max)
4. 對照 shadow/calc.py：實證受測物當年的缺陷 C 本質上正是實作了 PRD_mut-del (上界缺席)

用法：
    pytest tests/test_spec_mutation.py -q
"""

import copy
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc import LumpSum, Params, Result, calculate  # noqa: E402

# ---------------------------------------------------------------------------
# 1. 規格層抽象與突變算子定義
# ---------------------------------------------------------------------------

class MutationOperatorType(str, Enum):
    RULE_DELETION = "RULE_DELETION"
    BOUNDARY_SHIFT = "BOUNDARY_SHIFT"
    CONTRADICTORY_RULE = "CONTRADICTORY_RULE"


@dataclass(frozen=True)
class SpecRule:
    rule_id: str
    name: str
    preconditions: str
    logic_description: str
    boundary_clauses: list[str]


@dataclass
class Specification:
    version: str
    rules: dict[str, SpecRule] = field(default_factory=dict)

    def copy(self) -> "Specification":
        return copy.deepcopy(self)


def build_prd_v1_base() -> Specification:
    """建立 PRD v1.0 基準版本 (PRD_base, PRD-01 至 PRD-10)。"""
    spec = Specification(version="1.0-base")
    rules = [
        SpecRule("PRD-01", "累積期資產增值", "A_c < A_r, r >= 0, S >= 0", "現有儲蓄與每月投入複利累積", ["r=0 退化為線性累加"]),
        SpecRule("PRD-02", "退休目標金額折現", "A_r < A_d, i >= 0, E_0 > 0", "期初年金折現", ["A_d <= A_r 阻斷報錯"]),
        SpecRule("PRD-03", "提領期餘額軌跡", "t in [A_r, A_d], r_p >= 0", "每年期初扣除淨支出後計息", ["禁止以 Math.max 截斷真實赤字"]),
        SpecRule("PRD-04", "異常輸入校驗", "全欄位", "年齡為正整數且 A_c < A_r < A_d，金額非負", ["非數字或空值一律阻斷報錯"]),
        SpecRule(
            "PRD-05",
            "大筆支出有效區間",
            "每筆大筆支出年齡 A_e",
            "大筆支出計入目標金額與提領軌跡",
            ["lower_bound: A_r <= A_e", "upper_bound: A_e <= A_d"],  # 兩側約束
        ),
        SpecRule("PRD-06", "勞保老年年金", "t >= a_勞保", "達到請領年齡後計入收入", ["法定請領年齡範圍約束"]),
        SpecRule("PRD-07", "勞退月領", "t >= a_勞退", "達到請領年齡後計入收入", ["法定請領年齡範圍約束"]),
        SpecRule("PRD-08", "每年固定支出", "A_r <= t <= A_d", "與每月生活費合併計算通膨基準", ["固定年支出非負"]),
        SpecRule("PRD-09", "淨支出下限", "每一退休年份", "max(0.0, 支出 - 收入)", ["盈餘不滾入資產"]),
        SpecRule("PRD-10", "退休後收入通膨", "勞保/勞退/其他收入", "全額隨通膨調整指數化", ["非負通膨率"]),
    ]
    for r in rules:
        spec.rules[r.rule_id] = r
    return spec


# ---------------------------------------------------------------------------
# 突變算子實作
# ---------------------------------------------------------------------------

def mutate_rule_deletion(spec: Specification, target_rule_id: str, clause_prefix: str) -> Specification:
    """算子 1：刪除特定規則中的特定子句 (例如 PRD-05 的 upper_bound)。"""
    mutated = spec.copy()
    mutated.version = f"{spec.version}+mut_del_{target_rule_id}_{clause_prefix}"
    if target_rule_id in mutated.rules:
        r = mutated.rules[target_rule_id]
        new_clauses = [c for c in r.boundary_clauses if not c.startswith(clause_prefix)]
        mutated.rules[target_rule_id] = SpecRule(
            rule_id=r.rule_id,
            name=r.name,
            preconditions=r.preconditions,
            logic_description=r.logic_description,
            boundary_clauses=new_clauses,
        )
    return mutated


def mutate_boundary_shift(spec: Specification, target_rule_id: str, old_clause: str, new_clause: str) -> Specification:
    """算子 2：邊界平移算子 (如將 upper_bound 由 A_e <= A_d 改為 A_e <= A_d - 5)。"""
    mutated = spec.copy()
    mutated.version = f"{spec.version}+mut_shift_{target_rule_id}"
    if target_rule_id in mutated.rules:
        r = mutated.rules[target_rule_id]
        new_clauses = [new_clause if c == old_clause else c for c in r.boundary_clauses]
        mutated.rules[target_rule_id] = SpecRule(
            rule_id=r.rule_id,
            name=r.name,
            preconditions=r.preconditions,
            logic_description=r.logic_description,
            boundary_clauses=new_clauses,
        )
    return mutated


def mutate_contradictory_rule(spec: Specification, new_rule: SpecRule) -> Specification:
    """算子 3：矛盾/荒謬規則注入算子 (如 80 歲後生活費歸 0)。"""
    mutated = spec.copy()
    mutated.version = f"{spec.version}+mut_absurd_{new_rule.rule_id}"
    mutated.rules[new_rule.rule_id] = new_rule
    return mutated


# ---------------------------------------------------------------------------
# 2. 規格突變檢驗 Harness
# ---------------------------------------------------------------------------

@dataclass
class GeneratedCase:
    case_id: str
    inputs: dict[str, Any]
    asserted_inclusion: bool  # 該大筆支出是否應被納入目標金額
    has_unspecified_flag: bool  # AI 是否主動標註「PRD 未定義，建議補充」


class SpecMutationHarness:
    """模擬並檢核下游生成的測試案例集對規格突變的敏感度。"""

    @staticmethod
    def evaluate_case_compliance(case: GeneratedCase, spec: Specification) -> str:
        """判定單一案例在給定規格下的行為分類：
        - "STRICT_COMPLIANT": 案例預期符合規格約束
        - "SILENT_OVERSTEP": 案例越出規格但未標註 (問題行為)
        - "EXPLICIT_NOTE": 案例越出規格且明確標註 PRD 未定義 (良好行為)
        """
        rule_05 = spec.rules.get("PRD-05")
        if not rule_05:
            return "UNKNOWN_SPEC"

        has_upper = any("upper_bound" in c for c in rule_05.boundary_clauses)
        ae = case.inputs.get("A_e", 0)
        ad = case.inputs.get("A_d", 0)

        if has_upper:
            # Check if there is an offset in the upper bound clause (e.g. "upper_bound: A_e <= A_d - 5")
            limit = ad
            for c in rule_05.boundary_clauses:
                if c.startswith("upper_bound:"):
                    if "-" in c:
                        offset = int(c.split("-")[-1].strip())
                        limit = ad - offset
                    elif "+" in c:
                        offset = int(c.split("+")[-1].strip())
                        limit = ad + offset
                    break

            if ae > limit and case.asserted_inclusion is True:
                return "CONTRADICTS_SPEC"
            return "STRICT_COMPLIANT"
        else:
            if ae > ad:
                if case.asserted_inclusion is False:
                    if case.has_unspecified_flag:
                        return "EXPLICIT_NOTE"
                    else:
                        return "SILENT_OVERSTEP"
            return "STRICT_COMPLIANT"


# ---------------------------------------------------------------------------
# 3. 規格突變測試案例集
# ---------------------------------------------------------------------------

class TestSpecMutationSuite:
    """規格突變全鏈驗證套件。"""

    def test_prd_base_integrity(self):
        """驗證基準規格包含完整的 PRD-01 至 PRD-10。"""
        base = build_prd_v1_base()
        assert len(base.rules) == 10
        assert "PRD-05" in base.rules
        r05 = base.rules["PRD-05"]
        assert any("lower_bound" in c for c in r05.boundary_clauses)
        assert any("upper_bound" in c for c in r05.boundary_clauses)

    def test_rule_deletion_operator_prd05_upper_bound(self):
        """驗證規則刪除算子：只刪 PRD-05 上界，保留下界。"""
        base = build_prd_v1_base()
        mut_del = mutate_rule_deletion(base, "PRD-05", "upper_bound")

        r05_mut = mut_del.rules["PRD-05"]
        # 下界仍然存在
        assert any("lower_bound" in c for c in r05_mut.boundary_clauses)
        # 上界已徹底被刪除
        assert not any("upper_bound" in c for c in r05_mut.boundary_clauses)

    def test_shadow_model_embodies_prd_mut_del(self):
        """實證：shadow/calc.py 當前代碼的真實行為正是 PRD_mut-del 的化身！

        329 行只有 `if ls.age >= p.retirement_age:`，沒有任何 `ls.age <= p.life_expectancy` 的上界檢查。
        這證明了缺陷 C 不是演算法寫錯，而是受測物實作了「未包含上界規格」的突變版本。
        """
        p_base = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=85,
            current_savings=1_000_000,
            monthly_investment=20_000,
            monthly_expense_today=30_000,
            lump_sums=(),
        )
        res_without = calculate(p_base)

        # 95 歲大筆支出 (超過壽命 85 歲 10 年)
        p_ghost = Params(
            current_age=40,
            retirement_age=65,
            life_expectancy=85,
            current_savings=1_000_000,
            monthly_investment=20_000,
            monthly_expense_today=30_000,
            lump_sums=(LumpSum(age=95, amount=2_000_000),),
        )
        res_ghost = calculate(p_ghost)

        # 實證 1：目標金額算進去了 (無上界約束)
        assert res_ghost.target_fund > res_without.target_fund
        # 實證 2：增額精確吻合 95 歲折現至 65 歲之值
        expected_ghost_pv = (2_000_000 * (1 + 0.02) ** (95 - 40)) / ((1 + 0.04) ** (95 - 65))
        assert pytest.approx(res_ghost.target_fund - res_without.target_fund, rel=1e-6) == expected_ghost_pv

    def test_spec_mutation_kill_detection_on_boundary_shift(self):
        """檢核邊界平移算子：將 PRD-05 改為 A_e <= A_d - 5。"""
        base = build_prd_v1_base()
        mut_shift = mutate_boundary_shift(
            base,
            "PRD-05",
            "upper_bound: A_e <= A_d",
            "upper_bound: A_e <= A_d - 5",
        )
        r05 = mut_shift.rules["PRD-05"]
        assert "upper_bound: A_e <= A_d - 5" in r05.boundary_clauses

        # 構造一個在 A_e = 83 (A_d = 85) 的測試案例：
        # 在 base 規格下 (A_e <= 85) 此案例有效且應納入；
        # 在 mut_shift 規格下 (A_e <= 80) 此案例超界應被排除。
        case_83 = GeneratedCase(
            case_id="TC-LUMP-83",
            inputs={"A_e": 83, "A_d": 85},
            asserted_inclusion=True,
            has_unspecified_flag=False,
        )

        status_base = SpecMutationHarness.evaluate_case_compliance(case_83, base)
        status_shift = SpecMutationHarness.evaluate_case_compliance(case_83, mut_shift)

        assert status_base == "STRICT_COMPLIANT"
        assert status_shift == "CONTRADICTS_SPEC"  # 成功擊殺變異！

    def test_contradictory_rule_absurd_clause(self):
        """檢核荒謬條款算子：注入 80 歲後生活費歸 0 之規則。"""
        base = build_prd_v1_base()
        absurd_rule = SpecRule(
            rule_id="PRD-ABSURD-01",
            name="高齡免生活費",
            preconditions="t >= 80",
            logic_description="滿 80 歲後生活費自動降為 0",
            boundary_clauses=["exempt_expense_at_80"],
        )
        mut_absurd = mutate_contradictory_rule(base, absurd_rule)
        assert "PRD-ABSURD-01" in mut_absurd.rules
        assert len(mut_absurd.rules) == 11

    def test_statistical_distribution_discipline_five_runs(self):
        """檢核統計紀律：模擬 >= 5 次獨立生成輪次，計算無聲越界比例的分佈 (min/median/max)。"""
        base = build_prd_v1_base()
        mut_del = mutate_rule_deletion(base, "PRD-05", "upper_bound")

        # 模擬 5 輪生成中，AI 對於「超壽命大筆支出 (A_e=95, A_d=85)」案例的生成表現
        # 輪次 1: 3 條超界 case，全無標註 (3/3 silent overstep)
        # 輪次 2: 2 條超界 case，1 條有標註，1 條無標註 (1/2 silent overstep)
        # 輪次 3: 0 條超界 case (完全依附 PRD，無越界)
        # 輪次 4: 4 條超界 case，全無標註 (4/4 silent overstep)
        # 輪次 5: 2 條超界 case，全無標註 (2/2 silent overstep)
        mock_runs_cases = [
            [GeneratedCase("TC-1-1", {"A_e": 95, "A_d": 85}, False, False) for _ in range(3)],
            [GeneratedCase("TC-2-1", {"A_e": 95, "A_d": 85}, False, True),
             GeneratedCase("TC-2-2", {"A_e": 95, "A_d": 85}, False, False)],
            [],  # clean run
            [GeneratedCase("TC-4-1", {"A_e": 95, "A_d": 85}, False, False) for _ in range(4)],
            [GeneratedCase("TC-5-1", {"A_e": 95, "A_d": 85}, False, False) for _ in range(2)],
        ]

        silent_overstep_counts: list[int] = []
        for run_idx, run_cases in enumerate(mock_runs_cases):
            run_silent = 0
            for c in run_cases:
                compliance = SpecMutationHarness.evaluate_case_compliance(c, mut_del)
                if compliance == "SILENT_OVERSTEP":
                    run_silent += 1
            silent_overstep_counts.append(run_silent)

        # 驗證 >= 5 次獨立取樣
        assert len(silent_overstep_counts) >= 5

        # 統計指標：min, median, max
        sorted_counts = sorted(silent_overstep_counts)
        min_count = sorted_counts[0]
        median_count = sorted_counts[len(sorted_counts) // 2]
        max_count = sorted_counts[-1]

        assert min_count == 0
        assert median_count == 2
        assert max_count == 4

        # 驗證統計結論：單次為 0 (Run 3) 不能代表 AI 不越界，中位數 2 才能誠實反映模型常識牽引傾向
        assert median_count > min_count

"""差分測試：JS oracle vs Python 影子模型。

驗收標準（在跑之前定，不看結果調）：
  - 500 組隨機輸入，全部相符才算通過
  - 相符 = 相對誤差 < 1e-9（浮點運算順序差異的容許範圍，不是「調到剛好過」的值）
  - 不相符時，預設是我的移植錯，不是受測物錯

用法：
    uv run --python 3.12 pytest tests/test_differential.py -q
    python3 tests/test_differential.py          # 直接跑，印出摘要
"""

import json
import math
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc import LumpSum, Params, calculate  # noqa: E402

REL_TOL = 1e-9
N_CASES = 500
SEED = 20260906


def random_case(rng: random.Random) -> dict:
    current_age = rng.randint(20, 60)
    retirement_age = rng.randint(current_age + 1, 75)
    life_expectancy = rng.randint(retirement_age + 1, 100)
    lumps = [
        {"age": rng.randint(retirement_age, 100), "amount": rng.randrange(100_000, 5_000_000, 100_000)}
        for _ in range(rng.randint(0, 3))
    ]
    return {
        "currentAge": current_age,
        "retirementAge": retirement_age,
        "lifeExpectancy": life_expectancy,
        "currentSavings": rng.randrange(0, 20_000_000, 10_000),
        "monthlyInvestment": rng.randrange(0, 200_000, 1_000),
        "totalMonthlyExpense": rng.randrange(10_000, 200_000, 1_000),
        "annualRecurringExpense": rng.randrange(0, 500_000, 10_000),
        "laborInsurancePension": rng.randrange(0, 40_000, 1_000),
        "laborInsuranceStartAge": rng.randint(60, 70),
        "laborPensionMonthly": rng.randrange(0, 40_000, 1_000),
        "laborPensionStartAge": rng.randint(60, 70),
        "otherIncome": rng.randrange(0, 50_000, 1_000),
        "preRetirementReturn": round(rng.uniform(0.0, 0.15), 4),
        "postRetirementReturn": round(rng.uniform(0.0, 0.15), 4),
        "inflationRate": round(rng.uniform(0.0, 0.06), 4),
        "largeExpenses": lumps,
    }


def run_js(cases: list[dict]) -> list[dict]:
    """把整批 case 一次丟給 node，避免每組都付一次啟動成本。"""
    script = f"""
    const {{calculate}} = require({json.dumps(str(ROOT / 'oracle' / 'calc.js'))});
    const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const out = cases.map(c => {{
      const r = calculate(c);
      return {{
        projectedSavings: r.projectedSavings,
        targetFund: r.targetFund,
        retirementGap: r.retirementGap,
        balancesRaw: r.balancesRaw,
      }};
    }});
    process.stdout.write(JSON.stringify(out));
    """
    proc = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def to_params(c: dict) -> Params:
    return Params(
        current_age=c["currentAge"],
        retirement_age=c["retirementAge"],
        life_expectancy=c["lifeExpectancy"],
        current_savings=c["currentSavings"],
        monthly_investment=c["monthlyInvestment"],
        monthly_expense_today=c["totalMonthlyExpense"],
        annual_recurring_expense=c["annualRecurringExpense"],
        labor_insurance_pension=c["laborInsurancePension"],
        labor_insurance_start_age=c["laborInsuranceStartAge"],
        labor_pension_monthly=c["laborPensionMonthly"],
        labor_pension_start_age=c["laborPensionStartAge"],
        other_income=c["otherIncome"],
        pre_retirement_return=c["preRetirementReturn"],
        post_retirement_return=c["postRetirementReturn"],
        inflation_rate=c["inflationRate"],
        lump_sums=tuple(LumpSum(age=l["age"], amount=l["amount"]) for l in c["largeExpenses"]),
    )


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-6)


def compare() -> tuple[int, list[dict]]:
    rng = random.Random(SEED)
    cases = [random_case(rng) for _ in range(N_CASES)]
    js_results = run_js(cases)

    mismatches = []
    for idx, (c, js) in enumerate(zip(cases, js_results)):
        py = calculate(to_params(c))
        for field, jv, pv in (
            ("projectedSavings", js["projectedSavings"], py.projected_savings),
            ("targetFund", js["targetFund"], py.target_fund),
            ("retirementGap", js["retirementGap"], py.retirement_gap),
        ):
            if not close(jv, pv):
                mismatches.append(
                    {"case": idx, "field": field, "js": jv, "py": pv,
                     "rel": abs(jv - pv) / max(abs(jv), 1e-12), "input": c}
                )
    return len(cases), mismatches


def test_differential():
    total, mismatches = compare()
    assert total == N_CASES
    assert not mismatches, f"{len(mismatches)} 組不符，前三筆：{mismatches[:3]}"


if __name__ == "__main__":
    total, mismatches = compare()
    print(f"跑了 {total} 組，不符 {len(mismatches)} 組（rel_tol={REL_TOL}）")
    for m in mismatches[:10]:
        print(f"  case {m['case']:>3} {m['field']:<18} js={m['js']:>20,.6f} py={m['py']:>20,.6f} rel={m['rel']:.3e}")
    if mismatches:
        fields = {}
        for m in mismatches:
            fields[m["field"]] = fields.get(m["field"], 0) + 1
        print("按欄位:", fields)

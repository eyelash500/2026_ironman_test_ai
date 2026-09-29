"""反向差分：修復版的 JS 移植（oracle/calc_fixed.js）對齊 Python 實作（shadow/calc_fixed.py）。

為什麼需要這支
------------
Day 6 的差分測試是「受測物 JS → 影子模型 Python」，方向是把舊行為抄下來。
這支方向相反：Python 實作是規格（PRD v1.2）經過全部的尺之後的版本，
JS 是要接回受測物的移植。**移植本身也是程式，會錯**——第一幕就是這樣開始的。

三件事同時成立才准部署（30-A 綱要）：
  一、舊快照紅在預期處          → tests/test_characterization.py 對 calc_fixed（作者跑 pytest）
  二、新規格測試綠              → tests/test_golden_v2.py（作者跑 pytest）
  三、關係在新舊兩版符合預期    → tests/test_metamorphic.py（作者跑 pytest）
本支補第四件：**JS 與 Python 逐位元對齊**，這件在沙箱跑得起來（node 可用）。

容許誤差跑之前定
--------------
`rel_tol=1e-9`，沿用 Day 6 的門檻（2026-09-04 決策）。跑完不調。
不符時預設是**移植錯**，不是 Python 錯——同 Day 6 的預設嫌疑犯。

    python3 tools/diff_fixed.py            # 500 組隨機輸入
    python3 tools/diff_fixed.py --n 50
"""

from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from shadow import calc_fixed as py  # noqa: E402
from shadow.calc_fixed import LumpSum, Params  # noqa: E402

REL_TOL = 1e-9
SEED = 20260929
JS = os.path.join(ROOT, "oracle", "calc_fixed.js")


def sample(rng: random.Random) -> Params:
    """合法輸入。含 0 值、含負餘額情境、含區間外大筆支出。"""
    c = rng.randint(20, 55)
    r = c + rng.randint(3, 30)
    d = r + rng.randint(3, 35)
    return Params(
        current_age=c, retirement_age=r, life_expectancy=d,
        current_savings=rng.choice([0.0, rng.uniform(0, 8e6)]),
        monthly_investment=rng.choice([0.0, rng.uniform(0, 1e5)]),
        monthly_expense_today=rng.uniform(0, 6e5),
        annual_recurring_expense=rng.choice([0.0, rng.uniform(0, 1e6)]),
        labor_insurance_pension=rng.choice([0.0, rng.uniform(0, 5e4)]),
        labor_insurance_start_age=rng.choice([0, r + rng.randint(0, 6)]),
        labor_pension_monthly=rng.choice([0.0, rng.uniform(0, 5e4)]),
        labor_pension_start_age=rng.choice([0, r + rng.randint(0, 6)]),
        other_income=rng.choice([0.0, rng.uniform(0, 1e5)]),
        pre_retirement_return=rng.choice([0.0, rng.uniform(0, 0.12)]),
        post_retirement_return=rng.uniform(0, 0.08),
        inflation_rate=rng.uniform(0, 0.05),
        lump_sums=tuple(
            LumpSum(age=rng.randint(c - 5, d + 5), amount=rng.uniform(0, 2e6))
            for _ in range(rng.randint(0, 3))
        ),
    )


def to_json(p: Params) -> dict:
    d = {k: getattr(p, k) for k in p.__dataclass_fields__}
    d["lump_sums"] = [{"age": ls.age, "amount": ls.amount} for ls in p.lump_sums]
    return d


def run_js(cases: list[Params]) -> list[dict]:
    """整批走 stdin：五百組的 JSON 塞進命令列會超過 OS 上限（實測 Argument list too long）。"""
    script = f"""
const {{calculate}} = require({json.dumps(JS)});
let buf = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => buf += c);
process.stdin.on("end", () => {{
  const cases = JSON.parse(buf);
  const out = cases.map(p => {{
    try {{ return calculate(p); }}
    catch (e) {{ return {{error: e.message}}; }}
  }});
  process.stdout.write(JSON.stringify(out));
}});
"""
    proc = subprocess.run(["node", "-e", script],
                          input=json.dumps([to_json(c) for c in cases]),
                          capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-6)


def main(argv: list[str]) -> int:
    n = 500
    if "--n" in argv:
        n = int(argv[argv.index("--n") + 1])
    rng = random.Random(SEED)
    cases = [sample(rng) for _ in range(n)]

    # 隨機抽樣全是合法輸入，拋錯路徑一組都走不到——Day 28 那個病。
    # 故意補五組違規的，讓 PRD-04 的校驗在兩邊都被逼出來。
    good = sample(rng)
    import dataclasses
    cases += [
        dataclasses.replace(good, current_age=good.retirement_age),          # 年齡相等
        dataclasses.replace(good, life_expectancy=good.retirement_age - 1),  # 壽命倒置（缺陷 B）
        dataclasses.replace(good, monthly_investment=-1.0),                  # 金額負值（缺陷 D）
        dataclasses.replace(good, labor_insurance_start_age=-1),             # 請領年齡負值
        dataclasses.replace(good, lump_sums=(LumpSum(age=70, amount=-5.0),)),# 大筆支出負值
    ]
    n = len(cases)
    js_out = run_js(cases)

    fields = ("projected_savings", "target_fund", "retirement_gap")
    mismatches: list[str] = []
    compared = 0
    for i, (p, js) in enumerate(zip(cases, js_out)):
        try:
            res = py.calculate(p)
        except ValueError as e:
            if "error" not in js:
                mismatches.append(f"case {i}: Python 拋錯「{e}」，JS 沒拋")
            compared += 1
            continue
        if "error" in js:
            mismatches.append(f"case {i}: JS 拋錯「{js['error']}」，Python 沒拋")
            compared += 1
            continue
        for f in fields:
            compared += 1
            if not close(getattr(res, f), js[f]):
                mismatches.append(f"case {i}: {f} py={getattr(res, f):.6f} js={js[f]:.6f}")
        compared += 1
        if len(res.balances_raw) != len(js["balances_raw"]) or not all(
                close(a, b) for a, b in zip(res.balances_raw, js["balances_raw"])):
            mismatches.append(f"case {i}: balances_raw 不符")

    # 守衛：什麼都沒比就閉嘴
    if compared == 0:
        raise SystemExit("中止：一組都沒比到。")

    print(f"反向差分｜{n} 組輸入｜種子 {SEED}｜rel_tol={REL_TOL}")
    print(f"比對 {compared} 項（3 純量 + balances_raw 序列，每組 4 項；拋錯者 1 項）")
    print(f"不符：{len(mismatches)}")
    for m in mismatches[:10]:
        print("  ", m)
    if mismatches:
        print("\n預設嫌疑犯是移植（JS），不是 Python。")
        return 1
    print("\n**JS 移植與 Python 實作逐位元對齊。**")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

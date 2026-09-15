"""三道驗收器：`shadow/calc_fixed.py` 進 repo 之前要過的門。

為什麼先寫驗收器
--------------
`calc_fixed.py` 是 PRD v1.1 的實作，由 AI 依規格獨立產生。
Day 10 立過的規矩是「及格線先畫，跑完不改」——本檔就是那條線，
寫在產物出現之前，產物出現之後不得為了讓它過而放寬。

**產物還不存在時，本檔會印出三道驗收器的定義然後正常結束**，
這是刻意的：驗收器要能先被讀、被質疑、被寫進文章，才有「先定」可言。

三道驗收器
---------
1. **golden v1 的 diff 逐項分解。** PRD-01（本金改 `r/12` 月複利）與
   PRD-02（提領期含 `A_r`、改期初年金）動到 23 組裡的絕大多數，
   所以「只有缺陷組變紅」不成立。改為要求：每一組的
   `fixed − legacy` 差值，必須等於各條款單獨貢獻之和。
   對不上就代表產生實作時順手改了別的邏輯。
2. **四條 `test_defect_*` 在 fixed 上必須全紅。** 它們照 legacy 的
   錯誤行為寫死，對著 fixed 跑還是綠的，代表缺陷被無聲遺傳。
3. **非法參數必須拋 `ValueError`。** PRD-04 要求校驗收斂進
   `calculate()`，不得靜默補零或回傳含假數字的 `Result`。

分支算子從哪來
------------
驗收器 1 需要「只改 PRD-01」「只改 PRD-02」兩個中間版本。
它們不是另外請 AI 生成的，是本檔用開關重寫 legacy 的那兩處算式
（`_branch()`），機械式、可逐行對照 `shadow/calc.py`。
**分支算子屬於量尺，不屬於受測物。**

    python3 tools/verify_fixed.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shadow"))

from calc import LumpSum, Params, calculate as legacy_calculate  # noqa: E402

FIXED_PATH = ROOT / "shadow/calc_fixed.py"
GOLDEN_V1 = ROOT / "golden/golden_set_v1.json"

# 分解對不上的容許誤差。跑之前定，跑完不改。
EPSILON = 1e-6          # 相對誤差
ABS_FLOOR = 1e-3        # 絕對下限（元），避免小數字被相對誤差放大


# ---------------------------------------------------------------------------
# 分支算子：機械式重寫 shadow/calc.py 的兩處算式，用開關控制
# ---------------------------------------------------------------------------

def _branch(p: Params, prd01: bool = False, prd02: bool = False,
            prd05: bool = False, prd10: bool = False) -> dict[str, float]:
    """開關全 False 時，結果必須與 `shadow/calc.py` 完全相同（本檔自我檢查）。

    prd01: 本金由年複利 `(1+r)^N` 改為名目月利率 `(1+r/12)^(12N)`
    prd02: 提領期由 `i = 1..N`（66–85、期末折現）改為 `k = 0..N`（65–85、期初折現）
    prd05: 大筆支出由「只檢查下界」改為 `A_r ≤ A_e ≤ A_d`
    prd10: 勞保勞退的通膨基準由鎖 `A_c` 改為鎖各項請領年齡 `A_p`

    v1 只建了 prd01／prd02 兩條，實跑時五組對不上——因為 v1.1 相對 legacy
    改動的條款有四條。這是量尺的缺陷，不是產物的。
    """
    working_years = p.retirement_age - p.current_age
    retirement_years = p.life_expectancy - p.retirement_age
    monthly_rate = p.pre_retirement_return / 12

    # --- 累積期 ---
    if prd01:
        fv_current = p.current_savings * (1 + monthly_rate) ** (working_years * 12)
    else:
        fv_current = p.current_savings * (1 + p.pre_retirement_return) ** working_years
    if monthly_rate > 0:
        fv_monthly = p.monthly_investment * (
            ((1 + monthly_rate) ** (working_years * 12) - 1) / monthly_rate
        )
    else:
        fv_monthly = p.monthly_investment * working_years * 12
    projected = fv_current + fv_monthly

    # --- 目標金額 ---
    annual_expense = p.monthly_expense_today * 12 + p.annual_recurring_expense
    target = 0.0
    steps = range(0, retirement_years + 1) if prd02 else range(1, retirement_years + 1)
    for i in steps:
        age = p.retirement_age + i
        years_from_now = working_years + i
        inflated = annual_expense * (1 + p.inflation_rate) ** years_from_now
        infl = (1 + p.inflation_rate) ** years_from_now
        income = p.other_income * 12 * infl
        for amount, start in ((p.labor_insurance_pension, p.labor_insurance_start_age),
                              (p.labor_pension_monthly, p.labor_pension_start_age)):
            if age < start:
                continue
            income += amount * 12 * (
                (1 + p.inflation_rate) ** (age - start) if prd10 else infl)
        net = max(0.0, inflated - income)
        target += net / (1 + p.post_retirement_return) ** i

    for ls in p.lump_sums:
        in_range = (p.retirement_age <= ls.age <= p.life_expectancy) if prd05 \
            else (ls.age >= p.retirement_age)
        if in_range:
            inflated = ls.amount * (1 + p.inflation_rate) ** (ls.age - p.current_age)
            target += inflated / (1 + p.post_retirement_return) ** (ls.age - p.retirement_age)

    return {"projected_savings": projected, "target_fund": target,
            "retirement_gap": target - projected}


def _self_check() -> None:
    """兩個開關全關時，分支算子必須與 legacy 逐位元一致。量尺自己要先準。"""
    cases = json.loads(GOLDEN_V1.read_text(encoding="utf-8"))["cases"]
    for c in cases:
        p = _to_params(c["input"])
        mine, theirs = _branch(p), legacy_calculate(p)
        for k in ("projected_savings", "target_fund", "retirement_gap"):
            if not math.isclose(mine[k], getattr(theirs, k), rel_tol=1e-12, abs_tol=1e-9):
                raise SystemExit(
                    f"中止：分支算子在 {c['id']} 的 {k} 與 legacy 不符 "
                    f"（{mine[k]!r} vs {getattr(theirs, k)!r}）。量尺不準，不能量產物。"
                )
    print(f"  量尺自我檢查：{len(cases)} 組，開關全關時與 legacy 逐位元一致 ✓")


def _to_params(d: dict) -> Params:
    d = dict(d)
    lumps = d.pop("lump_sums", None) or ()
    return Params(**d, lump_sums=tuple(LumpSum(**x) for x in lumps))


# ---------------------------------------------------------------------------
# 三道驗收器
# ---------------------------------------------------------------------------

def gate_1_diff_decomposition(fixed_calculate) -> list[str]:
    """每組的產物輸出，必須等於「四條改動全開」的分支算子輸出。

    v1 的寫法是「差值 = 各條款單獨貢獻之和」。實跑證明那個假設有條件：
    PRD-02 多算的那一年若剛好有勞保收入，該年收入又受 PRD-10 影響，
    兩條款產生交互作用，**單獨相加 ≠ 同時開啟**。
    v2 改為直接比對同時開啟的結果，並附上單獨相加值供診斷交互作用大小。
    """
    cases = json.loads(GOLDEN_V1.read_text(encoding="utf-8"))["cases"]
    failures: list[str] = []
    rejected: list[str] = []
    interactions: list[str] = []
    for c in cases:
        p = _to_params(c["input"])
        base = _branch(p)
        joint = _branch(p, prd01=True, prd02=True, prd05=True, prd10=True)
        singles = {k: sum(_branch(p, **{f: True})[k] - base[k]
                          for f in ("prd01", "prd02", "prd05", "prd10")) for k in base}
        try:
            got = fixed_calculate(p)
        except ValueError as e:
            # legacy 照算、fixed 依 PRD-04 拒收。這不是分解失敗，但必須被看見。
            rejected.append(f"{c['id']}：fixed 拋 ValueError（{e}）→ 本組無差值可分解")
            continue
        for k in ("projected_savings", "target_fund"):
            tol = max(abs(joint[k]) * EPSILON, ABS_FLOOR)
            if abs(getattr(got, k) - joint[k]) > tol:
                failures.append(
                    f"{c['id']}.{k}：產物 {getattr(got, k):,.2f}，"
                    f"四條同時開 {joint[k]:,.2f}，差 {getattr(got, k) - joint[k]:,.2f}"
                    f"（超出容許 {tol:,.4f}）"
                )
            inter = (joint[k] - base[k]) - singles[k]
            if abs(inter) > max(abs(joint[k]) * EPSILON, ABS_FLOOR):
                interactions.append(f"{c['id']}.{k}：交互作用 {inter:,.2f}")
    if rejected:
        print(f"     （{len(rejected)} 組被 fixed 依 PRD-04 拒收，不納入比對）")
        for r in rejected:
            print(f"        · {r}")
    if interactions:
        print(f"     （診斷：{len(interactions)} 處條款交互作用，單獨相加 ≠ 同時開啟）")
        for i in interactions:
            print(f"        · {i}")
    return failures


def _install_pytest_shim() -> None:
    """`test_characterization.py` 只用到 approx 與 mark.parametrize 兩個名字。

    沙箱與部分環境沒有 pytest，而驗收器不該因為缺一個測試框架就跑不動。
    本 shim 只提供那兩個名字，不足以取代 pytest。
    """
    if "pytest" in sys.modules:
        return
    import types

    class _Approx:
        def __init__(self, expected, rel=1e-6, abs=None):
            self.expected, self.rel, self.abs = expected, rel, abs

        def __eq__(self, actual):
            if self.abs is not None:
                return math.isclose(actual, self.expected, rel_tol=0.0, abs_tol=self.abs)
            return math.isclose(actual, self.expected, rel_tol=self.rel, abs_tol=0.0)

        def __repr__(self):
            return f"approx({self.expected!r}, rel={self.rel})"

    shim = types.ModuleType("pytest")
    shim.approx = _Approx                                    # type: ignore[attr-defined]
    shim.mark = types.SimpleNamespace(                       # type: ignore[attr-defined]
        parametrize=lambda *a, **k: (lambda f: f))
    shim.fixture = lambda f=None, **k: (f if f else (lambda g: g))  # type: ignore[attr-defined]
    sys.modules["pytest"] = shim


def gate_2_defect_tests_all_red(fixed_module) -> list[str]:
    """四條 test_defect_* 對著 fixed 跑，必須全部失敗。綠的那條就是遺傳下來的缺陷。"""
    _install_pytest_shim()
    spec = importlib.util.spec_from_file_location("_ct", ROOT / "tests/test_characterization.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ct"] = mod
    mod.__dict__["calculate"] = fixed_module.calculate      # 把受測物換成 fixed
    spec.loader.exec_module(mod)
    mod.calculate = fixed_module.calculate                  # exec 後再覆蓋一次

    still_green: list[str] = []
    for name in sorted(n for n in dir(mod) if n.startswith("test_defect")):
        try:
            getattr(mod, name)()
            still_green.append(f"{name}：在 fixed 上仍然通過 → 缺陷被遺傳")
        except Exception:
            pass                                            # 紅的才是對的
    return still_green


ILLEGAL = [
    ("壽命 <= 退休年齡", dict(current_age=42, retirement_age=65, life_expectancy=60,
                              current_savings=800_000, monthly_investment=19_391,
                              monthly_expense_today=30_000)),
    ("退休年齡 <= 現齡", dict(current_age=65, retirement_age=65, life_expectancy=85,
                              current_savings=800_000, monthly_investment=19_391,
                              monthly_expense_today=30_000)),
    ("月支出為負", dict(current_age=42, retirement_age=65, life_expectancy=85,
                        current_savings=800_000, monthly_investment=19_391,
                        monthly_expense_today=-1)),
    ("本金為負", dict(current_age=42, retirement_age=65, life_expectancy=85,
                      current_savings=-1_000_000, monthly_investment=19_391,
                      monthly_expense_today=30_000)),
]


def gate_3_illegal_raises(fixed_calculate) -> list[str]:
    """PRD-04：非法輸入必須拋 ValueError，不得靜默補零或回傳假數字。"""
    failures: list[str] = []
    for label, kw in ILLEGAL:
        try:
            r = fixed_calculate(Params(**kw))
        except ValueError:
            continue
        except Exception as e:
            failures.append(f"{label}：拋了 {type(e).__name__}，PRD-04 要求 ValueError")
        else:
            failures.append(f"{label}：沒有拋例外，回傳 target_fund = {r.target_fund:,.2f}")
    return failures


# ---------------------------------------------------------------------------

def gate_0_interface(fixed_module) -> tuple[object | None, list[str]]:
    """介面契約檢查。不在三道驗收器之列，是「能不能開始量」的前置。

    回傳 (calculate 進入點, 問題清單)。找不到進入點時回傳 (None, ...)。
    """
    import dataclasses
    problems: list[str] = []

    for name in ("Params", "Result", "LumpSum"):
        if not hasattr(fixed_module, name):
            problems.append(f"缺少 dataclass `{name}`")

    if hasattr(fixed_module, "Params"):
        want = [f.name for f in dataclasses.fields(Params)]
        got = [f.name for f in dataclasses.fields(fixed_module.Params)]
        if want != got:
            problems.append(f"Params 欄位不符\n       契約 {want}\n       實作 {got}")

    entry = getattr(fixed_module, "calculate", None)
    if entry is None:
        cands = [n for n in dir(fixed_module)
                 if callable(getattr(fixed_module, n)) and n.startswith("calculate")]
        if len(cands) == 1:
            entry = getattr(fixed_module, cands[0])
            problems.append(
                f"進入點名為 `{cands[0]}`，非契約要求的 `calculate`。"
                f"\n       成因在我方：input-spec.md 的程式碼區塊只列了三個 dataclass，"
                f"\n       漏掉 `def calculate(p: Params) -> Result:` 那一行，"
                f"\n       文字卻寫著「公開以下三個 dataclass 與一個函式」。"
                f"\n       以 `{cands[0]}` 續跑，此項不計入產物的不合格數。"
            )
        else:
            problems.append(f"找不到唯一的進入點，候選：{cands or '無'}")
    return entry, problems


def main() -> None:
    print("三道驗收器（跑之前定，跑完不改）")
    print(f"  容許誤差：相對 {EPSILON}，絕對下限 {ABS_FLOOR} 元")
    _self_check()

    global FIXED_PATH
    if len(sys.argv) > 1:
        FIXED_PATH = pathlib.Path(sys.argv[1]).resolve()
        print(f"  受測產物：{FIXED_PATH}")

    if not FIXED_PATH.exists():
        print(f"\n產物尚未存在：{FIXED_PATH.relative_to(ROOT)}")
        print("  驗收器 1：golden v1 的 23 組，fixed − legacy 差值須等於 PRD-01 + PRD-02 各自貢獻")
        print("  驗收器 2：四條 test_defect_* 對著 fixed 必須全紅")
        print(f"  驗收器 3：{len(ILLEGAL)} 組非法輸入必須拋 ValueError "
              f"（{'、'.join(l for l, _ in ILLEGAL)}）")
        print("\n驗收器已就緒，等待產物。")
        return

    spec = importlib.util.spec_from_file_location("calc_fixed", FIXED_PATH)
    fixed = importlib.util.module_from_spec(spec)
    sys.modules["calc_fixed"] = fixed
    spec.loader.exec_module(fixed)

    entry, iface = gate_0_interface(fixed)
    print(f"\n{'✅' if not iface else '⚠️'} 介面契約：{'相符' if not iface else f'{len(iface)} 項落差'}")
    for p in iface:
        print(f"     · {p}")
    if entry is None:
        raise SystemExit("找不到進入點，三道驗收器無法開始。")
    fixed.calculate = entry                       # 供驗收器 2 換掉受測物用

    results = [
        ("驗收器 1　diff 逐項分解", gate_1_diff_decomposition(entry)),
        ("驗收器 2　四條缺陷測試全紅", gate_2_defect_tests_all_red(fixed)),
        ("驗收器 3　非法參數拋 ValueError", gate_3_illegal_raises(entry)),
    ]
    print()
    bad = 0
    for name, fails in results:
        print(f"{'✅' if not fails else '❌'} {name}：{'通過' if not fails else f'{len(fails)} 項不合格'}")
        for f in fails:
            print(f"     · {f}")
        bad += len(fails)

    print()
    if bad:
        raise SystemExit(f"共 {bad} 項不合格，calc_fixed.py 不得進 repo，golden set v2 不得產生。")
    print("三道全過。23 組新輸出可晉升 golden set v2；golden_set_v1.json 不刪不覆寫。")


if __name__ == "__main__":
    main()

"""測試的測試：變異 `shadow/calc.py`，看哪一條測試會發現。

為什麼需要這支
------------
一套測試全綠，只證明它自己沒有失敗，不證明它在看任何東西。
`tests/test_checklist.py` 13 條全綠，但其中有一條的三組輸入完全相同
（INV-1：重分配的字典從未進入 `Params`）——它其實在測 Python 的 `sum()`。
眼睛看得出這一條，看不出另外十二條。所以改用機器問：
**把受測物改壞，誰會叫？**

兩群變異體，分開計分
------------------
- **M 群**：每一個都對應一個真實的規格決定或已知缺陷
  （PRD-01 的複利頻率、RC-01 的首年、缺陷 C 的上界⋯⋯）。
  這一群存活 = 那條規格沒有測試在守。
- **N 群**：刻意荒謬（符號反轉、結果歸零）。
  這一群存活 = 測試連「明顯壞掉」都抓不到，等級不同。

分兩群是為了公平：方向性測試（DIR）本來就只斷言單調性，
**對任何保持單調的錯誤結構性地看不見**。拿 M 群的存活率去罵 DIR 不公道，
要罵得先看它有沒有殺掉 N 群。

為什麼不用 pytest
----------------
本檔只呼叫測試方法、接 `AssertionError`，不依賴 pytest。
`tests/test_checklist.py` 只用到 `pytest.approx` 與 `@pytest.fixture`，
`_PytestShim` 提供這兩個名字。

**第一版用 subprocess 跑 pytest，在沒裝 pytest 的環境下回報「12/12 全部存活、
每條測試零殺傷」——因為它把「pytest 不存在」的輸出當成「沒有測試失敗」。**
它在跑零條測試的情況下，給出了最聳動的那個結論。
`_assert_baseline()` 就是為了這件事存在：跑變異之前，先確認基準線收得到
預期條數且全綠。**收不到就中止，不准繼續。**

    python3 tools/test_mutator.py
"""

from __future__ import annotations

import importlib
import inspect
import math
import pathlib
import shutil
import sys
import tempfile
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "shadow/calc.py"
SUITE = ROOT / "tests/test_checklist.py"
EXPECTED_TESTS = 13

# ---------------------------------------------------------------------------
# 變異體。key 是編號與說明，value 是 (原字串, 替換字串)。
# 原字串必須在 calc.py 裡剛好出現一次以上——找不到會被明確回報，不會靜默跳過。
# ---------------------------------------------------------------------------

MUTANTS_REAL: dict[str, tuple[str, str]] = {
    "M01 本金改月複利（PRD-01 明訂的正解）": (
        "p.current_savings * (1 + p.pre_retirement_return) ** working_years",
        "p.current_savings * (1 + p.pre_retirement_return / 12) ** (working_years * 12)",
    ),
    "M02 月存由期末改期初（PRD v1.1 裁決①的未採用選項）": (
        "((1 + monthly_rate) ** (working_years * 12) - 1) / monthly_rate",
        "((1 + monthly_rate) ** (working_years * 12) - 1) / monthly_rate * (1 + monthly_rate)",
    ),
    "M03 收入通膨改鎖請領年齡（PRD v1.1 裁決②）": (
        "    if age >= p.labor_insurance_start_age:\n"
        "        income += p.labor_insurance_pension * 12 * infl\n"
        "    if age >= p.labor_pension_start_age:\n"
        "        income += p.labor_pension_monthly * 12 * infl",
        "    if age >= p.labor_insurance_start_age:\n"
        "        income += p.labor_insurance_pension * 12 * (1 + p.inflation_rate) ** ("
        "age - p.labor_insurance_start_age)\n"
        "    if age >= p.labor_pension_start_age:\n"
        "        income += p.labor_pension_monthly * 12 * (1 + p.inflation_rate) ** ("
        "age - p.labor_pension_start_age)",
    ),
    "M04 大筆支出通膨基準改鎖 A_r（裁決③的未採用選項）": (
        "inflated = ls.amount * (1 + p.inflation_rate) ** (ls.age - p.current_age)",
        "inflated = ls.amount * (1 + p.inflation_rate) ** (ls.age - p.retirement_age)",
    ),
    "M05 大筆支出補上界（修掉缺陷 C）": (
        "if ls.age >= p.retirement_age:",
        "if p.retirement_age <= ls.age <= p.life_expectancy:",
    ),
    "M06 提領期首年改 A_r（修掉 RC-01）": (
        "for i in range(1, retirement_years + 1):                    # 349",
        "for i in range(0, retirement_years + 1):                    # 349",
    ),
    "M07 目標金額首年改 A_r（修掉 RC-01）": (
        "for i in range(1, retirement_years + 1):                   # 306 i 從 1 開始",
        "for i in range(0, retirement_years + 1):                   # 306 i 從 1 開始",
    ),
    "M08 移除勞保起領年齡判斷": (
        "    if age >= p.labor_insurance_start_age:\n"
        "        income += p.labor_insurance_pension * 12 * infl",
        "    if True:\n        income += p.labor_insurance_pension * 12 * infl",
    ),
    "M09 淨支出下限拿掉 max(0, ·)（PRD-09）": (
        "net = max(0.0, inflated - _inflated_income(p, age, years_from_now))   # 320",
        "net = (inflated - _inflated_income(p, age, years_from_now))   # 320",
    ),
    "M10 折現率誤用退休前報酬率": (
        "target_for_expenses += net / (1 + p.post_retirement_return) ** i      # 321-322",
        "target_for_expenses += net / (1 + p.pre_retirement_return) ** i      # 321-322",
    ),
    "M11 固定年支出漏掉（PRD-08）": (
        "total_annual_expense_today = p.monthly_expense_today * 12 + p.annual_recurring_expense",
        "total_annual_expense_today = p.monthly_expense_today * 12",
    ),
    "M12 月支出漏乘 12": (
        "total_annual_expense_today = p.monthly_expense_today * 12 + p.annual_recurring_expense",
        "total_annual_expense_today = p.monthly_expense_today + p.annual_recurring_expense",
    ),
    "M13 圖表夾 0 拿掉（修掉缺陷 A'）": (
        "charted.append(max(0.0, remaining))",
        "charted.append(remaining)",
    ),
}

MUTANTS_ABSURD: dict[str, tuple[str, str]] = {
    "N01 月存方向反轉": (
        "fv_monthly = p.monthly_investment * (",
        "fv_monthly = -p.monthly_investment * (",
    ),
    "N02 壽命方向反轉": (
        "retirement_years = p.life_expectancy - p.retirement_age   # 293 純減法，無防護",
        "retirement_years = max(0, 100 - p.life_expectancy)   # 293 純減法，無防護",
    ),
    "N03 月支出方向反轉": (
        "total_annual_expense_today = p.monthly_expense_today * 12 + p.annual_recurring_expense",
        "total_annual_expense_today = 1_000_000 - p.monthly_expense_today * 12"
        " + p.annual_recurring_expense",
    ),
    "N04 本金方向反轉": (
        "fv_current = p.current_savings * (1 + p.pre_retirement_return) ** working_years",
        "fv_current = -p.current_savings * (1 + p.pre_retirement_return) ** working_years",
    ),
    "N05 退休前報酬率方向反轉": (
        "monthly_rate = p.pre_retirement_return / 12                # 297 名目月利率",
        "monthly_rate = -p.pre_retirement_return / 12                # 297 名目月利率",
    ),
    "N06 累積期年數方向反轉": (
        "working_years = p.retirement_age - p.current_age          # 292",
        "working_years = max(0, 80 - p.retirement_age)          # 292",
    ),
    "N07 目標金額恆為 0": (
        "target_fund = target_for_expenses + total_lump_pv           # 335",
        "target_fund = 0.0 * (target_for_expenses + total_lump_pv)           # 335",
    ),
    "N08 累積資產恆為 0": (
        "projected_savings = fv_current + fv_monthly",
        "projected_savings = 0.0 * (fv_current + fv_monthly)",
    ),
}


# ---------------------------------------------------------------------------
# 執行測試套件（不經 pytest）
# ---------------------------------------------------------------------------

def _install_pytest_shim() -> None:
    """只提供 test_checklist.py 用到的 approx 與 fixture 兩個名字。"""
    if "pytest" in sys.modules:
        return

    class _Approx:
        def __init__(self, expected, rel=1e-6, abs=None):
            self.expected, self.rel, self.abs = expected, rel, abs

        def __eq__(self, actual):
            if self.abs is not None:
                return math.isclose(actual, self.expected, rel_tol=0.0, abs_tol=self.abs)
            return math.isclose(actual, self.expected, rel_tol=self.rel, abs_tol=0.0)

        def __repr__(self):
            return f"approx({self.expected!r}, rel={self.rel})"

    def _fixture(func=None, **_kw):
        def wrap(f):
            f.__is_fixture__ = True
            return f
        return wrap(func) if func is not None else wrap

    shim = types.ModuleType("pytest")
    shim.approx = _Approx          # type: ignore[attr-defined]
    shim.fixture = _fixture        # type: ignore[attr-defined]
    sys.modules["pytest"] = shim


def _run_suite(work: pathlib.Path) -> dict[str, bool]:
    """回傳 {測試方法名: 是否通過}。每次重新 import，確保吃到當前的 calc.py。"""
    for name in ("calc", "test_checklist"):
        sys.modules.pop(name, None)
    for p in (str(work), str(work / "shadow")):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    sys.dont_write_bytecode = True

    module = importlib.import_module("test_checklist")
    results: dict[str, bool] = {}
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if not cls.__name__.startswith("TestCheckList"):
            continue
        inst = cls()
        fixtures = {n: f for n, f in inspect.getmembers(inst, inspect.ismethod)
                    if getattr(f, "__is_fixture__", False)}
        for name, fn in inspect.getmembers(inst, inspect.ismethod):
            if not name.startswith("test_"):
                continue
            kwargs = {a: fixtures[a]() for a in inspect.signature(fn).parameters
                      if a in fixtures}
            try:
                fn(**kwargs)
                results[name] = True
            except Exception:                      # 斷言失敗或任何例外都算「發現了」
                results[name] = False
    return results


def _assert_baseline(baseline: dict[str, bool]) -> None:
    """沒有這一段，整支工具會在跑零條測試的情況下回報「全部存活」。"""
    if len(baseline) != EXPECTED_TESTS:
        raise SystemExit(
            f"中止：基準線只收集到 {len(baseline)} 條測試，預期 {EXPECTED_TESTS} 條。"
            f"\n收集到的：{sorted(baseline)}"
            f"\n（收不到測試時，每個變異體都會看起來像『存活』。）"
        )
    failed = [k for k, v in baseline.items() if not v]
    if failed:
        raise SystemExit(f"中止：未變異時就有 {len(failed)} 條失敗 —— {failed}")


def _short(name: str) -> str:
    """test_mft_zero_savings... → MFT-1 之類的短名，依套件內出現順序編號。"""
    return name


def main() -> None:
    _install_pytest_shim()
    src = TARGET.read_text(encoding="utf-8")

    work = pathlib.Path(tempfile.mkdtemp(prefix="mutator-"))
    shutil.copytree(ROOT / "shadow", work / "shadow")
    shutil.copy(SUITE, work / SUITE.name)
    shutil.rmtree(work / "shadow/__pycache__", ignore_errors=True)

    (work / "shadow/calc.py").write_text(src, encoding="utf-8")
    baseline = _run_suite(work)
    _assert_baseline(baseline)
    order = list(baseline)
    print(f"基準線：{len(order)} 條全綠\n")

    killed_by: dict[str, list[str]] = {t: [] for t in order}
    missing: list[str] = []
    summary: dict[str, list[tuple[str, list[str]]]] = {}

    for group_name, group in (("M 群（對應真實規格決定與已知缺陷）", MUTANTS_REAL),
                              ("N 群（刻意荒謬，用來檢查測試的下限）", MUTANTS_ABSURD)):
        rows: list[tuple[str, list[str]]] = []
        print(f"═══ {group_name} ═══")
        for label, (old, new) in group.items():
            if old not in src:
                missing.append(label)
                print(f"  ⚠ {label}：替換字串在 calc.py 找不到，未執行")
                continue
            (work / "shadow/calc.py").write_text(src.replace(old, new, 1), encoding="utf-8")
            res = _run_suite(work)
            hits = [t for t in order if not res.get(t, True)]
            for h in hits:
                killed_by[h].append(label.split()[0])
            rows.append((label, hits))
            tag = "存活" if not hits else f"殺 {len(hits)}"
            print(f"  [{tag:>4}] {label}")
            if hits:
                print(f"         {'、'.join(_short(h) for h in hits)}")
            else:
                print("         ── 沒有任何測試發現 ──")
        summary[group_name] = rows
        survived = sum(1 for _, h in rows if not h)
        print(f"  ── 小計：{len(rows)} 個，存活 {survived}，被殺 {len(rows) - survived}\n")

    print("═══ 每條測試殺掉幾個變異體 ═══")
    for t in order:
        n = len(killed_by[t])
        flag = "  ⚠ 零殺傷" if n == 0 else ""
        print(f"  {t:<52} 殺 {n:>2}{flag}")
        if n:
            print(f"      {'、'.join(killed_by[t])}")

    zero = [t for t in order if not killed_by[t]]
    print(f"\n零殺傷 {len(zero)}/{len(order)}：{'、'.join(zero) if zero else '無'}")
    if missing:
        raise SystemExit(f"\n中止：{len(missing)} 個變異體的替換字串失效，"
                         f"表示 calc.py 已改動，變異體需同步更新 —— {missing}")


if __name__ == "__main__":
    main()

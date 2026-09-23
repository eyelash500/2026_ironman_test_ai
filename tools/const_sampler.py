"""從 pytest 腳本抽出「真的餵進去的數字」，量整數偏好與邊界命中。

要回答的問題
----------
一份測試看起來有很多案例，但那些案例挑的值長什麼樣？
年齡是不是全落在 30／60／65／85，金額是不是全是一萬的倍數，
邊界 ±1 有沒有人寫過。人眼數三份還行，數二十份就會數錯。

與 Day 12 `bva_checker.py` 的分工
-------------------------------
Day 12 檢核的是 test case（文件層，markdown 表格）；本檔處理的是 script（代碼層，
`ast`）。抽出來的案例字典格式**刻意與 `bva_checker` 相同**，邊界命中直接呼叫它，
不另寫一套判定——同一條尺量兩層，數字才可比。

怎麼分辨「輸入」與「期望值」
------------------------
`assert result.target_fund == 22938825.0` 裡的那個數字是期望值，不是輸入；
把它算進「金額的分佈」會得到一堆七位數，結論整個歪掉。判別規則寫死兩條：

1. 落在 `ast.Assert` 節點底下的數值 → **期望值**，排除。
2. 被綁在「已知欄位名」的關鍵字引數上的數值 → **輸入**，不管呼叫的是
   `Params(...)`、`_p(...)` 還是 `dict(...)`。只認欄位名，不認函式名——
   產物幾乎都會包一層自己的 helper，認函式名會整批漏掉。

兩條都不符的算 **其他**，照實報數量，不塞進任何一群。

基準情境的老問題
--------------
產物常寫成 `get_valid_params(retirement_age=65)`，呼叫點只看得到一個欄位，
其餘來自 helper 的預設值。Day 12 的 `case_extractor.py` 在文件層撞過同一件事
（「同上」「其餘同 baseline」），到了代碼層它換個樣子又出現一次。
本檔的處理：把欄位數最多的那一處當基準情境，併入欄位較少的案例，
**並且把這個動作印出來**——它是推論，不是讀到的事實。

    python3 tools/const_sampler.py <測試檔 ...>
    python3 tools/const_sampler.py --self-test
"""

from __future__ import annotations

import ast
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bva_checker import check_bva  # noqa: E402

# 欄位 → (符號, 類別)。符號沿用 PRD 的寫法，沒有符號的就用欄位名。
FIELDS: dict[str, tuple[str, str]] = {
    "current_age": ("A_c", "年齡"),
    "retirement_age": ("A_r", "年齡"),
    "life_expectancy": ("A_d", "年齡"),
    "labor_insurance_start_age": ("A_p_ins", "年齡"),
    "labor_pension_start_age": ("A_p_pen", "年齡"),
    "age": ("A_e", "年齡"),                       # LumpSum.age
    "current_savings": ("current_savings", "金額"),
    "monthly_investment": ("monthly_investment", "金額"),
    "monthly_expense_today": ("monthly_expense_today", "金額"),
    "annual_recurring_expense": ("annual_recurring_expense", "金額"),
    "labor_insurance_pension": ("labor_insurance_pension", "金額"),
    "labor_pension_monthly": ("labor_pension_monthly", "金額"),
    "other_income": ("other_income", "金額"),
    "amount": ("amount", "金額"),                 # LumpSum.amount
    "pre_retirement_return": ("r", "比率"),
    "post_retirement_return": ("r_p", "比率"),
    "inflation_rate": ("i", "比率"),
}

# PRD 的邊界。(約束, step)
CONSTRAINTS: list[tuple[tuple[str, str, str | float], float]] = [
    (("A_c", "<", "A_r"), 1.0),          # PRD-04
    (("A_r", "<", "A_d"), 1.0),          # PRD-04
    (("A_e", ">=", "A_r"), 1.0),         # PRD-05 下界
    (("A_e", "<=", "A_d"), 1.0),         # PRD-05 上界
    (("r", ">=", 0.0), 0.01),            # PRD-01：r = 0 退化
    (("i", ">=", 0.0), 0.01),            # PRD-02／05／08／10
]


def _number(node: ast.AST) -> float | None:
    """取數值，處理 `-1` 這種 UnaryOp 包一層的寫法。bool 不算數字。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _number(node.operand)
        return None if inner is None else -inner
    return None


def _mark_assert_subtrees(tree: ast.AST) -> set[int]:
    """回傳所有位於 assert 底下的節點 id。那些數值是期望值。"""
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            for sub in ast.walk(node):
                inside.add(id(sub))
    return inside


def extract(source: str) -> dict:
    """抽出案例與三群數值。回傳 dict，不印東西。"""
    tree = ast.parse(source)
    in_assert = _mark_assert_subtrees(tree)

    cases: list[dict[str, float]] = []
    by_kind: dict[str, list[float]] = {"年齡": [], "金額": [], "比率": []}
    expected = other = 0

    seen: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        case: dict[str, float] = {}
        for kw in node.keywords:
            if kw.arg not in FIELDS:
                continue
            val = _number(kw.value)
            if val is None:
                continue
            seen.add(id(kw.value))
            if id(kw.value) in in_assert:
                expected += 1
                continue
            symbol, kind = FIELDS[kw.arg]
            case[symbol] = val
            by_kind[kind].append(val)
        if case:
            cases.append(case)

    for node in ast.walk(tree):
        if _number(node) is None or id(node) in seen:
            continue
        if isinstance(node, ast.UnaryOp):       # 內層 Constant 會另外被走到
            continue
        expected += 1 if id(node) in in_assert else 0
        other += 0 if id(node) in in_assert else 1

    baseline, merged = _merge_baseline(cases)
    return {
        "cases": cases,
        "baseline": baseline,
        "merged": merged,
        "by_kind": by_kind,
        "expected": expected,
        "other": other,
    }


def extract_json(text: str) -> dict:
    """golden set 的版本：輸入與期望值本來就分在兩個 key 底下。

    對照組要用 `golden/golden_set_v2.json`，而它是 JSON 不是 script——
    案例的 `input` 與 `expected` 天生分開，不必靠 `ast` 猜哪個數字是輸入。
    腳本沒有這條分界線，那正是上面那兩條判別規則存在的理由。
    """
    import json

    doc = json.loads(text)
    cases: list[dict[str, float]] = []
    by_kind: dict[str, list[float]] = {"年齡": [], "金額": [], "比率": []}
    expected = 0

    for item in doc.get("cases", []):
        case: dict[str, float] = {}
        for key, val in (item.get("input") or {}).items():
            if key == "lump_sums":
                for ls in val or ():
                    for k2, v2 in ls.items():
                        if k2 in FIELDS:
                            symbol, kind = FIELDS[k2]
                            case[symbol] = float(v2)
                            by_kind[kind].append(float(v2))
                continue
            if key in FIELDS and isinstance(val, (int, float)) and not isinstance(val, bool):
                symbol, kind = FIELDS[key]
                case[symbol] = float(val)
                by_kind[kind].append(float(val))
        expected += sum(1 for v in (item.get("expected") or {}).values()
                        if isinstance(v, (int, float)))
        if case:
            cases.append(case)

    return {"cases": cases, "baseline": {}, "merged": 0,
            "by_kind": by_kind, "expected": expected, "other": 0}


def _merge_baseline(cases: list[dict[str, float]]) -> tuple[dict[str, float], int]:
    """把欄位最多的那一處當基準情境，補進欄位較少的案例。

    這是推論，不是讀到的事實——所以回傳它，由呼叫端印出來給人看。
    """
    if not cases:
        return {}, 0
    baseline = max(cases, key=len)
    if len(baseline) < 3:                        # 太少就不當基準，寧可不補
        return {}, 0
    merged = 0
    for case in cases:
        if case is baseline:
            continue
        missing = {k: v for k, v in baseline.items() if k not in case}
        if missing:
            case.update(missing)
            merged += 1
    return baseline, merged


def roundness(values: list[float], kind: str) -> dict:
    """整數偏好：各類別有各自的『整』的定義。"""
    if not values:
        return {"n": 0}
    if kind == "年齡":
        hit = sum(1 for v in values if v % 5 == 0)
        label = "5 的倍數"
    elif kind == "金額":
        hit = sum(1 for v in values if v != 0 and v % 10000 == 0)
        label = "一萬的倍數（0 不計）"
    else:
        hit = sum(1 for v in values if abs(round(v * 100) - v * 100) < 1e-9)
        label = "0.01 的整數倍"
    return {"n": len(values), "hit": hit, "ratio": hit / len(values),
            "label": label, "top": Counter(values).most_common(5)}


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def report(name: str, data: dict) -> None:
    print(f"\n── {name} ──")
    n_const = sum(len(v) for v in data["by_kind"].values())
    print(f"輸入數值 {n_const}｜期望值（assert 底下）{data['expected']}｜其他 {data['other']}")
    print(f"案例 {len(data['cases'])} 組")
    if data["baseline"]:
        print(f"  基準情境：{len(data['baseline'])} 個欄位，併入 {data['merged']} 組案例（推論，非讀到的事實）")

    for kind, values in data["by_kind"].items():
        r = roundness(values, kind)
        if not r["n"]:
            print(f"  {kind}：無")
            continue
        top = "、".join(f"{_fmt(v)}×{c}" for v, c in r["top"])
        print(f"  {kind}：{r['n']} 個，{r['hit']} / {r['n']} = {r['ratio']:.0%} 是 {r['label']}")
        print(f"        最常出現：{top}")

    print("  邊界命中：")
    for constraint, step in CONSTRAINTS:
        out = check_bva(constraint, data["cases"], step=step)
        lhs, op, rhs = constraint
        miss = "、".join(out["missing"]) if out["missing"] else "無"
        print(f"    {lhs} {op} {rhs}　{out['score']:.0%}　缺 {miss}")


def audit(paths: list[str]) -> int:
    total = 0
    for path in paths:
        text = open(path, encoding="utf-8").read()
        data = extract_json(text) if path.endswith(".json") else extract(text)
        total += sum(len(v) for v in data["by_kind"].values())
        report(os.path.basename(path), data)
    if total == 0:
        raise SystemExit(
            "\n中止：所有檔案加起來抽到 0 個輸入數值。"
            "\n不是『這些測試都不用數字』，是抽取規則沒對上它們的寫法——"
            "\n這種時候印出『整數偏好 0%』比不印更糟。")
    return 0


def _kat() -> None:
    """人手寫、答案確鑿。遞迴懷疑停在這一層。"""

    # 1) assert 右邊的數字不算輸入
    src = ("from calc_fixed import Params, calculate\n"
           "def test_x():\n"
           "    p = Params(current_age=30, retirement_age=65, life_expectancy=85)\n"
           "    assert calculate(p).target_fund == 22938825.0\n")
    d = extract(src)
    assert d["by_kind"]["年齡"] == [30.0, 65.0, 85.0], d["by_kind"]
    assert d["by_kind"]["金額"] == [], d["by_kind"]
    assert d["expected"] == 1, d["expected"]

    # 2) 認欄位名，不認函式名——helper 包一層也要抓到
    src = ("def test_y():\n"
           "    p = _p(current_age=40, retirement_age=65, life_expectancy=85)\n"
           "    q = _p(current_age=41)\n")
    d = extract(src)
    assert len(d["cases"]) == 2, d["cases"]
    assert d["cases"][1]["A_c"] == 41.0 and d["cases"][1]["A_d"] == 85.0, "基準情境沒併進來"
    assert d["merged"] == 1, d["merged"]

    # 3) 負數要抓得到（UnaryOp 包一層）
    d = extract("def t():\n    p = Params(current_savings=-1.0)\n")
    assert d["by_kind"]["金額"] == [-1.0], d["by_kind"]

    # 4) 整數偏好：年齡看 5 的倍數
    r = roundness([30.0, 65.0, 85.0, 41.0], "年齡")
    assert r["hit"] == 3 and abs(r["ratio"] - 0.75) < 1e-9, r

    # 5) 金額的 0 不算「一萬的倍數」——否則一堆預設 0 會把比例灌到 100%
    r = roundness([0.0, 10000.0], "金額")
    assert r["hit"] == 1, r

    # 6) 邊界命中沿用 bva_checker，同一條尺
    cases = [{"A_e": 84, "A_d": 85}, {"A_e": 85, "A_d": 85}, {"A_e": 86, "A_d": 85}]
    assert check_bva(("A_e", "<=", "A_d"), cases)["pass"]

    # 7) JSON 版：input／expected 天生分開，期望值不得混進輸入
    d = extract_json('{"cases": [{"input": {"current_age": 30, "lump_sums": '
                     '[{"age": 70, "amount": 500000}]}, '
                     '"expected": {"target_fund": 123.0}}]}')
    assert d["by_kind"]["年齡"] == [30.0, 70.0], d["by_kind"]
    assert d["by_kind"]["金額"] == [500000.0] and d["expected"] == 1, d

    # 8) 空檔案不得回報任何比例
    d = extract("x = 1\n")
    assert sum(len(v) for v in d["by_kind"].values()) == 0, d["by_kind"]

    print("KAT 全部通過（8 組）")


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        _kat()
        return 0
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if not paths:
        raise SystemExit("用法：const_sampler.py <測試檔 ...>　｜　const_sampler.py --self-test")
    _kat()
    return audit(paths)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

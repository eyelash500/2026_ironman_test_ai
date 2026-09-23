"""斷言審計器：用 `ast` 問一句「這條測試到底在比什麼？」

為什麼需要這支
------------
pytest 的 PASS 只代表函式沒有拋例外。一條測試把預期值寫成
`assert result is not None`，跑起來跟真的在比數字一模一樣綠。
Day 14 的 `test_mutator.py` 是事後問「改壞了誰會叫」，本檔是事前問
「你寫下來的斷言，有沒有在約束任何一個金額」。

分類不是二分，是八類
------------------
`strict` 之外還要分開記，因為它們的成因不同、處置也不同：

- `strict`     等式、`isclose`／`approx`、**同一個值被上下夾住**
- `contract`   `with pytest.raises(...)`：沒有 assert 但確實在驗約定
- `relational` `a.target_fund < b.target_fund`：**兩邊都是算出來的**，
               單調性與蛻變關係的正確形狀，不是放水
- `flag`       `assert found_loop`：真正的檢查在斷言之前，本檔看不到，
               判定是「無法判定」而不是「不合格」
- `weak`       單邊不等式與 `!=`，且另一邊是**寫死的常數**——弱化模式的本體
- `vacuum`     `is not None`、裸真值物件、`isinstance`、`len(x) > 0`
- `structural` `len(x) == 21` 這種：有等號，但主體不是金額
- `blurry`     `int(v) == 14903594`、`round(v, -6) == 15000000`

`relational` 與 `flag` 是第一版沒有的
---------------------------------
第一版只分六類，掃出來 `test_checklist.py` 四條單調性測試被判 `weak`、
`test_spec_recovery.py` 十一條 AST 考古測試被判 `vacuum`，全部進 `VACUUM_ONLY`。
那是量尺的錯：**單調性斷言必須拿兩個結果互比，本來就不會出現常數**；
而把邏輯寫在斷言之前的測試，檢核器沒有資格說它是假的。
Day 14 自己寫過「方向性測試對任何保持單調的錯誤結構性地看不見，
拿 M 群存活率罵它不公道」——第一版把同一個錯又犯了一次。

`fidelity_ratio` 的分母只含「該拿數字去比的斷言」
--------------------------------------------
分母 = `strict + weak + vacuum + blurry`。
`contract`（驗約定）、`relational`（驗關係）、`structural`（驗形狀）、
`flag`（驗不到）四類都不進分母——它們不是在回答「金額對不對」這個問題，
放進去只會讓比值失去意義。

判定以函式為單位，不以檔案為單位
----------------------------
檔案層的 `total_asserts > 0` 擋不住灌水：二十條測試裡五條是空的，
總數依然大於零。每條函式給一個判定：

- `EMPTY`        一條斷言都沒有，pytest 照樣綠
- `SKIPPED`      一條斷言都沒有，但整條函式被 `skip` 宣告掉——pytest 報的是
                 SKIPPED 而不是綠。2026-09-23 修正，見下方〈為什麼要拆出 SKIPPED〉
- `OK`           至少有一條 `strict`／`contract`／`relational`
- `OPAQUE`       只有 `flag`：邏輯在斷言之前，本檔無法判定
- `VACUUM_ONLY`  其餘——有寫斷言，但沒有一條在約束任何東西

為什麼要拆出 SKIPPED（2026-09-23 修正）
-----------------------------------
初版把「沒有任何斷言」一律判 `EMPTY`，訊息寫「pytest 照樣綠」。
**那句話對被 `skip` 宣告掉的函式是假的**——pytest 報的是 SKIPPED，
獨立一欄，帶著 reason 字串，不會混進 passed 裡。

這個錯能活到今天，是因為 repo 裡九個測試檔、Day 21 三份產物，
用到 `skip` 的是零。沒有任何輸入逼模型說過「我不知道」。
Day 22 把規格降到一句話之後，產物開始大量宣告規格缺口，
這條路徑才第一次被走到——**實驗的自變數本身揭開了量具的缺陷**。

判別三分，界線畫在「pytest 到底報什麼」：

- 有 `@pytest.mark.skip`／`skipif`，或函式本體第一句就是 `pytest.skip(...)`
  → `SKIPPED`。pytest 必定報 SKIPPED，不計入閘門 3 失敗。
- `pytest.skip()` 藏在 `if`／`except` 裡 → 仍判 `EMPTY`。
  條件不成立時它真的會變綠，**工具不猜**。
- 其餘（本體只有 `pass` 或 docstring）→ `EMPTY`，照舊。

忠實性門檻 0.8 與 `VACUUM_ONLY` 一個字都沒動。
那兩個沒有第一性原理支撐，動它們就是調參。
本次修正只改一處，而且這條規則不看任何一份產物也寫得出來：
**pytest 報成 SKIPPED 的函式，不是靜默變綠的函式。**

既有檔案無一使用 `skip`，故本次修正不改動任何已發表的數字。

誰驗收這支
---------
檔尾 `_self_check()` 的 KAT 是人先寫下答案、再讓程式去對的：
斷言分類與 5 種函式判定，全部手寫預期分類。不符即 `SystemExit`。
另外掃描目標若解析到零條測試函式，本檔拒絕印出任何比值——
Day 14 那次「跑零條測試卻回報最聳動結論」不可以再發生一次。

    python3 tools/assert_inspector.py tests/test_checklist.py
    python3 tools/assert_inspector.py tests/            # 目錄
    python3 tools/assert_inspector.py                   # 只跑 KAT
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── 閘門 3（門檻層）自訂值，非實證得出 ───────────────────────────
FIDELITY_THRESHOLD = 0.8

STRICT_CALLS = ("isclose", "approx")
VACUUM_CALLS = ("isinstance", "hasattr", "callable", "bool")
STRUCTURAL_CALLS = ("len", "type", "sorted", "list", "tuple", "set", "dict", "str", "repr")
BLURRY_CALLS = ("int", "round", "trunc", "floor", "ceil")

ASC = (ast.Lt, ast.LtE)
DESC = (ast.Gt, ast.GtE)


@dataclass
class Finding:
    """一條斷言（或一個 raises 區塊）的判定結果。"""

    line: int
    kind: str          # strict / contract / relational / flag / weak / vacuum / structural / blurry
    expr: str

    @property
    def counts_in_ratio(self) -> bool:
        """只有「該拿數字去比」的斷言進分母。"""
        return self.kind in ("strict", "weak", "vacuum", "blurry")

    @property
    def is_binding(self) -> bool:
        """有實質約束力：行為變了，這條斷言會叫。

        `structural` 與 `blurry` 也算——`len(x) == 21` 與 `int(v) == 14903594`
        都會因為行為改變而失敗，它們是**忠實度**問題，不是「什麼都沒驗」。
        `weak` 與 `vacuum` 不算：單邊門檻與存在性檢查，幾乎任何行為都過。
        """
        return self.kind in ("strict", "contract", "relational", "structural", "blurry")


@dataclass
class FunctionReport:
    name: str
    line: int
    findings: list[Finding] = field(default_factory=list)
    skip: str = ""          # "declared"｜"conditional"｜""

    @property
    def verdict(self) -> str:
        if not self.findings:
            return "SKIPPED" if self.skip == "declared" else "EMPTY"
        if any(f.is_binding for f in self.findings):
            return "OK"
        if any(f.kind == "flag" for f in self.findings):
            return "OPAQUE"
        return "VACUUM_ONLY"


def _call_name(node: ast.AST) -> str:
    return ast.unparse(node.func) if isinstance(node, ast.Call) else ""


def _contains_call(node: ast.AST, names: tuple[str, ...]) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and any(n in _call_name(sub) for n in names):
            return True
    return False


def _subject(cmp_node: ast.Compare) -> ast.expr:
    """單邊比較裡「被比的那一側」：常數在左就取右，否則取左。"""
    if isinstance(cmp_node.left, ast.Constant) and cmp_node.comparators:
        return cmp_node.comparators[0]
    return cmp_node.left


def _is_bounded_chain(cmp_node: ast.Compare) -> bool:
    """`a <= x <= b`：兩個運算子、方向一致，中間那個才是主體。"""
    ops = cmp_node.ops
    if len(ops) != 2:
        return False
    return all(isinstance(o, ASC) for o in ops) or all(isinstance(o, DESC) for o in ops)


def _is_bounded_pair(bool_node: ast.BoolOp) -> bool:
    """`x >= 100 and x <= 200`：**同一個主體**被兩個相反方向夾住。

    `x > 0 and y > 0` 不算——那是兩個不同主體各一個單邊不等式，
    是「弱化不等式」做了兩次，不是一個封閉區間。
    """
    if not isinstance(bool_node.op, ast.And) or len(bool_node.values) != 2:
        return False
    left, right = bool_node.values
    if not (isinstance(left, ast.Compare) and isinstance(right, ast.Compare)):
        return False
    if len(left.ops) != 1 or len(right.ops) != 1:
        return False
    if ast.unparse(_subject(left)) != ast.unparse(_subject(right)):
        return False
    dirs = {isinstance(left.ops[0], ASC), isinstance(right.ops[0], ASC)}
    return dirs == {True, False}


def _is_literal(node: ast.expr) -> bool:
    """寫死的常數：`0`、`-1`、`1e-6`。用來分開「弱化」與「關係」。"""
    if isinstance(node, ast.Constant):
        return True
    return isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant)


def _bool_names(fn: ast.FunctionDef) -> frozenset[str]:
    """函式內「值是自己算出來的旗標或集合」的區域變數名。

    `found_loop = False`、`ok = a == b`、`hit = any(...)`、
    `mismatches = []`（之後在迴圈裡 append）、`orphans = [t for t in ...]` 都算——
    這些名字後面的 `assert found_loop` 或 `assert not mismatches`，
    真正的檢查在斷言之前就做完了，本檔只看得到最後那一行。

    `result = calculate(p)` 不算——那是物件，`assert result` 仍是真空。
    """
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        boolish = (
            isinstance(value, (ast.Compare, ast.BoolOp))
            or (isinstance(value, ast.Constant) and isinstance(value.value, bool))
            or (isinstance(value, ast.Call)
                and any(n in _call_name(value) for n in ("any", "all", "isinstance")))
        )
        derived = (
            isinstance(value, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
            or (isinstance(value, (ast.List, ast.Set, ast.Dict)) and not getattr(value, "elts", None))
            or (isinstance(value, ast.Call)
                and _call_name(value) in ("list", "set", "dict", "sorted", "filter"))
        )
        if not (boolish or derived):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for t in targets:
            if isinstance(t, ast.Name):
                names.add(t.id)
    return frozenset(names)


def classify(test: ast.expr, bool_names: frozenset[str] = frozenset()) -> str:
    """一條 `assert` 的判定。順序有意義：先排除假的，再認真的。"""
    # 裸真值：`assert found_loop` 是旗標（邏輯在前面），`assert result` 是真空
    if isinstance(test, ast.Name):
        return "flag" if test.id in bool_names else "vacuum"
    if isinstance(test, ast.UnaryOp):
        inner = test.operand
        if isinstance(inner, ast.Name) and inner.id in bool_names:
            return "flag"
        if isinstance(inner, (ast.Call, ast.Compare)):
            return classify(inner, bool_names)      # `not any(...)` 同 `any(...)`
        return "vacuum"
    if isinstance(test, ast.Attribute):
        return "vacuum"

    if isinstance(test, ast.Call):
        name = _call_name(test)
        if any(n in name for n in STRICT_CALLS):
            return "strict"
        if name in ("any", "all"):
            # `any('upper_bound' in c for c in clauses)`：驗的是內容有沒有出現，
            # 不是金額對不對——形狀類，進不了忠實性分母
            return "structural"
        if any(name.endswith(n) or name == n for n in VACUUM_CALLS):
            return "vacuum"
        return "vacuum"          # 其他裸呼叫：驗的是它自己不拋錯

    if isinstance(test, ast.BoolOp):
        if _is_bounded_pair(test):
            return "strict"
        # 逐項看，取最寬鬆的那一項代表整條
        kinds = [classify(v, bool_names) for v in test.values]
        for weakest in ("vacuum", "flag", "weak", "blurry", "structural",
                        "relational", "strict"):
            if weakest in kinds:
                return weakest
        return "vacuum"

    if isinstance(test, ast.Compare):
        ops = test.ops
        if any(isinstance(o, (ast.Is, ast.IsNot)) for o in ops):
            # `x is True` / `x is False` 是對布林結果的精確比對，與 `== True` 等價；
            # `x is None` / `is not None` 才是存在性檢查。
            if all(isinstance(c, ast.Constant) and isinstance(c.value, bool)
                   for c in test.comparators):
                return "strict"
            return "vacuum"
        if any(isinstance(o, (ast.In, ast.NotIn)) for o in ops):
            return "structural"
        if _is_bounded_chain(test):
            return "strict"
        if any(isinstance(o, ast.Eq) for o in ops):
            if _contains_call(test, BLURRY_CALLS):
                return "blurry"
            if _contains_call(_subject(test), STRUCTURAL_CALLS):
                return "structural"
            return "strict"
        if any(isinstance(o, ast.NotEq) for o in ops):
            return "weak"
        # 剩下的是單邊不等式，分三種：
        if _contains_call(_subject(test), STRUCTURAL_CALLS):
            return "vacuum"          # `len(x) > 0`：什麼都沒保證
        if _is_literal(test.left) or any(_is_literal(c) for c in test.comparators):
            return "weak"            # `r.savings > 0`：門檻是寫死的常數
        return "relational"          # `a.fund < b.fund`：兩邊都是算出來的

    return "vacuum"


class _FunctionScanner(ast.NodeVisitor):
    """只收集**這個函式自己**的斷言，不含嵌套的內層函式。"""

    def __init__(self, bool_names: frozenset[str] = frozenset()) -> None:
        self.findings: list[Finding] = []
        self.bool_names = bool_names

    def visit_Assert(self, node: ast.Assert) -> None:
        self.findings.append(
            Finding(
                line=node.lineno,
                kind=classify(node.test, self.bool_names),
                expr=ast.unparse(node.test),
            )
        )

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            expr = item.context_expr
            if isinstance(expr, ast.Call) and "raises" in _call_name(expr):
                self.findings.append(
                    Finding(line=node.lineno, kind="contract", expr=ast.unparse(expr))
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return  # 內層函式不併入外層


def _skip_kind(node: ast.FunctionDef) -> str:
    """回傳 "declared"／"conditional"／""。界線是「pytest 必定報 SKIPPED 嗎」。"""
    for d in node.decorator_list:
        if "pytest.mark.skip" in ast.unparse(d):
            return "declared"
    body = [s for s in node.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call) \
            and "pytest.skip" in _call_name(body[0].value):
        return "declared"
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and "pytest.skip" in _call_name(sub):
            return "conditional"
    return ""


def _scan_function(node: ast.FunctionDef) -> FunctionReport:
    scanner = _FunctionScanner(_bool_names(node))
    for stmt in node.body:
        scanner.visit(stmt)
    return FunctionReport(name=node.name, line=node.lineno,
                          findings=scanner.findings, skip=_skip_kind(node))


@dataclass
class FileReport:
    path: str
    functions: list[FunctionReport]

    def tally(self) -> dict[str, int]:
        out = dict.fromkeys(
            ("strict", "contract", "relational", "flag",
             "weak", "vacuum", "structural", "blurry"), 0
        )
        for fn in self.functions:
            for f in fn.findings:
                out[f.kind] += 1
        return out

    @property
    def denominator(self) -> int:
        return sum(1 for fn in self.functions for f in fn.findings if f.counts_in_ratio)

    @property
    def fidelity_ratio(self) -> float | None:
        """分母為零時回傳 None，不回傳 0.0——「沒有可比的斷言」與
        「一條都不嚴格」是兩件不同的事，混在一起就是在報一個假的分數。"""
        return None if self.denominator == 0 else self.tally()["strict"] / self.denominator

    @property
    def empty(self) -> list[FunctionReport]:
        return [f for f in self.functions if f.verdict == "EMPTY"]

    @property
    def vacuum_only(self) -> list[FunctionReport]:
        return [f for f in self.functions if f.verdict == "VACUUM_ONLY"]

    @property
    def skipped(self) -> list[FunctionReport]:
        """宣告式跳過——不計入不合格，但必須列出來讓人去看它宣告了什麼。"""
        return [f for f in self.functions if f.verdict == "SKIPPED"]

    @property
    def opaque(self) -> list[FunctionReport]:
        """無法判定——不計入不合格，但必須列出來讓人去看。"""
        return [f for f in self.functions if f.verdict == "OPAQUE"]

    @property
    def passed(self) -> bool:
        ratio = self.fidelity_ratio
        return (
            ratio is not None
            and ratio >= FIDELITY_THRESHOLD
            and not self.empty
            and not self.vacuum_only
        )


def audit_source(source: str, path: str = "<memory>") -> FileReport:
    tree = ast.parse(source, filename=path)
    funcs = [
        _scan_function(n)
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test")
    ]
    return FileReport(path=path, functions=funcs)


def audit_file(path: str | Path) -> FileReport:
    p = Path(path)
    return audit_source(p.read_text(encoding="utf-8"), str(p))


def report(fr: FileReport) -> None:
    t = fr.tally()
    ratio = fr.fidelity_ratio
    shown = "n/a（無可比斷言）" if ratio is None else f"{ratio:.0%}"
    print(f"\n{fr.path}")
    print(f"  測試函式 {len(fr.functions)} 條｜忠實性 {shown}"
          f"｜閘門 3 {'PASS' if fr.passed else 'FAIL'}")
    print("  " + "｜".join(f"{k} {v}" for k, v in t.items() if v))
    for fn in fr.empty:
        print(f"  ✗ EMPTY        {fn.name}（第 {fn.line} 行）什麼都沒驗，pytest 照樣綠")
    for fn in fr.vacuum_only:
        kinds = "、".join(sorted({f.kind for f in fn.findings}))
        print(f"  ✗ VACUUM_ONLY  {fn.name}（第 {fn.line} 行）只有 {kinds}，沒有一條在比數字")
    for fn in fr.skipped:
        print(f"  − SKIPPED      {fn.name}（第 {fn.line} 行）以 skip 宣告跳過，pytest 不報綠")
    for fn in fr.opaque:
        print(f"  ? OPAQUE       {fn.name}（第 {fn.line} 行）邏輯在斷言之前，本檔無法判定")


# ── KAT：人先寫答案，程式再去對 ─────────────────────────────────

_KAT_SOURCE = '''
import math
import pytest

def test_k01_eq():            assert r.projected_savings == 22938825
def test_k02_approx():        assert r.projected_savings == pytest.approx(22938825, rel=1e-9)
def test_k03_isclose():       assert math.isclose(r.ratio, 0.667)
def test_k04_chain():         assert 0 <= r.ratio <= 1
def test_k05_pair_same():     assert r.x >= 100 and r.x <= 200
def test_k06_pair_diff():     assert r.x > 0 and r.y > 0
def test_k07_single():        assert r.projected_savings > 0
def test_k08_noteq():         assert r.projected_savings != 0
def test_k09_notnone():       assert r is not None
def test_k10_truthy():        assert r
def test_k11_isinstance():    assert isinstance(r, Result)
def test_k12_len_gt():        assert len(r.balances_raw) > 0
def test_k13_len_eq():        assert len(r.balances_raw) == 21
def test_k14_int_trunc():     assert int(r.projected_savings) == 14903594
def test_k15_round_neg():     assert round(r.projected_savings, -6) == 15000000

def test_k16_raises():
    with pytest.raises(ValueError):
        calculate(bad_params)

def test_k17_empty():
    result = calculate(p)

def test_k21_any_content():   assert any('upper_bound' in c for c in r05.clauses)
def test_k22_not_any():       assert not any('upper_bound' in c for c in mutated.clauses)

def test_k23_is_true():
    result = check_bva(rule, cases)
    assert result['pass'] is True

def test_k24_is_none():
    assert inflated_func is None

def test_k25_empty_collection():
    mismatches = []
    for case in cases:
        mismatches.append(case)
    assert not mismatches

def test_k26_comprehension():
    orphans = [t for t in tests if t not in mapped]
    assert not orphans

def test_k18_relational():
    a = calculate(p_low)
    b = calculate(p_high)
    assert a.target_fund < b.target_fund

def test_k19_flag():
    found_loop = False
    for node in walk(tree):
        found_loop = True
    assert found_loop

def test_k20_object_truthy():
    result = calculate(p)
    assert result

@pytest.mark.skip(reason="PRD-11 是介面標示需求，計算核心無對應欄位可測")
def test_k27_decorator_skip():
    pass


def test_k28_body_skip():
    """規格未定義具體計算公式，無法進行數值驗證"""
    pytest.skip("規格未定義月／年複利與期初／期末投入，無法斷言數值")


def test_k29_conditional_skip():
    try:
        res = calculate(p)
    except Exception as e:
        pytest.skip(f"實作拋出例外，規格未定義錯誤處理: {e}")
    assert res is not None


def test_k30_skip_but_has_assert():
    p = Params(current_age=30)
    pytest.skip("這條其實跳過了，但底下仍寫了一條嚴格斷言")
    assert p.current_age == 30
'''

# (函式名, 預期分類序列, 預期函式判定)
_KAT_EXPECTED: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("test_k01_eq",         ("strict",),     "OK"),
    ("test_k02_approx",     ("strict",),     "OK"),
    ("test_k03_isclose",    ("strict",),     "OK"),
    ("test_k04_chain",      ("strict",),     "OK"),
    ("test_k05_pair_same",  ("strict",),     "OK"),
    ("test_k06_pair_diff",  ("weak",),       "VACUUM_ONLY"),
    ("test_k07_single",     ("weak",),       "VACUUM_ONLY"),
    ("test_k08_noteq",      ("weak",),       "VACUUM_ONLY"),
    ("test_k09_notnone",    ("vacuum",),     "VACUUM_ONLY"),
    ("test_k10_truthy",     ("vacuum",),     "VACUUM_ONLY"),
    ("test_k11_isinstance", ("vacuum",),     "VACUUM_ONLY"),
    ("test_k12_len_gt",     ("vacuum",),     "VACUUM_ONLY"),
    ("test_k13_len_eq",     ("structural",), "OK"),
    ("test_k14_int_trunc",  ("blurry",),     "OK"),
    ("test_k15_round_neg",  ("blurry",),     "OK"),
    ("test_k16_raises",     ("contract",),   "OK"),
    ("test_k17_empty",      (),              "EMPTY"),
    ("test_k18_relational", ("relational",), "OK"),
    ("test_k19_flag",       ("flag",),       "OPAQUE"),
    ("test_k20_object_truthy", ("vacuum",),  "VACUUM_ONLY"),
    ("test_k21_any_content", ("structural",), "OK"),
    ("test_k22_not_any",     ("structural",), "OK"),
    ("test_k23_is_true",     ("strict",),     "OK"),
    ("test_k24_is_none",     ("vacuum",),     "VACUUM_ONLY"),
    ("test_k25_empty_collection", ("flag",),  "OPAQUE"),
    ("test_k26_comprehension",    ("flag",),  "OPAQUE"),
    # ── 2026-09-23 新增：四條 skip 的真實寫法，素材取自 Day 22 的產物 ──
    # 裝飾器式：pytest 必定報 SKIPPED，不是綠
    ("test_k27_decorator_skip",   (),         "SKIPPED"),
    # 本體第一句式：同上。docstring 不算語句
    ("test_k28_body_skip",        (),         "SKIPPED"),
    # 藏在 except 裡：實作沒拋例外時它真的會變綠 → 仍判 EMPTY，工具不猜
    ("test_k29_conditional_skip", ("vacuum",), "VACUUM_ONLY"),
    # 有 skip 也有斷言：斷言存在就照斷言判，不因 skip 而降級
    ("test_k30_skip_but_has_assert", ("strict",), "OK"),
)


def _self_check() -> None:
    fr = audit_source(_KAT_SOURCE, "<KAT>")
    got = {fn.name: fn for fn in fr.functions}

    if len(got) != len(_KAT_EXPECTED):
        raise SystemExit(
            f"中止：KAT 應解析到 {len(_KAT_EXPECTED)} 條測試函式，實際 {len(got)} 條"
        )

    problems: list[str] = []
    for name, kinds, verdict in _KAT_EXPECTED:
        fn = got.get(name)
        if fn is None:
            problems.append(f"{name}：沒有被解析到")
            continue
        actual = tuple(f.kind for f in fn.findings)
        if actual != kinds:
            problems.append(f"{name}：分類 {actual} ≠ 預期 {kinds}")
        if fn.verdict != verdict:
            problems.append(f"{name}：判定 {fn.verdict} ≠ 預期 {verdict}")

    if problems:
        raise SystemExit("中止：KAT 不符——\n  " + "\n  ".join(problems))
    print(f"KAT {len(_KAT_EXPECTED)} 條全部符合"
          f"（含 EMPTY／SKIPPED／OPAQUE／VACUUM_ONLY／OK 五種判定）")


def main(argv: list[str]) -> int:
    _self_check()
    if len(argv) < 2:
        return 0

    target = Path(argv[1])
    files = sorted(target.rglob("test_*.py")) if target.is_dir() else [target]
    if not files:
        raise SystemExit(f"中止：{target} 之下找不到任何 test_*.py")

    all_pass = True
    for f in files:
        fr = audit_file(f)
        if not fr.functions:
            # 解析得到檔案卻找不到測試函式 → 不印比值，直接喊停
            print(f"\n{f}\n  中止：解析到 0 條測試函式，不產生忠實性數字")
            all_pass = False
            continue
        report(fr)
        all_pass = all_pass and fr.passed
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

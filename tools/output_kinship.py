"""把 Day 26 的人工 grep 自動化：這條斷言的兩邊，是不是同一個東西？

為什麼需要這支
------------
Day 26 量到一件事：十份 AI 產物**全部**寫了

    assert res.balances_charted == res.balances_raw

而在受測的實作上，那兩個欄位指向同一個 tuple（154 與 156 行都是
`balances_tuple`）。這條斷言在比較一個東西跟它自己，**恆綠**。

當時的檢查是人工 grep。問題不在慢——grep 一次三十秒——
在於**人會略過它，而且略過的時候自我感覺良好**：
Day 26 的作者連續判錯三次，每一次當下都覺得自己看懂了。

工具不會覺得自己看懂了。這支就是把那個檢查變成機器做的一步。

做法分兩層，兩層的證據強度不同，報表分開印
--------------------------------------
**第一層：親緣表（量實作）**
跑 N 組輸入，逐對檢查輸出欄位之間的關係：

    IDENTITY     兩個欄位永遠是同一個物件（`is` 為真）
    EQUAL_VALUE  值永遠相等，但不是同一個物件
    LINEAR       一個欄位永遠等於另外兩個的和或差
    （其餘）     沒有偵測到關係

`IDENTITY` 是 `is` 判定，**確鑿**。
`EQUAL_VALUE` 與 `LINEAR` 是在 N 組輸入上成立，**那是推論不是證明**——
換一組輸入可能就不成立。報表會標出來並印出 N（Day 13：罪在不標示，不在推論）。

**第二層：掃斷言（量測試）**
逐條 `assert`，抽出兩邊碰到的 `(物件, 欄位)`。
**只有在兩邊用的是同一個結果物件**、而且牽涉的欄位落在親緣表裡時才標記。
跨執行的斷言（`res1.x` 對 `res2.y`）不標——那是蛻變關係的正常形狀。

這支看不到什麼
------------
**關係本身在數學上錯了，它看不到。** Day 26 那條把年額與月額相抵的
（固定年支出是年額、其他收入程式裡會再乘十二，差了十二倍），
兩個欄位確實來自不同路徑，結構上完全合格。
斷言檢核器也看不到，它給了那份 100% 忠實性。

**結構問題交給工具，語意問題留給人。** 這支只管前者。

    python3 tools/output_kinship.py --table
    python3 tools/output_kinship.py generated/2026-09-26-ai-metamorphic/run-A-MR-01.txt
    python3 tools/output_kinship.py --self-test
"""

from __future__ import annotations

import ast
import dataclasses
import itertools
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from shadow import calc_fixed as sut  # noqa: E402
from shadow.calc_fixed import LumpSum, Params  # noqa: E402

FIELDS = tuple(f.name for f in dataclasses.fields(sut.Result))
SAMPLES = 200
SEED = 20260928          # 固定種子：同一份報表任何人都跑得出來


def sample_params(rng: random.Random) -> Params:
    """產生一組合法輸入。年齡順序與非負金額是 PRD-04 的硬性要求。"""
    current = rng.randint(20, 50)
    retire = current + rng.randint(5, 30)
    death = retire + rng.randint(5, 35)
    return Params(
        current_age=current,
        retirement_age=retire,
        life_expectancy=death,
        current_savings=rng.choice([0.0, rng.uniform(0, 5e6)]),
        monthly_investment=rng.choice([0.0, rng.uniform(0, 1e5)]),
        monthly_expense_today=rng.uniform(0, 5e5),
        annual_recurring_expense=rng.choice([0.0, rng.uniform(0, 1e6)]),
        labor_insurance_pension=rng.choice([0.0, rng.uniform(0, 5e4)]),
        labor_insurance_start_age=retire + rng.randint(0, 5),
        labor_pension_monthly=rng.choice([0.0, rng.uniform(0, 5e4)]),
        labor_pension_start_age=retire + rng.randint(0, 5),
        other_income=rng.choice([0.0, rng.uniform(0, 1e5)]),
        pre_retirement_return=rng.uniform(0.0, 0.12),
        post_retirement_return=rng.uniform(0.0, 0.08),
        inflation_rate=rng.uniform(0.0, 0.05),
        lump_sums=tuple(
            LumpSum(age=rng.randint(retire, death), amount=rng.uniform(0, 1e6))
            for _ in range(rng.randint(0, 3))
        ),
    )


def _close(a, b) -> bool:
    if isinstance(a, tuple) != isinstance(b, tuple):
        return False
    if isinstance(a, tuple):
        return len(a) == len(b) and all(
            math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-9) for x, y in zip(a, b))
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


def kinship(n: int = SAMPLES) -> dict[frozenset[str], str]:
    """量實作：輸出欄位之間有哪些恆定關係。

    回傳 {欄位集合: 關係種類}。IDENTITY 是 `is` 判定，確鑿；
    其餘是在 n 組輸入上成立的推論。
    """
    rng = random.Random(SEED)
    results = [sut.calculate(sample_params(rng)) for _ in range(n)]

    table: dict[frozenset[str], str] = {}

    # 兩兩：同一物件？值恆等？
    for a, b in itertools.combinations(FIELDS, 2):
        va = [getattr(r, a) for r in results]
        vb = [getattr(r, b) for r in results]
        if all(x is y for x, y in zip(va, vb)):
            table[frozenset((a, b))] = "IDENTITY"
        elif all(_close(x, y) for x, y in zip(va, vb)):
            table[frozenset((a, b))] = "EQUAL_VALUE"

    # 三個一組：其中一個是否恆等於另外兩個的和或差
    scalars = [f for f in FIELDS
               if all(isinstance(getattr(r, f), float) for r in results)]
    for target in scalars:
        for x, y in itertools.permutations([s for s in scalars if s != target], 2):
            key = frozenset((target, x, y))
            if key in table:
                continue
            tv = [getattr(r, target) for r in results]
            if all(math.isclose(t, getattr(r, x) - getattr(r, y),
                                rel_tol=1e-12, abs_tol=1e-6)
                   for t, r in zip(tv, results)):
                table[key] = f"LINEAR: {target} == {x} - {y}"
    return table


# ── 掃斷言 ────────────────────────────────────────────────────────────

def _refs(node: ast.AST, alias: dict[str, tuple[str, str]]) -> set[tuple[str, str]]:
    """抽出這棵子樹裡所有的 `變數.欄位`，只收 Result 的欄位。

    `alias` 是別名表：AI 會把欄位先拆出來再比較，例如

        for charted, raw in zip(res.balances_charted, res.balances_raw):
            assert charted == raw

    第一版只認 `變數.欄位` 的形狀，這種就看不見（實測漏掉一條）。
    """
    out = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                and sub.attr in FIELDS):
            out.add((sub.value.id, sub.attr))
        elif isinstance(sub, ast.Name) and sub.id in alias:
            out.add(alias[sub.id])
    return out


def _aliases(fn: ast.AST) -> tuple[dict[str, tuple[str, str]], set[int]]:
    """在一個函式裡，哪些區域名字其實就是某個輸出欄位。

    只認三種**不改變值**的搬運：

        a = res.f                              直接指派
        a, b = res.f1, res.f2                  同時指派
        for a, b in zip(res.f1, res.f2)        逐項配對

    `zip` 拆出來的是元素不是整個 tuple，但「元素逐項比對」與
    「整個 tuple 比對」問的是同一件事，所以一樣列入。

    **這裡不追更遠。** 補完 zip 還有生成式、還有先存進 list 再比，
    補到最後就變成它要取代的那個 grep。改成讓工具自報漏了幾處
    （見 `completeness`），而不是假裝補得完。
    """
    alias: dict[str, tuple[str, str]] = {}
    lines: set[int] = set()          # 真正產生了綁定的那幾行，給完備性檢查用

    def field_of(node: ast.AST) -> tuple[str, str] | None:
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.attr in FIELDS):
            return (node.value.id, node.attr)
        return None

    def bind(targets: ast.AST, values: list[ast.AST], lineno: int) -> None:
        names = targets.elts if isinstance(targets, ast.Tuple) else [targets]
        if len(names) != len(values):
            return
        for name, value in zip(names, values):
            got = field_of(value)
            if isinstance(name, ast.Name) and got:
                alias[name.id] = got
                lines.add(lineno)

    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
            target, value = sub.targets[0], sub.value
            if isinstance(value, ast.Tuple):
                bind(target, list(value.elts), sub.lineno)
            else:
                bind(target, [value], sub.lineno)
        elif isinstance(sub, ast.For):
            call = sub.iter
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "zip"):
                bind(sub.target, list(call.args), sub.lineno)
    return alias, lines


def scan(path: str, table: dict[frozenset[str], str]) -> list[tuple[int, str, str]]:
    """逐條 assert，標出「兩邊其實是親戚」的。

    只在**兩邊用同一個結果物件**時才標記：跨執行的斷言是蛻變關係的
    正常形狀，不是問題。
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    hits = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        alias, _bound = _aliases(fn)
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assert):
                continue
            test = node.test
            if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
                continue
            left = _refs(test.left, alias)
            right = _refs(test.comparators[0], alias)
            if not left or not right:
                continue
            objs = {o for o, _ in left | right}
            if len(objs) != 1:                   # 跨執行，不標
                continue
            fields = frozenset(f for _, f in left | right)
            if len(fields) < 2:
                continue
            kind = table.get(fields)
            if kind:
                hits.append((node.lineno, kind, ast.unparse(test)[:96]))
    return sorted(set(hits))


def completeness(path: str, table: dict[frozenset[str], str],
                 hit_lines: set[int]) -> list[int]:
    """工具自己承認哪幾行沒被解釋到。

    為什麼需要這個
    ------------
    上面的掃描是**語法比對，永遠不完備**。第一版就漏掉一條
    （`for charted, raw in zip(...)` 裡的比較），而漏掉的方式是
    安靜的——報表顯示「標記 1 條」，看起來就像那個檔案只有一處。

    做法：把註解與字串拿掉，找出所有「同時提到同一組親緣欄位裡兩個名字」
    的程式行，再扣掉已經被解釋的行（被標記的斷言，以及把欄位搬給
    區域名字的那幾行）。**剩下的就是工具沒解釋的，叫人去看。**

    第一版的守衛是壞的：它拿「提到欄位的行數」去比「被標記的斷言數」，
    兩邊根本不是同一組行，相等只是巧合。比對行號集合才有意義。

    工具不假裝完備，但它要知道自己漏了。
    """
    import tokenize

    with open(path, "rb") as fh:
        toks = list(tokenize.tokenize(fh.readline))
    code_lines: dict[int, set[str]] = {}
    for tok in toks:
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        if tok.string in FIELDS:
            code_lines.setdefault(tok.start[0], set()).add(tok.string)

    mentions = {ln for ln, names in code_lines.items()
                if any(len(names & set(group)) >= 2 for group in table)}

    # 把欄位搬給區域名字的那幾行也算「已解釋」——它們不是斷言，
    # 但工具確實看懂了，而且下游的斷言已經因此被標記。
    tree = ast.parse(open(path, encoding="utf-8").read())
    bound: set[int] = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            bound |= _aliases(fn)[1]

    return sorted(mentions - hit_lines - bound)


# ── 報表 ──────────────────────────────────────────────────────────────

def print_table(table: dict[frozenset[str], str]) -> None:
    print(f"親緣表｜受測物 shadow/calc_fixed.py｜{SAMPLES} 組輸入｜種子 {SEED}\n")
    for key, kind in sorted(table.items(), key=lambda kv: sorted(kv[0])):
        print(f"  {'、'.join(sorted(key)):<46} {kind}")
    print("\n  IDENTITY 是 `is` 判定，確鑿。"
          f"\n  EQUAL_VALUE 與 LINEAR 是在這 {SAMPLES} 組輸入上成立——"
          "\n  **那是推論，不是證明**。換一組輸入可能就不成立。")


def report(paths: list[str]) -> int:
    table = kinship()

    # 守衛：受測物上明知有一對是同一個物件（154 與 156 行都是 balances_tuple）。
    # 量不到就是這支壞了，不能讓它安靜地回報「零命中」。
    if not any(k == "IDENTITY" for k in table.values()):
        raise SystemExit(
            "中止：親緣表一個 IDENTITY 都沒量到。"
            "\n受測物的 balances_raw 與 balances_charted 是同一個 tuple，"
            "\n量不到代表這支自己壞了——而壞掉的版本會回報「零命中」，"
            "\n那看起來就像產物很乾淨。")

    print_table(table)
    total_hits = 0
    print()
    for p in paths:
        hits = scan(p, table)
        total_hits += len(hits)
        mark = "—" if not hits else f"{len(hits)} 條"
        print(f"\n{os.path.basename(p)}｜標記 {mark}")
        for lineno, kind, text in hits:
            print(f"    L{lineno:<4} [{kind.split(':')[0]}]  {text}")
        unexplained = completeness(p, table, {h[0] for h in hits})
        if unexplained:
            print(f"    ⚠ 另有 {len(unexplained)} 行同時提到一組親緣欄位，"
                  f"但工具沒解釋：L{'、L'.join(map(str, unexplained))}"
                  f"\n      不必然是漏網（取值、傳參都算），但要人去看。")

    print(f"\n合計標記 {total_hits} 條，掃了 {len(paths)} 個檔案。")
    print("\n被標記的不等於沒用，等於**它的兩邊在實作上是親戚**——"
          "\n那條斷言約束的東西比它的長相少。逐條要人看。"
          "\n這支看不到「關係本身算錯」那一類（Day 26 那條年額對月額的），"
          "\n那一類目前沒有任何一把尺看得到。")
    return 0


def _kat() -> None:
    """人手寫、答案確鑿。驗的是「這支自己不會說謊」。"""
    table = kinship(n=30)

    # 1) 受測物的 charted 與 raw 必須被判成 IDENTITY（Day 26 已用 `is` 驗過）
    key = frozenset(("balances_raw", "balances_charted"))
    assert table.get(key) == "IDENTITY", table.get(key)

    # 2) 缺口的定義關係必須被抓到（calc_fixed.py 153 行）
    gap = frozenset(("retirement_gap", "target_fund", "projected_savings"))
    assert table.get(gap, "").startswith("LINEAR"), table.get(gap)

    # 3) 同物件、同親緣 → 標記；4) 跨物件 → 不標記；
    # 5) zip 拆出來的迴圈變數也要認得（第一版漏掉的就是這種）
    import tempfile
    src = (
        "def test_a(res):\n"
        "    assert res.balances_charted == res.balances_raw\n"
        "def test_b(res1, res2):\n"
        "    assert res1.balances_charted == res2.balances_raw\n"
        "def test_c(res):\n"
        "    assert res.target_fund > 0\n"
        "def test_d(res):\n"
        "    for charted, raw in zip(res.balances_charted, res.balances_raw):\n"
        "        assert charted == raw\n"
        "def test_e(res):\n"
        "    c, r = res.balances_charted, res.balances_raw\n"
        "    assert c == r\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src)
        tmp = fh.name
    try:
        hits = scan(tmp, table)
        lines = sorted(h[0] for h in hits)
        assert lines == [2, 9, 12], lines      # a、d、e 中；b、c 不中
    finally:
        os.remove(tmp)

    # 5) 欄位清單沒有被改動過（改了上面的 KAT 就失去意義）
    assert FIELDS == ("projected_savings", "target_fund", "retirement_gap",
                      "balances_raw", "balances_charted"), FIELDS

    # 6) 完備性守衛必須真的會響。
    #    第一版的守衛拿「提到欄位的行數」比「被標記的斷言數」，
    #    兩邊不是同一組行，相等只是巧合——那種守衛跟壞掉的沒有差別。
    #    這裡餵一個工具**解不開**的搬運形狀，它必須把那一行報出來。
    src2 = (
        "def test_f(res):\n"
        "    pairs = list(zip(res.balances_charted, res.balances_raw))\n"
        "    assert all(a == b for a, b in pairs)\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(src2)
        tmp2 = fh.name
    try:
        hits2 = scan(tmp2, table)
        assert not hits2, hits2                       # 確實解不開
        assert completeness(tmp2, table, set()) == [2], \
            completeness(tmp2, table, set())          # 但它要自己報出來
    finally:
        os.remove(tmp2)

    print("KAT 全部通過（6 組）")


def main(argv: list[str]) -> int:
    _kat()
    if "--self-test" in argv:
        return 0
    if "--table" in argv:
        print_table(kinship())
        return 0
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if not paths:
        raise SystemExit("用法：python3 tools/output_kinship.py <測試檔> [測試檔 ...]")
    return report(paths)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

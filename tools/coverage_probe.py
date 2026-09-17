"""行覆蓋率探針：用 `sys.settrace` 數哪幾行被走過。

為什麼不用 coverage.py
--------------------
沒有別的理由，本機環境裝不了。既然要自己數，就得先決定分母算哪些行：
`@dataclass` 的欄位宣告是型別描述不是邏輯，把它們算進去會稀釋
「測試跑得多深」這件事。本檔預設排除 class body 內的宣告，
`--with-decl` 可以切回含宣告的算法——**兩種算法都要報得出正確的數字**。

第一版兩種都報錯，原因只有一個
------------------------------
追蹤器掛在 import 之後，受測模組的模組層級與 class body 早就執行完了，
那 23 行宣告永遠不會進分子。於是 `--with-decl` 報出 43/66 = 65.2%——
分母含了宣告，分子卻沒有。那不是另一種算法，是一個錯的數字。
`sys.settrace` 必須在 import 之前掛上，兩種算法才會各自成立
（修正後：排除宣告 43/43、含宣告 66/66，皆為 100%）。

誰驗收這支
---------
`_assert_all_ran()`：任何一條測試沒跑起來就 `SystemExit`，不印覆蓋率。
Day 14 的 `test_mutator.py` 曾經在 pytest 不存在的情況下回報
「12/12 全部存活」——一個什麼都沒跑的工具，看起來跟一切正常一模一樣。
覆蓋率更危險：測試少跑幾條，數字只會變低，低到讓人以為是測試不夠好。

    python3 tools/coverage_probe.py shadow/calc.py tests/test_checklist.py
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import sys
import types
from dataclasses import dataclass


# ── pytest shim：本檔只需要 approx / raises / mark / fixture ──────────
def _install_pytest_shim() -> None:
    if "pytest" in sys.modules:
        return
    shim = types.ModuleType("pytest")

    class _Approx:
        def __init__(self, v, rel=None, ab=None):
            self.v, self.rel, self.ab = v, rel or 1e-9, ab

        def __eq__(self, o):
            if isinstance(o, (list, tuple)):
                return len(o) == len(self.v) and all(
                    _Approx(a, self.rel, self.ab) == b for a, b in zip(self.v, o)
                )
            tol = self.ab if self.ab is not None else self.rel * max(abs(self.v), abs(o), 1e-12)
            return abs(o - self.v) <= tol

    class _Raises:
        def __init__(self, exc):
            self.exc = exc

        def __enter__(self):
            return self

        def __exit__(self, t, v, tb):
            return t is not None and issubclass(t, self.exc)

    class _Mark:
        def __getattr__(self, _):
            return lambda *a, **k: (lambda f: f)

    def _fixture(*a, **k):
        if a and callable(a[0]):
            a[0]._is_fixture = True
            return a[0]

        def deco(f):
            f._is_fixture = True
            return f

        return deco

    shim.approx = lambda v, rel=None, abs=None: _Approx(v, rel, abs)
    shim.raises = lambda exc, *a, **k: _Raises(exc)
    shim.mark = _Mark()
    shim.fixture = _fixture
    sys.modules["pytest"] = shim


@dataclass
class Report:
    total: int
    hit: int
    missed: list[int]
    ran: int
    failed: list[str]

    @property
    def ratio(self) -> float:
        return self.hit / self.total if self.total else 0.0


def statement_lines(path: str, with_decl: bool = False) -> set[int]:
    """分母：可執行的邏輯敘述。預設排除 class body 內的宣告與純 docstring。"""
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    decl: set[int] = set()
    if not with_decl:
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            decl |= {s.lineno for s in cls.body
                     if isinstance(s, (ast.AnnAssign, ast.Assign, ast.Expr))}
    skip = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
            ast.Import, ast.ImportFrom, ast.Expr)
    return {n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.stmt) and not isinstance(n, skip)} - decl


def _collect(module) -> list[tuple[str, object, dict]]:
    def fixtures(owner) -> dict:
        out = {}
        for name in dir(owner):
            obj = getattr(owner, name, None)
            if callable(obj) and getattr(obj, "_is_fixture", False):
                try:
                    out[name] = obj()
                except Exception:
                    pass
        return out

    cases: list[tuple[str, object, dict]] = []
    mod_fx = fixtures(module)
    for name, obj in vars(module).items():
        if isinstance(obj, type) and name.startswith("Test"):
            inst = obj()
            fx = {**mod_fx, **fixtures(inst)}
            cases += [(f"{name}.{m}", getattr(inst, m), fx)
                      for m in dir(inst) if m.startswith("test")]
        elif callable(obj) and name.startswith("test") and not getattr(obj, "_is_fixture", False):
            cases.append((name, obj, mod_fx))
    return cases


def measure(source: str, test_file: str, with_decl: bool = False) -> Report:
    _install_pytest_shim()
    target = os.path.abspath(source)
    root = os.path.dirname(os.path.dirname(target))
    for p in (os.path.dirname(target), root):
        if p not in sys.path:
            sys.path.insert(0, p)

    executed: set[int] = set()

    def tracer(frame, event, _arg):
        if event == "line" and frame.f_code.co_filename == target:
            executed.add(frame.f_lineno)
        return tracer

    spec = importlib.util.spec_from_file_location("_probe_tests", test_file)
    module = importlib.util.module_from_spec(spec)

    failed: list[str] = []
    # 追蹤在 import 之前掛上：受測模組的模組層級與 class body 也要算進分子，
    # 否則 `@dataclass` 欄位宣告會被記成「沒走過」——那是量測錯誤，不是測試不足。
    sys.settrace(tracer)
    spec.loader.exec_module(module)
    cases = _collect(module)
    for name, fn, fx in cases:
        try:
            kwargs = {p: fx[p] for p in inspect.signature(fn).parameters if p in fx}
            fn(**kwargs)
        except Exception as exc:                     # noqa: BLE001
            failed.append(f"{name}（{type(exc).__name__}）")
    sys.settrace(None)

    lines = statement_lines(source, with_decl)
    return Report(total=len(lines), hit=len(executed & lines),
                  missed=sorted(lines - executed), ran=len(cases), failed=failed)


def _assert_all_ran(r: Report) -> None:
    if r.ran == 0:
        raise SystemExit("中止：一條測試都沒收集到，不產生覆蓋率數字")
    if r.failed:
        raise SystemExit(
            f"中止：{len(r.failed)} / {r.ran} 條測試沒有跑起來，覆蓋率作廢——\n  "
            + "\n  ".join(r.failed)
        )


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        raise SystemExit("用法：coverage_probe.py <受測原始碼> <測試檔> [--with-decl]")
    source, test_file = argv[1], argv[2]
    with_decl = "--with-decl" in argv

    r = measure(source, test_file, with_decl)
    _assert_all_ran(r)

    print(f"{test_file} → {source}")
    print(f"  測試 {r.ran} 條全部執行成功")
    print(f"  邏輯敘述 {r.total} 行，走過 {r.hit} 行 → 行覆蓋率 {r.ratio:.1%}"
          f"{'（含 class 宣告）' if with_decl else ''}")
    print(f"  未覆蓋：{r.missed if r.missed else '無'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

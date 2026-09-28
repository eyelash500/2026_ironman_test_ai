"""逐條驗收「別人寫的」蛻變關係：這一條殺得掉幾個變異體？

跟 mr_audit.py 的差別
-------------------
`mr_audit.py` 的四條關係是寫死的（RELATIONS 常數），因為那是作者自己寫的，
數量固定、名字固定。本檔要量的是 AI 交出來的十份產物，每份條數不一樣、
名字也不一樣，所以改成從檔案裡把測試函式列舉出來。

判定與 mr_audit.py 完全相同，不另立標準：
  pytest 回傳碼 1 → 殺掉；0 → 存活；其餘 → 無效，不入分數。

**這把尺只能證實，不能證偽。**
殺得掉 → 那條關係有用；殺不掉 → 只代表這十四種錯法碰不到它。
十四個變異體是 Day 19 為了打 calc_fixed 設計的，換一份目錄結論就換一個
（Day 20）。所以本檔不印「廢話」「無用」這種字眼，只印「這批錯法碰不到」。

三個守衛
-------
一、`-k` 是子字串比對。若某條測試的名字是另一條的前綴，
    `-k 短名` 會同時選到兩條，量出來的是兩條的聯集而不是單獨。
    偵測到就中止，不猜。
二、基準線紅的那條不能算。它在未變異的實作上就是紅的，
    套上變異體照樣紅，會被判成「殺掉全部十四個」——一個假的滿分。
    這種要單獨列出來排除，而不是靜靜丟掉。
三、`-k` 選不到任何測試時 pytest 回傳 5。不攔的話會顯示「殺 0 個」，
    看起來就像那條關係沒用，而它其實根本沒跑（同 Day 24 的教訓：
    工具在什麼都沒做的時候必須閉嘴）。

    python3 tools/mr_audit_batch.py generated/2026-09-26-ai-metamorphic/run-A-MR-01.txt
    python3 tools/mr_audit_batch.py --self-test
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from domain_mutants import DOMAIN_MUTANTS, REL_SOURCE  # noqa: E402
from harness import Verdict, apply_mutant, run_tests  # noqa: E402

LANDING = "tests/test_ai_mr.py"


def test_names(path: str) -> list[str]:
    src = open(path, encoding="utf-8").read()
    return [n.name for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]


def collisions(names: list[str]) -> list[tuple[str, str]]:
    """回傳所有「a 是 b 的子字串」的配對。有任何一組就不能用 -k 單獨跑。"""
    return [(a, b) for a in names for b in names if a != b and a in b]


def _run(k: str, target: str = LANDING) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", target, "-q", "-p", "no:cacheprovider",
         "-k", k],
        cwd=ROOT, capture_output=True, text=True,
    )


def _pytest_missing(proc: subprocess.CompletedProcess) -> bool:
    return "No module named pytest" in (proc.stderr or "")


def audit(product: str) -> int:
    names = test_names(product)
    if not names:
        raise SystemExit(f"中止：{product} 裡一條測試函式都沒有。")

    bad = collisions(names)
    if bad:
        lines = "\n".join(f"  「{a}」是「{b}」的子字串" for a, b in bad)
        raise SystemExit(
            f"中止：{len(bad)} 組名字會讓 `-k` 同時選到兩條測試。\n{lines}\n"
            "量出來的會是聯集而不是單獨，不能當成「這一條殺得掉幾個」。")

    landing_abs = os.path.join(ROOT, LANDING)
    # 使用者若自己先把產物複製到降落點，再把降落點餵進來，
    # copyfile 會丟 SameFileError；而底下的 finally 還會把那個檔案刪掉。
    # 直接擋下來並說清楚該怎麼下指令。
    if os.path.exists(landing_abs) and os.path.samefile(product, landing_abs):
        raise SystemExit(
            f"中止：{product} 就是本工具的降落點 {LANDING}。"
            f"\n不必自己複製，直接餵產物路徑："
            f"\n    python3 tools/mr_audit_batch.py <產物檔>")
    shutil.copyfile(product, landing_abs)
    try:
        print(f"{os.path.basename(product)}｜關係 {len(names)} 條"
              f"｜變異體 {len(DOMAIN_MUTANTS)} 個\n")

        # 守衛二、三：先逐條確認基準線
        live, red = [], []
        for n in names:
            proc = _run(n)
            if _pytest_missing(proc):
                raise SystemExit(
                    "中止：這個環境跑不起 pytest。"
                    "\n不擋的話會變成「基準線全紅」，那是誤導（同 Day 18）。")
            if proc.returncode == 5:
                raise SystemExit(f"中止：`-k {n}` 一條測試都沒選到。")
            (live if proc.returncode == 0 else red).append(n)

        if red:
            print(f"基準線紅、排除 {len(red)} 條（未變異就不過，不列入計分）：")
            for n in red:
                print(f"  {n}")
            print()

        killed_by: dict[str, list[str]] = {}
        for n in live:
            hits: list[str] = []
            for m in DOMAIN_MUTANTS:
                with tempfile.TemporaryDirectory() as tmp:
                    try:
                        copy = apply_mutant(ROOT, REL_SOURCE, m, tmp)
                        v = run_tests(copy, LANDING, ROOT, extra_args=["-k", n])
                    except Exception:                            # noqa: BLE001
                        v = Verdict.ERROR
                if v in (Verdict.KILLED, Verdict.TIMEOUT):
                    hits.append(m.id)
            killed_by[n] = hits
            mark = "這批錯法碰不到" if not hits else f"殺掉 {len(hits)}"
            print(f"  {n[:58]:<58} {mark:<14} {'、'.join(hits)}")

        union = sorted({i for v in killed_by.values() for i in v})
        missed = [m.id for m in DOMAIN_MUTANTS if m.id not in union]
        cold = [n for n, v in killed_by.items() if not v]

        print(f"\n計分 {len(live)} 條｜聯集殺掉 {len(union)} / {len(DOMAIN_MUTANTS)}"
              f"（{len(union) / len(DOMAIN_MUTANTS):.1%}）")
        print(f"沒有任何一條抓得到：{'、'.join(missed) if missed else '無'}")
        print(f"這批錯法碰不到的關係：{len(cold)} / {len(live)}")
        print("\n**這把尺只能證實，不能證偽。**"
              "\n殺不掉不等於沒用——那十四種錯法是人設計的（Day 20）。")
    finally:
        landing = os.path.join(ROOT, LANDING)
        if os.path.exists(landing):
            os.remove(landing)
    return 0


def _kat() -> None:
    """人手寫、答案確鑿。驗的是「這支自己不會說謊」。"""
    # 1) 子字串偵測抓得到真的碰撞
    assert collisions(["test_gap", "test_gap_delta"]) == [("test_gap", "test_gap_delta")]
    # 2) 沒有碰撞時要回空，不能誤報
    assert collisions(["test_alpha", "test_beta"]) == []
    # 3) 同名不算碰撞（a != b 的條件）
    assert collisions(["test_x", "test_x"]) == []
    # 4) 列舉抓得到函式，且只抓 test_ 開頭的
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("def helper():\n    pass\n\n\ndef test_one():\n    assert 1\n")
        tmp_path = fh.name
    try:
        assert test_names(tmp_path) == ["test_one"], test_names(tmp_path)
    finally:
        os.remove(tmp_path)
    # 5) 變異體目錄不得為空
    assert len(DOMAIN_MUTANTS) == 14, len(DOMAIN_MUTANTS)

    print("KAT 全部通過（5 組）")


def main(argv: list[str]) -> int:
    _kat()
    if "--self-test" in argv:
        return 0
    targets = [a for a in argv[1:] if not a.startswith("--")]
    if not targets:
        raise SystemExit("用法：python3 tools/mr_audit_batch.py <產物檔> [產物檔 ...]")
    for t in targets:
        audit(t)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

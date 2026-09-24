"""把「測試失敗」分成兩件不同的事：算錯答案，還是餵錯輸入。

要回答的問題
----------
Day 22 的二十份 AI 腳本，有十二份在**未修改的**實作上就是紅的。
紅有兩種完全不同的成因：

  1. 它讀了規格，自己推導出一個期望值，推錯了 —— `AssertionError`
  2. 它餵了規格明文禁止的輸入，卻期待算出結果 —— `ValueError`

第一種是 Oracle Problem 的本體：**沒有人能替它確認那個數字對不對**。
第二種是它自己沒讀完規格。兩者混在一起叫「測試失敗」，就看不出 AI 到底卡在哪。

判別規則
-------
只看 pytest `--tb=line` 印出的例外型別與訊息，不讀原始碼、不猜意圖：

  AssertionError／`assert ...`           → EXPECTED_WRONG（期望值算錯）
  ValueError + 受測物的校驗訊息之一      → ILLEGAL_INPUT（踩到非法輸入）
  ValueError + 其他訊息                  → NEEDS_REVIEW（不自動歸類）
  TypeError／AttributeError／KeyError 等 → INTERFACE（介面用錯）
  解析不出型別                           → NEEDS_REVIEW

`NEEDS_REVIEW` 刻意保留。工具分不出來的就說分不出來，不硬塞進某一格——
Day 19 起的規矩：工具不猜。

誰驗收這支
---------
檔尾 `_kat()` 的十一條，輸入是人手寫的 pytest 輸出片段，預期分類先寫死。
另外兩道守衛：解析數與 pytest 自報的失敗數對不上就中止；一條都解析不到也中止。
**第一道是第二道擋不住的**——「總數為 0」抓得到全盤失效，
抓不到「少抓了六成」，而後者才是這支工具第一版真正發生的事。
Day 14 的校準器與 Day 17 的覆蓋率探針都栽在同一件事——
**工具在什麼都沒做的時候，印出了一個看起來很合理的數字。**

    python3 tools/failure_classifier.py <產物檔 ...>
    python3 tools/failure_classifier.py --self-test
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(ROOT, "tests", "test_ai_matrix.py")

# 受測物 shadow/calc_fixed.py 裡 PRD-04 校驗會拋的五種訊息。
# 寫死在這裡，不用模糊比對——訊息換了就該讓分類器壞掉，而不是默默改判。
PRD04_MESSAGES = (
    "年齡必須為正整數",
    "請領年齡不得為負數",
    "金額不得為負數",
    "大筆支出年齡不得為負數",
    "大筆支出金額不得為負數",
)

# pytest --tb=line 的一行長這樣：
#   /path/to/tests/test_ai_matrix.py:42: assert 21 in (55, 56)
#   /path/to/shadow/calc_fixed.py:91: ValueError: 大筆支出金額不得為負數
#
# **第二種的路徑是受測物，不是測試檔。** 例外在受測物裡拋出時，
# --tb=line 印的是最後一個 frame。第一版要求路徑含 `test_`，
# 結果把「踩到非法輸入」整類系統性濾掉——而那正是本輪的對照組。
# 報表當時印「期望值算錯 14%」，看起來完全合理。
_LINE = re.compile(r"^(?P<path>[^\s:]+):(?P<line>\d+):\s*(?P<exc>[A-Za-z_][A-Za-z0-9_.]*):?\s*(?P<msg>.*)$")


def classify(exc: str, msg: str) -> str:
    # pytest --tb=line 對「沒有附訊息的斷言」印的是 `assert a > b`，
    # 不是 `AssertionError`。第一版漏了這個形狀，十一條失敗被誤丟進覆核區。
    if exc in ("AssertionError", "assert"):
        return "EXPECTED_WRONG"
    if exc == "ValueError":
        if any(m in msg for m in PRD04_MESSAGES):
            return "ILLEGAL_INPUT"
        return "NEEDS_REVIEW"
    if exc in ("TypeError", "AttributeError", "KeyError", "IndexError", "NameError"):
        return "INTERFACE"
    return "NEEDS_REVIEW"


def parse(output: str) -> list[dict]:
    """從 pytest --tb=line 的輸出抽出每一條失敗。"""
    found: list[dict] = []
    for raw in output.split("\n"):
        line = raw.strip()
        if not line or line.startswith(("=", "_", "E ", "#")):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        exc, msg = m.group("exc"), m.group("msg").strip()
        found.append({"line": int(m.group("line")), "exc": exc, "msg": msg,
                      "kind": classify(exc, msg)})
    return found


_SUMMARY = re.compile(r"(\d+)\s+(failed|error)")


def expected_count(output: str) -> int:
    """從 pytest 自己的結尾摘要讀出失敗數，用來跟解析結果對帳。"""
    tail = [ln for ln in output.split("\n") if " passed" in ln or " failed" in ln or " error" in ln]
    return sum(int(n) for ln in tail[-1:] for n, _ in _SUMMARY.findall(ln))


def run_one(product: str, dump_dir: str | None = None) -> tuple[list[dict], int, str]:
    """回傳（解析到的失敗、pytest 自報的失敗數、原始輸出）。

    第三個回傳值是給對帳用的。第一版只回傳解析結果，
    於是「解析規則沒對上」與「真的全綠」印出來一模一樣——
    十二份裡有五份因此被默默當成全綠。
    """
    shutil.copyfile(product, SCRATCH)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_ai_matrix.py",
         "-q", "--tb=line", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    raw = proc.stdout + "\n" + proc.stderr
    if dump_dir:
        os.makedirs(dump_dir, exist_ok=True)
        name = os.path.basename(product).replace(".txt", "") + ".pytest.txt"
        open(os.path.join(dump_dir, name), "w", encoding="utf-8").write(raw)
    return parse(raw), expected_count(raw), raw


LABEL = {
    "EXPECTED_WRONG": "期望值算錯",
    "ILLEGAL_INPUT": "踩到非法輸入",
    "INTERFACE": "介面用錯",
    "NEEDS_REVIEW": "待人工覆核",
}


def audit(products: list[str], dump_dir: str | None = None) -> int:
    total = Counter()
    distinct = Counter()
    seen: set[tuple[str, int, str]] = set()
    mismatch: list[str] = []
    for p in products:
        found, reported, _raw = run_one(p, dump_dir)
        name = os.path.basename(p)
        if len(found) != reported:
            mismatch.append(f"{name}：pytest 自報 {reported} 條，解析到 {len(found)} 條")
        if not found:
            print(f"\n── {name} ──　pytest 自報 {reported} 條失敗，解析到 0 條")
            continue
        print(f"\n── {name} ──　失敗 {len(found)} 條（pytest 自報 {reported} 條）")
        for f in found:
            key = (name, f["line"], f["msg"])
            dup = key in seen
            seen.add(key)
            if not dup:
                distinct[f["kind"]] += 1
            mark = "　（重複）" if dup else ""
            print(f"   第 {f['line']:>4} 行　{LABEL[f['kind']]:<6}　{f['exc']}: {f['msg'][:44]}{mark}")
            total[f["kind"]] += 1

    if os.path.exists(SCRATCH):
        os.remove(SCRATCH)

    if mismatch:
        print("\n對帳不符，不出具比例：")
        for m in mismatch:
            print("  -", m)
        raise SystemExit(
            "中止：解析結果與 pytest 自報的失敗數對不上。"
            "\n擋住『總數為 0』擋不住『少抓了六成』——要對帳的不是有沒有數字，"
            "\n是數字跟來源對不對得上（同 Day 17 的 _assert_all_ran）。"
            "\n原始輸出已存到 dump 目錄，逐份比對解析規則。")

    n = sum(total.values())
    if n == 0:
        raise SystemExit(
            "\n中止：所有檔案加起來解析到 0 條失敗。"
            "\n不是『全部都過了』，是 pytest 的輸出格式沒對上解析規則——"
            "\n這種時候印出『期望值算錯 0%』比不印更糟。")

    d = sum(distinct.values())
    print(f"\n{'':4}{'':14}原始 {n} 條　　去重後 {d} 條")
    for kind in ("EXPECTED_WRONG", "ILLEGAL_INPUT", "INTERFACE", "NEEDS_REVIEW"):
        c, dc = total[kind], distinct[kind]
        if c:
            print(f"{'':6}{LABEL[kind]:<6}　{c:>3} 條（{c / n:>3.0%}）　　{dc:>3} 條（{dc / d:>3.0%}）")
    print("\n去重規則：同一份產物、同一行、同一則訊息只計一次。")
    print("一個壞掉的 fixture 會讓共用它的每一條測試都紅，"
          "原始計數把那算成好幾個錯誤——分母灌水，比例就不能看。")
    print("待人工覆核的每一條都要人去看。工具分不出來的，工具不猜。")
    return 0


def _kat() -> None:
    """人手寫、答案確鑿。輸入是 pytest --tb=line 的真實形狀。"""
    sample = """
/repo/tests/test_ai_matrix.py:42: ValueError: 金額不得為負數
/repo/tests/test_ai_matrix.py:55: AssertionError: assert 22938825.0 == 14903594.0
/repo/tests/test_ai_matrix.py:61: TypeError: unexpected keyword argument 'monthly_income'
/repo/tests/test_ai_matrix.py:70: ValueError: 這是受測物沒有的訊息
=========================== short test summary info ============================
E   AssertionError: 這一行是 traceback 的延續，不該被算成一條失敗
""".strip()

    got = parse(sample)
    assert len(got) == 4, [g["exc"] for g in got]
    assert [g["kind"] for g in got] == [
        "ILLEGAL_INPUT", "EXPECTED_WRONG", "INTERFACE", "NEEDS_REVIEW"], got

    # 1) 非法輸入認的是受測物的訊息，不是 ValueError 這個型別本身
    assert classify("ValueError", "金額不得為負數") == "ILLEGAL_INPUT"
    assert classify("ValueError", "something else") == "NEEDS_REVIEW"

    # 2) 年齡那條的訊息很長，只比對前綴
    assert classify(
        "ValueError",
        "年齡必須為正整數且 current_age < retirement_age < life_expectancy",
    ) == "ILLEGAL_INPUT"

    # 3) 沒見過的例外不硬塞，進覆核
    assert classify("ZeroDivisionError", "division by zero") == "NEEDS_REVIEW"

    # 4) 沒有訊息的斷言，pytest 印的是 `assert a > b`，不是 AssertionError
    bare = parse("/repo/tests/test_ai_matrix.py:134: assert 8322586.35 > 8322586.35")
    assert len(bare) == 1 and bare[0]["kind"] == "EXPECTED_WRONG", bare

    # 5) 對帳：從 pytest 的結尾摘要讀得出失敗數
    assert expected_count("6 failed, 26 passed in 0.12s") == 6
    assert expected_count("37 passed, 1 skipped in 0.07s") == 0

    # 6) 空輸入不得回報任何分類
    assert parse("") == []

    # 7) 例外在受測物裡拋出時，路徑是受測物而不是測試檔——照樣要算一條
    sut = parse("/repo/shadow/calc_fixed.py:91: ValueError: 大筆支出金額不得為負數")
    assert len(sut) == 1 and sut[0]["kind"] == "ILLEGAL_INPUT", sut

    # 8) 去重的鍵是（檔名、行號、訊息），同一個壞值擴散出的失敗只計一次
    same = parse("/r/shadow/calc_fixed.py:91: ValueError: 大筆支出金額不得為負數\n"
                 "/r/shadow/calc_fixed.py:91: ValueError: 大筆支出金額不得為負數")
    assert len(same) == 2, same
    assert len({(x["line"], x["msg"]) for x in same}) == 1, "去重鍵取錯"

    # 9) `E   ` 開頭是 traceback 的重複行，不得重複計數
    dup = parse("E   ValueError: 大筆支出金額不得為負數\n"
                "/repo/shadow/calc_fixed.py:91: ValueError: 大筆支出金額不得為負數")
    assert len(dup) == 1, dup

    print("KAT 全部通過（11 組）")


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        _kat()
        return 0
    products = [a for a in argv[1:] if not a.startswith("--")]
    if not products:
        raise SystemExit(
            "用法：failure_classifier.py <產物檔 ...> [--dump <目錄>]"
            "　｜　failure_classifier.py --self-test")
    dump = None
    if "--dump" in argv:
        i = argv.index("--dump")
        dump = argv[i + 1] if i + 1 < len(argv) else None
        products = [a for a in products if a != dump]
    _kat()
    return audit(products, dump)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

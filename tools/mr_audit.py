"""誰來驗收蛻變關係：一條關係殺不掉任何變異體，就是廢話。

為什麼需要這支
------------
寫出一條蛻變關係不算完。三種寫法都會在報表上顯示綠色：

  對的　　「所有金額 ×10 → 目標金額剛好 ×10」
  太弱的　「金額變大 → 目標金額變大」——方向對，約束鬆到抓不到東西
  廢話的　「目標金額 ≥ 0」——恆真，永遠不會紅

肉眼分不出來，因為三者都是綠的。本檔用 Day 19 的十四個領域變異體逐條試：
**把那條關係單獨拿去跑，它殺得掉幾個？** 殺 0 個的不列入。

這把尺同時也要量作者自己
----------------------
底下四條關係是人手寫的。人寫的一樣會寫出廢話，這不是 AI 的專利——
先量自己，再拿同一把尺去量別人。

判定沿用 Day 18 的規矩
-------------------
pytest 回傳碼 1 → 殺掉；0 → 存活；其餘 → 無效，不入分數。
每一條關係在未變異的實作上必須先全綠，否則中止（基準線紅的，變異結果沒有意義）。

    python3 tools/mr_audit.py
    python3 tools/mr_audit.py --self-test
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from domain_mutants import DOMAIN_MUTANTS, REL_SOURCE  # noqa: E402
from harness import Verdict, apply_mutant, run_tests  # noqa: E402

REL_TESTS = "tests/test_metamorphic.py"

# 關係代號 → (人看得懂的名字, pytest -k 的樣式)
# 只跑 fixed，legacy 是 Day 6 差分測試的守備範圍，變異體也打不到它。
RELATIONS: tuple[tuple[str, str, str], ...] = (
    ("MR-01", "線性齊次", "mr01 and fixed"),
    ("MR-02", "單調性", "mr02 and fixed"),
    ("MR-03", "支出配置不變", "mr03 and fixed"),
    ("MR-04", "自我一致性", "mr04 and fixed"),
)


def _pytest_missing(proc: subprocess.CompletedProcess) -> bool:
    return "No module named pytest" in (proc.stderr or "")


def _baseline(k_filter: str) -> None:
    """未變異時必須全綠。紅的基準線跑變異沒有意義（Day 18）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", REL_TESTS, "-q", "-p", "no:cacheprovider",
         "-k", k_filter],
        cwd=ROOT, capture_output=True, text=True,
    )
    if _pytest_missing(proc):
        raise SystemExit(
            "中止：這個環境跑不起 pytest。"
            "\n不擋的話訊息會變成「基準線不是全綠」，那是誤導——"
            "\n真正的原因是沒有東西跑得起來（同 Day 18 的 _assert_baseline）。")
    if proc.returncode == 5:
        raise SystemExit(
            f"中止：`-k {k_filter}` 一條測試都沒選到。"
            "\n樣式打錯時 pytest 回傳 5，而不是報錯——"
            "\n若不擋，這條關係會顯示『殺 0 個』，看起來就像它是廢話。")
    if proc.returncode != 0:
        raise SystemExit(
            f"中止：`-k {k_filter}` 在未變異的實作上就不是全綠（回傳碼 {proc.returncode}）。")


def audit() -> int:
    print(f"基底 {REL_SOURCE}｜變異體 {len(DOMAIN_MUTANTS)} 個｜關係 {len(RELATIONS)} 條\n")

    killed_by: dict[str, list[str]] = {}
    for code, name, k in RELATIONS:
        _baseline(k)
        hits: list[str] = []
        for m in DOMAIN_MUTANTS:
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    copy = apply_mutant(ROOT, REL_SOURCE, m, tmp)
                    v = run_tests(copy, REL_TESTS, ROOT, extra_args=["-k", k])
                except Exception:                                # noqa: BLE001
                    v = Verdict.ERROR
            if v in (Verdict.KILLED, Verdict.TIMEOUT):
                hits.append(m.id)
        killed_by[code] = hits
        verdict = "廢話，不列入" if not hits else f"殺掉 {len(hits)}"
        print(f"  {code} {name:<8} {verdict:<12} {'、'.join(hits) if hits else '—'}")

    union = sorted({i for v in killed_by.values() for i in v})
    missed = [m.id for m in DOMAIN_MUTANTS if m.id not in union]
    useless = [c for c, v in killed_by.items() if not v]

    print(f"\n聯集殺掉 {len(union)} / {len(DOMAIN_MUTANTS)}"
          f"（{len(union) / len(DOMAIN_MUTANTS):.1%}）")
    print(f"沒有任何一條關係抓得到：{'、'.join(missed) if missed else '無'}")

    if useless:
        print(f"\n**廢話關係 {len(useless)} 條：{'、'.join(useless)}**")
        print("殺不掉任何一個變異體。它們在報表上是綠的，而且永遠會是綠的。")
    else:
        print("\n四條關係都殺得掉東西，沒有廢話。")

    print("\n殺不掉的不代表關係寫錯，也可能是那種錯法本來就不破壞這個關係。"
          "\n每一個都要人工判，工具不猜。")
    return 0


def _kat() -> None:
    """人手寫、答案確鑿。驗的是「這支自己不會說謊」。"""
    # 0) 沒有 pytest 的環境要能自己說出來，而不是誤報成「基準線不是全綠」
    probe = subprocess.run(
        [sys.executable, "-m", "pytest", REL_TESTS, "-q", "-p", "no:cacheprovider",
         "-k", "這個樣式不存在"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if _pytest_missing(probe):
        print("KAT 略過：這個環境沒有 pytest。判定邏輯無法在此驗收。")
        return

    # 1) 樣式打錯時 pytest 回傳 5，必須被擋下來而不是當成「殺 0 個」
    assert probe.returncode == 5, f"預期 pytest 回傳 5，實得 {probe.returncode}"

    # 2) 四條關係的 -k 樣式都真的選得到測試
    for code, _name, k in RELATIONS:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", REL_TESTS, "--collect-only", "-q",
             "-p", "no:cacheprovider", "-k", k],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"{code} 的樣式 `{k}` 選不到任何測試"

    # 3) 變異體目錄不得為空
    assert len(DOMAIN_MUTANTS) == 14, len(DOMAIN_MUTANTS)

    print("KAT 全部通過（3 組）")


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        _kat()
        return 0
    _kat()
    return audit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

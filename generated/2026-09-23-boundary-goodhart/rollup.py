"""把 const_sampler 的逐檔結果彙總到「格」的層級。

逐檔看不出東西：一份腳本只有兩三組案例，沒打到邊界很正常。
要問的是**整格五份加起來、幾十組案例裡，有沒有任何一組踩到邊界**。
所以本檔把同一格的案例池在一起，再交給 bva_checker 判一次。

對照組有兩個，兩個都是人寫的：
  golden_set_v2.json  —— 鎖住行為的 23 組快照
  tests/test_checklist.py —— MFT／INV／DIR 三型的行為測試

    python3 generated/2026-09-23-boundary-goodhart/rollup.py
"""

from __future__ import annotations

import glob
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from bva_checker import check_bva                      # noqa: E402
from const_sampler import CONSTRAINTS, _fmt, extract, extract_json, roundness  # noqa: E402

M = "generated/2026-09-22-scripts-matrix"

GROUPS: list[tuple[str, list[str]]] = [
    ("A-L1（Pro・一句話）", sorted(glob.glob(f"{ROOT}/{M}/run-A-L1-0?.txt"))),
    ("A-PRD（Pro・十二條）", sorted(glob.glob(f"{ROOT}/{M}/run-A-pro-0?.txt"))),
    ("B-L1（Flash・一句話）", sorted(glob.glob(f"{ROOT}/{M}/run-B-L1-0?.txt"))),
    ("B-PRD（Flash・十二條）", sorted(glob.glob(f"{ROOT}/{M}/run-B-pro-0?.txt"))),
    ("golden v2（人寫・快照）", [f"{ROOT}/golden/golden_set_v2.json"]),
    ("test_checklist（人寫・行為）", [f"{ROOT}/tests/test_checklist.py"]),
]


def collect(paths: list[str]) -> dict:
    cases: list[dict] = []
    by_kind: dict[str, list[float]] = {"年齡": [], "金額": [], "比率": []}
    for p in paths:
        text = open(p, encoding="utf-8").read()
        d = extract_json(text) if p.endswith(".json") else extract(text)
        cases.extend(d["cases"])
        for k in by_kind:
            by_kind[k].extend(d["by_kind"][k])
    return {"cases": cases, "by_kind": by_kind, "files": len(paths)}


def main() -> int:
    rows = []
    for name, paths in GROUPS:
        if not paths:
            continue
        d = collect(paths)
        line = {"格": name, "檔": d["files"], "案例": len(d["cases"])}
        for kind in ("年齡", "金額", "比率"):
            r = roundness(d["by_kind"][kind], kind)
            line[kind] = f"{r['ratio']:.0%}（n={r['n']}）" if r["n"] else "—"
        hits = []
        for constraint, step in CONSTRAINTS:
            out = check_bva(constraint, d["cases"], step=step)
            if out["score"] > 0:
                lhs, op, rhs = constraint
                hits.append(f"{lhs}{op}{rhs} {out['score']:.0%}")
        line["邊界"] = "、".join(hits) if hits else "**全部 0%**"
        rows.append(line)

        top = Counter(d["by_kind"]["年齡"]).most_common(6)
        line["年齡取值"] = "、".join(f"{_fmt(v)}×{c}" for v, c in top)

    print(f"{'格':26}{'檔':>3}{'案例':>5}  {'年齡整數':>10}{'金額整萬':>11}{'比率':>10}  邊界命中")
    for r in rows:
        print(f"{r['格']:26}{r['檔']:>3}{r['案例']:>5}  "
              f"{r['年齡']:>10}{r['金額']:>11}{r['比率']:>10}  {r['邊界']}")
    print()
    for r in rows:
        print(f"{r['格']:26} 年齡最常出現：{r['年齡取值']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

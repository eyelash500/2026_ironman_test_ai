"""把 AI 產出的 markdown 測試案例集，解析成可餵給 bva_checker 的參數字典。

為什麼需要這支
------------
`bva_checker.check_bva` 吃的是 `{"A_e": 85, "A_d": 85}` 這種字典。
但模型交出來的是 markdown 表格，而且十份輸出各自發明了自己的編碼慣例。
判斷邏輯 38 行就寫完，這一步卻是整條流程真正的阻力。

已觀測到的編碼慣例（全部來自 Day 10 的十份輸出）
--------------------------------------------
基準情境三種寫法：
  (1) 每列一個參數      | `A_c` 現齡 | 40 |
  (2) 一列塞多個參數    | `A_c` / `A_r` / `A_d` | 40 / 65 / 85 |
  (3) 不設基準          每條案例自己把參數寫滿

案例列一種相對引用：
  (4) 「同上」／「同 TC-xx」  後續案例只寫差異，其餘沿用前一列
      （2026-09-10 在 run-B-02 發現，當時已經以為分析完了）

凍結宣告（2026-09-11 起生效）
--------------------------
本檔對 Day 10 的十份輸出調到可用、並補齊 KAT 之後即凍結。
規格突變實驗的輸出是**沒見過的測試集**：屆時本檔不得先修改，
必須原封不動跑一次，記錄解析成功率與撞到的新寫法。

這是在驗一個假設——「AI 產出要能自動驗收，卡點在格式沒有契約」。
若本檔在新資料上直接可用，該假設被削弱；
若又撞上第五種寫法，那就是實證。

用法
----
    python3 tools/case_extractor.py --kat              # 先驗收驗收者
    python3 tools/case_extractor.py <案例集檔案> [...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

FIELDS = ("A_c", "A_r", "A_d", "A_e")

# 案例列：首欄是 TC-xx / TC-xx-xx / AC-xxx 這類編號（可能被 ** 包住）
_CASE_ROW = re.compile(r"^\|\s*\*{0,2}(?:TC|AC|TG|WD|CASE)-")
# 條款與缺口編號不是案例編號
_NOT_CASE = ("PRD-", "GAP-", "G-", "D-", "RC-")
# (4) 相對引用：這一列只寫差異，其餘沿用**前一列**。
#     「其餘 baseline」不算——那是「其餘用基準值」，`dict(base)` 已經做了；
#     若當成沿用前一列，前一列的覆寫值會洩漏到這一列。兩者語意不同。
_SAME_AS = re.compile(r"同上|同\s*TC-|同前|其餘\s*同(?!.*baseline)")


def _load(path: str | Path) -> str:
    """輸出檔可能是純 markdown，也可能是被 JSON 字串包起來的單行。"""
    raw = Path(path).read_text(encoding="utf-8").strip()
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return raw.replace("\\n", "\n")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _inline(text: str) -> dict[str, list[int]]:
    """抓行內的 `A_x = 40` 寫法；同一欄可能出現多個值。"""
    found: dict[str, list[int]] = {}
    for f in FIELDS:
        vals = [int(m) for m in re.findall(rf"`?{f}`?\s*[=＝:：]\s*`?(-?\d+)", text)]
        if vals:
            found[f] = vals
    # 「三次執行：A_e = 64 / 65 / 66」這種連寫
    trio = re.search(
        r"`?A_e`?\s*[=＝]\s*`?(\d+)\s*[/／]\s*(\d+)\s*[/／]\s*(\d+)", text
    )
    if trio:
        found["A_e"] = [int(x) for x in trio.groups()]
    return found


def parse_baseline(lines: list[str]) -> dict[str, int]:
    """解析基準情境。三種寫法都吃，先出現者為準。"""
    base: dict[str, int] = {}
    for line in lines:
        s = line.strip()
        if s.startswith("|"):
            cells = _cells(s)
            if len(cells) >= 2:
                # (2) 一列多參數：左欄列出 n 個欄名，右欄用同樣的分隔給 n 個值
                names = [f for f in FIELDS if re.search(rf"`?{f}`?", cells[0])]
                nums = [int(x) for x in re.findall(r"-?\d+", cells[1])]
                if len(names) > 1 and len(names) == len(nums):
                    for f, v in zip(names, nums):
                        base.setdefault(f, v)
                    continue
                # (1) 每列一參數
                if len(names) == 1 and nums:
                    base.setdefault(names[0], nums[0])
                    continue
        # (3) 行內寫法也可能出現在前置區
        for f, v in _inline(s).items():
            base.setdefault(f, v[0])
    return base


def extract(path: str | Path, clause: str | None = None) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """回傳 (基準情境, 案例參數字典清單)。

    clause 給了就只取宣稱覆蓋該條款的案例列（如 "PRD-05"）。
    """
    lines = _load(path).split("\n")
    first = next(
        (i for i, l in enumerate(lines) if _CASE_ROW.match(l.strip())), len(lines)
    )
    base = parse_baseline(lines[:first])

    cases: list[dict[str, Any]] = []
    prev: dict[str, int] = {}
    for line in lines:
        s = line.strip()
        if not _CASE_ROW.match(s):
            continue
        cells = _cells(s)
        cid = (cells[0].replace("**", "").split() or [""])[0]
        if cid.startswith(_NOT_CASE) or len(cells) < 3:
            continue

        # 只從「輸入參數」欄取值（倒數第二欄），不掃預期輸出欄。
        # 預期輸出裡常出現「結果不得等於 A_e = 90 時的值」這種句子，
        # 掃整列會把它當成輸入。2026-09-10 實測：十份裡有 4 列踩到，
        # 但那些值剛好與輸入欄重複，所以沒有改變分數——是運氣，不是設計。
        param_cell = cells[-2]
        found = _inline(param_cell)
        # (4) 「同上」／「同 TC-xx」：沿用前一列解析出來的參數。
        #     沒有這一步，run-B-02 的 TC-05-02~06 會掉光 A_r / A_d。
        inherited = prev if _SAME_AS.search(param_cell) else {}

        row: list[dict[str, Any]] = []
        n = max((len(v) for v in found.values()), default=1)
        for i in range(n):
            case = dict(base)
            case.update(inherited)
            case["_id"] = cid
            for f, vals in found.items():
                case[f] = vals[min(i, len(vals) - 1)]
            row.append(case)

        # prev 必須在 clause 過濾**之前**更新：「同上」指的是文件裡的上一列，
        # 不是「上一條符合篩選條件的列」。若在過濾後才更新，
        # 篩選會改變「同上」解析到的對象。
        prev = {f: v for f, v in row[-1].items() if f in FIELDS}

        if clause and clause not in s:
            continue
        cases.extend(row)
    return base, cases


def coverage(base: dict[str, int], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """解析品質自評：基準抓到幾欄、案例裡各欄有值的比例。"""
    need = [f for f in FIELDS]
    return {
        "baseline_fields": sorted(base),
        "baseline_complete": all(f in base for f in ("A_c", "A_r", "A_d")),
        # 格式 (3) 不設基準，base 為空是正確行為，不是解析失敗。
        # 區分方式：前置區有沒有提到那些欄名。
        "cases": len(cases),
        "field_fill": {
            f: sum(1 for c in cases if f in c) / len(cases) if cases else 0.0
            for f in need
        },
    }


def _kat() -> None:
    """人手寫、人持有的已知答案測試。輸入小到眼睛讀得完。

    bva_checker 有 7 組 KAT，這支一度一組都沒有——
    而它比檢核器難寫、也更容易錯。補上。
    """
    import tempfile, os

    def run(md: str, clause: str | None = "PRD-05"):
        fd, path = tempfile.mkstemp(suffix=".md", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(md)
        try:
            return extract(path, clause=clause)
        finally:
            os.unlink(path)

    # 1) 基準表寫法 (1)：每列一參數
    base, cases = run(
        "| 參數 | 值 |\n|---|---|\n| `A_c` 現齡 | 40 |\n| `A_r` 退休 | 65 |\n| `A_d` 壽命 | 85 |\n"
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_e = 85` | 計入 |\n")
    assert base == {"A_c": 40, "A_r": 65, "A_d": 85}, base
    assert cases[0]["A_e"] == 85 and cases[0]["A_d"] == 85, cases

    # 2) 基準表寫法 (2)：一列多參數
    base, _ = run(
        "| 參數 | 值 |\n|---|---|\n| `A_c` / `A_r` / `A_d` | 40 / 65 / 85 |\n"
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_e = 85` | 計入 |\n")
    assert base == {"A_c": 40, "A_r": 65, "A_d": 85}, base

    # 3) 寫法 (3)：不設基準，案例自帶
    base, cases = run(
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_c=40, A_r=65, A_d=85, A_e=86` | 排除 |\n")
    assert base == {} and cases[0]["A_d"] == 85 and cases[0]["A_e"] == 86, (base, cases)

    # 4) 寫法 (4)：「同上」沿用前一列
    _, cases = run(
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_r=65, A_d=70, A_e=65` | 計入 |\n"
        "| TC-05-02 | PRD-05 | 同上，`A_e=70` | 計入 |\n")
    assert cases[1]["A_d"] == 70 and cases[1]["A_e"] == 70, cases[1]

    # 5) 「其餘 baseline」不是「同上」：不得沿用前一列的覆寫值
    _, cases = run(
        "| 參數 | 值 |\n|---|---|\n| `A_d` 壽命 | 85 |\n"
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_d=70, A_e=70` | 計入 |\n"
        "| TC-05-02 | PRD-05 | `A_e = 85`，其餘 baseline | 計入 |\n")
    assert cases[1]["A_d"] == 85, f"其餘 baseline 應回到基準 85，卻拿到 {cases[1]['A_d']}"

    # 6) 預期輸出欄裡的參數不得被當成輸入
    _, cases = run(
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_d=85, A_e=70` | 結果不得等於 `A_e = 90` 時的值 |\n")
    assert [c["A_e"] for c in cases] == [70], [c["A_e"] for c in cases]

    # 7) 「三次執行 A_e = 64 / 65 / 66」展開成三筆
    _, cases = run(
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-05 | PRD-05 | 三次執行：`A_e = 64 / 65 / 66`，`A_r=65, A_d=85` | 略 |\n")
    assert sorted(c["A_e"] for c in cases) == [64, 65, 66], cases

    # 8) clause 過濾不得改變「同上」解析到的對象
    _, cases = run(
        "| ID | 條款 | 輸入 | 預期 |\n|---|---|---|---|\n"
        "| TC-05-01 | PRD-05 | `A_r=65, A_d=70, A_e=65` | 略 |\n"
        "| TC-06-01 | PRD-06 | `A_d=99` | 略 |\n"
        "| TC-05-02 | PRD-05 | 同上，`A_e=70` | 略 |\n")
    assert cases[-1]["A_d"] == 99, f"「同上」應指文件的上一列(TC-06-01, A_d=99)，卻拿到 {cases[-1]['A_d']}"

    print("KAT 全部通過（8 組）")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--kat":
        _kat(); raise SystemExit(0)
    if len(sys.argv) < 2:
        print(__doc__.strip().split("\n")[-1])
        raise SystemExit(1)
    for p in sys.argv[1:]:
        base, cases = extract(p, clause="PRD-05")
        cov = coverage(base, cases)
        lines = _load(p).split("\n")
        first = next((i for i, l in enumerate(lines) if _CASE_ROW.match(l.strip())), len(lines))
        declares_base = any(re.search(r"`?A_[crd]`?", l) for l in lines[:first])
        if cov["baseline_complete"]:
            flag = "✅ 基準表"
        elif not declares_base:
            flag = "✅ 無基準表（格式 3，案例自帶參數）"
        else:
            flag = "❌ 有基準表但解析失敗"
        print(
            f"{flag} {Path(p).name:20s} base={ {k: base[k] for k in ('A_c','A_r','A_d') if k in base} } "
            f"PRD-05 案例 {cov['cases']:3d}  A_e 有值 {cov['field_fill']['A_e']*100:3.0f}%"
        )

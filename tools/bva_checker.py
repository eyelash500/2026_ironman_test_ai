"""邊界值分析檢核器：量一組測試案例有沒有真的打在邊界上。

用途
----
測試案例集看起來覆蓋了某條規格，不代表它測到了那條規格的邊界。
本檔把「`≤ A_d` 就該有 A_d−1 / A_d / A_d+1」這個 QA 直覺寫成可執行的判定。

為什麼要吃「參數對」
------------------
受測物的邊界多半不是常數。PRD-05 寫的是 `A_r ≤ A_e ≤ A_d`——三個都是使用者輸入，
邊界在「兩個輸入的相對位置」上。所以約束的右手邊可以是參數名（關係式邊界），
也可以是數字（常數邊界，如 `r = 0`）。

誰驗收這支檢核器
--------------
檔尾的 KAT（known-answer test，已知答案測試）由人手寫、人持有：
輸入小到眼睛讀得完、預期結果確鑿無疑。遞迴懷疑停在這一層。

    python3 tools/bva_checker.py
"""

from __future__ import annotations

import math
from typing import Any

# ("A_e", "<=", "A_d") 關係式邊界；("r", ">=", 0.0) 常數邊界
Constraint = tuple[str, str, str | float]
Case = dict[str, Any]

def check_bva(
    constraint: Constraint,
    cases: list[Case],
    step: float = 1.0,
    tolerance: float = 1e-9,
    mode: str = "3-point",
) -> dict[str, Any]:
    """檢核 cases 是否命中 constraint 的臨界點。

    做法：對每個案例算出 `左值 − 右值`，看這組差值裡有沒有出現
    −step（界內一步）、0（邊界上）、+step（界外一步）。

    回傳 {"score", "hit", "missing", "deltas", "pass"}。
    score = 命中點數 / 必要點數；缺任一點 pass 即為 False。
    """
    lhs_field, _op, rhs_spec = constraint
    required = {-1.0: "off-below", 0.0: "on-point", +1.0: "off-above"}
    if mode == "5-point":
        required = {-2.0: "off-2-below", -1.0: "off-1-below", 0.0: "on-point",
                    +1.0: "off-1-above", +2.0: "off-2-above"}

    deltas: list[float] = []
    for case in cases:
        if lhs_field not in case:
            continue
        if isinstance(rhs_spec, str):
            if rhs_spec not in case:
                continue
            rhs_val = float(case[rhs_spec])
        else:
            rhs_val = float(rhs_spec)
        deltas.append(float(case[lhs_field]) - rhs_val)

    hit: dict[str, bool] = {}
    missing: list[str] = []
    for offset, label in required.items():
        target = offset * step
        is_hit = any(math.isclose(d, target, abs_tol=tolerance) for d in deltas)
        hit[label] = is_hit
        if not is_hit:
            missing.append(label)

    return {
        "score": (len(required) - len(missing)) / len(required),
        "hit": hit,
        "missing": missing,
        "deltas": sorted(set(deltas)),
        "pass": not missing,
    }


# ---------------------------------------------------------------------------
# KAT：人手寫、人持有。這一層不由 AI 產生，也不從別處 import。
# ---------------------------------------------------------------------------

def _kat() -> None:
    up = ("A_e", "<=", "A_d")

    # 1) 完美三點 → 滿分
    r = check_bva(up, [{"A_e": 84, "A_d": 85},
                       {"A_e": 85, "A_d": 85},
                       {"A_e": 86, "A_d": 85}])
    assert r["pass"] and r["score"] == 1.0, r

    # 2) 只給界內遠點與界外遠點 → 三點全缺，且必須指名 on-point
    r = check_bva(up, [{"A_e": 75, "A_d": 85}, {"A_e": 95, "A_d": 85}])
    assert not r["pass"] and r["score"] == 0.0, r
    assert "on-point" in r["missing"], r

    # 3) 邊界上 + 界外一步，缺界內一步 → 2/3。這正是本輪多數 run 的形狀
    r = check_bva(up, [{"A_e": 85, "A_d": 85}, {"A_e": 86, "A_d": 85}])
    assert not r["pass"] and math.isclose(r["score"], 2 / 3), r
    assert r["missing"] == ["off-below"], r

    # 4) 常數邊界（右手邊是數字，不是參數名）
    r = check_bva(("i", ">=", 0.0), [{"i": -1.0}, {"i": 0.0}, {"i": 1.0}])
    assert r["pass"], r

    # 5) 關係式邊界不因 A_d 改變而失效：同樣的差值，不同的絕對值
    r = check_bva(up, [{"A_e": 65, "A_d": 66},
                       {"A_e": 70, "A_d": 70},
                       {"A_e": 71, "A_d": 70}])
    assert r["pass"], r  # 差值 −1 / 0 / +1 都有，即使 A_d 不同

    # 6) 缺欄位的案例應被跳過，不得當成命中
    r = check_bva(up, [{"A_e": 85}, {"A_d": 85}])
    assert r["score"] == 0.0 and r["deltas"] == [], r

    # 7) step 不是 1 的情況（利率以 0.01 為一步）
    r = check_bva(("r", ">=", 0.0),
                  [{"r": -0.01}, {"r": 0.0}, {"r": 0.01}], step=0.01)
    assert r["pass"], r

    print("KAT 全部通過（7 組）")


if __name__ == "__main__":
    _kat()

"""依 PRD 條文計算目標金額與累積期終值，用來量「改一條規格值多少錢」。

這支不是受測物的影子模型
------------------------
`shadow/calc.py` 複製的是**受測物當下的行為**（含缺陷），驗收器是差分測試。
本檔實作的是**PRD 說應該怎麼算**，兩者本來就該不一樣——
PRD v1.0 的存在意義就是宣告「受測物算錯了」。

參數化的是被裁決過的那幾個點
--------------------------
`income_base` / `lump_base` / `timing` 三個開關對應 PRD v1.1 的三項裁決。
把它們切到「未採用」的那一邊，就能量出裁決的代價。

誰驗收這支
---------
檔尾的 KAT 釘住 PRD v1.0 正文已經印出來的六個數字。
那六個數字是 Day 9 人工算出、寫進規格書、公開發表過的——
本檔若算不出它們，是本檔錯，不是規格書錯。

    python3 tools/prd_cost.py
"""

from __future__ import annotations

Pension = tuple[float, int]   # (月額, 請領年齡 A_p)
LumpSum = tuple[int, float]   # (發生年齡 A_e, 今日幣值金額)


def target_fund(
    A_c: int,
    A_r: int,
    A_d: int,
    E_month: float,
    r_p: float,
    i: float,
    annual_recurring: float = 0.0,
    pensions: tuple[Pension, ...] = (),
    other_month: float = 0.0,
    lumps: tuple[LumpSum, ...] = (),
    income_base: str = "A_p",
    lump_base: str = "A_c",
) -> float:
    """PRD-02／05／06～10：退休當日所需的目標金額。

    PRD-02 期初年金，第一期對應 `A_r`，共 `A_d − A_r + 1` 年，支出端通膨鎖 `A_c`。
    PRD-09 淨支出取 `max(0, 支出 − 收入)`，盈餘不滾存。

    income_base: "A_p" = PRD v1.1（勞保勞退鎖各自請領年齡）
                 "A_c" = PRD v1.0（鎖現齡，未採用）
    lump_base:   "A_c" = PRD v1.1 明文（未採用選項為 "A_r"）
    """
    if income_base not in ("A_p", "A_c"):
        raise ValueError(f"income_base 只能是 A_p 或 A_c，收到 {income_base!r}")
    if lump_base not in ("A_c", "A_r"):
        raise ValueError(f"lump_base 只能是 A_c 或 A_r，收到 {lump_base!r}")

    annual_expense_today = E_month * 12 + annual_recurring   # PRD-08 合併
    total = 0.0

    for k in range(A_d - A_r + 1):                            # PRD-02 期初、含 A_r
        age = A_r + k
        expense = annual_expense_today * (1 + i) ** (age - A_c)

        # PRD-10：其他收入視為今日幣值，恆鎖 A_c
        income = other_month * 12 * (1 + i) ** (age - A_c)
        for amount, A_p in pensions:                          # PRD-06／07
            if age < A_p:
                continue
            base = A_p if income_base == "A_p" else A_c
            income += amount * 12 * (1 + i) ** (age - base)

        total += max(0.0, expense - income) / (1 + r_p) ** k   # PRD-09、PRD-02

    for A_e, amount in lumps:                                  # PRD-05
        if not (A_r <= A_e <= A_d):
            continue
        base = A_c if lump_base == "A_c" else A_r
        total += amount * (1 + i) ** (A_e - base) / (1 + r_p) ** (A_e - A_r)

    return total


def accumulated(
    principal: float,
    monthly: float,
    r: float,
    years: int,
    timing: str = "期末",
    principal_compounding: str = "月",
) -> float:
    """PRD-01：本金與月存統一採名目月利率 `r/12`，月存為期末投入。

    timing: "期末" = PRD v1.1 裁決①；"期初" = 未採用選項。
    principal_compounding:
        "月" = PRD-01（本金與月存同頻率，RC-04 查證後改判）
        "年" = 受測物現況（同一個帳戶兩種複利頻率），僅供對照
    """
    if timing not in ("期末", "期初"):
        raise ValueError(f"timing 只能是 期末 或 期初，收到 {timing!r}")
    if principal_compounding not in ("月", "年"):
        raise ValueError(f"principal_compounding 只能是 月 或 年，收到 {principal_compounding!r}")

    n = years * 12
    monthly_rate = r / 12
    if principal_compounding == "月":
        fv_principal = principal * (1 + monthly_rate) ** n
    else:
        fv_principal = principal * (1 + r) ** years

    if monthly_rate == 0:                                      # PRD-01 邊界處置
        fv_monthly = monthly * n
    else:
        fv_monthly = monthly * (((1 + monthly_rate) ** n - 1) / monthly_rate)
        if timing == "期初":
            fv_monthly *= 1 + monthly_rate
    return fv_principal + fv_monthly


# ---------------------------------------------------------------------------
# KAT：釘住 PRD v1.0 正文已發表的六個數字。人手抄自規格書，不由本檔產生。
# ---------------------------------------------------------------------------

BASE = dict(A_c=42, A_r=65, A_d=85, E_month=30_000, r_p=0.04, i=0.02)


def _kat() -> None:
    def close(a: float, b: float) -> bool:
        """比到元。兩邊都 round，才不會把 float 拿去跟 int 比而恆為 False。"""
        return round(a) == round(b)

    # 1) PRD v1.0「目標金額 9,885,351」：期初、65–85 共 21 年、零收入
    assert close(target_fund(**BASE), 9_885_351), target_fund(**BASE)

    # 2) 受測物現況「9,317,668」：期末、66–85 共 20 年
    now = sum(30_000 * 12 * 1.02 ** ((65 + k) - 42) / 1.04 ** k for k in range(1, 21))
    assert close(now, 9_317_668), now

    # 3) 只改期初、仍 20 年「9,690,374」
    mid = sum(30_000 * 12 * 1.02 ** ((65 + k) - 42) / 1.04 ** (k - 1) for k in range(1, 21))
    assert close(mid, 9_690_374), mid

    # 4) PRD v1.0「本金 年複利（現況）4,697,171 → r/12（新規格）5,006,566」
    acc_old = accumulated(800_000, 19_391, 0.08, 23, "期末", principal_compounding="年")
    acc_new = accumulated(800_000, 19_391, 0.08, 23, "期末", principal_compounding="月")
    assert close(800_000 * 1.08 ** 23, 4_697_171)
    assert close(800_000 * (1 + 0.08 / 12) ** 276, 5_006_566)

    # 5) PRD v1.0「累積期合計 現況 19,991,456 → 新規格 20,300,851」
    assert close(acc_old, 19_991_456), acc_old
    assert close(acc_new, 20_300_851), acc_new

    # 6) 零報酬率退化為線性累加（PRD-01 邊界處置），且兩種複利頻率同值
    assert close(accumulated(0, 1_000, 0.0, 10, "期末"), 120_000)
    assert accumulated(500, 0, 0.0, 10, "期末", principal_compounding="年") == 500.0

    # 7) 裁決①：期初比期末多剛好一個 (1 + r/12) 因子
    early = accumulated(800_000, 19_391, 0.08, 23, "期初")
    fv_p = 800_000 * (1 + 0.08 / 12) ** 276
    assert abs((early - fv_p) - (acc_new - fv_p) * (1 + 0.08 / 12)) < 1e-6
    assert close(early, 20_402_813), early

    # 8) 裁決②：鎖 A_c 時收入／支出比恆為今日比值，通膨在淨支出上消失
    p = ((15_000, 65), (5_000, 65))
    ratios = []
    for age in (65, 75, 85):
        exp = 30_000 * 12 * 1.02 ** (age - 42)
        inc = 20_000 * 12 * 1.02 ** (age - 42)
        ratios.append(inc / exp)
    assert max(ratios) - min(ratios) < 1e-12, ratios

    # 9) 裁決②的方向：鎖 A_p 認列的收入較少，目標金額必較高
    v10 = target_fund(**BASE, pensions=p, income_base="A_c")
    v11 = target_fund(**BASE, pensions=p, income_base="A_p")
    assert v11 > v10 and close(v10, 3_295_117) and close(v11, 5_706_115), (v10, v11)

    # 10) 裁決③：PRD-05 上界——A_e > A_d 者不得計入（缺陷 C 的規格面）
    over = target_fund(**BASE, lumps=((90, 1_000_000),))
    assert close(over, target_fund(**BASE)), over

    # 11) 非法開關要擋下來，不得靜默採用預設
    for bad in ({"income_base": "A_r"}, {"lump_base": "A_p"}):
        try:
            target_fund(**BASE, **bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} 應該要 raise")
    for bad_acc in ({"timing": "月初"}, {"principal_compounding": "日"}):
        try:
            accumulated(1, 1, 0.01, 1, **bad_acc)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad_acc} 應該要 raise")

    print("KAT 全部通過（11 組）")


if __name__ == "__main__":
    _kat()

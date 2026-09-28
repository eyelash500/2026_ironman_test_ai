#!/usr/bin/env bash
# Day 26 前三道關的完整驗收。一行跑完，輸出存進 results/。
#
# 為什麼要有這支：manifest.yaml 裡的數字是人手抄進去的。
# 沒有原始輸出，抄錯了沒人查得出來（同 Day 22）。
#
#     bash generated/2026-09-26-ai-metamorphic/verify.sh
#
# 需在 repo 根目錄、已 source venv 的情況下執行。
#
# 第四道關（逐條關係的變異體驗收）另外一支：gate-d.sh。
# 分開的理由是它要跑 143 條 × 14 個變異體，約兩千次 pytest，
# 跟前三關放在一起會讓「快速驗收」變成半小時的事。

set -u
cd "$(dirname "$0")/../.." || exit 1
D="generated/2026-09-26-ai-metamorphic"
OUT="$D/results"
mkdir -p "$OUT"

ALL="run-A-MR-01 run-A-MR-02 run-A-MR-03 run-A-MR-04 run-A-MR-05
     run-B-MR-01 run-B-MR-02 run-B-MR-03 run-B-MR-04 run-B-MR-05"

echo "環境：$(python3 -V)、pytest $(python3 -m pytest --version 2>&1 | head -1)"

# ── 關 A：斷言檢核器 ────────────────────────────────────────────
{
  echo "# 關 A：tools/assert_inspector.py（忠實性 >= 0.8、無 EMPTY、無 VACUUM_ONLY）"
  echo "# 判準沿用 2026-09-23 修正版：SKIPPED 不計入失敗"
  for f in $ALL; do
    echo "########## $f ##########"
    cp "$D/$f.txt" tests/test_ai_mr.py
    python3 tools/assert_inspector.py tests/test_ai_mr.py 2>&1 | grep -v "^KAT"
  done
} | tee "$OUT/gate-a.txt"

# ── 關 B：未變異時必須全綠 ──────────────────────────────────────
{
  echo "# 關 B：未變異的 calc_fixed 上，該份測試必須全綠"
  echo "# 本輪特別要看的：關係本身寫錯的那種紅（事前預測過會出現，見 expectations）"
  for f in $ALL; do
    echo "########## $f ##########"
    cp "$D/$f.txt" tests/test_ai_mr.py
    python3 -m pytest tests/test_ai_mr.py -q 2>&1 | tail -1
  done
} | tee "$OUT/gate-b.txt"

# ── 關 C：14 個領域變異體，合計與單獨兩種量法 ──────────────────
{
  echo "# 關 C：tools/harness.py --domain（合計 = golden v2 + 該份；單獨 = --solo 不帶 golden）"
  echo "# 關 B 紅的會在此中止，那是 _assert_baseline 的預期行為，不是故障"
  for f in $ALL; do
    echo "########## $f 合計 ##########"
    cp "$D/$f.txt" tests/test_ai_mr.py
    python3 tools/harness.py --domain tests/test_ai_mr.py 2>&1 | grep -E "存活|殺掉 |變異分數|中止"
    echo "########## $f 單獨 ##########"
    python3 tools/harness.py --domain tests/test_ai_mr.py --solo 2>&1 | grep -E "存活|殺掉 |變異分數|中止"
  done
} | tee "$OUT/gate-c.txt"

rm -f tests/test_ai_mr.py
echo
echo "前三關完成，輸出在 $OUT/。第四關另跑：bash $D/gate-d.sh"

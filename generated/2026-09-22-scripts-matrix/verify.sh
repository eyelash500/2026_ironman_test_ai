#!/usr/bin/env bash
# Day 22 三道關的完整驗收。一行跑完，輸出存進 results/。
#
# 為什麼要有這支：manifest.yaml 裡的數字是人手抄進去的。
# 沒有原始輸出，抄錯了沒人查得出來。
# 系列的原則是「可查證」而不是「可重現」——這支讓查證不必重跑。
#
#     bash generated/2026-09-22-scripts-matrix/verify.sh
#
# 需在 repo 根目錄、已 source venv 的情況下執行。

set -u
cd "$(dirname "$0")/../.." || exit 1
D="generated/2026-09-22-scripts-matrix"
OUT="$D/results"
mkdir -p "$OUT"

ALL="run-A-L1-01 run-A-L1-02 run-A-L1-03 run-A-L1-04 run-A-L1-05
     run-A-pro-01 run-A-pro-02 run-A-pro-03 run-A-pro-04 run-A-pro-05
     run-B-L1-01 run-B-L1-02 run-B-L1-03 run-B-L1-04 run-B-L1-05
     run-B-pro-01 run-B-pro-02 run-B-pro-03 run-B-pro-04 run-B-pro-05"

echo "環境：$(python3 -V)、pytest $(python3 -m pytest --version 2>&1 | head -1)"

# ── 關 A：斷言檢核器 ────────────────────────────────────────────
{
  echo "# 關 A：tools/assert_inspector.py（忠實性 >= 0.8、無 EMPTY、無 VACUUM_ONLY）"
  echo "# 判準為 2026-09-23 修正版：SKIPPED 不計入失敗，見 decisions.md"
  for f in $ALL; do
    echo "########## $f ##########"
    cp "$D/$f.txt" tests/test_ai_matrix.py
    python3 tools/assert_inspector.py tests/test_ai_matrix.py 2>&1 | grep -v "^KAT"
  done
} | tee "$OUT/gate-a.txt"

# ── 關 B：未變異時必須全綠 ──────────────────────────────────────
{
  echo "# 關 B：未變異的 calc_fixed 上，該份測試必須全綠"
  for f in $ALL; do
    echo "########## $f ##########"
    cp "$D/$f.txt" tests/test_ai_matrix.py
    python3 -m pytest tests/test_ai_matrix.py -q 2>&1 | tail -1
  done
} | tee "$OUT/gate-b.txt"

# ── 關 C：14 個領域變異體，合計與單獨兩種量法 ──────────────────
{
  echo "# 關 C：tools/harness.py --domain（合計 = golden v2 + 該份；單獨 = --solo 不帶 golden）"
  echo "# 關 B 紅的會在此中止，那是 _assert_baseline 的預期行為，不是故障"
  for f in $ALL; do
    echo "########## $f 合計 ##########"
    cp "$D/$f.txt" tests/test_ai_matrix.py
    python3 tools/harness.py --domain tests/test_ai_matrix.py 2>&1 | grep -E "存活|殺掉 |變異分數|中止"
    echo "########## $f 單獨 ##########"
    python3 tools/harness.py --domain tests/test_ai_matrix.py --solo 2>&1 | grep -E "存活|殺掉 |變異分數|中止"
  done
} | tee "$OUT/gate-c.txt"

rm -f tests/test_ai_matrix.py
echo
echo "完成。三份輸出在 $OUT/"

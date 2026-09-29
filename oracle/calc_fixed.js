// PRD v1.2 的 JavaScript 實作：從 shadow/calc_fixed.py 逐段移植。
//
// 為什麼要有這支
// ------------
// 修復版要回到受測物那支 HTML 裡跑，而受測物是 JavaScript。
// shadow/calc_fixed.py 是規格的 Python 實作，經過 Day 14–28 全部的尺；
// 這支是它的 JS 對應版，兩者之間用差分測試對齊（tools/diff_fixed.py）。
//
// 移植規則（同 Day 5 的機械式抽取，方向相反）
// ------------------------------------------
// 一段 Python 對一段 JS，順序不變、變數名不變、不做「順手優化」。
// 任何一處兩邊不一致，差分測試會抓到；差分過了才准接進 HTML。
//
// 與受測物原版（sut/進階退休規劃試算.html 292–375 行）的差異，逐條對應到第一幕的缺陷：
//   缺陷 A   折現與提領改期初，第一期對應退休當年（PRD-02／03）
//   缺陷 A'  餘額軌跡不夾 0（PRD-03／12）
//   缺陷 B   年齡順序校驗，倒置即拋錯（PRD-04）
//   缺陷 C   大筆支出限定 A_r ≤ A_e ≤ A_d（PRD-05）
//   缺陷 D   金額負值校驗（PRD-04）；parseNumber 的 || 0 在 HTML 層另外處理
//   v1.1     勞保／勞退通膨基準改鎖各自的請領年齡（PRD-10）

"use strict";

function calculate(p) {
  // PRD-04: 輸入校驗
  if (!(p.current_age > 0 && p.current_age < p.retirement_age && p.retirement_age < p.life_expectancy)) {
    throw new Error("年齡必須為正整數且 current_age < retirement_age < life_expectancy");
  }
  if (p.labor_insurance_start_age < 0 || p.labor_pension_start_age < 0) {
    throw new Error("請領年齡不得為負數");
  }
  const amounts = [
    p.current_savings, p.monthly_investment, p.monthly_expense_today,
    p.annual_recurring_expense, p.labor_insurance_pension,
    p.labor_pension_monthly, p.other_income,
  ];
  if (amounts.some((amt) => amt < 0)) {
    throw new Error("金額不得為負數");
  }
  for (const ls of p.lump_sums) {
    if (ls.age < 0) throw new Error("大筆支出年齡不得為負數");
    if (ls.amount < 0) throw new Error("大筆支出金額不得為負數");
  }

  // PRD-01: 累積期增值
  const months = (p.retirement_age - p.current_age) * 12;
  const r_monthly = p.pre_retirement_return / 12.0;
  let projected_savings;
  if (r_monthly === 0.0) {
    projected_savings = p.current_savings + p.monthly_investment * months;
  } else {
    const compounded_savings = p.current_savings * Math.pow(1.0 + r_monthly, months);
    const accumulated_investment = p.monthly_investment * ((Math.pow(1.0 + r_monthly, months) - 1.0) / r_monthly);
    projected_savings = compounded_savings + accumulated_investment;
  }

  const net_expenses = [];

  // PRD-02: 目標金額折現（共 A_d - A_r + 1 年，第一期對應 A_r）
  for (let t = p.retirement_age; t <= p.life_expectancy; t++) {
    // PRD-08: 固定年支出與月支出合併計算
    const expense_base_today = p.monthly_expense_today * 12 + p.annual_recurring_expense;
    // PRD-02, PRD-08: 支出端通膨基準鎖現齡 A_c
    let total_expense = expense_base_today * Math.pow(1.0 + p.inflation_rate, t - p.current_age);

    // PRD-05: 大筆支出區間，通膨基準鎖 A_c
    for (const ls of p.lump_sums) {
      if (ls.age === t) {
        total_expense += ls.amount * Math.pow(1.0 + p.inflation_rate, t - p.current_age);
      }
    }

    let total_income = 0.0;

    // PRD-06, PRD-10: 勞保年金，通膨基準鎖 A_p
    if (t >= p.labor_insurance_start_age && p.labor_insurance_start_age > 0) {
      total_income += p.labor_insurance_pension * 12 * Math.pow(1.0 + p.inflation_rate, t - p.labor_insurance_start_age);
    }

    // PRD-07, PRD-10: 勞退月領，通膨基準鎖 A_p
    if (t >= p.labor_pension_start_age && p.labor_pension_start_age > 0) {
      total_income += p.labor_pension_monthly * 12 * Math.pow(1.0 + p.inflation_rate, t - p.labor_pension_start_age);
    }

    // PRD-10: 其他收入視為今日幣值，通膨基準鎖 A_c
    total_income += p.other_income * 12 * Math.pow(1.0 + p.inflation_rate, t - p.current_age);

    // PRD-09: 淨支出下限 max(0, 支出 - 收入)
    const net_exp = Math.max(0.0, total_expense - total_income);
    net_expenses.push(net_exp);
  }

  let target_fund = 0.0;
  const balances = [];
  let current_balance = projected_savings;

  net_expenses.forEach((net_exp, idx) => {
    // PRD-02: 目標金額折現
    target_fund += net_exp / Math.pow(1.0 + p.post_retirement_return, idx);

    // PRD-03: 提領餘額軌跡，期初扣款，禁止 Math.max(0, ...) 截斷
    const balance_after_deduction = current_balance - net_exp;
    current_balance = balance_after_deduction * (1.0 + p.post_retirement_return);
    balances.push(current_balance);
  });

  return {
    projected_savings,
    target_fund,
    retirement_gap: target_fund - projected_savings,
    balances_raw: balances,
    // PRD-12: 圖表餘額保真，必須逐項等於 balances_raw，不得下限截斷
    balances_charted: balances,
  };
}

if (typeof module !== "undefined") {
  module.exports = { calculate };
}

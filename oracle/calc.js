/**
 * oracle/calc.js — 受測物計算核心的機械式抽取
 *
 * 來源：sut/進階退休規劃試算.html，第 292–375 行（calculateBtn 的 click handler 內）
 *
 * 抽取規則（Day 5 閘門 2 裁決）：
 *   1. 第 292–375 行的計算邏輯**逐行照抄**，運算順序、括號位置、變數名一律不動
 *   2. 原本從 DOM 讀取的輸入（274–290 行）改為函式參數
 *   3. 原本寫入 DOM 的輸出（377–402 行）改為回傳物件
 *   4. **不修正任何已知缺陷**——包括 293 行的無防護減法、297 行的 /12、
 *      321 行的期末折現、329 行的缺上界、374 行的夾 0。這是 oracle，不是修正版
 *
 * 本檔由 AI 產生，尚未經人工逐行比對驗收，尚未跑過差分測試。
 */

function calculate(input) {
  const {
    currentAge,
    retirementAge,
    lifeExpectancy,
    currentSavings,
    monthlyInvestment,
    totalMonthlyExpense,
    annualRecurringExpense = 0,
    laborInsurancePension = 0,
    laborInsuranceStartAge = 0,
    laborPensionMonthly = 0,
    laborPensionStartAge = 0,
    otherIncome = 0,
    preRetirementReturn,
    postRetirementReturn,
    inflationRate,
    largeExpenses = [],   // [{ age, amount }]
  } = input;

  // ---- 292-293 ----
  const workingYears = retirementAge - currentAge;
  const retirementYears = lifeExpectancy - retirementAge;   // 無防護

  // ---- 295-299 累積期 ----
  const fvCurrentSavings = currentSavings * Math.pow(1 + preRetirementReturn, workingYears);
  const monthlyPreReturn = preRetirementReturn / 12;        // 297 名目月利率
  const fvMonthlyInvestments = monthlyPreReturn > 0
    ? monthlyInvestment * (Math.pow(1 + monthlyPreReturn, workingYears * 12) - 1) / monthlyPreReturn
    : monthlyInvestment * workingYears * 12;
  const projectedSavings = fvCurrentSavings + fvMonthlyInvestments;

  // ---- 301-303 ----
  const totalAnnualExpense_today = totalMonthlyExpense * 12 + annualRecurringExpense;

  // ---- 305-323 目標金額：期末年金折現 ----
  let targetFundForExpenses = 0;
  for (let i = 1; i <= retirementYears; i++) {
    const age = retirementAge + i;
    const yearsFromNow = workingYears + i;

    const inflatedAnnualExpense = totalAnnualExpense_today * Math.pow(1 + inflationRate, yearsFromNow);

    let inflatedAnnualIncome = otherIncome * 12 * Math.pow(1 + inflationRate, yearsFromNow);
    if (age >= laborInsuranceStartAge) {
      inflatedAnnualIncome += laborInsurancePension * 12 * Math.pow(1 + inflationRate, yearsFromNow);
    }
    if (age >= laborPensionStartAge) {
      inflatedAnnualIncome += laborPensionMonthly * 12 * Math.pow(1 + inflationRate, yearsFromNow);
    }

    const netExpenseForYear = Math.max(0, inflatedAnnualExpense - inflatedAnnualIncome);
    const pvOfNetExpense = netExpenseForYear / Math.pow(1 + postRetirementReturn, i);
    targetFundForExpenses += pvOfNetExpense;
  }

  // ---- 325-334 大筆支出：只檢查下界 ----
  let totalLargeExpensePv = 0;
  largeExpenses.forEach(item => {
    const age = item.age;
    const amount = item.amount;
    if (age >= retirementAge) {
      const inflatedAmount = amount * Math.pow(1 + inflationRate, age - currentAge);
      const pvAtRetirement = inflatedAmount / Math.pow(1 + postRetirementReturn, age - retirementAge);
      totalLargeExpensePv += pvAtRetirement;
    }
  });

  const targetFund = targetFundForExpenses + totalLargeExpensePv;   // 335

  // ---- 337-346 圖表：累積期 ----
  const chartLabels = [], assetData = [];
  for (let i = 0; i <= workingYears; i++) {
    const age = currentAge + i;
    const fvS = currentSavings * Math.pow(1 + preRetirementReturn, i);
    const fvM = monthlyPreReturn > 0
      ? monthlyInvestment * (Math.pow(1 + monthlyPreReturn, i * 12) - 1) / monthlyPreReturn
      : monthlyInvestment * i * 12;
    chartLabels.push(age);
    assetData.push(fvS + fvM);
  }

  // ---- 347-375 圖表：提領期 ----
  let remainingFund = projectedSavings;
  const balancesRaw = [];          // 抽取時新增：未夾 0 的真實餘額
  for (let i = 1; i <= retirementYears; i++) {
    const age = retirementAge + i;
    const yearsFromNow = workingYears + i;

    const inflatedAnnualExpense = totalAnnualExpense_today * Math.pow(1 + inflationRate, yearsFromNow);

    let inflatedAnnualIncome = otherIncome * 12 * Math.pow(1 + inflationRate, yearsFromNow);
    if (age >= laborInsuranceStartAge) {
      inflatedAnnualIncome += laborInsurancePension * 12 * Math.pow(1 + inflationRate, yearsFromNow);
    }
    if (age >= laborPensionStartAge) {
      inflatedAnnualIncome += laborPensionMonthly * 12 * Math.pow(1 + inflationRate, yearsFromNow);
    }

    const netAnnualExpense = Math.max(0, inflatedAnnualExpense - inflatedAnnualIncome);

    let largeExpenseForYear = 0;
    largeExpenses.forEach(item => {
      if (item.age === age) {
        largeExpenseForYear += item.amount * Math.pow(1 + inflationRate, age - currentAge);
      }
    });

    remainingFund = (remainingFund - (netAnnualExpense + largeExpenseForYear)) * (1 + postRetirementReturn);
    chartLabels.push(age);
    balancesRaw.push(remainingFund);
    assetData.push(Math.max(0, remainingFund));   // 374 遮羞布
  }

  // ---- 380 ----
  const retirementGap = targetFund - projectedSavings;

  return { projectedSavings, targetFund, retirementGap, chartLabels, assetData, balancesRaw };
}

if (typeof module !== 'undefined') { module.exports = { calculate }; }

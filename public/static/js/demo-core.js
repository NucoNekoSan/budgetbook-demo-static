/* Pure accounting model. No network, DOM, or storage access. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.BudgetDemo = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const clone = value => JSON.parse(JSON.stringify(value));
  function validDate(value) {
    return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number(value.slice(0, 4)) >= 1900 &&
      Number(value.slice(0, 4)) <= 2100 && !Number.isNaN(Date.parse(value + 'T00:00:00Z')) &&
      new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) === value;
  }
  function totals(state, period) {
    const categories = new Map(state.categories.map(x => [x.id, x]));
    let income = 0, expense = 0;
    const sections = {}, monthly = {};
    for (const t of state.transactions) {
      if (!t.date.startsWith(period)) continue;
      const c = categories.get(t.category_id), m = t.date.slice(0, 7);
      monthly[m] ||= {income: 0, expense: 0};
      if (c.kind === 'income') { income += t.amount; monthly[m].income += t.amount; }
      else { expense += t.amount; monthly[m].expense += t.amount; sections[c.section] = (sections[c.section] || 0) + t.amount; }
    }
    return {income, expense, net: income - expense, sections, monthly};
  }
  function balances(state, end) {
    const result = Object.fromEntries(state.accounts.map(a => [a.id, a.opening_balance]));
    const cats = new Map(state.categories.map(c => [c.id, c]));
    for (const t of state.transactions) if (t.date <= end) result[t.account_id] += (cats.get(t.category_id).kind === 'income' ? 1 : -1) * t.amount;
    for (const t of state.transfers) if (t.date <= end) { result[t.from_account_id] -= t.amount; result[t.to_account_id] += t.amount; }
    return result;
  }
  function budgetSummary(state, month) {
    const spent = totals(state, month).sections;
    return Object.entries(state.sections).map(([section, name]) => {
      const budget = state.budgets.find(b => b.month.slice(0, 7) === month && b.section === section)?.amount || 0;
      return {section, name, budget, spent: spent[section] || 0, remaining: budget - (spent[section] || 0), percent: budget ? (spent[section] || 0) / budget * 100 : null};
    });
  }
  function checkClosed(state, date, original) {
    if ([date, original?.date].filter(Boolean).some(d => state.closedMonths.includes(d.slice(0, 7)))) throw Error('締め済みの月は変更できません。日付を移す場合は変更前の月も確認します。');
  }
  function validate(state, type, row, original) {
    if (!Number.isSafeInteger(row.amount) || row.amount < (type === 'budgets' ? 0 : 1)) throw Error('金額は整数の円で入力してください。');
    if (type === 'budgets') {
      if (!/^\d{4}-\d{2}-01$/.test(row.month) || !validDate(row.month) || !Object.hasOwn(state.sections, row.section)) throw Error('対象月・区分が正しくありません。');
      if ((row.notes || '').length > 500) throw Error('メモは500文字以内で入力してください。');
      return;
    }
    if (!validDate(row.date)) throw Error('有効な日付を入力してください（1900〜2100年）。');
    checkClosed(state, row.date, original);
    const account = id => state.accounts.some(a => a.id === id && (a.is_active || [original?.account_id, original?.from_account_id, original?.to_account_id].includes(id)));
    if (type === 'transactions') {
      if (!account(row.account_id) || !state.categories.some(c => c.id === row.category_id && (c.is_active || original?.category_id === c.id))) throw Error('有効な口座とカテゴリを選択してください。');
    } else if (!account(row.from_account_id) || !account(row.to_account_id) || row.from_account_id === row.to_account_id) throw Error('振替元と振替先には異なる口座を選択してください。');
    if (!(row.description || '').trim() || row.description.length > 120 || (row.memo || '').length > 500) throw Error('摘要は1〜120文字、メモは500文字以内で入力してください。');
  }
  function save(state, type, row) {
    if (!['transactions', 'transfers', 'budgets'].includes(type)) throw Error('変更対象が正しくありません。');
    let index = row.id == null ? -1 : state[type].findIndex(x => x.id === row.id);
    if (row.id != null && index < 0) throw Error('変更対象が見つかりません。');
    if (type === 'budgets' && index < 0) index = state.budgets.findIndex(x => x.month === row.month && x.section === row.section);
    if (type === 'budgets' && state.budgets.some((b, i) => i !== index && b.month === row.month && b.section === row.section)) throw Error('同じ月・区分の予算が既にあります。既存の予算から変更してください。');
    validate(state, type, row, state[type][index]);
    const next = clone(state);
    const value = {...row, id: index < 0 ? Math.max(0, ...next[type].map(x => x.id)) + 1 : next[type][index].id};
    if (index < 0) next[type].push(value); else next[type][index] = value;
    return next;
  }
  function remove(state, type, id) {
    if (!['transactions', 'transfers'].includes(type)) throw Error('削除対象が正しくありません。');
    const row = state[type].find(x => x.id === id);
    if (!row) throw Error('削除対象が見つかりません。');
    checkClosed(state, row.date, row);
    const next = clone(state); next[type] = next[type].filter(x => x.id !== id); return next;
  }
  return {clone, validDate, totals, balances, budgetSummary, save, remove};
});

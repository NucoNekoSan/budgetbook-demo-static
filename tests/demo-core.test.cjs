const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../public/static/js/demo-core.js');
const fixture = require('../public/demo-data.json');
const state = () => ({schema:1,accounts:[{id:1,kind:'asset',name:'Cash',opening_balance:1000,is_active:true},{id:2,kind:'asset',name:'Bank',opening_balance:2000,is_active:true},{id:3,kind:'liability',name:'Card',opening_balance:-500,is_active:true}],categories:[{id:1,kind:'expense',section:'living',is_active:true},{id:2,kind:'income',section:'other',is_active:true}],sections:{living:'Living'},transactions:[],transfers:[],budgets:[],closedMonths:['2026-08']});
const expense = {date:'2026-09-15',account_id:1,category_id:1,amount:100,description:'Lunch',memo:''};
test('transaction CRUD updates net, section budgets, balances without mutating original',()=>{
  let s=state();const original=C.clone(s);s=C.save(s,'transactions',expense);
  assert.deepEqual(C.totals(s,'2026-09').net,-100);assert.equal(C.balances(s,'2026-09-30')[1],900);
  assert.equal(C.budgetSummary(s,'2026-09')[0].spent,100);
  s=C.save(s,'transactions',{...expense,id:1,amount:150});assert.equal(C.totals(s,'2026').expense,150);
  s=C.remove(s,'transactions',1);assert.equal(C.totals(s,'2026').expense,0);assert.deepEqual(s.transactions,original.transactions);
});
test('transfers move balances and leave net assets/income/expense unchanged',()=>{
  let s=state();s=C.save(s,'transfers',{date:'2026-09-02',from_account_id:1,to_account_id:3,amount:100,description:'Card payment'});
  assert.deepEqual(C.balances(s,'2026-09-30'),{1:900,2:2000,3:-400});
  assert.equal(Object.values(C.balances(s,'2026-09-30')).reduce((n,v)=>n+v,0),2500);
  assert.equal(C.totals(s,'2026').net,0);
  assert.throws(()=>C.save(s,'transfers',{...s.transfers[0],to_account_id:1}),/異なる/);
});
test('closed-month checks include original month when moving an entry out',()=>{
  const s=state();s.transactions=[{...expense,id:1,date:'2026-08-15'}];
  assert.throws(()=>C.save(s,'transactions',{...expense,id:1}),/締め済み/);
  assert.throws(()=>C.remove(s,'transactions',1),/締め済み/);
  assert.throws(()=>C.save(s,'transactions',{...expense,date:'2026-08-15'}),/締め済み/);
});
test('date validation rejects rollover and validates leap years',()=>{
  assert.equal(C.validDate('2026-02-29'),false);assert.equal(C.validDate('2024-02-29'),true);
  for(const date of ['2026-13-01','2026-04-31','2026-00-10','2101-01-01','1'])assert.equal(C.validDate(date),false);
});
test('budgets are month-specific; zero is unset; upsert unique month/section',()=>{
  let s=C.save(state(),'budgets',{month:'2026-09-01',section:'living',amount:500,notes:''});
  s=C.save(s,'transactions',expense);assert.equal(C.budgetSummary(s,'2026-09')[0].percent,20);
  assert.equal(C.budgetSummary(s,'2026-10')[0].budget,0);
  s=C.save(s,'budgets',{month:'2026-09-01',section:'living',amount:0});assert.equal(s.budgets.length,1);
  assert.equal(C.budgetSummary(s,'2026-09')[0].percent,null);
});
test('invalid fields and unsafe amounts rejected; text preserved as text',()=>{
  for(const amount of [0,-1,0.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1])assert.throws(()=>C.save(state(),'transactions',{...expense,amount}));
  assert.throws(()=>C.save(state(),'transactions',{...expense,category_id:99}));
  assert.equal(C.save(state(),'transactions',{...expense,description:'<script>alert(1)</script>'}).transactions[0].description,'<script>alert(1)</script>');
});
test('seed balances include full history and agree with exported Django references',()=>{
  assert.equal(fixture.provenance,'fresh-synthetic-seed');
  assert.ok(fixture.transactions.length>100);
  for(const ref of fixture.references || []) {
    assert.deepEqual(C.balances(fixture,ref.end),ref.balances);
    const t=C.totals(fixture,ref.month);assert.equal(t.income,ref.income);assert.equal(t.expense,ref.expense);
  }
  assert.ok(fixture.references?.length,'Django comparison references required');
});

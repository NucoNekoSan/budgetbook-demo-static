/* Portfolio sandbox: every write stays in this tab's sessionStorage. */
(async function () {
  'use strict';
  const loader = document.querySelector('script[data-demo-root]');
  if (!loader) return;
  const base = new URL(loader.dataset.demoRoot, location.href), C = window.BudgetDemo;
  const key = 'budgetbook-portfolio-session-v1';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const yen = value => `${Number(value).toLocaleString('ja-JP')}円`;
  const main = document.getElementById('main');
  const route = loader.dataset.demoRoute;
  const active = ['dashboard', 'annual', 'balance-sheet', 'expense-breakdown', 'budgets'].includes(route);
  const banner = document.createElement('aside');
  banner.className = 'portfolio-banner';
  banner.setAttribute('aria-label', '公開デモについて');
  banner.innerHTML = `<div><strong>BudgetBook / 体験デモ</strong><span>架空の4人家族のデータです。取引・振替・予算を変更して、集計の変化を試せます。</span></div><div class="demo-actions"><button type="button" data-demo="guide">使い方</button><button type="button" data-demo="reset">データをリセット</button><a href="https://nuconeko-garden.com/blog/budgetbook-read-only-demo/">開発記事</a><a href="https://github.com/NucoNekoSan/budgetbook-demo" target="_blank" rel="noopener">GitHub ↗</a></div><small>変更はこのタブ内だけに保存されます。同じタブでの再読み込み・画面移動に対応し、タブを閉じると終了します。サーバーへの保存はありません。</small>`;
  document.body.prepend(banner);
  const notice = document.createElement('p'); notice.className = 'demo-notice'; notice.setAttribute('role', 'status'); notice.setAttribute('aria-live', 'polite');
  banner.after(notice);
  let seed, state, month, year, filter = '', categoryFilter = '', page = 1, tableType = 'transactions', charts = [], previousFocus;
  function message(text) { notice.textContent = text; }
  try {
    const response = await fetch(new URL('demo-data.json', base));
    if (!response.ok) throw Error('デモデータを取得できませんでした。');
    seed = await response.json();
    if (seed.schema !== 1 || seed.provenance !== 'fresh-synthetic-seed') throw Error('デモデータの形式が一致しません。');
    state = C.clone(seed);
    try {
      const stored = JSON.parse(sessionStorage.getItem(key));
      if (stored && stored.generated === seed.generated && stored.schema === seed.schema) state = stored;
    } catch { message('このブラウザーではタブ内保存が使えません。画面を移動すると変更は初期化されます。'); }
  } catch (error) { message(error.message + ' 再読み込みしてお試しください。'); return; }
  const variantMonth = location.pathname.match(/(\d{4}-\d{2})/);
  const variantYear = location.pathname.match(/(?:\/|year-)(\d{4})(?:\/|\.html)/);
  month = new URLSearchParams(location.search).get('month') || variantMonth?.[1] || seed.generated.slice(0, 7);
  if (!C.validDate(month + '-01')) month = seed.generated.slice(0, 7);
  year = new URLSearchParams(location.search).get('year') || variantYear?.[1] || month.slice(0, 4);
  if (!/^\d{4}$/.test(year) || +year < 1900 || +year > 2100) year = month.slice(0, 4);
  const dialog = document.createElement('dialog'); dialog.className = 'demo-dialog'; dialog.setAttribute('aria-label', 'BudgetBook デモ操作'); document.body.append(dialog);
  function close() { dialog.close(); previousFocus?.focus(); }
  function open(content) {
    previousFocus = document.activeElement; dialog.innerHTML = content;
    dialog.showModal(); dialog.querySelector('input, select, button')?.focus();
  }
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  function persist(next) {
    state = next;
    try { sessionStorage.setItem(key, JSON.stringify(state)); }
    catch { message('保存領域を利用できません。変更はこの画面を開いている間だけ有効です。'); return false; }
    return true;
  }
  function opts(rows, selected) { return rows.map(r => `<option value="${escape(r.id)}" ${String(r.id) === String(selected) ? 'selected' : ''}>${escape(r.name)}</option>`).join(''); }
  function field(label, input) { return `<label>${label}${input}</label>`; }
  function form(type, id) {
    const existing = id == null ? null : state[type].find(x => x.id === id);
    const row = existing || {date: month + '-15', month: month + '-01', amount: '', description: '', memo: ''};
    const accounts = state.accounts.filter(a => a.is_active || [row.account_id, row.from_account_id, row.to_account_id].includes(a.id));
    const categories = state.categories.filter(c => c.is_active || c.id === row.category_id);
    let fields;
    if (type === 'budgets') {
      fields = field('対象月', `<input name="month" type="month" value="${escape(month)}" required min="1900-01" max="2100-12">`) +
        field('区分', `<select name="section">${Object.entries(state.sections).map(([s,n]) => `<option value="${escape(s)}" ${s === row.section ? 'selected' : ''}>${escape(n)}</option>`).join('')}</select>`) +
        field('予算（円・0は未設定）', `<input name="amount" type="number" min="0" max="1000000000000" step="1" value="${escape(row.amount)}" required>`) +
        field('メモ', `<textarea name="notes" maxlength="500">${escape(row.notes)}</textarea>`);
    } else {
      fields = field('日付', `<input name="date" type="date" min="1900-01-01" max="2100-12-31" value="${escape(row.date)}" required>`);
      if (type === 'transactions') fields += field('口座', `<select name="account_id">${opts(accounts,row.account_id)}</select>`) + field('カテゴリ（収入 / 支出）', `<select name="category_id">${opts(categories.map(c=>({...c,name:`${c.kind === 'income' ? '収入' : '支出'} / ${c.name}`})),row.category_id)}</select>`);
      else fields += field('振替元', `<select name="from_account_id">${opts(accounts,row.from_account_id)}</select>`) + field('振替先', `<select name="to_account_id">${opts(accounts,row.to_account_id || accounts[1]?.id)}</select>`);
      fields += field('金額（円）', `<input name="amount" type="number" min="1" max="1000000000000" step="1" value="${escape(row.amount)}" required>`) + field('摘要', `<input name="description" maxlength="120" value="${escape(row.description)}" required>`) + field('メモ', `<textarea name="memo" maxlength="500">${escape(row.memo)}</textarea>`);
    }
    open(`<h2>${type === 'budgets' ? '月別予算' : type === 'transfers' ? '口座間振替' : '取引'}${existing ? 'を編集' : 'を追加'}</h2><form id="demo-edit" data-type="${type}" ${existing ? `data-id="${existing.id}"` : ''}><div class="demo-form-grid">${fields}</div><p id="demo-error" role="alert"></p><div class="demo-actions"><button type="submit">保存して集計に反映</button><button type="button" data-demo="close">キャンセル</button></div></form>`);
  }
  dialog.addEventListener('submit', event => {
    event.preventDefault(); const formEl = event.target;
    if (formEl.id !== 'demo-edit') return;
    const row = Object.fromEntries(new FormData(formEl));
    row.amount = Number(row.amount);
    for (const key of ['account_id','category_id','from_account_id','to_account_id']) if (key in row) row[key] = Number(row[key]);
    if (row.month) row.month += '-01';
    if (formEl.dataset.id) row.id = Number(formEl.dataset.id);
    try { const saved = persist(C.save(state, formEl.dataset.type, row)); close(); render(); if (saved) message('変更をこのタブに保存しました。集計に反映しています。'); }
    catch (e) { dialog.querySelector('#demo-error').textContent = e.message; }
  });
  function endOfMonth() { return new Date(Date.UTC(+month.slice(0,4), +month.slice(5), 0)).toISOString().slice(0,10); }
  function summary(period) {
    const t = C.totals(state, period);
    return `<div class="demo-kpis">${[['収入',t.income],['支出',t.expense],['収支',t.net]].map(([name,value]) => `<section class="card"><span>${name}</span><strong>${yen(value)}</strong></section>`).join('')}</div>`;
  }
  function budgetTable(editable) {
    const rows = C.budgetSummary(state,month);
    return `<div class="card"><h2>区分別の予算と支出</h2><p>予算は選択した月の設定です。0円は未設定として扱います。</p><div class="demo-table-scroll"><table><thead><tr><th>区分</th><th>予算</th><th>支出</th><th>残り</th><th>消化率</th>${editable ? '<th>操作</th>' : ''}</tr></thead><tbody>${rows.filter(r=>editable || r.budget || r.spent).map(r=>`<tr><th scope="row">${escape(r.name)}</th><td>${r.budget ? yen(r.budget) : '未設定'}</td><td>${yen(r.spent)}</td><td>${r.budget ? yen(r.remaining) : '—'}</td><td>${r.percent == null ? '—' : `${r.percent.toFixed(1)}%`}</td>${editable ? `<td><button data-demo="budget" data-section="${escape(r.section)}">変更</button></td>` : ''}</tr>`).join('')}</tbody></table></div></div>`;
  }
  function balanceTable() {
    const balances = C.balances(state,endOfMonth());
    const assets = state.accounts.filter(a=>a.kind==='asset').reduce((n,a)=>n+balances[a.id],0);
    const debts = -state.accounts.filter(a=>a.kind==='liability').reduce((n,a)=>n+balances[a.id],0);
    return `<div class="card"><h2>月末の資産・負債</h2><p>資産 ${yen(assets)} / 負債 ${yen(debts)} / 純資産 ${yen(assets-debts)}</p><div class="demo-table-scroll"><table><thead><tr><th>口座</th><th>区分</th><th>帳簿残高</th></tr></thead><tbody>${state.accounts.map(a=>`<tr><th scope="row">${escape(a.name)}${a.is_active ? '' : '（無効）'}</th><td>${a.kind==='asset'?'資産':'負債'}</td><td>${yen(balances[a.id])}</td></tr>`).join('')}</tbody></table></div><p>開始残高から全履歴を集計しています。負債口座の帳簿残高はマイナスで表示します。</p></div>`;
  }
  function ledger() {
    const cats = new Map(state.categories.map(c=>[c.id,c]));
    const accounts = new Map(state.accounts.map(a=>[a.id,a.name]));
    const rows = state[tableType].filter(t=>t.date.startsWith(month) && (!categoryFilter || tableType==='transfers' || String(t.category_id)===categoryFilter) && `${t.description} ${t.memo}`.toLowerCase().includes(filter.toLowerCase())).sort((a,b)=>b.date.localeCompare(a.date)||b.id-a.id);
    const pages = Math.max(1,Math.ceil(rows.length/20)); page = Math.min(page,pages);
    return `<section class="card"><h2>取引を試す</h2><div class="demo-actions"><button data-demo="tab" data-type="transactions" aria-pressed="${tableType==='transactions'}">収入・支出</button><button data-demo="tab" data-type="transfers" aria-pressed="${tableType==='transfers'}">口座間振替</button><button data-demo="add" data-type="${tableType}">${tableType==='transactions'?'取引':'振替'}を追加</button></div><form id="demo-filter" class="demo-filters">${field('摘要・メモで検索',`<input name="query" value="${escape(filter)}" type="search">`)}${tableType==='transactions'?field('カテゴリ',`<select name="category"><option value="">すべて</option>${opts(state.categories,categoryFilter)}</select>`):''}<button type="submit">絞り込む</button></form><p>${rows.length}件 / ${page}ページ目</p><div class="demo-table-scroll"><table><thead><tr><th>日付</th><th>摘要 / カテゴリ・口座</th><th>金額</th><th>操作</th></tr></thead><tbody>${rows.slice((page-1)*20,page*20).map(t=>`<tr><td>${escape(t.date)}</td><td><strong>${escape(t.description)}</strong><br><small>${tableType==='transactions'?`${escape(cats.get(t.category_id).name)} / ${escape(accounts.get(t.account_id))}`:`${escape(accounts.get(t.from_account_id))} → ${escape(accounts.get(t.to_account_id))}`}</small></td><td>${tableType==='transactions'?(cats.get(t.category_id).kind==='income'?'+':'−'):''}${yen(t.amount)}</td><td><button data-demo="edit" data-type="${tableType}" data-id="${t.id}">編集</button> <button data-demo="delete" data-type="${tableType}" data-id="${t.id}">削除</button></td></tr>`).join('') || '<tr><td colspan="4">該当するデータがありません。</td></tr>'}</tbody></table></div><div class="demo-actions"><button data-demo="page" data-page="${page-1}" ${page<=1?'disabled':''}>前へ</button><button data-demo="page" data-page="${page+1}" ${page>=pages?'disabled':''}>次へ</button></div><p>振替は収入・支出に含めず、口座残高だけに反映します。</p></section>`;
  }
  function render() {
    if (!active) return;
    charts.forEach(c=>c.destroy()); charts=[];
    const annual = route === 'annual';
    const titles = {dashboard:'家計のダッシュボード',annual:'年間の収支', 'balance-sheet':'資産・負債の状況','expense-breakdown':'支出の内訳',budgets:'月別予算の設定'};
    main.classList.add('portfolio-main');
    main.innerHTML = `<header class="demo-page-heading"><div><p class="demo-eyebrow">BUDGETBOOK · SAMPLE HOUSEHOLD</p><h1>${titles[route]}</h1></div><form id="demo-period">${field(annual?'対象年':'対象月',`<input name="period" type="${annual?'number':'month'}" value="${annual?year:month}" min="${annual?'1900':'1900-01'}" max="${annual?'2100':'2100-12'}" required>`)}<button type="submit">表示</button></form></header><nav class="demo-subnav" aria-label="体験できる画面">${Object.entries(titles).map(([r,t])=>`<a ${r===route?'aria-current="page"':''} href="${new URL(r==='dashboard'?'index.html':r+'/index.html',base).href}?month=${month}&year=${year}">${t}</a>`).join('')}</nav>`;
    if (route === 'balance-sheet') main.innerHTML += balanceTable();
    else if (route === 'budgets') main.innerHTML += budgetTable(true);
    else if (route === 'annual') {
      const totals = C.totals(state,year);
      main.innerHTML += summary(year) + `<section class="card"><h2>月別の収入と支出</h2><div class="demo-chart"><canvas id="demo-chart" aria-label="月別の収入と支出。数値は以下の表にも記載しています。" role="img"></canvas></div><div class="demo-table-scroll"><table><thead><tr><th>月</th><th>収入</th><th>支出</th><th>収支</th></tr></thead><tbody>${Array.from({length:12},(_,i)=>{const m=`${year}-${String(i+1).padStart(2,'0')}`,t=totals.monthly[m]||{income:0,expense:0};return `<tr><th scope="row">${i+1}月</th><td>${yen(t.income)}</td><td>${yen(t.expense)}</td><td>${yen(t.income-t.expense)}</td></tr>`;}).join('')}</tbody></table></div></section>`;
      chart('bar',Array.from({length:12},(_,i)=>`${i+1}月`),['income','expense'].map((k,i)=>({label:i?'支出':'収入',data:Array.from({length:12},(_,n)=>totals.monthly[`${year}-${String(n+1).padStart(2,'0')}`]?.[k]||0),backgroundColor:i?'#f59e0b':'#3b82f6'})));
    } else {
      main.innerHTML += summary(month);
      if (route === 'dashboard') main.innerHTML += ledger() + budgetTable(false) + balanceTable();
      else {
        const rows = Object.entries(C.totals(state,month).sections);
        main.innerHTML += `<section class="card"><h2>区分ごとの支出</h2><div class="demo-chart"><canvas id="demo-chart" role="img" aria-label="区分別の支出。金額は下の表でも確認できます。"></canvas></div></section>` + budgetTable(false);
        chart('doughnut',rows.map(([s])=>state.sections[s]),[{data:rows.map(([,v])=>v),backgroundColor:['#3b82f6','#14b8a6','#f59e0b','#a78bfa','#fb7185','#64748b','#84cc16','#06b6d4']}]);
      }
    }
    main.insertAdjacentHTML('beforeend', '<p class="demo-footnote">医療・保険・税務・月次締め・照合・ローン戦略は、別画面で初期サンプルを閲覧できます。これらの画面はこのタブでの変更を反映しません。</p>');
  }
  function chart(type,labels,datasets) {
    if (!window.Chart) return;
    charts.push(new Chart(document.getElementById('demo-chart'),{type,data:{labels,datasets},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{labels:{color:getComputedStyle(main).color}}}}}));
  }
  new MutationObserver(() => charts.forEach(c => { c.options.plugins.legend.labels.color = getComputedStyle(main).color; c.update(); })).observe(document.documentElement, {attributes:true, attributeFilter:['data-theme']});
  main.addEventListener('submit',event=>{
    if (!['demo-period','demo-filter'].includes(event.target.id)) return;
    event.preventDefault(); const values = Object.fromEntries(new FormData(event.target));
    if (event.target.id==='demo-period') {
      if (route==='annual') year=values.period; else {month=values.period;year=month.slice(0,4);}
      page=1; const url = new URL(location.href);url.searchParams.set('month',month);url.searchParams.set('year',year);history.replaceState(null,'',url);
    } else {filter=values.query||'';categoryFilter=values.category||'';page=1;}
    render();
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-demo]'); if (!button) return;
    event.preventDefault();
    const action=button.dataset.demo, type=button.dataset.type, id=Number(button.dataset.id);
    if (action==='close') close();
    if (action==='guide') open('<h2>3分で試すBudgetBook</h2><ol><li>ダッシュボードで食費などの取引を追加します。</li><li>収支と予算の残額が変わることを確認します。</li><li>口座間振替を追加し、収支を変えずに残高が動くことを確認します。</li><li>年間収支・資産負債・支出内訳の画面で変化を見ます。</li></ol><p>変更はこのタブ内だけに保存されます。別のタブ・別の端末とは共有されません。医療・保険・税務などは初期サンプルの閲覧専用です。</p><button data-demo="close">閉じる</button>');
    if (action==='reset') open('<h2>デモデータをリセット</h2><p>このタブで追加・変更・削除したデータを破棄し、初期サンプルに戻します。</p><div class="demo-actions"><button data-demo="confirm-reset">初期データに戻す</button><button data-demo="close">キャンセル</button></div>');
    if (action==='confirm-reset') {const saved=persist(C.clone(seed));close();render();if(saved)message('初期データに戻しました。');}
    if (action==='add'||action==='edit') form(type,action==='edit'?id:null);
    if (action==='delete') open(`<h2>この${type==='transactions'?'取引':'振替'}を削除しますか？</h2><p>削除すると収支・残高・予算集計を更新します。</p><div class="demo-actions"><button data-demo="confirm-delete" data-type="${type}" data-id="${id}">削除する</button><button data-demo="close">キャンセル</button></div>`);
    if (action==='confirm-delete') {try{const saved=persist(C.remove(state,type,id));close();render();if(saved)message('削除を集計に反映しました。');}catch(e){close();message(e.message);}}
    if (action==='tab') {tableType=type;page=1;categoryFilter='';render();}
    if (action==='page') {page=Number(button.dataset.page);render();}
    if (action==='budget') {const b=state.budgets.find(b=>b.month.slice(0,7)===month&&b.section===button.dataset.section);form('budgets',b?.id);dialog.querySelector('[name="section"]').value=button.dataset.section;}
  });
  if (active) render();
  else {const note=document.createElement('p');note.className='demo-snapshot-note';note.textContent='この画面は初期サンプルの閲覧専用です。取引・振替・予算の体験画面で行った変更は反映しません。';main?.prepend(note);}
})();

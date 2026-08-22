<script>
"use strict";
const D = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s), $$ = s => Array.from(document.querySelectorAll(s));
const fmt = n => Math.round(n || 0).toLocaleString('uk-UA').replace(/ /g, ' ');
const kfmt = n => { n = Math.round(n || 0); return n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : n >= 1e4 ? Math.round(n / 1e3) + 'K' : fmt(n); };
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = (a, b) => b ? Math.round((a - b) / b * 100) : (a ? 100 : 0);
const sign = v => (v > 0 ? '+' : '') + v;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const GC = D.group_colors, GL = D.group_labels;
const GROUPS = ['site_ua','b2b','intl','bot','manual','social_leads','other'];
const DATES = D.dates, DI = {}; DATES.forEach((d, i) => DI[d] = i);
const CH = D.ch_list, CHG = D.ch_group, NDAY = DATES.length;
const idx = d => { const i = DI[d]; return i === undefined ? -1 : i; };
const dayAdd = (d, n) => { const t = new Date(d + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); };
const dayDiff = (a, b) => Math.round((new Date(b + 'T00:00:00Z') - new Date(a + 'T00:00:00Z')) / 86400000);
const NS = 'http://www.w3.org/2000/svg';

const S = { p: 'mtd', from: D.period_cur[0], to: D.period_cur[1], metric: 'revenue',
  groups: new Set(GROUPS), q: '', stock: 'all', mod: 'src', sort: {}, charts: {} };
const METRIC_LABEL = { revenue: 'виручка, ₴', orders: 'замовлення', margin: 'маржа, ₴', aov: 'середній чек, ₴' };
const mval = a => S.metric === 'revenue' ? a.r : S.metric === 'orders' ? a.o : S.metric === 'margin' ? a.m : (a.o ? a.r / a.o : 0);
const munit = () => S.metric === 'orders' ? '' : ' ₴';

function periodRange() {
  if (S.p === 'mtd') return [D.period_cur[0], D.period_cur[1]];
  if (S.p === 'prev') return [D.prev_month_full[0], D.prev_month_full[1]];
  if (S.p === 'custom') return [S.from, S.to];
  const n = { '7d': 7, '14d': 14, '30d': 30, '90d': 90 }[S.p] || 30;
  return [dayAdd(D.today, -(n - 1)), D.today];
}
function comparePrev(a, b) {
  if (S.p === 'mtd') return [D.period_prev[0], D.period_prev[1]];
  const len = dayDiff(a, b) + 1; return [dayAdd(a, -len), dayAdd(a, -1)];
}
function slice(a, b) {
  const i0 = idx(a) < 0 ? 0 : idx(a), i1 = idx(b) < 0 ? NDAY - 1 : idx(b);
  const byCh = {}, byGroup = {}, daily = {}, tot = { o: 0, r: 0, m: 0, c: 0 };
  const n = Math.max(0, i1 - i0 + 1);
  const dR = new Array(n).fill(0), dO = new Array(n).fill(0), dM = new Array(n).fill(0);
  GROUPS.forEach(g => { byGroup[g] = { o: 0, r: 0, m: 0, c: 0 }; daily[g] = new Array(n).fill(0); });
  for (const f of D.facts) {
    if (f[0] < i0 || f[0] > i1) continue;
    const ch = CH[f[1]], g = CHG[ch] || 'other';
    if (!S.groups.has(g)) continue;
    const t = byCh[ch] || (byCh[ch] = { o: 0, r: 0, m: 0, c: 0, g });
    t.o += f[2]; t.r += f[3]; t.m += f[4]; t.c += f[5];
    byGroup[g].o += f[2]; byGroup[g].r += f[3]; byGroup[g].m += f[4]; byGroup[g].c += f[5];
    daily[g][f[0] - i0] += f[3];
    dR[f[0] - i0] += f[3]; dO[f[0] - i0] += f[2]; dM[f[0] - i0] += f[4];
    tot.o += f[2]; tot.r += f[3]; tot.m += f[4]; tot.c += f[5];
  }
  return { byCh, byGroup, daily, tot, i0, i1, dR, dO, dM, labels: DATES.slice(i0, i1 + 1) };
}
function sliceFacts(facts, a, b, keyPos, valPos) {
  const i0 = idx(a) < 0 ? 0 : idx(a), i1 = idx(b) < 0 ? NDAY - 1 : idx(b), out = {};
  for (const f of facts) { if (f[0] < i0 || f[0] > i1) continue;
    const t = out[f[keyPos]] || (out[f[keyPos]] = valPos.map(() => 0)); valPos.forEach((p, j) => t[j] += f[p]); }
  return out;
}
const PIPE_CH = {}; (D.pipeline.by_channel || []).forEach(p => PIPE_CH[p.channel] = p);
const cmp = (a, b) => typeof a === 'string' ? a.localeCompare(b, 'uk') : (a || 0) - (b || 0);

/* ── SVG helpers ───────────────────────────────────── */
const pol = (cx, cy, r, deg) => [cx + r * Math.cos((deg - 90) * Math.PI / 180), cy + r * Math.sin((deg - 90) * Math.PI / 180)];
function arcPath(cx, cy, r, a0, a1) {
  const [x0, y0] = pol(cx, cy, r, a0), [x1, y1] = pol(cx, cy, r, a1);
  return `M ${x0} ${y0} A ${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`;
}
function sectorPath(cx, cy, r0, r1, a0, a1) {
  const [ax, ay] = pol(cx, cy, r1, a0), [bx, by] = pol(cx, cy, r1, a1);
  const [cx2, cy2] = pol(cx, cy, r0, a1), [dx, dy] = pol(cx, cy, r0, a0);
  const big = a1 - a0 > 180 ? 1 : 0;
  return `M ${ax} ${ay} A ${r1} ${r1} 0 ${big} 1 ${bx} ${by} L ${cx2} ${cy2} A ${r0} ${r0} 0 ${big} 0 ${dx} ${dy} Z`;
}

function chanRows() {
  const rows = Object.entries(CUR.byCh).map(([ch, a]) => {
    const pv = PRV.byCh[ch] || { o: 0, r: 0, m: 0, c: 0 }, pipe = PIPE_CH[ch];
    return { channel: ch, group: a.g, orders: a.o, revenue: a.r, margin: a.m, cancelled: a.c,
      aov: a.o ? Math.round(a.r / a.o) : 0, mrate: a.r ? Math.round(a.m / a.r * 100) : 0,
      prev: pv.r, delta: pct(a.r, pv.r), pipe: pipe ? pipe.sum : 0, metric: mval(a) };
  }).filter(r => r.revenue > 0 || r.cancelled > 0 || r.pipe > 0);
  if (S.q) { const q = S.q.toLowerCase(); return rows.filter(r => r.channel.toLowerCase().includes(q)); }
  return rows;
}
/* ── CHARTS ─────────────────────────────────────────── */
function chart(id, cfg) { if (S.charts[id]) S.charts[id].destroy(); const c = document.getElementById(id); if (c) S.charts[id] = new Chart(c, cfg); }
const legendOpt = { position: 'bottom', labels: { boxWidth: 9, boxHeight: 9, font: { size: 9.5 }, color: '#93A6AF', padding: 10 } };
const grid = { color: 'rgba(255,255,255,.055)' };
function renderDaily() {
  const gs = GROUPS.filter(g => S.groups.has(g) && CUR.daily[g].some(v => v > 0));
  chart('chDaily', { type: 'bar',
    data: { labels: CUR.labels.map(d => d.slice(5).replace('-', '.')),
      datasets: gs.map(g => ({ label: GL[g], data: CUR.daily[g], backgroundColor: GC[g], stack: 's', borderWidth: 0, borderRadius: 2 })) },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: legendOpt, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${fmt(c.parsed.y)} ₴`,
        footer: i => 'РАЗОМ ' + fmt(i.reduce((s, x) => s + x.parsed.y, 0)) + ' ₴' } } },
      scales: { x: { stacked: true, grid: { display: false }, ticks: { font: { size: 8.5 }, maxRotation: 0, autoSkipPadding: 8 } },
        y: { stacked: true, ticks: { callback: v => kfmt(v) }, grid } } } });
}
function renderMonth() {
  const gs = GROUPS.filter(g => (D.month_series[g] || []).some(v => v > 0));
  chart('chMonth', { type: 'bar',
    data: { labels: D.month_labels, datasets: gs.map(g => ({ label: GL[g], data: D.month_series[g], backgroundColor: GC[g], stack: 'm', borderWidth: 0, borderRadius: 2 })) },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: legendOpt, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${fmt(c.parsed.y)} ₴`,
        footer: i => 'РАЗОМ ' + fmt(i.reduce((s, x) => s + x.parsed.y, 0)) + ' ₴' } } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, ticks: { callback: v => kfmt(v) }, grid } } } });
}
function renderForecast() {
  const gs = GROUPS.filter(g => D.forecast30[g] > 0);
  chart('chFc', { type: 'bar', data: { labels: gs.map(g => GL[g]),
      datasets: [{ data: gs.map(g => D.forecast30[g]), backgroundColor: gs.map(g => GC[g]), borderWidth: 0, borderRadius: 2 }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, title: { display: true, color: '#E9F1F5',
          text: 'РАЗОМ ' + fmt(D.forecast30_total) + ' ₴ · ЗАЛИШИЛОСЬ ' + D.rem_days + ' ДН.', font: { size: 11, weight: '700' } },
        tooltip: { callbacks: { label: c => ' ' + fmt(c.parsed.x) + ' ₴' } } },
      scales: { x: { ticks: { callback: v => kfmt(v) }, grid }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } } } });
}
function renderFam() {
  const [pa, pb] = comparePrev(RA, RB);
  const c = sliceFacts(D.fam_facts, RA, RB, 1, [2]), p = sliceFacts(D.fam_facts, pa, pb, 1, [2]);
  const rows = D.fam_list.map((f, i) => ({ f, c: (c[i] || [0])[0], p: (p[i] || [0])[0] }))
    .filter(r => r.c > 0 || r.p > 0).sort((a, b) => b.c - a.c).slice(0, 13);
  chart('chFam', { type: 'bar', data: { labels: rows.map(r => r.f), datasets: [
      { label: 'Період', data: rows.map(r => r.c), backgroundColor: '#FF7701', borderWidth: 0, borderRadius: 2 },
      { label: 'Попередній', data: rows.map(r => r.p), backgroundColor: 'rgba(255,255,255,.16)', borderWidth: 0, borderRadius: 2 }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: legendOpt, tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${fmt(c.parsed.x)} ₴` } } },
      scales: { x: { ticks: { callback: v => kfmt(v) }, grid }, y: { grid: { display: false }, ticks: { font: { size: 9.5 } } } } } });
}

/* ── TABLES ─────────────────────────────────────────── */
function renderChanTable() {
  const k = S.sort.chan || { k: 'revenue', d: -1 };
  const rows = chanRows().sort((a, b) => cmp(a[k.k], b[k.k]) * k.d);
  $('#tblChannels tbody').innerHTML = rows.length ? rows.map(r => `<tr class="clk" data-ch="${esc(r.channel)}">
    <td><i class="dot" style="background:${GC[r.group]}"></i>${esc(r.channel)}</td>
    <td><span class="tag">${esc(GL[r.group] || r.group)}</span></td>
    <td class="num">${fmt(r.orders)}</td><td class="num"><b>${fmt(r.revenue)}</b></td>
    <td class="num">${fmt(r.aov)}</td><td class="num">${fmt(r.margin)}</td>
    <td class="num" style="color:var(--ink-3)">${r.mrate}%</td>
    <td class="num" style="color:var(--ink-3)">${fmt(r.prev)}</td>
    <td class="num ${r.delta > 0 ? 'up' : r.delta < 0 ? 'down' : ''}">${sign(r.delta)}%</td>
    <td class="num" style="color:var(--cyan)">${r.pipe ? fmt(r.pipe) : '—'}</td>
    <td class="num ${r.cancelled > 2 ? 'flag' : ''}">${r.cancelled || '—'}</td></tr>`).join('')
    : '<tr><td colspan="11" class="empty">НЕМАЄ ДАНИХ</td></tr>';
  bindDrill('#tblChannels tr.clk');
}
function renderTopSku() {
  const s = sliceFacts(D.sku_facts, RA, RB, 1, [2, 3]);
  const k = S.sort.sku || { k: 'rev', d: -1 };
  let rows = Object.entries(s).map(([i, v]) => ({ ...D.sku_list[i], qty: v[0], rev: v[1] }));
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(r => (r.name + ' ' + r.sku).toLowerCase().includes(q)); }
  rows.sort((a, b) => cmp(a[k.k], b[k.k]) * k.d);
  $('#tblTopSku tbody').innerHTML = rows.slice(0, 15).map(r => `<tr>
    <td style="font-size:11px">${esc(r.name.slice(0, 50))} <span style="color:var(--ink-3);font-family:var(--mono);font-size:9.5px">${esc(r.sku)}</span></td>
    <td class="num">${r.qty}</td><td class="num"><b>${fmt(r.rev)}</b></td></tr>`).join('')
    || '<tr><td colspan="3" class="empty">НЕМАЄ ПРОДАЖІВ У ПЕРІОДІ</td></tr>';
}
function renderCamp() {
  const s = sliceFacts(D.camp_facts, RA, RB, 1, [2, 3, 4]);
  const k = S.sort.camp || { k: 'rev', d: -1 };
  let rows = Object.entries(s).map(([i, v]) => ({ ...D.camp_list[i], orders: v[0], rev: v[1], canc: v[2],
    aov: v[0] ? Math.round(v[1] / v[0]) : 0 })).filter(r => S.groups.has(CHG[r.channel] || 'other'));
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(r => (r.campaign + ' ' + r.channel).toLowerCase().includes(q)); }
  rows.sort((a, b) => cmp(a[k.k], b[k.k]) * k.d);
  $('#tblCamp tbody').innerHTML = rows.slice(0, 22).map(r => `<tr>
    <td style="font-size:10.5px;color:var(--ink-3)">${esc(r.channel.replace(' (PMax/Search)', '').replace(' (FB/IG)', ''))}</td>
    <td style="font-size:11px">${esc(r.campaign)}</td><td class="num">${r.orders}</td>
    <td class="num"><b>${fmt(r.rev)}</b></td><td class="num">${fmt(r.aov)}</td>
    <td class="num ${r.canc > 2 ? 'flag' : ''}">${r.canc || '—'}</td></tr>`).join('')
    || '<tr><td colspan="6" class="empty">НЕМАЄ ЗАКРИТИХ ЗАМОВЛЕНЬ ВІД ПЛАТНИХ КАМПАНІЙ</td></tr>';
}
function renderCanc() {
  const i0 = idx(RA), i1 = idx(RB), byR = {};
  for (const f of D.canc_facts) { if (f[0] < i0 || f[0] > i1) continue;
    if (!S.groups.has(CHG[CH[f[2]]] || 'other')) continue; byR[f[1]] = (byR[f[1]] || 0) + f[3]; }
  const rr = Object.entries(byR).map(([i, n]) => ({ r: D.canc_list[i], n })).sort((a, b) => b.n - a.n);
  const mx = Math.max(...rr.map(r => r.n), 1);
  $('#cancReasons').innerHTML = rr.length ? rr.map(r => `<div class="brow" style="cursor:default">
    <div class="nm">${esc(r.r)}</div><div class="track"><div class="fill" style="width:${(r.n / mx * 100).toFixed(1)}%;background:var(--crit)"></div></div>
    <div class="val">${r.n}</div></div>`).join('') : '<div class="empty">СКАСУВАНЬ НЕМАЄ</div>';
  const k = S.sort.cancch || { k: 'rate', d: -1 };
  const rows = Object.entries(CUR.byCh).map(([ch, a]) => ({ channel: ch, group: a.g, orders: a.o, cancelled: a.c,
    rate: (a.o + a.c) ? Math.round(a.c / (a.o + a.c) * 100) : 0 })).filter(r => r.cancelled > 0)
    .sort((a, b) => cmp(a[k.k], b[k.k]) * k.d);
  $('#tblCancCh tbody').innerHTML = rows.length ? rows.map(r => `<tr class="clk" data-ch="${esc(r.channel)}">
    <td><i class="dot" style="background:${GC[r.group]}"></i>${esc(r.channel)}</td>
    <td class="num">${r.orders}</td><td class="num ${r.cancelled > 2 ? 'flag' : ''}">${r.cancelled}</td>
    <td class="num ${r.rate >= 40 ? 'flag' : r.rate >= 25 ? '' : 'ok'}">${r.rate}%</td></tr>`).join('')
    : '<tr><td colspan="4" class="empty">СКАСУВАНЬ НЕМАЄ</td></tr>';
  bindDrill('#tblCancCh tr.clk');
}
function renderStock() {
  const k = S.sort.stock || { k: 'sold14', d: -1 };
  let rows = D.top_stock.slice();
  if (S.stock === 'risk') rows = rows.filter(r => r.cover_days <= 21);
  if (S.stock === 'out') rows = rows.filter(r => r.stock === 0);
  if (S.q) { const q = S.q.toLowerCase(); rows = rows.filter(r => (r.name + ' ' + r.sku).toLowerCase().includes(q)); }
  rows.sort((a, b) => cmp(a[k.k], b[k.k]) * k.d);
  $('#tblStock tbody').innerHTML = rows.slice(0, 24).map(s => {
    const cls = s.stock === 0 || s.cover_days <= 10 ? 'risk-hi' : s.cover_days <= 21 ? 'risk' : '';
    const st = s.stock === 0 ? '<span class="badge b-crit">■ СТОКАУТ</span>'
      : s.cover_days <= 10 ? '<span class="badge b-crit">▲ &lt;10Д</span>'
      : s.cover_days <= 21 ? '<span class="badge b-warn">▲ ПОПОВНИТИ</span>' : '<span class="badge b-ok">✓ ОК</span>';
    return `<tr class="${cls}"><td style="font-size:11px">${esc(s.name.slice(0, 54))}
      <span style="color:var(--ink-3);font-family:var(--mono);font-size:9.5px">${esc(s.sku)}</span></td>
      <td class="num">${s.sold14}</td><td class="num">${s.stock}</td>
      <td class="num">${s.cover_days > 365 ? '365+' : s.cover_days}</td><td>${st}</td></tr>`; }).join('')
    || '<tr><td colspan="5" class="empty">НІЧОГО НЕ ПІДПАДАЄ ПІД ФІЛЬТР</td></tr>';
}
function renderPipeTables() {
  const P = D.pipeline;
  const mxc = Math.max(...P.by_channel.map(c => c.sum), 1);
  $('#pipeByCh').innerHTML = P.by_channel.slice(0, 10).map(c => `<div class="brow" data-ch="${esc(c.channel)}" tabindex="0" role="button">
    <div class="nm"><i class="dot" style="background:${GC[c.group] || '#8073e1'}"></i>${esc(c.channel)}</div>
    <div class="track"><div class="fill" style="width:${(c.sum / mxc * 100).toFixed(1)}%;background:${GC[c.group] || '#8073e1'}"></div></div>
    <div><div class="val">${fmt(c.sum)} ₴</div><div class="dlt" style="color:var(--ink-3)">${c.orders} зам.</div></div></div>`).join('');
  bindDrill('#pipeByCh .brow');
  $('#staleHd').innerHTML = `Зависло — старше ${P.stale_days} днів · ${P.stale_orders} зам / ${fmt(P.stale_sum)} ₴`;
  const kst = S.sort.stale || { k: 'sum', d: -1 };
  $('#tblStale tbody').innerHTML = P.stale.length ? P.stale.slice().sort((a, b) => cmp(a[kst.k], b[kst.k]) * kst.d)
    .map(s => `<tr><td class="num">${s.id}</td><td class="num">${esc(s.created.slice(5))}</td>
      <td class="num ${s.age > 30 ? 'flag' : ''}">${s.age}</td><td style="font-size:11px">${esc(s.status)}</td>
      <td style="font-size:11px;color:var(--ink-3)">${esc(s.channel.slice(0, 24))}</td>
      <td class="num"><b>${fmt(s.sum)}</b></td></tr>`).join('')
    : '<tr><td colspan="6" class="empty">ВОРОНКА ЧИСТА</td></tr>';
}
const ST = { open: ['st-open', 'ВІДКРИТО'], in_progress: ['st-prog', 'В РОБОТІ'], done: ['st-done', 'ЗРОБЛЕНО'], dropped: ['st-drop', 'ЗНЯТО'] };
const VD = { helped: ['✅ допомогло', 'up'], hurt: ['⚠ гірше', 'down'], neutral: ['➖ нейтр.', ''], pending: ['⏳ рано', ''], done: ['✔ закрито', ''] };
function renderDecisions() {
  const k = S.sort.dec || { k: 'id', d: 1 };
  const zone = d => d.channel_key === '__stock__' ? 'Склад' : d.channel_key === '__assort__' ? 'Асортимент'
    : d.channel_key === '__pipe__' ? 'Воронка' : d.channel_key;
  const rows = (D.decisions || []).slice().map(d => ({ ...d, zone: zone(d) })).sort((a, b) => cmp(a[k.k], b[k.k]) * k.d);
  $('#tblDec tbody').innerHTML = rows.map(d => { const s = ST[d.status] || ST.open, v = VD[d.verdict] || VD.pending;
    return `<tr><td class="num">${d.id}</td><td class="num">${esc(d.created.slice(5))}</td>
      <td style="font-size:11.5px"><b>${esc(d.zone)}</b></td><td style="font-size:11.5px">${esc(d.action)}</td>
      <td style="font-size:11px;color:var(--ink-3)">${esc(d.owner || '—')}</td>
      <td><span class="st ${s[0]}">${s[1]}</span></td>
      <td class="num">${d.before != null ? fmt(d.before) : '—'}</td><td class="num">${d.after != null ? fmt(d.after) : '—'}</td>
      <td class="num ${d.effect_pct > 0 ? 'up' : d.effect_pct < 0 ? 'down' : ''}">${d.effect_pct != null ? sign(d.effect_pct) + '%' : '—'}</td>
      <td class="vd ${v[1]}">${v[0]}</td><td><button class="dbtn" data-id="${d.id}">▸</button></td></tr>
      <tr class="drow" id="dr${d.id}" style="display:none"><td colspan="11"><div class="dwrap">
        <div><div class="dh">Чому так</div><ul>${(d.details && d.details.why || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
        <div><div class="dh">Що зробити</div><ol>${(d.details && d.details.how || []).map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>
      </div></td></tr>`; }).join('');
  $$('#tblDec .dbtn').forEach(b => b.onclick = () => {
    const r = document.getElementById('dr' + b.dataset.id), open = r.style.display !== 'none';
    r.style.display = open ? 'none' : 'table-row'; b.textContent = open ? '▸' : '▾'; b.classList.toggle('on', !open); });
}

/* ── DRILLDOWN ── */
function bindDrill(sel) { $$(sel).forEach(el => { el.onclick = () => openDrill(el.dataset.ch);
  el.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDrill(el.dataset.ch); } }; }); }
function openDrill(ch) {
  if (!ch) return;
  const a = CUR.byCh[ch] || { o: 0, r: 0, m: 0, c: 0, g: CHG[ch] || 'other' };
  const p = PRV.byCh[ch] || { o: 0, r: 0, m: 0, c: 0 };
  const g = CHG[ch] || 'other', ci = CH.indexOf(ch), i0 = idx(RA), i1 = idx(RB);
  const days = [], vals = []; for (let i = i0; i <= i1; i++) { days.push(DATES[i]); vals.push(0); }
  const canc = {};
  for (const f of D.facts) if (f[1] === ci && f[0] >= i0 && f[0] <= i1) vals[f[0] - i0] += f[3];
  for (const f of D.canc_facts) if (f[2] === ci && f[0] >= i0 && f[0] <= i1) canc[D.canc_list[f[1]]] = (canc[D.canc_list[f[1]]] || 0) + f[3];
  const cmpRows = Object.entries(sliceFacts(D.camp_facts, RA, RB, 1, [2, 3, 4]))
    .map(([i, v]) => ({ ...D.camp_list[i], orders: v[0], rev: v[1], canc: v[2] }))
    .filter(r => r.channel === ch).sort((x, y) => y.rev - x.rev).slice(0, 10);
  const pipe = PIPE_CH[ch], stale = (D.pipeline.stale || []).filter(s => s.channel === ch);
  const decs = (D.decisions || []).filter(d => d.channel_key === ch);
  const chStat = (D.channels || []).find(c => c.channel === ch) || {};
  const aov = a.o ? a.r / a.o : 0, paov = p.o ? p.r / p.o : 0;
  const crate = (a.o + a.c) ? Math.round(a.c / (a.o + a.c) * 100) : 0;
  $('#ddTitle').innerHTML = `<i class="dot" style="width:13px;height:13px;background:${GC[g]};box-shadow:0 0 12px ${GC[g]}"></i>${esc(ch)}`;
  $('#ddPeriod').textContent = RA + ' → ' + RB + ' · ГРУПА: ' + (GL[g] || g).toUpperCase();
  const kpi = (l, v, d) => `<div class="dd-kpi"><div class="l">${esc(l)}</div><div class="v">${v}</div>
    <div class="d ${d > 0 ? 'up' : d < 0 ? 'down' : ''}">${d === null ? '' : sign(d) + '% vs попер.'}</div></div>`;
  let html = `<div class="dd-kpis">${kpi('Виручка', fmt(a.r) + ' ₴', pct(a.r, p.r))}
    ${kpi('Замовлення', fmt(a.o), pct(a.o, p.o))}${kpi('Сер. чек', fmt(aov) + ' ₴', pct(aov, paov))}
    ${kpi('Маржа', fmt(a.m) + ' ₴', pct(a.m, p.m))}</div>`;
  html += `<div class="dd-block"><h4>Потік по днях</h4><div class="chart sm"><canvas id="ddChart"></canvas></div></div>`;
  html += `<div class="dd-block"><h4>Стан каналу</h4><table><tbody>
    <tr><td>Скасувань у періоді</td><td class="num ${crate >= 40 ? 'flag' : ''}">${a.c} · ${crate}%</td></tr>
    <tr><td>У роботі зараз</td><td class="num" style="color:var(--cyan)">${pipe ? fmt(pipe.sum) + ' ₴ · ' + pipe.orders + ' зам.' : '—'}</td></tr>
    <tr><td>Завислих &gt; ${D.pipeline.stale_days} днів</td><td class="num ${stale.length ? 'flag' : ''}">${stale.length ? stale.length + ' зам / ' + fmt(stale.reduce((s, x) => s + x.sum, 0)) + ' ₴' : '—'}</td></tr>
    <tr><td>MTD</td><td class="num">${fmt(chStat.cur_revenue || 0)} ₴ · ${chStat.cur_orders || 0} зам.</td></tr>
    <tr><td>${esc(D.prev_month_name)} повний</td><td class="num" style="color:var(--ink-3)">${fmt(chStat.pfull_revenue || 0)} ₴</td></tr>
    </tbody></table></div>`;
  if (cmpRows.length) html += `<div class="dd-block"><h4>Кампанії каналу</h4><table>
    <thead><tr><th>Кампанія</th><th class="num">Зам.</th><th class="num">₴</th><th class="num">Скас.</th></tr></thead>
    <tbody>${cmpRows.map(r => `<tr><td style="font-size:11px">${esc(r.campaign)}</td><td class="num">${r.orders}</td>
      <td class="num"><b>${fmt(r.rev)}</b></td><td class="num ${r.canc > 2 ? 'flag' : ''}">${r.canc || '—'}</td></tr>`).join('')}</tbody></table></div>`;
  const cancArr = Object.entries(canc).sort((x, y) => y[1] - x[1]);
  if (cancArr.length) html += `<div class="dd-block"><h4>Причини скасувань</h4><table><tbody>
    ${cancArr.map(([r, n]) => `<tr><td>${esc(r)}</td><td class="num">${n}</td></tr>`).join('')}</tbody></table></div>`;
  if (stale.length) html += `<div class="dd-block"><h4>Завислі замовлення</h4><table>
    <thead><tr><th>№</th><th>Створено</th><th class="num">Днів</th><th>Статус</th><th class="num">₴</th></tr></thead>
    <tbody>${stale.map(s => `<tr><td class="num">${s.id}</td><td class="num">${esc(s.created.slice(5))}</td>
      <td class="num flag">${s.age}</td><td style="font-size:11px">${esc(s.status)}</td><td class="num">${fmt(s.sum)}</td></tr>`).join('')}</tbody></table></div>`;
  if (decs.length) html += `<div class="dd-block"><h4>Рішення по каналу</h4>
    ${decs.map(d => `<div style="border-left:2px solid var(--brand);padding:8px 12px;margin-bottom:9px;background:rgba(255,119,1,.05)">
      <div style="font:9.5px var(--mono);color:var(--ink-3);letter-spacing:.12em">№${d.id} · ${esc(d.created)} · ${esc(d.owner || '—')}</div>
      <div style="margin:5px 0;font-size:12.5px">${esc(d.action)}</div>
      <div class="dwrap" style="margin-top:8px">
        <div><div class="dh">Чому так</div><ul>${(d.details && d.details.why || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
        <div><div class="dh">Що зробити</div><ol>${(d.details && d.details.how || []).map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>
      </div></div>`).join('')}</div>`;
  $('#ddBody').innerHTML = html;
  $('#dd').classList.add('open'); document.body.style.overflow = 'hidden';
  if (S.charts.ddChart) { S.charts.ddChart.destroy(); delete S.charts.ddChart; }
  S.charts.ddChart = new Chart(document.getElementById('ddChart'), {
    type: 'bar', data: { labels: days.map(d => d.slice(5).replace('-', '.')),
      datasets: [{ data: vals, backgroundColor: GC[g], borderWidth: 0, borderRadius: 2 }] },
    options: { responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ' ' + fmt(c.parsed.y) + ' ₴' } } },
      scales: { x: { grid: { display: false }, ticks: { font: { size: 8.5 }, maxRotation: 0, autoSkipPadding: 8 } },
        y: { ticks: { callback: v => kfmt(v) }, grid } } } });
}
function closeDrill() { $('#dd').classList.remove('open'); document.body.style.overflow = ''; }


/* ── SPARKLINE (SVG) ─────────────────────────────────── */
function sparkSvg(vals, color, w, h, cls) {
  w = w || 260; h = h || 44;
  if (!vals || !vals.length) return '';
  const mx = Math.max(...vals, 1), n = vals.length;
  const bw = w / n, gap = Math.min(3, bw * .22);
  const bars = vals.map((v, i) => {
    const bh = Math.max(1.5, v / mx * (h - 4));
    return `<rect x="${(i * bw + gap / 2).toFixed(1)}" y="${(h - bh).toFixed(1)}"
      width="${(bw - gap).toFixed(1)}" height="${bh.toFixed(1)}" fill="${color}"
      opacity="${i === n - 1 ? 1 : .6}" rx="1"/>`;
  }).join('');
  return `<svg class="${cls || 'spark'}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${bars}</svg>`;
}

/* ── LEDE + TRIO ─────────────────────────────────────── */
function renderLede() {
  const T = D.totals.cur, PI = D.pipeline, Y = D.yoy || {}, M = D.target_model || {};
  const aov = T.orders ? T.revenue / T.orders : 0;
  const mrate = T.revenue ? Math.round(T.margin / T.revenue * 100) : 0;
  const ly = Y.ly_same, lyM = Y.ly_month;
  const fcYoY = lyM && lyM.revenue ? Math.round((D.forecast30_total - lyM.revenue) / lyM.revenue * 100) : null;
  const P = D.totals.prev;
  const dRev = pct(T.revenue, P.revenue);
  const prevLbl = '1–' + D.period_prev[1].slice(8) + ' ' + D.prev_month_gen;
  const fun = (D.funnels || []).filter(f => f.prev > 0 || f.rev > 0);
  const drop = fun.slice().sort((a, b) => (a.rev - a.prev) - (b.rev - b.prev))[0];
  const gain = fun.slice().sort((a, b) => (b.rev - b.prev) - (a.rev - a.prev))[0];
  $('#eyebrow').textContent = 'Стан на ' + D.today + ' · ' + D.month_name;

  let h = `${D.month_short.charAt(0).toUpperCase() + D.month_short.slice(1)} іде на <b>${fmt(D.forecast30_total)} ₴</b>`;
  if (fcYoY !== null) h += ` — це <span class="${fcYoY < 0 ? 'bad' : 'good'}">${fcYoY < 0 ? 'на ' + Math.abs(fcYoY) + '% нижче' : 'на ' + fcYoY + '% вище'}</span> ${esc(D.month_gen)} ${Number(D.today.slice(0,4)) - 1}.`;
  else h += '.';
  if (ly && Y.delta_orders !== null && Y.delta_aov !== null) {
    const same = Math.abs(Y.delta_orders) <= 10;
    h += ` Замовлень ${same ? 'стільки ж' : (Y.delta_orders > 0 ? 'більше на ' + Y.delta_orders + '%' : 'менше на ' + Math.abs(Y.delta_orders) + '%')}` +
         ` (${T.orders} проти ${ly.orders}), а середній чек <span class="${Y.delta_aov < 0 ? 'bad' : 'good'}">${sign(Y.delta_aov)}%</span>: ${fmt(ly.aov)} → ${fmt(aov)} ₴.`;
  }
  if (drop && gain && drop.key !== gain.key)
    h += ` Найбільше просів <span class="bad">${esc(drop.name)}</span>, найбільше додав <span class="good">${esc(gain.name)}</span>.`;
  $('#lede').innerHTML = h;
  $('#ledeSub').innerHTML = `${D.period_cur[0]} → ${D.period_cur[1]} · тільки закриті угоди (KeyCRM) ·
    ціль місяця <b>${fmt(M.target || D.target)} ₴</b> (${esc(M.basis || D.target_source)}) ·
    режим: <b>${M.phase === 'grow' ? 'зростання +' + Math.round((M.g || 0) * 100) + '%' : 'відновлення до рівня минулого року'}</b>`;

  const months = D.month_labels.map((l, i) => GROUPS.reduce((s, g) => s + (D.month_series[g] || [])[i] || 0, 0));
  $('#tMoney').innerHTML = `<div class="h">Гроші</div>
    <div class="big">${fmt(T.revenue)} ₴</div>
    <div class="li"><span>виручка ${esc(D.month_short)} MTD,</span>
      <b class="${dRev > 0 ? 'up' : 'dn'}">${sign(dRev)}%</b> <span>до ${esc(prevLbl)}</span><br>
      ${T.orders} замовлень · середній чек ${fmt(aov)} ₴<br>
      маржа ${fmt(T.margin)} ₴ (${mrate}%) · скасувань ${T.cancelled}</div>
    ${sparkSvg(months, '#FF7701')}
    <div class="ax"><span>${esc(D.month_labels[0] || '')}</span><span>${esc(D.month_labels[D.month_labels.length - 1] || '')}</span></div>`;

  const tgt = M.target || D.target || 0;
  const prog = tgt ? Math.min(1, T.revenue / tgt) : 0;
  const fcProg = tgt ? Math.min(1, D.forecast30_total / tgt) : 0;
  const gap = M.gap != null ? M.gap : (D.gap_to_target || 0);
  $('#tPlan').innerHTML = `<div class="h">Ціль місяця</div>
    <div class="big">${fmt(tgt)} ₴</div>
    <div class="li"><span>база:</span> <b>${esc(M.basis || D.target_source)}</b><br>
      <span>факт зараз</span> <b>${fmt(T.revenue)} ₴</b> <span>(${Math.round(prog * 100)}%)</span> ·
      <span>прогноз</span> <b>${fmt(D.forecast30_total)} ₴</b> <span>(${Math.round(fcProg * 100)}%)</span><br>
      ${gap > 0 ? `<span>розрив</span> <b class="dn">${fmt(gap)} ₴</b> <span>= ${fmt(M.gap_per_day || 0)} ₴/день понад темп</span>`
                : '<span class="up">ціль перекрита</span>'}</div>
    <div class="prog"><i style="width:${(prog * 100).toFixed(1)}%"></i>
      <span class="mark" style="left:${(fcProg * 100).toFixed(1)}%" title="прогноз"></span></div>
    <div class="ax"><span>факт ${Math.round(prog * 100)}%</span>
      <span>${M.mer ? 'MER ' + M.mer + ' при беззбитковості ' + M.breakeven_mer : 'беззбитковий MER ' + (M.breakeven_mer || '—') + ' · spend не підключено'}</span></div>`;

  const SEV = { ok: '#4E9AC7', warn: '#F5C451', serious: '#FF9A52', critical: '#FF8A8A' };
  const ageTot = PI.by_age.reduce((s, a) => s + a.sum, 0) || 1;
  $('#tRisk').innerHTML = `<div class="h">Ризик</div>
    <div class="big" style="color:${PI.stale_orders ? 'var(--crit)' : 'var(--good)'}">${fmt(PI.stale_sum)} ₴</div>
    <div class="li">${PI.stale_orders} замовлень висять довше ${PI.stale_days} днів<br>
      <span>усього в роботі</span> <b>${fmt(PI.sum)} ₴</b> <span>(${PI.orders} зам.)</span><br>
      <span>дозакриється ≈</span> <b>${fmt(PI.expected)} ₴</b> <span>(конверсія ${Math.round(PI.close_rate * 100)}%)</span></div>
    <div class="agebar">${PI.by_age.map(a => `<span title="${esc(a.bucket)}: ${fmt(a.sum)} ₴ · ${a.orders} зам."
      style="flex:${Math.max(a.sum / ageTot, .03)};background:${SEV[a.sev]}"></span>`).join('')}</div>
    <div class="ax">${PI.by_age.map(a => `<span>${esc(a.bucket)}<b>${fmt(a.sum)} ₴</b></span>`).join('')}</div>`;
}

/* ── ТРИ ВАЖЕЛІ ──────────────────────────────────────── */
function renderLevers() {
  const M = D.target_model, Y = D.yoy || {};
  if (!M || !M.levers) { $('#levers').innerHTML = ''; $('#leverNote').innerHTML = ''; return; }
  const L = M.levers, lyLbl = D.month_short + ' ' + (Number(D.today.slice(0, 4)) - 1);
  const cards = [
    { k: 'Замовлення', now: fmt(L.orders.now), ly: L.orders.ly != null ? fmt(L.orders.ly) : '—',
      d: L.orders.delta, unit: '',
      req: 'при чеку ' + fmt(L.aov.now) + ' ₴ треба ' + fmt(L.orders.required) + ' зам.',
      say: L.orders.delta != null && Math.abs(L.orders.delta) <= 10
        ? 'Попит на місці — покупців стільки ж, як торік. Це не проблема трафіку.'
        : (L.orders.delta < 0 ? 'Покупців менше, ніж торік — тут працює трафік і конверсія.'
                              : 'Покупців більше, ніж торік — трафік працює.'),
      good: L.orders.delta != null && L.orders.delta >= -10 },
    { k: 'Середній чек', now: fmt(L.aov.now) + ' ₴', ly: L.aov.ly != null ? fmt(L.aov.ly) + ' ₴' : '—',
      d: L.aov.delta, unit: '',
      req: 'для цілі треба ' + fmt(L.aov.required) + ' ₴' + (L.aov.ratio ? ' (×' + L.aov.ratio + ')' : ''),
      say: L.aov.delta != null && L.aov.delta < -15
        ? 'Головний важіль. Чек росте від комплекту, допродажу й дорогого героя в рекламі — без додаткових вкладень у трафік.'
        : 'Чек тримається на рівні минулого року.',
      good: L.aov.delta != null && L.aov.delta >= -15 },
    { k: 'Скасування', now: L.cancel.now + '%', ly: L.cancel.ly != null ? L.cancel.ly + '%' : '—',
      d: L.cancel.delta, unit: ' п.п.',
      req: 'кожен пункт скасувань = мінус ' + fmt(D.totals.cur.revenue / Math.max(100 - L.cancel.now, 1)) + ' ₴',
      say: 'Найдешевший приріст: не потребує ні бюджету, ні креативів. Дзвінок-підтвердження за 2 години й розмірна сітка на картці.',
      good: L.cancel.delta != null && L.cancel.delta <= 0 },
  ];
  $('#levers').innerHTML = cards.map(c => `<div class="fc st-${c.good ? 'growing' : 'dropping'}" style="cursor:default">
    <div class="top"><div class="nm">${esc(c.k)}</div>
      <div class="vd">${c.d == null ? '' : (c.d > 0 ? '▲ ' : c.d < 0 ? '▼ ' : '') + sign(c.d) + (c.unit || '%')}</div></div>
    <div class="rev">${c.now}</div>
    <div class="d" style="color:var(--ink-3)">${esc(lyLbl)}: <b>${c.ly}</b></div>
    <div class="meta" style="margin-top:10px">${esc(c.req)}</div>
    <div class="role">${esc(c.say)}</div></div>`).join('');

  const tgt = M.target, need = tgt - M.forecast;
  $('#leverNote').innerHTML = `<div style="font-size:14px;line-height:1.65">
    <b>Як читати.</b> Ціль <b>${fmt(tgt)} ₴</b> — це ${esc(M.basis)}.
    За поточним темпом вийде ${fmt(M.forecast)} ₴, тобто не вистачає <b class="dn">${fmt(Math.max(0, need))} ₴</b>.
    При темпі <b>${L.orders.projected} замовлень</b> на місяць цю діру закриває середній чек
    <b>${fmt(L.aov.required)} ₴</b> — це ${L.aov.ratio ? '×' + L.aov.ratio : ''} до нинішнього
    і ${L.aov.ly ? (L.aov.required > L.aov.ly ? 'на ' + Math.round((L.aov.required / L.aov.ly - 1) * 100) + '% вище' : 'на рівні') + ' торішнього' : ''}.
    <br><br>
    <b>Стеля ефективності.</b> Валова маржа <b>${M.cm_pct}%</b> → беззбитковий MER <b>${M.breakeven_mer}</b>.
    Нарощуємо бюджет, поки кожна наступна гривня приносить більше ніж ${M.breakeven_mer} ₴ виручки.
    ${M.mer ? 'Поточний MER <b>' + M.mer + '</b> при витратах ' + fmt(M.spend) + ' ₴.'
            : '<span style="color:var(--ink-3)">Витрати на рекламу ще не підключені — MER рахуватиметься, щойно зʼявиться spend.json.</span>'}
  </div>`;
}

/* ── ВОРОНКИ ─────────────────────────────────────────── */
const FUN_COLOR = { 'Google Ads': '#e66900', 'Meta Ads': '#ae3a6f', 'TikTok Ads': '#00a7bc',
  'SEO': '#9e5900', 'Email / Retention': '#8073e1', 'B2B / дилери': '#56a76a',
  'Shopify INTL': '#0a73aa', 'Соцмережі органіка': '#00a7bc', 'Леся (AI-бот)': '#ae3a6f',
  'Офіс / телефон': '#9e5900', 'Direct / бренд': '#e66900' };
function renderFunnels() {
  const F = D.funnels || [];
  $('#funNote').textContent = D.month_name + ' MTD vs той самий відрізок ' + D.prev_month_gen +
    ' · ' + F.filter(f => f.status === 'broken' || f.status === 'dropping').length + ' з ' + F.length + ' потребують дії';
  $('#funnels').innerHTML = F.map(f => {
    const c = FUN_COLOR[f.name] || '#8073e1';
    return `<div class="fc st-${f.status}" data-fun="${esc(f.key)}" tabindex="0" role="button">
      <div class="top"><div class="nm">${esc(f.name)}</div><div class="vd">${esc(f.verdict)}</div></div>
      <div class="rev">${fmt(f.rev)} ₴</div>
      <div class="d ${f.delta > 0 ? 'up' : f.delta < 0 ? 'dn' : ''}">${sign(f.delta)}% до ${esc(D.prev_month_gen)} · ${f.share}% усієї виручки</div>
      <div class="meta">${f.orders} зам · чек <b>${fmt(f.aov)} ₴</b> · маржа <b>${fmt(f.margin)} ₴</b><br>
        скасувань <b class="${f.cancel_rate >= 30 ? 'dn' : ''}">${f.cancel_rate}%</b> (${f.cancelled}) ·
        у роботі <b>${fmt(f.pipe)} ₴</b><br>
        ${esc(D.prev_month_name)} повний: <b>${fmt(f.pfull)} ₴</b></div>
      ${sparkSvg(f.months, c, 260, 30, 'mini')}
      <div class="role">${esc(f.role)}</div>
      <span class="tag">${esc(f.owner)}</span> <span class="tag">${esc(f.strategy)}</span>
    </div>`;
  }).join('');
  $$('#funnels .fc').forEach(el => {
    const open = () => { const f = F.find(x => x.key === el.dataset.fun); if (f) openFunnel(f); };
    el.onclick = open;
    el.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } };
  });
}
function openFunnel(f) {
  if (f.members && f.members.length === 1) return openDrill(f.members[0]);
  const rows = f.members.map(m => (D.channels || []).find(c => c.channel === m)).filter(Boolean);
  const c = FUN_COLOR[f.name] || '#8073e1';
  $('#ddTitle').innerHTML = `<i class="dot" style="width:13px;height:13px;background:${c}"></i>${esc(f.name)}`;
  $('#ddPeriod').textContent = D.month_name + ' MTD · відповідальний: ' + f.owner + ' · стратегія: ' + f.strategy;
  const kpi = (l, v, d) => `<div class="dd-kpi"><div class="l">${esc(l)}</div><div class="v">${v}</div>
    <div class="d ${d > 0 ? 'up' : d < 0 ? 'dn' : ''}">${d === null ? '' : sign(d) + '%'}</div></div>`;
  let html = `<div class="dd-kpis">${kpi('Виручка', fmt(f.rev) + ' ₴', f.delta)}
    ${kpi('Замовлення', fmt(f.orders), null)}${kpi('Середній чек', fmt(f.aov) + ' ₴', null)}
    ${kpi('Скасування', f.cancel_rate + '%', null)}</div>
    <div class="dd-block"><h4>Роль каналу</h4><div style="font-size:13.5px;line-height:1.6">${esc(f.role)}</div></div>
    <div class="dd-block"><h4>Динаміка по місяцях</h4>${sparkSvg(f.months, c, 620, 90, '')}
      <div class="ax">${D.month_labels.map((l, i) => `<span>${esc(l)}<b>${fmt(f.months[i])}</b></span>`).join('')}</div></div>`;
  if (rows.length > 1) html += `<div class="dd-block"><h4>Канали всередині воронки</h4><table>
    <thead><tr><th>Канал</th><th class="num">Зам.</th><th class="num">₴ MTD</th><th class="num">Δ</th><th class="num">Скас.</th></tr></thead>
    <tbody>${rows.map(r => `<tr class="clk" data-ch="${esc(r.channel)}"><td>${esc(r.channel)}</td>
      <td class="num">${r.cur_orders}</td><td class="num"><b>${fmt(r.cur_revenue)}</b></td>
      <td class="num ${r.delta_rev_pct > 0 ? 'up' : 'dn'}">${sign(r.delta_rev_pct)}%</td>
      <td class="num ${r.cur_cancelled > 2 ? 'flag' : ''}">${r.cur_cancelled || '—'}</td></tr>`).join('')}</tbody></table></div>`;
  const tasks = (D.plan || []).filter(t => t.funnel === f.name);
  if (tasks.length) html += `<div class="dd-block"><h4>Завдання по цій воронці</h4>${tasks.map(taskCard).join('')}</div>`;
  $('#ddBody').innerHTML = html;
  $('#dd').classList.add('open'); document.body.style.overflow = 'hidden';
  $$('#ddBody tr.clk').forEach(tr => tr.onclick = () => openDrill(tr.dataset.ch));
  bindTasks();
}

/* ── ПЛАН ДІЙ ────────────────────────────────────────── */
function taskCard(t, i) {
  const stra = t.type === 'strategic';
  return `<div class="task ${stra ? 'stra' : ''}" data-id="${esc(t.id)}">
    <div class="th">
      <div>
        <div class="chips">
          <span class="chip ${stra ? 'c-stra' : 'c-tact'}">${stra ? 'стратегія' : 'тактика'} · ${esc(t.horizon)}</span>
          <span class="chip c-own">${esc(t.owner)}</span>
          <span class="chip c-fun">${esc(t.funnel)}</span>
        </div>
        <div class="tt">${esc(t.title)}</div>
      </div>
      <div class="exp">розгорнути ▾</div>
    </div>
    <div class="body">
      <div class="tgrid">
        <div><h4>Навіщо це робимо</h4><ul>${t.why.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>
        <div><h4>Як робити</h4><ol>${t.how.map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>
      </div>
      <div class="goal">
        <div class="g"><div class="k">Ціль</div><div class="v">${esc(t.goal)}</div></div>
        <div class="g"><div class="k">Який результат нам потрібен</div><div class="v">${esc(t.result)}</div></div>
      </div>
      <div class="tfoot"><span>KPI: <b>${esc(t.kpi || '—')}</b></span>
        <span>Стратегія: <b>${esc(t.strategy)}</b></span>
        <span>Виконавець: <b>${esc(t.owner)}</b></span></div>
    </div></div>`;
}
function bindTasks() {
  $$('.task .th').forEach(h => h.onclick = () => {
    const t = h.parentElement, open = t.classList.toggle('open');
    h.querySelector('.exp').textContent = open ? 'згорнути ▴' : 'розгорнути ▾';
  });
}
function renderPlan() {
  const all = D.plan || [];
  const list = S.planTab === 'all' ? all : all.filter(t => t.type === S.planTab);
  $('#plan').innerHTML = list.length ? list.map(taskCard).join('')
    : '<div class="empty">Завдань цього типу зараз немає.</div>';
  bindTasks();
  $$('#plan .task').forEach((t, i) => { if (i < 2) { t.classList.add('open'); t.querySelector('.exp').textContent = 'згорнути ▴'; } });
}

/* ── ДЖЕРЕЛА ─────────────────────────────────────────── */
function renderSources() {
  const rows = chanRows().sort((a, b) => b.metric - a.metric);
  const top = rows.slice(0, 9), rest = rows.slice(9);
  const total = rows.reduce((s, r) => s + r.metric, 0) || 1;
  const mx = Math.max(...top.map(r => r.metric), 1);
  $('#srcNote').textContent = RA + ' → ' + RB + ' · виручка, ₴ · клік по рядку — деталізація';
  let html = top.map(r => `<div class="line" data-ch="${esc(r.channel)}" tabindex="0" role="button">
    <div class="nm"><i class="dot" style="background:${GC[r.group]}"></i>${esc(r.channel)}</div>
    <div class="bar"><i style="width:${(r.metric / mx * 100).toFixed(1)}%;background:${GC[r.group]}"></i></div>
    <div class="rv">${fmt(r.metric)} ₴<small>${Math.round(r.metric / total * 100)}% ·
      <span class="${r.delta > 0 ? 'up' : r.delta < 0 ? 'dn' : ''}">${sign(r.delta)}%</span> · ${r.orders} зам.</small></div></div>`).join('');
  if (rest.length) {
    const rv = rest.reduce((s, r) => s + r.metric, 0);
    html += `<div class="line" style="cursor:default;opacity:.75">
      <div class="nm"><i class="dot" style="background:#4a4d3e"></i>Інші (${rest.length})</div>
      <div class="bar"><i style="width:${(rv / mx * 100).toFixed(1)}%;background:#4a4d3e"></i></div>
      <div class="rv">${fmt(rv)} ₴<small>${Math.round(rv / total * 100)}%</small></div></div>`;
  }
  $('#srcLines').innerHTML = html || '<div class="empty">Немає даних у періоді.</div>';
  bindDrill('#srcLines .line[data-ch]');
}

/* ── СТАТИКА ─────────────────────────────────────────── */
function renderStatic() {
  document.title = 'UATAC · Бриф ' + D.month_name;
  $('#f-gen').textContent = 'Згенеровано ' + D.generated_at.slice(0, 16).replace('T', ' ') +
    ' · дані KeyCRM ' + D.data_start + ' → ' + D.today;
  $('#insights').innerHTML = (D.insights || []).map(i => `<div class="alert"><div class="i">▲</div><div>${i}</div></div>`).join('')
    || '<div class="empty">Проблем з атрибуцією не виявлено.</div>';
  $('#intlNote').textContent = 'Курс ' + D.usd_uah + ' ₴/$. UTM у синку Shopify→KeyCRM відсутні — джерела INTL тягнемо з аналітики Shopify окремим кроком.';
  $('#tblIntl tbody').innerHTML = (D.intl_monthly || []).map(r => `<tr><td>${esc(r.month)}</td>
    <td class="num">${r.orders}</td><td class="num"><b>${fmt(r.revenue)}</b></td><td class="num">${r.cancelled || '—'}</td></tr>`).join('');
  renderLede(); renderLevers(); renderFunnels(); renderPlan();
  renderPipeTables(); renderDecisions(); renderMonth(); renderForecast();
}

/* ── RENDER ──────────────────────────────────────────── */
let CUR, PRV, RA, RB;
function render() {
  [RA, RB] = periodRange();
  const [pa, pb] = comparePrev(RA, RB);
  CUR = slice(RA, RB); PRV = slice(pa, pb);
  renderSources(); renderChanTable(); renderDaily();
  renderFam(); renderTopSku(); renderCamp(); renderCanc(); renderStock();
}

/* ── КОНТРОЛИ ────────────────────────────────────────── */
const SORT_TARGET = { tblChannels: 'chan', tblCamp: 'camp', tblStock: 'stock', tblTopSku: 'sku',
  tblDec: 'dec', tblStale: 'stale', tblCancCh: 'cancch' };
const SORT_FN = { chan: () => renderChanTable(), camp: () => renderCamp(), stock: () => renderStock(),
  sku: () => renderTopSku(), dec: () => renderDecisions(), stale: () => renderPipeTables(), cancch: () => renderCanc() };
function bindSorting() {
  Object.entries(SORT_TARGET).forEach(([tid, key]) => $$('#' + tid + ' th.s').forEach(th => th.onclick = () => {
    const cur = S.sort[key] || {};
    S.sort[key] = { k: th.dataset.k, d: cur.k === th.dataset.k ? -cur.d : -1 };
    $$('#' + tid + ' th.s').forEach(x => x.classList.remove('asc', 'desc'));
    th.classList.add(S.sort[key].d === 1 ? 'asc' : 'desc'); SORT_FN[key]();
  }));
}
function bindControls() {
  $$('#segPeriod button').forEach(b => b.onclick = () => {
    $$('#segPeriod button').forEach(x => x.classList.remove('on')); b.classList.add('on');
    S.p = b.dataset.p; $('#frange').classList.toggle('show', S.p === 'custom');
    if (S.p === 'custom') { $('#dFrom').value = S.from; $('#dTo').value = S.to; } render(); });
  $$('#segStock button').forEach(b => b.onclick = () => {
    $$('#segStock button').forEach(x => x.classList.remove('on')); b.classList.add('on');
    S.stock = b.dataset.f; renderStock(); });
  $$('#planTabs button').forEach(b => b.onclick = () => {
    $$('#planTabs button').forEach(x => x.classList.remove('on')); b.classList.add('on');
    S.planTab = b.dataset.t; renderPlan(); });
  $$('#mods button').forEach(b => b.onclick = () => {
    $$('#mods button').forEach(x => x.classList.remove('on')); b.classList.add('on');
    $$('.mod').forEach(m => m.classList.toggle('on', m.dataset.m === b.dataset.m));
    Object.values(S.charts).forEach(c => { try { c.resize(); } catch (e) {} }); });
  const onRange = () => { S.from = $('#dFrom').value || D.data_start; S.to = $('#dTo').value || D.today; if (S.p === 'custom') render(); };
  $('#dFrom').onchange = onRange; $('#dTo').onchange = onRange;
  $('#dFrom').min = $('#dTo').min = D.data_start; $('#dFrom').max = $('#dTo').max = D.today;
  let tq; $('#qSearch').oninput = e => { clearTimeout(tq); tq = setTimeout(() => { S.q = e.target.value.trim(); render(); }, 180); };
  $$('#dd [data-close]').forEach(e => e.onclick = closeDrill);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrill(); });
}
S.planTab = 'tactical';
Chart.defaults.color = '#C3C5B6';
Chart.defaults.font.family = "'JetBrains Mono','SF Mono',ui-monospace,monospace";
Chart.defaults.font.size = 10;
try { renderStatic(); bindSorting(); bindControls(); render(); }
catch (e) { console.error(e); document.body.insertAdjacentHTML('afterbegin',
  '<div style="background:#331512;color:#FF9AA4;padding:12px;font:12px monospace">RENDER ERROR: ' + esc(e.message) + '</div>'); }
</script>
</body>
</html>

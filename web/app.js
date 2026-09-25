/* 厦大统一门户 · 前端逻辑
   纯原生 JS，无框架。搜索、筛选、打分全部在本地完成。

   同一份代码有两种跑法：
     · 桌面版：有本地 Python 后端，走 /api/*（本机模型、系统浏览器打开、文件持久化）
     · 静态版（手机 / PWA）：把 web/ 直接托管成静态站，没有后端，
       自动退回浏览器本地实现（portal.json + localStorage + window.open）
   判断方式：开机先试 /api/catalog，拿不到就退到 portal.json，并把 BACKEND 置 false。 */

const state = {
  items: [],
  facets: { campus: {}, audience: {}, purpose: {}, kind: {}, platform: {} },
  favorites: [],
  recent: [],
  history: [],         // 搜索记录
  query: '',
  campus: '',
  audience: '',
  purpose: '',
  kind: '',
  platform: '',
  onlyFav: false,
  searchFocused: false,
  view: 'home',        // 'home' 首页 | 'browse' 列表
  mobileSite: '',      // 手机端公网网址（桌面版由后端 /api/ping 给出，静态版留空）
};

/** 有没有本地后端。静态托管时是 false，此时所有 /api/* 都由 localApi 顶上。 */
let BACKEND = true;


const CAMPUS_ORDER = ['通用', '思明校区', '翔安校区', '漳州校区', '马来西亚分校'];
const AUDIENCE_ORDER = ['全体', '本科生', '研究生', '教师', '校友', '访客/公众'];
const PURPOSE_ORDER = ['学习', '科研', '办事', '生活', '资讯', '出行', '其他'];
const KIND_ORDER = ['web', 'miniprogram', 'wechat', 'workwechat', 'unionpay', 'app', 'confuse', 'thirdparty'];
const PLATFORM_ORDER = ['mobile', 'pc', 'both', 'offline'];
const PLATFORM_LABELS = { mobile: '手机端', pc: '电脑端', both: '手机+电脑', offline: '线下' };

const $ = (sel) => document.querySelector(sel);

/* ------------------------------------------------ 数据层
   桌面版有本地后端，静态版没有。api() 统一入口：后端在就走后端，
   后端没了（或本来就是静态托管）就交给下面的 localApi 用浏览器自带的存储顶上。 */

const LS_KEY = 'xmuhub';
const memoryStore = {};          // localStorage 不可用时（隐私模式）退化到内存

const store = {
  read() {
    try {
      return JSON.parse(localStorage.getItem(LS_KEY)) || {};
    } catch {
      return memoryStore;
    }
  },
  write(patch) {
    const data = Object.assign({}, this.read(), patch);
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(data));
    } catch {
      Object.assign(memoryStore, data);
    }
    return data;
  },
};

function uniqPush(list, value, max) {
  return [value, ...list.filter((x) => x !== value)].slice(0, max);
}

/* 静态版：按分数挑最相关的入口（与后端 /api/search 同一套打分与同义词扩展） */
function localSearch(query, limit = 3) {
  const terms = expandTerms(String(query || ''), tokenize(query));
  const rows = [];
  for (const item of state.items) {
    const score = scoreItem(item, terms);
    if (terms.length && score <= 0) continue;
    rows.push({ item, s: score });
  }
  rows.sort((a, b) => {
    if (b.s !== a.s) return b.s - a.s;
    if (!!b.item.hot !== !!a.item.hot) return b.item.hot ? 1 : -1;
    return a.item.name.localeCompare(b.item.name, 'zh');
  });
  return rows.slice(0, limit).map((r) => r.item);
}

/* 静态版：本地检索式回答（对应后端的 local_answer） */
function localAnswer(question) {
  const picks = localSearch(question, 3);
  if (!picks.length) {
    return {
      ok: true, engine: 'local', label: '本地检索', items: [], note: '',
      answer: '没有找到匹配的入口。可以换个说法，例如「研究生查成绩」「宿舍报修」「预约进校」。',
    };
  }
  const parts = picks.map((it) => {
    const how = it.entry || it.url || '';
    return `「${it.name}」（${it.kindLabel}）${how ? '：' + how : ''}`;
  });
  let answer = `本地检索到相关入口：${parts.join('；')}。`;
  if (picks.some((it) => !it.url)) answer += '小程序需在微信里搜索名称打开。';
  return { ok: true, engine: 'local', label: '本地检索', answer, items: picks.map((it) => it.id), note: '' };
}

/* 静态版：用系统浏览器打开（手机上就是新标签 / 站内浏览器）
   装到主屏后（standalone）万一把 window.open 拦了，就退回"点一个真链接"——
   注意不能用 location.href：那会把 App 窗口本身导航走，而且没有返回键。 */
function localOpen(payload) {
  const item = state.items.find((i) => i.id === payload.id);
  const url = (item && item.url) || payload.url || '';
  if (!url) return { ok: false, error: item && item.entry ? `小程序：${item.entry}` : '这条没有网址' };
  let opened = null;
  try {
    opened = window.open(url, '_blank', 'noopener,noreferrer');
  } catch { /* 被拦了就往下走 */ }
  if (!opened) {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }
  return { ok: true, opened: url };
}

/* 静态版把后端那 8 个接口都实现了；本机模型那几个（/api/ai/*）手机上没有，直接说不可用 */
function localApi(path, payload = {}) {
  switch (path) {
    case '/api/catalog':
      return Promise.resolve({ items: state.items, facets: state.facets });
    case '/api/userdata':
      return Promise.resolve(store.read());
    case '/api/ai':
      return Promise.resolve({ provider: 'local', label: '本地检索', model: '-', chainLabels: ['本地检索'] });
    case '/api/favorite': {
      const on = payload.on === undefined
        ? !state.favorites.includes(payload.id)
        : Boolean(payload.on);
      const favorites = on
        ? uniqPush(state.favorites, payload.id, 999)
        : state.favorites.filter((x) => x !== payload.id);
      store.write({ favorites });
      return Promise.resolve({ favorites });
    }
    case '/api/touch': {
      const recent = uniqPush(state.recent, payload.id, 12);
      store.write({ recent });
      return Promise.resolve({ recent });
    }
    case '/api/history': {
      if (payload.clear) {
        store.write({ history: [] });
        return Promise.resolve({ history: [] });
      }
      const query = String(payload.query || '').trim();
      const history = query.length < 2 ? state.history : uniqPush(state.history, query, 12);
      store.write({ history });
      return Promise.resolve({ history });
    }
    case '/api/profile': {
      const profile = {
        campus: String(payload.campus || ''),
        audience: String(payload.audience || ''),
        asked: Boolean(payload.asked),
        skipped: Boolean(payload.skipped),
      };
      store.write({ profile });
      return Promise.resolve({ ok: true, profile });
    }
    case '/api/open':
      return Promise.resolve(localOpen(payload));
    case '/api/search':
      return Promise.resolve({ items: localSearch(payload.query || '', Number(payload.limit) || 3) });
    case '/api/ask':
      return Promise.resolve(localAnswer(payload.question || ''));
    default:
      return Promise.resolve({ ok: false, offline: true, error: '静态模式下这个功能不可用（需要桌面版）' });
  }
}

function api(path, payload, method = 'POST') {
  if (BACKEND) {
    const init = method === 'GET'
      ? undefined
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload || {}) };
    return fetch(path, init)
      .then((r) => r.json())          // 400/404 的业务错误也照原样交给调用方
      .catch((err) => {               // 只有"连不上"才切换成静态实现
        BACKEND = false;
        console.warn('[xmuhub] 本地后端不可用，改用浏览器本地实现：', err && err.message);
        return localApi(path, payload || {});
      });
  }
  return localApi(path, payload || {});
}

/* ------------------------------------------------ 工具 */

/* 静态版的统计口径：和后端 Catalog.facets() 完全一致。
   portal.json 里只存 items（后端是现算的），所以没有后端时这里自己数一遍。 */
function computeFacets(items) {
  const count = (field) => {
    const out = {};
    const single = field === 'kind' || field === 'platform' || field === 'role';
    for (const it of items) {
      const values = single ? [it[field] || ''] : (it[field] || []);
      for (const v of values) out[v] = (out[v] || 0) + 1;
    }
    return out;
  };
  return {
    total: items.length,
    campus: count('campus'),
    audience: count('audience'),
    purpose: count('purpose'),
    kind: count('kind'),
    platform: count('platform'),
    role: count('role'),
  };
}

function toast(text, ms = 1900) {
  const el = $('#toast');
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, ms);
}

function esc(text) {
  return String(text == null ? '' : text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* 与后端一致的中英混合分词（单字 + 2-gram） */
const STOP = new Set('的了我想要一个有没有吗呢请问下帮个忙找在哪里怎么如何能不能可以请给出'.split(''));
function tokenize(text) {
  const out = [];
  const chunks = String(text || '').toLowerCase().match(/[a-z0-9_.]+|[\u4e00-\u9fff]+/g) || [];
  for (const c of chunks) {
    if (/[\u4e00-\u9fff]/.test(c)) {
      for (const ch of c) out.push(ch);
      for (let i = 0; i < c.length - 1; i++) out.push(c.slice(i, i + 2));
    } else out.push(c);
  }
  return out.filter((t) => t && !STOP.has(t));
}

/* 按意图扩展查询词：与后端 app.py 的 QUERY_HINTS 保持一致。
   用户说"漏水/坏了"，实际要找的是报修入口——纯字面相似度会命中"宿舍水控"。 */
const QUERY_HINTS = [
  [['漏', '堵', '坏', '故障', '跳闸', '停水', '停电', '不通', '维修'], ['报修', '维修']],
  [['借书', '还书', '续借', '查重', '文献'], ['图书馆', '借阅']],
  [['吃饭', '菜品', '餐厅', '夜宵'], ['食堂', '餐饮']],
  [['洗澡', '淋浴', '热水'], ['水控', '宿舍']],
  [['缴费', '学费', '住宿费', '交钱'], ['缴费', '财务']],
  [['看病', '挂号', '体检', '开药'], ['医院', '门诊']],
];

function expandTerms(query, terms) {
  for (const [keys, additions] of QUERY_HINTS) {
    if (keys.some((k) => query.includes(k))) {
      for (const word of additions) {
        if (!terms.includes(word)) terms.push(word);
      }
    }
  }
  return terms;
}

function scoreItem(item, terms) {
  if (!terms.length) return 0;
  const name = (item.name || '').toLowerCase();
  const kw = (item.keywords || []).join(' ').toLowerCase();
  const desc = (item.desc || '').toLowerCase();
  const group = (item.group || '').toLowerCase();
  const entry = (item.entry || '').toLowerCase();
  const tags = [...(item.campus || []), ...(item.audience || []), ...(item.purpose || [])].join(' ').toLowerCase();
  let total = 0;
  for (const t of terms) {
    const w = t.length >= 2 ? 1 : 0.25;   // 单字权重低，避免“报销”被“报名”抢走
    if (name.includes(t)) total += 6 * w;
    if (kw.includes(t)) total += 4 * w;
    if (tags.includes(t)) total += 2.5 * w;
    if (desc.includes(t)) total += 2 * w;
    if (entry.includes(t)) total += 1.5 * w;
    if (group.includes(t)) total += 1 * w;
  }
  // 检索加权用 hot（常用入口），跟首页"精选"那 7 个是两码事：
  // 精选一缩，这里的加分不能跟着少，否则搜索结果会凭空少掉一大截
  if (item.hot) total += 1.2;
  return total;
}

/* ------------------------------------------------ 筛选与渲染 */

function visibleItems() {
  const terms = expandTerms(state.query, tokenize(state.query));
  const rows = [];
  for (const item of state.items) {
    if (state.onlyFav && !state.favorites.includes(item.id)) continue;
    if (state.campus) {
      const campus = item.campus || [];
      if (!campus.includes(state.campus) && !campus.includes('通用')) continue;
    }
    if (state.audience) {
      const aud = item.audience || [];
      if (!aud.includes(state.audience) && !aud.includes('全体')) continue;
    }
    if (state.purpose && !(item.purpose || []).includes(state.purpose)) continue;
    if (state.platform && item.platform !== state.platform) continue;
    if (state.kind && item.kind !== state.kind) continue;
    const s = scoreItem(item, terms);
    if (terms.length && s <= 0) continue;
    rows.push({ item, s });
  }
  rows.sort((a, b) => {
    if (b.s !== a.s) return b.s - a.s;
    if (!!b.item.hot !== !!a.item.hot) return b.item.hot ? 1 : -1;
    return a.item.name.localeCompare(b.item.name, 'zh');
  });
  return rows.map((r) => r.item);
}

function tagHtml(item) {
  const campus = (item.campus || []).filter((c) => c !== '通用').slice(0, 2);
  const pur = (item.purpose || []).slice(0, 3);
  const aud = (item.audience || []).filter((a) => a !== '全体').slice(0, 2);
  return [
    ...campus.map((c) => `<span class="tag">${esc(c)}</span>`),
    ...pur.map((p) => `<span class="tag pur">${esc(p)}</span>`),
    ...aud.map((a) => `<span class="tag aud">${esc(a)}</span>`),
  ].join('');
}

function cardHtml(item) {
  const fav = state.favorites.includes(item.id);
  const action = item.url
    ? `<button class="btn primary" data-act="open" data-id="${item.id}">打开</button>`
    : `<button class="btn primary" data-act="copy" data-id="${item.id}">复制名称</button>`;
  const plat = item.platform || 'pc';
  const broken = item.linkOk === false
    ? `<span class="badge warn" title="实测无法打开（${esc(item.linkCheckedAt || '')} 检测，HTTP ${esc(String(item.linkStatus || 0))}）">⚠ 打不开</span>`
    : '';
  return `
  <article class="card ${fav ? 'is-fav' : ''} plat-${plat}" data-id="${item.id}">
    <div class="card-head">
      <div class="card-title">${item.featured ? '<span class="star">★</span>' : ''}${esc(item.name)}</div>
      <div class="badges">
        <span class="badge plat ${plat}">${esc(item.platformLabel || PLATFORM_LABELS[plat] || '')}</span>
        <span class="badge ${item.kind}">${esc(item.kindLabel)}</span>
        ${broken}
      </div>
    </div>
    <div class="card-desc">${esc(item.desc || '（暂无简介）')}</div>
    ${item.entry ? `<div class="entry-hint">入口：${esc(item.entry)}</div>` : ''}
    <div class="card-tags">${tagHtml(item)}</div>
    <div class="card-foot">
      ${action}
      ${item.url ? `<button class="btn icon" data-act="copy" data-id="${item.id}" title="复制网址">⧉</button>` : ''}
      <button class="btn icon" data-act="fav" data-id="${item.id}" title="收藏">${fav ? '★' : '☆'}</button>
      <button class="btn icon" data-act="detail" data-id="${item.id}" title="详情">ⓘ</button>
    </div>
  </article>`;
}

/** 把"实测打不开"翻译成人话：区分"站没了"和"只是拦自动访问" */
function linkNote(item) {
  const status = Number(item.linkStatus || 0);
  if (status === 401 || status === 403) {
    return '⚠ 服务器拒绝了自动访问（多为需要登录或仅限校园网），用浏览器直接打开通常正常。';
  }
  if (status >= 300 && status < 400) {
    return '⚠ 会自动跳转（通常是登录页或新地址），浏览器打开后会转到正式入口。';
  }
  if (status >= 500) {
    return '⚠ 服务器返回错误（站点暂时故障），稍后或用浏览器重试可能恢复。';
  }
  if (status === 400) {
    return '⚠ 只接受正常浏览器访问（拒绝脚本请求），条目地址本身仍然有效。';
  }
  return '⚠ 自动检测连不上：可能仅校园网可访问，或站点已下线，建议搜索该单位最新入口。';
}

/** ⚙ 按钮状态：本机模型没就绪时高亮提示，就绪后收敛 */
function updateKeyButton(status) {
  const btn = $('#aiKeyBtn');
  if (!btn) return;
  const st = status || state.aiStatus || {};
  const ready = Boolean(st.provider && st.provider !== 'local');
  btn.classList.toggle('attention', !ready);
  btn.classList.toggle('on', ready);
  const text = $('#aiKeyBtnText');
  if (text) text.textContent = ready ? '本机 AI' : '配置本机 AI';
  btn.title = ready
    ? `当前引擎：${st.label || ''}（点这里换模型）`
    : '还没有本机模型，问答走内置本地检索；点这里可下载本机模型（免费、不用 Key）';
}

function hasFilters() {
  return Boolean(state.campus || state.audience || state.purpose || state.kind || state.platform || state.onlyFav);
}

/** 去掉全部筛选后这个关键词还剩多少条（用于"放宽筛选"提示） */
function countWithoutFilters() {
  const saved = { ...state };
  Object.assign(state, { campus: '', audience: '', purpose: '', kind: '', platform: '', onlyFav: false });
  const n = visibleItems().length;
  Object.assign(state, saved);
  return n;
}

// 空状态下的自救建议：换几个最可能命中的说法
const EMPTY_SUGGESTIONS = ['成绩', '报修', '宿舍', '一卡通', '场馆预约'];

function renderEmptyState() {
  const box = $('#empty');
  const hint = $('#emptyHint');
  const actions = $('#emptyActions');
  const sugs = $('#emptySugs');

  // 目录根本没加载（后端断开）时，别说"没有匹配"，直接把原因说清楚
  if (!state.items.length) {
    $('#emptyBoot').hidden = false;
    $('#emptyNormal').hidden = true;
    return;
  }
  $('#emptyBoot').hidden = true;
  $('#emptyNormal').hidden = false;

  const relaxing = hasFilters() ? countWithoutFilters() : 0;
  const parts = [];
  if (state.query) parts.push(`关键词「${state.query}」`);
  if (state.campus) parts.push(state.campus);
  if (state.audience) parts.push(state.audience);
  if (state.purpose) parts.push(state.purpose);
  if (state.platform) parts.push(PLATFORM_LABELS[state.platform] || state.platform);
  if (state.onlyFav) parts.push('仅收藏');
  hint.textContent = parts.length
    ? `${parts.join(' · ')} 这些条件叠加后没有结果${relaxing ? `；去掉筛选后还有 ${relaxing} 条相关入口` : ''}。`
    : '试试更口语的说法，或者按 Ctrl K 打开命令面板。';

  const btns = [];
  if (relaxing) btns.push('<button class="btn primary" data-act="relax">放宽筛选，看这 ' + relaxing + ' 条</button>');
  if (state.query) btns.push('<button class="btn" data-act="ask-ai-empty">✨ 让 AI 帮我找</button>');
  btns.push('<button class="btn ghost" data-act="show-all">清空条件，浏览全部 ' + state.items.length + ' 条</button>');
  actions.innerHTML = btns.join('');

  sugs.innerHTML = state.query
    ? EMPTY_SUGGESTIONS.map((q) => `<span class="chip sug" data-sug="${esc(q)}">试试「${esc(q)}」</span>`).join('')
    : '';
}

function render() {
  const rows = visibleItems();
  $('#list').innerHTML = rows.map(cardHtml).join('');
  $('#empty').hidden = rows.length > 0;
  if (!rows.length) renderEmptyState();

  const bits = [];
  if (state.query) bits.push(`关键词「${state.query}」`);
  if (state.campus) bits.push(state.campus);
  if (state.audience) bits.push(state.audience);
  if (state.purpose) bits.push(state.purpose);
  if (state.kind) bits.push($(`#fKind .chip[data-v="${state.kind}"]`)?.textContent.replace(/\d+$/, '') || state.kind);
  if (state.platform) bits.push(PLATFORM_LABELS[state.platform] || state.platform);
  if (state.onlyFav) bits.push('仅收藏');
  $('#listInfo').textContent = bits.length
    ? `${bits.join(' · ')} — 共 ${rows.length} 条`
    : `全部入口 — 共 ${rows.length} 条`;
  syncHash();
}

function chip(label, value, count, active, group) {
  return `<span class="chip ${active ? 'active' : ''}" data-g="${group}" data-v="${esc(value)}">${esc(label)}<span class="n">${count}</span></span>`;
}

function renderSidebar() {
  const f = state.facets;
  const render = (sel, group, order, counts, current) => {
    const values = order.filter((v) => counts[v]);
    $(sel).innerHTML = values.map((v) => chip(v, v, counts[v], current === v, group)).join('');
  };
  render('#fPurpose', 'purpose', PURPOSE_ORDER, f.purpose || {}, state.purpose);

  renderProfileCard();

  const kindLabels = {};
  state.items.forEach((it) => { kindLabels[it.kind] = it.kindLabel; });
  const kinds = KIND_ORDER.filter((k) => (f.kind || {})[k]);
  $('#fKind').innerHTML = kinds
    .map((k) => chip(kindLabels[k] || k, k, f.kind[k], state.kind === k, 'kind')).join('');

  const platforms = PLATFORM_ORDER.filter((p) => (f.platform || {})[p]);
  $('#fPlatform').innerHTML = platforms
    .map((p) => chip(PLATFORM_LABELS[p] || p, p, f.platform[p], state.platform === p, 'platform')).join('');

  const recentItems = state.recent.map((id) => state.items.find((i) => i.id === id)).filter(Boolean);
  $('#recentBlock').hidden = recentItems.length === 0;
  $('#recentList').innerHTML = recentItems
    .map((it) => `<a href="#" data-act="detail" data-id="${it.id}">${esc(it.name)}</a>`).join('');

  renderHistoryBlock();

  $('#favBtn').classList.toggle('on', state.onlyFav);
  $('#favBtn').textContent = `★ 只看收藏${state.favorites.length ? ` (${state.favorites.length})` : ''}`;
  refreshSideDot();
}

/* ------------------------------------------------ 打开网址 */

async function openEntry(item) {
  if (!item || !item.url) {
    toast(item && item.entry ? `小程序：${item.entry}` : '这条没有网址');
    return;
  }
  const res = await api('/api/open', { id: item.id });
  toast(res.ok ? '已在系统浏览器打开' : (res.error || '打开失败'));
  await api('/api/touch', { id: item.id });
  state.recent = [item.id, ...state.recent.filter((x) => x !== item.id)].slice(0, 12);
  renderSidebar();
}

const OB_CAMPUS = [
  ['不限', ''], ['思明校区', '思明校区'], ['翔安校区', '翔安校区'],
  ['漳州校区', '漳州校区'], ['马来西亚分校', '马来西亚分校'],
];
const OB_AUDIENCE = [
  ['本科生', '本科生'], ['研究生', '研究生'], ['教师', '教师'],
  ['校友', '校友'], ['访客 / 公众', '访客/公众'], ['不限', ''],
];

let obDraft = { campus: '', audience: '' };

function renderOnboard() {
  const draw = (sel, choices, field) => {
    $(sel).innerHTML = choices.map(([label, value]) =>
      `<button type="button" class="ob-choice ${obDraft[field] === value ? 'active' : ''}"
        data-ob="${field}" data-value="${esc(value)}">${esc(label)}</button>`).join('');
  };
  draw('#obCampus', OB_CAMPUS, 'campus');
  draw('#obAudience', OB_AUDIENCE, 'audience');
}

function openOnboard(force = false) {
  const p = state.profile || {};
  obDraft = { campus: p.campus || '', audience: p.audience || '' };
  renderOnboard();
  $('#onboard').hidden = false;
  $('#obSkip').textContent = force ? '取消' : '先跳过，看全部';
}

async function saveProfile(skipped = false) {
  state.campus = obDraft.campus;
  state.audience = obDraft.audience;
  state.profile = {
    campus: obDraft.campus,
    audience: obDraft.audience,
    asked: true,
    skipped: skipped && !obDraft.campus && !obDraft.audience,
  };
  $('#onboard').hidden = true;
  renderSidebar();
  render();
  if (state.view === 'home') renderHome();
  syncHash();
  try {
    await api('/api/profile', state.profile);
  } catch { /* 存不上也不影响本次使用 */ }
}

function renderProfileCard() {
  const body = $('#profileBody');
  if (!body) return;
  const p = state.profile || {};
  if (!p.campus && !p.audience) {
    body.innerHTML = '<span class="pc-dim">未设置（显示全部）</span>';
  } else {
    body.textContent = [p.campus || '不限校区', p.audience || '不限身份'].join(' · ');
  }
}

document.addEventListener('click', (ev) => {
  const choice = ev.target.closest('[data-ob]');
  if (choice) {
    obDraft[choice.dataset.ob] = choice.dataset.value;
    renderOnboard();
    return;
  }
  if (ev.target.closest('#obDone')) { saveProfile(false); return; }
  if (ev.target.closest('#obSkip')) {
    if ($('#obSkip').textContent.startsWith('取消')) $('#onboard').hidden = true;
    else saveProfile(true);
    return;
  }
  if (ev.target.closest('#profileEdit')) { openOnboard(true); }
});



async function recordSearch(query) {
  const q = (query || '').trim();
  if (q.length < 2) return;
  try {
    const res = await api('/api/history', { query: q });
    state.history = res.history || state.history;
    renderHistoryBlock();
  } catch {
    // 记录失败不影响搜索本身
  }
}

function applyHistoryTerm(term) {
  state.query = term;
  $('#search').value = term;
  $('#searchHist').hidden = true;
  if (state.view === 'home') setView('browse');
  else render();
  recordSearch(term);
}

function renderHistoryBlock() {
  const list = $('#historyList');
  if (!list) return;
  $('#historyBlock').hidden = state.history.length === 0;
  list.innerHTML = state.history
    .map((q) => `<span class="chip hist" data-hist="${esc(q)}" title="再次搜索：${esc(q)}">🕘 ${esc(q)}</span>`)
    .join('');
}

function renderSearchHist() {
  const box = $('#searchHist');
  if (!box) return;
  const show = !!state.searchFocused && state.history.length > 0;
  box.hidden = !show;
  if (!show) return;
  $('#histListTop').innerHTML = state.history
    .map((q) => `<button type="button" class="sh-item" data-hist="${esc(q)}">🕘 ${esc(q)}</button>`)
    .join('');
}

async function clearSearchHistory() {
  const res = await api('/api/history', { clear: true });
  state.history = res.history || [];
  renderHistoryBlock();
  renderSearchHist();
  toast('已清空搜索记录');
}

function renderStats() {
  const f = state.facets;
  const total = f.total || 0;
  const web = f.kind?.web || 0;
  const mp = (f.kind?.miniprogram || 0) + (f.kind?.unionpay || 0) + (f.kind?.thirdparty || 0);
  const wx = (f.kind?.wechat || 0) + (f.kind?.workwechat || 0);
  const pc = f.platform?.pc || 0;
  const mo = f.platform?.mobile || 0;
  const bo = f.platform?.both || 0;
  const pct = (n) => (total ? Math.max(3, Math.round((n / total) * 100)) : 0);
  const bar = (label, n, color) =>
    `<div class="bar-row"><span class="bar-label">${label}</span>` +
    `<div class="bar"><i style="width:${pct(n)}%;background:${color}"></i></div>` +
    `<span class="bar-val">${n}</span></div>`;

  $('#stats').innerHTML = `
    <div class="stat-head">
      <span class="stat-num">${total}</span>
      <span class="stat-unit"> 个入口已收录</span>
    </div>
    <div class="stat-bars">
      ${bar('网站系统', web, 'var(--pc)')}
      ${bar('小程序', mp, 'var(--mobile)')}
      ${bar('公众号', wx, 'var(--both)')}
    </div>
    <div class="stat-foot">PC ${pc} · MOBILE ${mo} · BOTH ${bo}</div>`;
  $('#footTotal').textContent = total;
}

/* ------------------------------------------------ 交互 */

async function openItem(item) {
  if (item.url) {
    // 统一用系统浏览器打开：站点该登录就登录、该用哪个浏览器内核就用哪个，
    // 不受内嵌窗口的 X-Frame-Options 与脚本限制。
    const res = await api('/api/open', { id: item.id });
    if (!res.ok) return toast(res.error || '打开失败');
    await api('/api/touch', { id: item.id });
    state.recent = [item.id, ...state.recent.filter((x) => x !== item.id)].slice(0, 12);
    renderSidebar();
    if (state.view === 'home') renderHome();
    toast(`已在浏览器打开：${item.name}`);
  } else {
    await copyText(item.name);
    await api('/api/touch', { id: item.id });
    state.recent = [item.id, ...state.recent.filter((x) => x !== item.id)].slice(0, 12);
    renderSidebar();
    if (state.view === 'home') renderHome();
  }
}

/** 只负责写剪贴板，不弹提示（提示语由调用方决定） */
async function writeClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    // http 页面 / 老浏览器没有 clipboard API：退回 execCommand
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
}

async function copyText(text) {
  await writeClipboard(text);
  toast(`已复制：${text} — 打开微信搜索即可`);
}

async function toggleFav(item) {
  const res = await api('/api/favorite', { id: item.id });
  state.favorites = res.favorites || [];
  renderSidebar();
  render();
  if (state.view === 'home') renderHome();
  toast(state.favorites.includes(item.id) ? `已收藏：${item.name}` : `已取消收藏：${item.name}`);
}

/* 这些入口"在手机上其实是在某个 App 里用的"——手机上能给的就多一步：
   试着用 App 的 URL Scheme 直接唤起（只在"确实存在且相对可靠"的 scheme 上做，
   拿不准的宁可不做，免得点了没反应更像 bug）。
   注意：**微信内置浏览器会拦掉这些跳转**，所以微信里只给文字引导。 */
const APP_SCHEMES = [
  { re: /支付宝|一卡通充值/, scheme: 'alipays://', app: '支付宝' },
  { re: /企业微信/, scheme: 'wxwork://', app: '企业微信' },
];
// 微信相关的小程序/公众号：唤起微信本身是有意义的（用户接着粘贴搜索）
const WECHAT_KINDS = new Set(['miniprogram', 'wechat', 'workwechat', 'unionpay']);

function appSchemeFor(item) {
  const hay = `${item.name} ${item.desc || ''} ${item.entry || ''}`;
  return APP_SCHEMES.find((s) => s.re.test(hay)) || null;
}

/** 试着唤起 App：1.6 秒内没离开本页就认为是没装/被拦，给一句人话提示 */
function tryOpenApp(scheme, appName) {
  let left = false;
  const onHide = () => { left = true; };
  document.addEventListener('visibilitychange', onHide, { once: true });
  setTimeout(() => {
    document.removeEventListener('visibilitychange', onHide);
    if (!left && document.visibilityState === 'visible') {
      toast(isWeChat()
        ? `微信里打不开${appName}：点右上角 ⋯ →「在浏览器中打开」再试`
        : `没能唤起${appName}：先手动打开${appName}，再回来点一次`, 3200);
    }
  }, 1600);
  window.location.href = scheme;
}

/** 手机上给"没有网址 / 打不开"的入口生成一段"具体怎么办"。
 *
 *  目录里 320 条有 89 条没法直接跳转（45 条没有网址：小程序·公众号·App；
 *  44 条实测打不开或标题已变），光说"自行搜索"等于没说，所以这里按情况给
 *  可照做的步骤，能点的下一步都做成按钮。桌面版同样显示，只是按钮少几个。
 */
function helperEntry(key) {
  const table = {
    cas: /统一身份认证/,
    webvpn: /WebVPN|校外访问认证入口/,
    libproxy: /数据库代理/,
  };
  const re = table[key];
  if (!re) return null;
  return state.items.find((i) => i.url && re.test(i.name)) || null;
}

function helperButton(key, label) {
  const item = helperEntry(key);
  if (!item) return '';
  return `<button class="btn" data-act="open" data-id="${item.id}">${label}</button>`;
}

function entryHelp(item) {
  const handheld = isHandheld();
  const inWeChat = isWeChat();
  const scheme = appSchemeFor(item);
  const status = Number(item.linkStatus || 0);
  const noUrl = !item.url;
  const broken = item.linkOk === false;
  const mismatch = Boolean(item.linkTitleMismatch);

  if (!noUrl && !broken && !mismatch) return '';    // 能直接打开就不用解释

  const steps = [];
  const buttons = [];
  let title = '怎么进';
  if (noUrl) {
    title = handheld ? '在手机上怎么进' : '怎么进（这条没有网址）';
  } else if (broken) {
    title = '打不开？这样进';
  } else {
    title = '可能已改版，这样进';
  }

  if (noUrl) {
    if (scheme && handheld && !inWeChat) {
      steps.push(`这条要在 <b>${scheme.app}</b> 里用：点下面的「打开${scheme.app}」`);
      steps.push(`在里面搜索 <b>${esc(item.name)}</b>；没装的话先去应用商店装上`);
      buttons.push(`<button class="btn primary" data-act="openapp" data-id="${item.id}">打开${scheme.app}</button>`);
    } else if (WECHAT_KINDS.has(item.kind)) {
      if (inWeChat) {
        steps.push('点下面的「复制名称」，然后回到聊天列表、点顶部搜索框粘贴');
        steps.push('搜到后点开，右上角 <b>···</b> →「添加到我的小程序」，以后下拉就能找到');
      } else if (handheld) {
        steps.push('点下面的「复制名称并打开微信」——名称会进剪贴板，微信也会被唤起');
        steps.push('在微信顶部搜索框 <b>长按粘贴</b>，就能搜到它');
      } else {
        steps.push('点下面的「复制名称」，再打开<b>微信</b>，在顶部搜索框粘贴（Ctrl+V）');
        steps.push('搜到后点开，右上角 <b>···</b> →「添加到我的小程序」，以后好找');
      }
    } else {
      steps.push(`点「复制名称」，到<b>微信搜一搜</b>或应用商店里搜 <b>${esc(item.name)}</b>`);
    }
    if (!(scheme && handheld && !inWeChat)) {
      buttons.push(`<button class="btn primary" data-act="copywechat" data-id="${item.id}">${
        handheld && !inWeChat && WECHAT_KINDS.has(item.kind) ? '复制名称并打开微信' : '复制名称'}</button>`);
    }
  } else if (status === 401 || status === 403) {
    steps.push('多半是<b>需要登录</b>或<b>只限校园网</b>：先登录统一身份认证，再点上面的「在浏览器打开」');
    steps.push('不在校园网里的话，连上<b>校园网</b>，或者改用 <b>WebVPN</b> 访问');
    buttons.push(helperButton('cas', '先去登录统一身份认证'));
    buttons.push(helperButton('webvpn', '打开 WebVPN'));
  } else if (status >= 300 && status < 400) {
    steps.push('这条会自动跳到<b>登录页或新地址</b>：用上面的「在浏览器打开」，跟着跳转走就行');
    buttons.push(helperButton('cas', '先去登录统一身份认证'));
  } else if (status >= 500) {
    steps.push('站点这会儿<b>自己出故障了</b>：等一会儿再试，或先用「浏览器打开」直接访问');
  } else if (status === 404) {
    steps.push('地址可能<b>已改版或迁移</b>：建议从上级官网的导航里重新找，或按名称搜最新入口');
  } else if (broken) {
    steps.push('自动检测连不上：多半<b>只限校园网</b>，也可能站点已下线');
    steps.push('在校园网里就直接用「浏览器打开」；不在的话走 <b>WebVPN</b>');
    buttons.push(helperButton('webvpn', '打开 WebVPN'));
  } else if (mismatch) {
    steps.push(`打开后页面标题是「${esc(item.linkTitle || '（无标题）')}」，与条目名不一致，可能<b>已改版或改过地址</b>`);
    steps.push('地址本身还能打开，先按上面的按钮进去看；找不到想要的内容就从官网导航重新找');
  }

  if (noUrl) {
    buttons.push(`<button class="btn" data-act="copy" data-id="${item.id}">只复制名称</button>`);
  } else {
    buttons.push(`<button class="btn" data-act="copyurl" data-id="${item.id}">复制网址</button>`);
  }

  const fallback = `都试过还不行：点「复制名称」，到<b>微信搜一搜</b>或百度搜「<b>厦门大学 ${esc(item.name)}</b>」，`
    + '一般能找到最新入口。';

  return `<section class="di-block di-help">
    <h4>${title}</h4>
    <ol class="di-steps">${steps.map((s) => `<li>${s}</li>`).join('')}</ol>
    <div class="di-actions">${buttons.join('')}</div>
    <p class="di-fallback">${fallback}</p>
  </section>`;
}

function openDrawer(item) {
  const plat = item.platform || 'pc';
  const fav = state.favorites.includes(item.id);
  const related = state.items
    .filter((i) => i.id !== item.id && i.group === item.group)
    .slice(0, 6);

  $('#drawerBody').innerHTML = `
    <div class="drawer-inner">
      <div class="di-badges">
        <span class="badge plat ${plat}">${esc(item.platformLabel || PLATFORM_LABELS[plat] || '')}</span>
        <span class="badge ${item.kind}">${esc(item.kindLabel)}</span>
        ${item.featured ? '<span class="badge featured">精选</span>' : ''}
      </div>

      <h3 class="di-title">${esc(item.name)}</h3>
      <p class="di-sub">${esc(item.group || '')}${item.source ? ' · 收录自 ' + esc(item.source) : ''}</p>

      <div class="di-actions">
        ${item.url
          ? `<button class="btn primary" data-act="open" data-id="${item.id}">在浏览器打开</button>
             <button class="btn" data-act="copyurl" data-id="${item.id}">复制网址</button>`
          : `<button class="btn primary" data-act="copy" data-id="${item.id}">复制小程序名称</button>`}
        <button class="btn ${fav ? 'on' : ''}" data-act="fav" data-id="${item.id}">
          ${fav ? '★ 已收藏' : '☆ 收藏'}
        </button>
      </div>

      ${entryHelp(item)}

      ${item.desc ? `<section class="di-block"><h4>是什么</h4>
        <p class="di-text">${esc(item.desc)}</p></section>` : ''}

      ${item.linkOk === false || item.linkTitleMismatch ? `
      <section class="di-block"><h4>实测证据</h4>
        <p class="di-text link-note">${item.linkOk === false
          ? `${linkNote(item)}（${esc(item.linkCheckedAt || '')} 自动检测，HTTP ${esc(String(item.linkStatus || 0))}）`
          : `打开后页面标题是「${esc(item.linkTitle || '（无标题）')}」，与条目名不完全一致。`}</p>
      </section>` : ''}

      ${item.entry ? `<section class="di-block"><h4>怎么进</h4>
        <p class="di-text">${esc(item.entry)}</p></section>` : ''}

      ${item.url ? `<section class="di-block"><h4>网址</h4>
        <div class="di-url"><code>${esc(item.url)}</code>
          <button class="btn sm" data-act="copyurl" data-id="${item.id}">复制</button></div>
        ${(item.urls || []).length > 1
          ? `<div class="di-url dim"><code>${item.urls.slice(1).map(esc).join('</code></div><div class="di-url dim"><code>')}</code></div>`
          : ''}
      </section>` : ''}

      <section class="di-block"><h4>分类</h4>
        <div class="card-tags">${tagHtml(item) || '<span class="tag">未分类</span>'}</div>
      </section>

      ${(item.keywords || []).length ? `<section class="di-block"><h4>也能这样搜</h4>
        <div class="card-tags">${item.keywords.slice(0, 12).map((k) => `<span class="tag">${esc(k)}</span>`).join('')}</div>
      </section>` : ''}

      ${related.length ? `<section class="di-block"><h4>同板块的其他入口</h4>
        <div class="related">${related.map((r) =>
          `<button data-act="detail" data-id="${r.id}">
             <span class="rname">${esc(r.name)}</span>
             <span class="rmeta">${esc(r.platformLabel || '')}</span>
           </button>`).join('')}</div>
      </section>` : ''}
    </div>`;
  $('#drawer').hidden = false;
}

/* ------------------------------------------------ AI 面板 */

const aiHistory = [];

function aiPush(role, html) {
  const el = document.createElement('div');
  el.className = `msg ${role === 'user' ? 'me' : 'bot'}`;
  el.innerHTML = html;
  $('#aiBody').appendChild(el);
  $('#aiBody').scrollTop = $('#aiBody').scrollHeight;
  return el;
}

async function askAI() {
  const input = $('#aiInput');
  const question = input.value.trim();
  if (!question) return;
  input.value = '';
  aiPush('user', esc(question));
  aiHistory.push({ role: 'user', content: question });

  // 第一段：本地检索秒出候选（AI 免费接口约需十几秒，先给用户可点的结果）
  const box = aiPush('bot', '<span class="pending">本地检索中…</span>');
  let localPicks = [];
  try {
    const local = await api('/api/search', { query: question, limit: 3 });
    localPicks = (local.items || []).slice(0, 3);
  } catch (err) { /* 本地检索失败不阻塞 AI */ }

  const pickBtn = (p) =>
    `<button data-act="detail" data-id="${p.id}">${esc(p.name)} · ${esc(p.platformLabel || '')}／${esc(p.kindLabel)}</button>`;

  if (localPicks.length) {
    box.innerHTML =
      `<span class="hint">本地检索到 ${localPicks.length} 个入口：</span>
       <div class="picks">${localPicks.map(pickBtn).join('')}</div>
       <span class="pending">✨ 正在请 AI 精选…</span>`;
  } else {
    box.innerHTML = '<span class="pending">✨ 正在请 AI 帮你找…</span>';
  }

  // 第二段：AI 精选（失败时后端会返回本地答案）
  let res;
  try {
    res = await api('/api/ask', { question, history: aiHistory.slice(-4) });
  } catch (err) {
    box.innerHTML = `<span class="hint">网络异常，先用本地结果：</span>
      <div class="picks">${localPicks.map(pickBtn).join('')}</div>`;
    return;
  }

  const label = res.label || (res.engine === 'local' ? '本地检索' : res.engine);
  $('#aiEngine').textContent = label;
  $('#aiEngine').classList.toggle('deepseek', res.engine === 'deepseek');

  const picks = (res.items || [])
    .map((id) => state.items.find((i) => i.id === id))
    .filter(Boolean);
  const picksHtml = picks.length
    ? `<div class="picks">${picks.map(pickBtn).join('')}</div>`
    : (localPicks.length ? `<div class="picks">${localPicks.map(pickBtn).join('')}</div>` : '');
  const note = res.note ? `<span class="note">${esc(res.note)}</span>` : '';
  const cached = res.cached ? '<span class="note">（命中缓存，秒回）</span>' : '';
  const engineTip = res.engine && res.engine !== 'local'
    ? `<span class="hint">${esc(label)} 精选：</span>` : '';

  box.innerHTML = `${engineTip}${esc(res.answer || '（无回答）')}${picksHtml}${cached}${note}`;
  aiHistory.push({ role: 'assistant', content: res.answer || '' });
  $('#aiBody').scrollTop = $('#aiBody').scrollHeight;
}

/* ------------------------------------------------ 事件绑定 */

document.addEventListener('click', async (ev) => {
  // 搜索记录（必须放在 .chip 分支之前：历史词也是 chip 样式，但没有 data-g）
  const histEl = ev.target.closest('[data-hist]');
  if (histEl) {
    ev.preventDefault();
    applyHistoryTerm(histEl.dataset.hist);
    return;
  }
  if (ev.target.closest('#histClear') || ev.target.closest('#histClearTop')) {
    ev.preventDefault();
    await clearSearchHistory();
    return;
  }

  const chipEl = ev.target.closest('.chip');
  if (chipEl) {
    const group = chipEl.dataset.g;
    const value = chipEl.dataset.v;
    state[group] = state[group] === value ? '' : value;
    renderSidebar();
    if (state.view === 'home') setView('browse');   // 首页点标签 → 直接进列表看结果
    else render();
    return;
  }

  const actEl = ev.target.closest('[data-act]');
  if (actEl) {
    ev.preventDefault();
    const act = actEl.dataset.act;
    // 首页那条"手机端网址"不挂在任何条目上，先处理掉
    if (act === 'mobilecopy') {
      await writeClipboard(state.mobileSite);
      toast('手机端网址已复制，发到手机上打开即可');
      return;
    }
    if (act === 'mobileopen') {
      await openMobileSite();
      return;
    }
    const item = state.items.find((i) => i.id === actEl.dataset.id);
    if (!item) return;
    if (act === 'open') await openItem(item);
    else if (act === 'copy') await copyText(item.name);
    else if (act === 'copyurl') await copyText(item.url);
    else if (act === 'copywechat') {
      // 手机上最实用的一步：复制好名称，顺手把微信唤起来，用户直接粘贴搜索
      await copyText(item.name);
      if (!isWeChat() && WECHAT_KINDS.has(item.kind)) setTimeout(() => { window.location.href = 'weixin://'; }, 350);
    }
    else if (act === 'openapp') {
      const s = appSchemeFor(item);
      if (s) tryOpenApp(s.scheme, s.app);
    }
    else if (act === 'fav') await toggleFav(item);
    else if (act === 'detail') openDrawer(item);
    return;
  }

  if (ev.target.closest('[data-close]')) {
    $('#drawer').hidden = true;
  }
});

$('#search').addEventListener('input', (ev) => {
  state.query = ev.target.value.trim();
  if (state.view === 'home') setView('browse');   // 一开始搜索就切到列表
  else render();
  renderSearchHist();
});

// 回车/确认才算一次"搜索记录"（边打字边记会塞满垃圾词）
$('#search').addEventListener('keydown', async (ev) => {
  if (ev.key !== 'Enter') return;
  ev.preventDefault();
  await recordSearch(state.query);
  renderSearchHist();
});
$('#search').addEventListener('focus', () => { state.searchFocused = true; renderSearchHist(); });
$('#search').addEventListener('blur', () => {
  // 延迟收起，避免点击下拉里的历史词时先失焦
  setTimeout(() => { state.searchFocused = false; $('#searchHist').hidden = true; }, 160);
});

$('#resetBtn').addEventListener('click', () => {
  Object.assign(state, { query: '', campus: '', audience: '', purpose: '', kind: '', platform: '', onlyFav: false });
  $('#search').value = '';
  renderSidebar();
  setView('browse');
});

$('#favBtn').addEventListener('click', () => {
  state.onlyFav = !state.onlyFav;
  renderSidebar();
  render();
});

$('#aiBtn').addEventListener('click', () => {
  const panel = $('#aiPanel');
  panel.hidden = !panel.hidden;
  if (!panel.hidden) $('#aiInput').focus();
});
$('#aiClose').addEventListener('click', () => { $('#aiPanel').hidden = true; });
$('#aiSend').addEventListener('click', askAI);

/* ------------------------------------------------ 本机 AI 设置（无需 Key） */

function renderAiSettings(status) {
  if (status) state.aiStatus = status;
  updateKeyButton(state.aiStatus);
}

async function openAiSettings() {
  const box = $('#aiKeys');
  box.hidden = false;
  try {
    renderAiSettings(await fetch('/api/ai').then((r) => r.json()));
  } catch {
    renderAiSettings();
  }
  refreshLocalModel();
}

/* ------- 本机模型（永久免费、不需要 Key）：检测 / 一键下载 / 进度条 ------- */

let pullTimer = null;

function setProgress(show, percent, text) {
  const box = $('#akProgress');
  if (!box) return;
  box.hidden = !show;
  if (!show) return;
  $('#akBarFill').style.width = `${Math.max(0, Math.min(100, percent || 0))}%`;
  $('#akProgressText').textContent = text || '';
}

async function refreshLocalModel() {
  const box = $('#akLocalBody');
  if (!box) return;
  box.textContent = '检测中…';
  let data = {};
  try {
    data = await api('/api/ai/local', {});
  } catch {
    box.textContent = '检测失败（本地服务是否在运行？）';
    return;
  }
  const info = data.local || {};
  const suggest = data.suggest || [];
  const sources = data.sources || [];
  const running = Boolean(info.running);
  const installed = Boolean(info.installed);

  const picker = running && (info.models || []).length ? `
    <div class="ak-pick">
      <select id="akLocalPick">${info.models.map((m) =>
        `<option value="${esc(m)}"${m === info.current ? ' selected' : ''}>${esc(m)}</option>`).join('')}</select>
      <button class="btn primary sm" id="akLocalUse">用这个模型</button>
    </div>` : '';

  // 推荐模型始终显示：没装 Ollama 时按钮置灰并说明原因，用户才知道下一步要干什么
  const modelRows = suggest.map((m) => {
    const downloaded = (info.models || []).includes(m.id);
    const label = downloaded ? '已下载' : '下载';
    const disabled = downloaded || !running ? 'disabled' : '';
    return `<div class="ak-model-row">
      <span class="mid">${esc(m.id)}</span>
      <span class="msize">${esc(m.size)}</span>
      <span class="mnote">${esc(m.note)}</span>
      <button class="btn ${downloaded ? '' : 'primary'} sm" data-pull="${esc(m.id)}" ${disabled}
        title="${running ? '' : '先安装并启动 Ollama 才能下载模型'}">${label}</button>
    </div>`;
  }).join('');

  const state = running
    ? `✅ Ollama 正在运行${(info.models || []).length ? `，已有 ${info.models.length} 个模型` : '，还没有下载任何模型'}`
    : (installed ? '⚠️ 已安装 Ollama，但服务没在运行' : '❌ 未检测到 Ollama');

  box.innerHTML = `
    <div class="ak-state">${state}</div>
    ${picker}
    ${!running ? `
    <div class="ak-local-actions">
      ${installed
        ? '<button class="btn primary sm" id="akServe">启动 Ollama 服务</button>'
        : `<button class="btn primary sm" id="akInstall">下载 Ollama 安装包（${esc('约 1.57 GB')}）</button>`}
      <a class="btn sm" href="https://ollama.com/download" target="_blank" rel="noreferrer">打开下载页</a>
    </div>` : ''}
    <div class="ak-models-title">推荐模型（本机跑，免费）${running ? '' : '——先装好 Ollama 才能下载'}</div>
    ${modelRows}
    <div class="ak-note">
      下载源：${esc(sources.slice(0, 2).join(' / ') || '官方')}（官方站与 GitHub 在国内常连不上，会自动走加速源）。
      ${running ? '' : '若下载源都连不上，可在下面填一个能用的安装包地址。'}
    </div>
    ${running ? '' : `
    <div class="ak-custom">
      <input id="akSetupUrl" type="text" placeholder="安装包地址（可选，例如你能访问的镜像链接）" autocomplete="off">
      <button class="btn sm" id="akInstallCustom">用这个地址下载</button>
    </div>`}
  `;
  $('#akLocalUse')?.addEventListener('click', async () => {
    const picked = $('#akLocalPick').value;
    const res = await api('/api/ai/local', { model: picked });
    if (!res.ok) return toast(res.error || '设置失败');
    showVerify(res.verify);
    renderAiSettings(res.status);
    toast(res.verify?.ok ? `✔ 已切到本机模型 ${picked}` : `已选 ${picked}，但测试未通过`);
  });
  $('#akInstall')?.addEventListener('click', () => startInstaller(''));
  $('#akInstallCustom')?.addEventListener('click', () => startInstaller($('#akSetupUrl').value.trim()));
  $('#akServe')?.addEventListener('click', async () => {
    const res = await api('/api/ai/serve', {});
    toast(res.ok ? '✔ Ollama 已启动' : (res.error || '启动失败'));
    renderAiSettings(res.status);
    refreshLocalModel();
  });
  bindPullButtons();
  restorePullState();
  restoreInstallState();
}

function fmtSize(n) {
  const units = ['B', 'KB', 'MB', 'GB'];
  let v = Number(n) || 0;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(1)} ${units[i]}`;
}

function bindPullButtons() {
  document.querySelectorAll('[data-pull]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const model = btn.dataset.pull;
      const res = await api('/api/ai/pull', { model });
      if (!res.ok) return toast(res.error || '启动下载失败');
      toast(`开始下载 ${model}…`);
      pollPull();
    });
  });
}

function pollPull() {
  clearInterval(pullTimer);
  const tick = async () => {
    let p = {};
    try {
      p = (await api('/api/ai/pull', {})).progress || {};
    } catch { return; }
    if (p.state === 'running') {
      setProgress(true, p.percent || 0,
        `下载中 ${p.percent || 0}%｜${fmtSize(p.completed)} / ${fmtSize(p.total)}｜${p.status || ''}`);
      return;
    }
    clearInterval(pullTimer);
    pullTimer = null;
    if (p.state === 'done') {
      setProgress(true, 100, `✔ ${p.status || '下载完成'}`);
      toast('✔ 模型下载完成，正在切换…');
      const st = await api('/api/ai/local', { model: p.model });
      if (st.ok) {
        renderAiSettings(st.status);
        showVerify(st.verify);
      }
      setTimeout(refreshLocalModel, 500);
    } else if (p.state === 'error') {
      setProgress(true, 0, `✘ 下载失败：${p.error}`);
    }
  };
  tick();
  pullTimer = setInterval(tick, 900);
}

async function restorePullState() {
  try {
    const p = (await api('/api/ai/pull', {})).progress || {};
    if (p.state === 'running') { setProgress(true, p.percent || 0, `下载中 ${p.percent || 0}%`); pollPull(); }
    else if (p.state === 'done') setProgress(true, 100, `✔ ${p.status || '已完成'}`);
    else if (p.state === 'error') setProgress(true, 0, `✘ ${p.error}`);
  } catch { /* 忽略 */ }
}

function pollInstall() {
  clearInterval(pullTimer);
  const tick = async () => {
    let p = {};
    try {
      p = (await api('/api/ai/installer', {})).progress || {};
    } catch { return; }
    if (p.state === 'running') {
      const src = p.source ? `［${p.source}］` : '';
      setProgress(true, p.percent || 0,
        `安装包下载中 ${src} ${p.percent || 0}%｜${fmtSize(p.received)} / ${fmtSize(p.total)}`);
      return;
    }
    clearInterval(pullTimer);
    pullTimer = null;
    if (p.state === 'done') {
      setProgress(true, 100, `✔ 已下载到：${p.path} —— 双击安装后回来点「重新检测」`);
      toast('✔ 安装包下载完成，请到「下载」文件夹双击安装');
    } else if (p.state === 'error') {
      setProgress(true, 0, `✘ ${p.error}`);
    }
  };
  tick();
  pullTimer = setInterval(tick, 900);
}

async function startInstaller(customUrl = '') {
  const res = await api('/api/ai/installer', customUrl ? { url: customUrl } : {});
  if (!res.ok) return toast(res.error || '启动下载失败');
  toast(customUrl ? '开始按你填的地址下载…' : '开始下载 Ollama 安装包（约 1.57 GB，自动挑可用源）…');
  pollInstall();
}

async function restoreInstallState() {
  try {
    const p = (await api('/api/ai/installer', {})).progress || {};
    if (p.state === 'running') pollInstall();
    else if (p.state === 'done') setProgress(true, 100, `✔ 已下载到：${p.path}`);
    else if (p.state === 'error') setProgress(true, 0, `✘ ${p.error}`);
  } catch { /* 忽略 */ }
}

$('#akLocalRefresh')?.addEventListener('click', refreshLocalModel);

document.addEventListener('click', async (ev) => {
  const copy = ev.target.closest('[data-copy]');
  if (!copy) return;
  ev.preventDefault();
  await copyText(copy.dataset.copy);
});

$('#aiKeyBtn').addEventListener('click', () => {
  const box = $('#aiKeys');
  if (box.hidden) openAiSettings();
  else box.hidden = true;
  $('#aiKeyBtn').classList.toggle('on', !box.hidden);
});
$('#aiKeysClose').addEventListener('click', () => {
  $('#aiKeys').hidden = true;
  updateKeyButton();
});

function showVerify(res) {
  const box = $('#akVerify');
  if (!box) return;
  if (!res) { box.hidden = true; return; }
  box.hidden = false;
  box.className = `ak-verify ${res.ok ? 'ok' : 'bad'}`;
  box.innerHTML = res.ok
    ? `✔ ${esc(res.message)}${res.model ? `（模型 ${esc(res.model)}）` : ''}`
    : `✘ 验证失败：${esc(res.message)}${res.detail ? `<br><span class="ak-detail">平台原文：${esc(res.detail)}</span>` : ''}`;
}

$('#aiInput').addEventListener('keydown', (ev) => { if (ev.key === 'Enter') askAI(); });

document.addEventListener('keydown', (ev) => {
  // Ctrl/⌘ + K：命令面板（高评价软件的标配交互）
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') {
    ev.preventDefault();
    palette.isOpen ? palette.close() : palette.open();
    return;
  }
  if (palette.isOpen) {
    if (ev.key === 'ArrowDown') { ev.preventDefault(); palette.move(1); return; }
    if (ev.key === 'ArrowUp') { ev.preventDefault(); palette.move(-1); return; }
    if (ev.key === 'Enter') { ev.preventDefault(); palette.commit(); return; }
  }
  // “/” 聚焦顶部搜索框
  if (ev.key === '/' && !/^(INPUT|TEXTAREA)$/.test(document.activeElement?.tagName || '')) {
    ev.preventDefault();
    $('#search').focus();
    return;
  }
  if (ev.key === 'Escape') {
    if (palette.isOpen) { palette.close(); return; }
    $('#drawer').hidden = true;
    $('#aiPanel').hidden = true;
  }
});

/* ------------------------------------------------ 首页与视图切换 */

const SCENES = [
  ['📊', '查成绩', '成绩'],
  ['🔧', '宿舍报修', '报修'],
  ['🎫', '进校预约', '访客预约'],
  ['🏊', '场馆预约', '场馆预约'],
  ['🧾', '报销报账', '报销'],
  ['📚', '图书馆座位', '座位预约'],
  ['💳', '校园卡', '校园卡'],
  ['🚌', '班车时刻', '班车'],
  ['💰', '缴费', '缴费'],
  ['💼', '招聘就业', '招聘'],
];

function setView(view) {
  state.view = view;
  $('#home').hidden = view !== 'home';
  $('#browse').hidden = view !== 'browse';
  $('#navHome').classList.toggle('active', view === 'home');
  $('#navBrowse').classList.toggle('active', view === 'browse');
  $('#navCount').textContent = state.items.length;
  if (view === 'browse') render();
  syncHash();
}

/* ------------------------------------------------ 地址栏状态（刷新/切换不丢当前视图） */

const HASH_KEYS = ['campus', 'audience', 'purpose', 'kind', 'platform'];

function syncHash() {
  const p = new URLSearchParams();
  if (state.view !== 'home') p.set('view', state.view);
  if (state.query) p.set('q', state.query);
  for (const k of HASH_KEYS) if (state[k]) p.set(k, state[k]);
  if (state.onlyFav) p.set('fav', '1');
  const hash = p.toString();
  // replaceState：刷新能恢复，但不会把每次输入都塞进历史记录
  if (window.history?.replaceState) {
    window.history.replaceState(null, '', `${location.pathname}${location.search}${hash ? '#' + hash : ''}`);
  }
}

function applyHash() {
  let p;
  try {
    p = new URLSearchParams((location.hash || '').replace(/^#/, ''));
  } catch {
    return 'home';
  }
  state.query = p.get('q') || '';
  for (const k of HASH_KEYS) state[k] = p.get(k) || '';
  state.onlyFav = p.get('fav') === '1';
  // 明确回写搜索框：浏览器会把上次输入"复原"到框里，若不同步就会出现
  // "框里有词、列表却是全部"的错位（用户看到的刷新异常）
  const box = $('#search');
  if (box) box.value = state.query;
  return p.get('view') === 'browse' ? 'browse' : 'home';
}

function tileHtml(item) {
  const plat = item.platform || 'pc';
  return `<div class="tile plat-${plat}" data-act="detail" data-id="${item.id}"
            title="${esc(item.desc || '')}">
    <span class="tname">${item.featured ? '★ ' : ''}${esc(item.name)}</span>
    <span class="tmeta">${esc(item.platformLabel || PLATFORM_LABELS[plat] || '')}</span>
  </div>`;
}

function dimCard(title, key, order, labelOf) {
  const counts = state.facets[key] || {};
  const values = order.filter((v) => counts[v]);
  return `<div class="dim">
    <h4>${title}<span class="k">${values.length} 类</span></h4>
    <div class="chips">${values.map((v) =>
      `<span class="chip" data-g="${key}" data-v="${esc(v)}">${esc(labelOf(v))}<span class="n">${counts[v]}</span></span>`,
    ).join('')}</div>
  </div>`;
}

function renderHome() {
  const f = state.facets;
  const featured = state.items.filter((i) => i.featured).slice(0, 12);
  const pick = (ids) => ids.map((id) => state.items.find((i) => i.id === id)).filter(Boolean).slice(0, 6);
  const recent = pick(state.recent);
  const favs = pick(state.favorites);

  const kindLabelOf = (v) => state.items.find((i) => i.kind === v)?.kindLabel || v;

  $('#home').innerHTML = `
    <div class="hero">
      <img class="hero-emblem" src="assets/logo/logo-256.png" alt="厦大统一门户标志">
      <div>
        <h2>厦大统一门户</h2>
        <p>把全校散落的网站与小程序收进一处，按<b>校区 / 对象 / 用途 / 端</b>分类，
           用一句话告诉 AI 你要办什么，直接给你入口。所有条目均取自学校官网原文。</p>
        <div class="hero-stats">
          <span>${f.total || 0} 个入口</span>
          <span>电脑端 ${f.platform?.pc || 0}</span>
          <span>手机端 ${f.platform?.mobile || 0}</span>
          <span>双端 ${f.platform?.both || 0}</span>
          <span>访客相关 ${state.items.filter((i) => (i.audience || []).includes('访客/公众')).length}</span>
        </div>
      </div>
    </div>

    <section>
      <h3 class="sect">常用场景 <em>点一下直接搜</em></h3>
      <div class="scenes">
        ${SCENES.map(([ico, label, q]) =>
          `<button class="scene" data-scene="${esc(q)}"><span class="ico">${ico}</span>${esc(label)}</button>`).join('')}
      </div>
    </section>

    <section>
      <h3 class="sect">精选入口 <em>最常用的 ${featured.length} 个</em></h3>
      <div class="tiles">${featured.map(tileHtml).join('')}</div>
    </section>

    <section>
      <h3 class="sect">按维度浏览 <em>点标签直接筛选</em></h3>
      <div class="dims">
        ${dimCard('按用途', 'purpose', PURPOSE_ORDER, (v) => v)}
        ${dimCard('按端', 'platform', PLATFORM_ORDER, (v) => PLATFORM_LABELS[v] || v)}
        ${dimCard('按形态', 'kind', KIND_ORDER, kindLabelOf)}
      </div>
    </section>

    ${(recent.length || favs.length) ? `
    <section>
      <h3 class="sect">我的 <em>收藏与最近打开</em></h3>
      ${favs.length ? `<h4 style="margin:0 0 7px;font-size:12px;color:var(--text-dim)">★ 收藏 ${favs.length}</h4>
        <div class="tiles" style="margin-bottom:12px">${favs.map(tileHtml).join('')}</div>` : ''}
      ${recent.length ? `<h4 style="margin:0 0 7px;font-size:12px;color:var(--text-dim)">🕘 最近打开</h4>
        <div class="tiles">${recent.map(tileHtml).join('')}</div>` : ''}
    </section>` : ''}

    <div class="home-foot">
      <button id="browseAll" class="btn primary">浏览全部 ${f.total || 0} 个入口 →</button>
      <span class="hint">或按 <kbd>Ctrl K</kbd> 直接搜</span>
    </div>

    ${mobileBandHtml()}`;
}

/* 首页底部的"手机端网址"。只在桌面版显示：
   ——手机上本来就在用这个网址，再显示一遍是废话；
   ——静态托管版（公网/手机）没有后端，拿不到这个地址，也不显示。 */
function mobileBandHtml() {
  if (!BACKEND || !state.mobileSite || isHandheld()) return '';
  return `
    <div class="mobilesite">
      <span class="ms-ico">📱</span>
      <div class="ms-main">
        <b>手机上也能用：同一份目录，手机端网址是</b>
        <code class="ms-url">${esc(state.mobileSite)}</code>
        <span class="ms-why">
          手机浏览器打开这个网址即可（内容与电脑端一致，都是同一份数据）。
          在手机浏览器的菜单里选「添加到主屏幕」，图标点开就是全屏、没有地址栏，
          和 App 一样；装过之后断网也能翻已经看过的入口。
        </span>
      </div>
      <div class="ms-actions">
        <button class="btn sm" data-act="mobilecopy">复制网址</button>
        <button class="btn sm" data-act="mobileopen">在浏览器打开</button>
      </div>
    </div>`;
}



/* ------------------------------------------------ 主题切换 */

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  try { localStorage.setItem('xmuhub-theme', theme); } catch (err) { /* 隐私模式 */ }
  const btn = $('#themeBtn');
  if (btn) {
    btn.textContent = theme === 'dark' ? '☀' : '◐';
    btn.title = theme === 'dark' ? '切换到浅色主题' : '切换到深色主题';
  }
}

function currentTheme() {
  return document.documentElement.getAttribute('data-theme') || 'light';
}

$('#themeBtn').addEventListener('click', () => {
  applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
});

/* ------------------------------------------------ 命令面板（Ctrl K） */

const palette = {
  rows: [],
  active: 0,

  open() {
    const panel = $('#palette');
    if (!panel.hidden) return;
    panel.hidden = false;
    const input = $('#paletteInput');
    input.value = '';
    this.refresh('');
    input.focus();
  },

  close() {
    $('#palette').hidden = true;
  },

  get isOpen() {
    return !$('#palette').hidden;
  },

  refresh(query) {
    const terms = expandTerms(query, tokenize(query));
    let rows;
    if (terms.length) {
      rows = state.items
        .map((it) => ({ it, s: scoreItem(it, terms) }))
        .filter((r) => r.s > 0)
        .sort((a, b) => b.s - a.s || (b.it.hot ? 1 : 0) - (a.it.hot ? 1 : 0))
        .map((r) => r.it);
    } else {
      rows = state.items.filter((it) => it.featured);   // 没输入关键词时列"精选"那 7 个
    }
    this.rows = rows.slice(0, 60);
    this.active = 0;
    this.render();
  },

  render() {
    const list = $('#paletteList');
    if (!this.rows.length) {
      list.innerHTML = '<div class="palette-empty">没有匹配的入口，换个说法试试</div>';
      $('#paletteCount').textContent = '';
      return;
    }
    list.innerHTML = this.rows.map((it, i) => `
      <div class="palette-row ${i === this.active ? 'active' : ''}" data-palette-id="${it.id}">
        <span class="pdot plat-${it.platform || 'pc'}"></span>
        <span class="pname">${esc(it.name)}</span>
        <span class="pmeta">${esc(it.platformLabel || '')} · ${esc(it.kindLabel)}</span>
      </div>`).join('');
    $('#paletteCount').textContent = `${this.rows.length} 条结果`;
    const activeEl = list.querySelector('.palette-row.active');
    // 某些嵌入环境（旧 WebView / 测试环境）没有 scrollIntoView，做一次能力检测
    if (activeEl && typeof activeEl.scrollIntoView === 'function') {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  },

  move(step) {
    if (!this.rows.length) return;
    this.active = (this.active + step + this.rows.length) % this.rows.length;
    this.render();
  },

  commit() {
    const item = this.rows[this.active];
    if (!item) return;
    const typed = $('#paletteInput').value.trim();
    if (typed.length >= 2) recordSearch(typed);   // ⌘K 里敲过的词也记进搜索记录
    this.close();
    openItem(item);
  },
};

$('#paletteInput').addEventListener('input', (ev) => palette.refresh(ev.target.value.trim()));

$('#paletteList').addEventListener('click', (ev) => {
  const row = ev.target.closest('[data-palette-id]');
  if (!row) return;
  const item = state.items.find((i) => i.id === row.dataset.paletteId);
  palette.close();
  if (item) openDrawer(item);
});

document.addEventListener('click', (ev) => {
  if (ev.target.closest('[data-palette-close]')) palette.close();
});

/* ------------------------------------------------ 手机端：左侧栏抽屉 */

function setSidebar(open) {
  const bar = $('#sidebar');
  const back = $('#sideBackdrop');
  const toggle = $('#sideToggle');
  if (!bar || !back) return;
  bar.classList.toggle('open', open);
  back.hidden = !open;
  toggle?.setAttribute('aria-expanded', String(open));
  if (open) {
    // 点过就不闪了：这只是"第一次别错过这个入口"的提示
    toggle?.classList.remove('pulse');
    try { localStorage.setItem('xmuhub-side-hint', '1'); } catch { /* 隐私模式忽略 */ }
  }
}

/** 左上角"筛选"按钮上的绿点：有筛选生效时亮起来 */
function refreshSideDot() {
  const dot = $('#sideDot');
  if (!dot) return;
  const active = Boolean(state.purpose || state.kind || state.platform || state.onlyFav);
  dot.hidden = !active;
}

/** 第一次在手机上打开时，让"筛选"按钮呼吸几下（只提示一次） */
function hintSidebarOnce() {
  const toggle = $('#sideToggle');
  if (!toggle || !isHandheld()) return;
  let seen = false;
  try { seen = localStorage.getItem('xmuhub-side-hint') === '1'; } catch { /* 忽略 */ }
  if (!seen) toggle.classList.add('pulse');
}

$('#sideToggle')?.addEventListener('click', () => setSidebar(!$('#sidebar').classList.contains('open')));
$('#sideBackdrop')?.addEventListener('click', () => setSidebar(false));
$('#sideClose')?.addEventListener('click', () => setSidebar(false));
// 抽屉里点完一项就收起来，别挡着结果（只在窄屏生效：宽屏本来就没有抽屉）
document.addEventListener('click', (ev) => {
  if (window.innerWidth > 820) return;
  if (ev.target.closest('#navHome, #navBrowse, #resetBtn, .filterblock .chip')) setSidebar(false);
});
window.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') setSidebar(false);
});

/* ------------------------------------------------ 装到手机主屏（PWA 安装引导）
   三种情况分别给不同的话，别让用户自己猜：
     · 安卓 Chrome/Edge：浏览器给了安装事件 → 直接给一个「一键添加」按钮
     · iOS Safari：没有安装事件，只能手动「分享 → 添加到主屏幕」→ 给分步图示
     · 微信内置浏览器：根本装不了，先教「右上角 ⋯ → 在浏览器中打开」
   已经装在主屏（standalone）时，按钮直接不出现。 */

let deferredInstall = null;

// 浏览器菜单那条路永远有效（不受"只能调用一次"限制），所以到处都要把这条路指出来
const MENU_HINT = '手机的浏览器菜单 <b>⋮</b> →「<b>安装应用</b>」或「<b>添加到主屏幕</b>」——'
  + '这个入口比网页里的一键添加更稳，多试几次也不会失效。';

function isStandalone() {
  return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)
    || window.navigator.standalone === true;
}

function isWeChat() {
  return /MicroMessenger/i.test(window.navigator.userAgent || '');
}

function isIOS() {
  const ua = window.navigator.userAgent || '';
  return /iPad|iPhone|iPod/.test(ua)
    || (/Macintosh/.test(ua) && 'ontouchend' in document);   // iPadOS 13+ 伪装成 Mac
}

/** 手机/平板：按视口宽度判断，跟着窗口大小变（桌面版窗口缩窄也算） */
function isHandheld() {
  return window.matchMedia ? window.matchMedia('(max-width: 820px)').matches : false;
}

/** 判断当前是在哪个"壳"里打开的——这一层决定了能不能装到主屏 */
function browserEnv() {
  const ua = window.navigator.userAgent || '';
  const ios = isIOS();
  const wechat = /MicroMessenger/i.test(ua);
  const qq = /\bQQ\/[\d.]+/i.test(ua) || /QQBrowser/i.test(ua);
  const weibo = /Weibo/i.test(ua);
  const dingtalk = /DingTalk/i.test(ua);
  const alipay = /AlipayClient/i.test(ua);
  const webview = wechat || weibo || dingtalk || alipay || /\bwv\b/.test(ua)
    || (/Android/i.test(ua) && /Version\/[\d.]+/i.test(ua) && !/Chrome/i.test(ua));
  // 国产第三方浏览器：UA 里通常也带着 Chrome/xxx，所以要按自家标识认
  const thirdParty = /UCBrowser|Quark|baidubrowser|BIDUBrowser|SogouMobileBrowser|2345Explorer|LBBROWSER|Maxthon|MQQBrowser/i.test(ua);
  const iosBrowser = /CriOS/i.test(ua) ? 'Chrome' : /FxiOS/i.test(ua) ? 'Firefox'
    : /EdgiOS/i.test(ua) ? 'Edge' : 'Safari';
  const androidBrowser = /EdgA/i.test(ua) ? 'Edge'
    : (thirdParty || qq) ? '其它'
    : /Chrome\/\d/i.test(ua) ? 'Chrome' : '其它';
  return { ua, ios, wechat, qq, weibo, dingtalk, alipay, webview, thirdParty, iosBrowser, androidBrowser };
}

/** 给出"到底能不能装、卡在哪一步"的结论。
 *  kind 决定要不要继续做服务端自检：
 *    standalone 已装好 / shell 这个壳里根本装不了 / ios-manual iOS 手动加 /
 *    prompt 浏览器可以一键装 / server 该装的都齐了但浏览器没给入口 → 这才需要自检 */
function installVerdict() {
  const env = browserEnv();
  if (isStandalone()) {
    return { kind: 'standalone', ok: true, title: '已经装好了', steps: ['你现在就是从主屏图标打开的，不用再装一次。'] };
  }
  if (env.wechat) {
    return {
      kind: 'shell', ok: false, title: '在微信里装不了（这是微信的限制）',
      steps: ['点右上角 <b>⋯</b>（三个点）',
              '选 <b>在浏览器打开</b>',
              '到了浏览器里，再点一次「装到主屏」——那时才有用'],
      hint: '微信内置浏览器不提供"添加到主屏幕"，任何网站都一样，不是我们这个站点的问题。',
    };
  }
  if (env.weibo || env.dingtalk || env.alipay || env.qq || env.webview) {
    return {
      kind: 'shell', ok: false, title: '这个 App 的内置浏览器装不了',
      steps: ['点右上角菜单里的 <b>在浏览器打开</b>（或「用系统浏览器打开」）',
              '到了系统浏览器里，再点一次「装到主屏」'],
      hint: 'App 内置浏览器都不支持把网页装到主屏，换成 Chrome / Edge / Safari 才行。',
    };
  }
  if (env.ios && env.iosBrowser !== 'Safari') {
    return {
      kind: 'shell', ok: false, title: `iOS 上只有 Safari 能装到主屏（你现在用的是 ${env.iosBrowser}）`,
      steps: ['点下面的「复制本页链接」',
              '打开 <b>Safari</b>，把链接粘到地址栏',
              '点底部 <b>分享</b> <span class="k">□↑</span> → <b>添加到主屏幕</b> → 添加'],
      hint: 'iOS 的 Chrome / Edge / Firefox 都没有"添加到主屏幕"这个入口。',
    };
  }
  if (env.ios) {
    return {
      kind: 'ios-manual', ok: true, title: 'iOS 上要手动加（不会有自动弹窗）',
      steps: ['点底部中间的 <b>分享</b> 按钮 <span class="k">□↑</span>',
              '往下滑，选 <b>添加到主屏幕</b>',
              '右上角点 <b>添加</b>——主屏上就多了一个图标'],
      hint: '一定要是 Safari。如果分享菜单里没有「添加到主屏幕」，说明你用的不是 Safari。',
    };
  }
  if (deferredInstall) {
    return {
      kind: 'prompt', ok: true, title: '可以装，点下面的一键添加',
      steps: ['主屏上会出现图标，点它直接全屏打开（和 App 一样，没有地址栏）',
              '装好后断网也能翻目录：外壳和目录数据都缓存在手机里了',
              `⚠️ 如果点了一键添加<b>没弹出确认框</b>：${MENU_HINT}`],
    };
  }
  if (/Android/i.test(env.ua) && env.androidBrowser === '其它') {
    return {
      kind: 'shell', ok: false, title: '这个浏览器可能不支持安装',
      steps: ['点下面的「复制本页链接」',
              '用 <b>Chrome</b> 或 <b>Edge</b> 打开这个链接',
              '菜单里选 <b>安装应用 / 添加到主屏幕</b>'],
      hint: '部分国产浏览器（UC、QQ、百度等）不实现 PWA 安装。',
    };
  }
  return {
    kind: 'server', ok: false, title: '浏览器还没给出安装入口',
    steps: ['点右上角 <b>⋮</b> 菜单，看有没有 <b>安装应用 / 添加到主屏幕</b>',
            '没有的话看下面的自检结果——那是服务端配置的问题'],
  };
}

/** 认出用户手上这个浏览器叫什么、菜单大概在哪——"菜单在哪里"是最高频的问题 */
function browserName() {
  const env = browserEnv();
  const ua = env.ua;
  if (env.wechat) return { name: '微信', menu: '微信<b>没有</b>浏览器菜单：点右上角 <b>⋯</b> →「在浏览器打开」' };
  if (env.dingtalk) return { name: '钉钉', menu: '点右上角 <b>⋯</b> →「在浏览器打开」' };
  if (env.alipay) return { name: '支付宝', menu: '点右上角 <b>⋯</b> →「在浏览器打开」' };
  if (env.weibo) return { name: '微博', menu: '点右上角 <b>⋯</b> →「在浏览器打开」' };
  if (env.ios) {
    const n = env.iosBrowser === 'Safari' ? 'Safari' : env.iosBrowser + '（iOS 版）';
    return { name: n, menu: 'iOS 没有"菜单"，安装入口在底部中间的<b>分享</b>按钮 <span class="k">□↑</span>' };
  }
  if (/SamsungBrowser/i.test(ua)) return { name: '三星浏览器', menu: '菜单在<b>右下角 ☰</b>' };
  if (/EdgA|Edg\//i.test(ua)) return { name: 'Edge', menu: '菜单在<b>底部中间 ⋯</b>（旧版在右上角）' };
  if (/Firefox|FxiOS/i.test(ua)) return { name: 'Firefox', menu: '菜单在<b>右上角 ⋮</b>' };
  if (/UCBrowser/i.test(ua)) return { name: 'UC 浏览器', menu: '菜单在<b>底部中间 ≡</b>' };
  if (/MQQBrowser|QQBrowser/i.test(ua)) return { name: 'QQ 浏览器', menu: '菜单在<b>底部中间 ≡</b>' };
  if (/HuaweiBrowser|HBPC|Huawei/i.test(ua)) return { name: '华为浏览器', menu: '菜单在<b>右下角 ≡</b>' };
  if (/MiuiBrowser|XiaoMi/i.test(ua)) return { name: '小米浏览器', menu: '菜单在<b>底部中间 ≡</b>' };
  if (/baidubrowser|BIDUBrowser/i.test(ua)) return { name: '百度浏览器', menu: '菜单在<b>底部中间 ≡</b>' };
  if (/VivoBrowser|HeyTapBrowser|OPPO/i.test(ua)) return { name: '手机自带浏览器', menu: '菜单一般在<b>底部中间或右下角 ≡</b>' };
  if (/Chrome\/\d/i.test(ua)) return { name: 'Chrome', menu: '菜单在<b>右上角 ⋮</b>（三个竖点）' };
  return { name: '这个浏览器', menu: '菜单一般是<b>右上角的 ⋮</b> 或<b>底部中间的 ≡</b>' };
}

function installStepsHtml() {
  const v = installVerdict();
  const b = browserName();
  const head = `<p class="sheet-verdict ${v.ok ? 'ok' : 'no'}">${v.ok ? '✔' : '✘'} ${v.title}</p>`;
  const who = `<p class="sheet-note">你现在用的是：<b>${b.name}</b>。${b.menu}</p>`;
  const steps = `<ol class="steps">${v.steps.map((s) => `<li>${s}</li>`).join('')}</ol>`;
  const hint = v.hint ? `<p class="sheet-note">${v.hint}</p>` : '';
  // 只有"服务端可能配错"这一种才需要往下自检，其余情况查了也是噪音
  const why = v.kind === 'server' ? '<p class="sheet-note" id="installWhy">正在自检服务端配置…</p>' : '';
  return head + who + steps + hint + why;
}

/** 浏览器不给安装入口时，自己查一遍原因并写清楚——省得用户只能"装不上"三个字 */
async function diagnoseInstall() {
  const box = $('#installWhy');
  if (!box) return;
  const lines = [];
  try {
    if (location.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(location.hostname)) {
      lines.push('✘ 当前不是 https —— 浏览器不允许在 http 页面上安装');
    } else {
      lines.push('✔ 是 https');
    }
    if ('serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.getRegistration();
      lines.push(reg ? '✔ Service Worker 已注册（安装条件之一）' : '✘ Service Worker 没注册成功（安装条件之一）');
    } else {
      lines.push('✘ 这个浏览器不支持 Service Worker');
    }
    const link = document.querySelector('link[rel="manifest"]');
    if (!link) {
      lines.push('✘ 页面里没有 manifest 链接');
    } else {
      const res = await fetch(link.getAttribute('href'), { cache: 'no-store' });
      const ctype = (res.headers.get('content-type') || '').split(';')[0].trim();
      lines.push(res.ok ? `✔ manifest 能取到（${ctype || '无类型'}）` : `✘ manifest 取不到（HTTP ${res.status}）`);
      if (res.ok && !/json/i.test(ctype)) {
        lines.push(`✘ manifest 的类型是 ${ctype}，浏览器只认 JSON 类型 —— 托管平台没配对 MIME`);
      }
      if (res.ok) {
        const m = await res.json().catch(() => null);
        const sizes = (m && m.icons ? m.icons : []).map((i) => i.sizes);
        if (!sizes.includes('192x192') || !sizes.includes('512x512')) {
          lines.push(`✘ manifest 里缺 192 或 512 的图标（现在有 ${sizes.join('、') || '无'}）`);
        }
      }
    }
  } catch (err) {
    lines.push('自检失败：' + (err && err.message));
  }
  box.innerHTML = lines.join('<br>') +
    '<br><span style="opacity:.75">上面有 ✘ 的，把这一屏截图发我就能定位。</span>';
}

function refreshInstallUi() {
  const btn = $('#installBtn');
  if (!btn) return;
  // 已经装在主屏了就不再提示；桌面版（127.0.0.1）也不提示
  const desktop = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
  btn.hidden = isStandalone() || desktop;
}

function openInstallSheet() {
  const body = $('#installBody');
  if (body) body.innerHTML = installStepsHtml();
  const go = $('#installGo');
  if (go) go.hidden = !deferredInstall;
  $('#installSheet').hidden = false;
  // 只有"该配的都配了、浏览器却没给入口"才去自检服务端；壳的限制查了也没用
  if (installVerdict().kind === 'server') diagnoseInstall();
}

/** 复制当前网址：给"用 Safari / Chrome 打开"这条路用 */
async function copyPageLink() {
  const url = location.href.split('#')[0];     // 去掉筛选参数，给别人打开更干净
  await writeClipboard(url);
  toast(`已复制本页链接：${url}`);
}

/** 打开首页那条手机端网址：桌面版交给本地后端用系统浏览器打开（窗口会提到最前面） */
async function openMobileSite() {
  const url = state.mobileSite;
  if (!url) return;
  if (BACKEND) {
    const res = await api('/api/open', { url });
    toast(res.ok ? '已在系统浏览器打开手机端页面' : (res.error || '打开失败'));
    return;
  }
  window.open(url, '_blank', 'noopener');
}

function closeInstallSheet() {
  $('#installSheet').hidden = true;
}

window.addEventListener('beforeinstallprompt', (ev) => {
  ev.preventDefault();          // 拦下浏览器自带的小横幅，改用我们自己的入口
  deferredInstall = ev;
  refreshInstallUi();
});

window.addEventListener('appinstalled', () => {
  deferredInstall = null;
  closeInstallSheet();
  toast('已装到主屏，以后点图标就能打开');
  refreshInstallUi();
});

$('#installBtn')?.addEventListener('click', openInstallSheet);
$('#installCopy')?.addEventListener('click', copyPageLink);

/** 在引导卡片顶部插一条即时反馈（成功/失败都要说话，不能点了没反应） */
function installFeedback(ok, text) {
  const body = $('#installBody');
  if (!body) return null;
  body.querySelectorAll('.sheet-verdict.js-live').forEach((el) => el.remove());
  const p = document.createElement('p');
  p.className = `sheet-verdict js-live ${ok ? 'ok' : 'no'}`;
  p.innerHTML = `${ok ? '✔' : '✘'} ${text}`;
  body.prepend(p);
  return p;
}

// 浏览器菜单那条路永远有效（不受"只能调用一次"限制），失败时就把这条路指出来
$('#installGo')?.addEventListener('click', async () => {
  const ev = deferredInstall;
  if (!ev) {
    installFeedback(false, '浏览器这次没给出安装许可（可能之前取消过一次）。' + MENU_HINT);
    return;
  }
  let promptError = null;
  try {
    ev.prompt();                      // 只能调用一次；第二次会抛 InvalidStateError
  } catch (err) {
    promptError = err;
  }
  if (promptError) {
    installFeedback(false, `浏览器拒绝了这次安装请求（${promptError.name}）。` + MENU_HINT);
    deferredInstall = null;
    return;
  }
  installFeedback(true, '已经向浏览器请求安装 —— 屏幕上应该会弹出「安装」确认。'
    + '如果没弹出来，' + MENU_HINT);
  $('#installGo').hidden = true;

  const choice = await (ev.userChoice || Promise.resolve(null)).catch(() => null);
  deferredInstall = null;
  if (!choice) {
    installFeedback(false, '没等到浏览器的回应（有时它只是不弹这个框）。' + MENU_HINT);
    return;
  }
  if (choice.outcome === 'accepted') {
    installFeedback(true, '已确认安装 —— 等一两秒，主屏上就会出现图标。'
      + '找不到的话看看主屏<b>最后一页</b>或应用抽屉，新装的图标有时不落在当前这页。');
  } else {
    // Chrome 说的是"这次安装没完成"，不代表用户一定点了取消，所以把常见的三种来由都写出来
    installFeedback(false,
      `Chrome 返回的结果是 <b>${esc(choice.outcome)}</b>（这次安装没有完成）。常见的三种来由：<br>`
      + '① 安装卡片被划掉、或点了取消（它是个底部弹层，容易误触）；<br>'
      + '② 之前取消过一次，Chrome 会<b>静默一段时间</b>，这期间再点它也只回"取消"；<br>'
      + '③ <b>其实已经装上了</b>——去主屏<b>最后一页</b>或应用抽屉找找「厦大入口」的图标。<br>'
      + MENU_HINT);
  }
});
document.addEventListener('click', (ev) => {
  if (ev.target.closest('[data-close="install"]')) closeInstallSheet();
});
window.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape' && !$('#installSheet').hidden) closeInstallSheet();
});
// 从浏览器菜单装完之后不会再触发 appinstalled（比如 iOS），回来时再对一次状态
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshInstallUi();
});

/* ------------------------------------------------ 首页交互 */

$('#navHome').addEventListener('click', () => setView('home'));
$('#navBrowse').addEventListener('click', () => setView('browse'));

// 首页里的场景按钮是动态渲染的，用事件委托；
// 磁贴复用通用的 .tile[data-act="detail"]，维度标签复用通用的 .chip 逻辑，
// 都不在这里重复处理，避免同一次点击被处理两遍。
$('#home').addEventListener('click', (ev) => {
  const scene = ev.target.closest('[data-scene]');
  if (scene) {
    state.query = scene.dataset.scene;
    $('#search').value = state.query;
    setView('browse');
    render();
    recordSearch(state.query);
    return;
  }
  if (ev.target.closest('#browseAll')) setView('browse');
});

// 空状态 / 断线状态下的按钮：重试连接、放宽筛选、交给 AI、清空条件、换词
document.addEventListener('click', async (ev) => {
  const act = ev.target.closest('[data-act]')?.dataset.act;
  if (act === 'reboot') {
    ev.preventDefault();
    await boot({ retry: true });
    return;
  }
  if (act === 'relax') {
    ev.preventDefault();
    Object.assign(state, { campus: '', audience: '', purpose: '', kind: '', platform: '', onlyFav: false });
    renderSidebar();
    render();
    toast('已去掉筛选条件');
    return;
  }
  if (act === 'show-all') {
    ev.preventDefault();
    Object.assign(state, { query: '', campus: '', audience: '', purpose: '', kind: '', platform: '', onlyFav: false });
    $('#search').value = '';
    renderSidebar();
    render();
    return;
  }
  if (act === 'ask-ai-empty') {
    ev.preventDefault();
    if (state.query) $('#aiInput').value = state.query;
    $('#aiPanel').hidden = false;
    $('#aiInput').focus();
    return;
  }
});
document.addEventListener('click', (ev) => {
  const sug = ev.target.closest('[data-sug]');
  if (!sug) return;
  ev.preventDefault();
  state.query = sug.dataset.sug;
  $('#search').value = state.query;
  setView('browse');
  render();
  recordSearch(state.query);
});

/* ------------------------------------------------ 启动 */

function showOffline(on) {
  const bar = $('#offlineBar');
  if (bar) bar.hidden = !on;
}

async function boot(opts = {}) {
  const loading = $('#loading');
  let data = null;
  // 后端可能还在启动（onedir 首启 / 单文件自解压都要几秒），失败就退避重试（总计约 4 秒）
  for (let attempt = 0; attempt < 4 && !data; attempt++) {
    try {
      const res = await fetch('/api/catalog');
      if (res.ok) { data = await res.json(); BACKEND = true; }
    } catch {
      /* 继续重试 */
    }
    if (!data && attempt < 3) await new Promise((r) => setTimeout(r, 250 + attempt * 700));
  }

  // 手机 / PWA：web/ 是被当静态站托管的，没有后端，目录直接读同目录的 portal.json
  if (!data) {
    try {
      const res = await fetch('portal.json', { cache: 'no-cache' });
      if (res.ok) { data = await res.json(); BACKEND = false; }
    } catch {
      /* 静态文件也没有：下面统一走"没连上" */
    }
  }

  // 手机端网址由后端给（换部署地址只改 app.py 一处）。静态版自己就是手机端，不需要显示。
  if (BACKEND) {
    try {
      const ping = await (await fetch('/api/ping')).json();
      state.mobileSite = String(ping.mobile || '').trim();
    } catch {
      /* 拿不到就不显示这一块，不影响别的功能 */
    }
  }

  if (!data || !(data.items || []).length) {
    // 不是"没有匹配的入口"，而是数据没拿到：按跑法说清原因并给出重试
    if (loading) loading.hidden = true;
    state.items = [];
    state.facets = {};
    setView('browse');
    render();
    showOffline(true);
    const title = $('#emptyBootTitle');
    const why = $('#emptyBootWhy');
    const how = $('#emptyBootHow');
    if (title && why && how && location.protocol.startsWith('http')) {
      const isLocal = ['127.0.0.1', 'localhost', '::1'].includes(location.hostname);
      if (!isLocal) {
        // 公网/静态托管：没有后端，读的是同目录的 portal.json
        title.textContent = '没有读到目录数据';
        why.textContent = '这一版是静态托管的，目录来自同目录的 portal.json；'
          + '拿不到通常是文件没传上去、或路径不对。';
        how.textContent = '解决办法：确认 portal.json 与 index.html 在同一个目录下，然后刷新本页。';
      }
    }
    if (opts.retry) toast('还是连不上，请刷新页面重试');
    return false;
  }

  state.items = data.items;
  // portal.json 里只有 items；后端在时会现算 facets，静态版就自己数
  state.facets = (data.facets && data.facets.total) ? data.facets : computeFacets(state.items);
  try {
    const user = BACKEND
      ? await fetch('/api/userdata').then((r) => r.json())
      : store.read();                    // 静态版：收藏/最近/搜索记录/身份都存浏览器里
    state.favorites = user.favorites || [];
    state.recent = user.recent || [];
    state.history = user.history || [];
    state.profile = user.profile || {};
  } catch {
    /* 用户数据拿不到不影响浏览 */
  }
  showOffline(false);
  const initialView = applyHash();   // 必须先恢复地址栏状态：render() 里的 syncHash() 会把空状态写回地址栏
  // 校区/身份不再用两排筛选，而是在首次打开时问一次（之后的默认筛选来自这里）
  const prof = state.profile || {};
  if (prof.campus || prof.audience) {
    if (!state.campus) state.campus = prof.campus || '';
    if (!state.audience) state.audience = prof.audience || '';
  }
  renderStats();
  renderSidebar();
  renderSearchHist();
  render();
  renderHome();
  setView(initialView);       // 刷新后回到刚才那一屏（首页 / 列表 + 关键词 + 筛选）
  if (loading) loading.hidden = true;

  // 首次打开（或用户从没答过）：问一次校区与身份，之后记住
  const profile = state.profile || {};
  if (!profile.asked) openOnboard(false);
  else renderProfileCard();

  applyTheme(currentTheme());   // 同步主题按钮图标
  hintSidebarOnce();            // 手机上第一次打开：让"筛选"按钮呼吸几下

  // 显示当前 AI 引擎（自填 Key 的某一家 / 本机 Ollama / 本地检索）
  if (!BACKEND) {
    // 静态版（手机）：没有后端，问答就是本地检索；「本机模型」那套按钮直接不出现
    const el = $('#aiEngine');
    if (el) {
      el.textContent = '本地检索';
      el.title = '手机/网页版：问题在浏览器里直接匹配入口，不需要联网也不需要 Key';
    }
    const keyBtn = $('#aiKeyBtn');
    if (keyBtn) keyBtn.hidden = true;
    $('#aiBody').insertAdjacentHTML('afterbegin',
      '<div class="msg bot hint-line">当前用<b>本地检索</b>回答：你的问题直接在浏览器里匹配已收录的入口，'
      + '不联网、不需要 Key，入口照样能给全。</div>');
    return true;
  }

  try {
    const ai = await fetch('/api/ai').then((r) => r.json());
    const el = $('#aiEngine');
    if (el) {
      el.textContent = ai.label || '本地检索';
      const chain = (ai.chainLabels || []).join(' → ');
      el.title = `当前引擎：${ai.label || '本地检索'}${ai.model && ai.model !== '-' ? '（模型 ' + ai.model + '）' : ''}`
        + (chain ? `\n降级链：${chain}` : '')
        + '\n点右侧按钮可配置本机模型（免费、不需要 Key）';
      el.classList.toggle('deepseek', ai.provider === 'deepseek');
    }
    state.aiStatus = ai;
    updateKeyButton(ai);
    if (ai.provider === 'local') {
      $('#aiBody').insertAdjacentHTML('afterbegin',
        '<div class="msg bot hint-line">当前用<b>本地检索</b>回答（入口照样能给全）。'
        + '想让它在候选里再挑一遍并说明理由，点右上角 <b>「配置本机 AI」</b> 下载一个本机模型即可——免费、不用 Key、断网也能用。</div>');
    }
  } catch (err) { /* 忽略：引擎信息不影响使用 */ }

  return true;
}

// 窗口被重新激活时探一下后端：旧窗口 + 已退出的实例 = 用户看到的"什么都没有"
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState !== 'visible' || !state.items.length || !BACKEND) return;
  try {
    const res = await fetch('/api/ai', { cache: 'no-store' });
    showOffline(!res.ok);
  } catch {
    showOffline(true);
  }
});

boot();

/* ------------------------------------------------ 手机上禁止缩放

   三道一起上，因为单靠一道都不够：
     ① <meta viewport> 的 maximum-scale / user-scalable —— iOS Safari 从 iOS 10 起直接忽略
     ② CSS 的 touch-action: pan-x pan-y —— 现代 Chrome/Safari 认，挡掉捏合
     ③ 这里拦 iOS 专有的 gesture 事件 + 多指 touchmove —— 只有这条在 iOS 上真的管用
   代价说清楚：关掉缩放对视力不好的用户不友好，所以移动端的基础字号都提到 15–16px 了。
   桌面版不受影响（这里只在窄屏生效，Ctrl +/- 照常可用）。 */
let zoomLocked = false;

function lockZoom() {
  if (zoomLocked || !isHandheld()) return;
  zoomLocked = true;
  const blockGesture = (ev) => ev.preventDefault();
  ['gesturestart', 'gesturechange', 'gestureend'].forEach((name) => {
    document.addEventListener(name, blockGesture, { passive: false });
  });
  document.addEventListener('touchmove', (ev) => {
    if (ev.touches && ev.touches.length > 1) ev.preventDefault();   // 双指以上一律不当缩放
  }, { passive: false });
  document.addEventListener('dblclick', blockGesture, { passive: false });
}

lockZoom();
// 窗口跨过断点时（比如桌面版窗口被拖窄）重新判定
if (window.matchMedia) {
  const mq = window.matchMedia('(max-width: 820px)');
  if (mq.addEventListener) mq.addEventListener('change', lockZoom);
}

/* ------------------------------------------------ PWA：只有"静态托管的手机版"才注册
   桌面版跑在 127.0.0.1 上，注册 Service Worker 会把界面缓存住，
   结果 exe 更新了、窗口刷新还是旧界面——所以本机地址一律不注册。 */
(function registerServiceWorker() {
  refreshInstallUi();                  // 已装到主屏 / 桌面版：不显示"装到主屏"按钮
  if (!('serviceWorker' in navigator)) return;
  const host = location.hostname;
  if (host === '127.0.0.1' || host === 'localhost' || host === '::1') return;
  if (location.protocol !== 'https:' && location.protocol !== 'http:') return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch((err) => {
      console.warn('[xmuhub] Service Worker 注册失败（不影响使用）：', err && err.message);
    });
  });
})();

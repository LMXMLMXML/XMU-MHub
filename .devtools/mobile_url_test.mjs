/**
 * 手机端网址（首页那一块）测试。
 *
 * 测三件事：
 *   1. 桌面版（有后端）：首页出现"手机 / 平板也能用"那一块，网址与 app.py 里的
 *      MOBILE_SITE 一致，说明文字讲到"添加到主屏幕 / 断网也能用"
 *   2. 复制网址 → 剪贴板拿到的是这个网址；在浏览器打开 → 走 /api/open（不是 window.open）
 *   3. 手机上（窄屏）不显示；静态托管版（没有后端）也不显示
 *
 * 网址的唯一来源是 app.py 的 MOBILE_SITE 常量，这里直接把它读出来比对，
 * 防止哪天只改了一边。结果写到 data/_mobile_url.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_mobile_url.txt`;
const portal = JSON.parse(readFileSync(`${ROOT}\\data\\portal.json`, 'utf8'));
const appPy = readFileSync(`${ROOT}\\app.py`, 'utf8');
const html = readFileSync(`${ROOT}\\web\\index.html`, 'utf8');
const appJs = readFileSync(`${ROOT}\\web\\app.js`, 'utf8');

const m = /^MOBILE_SITE = "([^"]+)"/m.exec(appPy);
if (!m) {
  console.error('app.py 里找不到 MOBILE_SITE 常量');
  process.exit(1);
}
const MOBILE = m[1];

const lines = [];
const log = (s) => { lines.push(s); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const USERDATA = { favorites: [], recent: [], history: [], profile: { campus: '', audience: '', asked: true, skipped: true } };

async function run({ backend, handheld }) {
  const dom = new JSDOM(html, {
    url: 'http://127.0.0.1:8765/index.html',
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const calls = [];
  const opened = [];
  const posts = [];

  window.matchMedia = (q) => ({
    matches: handheld ? q.includes('820px') : false,
    media: q,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
  });

  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : String(input && input.url);
    calls.push(url);
    if (init && init.body) posts.push({ url, body: JSON.parse(init.body) });
    const json = (data) => ({ ok: true, status: 200, json: async () => data });
    // portal.json 是静态托管时的数据来源，任何模式都得给；
    // 没有后端时，只有 /api/* 才像断网一样失败。
    if (url.endsWith('portal.json')) return json(portal);
    if (!backend) throw new TypeError('Failed to fetch');
    if (url.endsWith('/api/catalog')) return json(portal);
    if (url.endsWith('/api/ping')) return json({ ok: true, items: portal.items.length, mobile: MOBILE });
    if (url.endsWith('/api/userdata')) return json(USERDATA);
    if (url.endsWith('/api/open')) return json({ ok: true, opened: (init && JSON.parse(init.body).url) || '' });
    return json({ ok: true });
  };
  window.open = (u) => { opened.push(u); return {}; };
  const clip = [];
  window.navigator.clipboard = { writeText: async (t) => { clip.push(t); } };
  window.document.execCommand = () => true;

  const errors = [];
  window.addEventListener('error', (e) => errors.push(String(e.message)));
  window.eval(appJs);

  const $ = (s) => window.document.querySelector(s);
  for (let i = 0; i < 40 && !$('#stats').textContent.includes('已收录'); i++) await wait(300);
  await wait(300);
  return { window, $, calls, opened, posts, clip, errors };
}

/* ---------------- 场景 1：桌面版（宽屏 + 有后端） ---------------- */
log('== 1. 桌面版首页 ==');
log(`  app.py 里的 MOBILE_SITE：${MOBILE}`);
const A = await run({ backend: true, handheld: false });
const band = A.$('#home .mobilesite');
log(`  首页出现这一块：${Boolean(band)}（应为 true）`);
if (band) {
  const text = band.textContent.replace(/\s+/g, ' ').trim();
  log(`  区块文案：${text}`);
  log(`  含正确网址：${text.includes(MOBILE)}（应为 true）`);
  log(`  说明了"加到主屏幕"：${text.includes('添加到主屏幕')}`);
  log(`  说明了"断网也能用"：${text.includes('断网')}`);
  log(`  说明了"同一份数据"：${text.includes('同一份')}`);
  log(`  两个按钮：${[...band.querySelectorAll('button')].map((b) => b.textContent.trim()).join(' / ')}`);
}
log(`  拉过 /api/ping：${A.calls.some((u) => u.includes('/api/ping'))}（应为 true）`);
log(`  列表视图里有没有这一块：${Boolean(A.$('#browse .mobilesite'))}（应为 false，只在首页）`);

log('\n== 2. 复制 / 打开两个按钮 ==');
A.$('#home [data-act="mobilecopy"]')?.dispatchEvent(new A.window.Event('click', { bubbles: true }));
await wait(300);
log(`  剪贴板收到：${A.clip.join(' | ') || '（空）'}`);
log(`  剪贴板与配置一致：${A.clip[0] === MOBILE}（应为 true）`);
log(`  提示语：${A.$('#toast').textContent.trim()}`);
A.$('#home [data-act="mobileopen"]')?.dispatchEvent(new A.window.Event('click', { bubbles: true }));
await wait(400);
const openPost = A.posts.find((p) => p.url.includes('/api/open'));
log(`  走了 /api/open：${Boolean(openPost)}｜带上去的网址：${openPost ? openPost.body.url : '（无）'}`);
log(`  打开后的提示语：${A.$('#toast').textContent.trim()}`);
log(`  没有误用 window.open：${A.opened.length === 0}（应为 true）`);
log(`  脚本异常：${A.errors.length ? A.errors.join(' | ') : '无'}`);

/* ---------------- 场景 3：手机（窄屏，抽屉布局） ---------------- */
log('\n== 3. 手机上（窄屏）不该出现 ==');
const B = await run({ backend: true, handheld: true });
log(`  首页出现这一块：${Boolean(B.$('#home .mobilesite'))}（应为 false）`);
log(`  其余不变，仍拉到目录：${B.$('#footTotal').textContent.trim()} 条`);
log(`  脚本异常：${B.errors.length ? B.errors.join(' | ') : '无'}`);

/* ---------------- 场景 4：静态托管版（公网 / 手机 PWA） ---------------- */
log('\n== 4. 静态托管版（没有后端）==');
const C = await run({ backend: false, handheld: false });
log(`  首页出现这一块：${Boolean(C.$('#home .mobilesite'))}（应为 false，自己就是手机端）`);
log(`  请求过的地址：${[...new Set(C.calls)].join(' | ')}`);
log(`  读取 portal.json：${C.calls.some((u) => u.includes('portal.json'))}（应为 true）`);
log(`  目录条数：${C.$('#footTotal').textContent.trim()}（应为 320，说明静态回退走通了）`);
log(`  有没有去问 /api/ping：${C.calls.some((u) => u.includes('/api/ping'))}（应为 false）`);
log(`  脚本异常：${C.errors.length ? C.errors.join(' | ') : '无'}`);

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log(lines.join('\n'));
console.log('\nwritten', OUT);

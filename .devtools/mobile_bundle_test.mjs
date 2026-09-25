/**
 * 静态托管版端到端测试（jsdom 打真实 HTTP）：验证 dist-mobile 真的能当静态站跑。
 *
 * 前提：先运行 python tools/preview_mobile.py 8100
 * 与 static_mode_test.mjs 的区别：那个把 fetch 换成假的，这个走真实网络、
 * 真实 404（/api/* 在静态服务器上不存在），更接近手机上打开的情形。
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const PORT = process.argv[2] || '8100';
const BASE = `http://127.0.0.1:${PORT}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_mobile_bundle.txt';

const lines = [];
const log = (s) => lines.push(s);
const html = readFileSync('D:\\AI\\xmu_hub\\dist-mobile\\index.html', 'utf8');

const dom = new JSDOM(html, {
  url: `${BASE}/index.html`,
  runScripts: 'outside-only',
  pretendToBeVisual: true,
  resources: 'usable',
});
const { window } = dom;
await new Promise((resolve) => {
  if (window.document.readyState === 'complete') return resolve();
  const t = setTimeout(resolve, 5000);
  window.addEventListener('load', () => { clearTimeout(t); resolve(); });
});

const calls = [];
const opened = [];
window.fetch = (input, init) => {
  // 浏览器里相对地址是按文档地址解析的；Node 的 fetch 不会，所以这里自己补全
  const raw = typeof input === 'string' ? input : String(input && input.url);
  const url = new URL(raw, `${BASE}/index.html`).href;
  calls.push(url.replace(BASE, ''));
  return fetch(url, init);
};
window.open = (url) => { opened.push(url); return {}; };
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;

const errors = [];
window.addEventListener('error', (e) => errors.push(String(e.message)));
window.eval(readFileSync('D:\\AI\\xmu_hub\\dist-mobile\\app.js', 'utf8'));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];
for (let i = 0; i < 40 && !$('#stats').textContent.includes('已收录'); i++) await wait(300);

log('== 静态托管的真实网络请求 ==');
log(`  ${[...new Set(calls)].join('\n  ')}`);
log(`  试过 /api/catalog：${calls.includes('/api/catalog')}（静态服务器上不存在，应回 404 后回落）`);
log(`  读到了 /portal.json：${calls.includes('/portal.json')}`);

log('\n== 首屏 ==');
log(`  统计面板：${$('#stats').textContent.replace(/\s+/g, ' ').trim().slice(0, 70)}`);
$('#browseAll')?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
log(`  列表卡片：${$$('#list .card').length} 张`);

log('\n== 手机端布局钩子 ==');
log(`  汉堡按钮存在：${Boolean($('#sideToggle'))}｜默认隐藏（宽屏）：${window.getComputedStyle($('#sideToggle')).display}`);
log(`  抽屉遮罩存在：${Boolean($('#sideBackdrop'))}｜侧栏可加 open 类：${Boolean($('#sidebar'))}`);
$('#sideToggle').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(100);
log(`  点汉堡 → 侧栏 open=${$('#sidebar').classList.contains('open')}｜遮罩显示=${!$('#sideBackdrop').hidden}`);
$('#sideBackdrop').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(100);
log(`  点遮罩 → 侧栏 open=${$('#sidebar').classList.contains('open')}｜遮罩显示=${!$('#sideBackdrop').hidden}`);
const css = readFileSync('D:\\AI\\xmu_hub\\dist-mobile\\styles.css', 'utf8');
log(`  CSS 里有窄屏断点 @media (max-width: 820px)：${css.includes('@media (max-width: 820px)')}`);
log(`  CSS 里有单列卡片规则：${css.includes('.grid { grid-template-columns: 1fr;')}`);
log(`  CSS 里有"侧栏变身抽屉"规则：${css.includes('.sidebar.open')}`);
// 手机能滑动的前提：窄屏里必须把 html/body 的 overflow:hidden 解开（桌面版是"内部两栏各自滚"）
const mobileBlock = css.slice(css.indexOf('@media (max-width: 820px)'));
const bodyRule = mobileBlock.slice(mobileBlock.indexOf('html, body'), mobileBlock.indexOf('html, body') + 200);
log(`  窄屏里 html/body 恢复滚动：${/overflow:\s*visible/.test(bodyRule)}`);
log(`  窄屏里 html/body 高度自适应：${/height:\s*auto/.test(bodyRule)}`);

log('\n== 搜索 / 打开 / 收藏 ==');
const box = $('#search');
box.value = '成绩';
box.dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(300);
log(`  搜「成绩」→ ${$$('#list .card').length} 张`);
const openBtn = $$('#list .card [data-act="open"]')[0];
openBtn?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
log(`  window.open：${opened[0] || '（没有）'}`);
log(`  调过 /api/open：${calls.some((u) => u.includes('/api/open'))}（应为 false）`);
const favBtn = $$('#list .card [data-act="fav"]')[0];
favBtn?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
log(`  localStorage：${window.localStorage.getItem('xmuhub')}`);

log('\n== PWA 资源 ==');
for (const path of ['/manifest.json', '/sw.js', '/portal.json']) {
  const res = await fetch(BASE + path);
  log(`  ${path} → HTTP ${res.status}｜${res.headers.get('content-type')}`);
}
log(`  本机地址下不注册 Service Worker（避免桌面版界面被缓存）：${
  window.location.hostname === '127.0.0.1' ? '当前就是 127.0.0.1，符合预期' : '非本机，会注册'}`);

log('\n== 收尾 ==');
log(`  脚本异常：${errors.length ? errors.join(' | ') : '无'}`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);

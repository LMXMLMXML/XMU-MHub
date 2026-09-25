/**
 * 线上站点真机级验证（jsdom 打公网）：把**线上那份** index.html + app.js 拿下来真的执行一遍。
 *
 * deploy_check.py 只能看 HTTP 层面（文件在不在、类型对不对、和本地是否一致），
 * 这个用例进一步确认"打开真的能用"：能不能读到目录、卡片渲染几张、搜索对不对、
 * 手机动作区块出不出来、manifest 指向对不对。
 *
 * 用法：node .devtools/live_site_test.mjs https://dapper-haupia-236d40.netlify.app/
 * 结果写到 data/_live_site.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const BASE = (process.argv[2] || 'https://dapper-haupia-236d40.netlify.app/').replace(/\/?$/, '/');
const OUT = 'D:\\AI\\xmu_hub\\data\\_live_site.txt';
const lines = [];
const log = (s) => lines.push(s);

const UA =
  'Mozilla/5.0 (Linux; Android 14; PIXEL 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36';

log(`线上站点：${BASE}`);

const html = await (await fetch(`${BASE}index.html`)).text();
const appJs = await (await fetch(`${BASE}app.js`)).text();
log(`  拉到 index.html ${html.length} B｜app.js ${appJs.length} B`);
log(`  manifest 链接：${(html.match(/rel="manifest" href="([^"]+)"/) || [])[1] || '（没找到）'}`);

const dom = new JSDOM(html, { url: `${BASE}index.html`, runScripts: 'outside-only', pretendToBeVisual: true });
const { window } = dom;
Object.defineProperty(window.navigator, 'userAgent', { value: UA, configurable: true });
window.matchMedia = (q) => ({
  matches: /max-width:\s*820px/.test(q), media: q,
  addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
});

const calls = [];
const opened = [];
window.fetch = (input, init) => {
  const raw = typeof input === 'string' ? input : String(input && input.url);
  const url = new URL(raw, `${BASE}index.html`).href;
  calls.push(url.replace(BASE, ''));
  return fetch(url, init);
};
window.open = (u) => { opened.push(u); return {}; };
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;
const errors = [];
window.addEventListener('error', (e) => errors.push(String(e.message)));

window.eval(appJs);

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];

for (let i = 0; i < 60 && !$('#stats').textContent.includes('已收录'); i++) await wait(300);

log('\n== 1. 首屏 ==');
log(`  统计面板：${$('#stats').textContent.replace(/\s+/g, ' ').trim().slice(0, 72)}`);
log(`  请求过的接口/文件：${[...new Set(calls)].join(' | ')}`);
log(`  首页可见：${!$('#home').hidden}｜断线横幅：${!$('#offlineBar').hidden}（应为 false）`);

log('\n== 2. 列表与搜索 ==');
$('#browseAll')?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
log(`  卡片数：${$$('#list .card').length}`);
const box = $('#search');
box.value = '报销';
box.dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(300);
log(`  搜「报销」→ ${$$('#list .card').length} 张，前三：` +
    $$('#list .card .card-title').slice(0, 3).map((e) => e.textContent.trim()).join(' / '));
box.value = '';
box.dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(200);

log('\n== 3. 打开一个网址（走 window.open，不依赖后端）==');
const openBtn = $$('#list .card [data-act="open"]')[0];
openBtn?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
log(`  window.open：${opened[0] || '（没有）'}`);
log(`  有没有调 /api/*：${calls.some((u) => u.startsWith('/api/')) ? '有（不对）' : '没有（正确）'}`);

log('\n== 4. 手机上的"在手机上怎么进" ==');
const miniDetail = $$('#list .card').map((c) => c.querySelector('[data-act="detail"]'))
  .find((b) => b && />|小程序|公众号/.test(b.closest('.card').textContent));
if (miniDetail) {
  miniDetail.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(300);
  const body = $('#drawerBody').textContent.replace(/\s+/g, ' ');
  log(`  抽屉里出现"在手机上怎么进"：${/在手机上怎么进/.test(body)}`);
  log(`  按钮：${$$('#drawerBody .di-mobile-help button').map((b) => b.textContent.trim()).join(' / ') || '（无）'}`);
  $('[data-close]')?.dispatchEvent(new window.Event('click', { bubbles: true }));
} else {
  log('  （没找到小程序类卡片）');
}

log('\n== 5. PWA 三件套 ==');
log(`  页面里有"装到主屏"按钮：${Boolean($('#installBtn'))}｜本机地址才隐藏，线上应可见：${!$('#installBtn').hidden}`);
const mres = await fetch(`${BASE}manifest.json`);
log(`  manifest.json → HTTP ${mres.status}｜${mres.headers.get('content-type')}`);

log('\n== 6. 收尾 ==');
log(`  脚本异常：${errors.length ? errors.join(' | ') : '无'}`);

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);

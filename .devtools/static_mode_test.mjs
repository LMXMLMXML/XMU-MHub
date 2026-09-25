/**
 * 静态模式测试（jsdom）：模拟"web/ 被当静态站托管、没有后端"的情形。
 *
 * 做法：把页面里的 window.fetch 换掉——凡是 /api/* 一律像断网一样抛错，
 * 只有 portal.json 正常返回磁盘上的数据文件。然后验证：
 *   1. 目录能从 portal.json 读出来，320 张卡片正常渲染
 *   2. 搜索、筛选、收藏、搜索记录、身份都还能用（走 localStorage）
 *   3. 点条目调用 window.open，而不是 /api/open
 *   4. AI 面板给出本地检索答案，且"配置本机 AI"按钮被隐藏
 * 结果写到 data/_static_mode.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_static_mode.txt`;
const portal = JSON.parse(readFileSync(`${ROOT}\\data\\portal.json`, 'utf8'));

const html = readFileSync(`${ROOT}\\web\\index.html`, 'utf8');
const appJs = readFileSync(`${ROOT}\\web\\app.js`, 'utf8');

const lines = [];
const log = (s) => { lines.push(s); };

const dom = new JSDOM(html, {
  url: 'https://example.github.io/xmuhub/index.html',   // 静态托管的典型地址
  runScripts: 'outside-only',
  pretendToBeVisual: true,
});
const { window } = dom;

const calls = [];          // 记录被调用的 URL
const opened = [];         // 记录 window.open 打开了什么

window.fetch = async (input) => {
  const url = typeof input === 'string' ? input : String(input && input.url);
  calls.push(url);
  if (url.endsWith('/portal.json') || url === 'portal.json') {
    return { ok: true, json: async () => portal };
  }
  throw new TypeError('Failed to fetch');     // 没有后端：所有 /api/* 都连不上
};
window.open = (url) => { opened.push(url); return {}; };
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;

const errors = [];
window.addEventListener('error', (e) => errors.push(String(e.message)));
window.eval(appJs);

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];

// 等 boot 真正跑完：它内部有 4 次退避重试（约 2.9 秒）才会去读 portal.json
for (let i = 0; i < 40 && !$('#stats').textContent.includes('已收录'); i++) await wait(300);

log('== 1. 目录来源 ==');
log(`  请求过的 URL：${[...new Set(calls)].join(' | ')}`);
log(`  读到了 portal.json：${calls.includes('portal.json')}（应为 true）`);
log(`  统计面板：${$('#stats').textContent.trim().slice(0, 60)}`);

// 静态版默认停在首页：切到列表再看卡片
$('#browseAll')?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
log(`  列表卡片数：${$$('#list .card').length}（期望 ${portal.items.length}）`);
log(`  首页可见：${!$('#home').hidden}（切到列表后应为 false）｜断线横幅：${!$('#offlineBar').hidden}（应为 false）`);

log('\n== 2. 搜索与筛选（本地算） ==');
const searchBox = $('#search');
searchBox.value = '报销';
searchBox.dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(300);
log(`  搜「报销」→ ${$$('#list .card').length} 张，前三：` +
    $$('#list .card .card-title').slice(0, 3).map((e) => e.textContent.trim()).join(' / '));
// 回车才算"用了一次搜索"，会被记进搜索记录
searchBox.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
await wait(500);
searchBox.value = '';
searchBox.dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(200);

log(`  筛选项：${$$('#fPurpose .chip').map((c) => c.dataset.v).join(' / ') || '（空）'}`);
const lifeChip = $('#fPurpose .chip[data-v="生活"]');
lifeChip?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(300);
log(`  筛「生活」→ ${$$('#list .card').length} 张（桌面版同样是 80）`);
log(`  统计面板：${$('#stats').textContent.replace(/\s+/g, ' ').trim().slice(0, 70)}`);

log('\n== 3. 收藏 / 搜索记录都写进了 localStorage ==');
const firstCard = $$('#list .card').find((c) => c.querySelector('[data-act="fav"]'));
firstCard?.querySelector('[data-act="fav"]')?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(400);
const saved = JSON.parse(window.localStorage.getItem('xmuhub') || '{}');
log(`  localStorage.xmuhub.favorites = ${JSON.stringify(saved.favorites || [])}`);
log(`  localStorage.xmuhub.history = ${JSON.stringify(saved.history || [])}`);
log(`  只看收藏按钮：${$('#favBtn').textContent.trim()}`);

log('\n== 4. 点条目走 window.open ==');
const openBtn = $$('#list .card [data-act="open"]')[0];
log(`  找到"打开"按钮：${Boolean(openBtn)}`);
if (openBtn) {
  openBtn.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(400);
}
log(`  window.open 打开：${opened.join(' | ') || '（没有）'}`);
log(`  有没有去调 /api/open：${calls.some((u) => u.includes('/api/open'))}（应为 false）`);

log('\n== 5. AI 面板 ==');
$('#aiOpen')?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(300);
$('#aiInput').value = '宿舍水管漏了找谁';
$('#aiSend')?.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(1200);
const bot = $$('#aiBody .msg.bot').pop();
log(`  引擎标记：${$('#aiEngine').textContent.trim()}`);
log(`  回答：${(bot && bot.textContent.trim()) || '（空）'}`);
log(`  「配置本机 AI」按钮隐藏：${$('#aiKeyBtn').hidden}（应为 true）`);

log('\n== 6. 首次打开问身份，答案也只存在浏览器里 ==');
const onb = $('#onboard');
log(`  身份弹窗显示：${!onb.hidden}（静态版第一次打开应为 true）`);
if (!onb.hidden) {
  $('#obCampus .ob-choice[data-value="翔安校区"]')?.dispatchEvent(new window.Event('click', { bubbles: true }));
  $('#obAudience .ob-choice[data-value="研究生"]')?.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(200);
  $('#obDone').dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(600);
}
const after = JSON.parse(window.localStorage.getItem('xmuhub') || '{}');
log(`  localStorage.xmuhub.profile = ${JSON.stringify(after.profile || {})}`);
log(`  侧栏身份卡：${$('#profileBody').textContent.trim()}`);

log('\n== 7. 收尾 ==');
log(`  脚本异常：${errors.length ? errors.join(' | ') : '无'}`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);

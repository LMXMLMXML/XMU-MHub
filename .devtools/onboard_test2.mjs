/**
 * 补测：身份筛选是否真的生效、以及「修改」按钮能否改回来。
 * 用法：node onboard_test2.mjs → data/_onboard2.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_onboard2.txt';
const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const dom = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true, resources: 'usable' });
const { window } = dom;
await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 3000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
window.fetch = (i, init) => fetch(typeof i === 'string' && i.startsWith('/') ? BASE + i : i, init);
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;
window.eval(appJs);
await wait(1500);
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];
const lines = [];

// 进列表看筛选后的条数
$('#navBrowse').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(300);
lines.push('== 身份筛选是否生效 ==');
lines.push(`  侧栏身份卡：${$('#profileBody').textContent.trim()}`);
lines.push(`  列表标题：${$('#listInfo').textContent.trim()}`);
lines.push(`  卡片数：${$$('#list .card').length}（全量 316）`);

// 点「修改」应重新打开弹窗并带出当前选择
$('#profileEdit').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(300);
lines.push('\n== 点「修改」==');
lines.push(`  弹窗显示：${!$('#onboard').hidden}｜跳过按钮文案：${$('#obSkip').textContent.trim()}`);
lines.push(`  已选中：${$$('.ob-choice.active').map((b) => b.textContent).join(' + ')}`);

// 改成不限 + 不限
$('#obCampus .ob-choice[data-value=""]').dispatchEvent(new window.Event('click', { bubbles: true }));
$('#obAudience .ob-choice[data-value=""]').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(150);
$('#obDone').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(600);
lines.push(`  改后身份卡：${$('#profileBody').textContent.trim()}`);
lines.push(`  改后卡片数：${$$('#list .card').length}`);

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

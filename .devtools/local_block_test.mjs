/**
 * 检查「本机模型」区块在三种状态下到底渲染出了什么（用户反馈“下载qwen不显示”）。
 * 用法：先启动后端，再 node local_block_test.mjs → data/_local_block.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_local_block.txt';
const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');

const dom = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true, resources: 'usable' });
const { window } = dom;
await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 3000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
window.fetch = (i, init) => fetch(typeof i === 'string' && i.startsWith('/') ? BASE + i : i, init);
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;
window.eval(appJs);
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];
await new Promise((r) => setTimeout(r, 1200));

// 打开 ⚙ 设置面板，触发本机模型检测
$('#aiKeyBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await new Promise((r) => setTimeout(r, 1200));

const lines = [];
lines.push('== ⚙ 面板状态 ==');
lines.push(`  面板可见：${!$('#aiKeys').hidden}`);
lines.push(`  按钮文案：${$('#aiKeyBtn').textContent.replace(/\s+/g, '').trim()}`);

const body = $('#akLocalBody');
lines.push('\n== 本机模型区块渲染结果 ==');
lines.push(`  状态行：${$('.ak-state')?.textContent.trim() || '（无）'}`);
lines.push(`  推荐模型行数：${$$('.ak-model-row').length}`);
for (const row of $$('.ak-model-row')) {
  const btn = row.querySelector('button');
  lines.push(`    · ${row.querySelector('.mid').textContent} | ${row.querySelector('.msize').textContent} | 按钮="${btn.textContent.trim()}" ${btn.disabled ? '（置灰）' : '（可点）'}`);
}
lines.push(`  模型下拉：${$('#akLocalPick') ? '有（' + $$('#akLocalPick option').length + ' 个选项）' : '无'}`);
lines.push(`  安装包按钮：${$('#akInstall') ? '有' : '无'}｜启动服务按钮：${$('#akServe') ? '有' : '无'}｜自定义地址框：${$('#akSetupUrl') ? '有' : '无'}`);
lines.push(`  进度条元素：${$('#akProgress') ? '有' : '无'}`);

lines.push('\n== 区块文本（截断） ==');
lines.push('  ' + (body?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 400));

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

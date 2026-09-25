/**
 * 检查"首次打开询问 + 身份卡片"：首开弹窗、选择、保存、侧栏显示、二次打开不再问。
 * 用法：先启动后端（且 userdata.json 里没有 profile），再 node onboard_test.mjs → data/_onboard.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_onboard.txt';
const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');
const css = readFileSync('D:\\AI\\xmu_hub\\web\\styles.css', 'utf8');
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function openPage() {
  const dom = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true, resources: 'usable' });
  const { window } = dom;
  await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 3000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
  window.fetch = (i, init) => fetch(typeof i === 'string' && i.startsWith('/') ? BASE + i : i, init);
  window.navigator.clipboard = { writeText: async () => {} };
  window.document.execCommand = () => true;
  window.eval(appJs);
  await wait(1500);
  return window;
}
const $ = (w, s) => w.document.querySelector(s);
const $$ = (w, s) => [...w.document.querySelectorAll(s)];

const lines = [];
// 这个用例测的是"第一次打开会不会问"，所以先把自己置成没问过的状态，
// 免得跟在别的用例后面跑时因为 profile.asked=true 直接崩在取元素上。
await fetch(`${BASE}/api/profile`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ campus: '', audience: '', asked: false }),
});
let w = await openPage();

lines.push('== 首次打开 ==');
lines.push(`  询问弹窗显示：${!$(w, '#onboard').hidden}`);
lines.push(`  校区选项：${$$(w, '#obCampus .ob-choice').map((b) => b.textContent).join(' / ')}`);
lines.push(`  身份选项：${$$(w, '#obAudience .ob-choice').map((b) => b.textContent).join(' / ')}`);
lines.push(`  侧栏身份卡：${$(w, '#profileBody').textContent.trim()}`);
lines.push(`  旧的两排筛选是否还在：校区=${Boolean($(w, '#fCampus'))} 对象=${Boolean($(w, '#fAudience'))}`);

// 选：翔安校区 + 研究生
$(w, '#obCampus .ob-choice[data-value="翔安校区"]').dispatchEvent(new w.Event('click', { bubbles: true }));
$(w, '#obAudience .ob-choice[data-value="研究生"]').dispatchEvent(new w.Event('click', { bubbles: true }));
await wait(120);
lines.push(`\n== 选择后（点开始使用前）==`);
lines.push(`  选中态：${$$(w, '.ob-choice.active').map((b) => b.textContent).join(' + ')}`);
$(w, '#obDone').dispatchEvent(new w.Event('click', { bubbles: true }));
await wait(700);
lines.push(`  弹窗关闭：${$(w, '#onboard').hidden}`);
lines.push(`  侧栏身份卡：${$(w, '#profileBody').textContent.trim()}`);
lines.push(`  导航计数：${$(w, '#navCount').textContent}`);

const user = await (await fetch(`${BASE}/api/userdata`)).json();
lines.push(`  后端已保存：${JSON.stringify(user.profile)}`);

// 再开一次页面，应该不再问
w = await openPage();
lines.push('\n== 第二次打开 ==');
lines.push(`  询问弹窗显示：${!$(w, '#onboard').hidden}（应为 false）`);
lines.push(`  侧栏身份卡：${$(w, '#profileBody').textContent.trim()}`);
lines.push(`  首页维度卡是否还有"按校区/按对象"：${$(w, '#home').innerHTML.includes('按校区') || $(w, '#home').innerHTML.includes('按对象')}`);

lines.push('\n== CSS 关键类 ==');
for (const k of ['.onboard', '.ob-choice', '.profile-card', '.ob-choice.active']) {
  lines.push(`  ${k}：${css.includes(k) ? '存在' : '缺失'}`);
}

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

/**
 * 刷新 / 视图切换回归：模拟"同一个窗口刷新一次"，看列表、搜索框、筛选是否对得上。
 *
 * 用法：先启动后端，再 node refresh_test.mjs → data/_refresh_test.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_refresh_test.txt';
const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');

const lines = [];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function openPage(hash = '', { failCatalog = false } = {}) {
  const dom = new JSDOM(html, {
    url: `${BASE}/index.html${hash}`,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
    resources: 'usable',
  });
  const { window } = dom;
  await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 3000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
  window.fetch = (i, init) => {
    const url = typeof i === 'string' && i.startsWith('/') ? BASE + i : i;
    if (failCatalog && String(url).includes('/api/catalog')) return Promise.reject(new Error('ECONNREFUSED'));
    return fetch(url, init);
  };
  window.navigator.clipboard = { writeText: async () => {} };
  window.document.execCommand = () => true;
  window.eval(appJs);
  await wait(1200);
  return window;
}

const $ = (w, s) => w.document.querySelector(s);
const $$ = (w, s) => [...w.document.querySelectorAll(s)];

// A. 首次打开
let w = await openPage();
lines.push('== A. 首次打开 ==');
lines.push(`  首页可见=${!$(w, '#home').hidden}｜列表可见=${!$(w, '#browse').hidden}｜卡片 ${$$(w, '#list .card').length} 张`);
lines.push(`  地址栏 hash：${w.location.hash || '（空）'}`);

// B. 搜索 + 筛选后"刷新"（用同一个 hash 重新开一个页面对象）
$(w, '#search').value = '报修';
$(w, '#search').dispatchEvent(new w.Event('input', { bubbles: true }));
await wait(60);
$(w, '.chip[data-g="purpose"][data-v="生活"]')?.dispatchEvent(new w.Event('click', { bubbles: true }));
await wait(80);
const beforeCards = $$(w, '#list .card').length;
const hash = w.location.hash;
lines.push('\n== B. 搜索+筛选后 ==');
lines.push(`  卡片 ${beforeCards} 张｜hash=${hash}`);

w = await openPage(hash);
const boxVal = $(w, '#search').value;
const afterCards = $$(w, '#list .card').length;
const activeChips = $$(w, '.chip.active').map((c) => c.textContent.trim());
lines.push('\n== C. 用同一个 hash 重新打开（= 刷新）==');
lines.push(`  搜索框内容「${boxVal}」｜卡片 ${afterCards} 张｜命中筛选 ${activeChips.join(' / ') || '（无）'}`);
lines.push(`  刷新前后是否一致：${beforeCards === afterCards && boxVal === '报修' ? '一致 ✔' : '不一致 ✘'}`);

// D. 列表页刷新后应停在列表页
lines.push('\n== D. 列表视图刷新后 ==');
lines.push(`  列表可见=${!$(w, '#browse').hidden}｜首页可见=${!$(w, '#home').hidden}（期望 列表可见=true / 首页可见=false）`);

// E. 后端断开后刷新：应给"没有连上本地服务"而不是空列表
const dead = await openPage('', { failCatalog: true });
await wait(5200);
lines.push('\n== E. 后端断开时刷新 ==');
lines.push(`  骨架屏隐藏=${$(dead, '#loading').hidden}｜空状态显示=${!$(dead, '#empty').hidden}`);
lines.push(`  文案：${$(dead, '#empty').textContent.replace(/\s+/g, ' ').trim().slice(0, 46)}`);
lines.push(`  顶部断线提示=${!$(dead, '#offlineBar').hidden}｜重试按钮=${$$(dead, '[data-act="reboot"]').length} 个`);

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

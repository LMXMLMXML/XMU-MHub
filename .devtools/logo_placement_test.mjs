/**
 * LOGO 落地检查：首页欢迎区、空状态插图、AI 面板头部、favicon 是否都换成了自研标志。
 * 用法：先启动后端，再 node logo_placement_test.mjs → data/_logo_test.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_logo_test.txt';
const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');

const dom = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true, resources: 'usable' });
const { window } = dom;
await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 3000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
window.fetch = (i, init) => fetch(typeof i === 'string' && i.startsWith('/') ? BASE + i : i, init);
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;
window.eval(appJs);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (s) => window.document.querySelector(s);
await wait(1200);

const lines = [];
lines.push('== LOGO 落地位置 ==');
const hero = $('.hero-emblem');
lines.push(`  首页欢迎区：src=${hero?.getAttribute('src')}｜尺寸 ${Math.round(hero?.getBoundingClientRect().width || 0)}px`);
const ai = $('.ai-head img');
lines.push(`  AI 面板头部：src=${ai?.getAttribute('src')}`);
const empty = $('.empty-mark');
lines.push(`  空状态插图：src=${empty?.getAttribute('src')}`);
const icon = window.document.querySelector('link[rel="icon"]');
lines.push(`  favicon：${icon?.getAttribute('href')}｜另有 ${window.document.querySelectorAll('link[rel="icon"]').length} 个 icon link`);

// 图片能否真的取到
for (const [name, url] of [['logo-256.png', '/assets/logo/logo-256.png'], ['logo-32.png', '/assets/logo/logo-32.png'],
  ['logo-256-mark.png', '/assets/logo/logo-256-mark.png'], ['logo-portal-mono.svg', '/assets/logo/logo-portal-mono.svg'],
  ['favicon.ico', '/assets/logo/favicon.ico']]) {
  const res = await fetch(BASE + url);
  lines.push(`  ${name}: HTTP ${res.status} ${res.headers.get('content-type')}`);
}

// 置空结果，看插图是否出现
$('#search').value = '阿巴阿巴阿巴';
$('#search').dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(120);
lines.push(`\n== 空结果时的插图 ==`);
lines.push(`  空状态可见=${!$('#empty').hidden}｜插图可见=${empty ? !empty.hidden : false}｜插图 src=${empty?.getAttribute('src')}`);

// 深色主题下插图会换成单色标（CSS content 生效与否由浏览器决定，这里只验证规则存在）
const css = readFileSync('D:\\AI\\xmu_hub\\web\\styles.css', 'utf8');
lines.push(`  CSS 深色规则含单色标：${css.includes('logo-portal-mono.svg')}`);
lines.push(`  首页欢迎区深色规则已移除校徽替换：${!css.includes('dark"] .hero-emblem { content')}`);

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

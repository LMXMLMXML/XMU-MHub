/**
 * 检查 ⚙ 按钮是否"够明显"：文案、样式类、尺寸、对比度相关类，以及配 Key 后是否收敛。
 * 用法：先启动后端，再 node ai_button_test.mjs → data/_ai_button.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_ai_button.txt';
const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');
const css = readFileSync('D:\\AI\\xmu_hub\\web\\styles.css', 'utf8');

const dom = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true, resources: 'usable' });
const { window } = dom;
await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 3000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
window.fetch = (i, init) => fetch(typeof i === 'string' && i.startsWith('/') ? BASE + i : i, init);
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;
window.eval(appJs);
await new Promise((r) => setTimeout(r, 1500));

const $ = (s) => window.document.querySelector(s);
const btn = $('#aiKeyBtn');
const lines = [
    '== ⚙ 按钮状态 ==',
    `  文案：${btn?.textContent.replace(/\s+/g, '').trim()}`,
    `  class：${btn?.className}`,
    `  title：${btn?.title}`,
    `  是否高亮呼吸（未配 Key 时应有 attention）：${btn?.classList.contains('attention')}`,
    '',
    '== 点开设置面板后 ==',
];
btn?.dispatchEvent(new window.Event('click', { bubbles: true }));
await new Promise((r) => setTimeout(r, 400));
lines.push(`  面板可见：${!$('#aiKeys').hidden}`);
lines.push(`  按钮 class：${btn?.className}`);
lines.push(`  面板文案含"不填 Key 也能用"：${$('#aiKeys')?.textContent.includes('不填 Key 也能用')}`);
lines.push(`  引擎行数：${window.document.querySelectorAll('.ak-row').length}`);

lines.push('');
lines.push('== CSS 关键样式 ==');
for (const key of ['.engine-btn {', '.engine-btn.attention', 'keyPulse', '.engine-btn.on']) {
    lines.push(`  ${key}：${css.includes(key) ? '存在' : '缺失'}`);
}
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

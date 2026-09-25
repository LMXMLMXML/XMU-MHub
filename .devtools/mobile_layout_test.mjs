/**
 * 手机端首页排布验算（不需要浏览器）：
 * 从 styles.css 里把窄屏那套 auto-fill minmax 的真值抠出来，按 CSS Grid 的
 * auto-fill 算法，对常见手机宽度逐个算出"排成几列、每格多宽"。
 * 判定标准：每格不能窄到读不下（磁贴 <150px 就会被省略号截断、看着变形），
 *          也不能出现"右边缘余一大截"（说明列数没铺满）。
 * 结果写到 data/_mobile_layout.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_mobile_layout.txt`;
const css = readFileSync(`${ROOT}\\web\\styles.css`, 'utf8');

const lines = [];
const log = (s) => lines.push(s);
let pass = 0, fail = 0;
const check = (name, ok, detail = '') => {
  ok ? pass++ : fail++;
  log(`  [${ok ? 'OK ' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
};

// 窄屏那一段（820px 以内）
const start = css.indexOf('@media (max-width: 820px)');
const end = css.indexOf('@media (min-width: 600px)', start);
const mobile = css.slice(start, end > 0 ? end : undefined);

function rule(sel) {
  const i = mobile.indexOf(sel + ' {');
  if (i < 0) return '';
  return mobile.slice(i, mobile.indexOf('}', i));
}
function minmaxPx(sel) {
  const m = rule(sel).match(/minmax\((\d+)px,\s*1fr\)/);
  return m ? Number(m[1]) : null;
}
function gapOf(sel) {
  const m = rule(sel).match(/gap:\s*(\d+)px/);
  return m ? Number(m[1]) : 10;
}

log('== 1. 窄屏里不再写死两列 ==');
check('磁贴用的是 auto-fill minmax（不是 repeat(2, 1fr)）',
      /repeat\(auto-fill,\s*minmax\(\d+px,\s*1fr\)\)/.test(rule('.tiles')), rule('.tiles').trim().replace(/\s+/g, ' '));
check('常用场景同样是 auto-fill',
      /repeat\(auto-fill,\s*minmax\(\d+px,\s*1fr\)\)/.test(rule('.scenes')));
check('窄屏这一整段里没有 repeat(2, 1fr)', !/repeat\(2,\s*1fr\)/.test(mobile));
check('磁贴名字允许折两行而不是省略号',
      /-webkit-line-clamp:\s*2/.test(rule('.tile .tname')));
check('磁贴/场景都设了 min-width: 0（允许收缩，不撑破格子）',
      /min-width:\s*0/.test(rule('.tile')) && /min-width:\s*0/.test(rule('.scene')));
check('首页有最小高度，短内容也把底部按钮顶到屏幕下方',
      /min-height:\s*calc\(100dvh/.test(rule('.home')) || /min-height:\s*calc\(100vh/.test(rule('.home')));
check('欢迎区通栏（用负边距抵消 .content 的留白）', /margin:\s*0 -12px/.test(rule('.hero')));

log('\n== 2. 逐个机型算列数与格子宽度 ==');
const CONTENT_PAD = 12;          // 窄屏 .content 左右各 12px
const tileMin = minmaxPx('.tiles');
const tileGap = gapOf('.tiles');
const sceneMin = minmaxPx('.scenes');
const sceneGap = gapOf('.scenes');
log(`  磁贴：minmax(${tileMin}px, 1fr)｜gap ${tileGap}px`);
log(`  场景：minmax(${sceneMin}px, 1fr)｜gap ${sceneGap}px`);

const devices = [
  ['iPhone SE / 小屏安卓', 320],
  ['iPhone 12/13 mini', 360],
  ['iPhone 14/15', 390],
  ['iPhone Plus / 大屏安卓', 430],
  ['iPad mini 竖屏', 768],
];

for (const [name, vw] of devices) {
  const avail = vw - CONTENT_PAD * 2;
  const cols = (min) => Math.max(1, Math.floor((avail + tileGap) / (min + tileGap)));
  const width = (n, gap) => (avail - (n - 1) * gap) / n;
  const tileCols = cols(tileMin);
  const tileW = width(tileCols, tileGap);
  const sceneCols = cols(sceneMin);
  const sceneW = width(sceneCols, sceneGap);
  log(`  ${name.padEnd(20)} ${vw}px｜可用 ${avail}px → 磁贴 ${tileCols} 列 × ${tileW.toFixed(0)}px` +
      `｜场景 ${sceneCols} 列 × ${sceneW.toFixed(0)}px`);
  check(`  ${name} 磁贴宽度够读（≥150px）`, tileW >= 150, `${tileW.toFixed(0)}px`);
  check(`  ${name} 场景宽度够读（≥96px）`, sceneW >= 96, `${sceneW.toFixed(0)}px`);
  check(`  ${name} 没有整块空余（列数已铺满）`, avail - (tileCols * tileW + (tileCols - 1) * tileGap) < 1);
}

log('\n== 3. 大屏手机不把内容拉扁 ==');
const bigStart = css.indexOf('@media (min-width: 600px) and (max-width: 820px)');
const big = css.slice(bigStart, css.indexOf('\n}', bigStart) + 2);
check('600–820px 有单独断点', bigStart > 0);
check('大屏上磁贴至少 3 列（minmax ≥ 180）', /minmax\((\d+)px/.test(big) && Number(big.match(/minmax\((\d+)px/)[1]) >= 180);
check('大屏上欢迎区恢复成卡片（不再通栏）', /\.hero \{ margin: 0;/.test(big));

log(`\n结果：${pass}/${pass + fail} 通过`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);
if (fail) process.exitCode = 1;

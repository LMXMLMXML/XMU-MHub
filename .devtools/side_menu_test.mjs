/**
 * 手机端"筛选"菜单按钮测试（jsdom）：
 *   1. 窄屏显示、宽屏隐藏
 *   2. 按钮是可点的（有文字"筛选"，不只是个容易被忽略的小图标）
 *   3. 点开/关闭：侧栏 open 类、遮罩、aria-expanded 三处同步
 *   4. 抽屉头里有明确的关闭按钮（原来只能点遮罩关）
 *   5. 有筛选生效时绿点亮起，没有时熄灭
 *   6. 第一次打开会呼吸提示，点过之后不再闪（localStorage 记住）
 * 结果写到 data/_side_menu.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_side_menu.txt`;
const portal = JSON.parse(readFileSync(`${ROOT}\\data\\portal.json`, 'utf8'));
const html = readFileSync(`${ROOT}\\web\\index.html`, 'utf8');
const appJs = readFileSync(`${ROOT}\\web\\app.js`, 'utf8');
const css = readFileSync(`${ROOT}\\web\\styles.css`, 'utf8');

const lines = [];
const log = (s) => lines.push(s);
let pass = 0, fail = 0;
const check = (name, ok, detail = '') => {
  ok ? pass++ : fail++;
  log(`  [${ok ? 'OK ' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
};

// 先做静态检查：样式与结构
log('== 1. 静态检查（样式 / 结构）==');
const base = css.slice(0, css.indexOf('@media (max-width: 820px)'));
const mobile = css.slice(css.indexOf('@media (max-width: 820px)'));
check('默认（桌面）隐藏：.side-toggle { display: none }', /\.side-toggle\s*\{[^}]*display:\s*none/.test(base));
check('窄屏里显示出来', /\.side-toggle\s*\{\s*display:\s*inline-flex/.test(mobile));
check('按钮是实心品牌色（不是灰色小图标）', /\.side-toggle\s*\{[^}]*linear-gradient\(135deg,\s*var\(--brand\)/.test(base));
check('按钮高度 ≥40px（手指点得准）', /\.side-toggle\s*\{[^}]*height:\s*(\d+)px/.test(base) &&
      Number(base.match(/\.side-toggle\s*\{[^}]*height:\s*(\d+)px/)[1]) >= 40);
check('带文字标签"筛选"', /st-text[^>]*>筛选</.test(html));
check('有"有筛选生效"的绿点', /st-dot/.test(html) && /\.st-dot\s*\{/.test(base));
check('第一次打开会呼吸提示', /\.side-toggle\.pulse\s*\{[^}]*animation:\s*sidePulse/.test(base));
check('抽屉头有明确的关闭按钮',
      /id="sideClose"/.test(html) && /\.side-close\s*\{/.test(mobile),
      '.side-close 的样式在窄屏断点里');

async function open({ narrow = true, seen = false }) {
  const dom = new JSDOM(html, { url: 'https://example.xmu.edu.cn/index.html', runScripts: 'outside-only', pretendToBeVisual: true });
  const { window } = dom;
  window.matchMedia = (q) => ({
    matches: /max-width:\s*820px/.test(q) ? narrow : false,
    media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
  });
  if (seen) window.localStorage.setItem('xmuhub-side-hint', '1');
  window.fetch = async (input) => {
    const raw = typeof input === 'string' ? input : String(input && input.url);
    if (raw.includes('portal.json')) return { ok: true, json: async () => portal };
    throw new TypeError('Failed to fetch');
  };
  window.open = () => ({});
  window.navigator.clipboard = { writeText: async () => {} };
  window.document.execCommand = () => true;
  window.eval(appJs);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 30 && !window.document.querySelector('#stats').textContent.includes('已收录'); i++) await wait(200);
  return window;
}

const click = (window, sel) => window.document.querySelector(sel)?.dispatchEvent(new window.Event('click', { bubbles: true }));

log('\n== 2. 手机上点开 / 关闭 ==');
{
  const w = await open({ narrow: true });
  const $ = (s) => w.document.querySelector(s);
  log(`  按钮文字：${$('#sideToggle').textContent.replace(/\s+/g, ' ').trim()}`);
  check('按钮上有"筛选"两个字', $('#sideToggle').textContent.includes('筛选'));
  check('初始 aria-expanded=false', $('#sideToggle').getAttribute('aria-expanded') === 'false');
  check('抽屉头可见（窄屏）', w.getComputedStyle($('.side-head')).display !== 'none' || css.includes('.side-head {\n    display: flex'));

  click(w, '#sideToggle');
  await new Promise((r) => setTimeout(r, 120));
  check('点开：侧栏有 open 类', $('#sidebar').classList.contains('open'));
  check('点开：遮罩显示', !$('#sideBackdrop').hidden);
  check('点开：aria-expanded=true', $('#sideToggle').getAttribute('aria-expanded') === 'true');
  check('点开：呼吸提示已停', !$('#sideToggle').classList.contains('pulse'));

  click(w, '#sideClose');
  await new Promise((r) => setTimeout(r, 120));
  check('点抽屉里的 ✕ 能关', !$('#sidebar').classList.contains('open') && $('#sideBackdrop').hidden);

  click(w, '#sideToggle');
  await new Promise((r) => setTimeout(r, 100));
  click(w, '#sideBackdrop');
  await new Promise((r) => setTimeout(r, 100));
  check('点遮罩也能关', !$('#sidebar').classList.contains('open'));
}

log('\n== 3. 绿点：筛选项生效时亮起 ==');
{
  const w = await open({ narrow: true });
  const $ = (s) => w.document.querySelector(s);
  check('默认不亮（没有额外筛选）', $('#sideDot').hidden, `hidden=${$('#sideDot').hidden}`);
  click(w, '#fPurpose .chip[data-v="学习"]');
  await new Promise((r) => setTimeout(r, 200));
  check('选了「学习」后亮起', !$('#sideDot').hidden);
  click(w, '#fPurpose .chip[data-v="学习"]');   // 再点一次取消
  await new Promise((r) => setTimeout(r, 200));
  check('取消筛选后熄灭', $('#sideDot').hidden);
}

log('\n== 4. 呼吸提示只出现一次 ==');
{
  const fresh = await open({ narrow: true, seen: false });
  check('第一次打开会呼吸', fresh.document.querySelector('#sideToggle').classList.contains('pulse'));
  click(fresh, '#sideToggle');                 // 点一下才算"看过了"
  await new Promise((r) => setTimeout(r, 150));
  check('点了之后记进 localStorage',
        fresh.localStorage.getItem('xmuhub-side-hint') === '1',
        String(fresh.localStorage.getItem('xmuhub-side-hint')));
  check('点完立刻停止呼吸', !fresh.document.querySelector('#sideToggle').classList.contains('pulse'));
  const again = await open({ narrow: true, seen: true });
  check('第二次打开不再呼吸', !again.document.querySelector('#sideToggle').classList.contains('pulse'));
}

log('\n== 5. 桌面版不受影响 ==');
{
  const w = await open({ narrow: false });
  // jsdom 不加载外部样式表，所以这里查 CSS 文本而不是 computedStyle
  check('基础规则里是 display:none（宽屏不显示）', /\.side-toggle\s*\{\s*display:\s*none/.test(base));
  check('基础规则里抽屉头也是隐藏的', /\.side-head\s*\{\s*display:\s*none/.test(base));
  check('宽屏下不呼吸', !w.document.querySelector('#sideToggle').classList.contains('pulse'));
  check('宽屏下侧栏常驻（没有 open 类也可见）', !w.document.querySelector('#sidebar').classList.contains('open'));
}

log(`\n结果：${pass}/${pass + fail} 通过`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);
if (fail) process.exitCode = 1;

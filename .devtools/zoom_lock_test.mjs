/**
 * 移动端禁止缩放测试（jsdom）：
 *   1. viewport meta 里有 maximum-scale=1 / user-scalable=no
 *   2. 窄屏 CSS 里有 touch-action: pan-x pan-y（iOS 忽略 user-scalable，靠这条兜底）
 *   3. 所有输入框字号 ≥16px（iOS 聚焦小于 16px 的输入框会自动放大整页）
 *   4. 窄屏下真的会拦 iOS 的 gesturestart / gesturechange / gestureend
 *   5. 窄屏下双指 touchmove 被 preventDefault，单指不拦（否则就没法滚动了）
 *   6. 宽屏（桌面版）不拦任何手势——Ctrl +/- 与触控板缩放照常可用
 * 结果写到 data/_zoom_lock.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_zoom_lock.txt`;
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

log('== 1. viewport meta ==');
const meta = (html.match(/<meta name="viewport"[^>]*>/) || [''])[0];
check('有 maximum-scale=1', /maximum-scale=1/.test(meta));
check('有 user-scalable=no', /user-scalable=no/.test(meta));
check('保留了 viewport-fit=cover（刘海屏安全区）', /viewport-fit=cover/.test(meta));
log(`     ${meta}`);

log('\n== 2. 窄屏 CSS ==');
const mobile = css.slice(css.indexOf('@media (max-width: 820px)'));
const bodyRule = mobile.slice(mobile.indexOf('html, body'), mobile.indexOf('html, body') + 320);
check('html/body 上有 touch-action: pan-x pan-y', /touch-action:\s*pan-x pan-y/.test(bodyRule));
check('可点元素用 touch-action: manipulation（去双击缩放）',
      /touch-action:\s*manipulation/.test(mobile));
check('保留了 overflow: visible（还能正常滚动）', /overflow:\s*visible/.test(bodyRule));

log('\n== 3. 输入框字号 ≥16px（iOS 自动放大的元凶）==');
const inputBlock = mobile.slice(mobile.indexOf('#search,'), mobile.indexOf('#search,') + 420);
check('窄屏里把 #search 等输入框提到 16px', /font-size:\s*16px/.test(inputBlock));
for (const sel of ['#search', '#paletteInput', '.ai-input input', 'textarea']) {
  check(`  ${sel} 在 16px 规则里`, inputBlock.includes(sel));
}

async function run({ narrow, name }) {
  const dom = new JSDOM(html, { url: 'https://example.xmu.edu.cn/index.html', runScripts: 'outside-only', pretendToBeVisual: true });
  const { window } = dom;
  window.matchMedia = (q) => ({
    matches: /max-width:\s*820px/.test(q) ? narrow : false,
    media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
  });
  window.fetch = async (input) => {
    const raw = typeof input === 'string' ? input : String(input && input.url);
    if (raw.includes('portal.json')) return { ok: true, json: async () => portal };
    throw new TypeError('Failed to fetch');
  };
  window.open = () => ({});
  window.navigator.clipboard = { writeText: async () => {} };
  window.document.execCommand = () => true;

  const blocked = { gesturestart: 0, gesturechange: 0, gestureend: 0, dblclick: 0, multiTouch: 0, singleTouch: 0 };
  window.eval(appJs);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  await wait(300);

  for (const ev of ['gesturestart', 'gesturechange', 'gestureend', 'dblclick']) {
    const e = new window.Event(ev, { bubbles: true, cancelable: true });
    window.document.dispatchEvent(e);
    if (e.defaultPrevented) blocked[ev] += 1;
  }
  const twoFinger = new window.Event('touchmove', { bubbles: true, cancelable: true });
  twoFinger.touches = [{}, {}];
  window.document.dispatchEvent(twoFinger);
  if (twoFinger.defaultPrevented) blocked.multiTouch += 1;

  const oneFinger = new window.Event('touchmove', { bubbles: true, cancelable: true });
  oneFinger.touches = [{}];
  window.document.dispatchEvent(oneFinger);
  if (oneFinger.defaultPrevented) blocked.singleTouch += 1;

  log(`\n== ${name} ==`);
  log(`  gesturestart/change/end 被拦：${blocked.gesturestart}/${blocked.gesturechange}/${blocked.gestureend}`);
  log(`  dblclick 被拦：${blocked.dblclick}｜双指 touchmove 被拦：${blocked.multiTouch}｜单指被拦：${blocked.singleTouch}`);
  return blocked;
}

const phone = await run({ narrow: true, name: '4. 手机（窄屏）' });
check('iOS gesturestart 被拦', phone.gesturestart === 1);
check('iOS gesturechange 被拦', phone.gesturechange === 1);
check('iOS gestureend 被拦', phone.gestureend === 1);
check('双击缩放被拦', phone.dblclick === 1);
check('双指 touchmove 被拦', phone.multiTouch === 1);
check('单指 touchmove 不拦（否则滚不动了）', phone.singleTouch === 0);

const desktop = await run({ narrow: false, name: '5. 桌面版（宽屏）' });
check('桌面版不拦 gesture（不影响触控板/浏览器缩放）', desktop.gesturestart === 0);
check('桌面版不拦双指（触控板手势照常）', desktop.multiTouch === 0);

log(`\n结果：${pass}/${pass + fail} 通过`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);
if (fail) process.exitCode = 1;

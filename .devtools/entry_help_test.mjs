/**
 * 「无法直接跳转 → 说明间接方法」测试（jsdom）。
 * 目录里 320 条有 89 条不能直接打开：45 条没网址（小程序/公众号/App）、
 * 44 条实测打不开或标题已变。这个用例逐类验证，每一类都给出了可照做的步骤：
 *   1. 小程序（无网址）             → 复制名称（+手机端唤起微信）
 *   2. App 类（无网址，如支付宝）    → 打开对应 App / 或去应用商店
 *   3. 403/401（需登录·仅校园网）    → 先登统一身份认证 + WebVPN（带可点按钮）
 *   4. 连不上（超时）               → 校园网 / WebVPN
 *   5. 404（地址已改版）            → 从上级官网/搜名称
 *   6. 标题不符（可能改版）          → 说明并给出下一步
 *   7. 正常能打开的条目            → 不该出现这一块（避免噪音）
 * 桌面版与手机版都要有。结果写到 data/_entry_help.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_entry_help.txt`;
const portal = JSON.parse(readFileSync(`${ROOT}\\data\\portal.json`, 'utf8'));
const html = readFileSync(`${ROOT}\\web\\index.html`, 'utf8');
const appJs = readFileSync(`${ROOT}\\web\\app.js`, 'utf8');

const BASE_UA = 'Mozilla/5.0 (Linux; Android 14; PIXEL 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36';

// 目录里没有 404 / 302 / 500 这三种状态的条目，临时造三条把分支补满
const extra = [
  { id: '__t404', name: '测试·已迁移的页面', kind: 'web', kindLabel: '网站/系统', platform: 'pc',
    platformLabel: '电脑端', group: '测试', campus: ['通用'], audience: ['全体'], purpose: ['学习'],
    url: 'https://example.xmu.edu.cn/gone', linkOk: false, linkStatus: 404, desc: '测试用', keywords: [], role: 'service' },
  { id: '__t302', name: '测试·会跳转的页面', kind: 'web', kindLabel: '网站/系统', platform: 'pc',
    platformLabel: '电脑端', group: '测试', campus: ['通用'], audience: ['全体'], purpose: ['学习'],
    url: 'https://example.xmu.edu.cn/redirect', linkOk: false, linkStatus: 302, desc: '测试用', keywords: [], role: 'service' },
  { id: '__t500', name: '测试·服务器故障', kind: 'web', kindLabel: '网站/系统', platform: 'pc',
    platformLabel: '电脑端', group: '测试', campus: ['通用'], audience: ['全体'], purpose: ['学习'],
    url: 'https://example.xmu.edu.cn/boom', linkOk: false, linkStatus: 500, desc: '测试用', keywords: [], role: 'service' },
];
portal.items.push(...extra);
portal.facets = portal.facets || {};

const lines = [];
const log = (s) => lines.push(s);
let pass = 0, fail = 0;
const check = (name, ok, detail = '') => {
  ok ? pass++ : fail++;
  log(`  [${ok ? 'OK ' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`);
};

async function open({ narrow = true, ua = BASE_UA }) {
  const dom = new JSDOM(html, { url: 'https://example.xmu.edu.cn/index.html', runScripts: 'outside-only', pretendToBeVisual: true });
  const { window } = dom;
  Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
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
  window.eval(appJs);
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 30 && !window.document.querySelector('#stats').textContent.includes('已收录'); i++) await wait(200);
  window.document.querySelector('#browseAll')?.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(300);
  return window;
}

function findItem(pred, label) {
  const it = portal.items.find(pred);
  if (!it) log(`  （目录里没有符合条件的条目：${label}）`);
  return it;
}

async function inspect(window, item) {
  const doc = window.document;
  const btn = doc.querySelector(`#list .card [data-act="detail"][data-id="${item.id}"]`);
  if (!btn) return null;
  btn.dispatchEvent(new window.Event('click', { bubbles: true }));
  await new Promise((r) => setTimeout(r, 250));
  const box = doc.querySelector('#drawerBody .di-help');
  if (!box) return null;
  return {
    title: box.querySelector('h4')?.textContent.trim(),
    steps: [...box.querySelectorAll('.di-steps li')].map((li) => li.textContent.replace(/\s+/g, ' ').trim()),
    buttons: [...box.querySelectorAll('.di-actions button')].map((b) => b.textContent.trim()),
    fallback: box.querySelector('.di-fallback')?.textContent.replace(/\s+/g, ' ').trim() || '',
  };
}

const cases = [
  {
    label: '1. 小程序（无网址）',
    item: findItem((i) => i.kind === 'miniprogram' && !i.url, 'miniprogram'),
    must: ['微信'],
    wantButtons: ['复制'],                     // 手机端会多一个"打开微信"动作，见下方按端断言
    mobileButtons: ['打开微信'],
  },
  {
    label: '2. App 类（无网址）',
    item: findItem((i) => i.kind === 'app' && !i.url, 'app'),
    must: [], wantButtons: ['复制'],
  },
  {
    label: '3. 403/401（需要登录或仅校园网）',
    item: findItem((i) => i.linkOk === false && [401, 403, 400].includes(Number(i.linkStatus)), '403'),
    must: ['登录'], wantButtons: ['统一身份认证', 'WebVPN'],
  },
  {
    label: '4. 连不上（超时/无响应）',
    item: findItem((i) => i.linkOk === false && Number(i.linkStatus || 0) === 0, 'timeout'),
    must: ['校园网'], wantButtons: ['WebVPN'],
  },
  {
    label: '5. 404（地址已改版）',
    item: findItem((i) => i.id === '__t404', '404'),
    must: ['改版'], wantButtons: [],
  },
  {
    label: '5b. 302（会跳转）',
    item: findItem((i) => i.id === '__t302', '302'),
    must: ['跳'], wantButtons: [],
  },
  {
    label: '5c. 500（服务器故障）',
    item: findItem((i) => i.id === '__t500', '500'),
    must: ['故障'], wantButtons: [],
  },
  {
    label: '6. 标题不符（可能已改版）',
    item: findItem((i) => i.linkTitleMismatch, 'mismatch'),
    must: ['改版'], wantButtons: [],
  },
  {
    label: '7. 正常能打开的条目（不该出现这一块）',
    item: findItem((i) => i.url && i.linkOk !== false && !i.linkTitleMismatch && i.kind === 'web', 'ok'),
    expectEmpty: true,
  },
];

for (const narrow of [true, false]) {
  log(`\n========== ${narrow ? '手机（窄屏）' : '桌面（宽屏）'} ==========`);
  const window = await open({ narrow });
  for (const c of cases) {
    if (!c.item) continue;
    const info = await inspect(window, c.item);
    log(`\n== ${c.label} ==`);
    log(`  条目：${c.item.name}（kind=${c.item.kind}｜url=${c.item.url || '无'}｜status=${c.item.linkStatus ?? '-'}）`);
    if (c.expectEmpty) {
      log(`  这一块出现：${Boolean(info)}（期望不出现）`);
      check(`${c.label} 不打扰能正常打开的条目`, !info);
      continue;
    }
    if (!info) { check(`${c.label} 给出了间接方法`, false, '没有渲染出指引块'); continue; }
    log(`  标题：${info.title}`);
    info.steps.forEach((s, i) => log(`     ${i + 1}) ${s}`));
    log(`  按钮：${info.buttons.join(' / ')}`);
    log(`  兜底：${info.fallback}`);
    check(`${c.label} 有步骤`, info.steps.length >= 1);
    check(`${c.label} 有兜底说明`, info.fallback.includes('搜'));
    for (const kw of c.must) check(`${c.label} 文案含「${kw}」`, info.steps.join(' ').includes(kw));
    for (const kw of c.wantButtons) {
      check(`${c.label} 有「${kw}」按钮`, info.buttons.some((b) => b.includes(kw)), info.buttons.join('/'));
    }
    // 「打开微信」这类动作只在手机端出现：桌面版点了也没用，属于正确行为
    if (c.mobileButtons) {
      const has = c.mobileButtons.some((kw) => info.buttons.some((b) => b.includes(kw)));
      check(`${c.label} ${narrow ? '手机端有' : '桌面端没有'}「打开微信」动作`, narrow ? has : !has,
            info.buttons.join('/'));
    }
  }
}

log(`\n结果：${pass}/${pass + fail} 通过`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);
if (fail) process.exitCode = 1;

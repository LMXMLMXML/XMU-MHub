/**
 * 手机端"在手机上怎么进"动作测试（jsdom）：
 *   1. 窄屏 + 小程序条目（没有网址）→ 抽屉里应出现「在手机上怎么进」+「复制名称并打开微信」
 *   2. 窄屏 + 支付宝/一卡通类条目      → 应出现「打开支付宝」按钮
 *   3. 微信内置浏览器                  → 不该出现「打开支付宝」，应改成"在浏览器中打开"的引导
 *   4. 宽屏（桌面版）                  → 整块不出现
 * 结果写到 data/_mobile_actions.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_mobile_actions.txt`;
const portal = JSON.parse(readFileSync(`${ROOT}\\data\\portal.json`, 'utf8'));
const html = readFileSync(`${ROOT}\\web\\index.html`, 'utf8');
const appJs = readFileSync(`${ROOT}\\web\\app.js`, 'utf8');

const UA = {
  android: 'Mozilla/5.0 (Linux; Android 14; PIXEL 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36',
  wechat: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49 NetType/WIFI',
};

const lines = [];
const log = (s) => lines.push(s);

/** 挑一条"没有网址"的条目，按名字关键词找 */
function pick(pred) {
  return portal.items.find(pred);
}

async function scenario(name, { narrow = true, ua = UA.android, target, expect }) {
  const dom = new JSDOM(html, { url: 'https://example.xmu.edu.cn/index.html', runScripts: 'outside-only', pretendToBeVisual: true });
  const { window } = dom;
  Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
  // jsdom 的 matchMedia 只认它自己支持的查询，这里按需要返回，模拟手机/桌面两种视口
  window.matchMedia = (q) => ({
    matches: /max-width:\s*820px/.test(q) ? narrow : /standalone/.test(q),
    media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
  });
  window.fetch = async (input) => {
    const raw = typeof input === 'string' ? input : String(input && input.url);
    if (raw.includes('portal.json')) return { ok: true, json: async () => portal };
    throw new TypeError('Failed to fetch');
  };
  window.open = () => ({});
  const copied = [];
  window.navigator.clipboard = { writeText: async (t) => { copied.push(t); } };
  window.document.execCommand = () => true;
  const errors = [];
  window.addEventListener('error', (e) => errors.push(String(e.message)));
  window.eval(appJs);

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s) => window.document.querySelector(s);
  for (let i = 0; i < 30 && !$('#stats').textContent.includes('已收录'); i++) await wait(200);

  // 切到列表视图，点该条目的「详情」按钮打开抽屉
  // （app.js 里的 state 是 eval 作用域的 const，外面拿不到，只能走 DOM）
  $('#browseAll')?.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(300);
  const detail = window.document.querySelector(`#list .card [data-act="detail"][data-id="${target.id}"]`);
  if (!detail) {
    log(`\n== ${name} ==\n  ✘ 列表里找不到该条目的详情按钮，跳过`);
    return;
  }
  detail.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(250);
  const body = $('#drawerBody').textContent.replace(/\s+/g, ' ');
  const hasBlock = /在手机上怎么进/.test(body);
  const buttons = [...window.document.querySelectorAll('#drawerBody .di-mobile-help button')].map((b) => b.textContent.trim());
  const hasAppBtn = buttons.some((t) => /^打开/.test(t));

  log(`\n== ${name} ==`);
  log(`  条目：${target.name}（kind=${target.kind}｜url=${target.url || '无'}）`);
  log(`  出现"在手机上怎么进"：${hasBlock}（期望 ${expect.block}）`);
  log(`  按钮：${buttons.join(' / ') || '（无）'}`);
  log(`  含"打开某 App"按钮：${hasAppBtn}（期望 ${expect.appBtn}）`);
  if (expect.mustInclude) {
    for (const word of expect.mustInclude) log(`  文案含「${word}」：${body.includes(word)}`);
  }

  // 点一下"复制名称"类按钮，确认真的复制了名称
  const copyBtn = [...window.document.querySelectorAll('#drawerBody .di-mobile-help button')]
    .find((b) => /复制名称/.test(b.textContent));
  if (copyBtn) {
    copyBtn.dispatchEvent(new window.Event('click', { bubbles: true }));
    await wait(400);
    log(`  点了复制按钮后剪贴板：${copied.join(' / ') || '（空）'}`);
  }
  log(`  脚本异常：${errors.length ? errors.join(' | ') : '无'}`);
}

const mini = pick((i) => i.kind === 'miniprogram' && !i.url) || pick((i) => i.kind === 'wechat' && !i.url);
// 支付宝类：优先挑"校园一卡通充值"这种本身就是 App 的条目
const alipay = pick((i) => i.kind === 'app' && /一卡通|支付宝/.test(`${i.name} ${i.desc || ''}`))
  || pick((i) => /支付宝/.test(`${i.name} ${i.desc || ''} ${i.entry || ''}`));

await scenario('1. 窄屏 + 小程序条目', {
  narrow: true, target: mini,
  expect: { block: true, appBtn: false, mustInclude: ['微信搜索框', '复制名称'] },
});
if (alipay) {
  await scenario('2. 窄屏 + 支付宝类条目', {
    narrow: true, target: alipay,
    expect: { block: true, appBtn: true, mustInclude: ['打开支付宝'] },
  });
} else {
  log('\n== 2. 窄屏 + 支付宝类条目 ==\n  （目录里没有匹配条目，跳过）');
}
await scenario('3. 微信内置浏览器打开同一条目', {
  narrow: true, ua: UA.wechat, target: alipay || mini,
  expect: { block: true, appBtn: false, mustInclude: ['在浏览器中打开'] },
});
await scenario('4. 宽屏（桌面版）', {
  narrow: false, target: mini,
  expect: { block: false, appBtn: false },
});

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);

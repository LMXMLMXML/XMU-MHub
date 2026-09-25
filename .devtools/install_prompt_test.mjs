/**
 * "装到手机主屏"引导测试（jsdom）：四种情形各跑一遍，看提示对不对。
 *   1. 安卓 Chrome（浏览器给了安装事件）→ 应该出现「一键添加」按钮
 *   2. iOS Safari（没有安装事件）        → 应该给「分享 → 添加到主屏幕」分步说明
 *   3. 微信内置浏览器                    → 应该先说「右上角 ⋯ → 在浏览器中打开」
 *   4. 已经装在主屏（standalone）        → 按钮不该出现
 * 顺带验证：桌面版（127.0.0.1）不显示这个按钮。
 * 结果写到 data/_install_prompt.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const ROOT = 'D:\\AI\\xmu_hub';
const OUT = `${ROOT}\\data\\_install_prompt.txt`;
const portal = JSON.parse(readFileSync(`${ROOT}\\data\\portal.json`, 'utf8'));
const html = readFileSync(`${ROOT}\\web\\index.html`, 'utf8');
const appJs = readFileSync(`${ROOT}\\web\\app.js`, 'utf8');

const UA = {
  android: 'Mozilla/5.0 (Linux; Android 14; PIXEL 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36',
  ios: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
  wechat: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49(0x18003129) NetType/WIFI Language/zh_CN',
  wechatAndroid: 'Mozilla/5.0 (Linux; Android 14; PIXEL 8; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0 Mobile Safari/537.36 MicroMessenger/8.0.49.2600(0x2800313D) WeChat/arm64',
  iosChrome: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/122.0.6261.62 Mobile/15E148 Safari/604.1',
  ucAndroid: 'Mozilla/5.0 (Linux; U; Android 14; zh-CN; PIXEL 8 Build/UQ1A) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.58 UCBrowser/15.5.8.1225 Mobile Safari/537.36',
};

const lines = [];
const log = (s) => lines.push(s);

async function scenario(name, { url, ua, standalone = false, installEvent = false, diagnose = false, promptBehaviour = 'accept' }) {
  const dom = new JSDOM(html, { url, runScripts: 'outside-only', pretendToBeVisual: true });
  const { window } = dom;
  Object.defineProperty(window.navigator, 'userAgent', { value: ua, configurable: true });
  if (standalone) {
    window.matchMedia = (q) => ({ matches: /standalone/.test(q), media: q, addListener() {}, removeListener() {} });
  }
  window.fetch = async (input) => {
    const raw = typeof input === 'string' ? input : String(input && input.url);
    if (raw.includes('portal.json')) return { ok: true, json: async () => portal };
    if (diagnose && raw.includes('manifest.json')) {
      // 模拟"托管平台没配对 MIME"的真实故障
      return {
        ok: true, status: 200,
        headers: { get: (k) => (k.toLowerCase() === 'content-type' ? 'application/octet-stream' : null) },
        json: async () => ({ name: 'x', short_name: 'x', icons: [{ sizes: '128x128' }] }),
      };
    }
    throw new TypeError('Failed to fetch');
  };
  if (diagnose) {
    // Service Worker 没注册成功
    Object.defineProperty(window.navigator, 'serviceWorker', {
      value: { getRegistration: async () => null, register: async () => ({}) },
      configurable: true,
    });
  }
  window.open = () => ({});
  window.navigator.clipboard = { writeText: async () => {} };
  window.document.execCommand = () => true;
  const errors = [];
  window.addEventListener('error', (e) => errors.push(String(e.message)));
  window.eval(appJs);

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s) => window.document.querySelector(s);

  let prompted = 0;
  if (installEvent) {
    const ev = new window.Event('beforeinstallprompt');
    ev.prompt = () => {
      prompted += 1;
      if (promptBehaviour === 'throw') {
        const err = new Error('already called');
        err.name = 'InvalidStateError';
        throw err;
      }
    };
    // 'accept' 用户点了安装｜'dismiss' 用户取消｜'never' 浏览器根本不弹、userChoice 永不 resolve
    ev.userChoice = promptBehaviour === 'never'
      ? new Promise(() => {})
      : Promise.resolve({ outcome: promptBehaviour === 'accept' ? 'accepted' : 'dismissed' });
    window.dispatchEvent(ev);
  }
  for (let i = 0; i < 30 && !$('#stats').textContent.includes('已收录'); i++) await wait(200);

  const btn = $('#installBtn');
  log(`\n== ${name} ==`);
  log(`  按钮可见：${!btn.hidden}`);
  if (btn.hidden) { log(`  （这种情况不该弹引导）`); return; }

  btn.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(150);
  log(`  引导卡片显示：${!$('#installSheet').hidden}`);
  log(`  一键添加按钮可见：${!$('#installGo').hidden}（安卓有安装事件时才是 true）`);
  const verdict = $('#installBody').querySelector('.sheet-verdict');
  log(`  判定：${verdict ? verdict.textContent.trim() : '（没有判定行）'}`);
  const who = [...$('#installBody').querySelectorAll('.sheet-note')]
    .map((n) => n.textContent.replace(/\s+/g, ' ').trim())
    .find((t) => t.startsWith('你现在用的是'));
  log(`  认出浏览器：${who || '（没认出来）'}`);
  log(`  文案：${$('#installBody').textContent.replace(/\s+/g, ' ').trim().slice(0, 150)}`);

  if (!$('#installGo').hidden) {
    $('#installGo').dispatchEvent(new window.Event('click', { bubbles: true }));
    await wait(300);
    log(`  点了「一键添加」→ 调起系统安装提示 ${prompted} 次`);
    const feedback = $('#installBody').querySelector('.sheet-verdict.js-live');
    log(`  即时反馈：${feedback ? feedback.textContent.replace(/\s+/g, ' ').trim().slice(0, 130) : '（没有！点了没反应）'}`);
    log(`  卡片是否仍然打开（能看到反馈）：${!$('#installSheet').hidden}`);
    if (promptBehaviour !== 'never') {
      $('[data-close="install"]').dispatchEvent(new window.Event('click', { bubbles: true }));
      await wait(100);
    }
  } else {
    await wait(400);
    const why = $('#installWhy');
    if (why) log(`  自检结果：${why.textContent.replace(/\s+/g, ' ').trim().slice(0, 220)}`);
    $('[data-close="install"]').dispatchEvent(new window.Event('click', { bubbles: true }));
    await wait(100);
    log(`  点「知道了」→ 卡片已关：${$('#installSheet').hidden}`);
  }
  log(`  脚本异常：${errors.length ? errors.join(' | ') : '无'}`);
}

await scenario('1. 安卓 Chrome（浏览器给了安装事件）', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.android, installEvent: true,
});
await scenario('2. iOS Safari（没有安装事件）', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.ios,
});
await scenario('3. 微信内置浏览器', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.wechat,
});
await scenario('4. 已经装到主屏（standalone）', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.android, standalone: true, installEvent: true,
});
await scenario('5. 桌面版桌面窗口（127.0.0.1）', {
  url: 'http://127.0.0.1:8765/index.html', ua: UA.android, installEvent: true,
});
await scenario('6. 安卓但浏览器没给安装入口 → 应自动自检并指出原因', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.android, diagnose: true,
});
await scenario('7. 微信里（安卓 WebView）→ 应直接说"微信里装不了"', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.wechatAndroid,
});
await scenario('8. iOS 上用 Chrome 打开 → 应让改用 Safari', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.iosChrome,
});
await scenario('9. 安卓第三方浏览器（UC）→ 应让改用 Chrome/Edge', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.ucAndroid,
});
// 下面三种就是"点了没反应"的真实成因，必须每一种都有可见反馈
await scenario('10. 一键添加后用户点了取消 → 必须有反馈并指向浏览器菜单', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.android, installEvent: true, promptBehaviour: 'dismiss',
});
await scenario('11. 第二次点（事件已失效，prompt 抛 InvalidStateError）→ 不能静默', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.android, installEvent: true, promptBehaviour: 'throw',
});
await scenario('12. 浏览器压根不弹框（userChoice 永不返回）→ 也得马上有反馈', {
  url: 'https://example.xmu.edu.cn/index.html', ua: UA.android, installEvent: true, promptBehaviour: 'never',
});

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written', OUT);

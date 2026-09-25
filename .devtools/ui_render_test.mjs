/**
 * 前端渲染与交互测试（jsdom）：真正执行 index.html + app.js，
 * 对接运行中的后端，验证列表渲染、搜索、筛选、收藏等是否按预期工作。
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 用默认端口 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_ui_render.txt';
const lines = [];
const log = (s) => { lines.push(s); };

const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');

const dom = new JSDOM(html, {
  url: `${BASE}/index.html`,
  runScripts: 'outside-only',
  pretendToBeVisual: true,
  resources: 'usable',        // 让 jsdom 真的去加载 styles.css，才能验证样式生效
});
const { window } = dom;

// 等样式表加载完
await new Promise((resolve) => {
  if (window.document.readyState === 'complete') return resolve();
  const timer = setTimeout(resolve, 5000);
  window.addEventListener('load', () => { clearTimeout(timer); resolve(); });
});

// 用 Node 侧 fetch 代理页面里的相对请求
window.fetch = (input, init) => {
  const url = typeof input === 'string' && input.startsWith('/') ? BASE + input : input;
  return fetch(url, init);
};
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;

const errors = [];
window.addEventListener('error', (e) => errors.push(String(e.message)));

window.eval(appJs);

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function until(fn, timeout = 8000, step = 120) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (fn()) return true;
    await wait(step);
  }
  return false;
}

const $ = (sel) => window.document.querySelector(sel);
const $$ = (sel) => [...window.document.querySelectorAll(sel)];

const ok = await until(() => $$('#list .card').length > 0);

log('== 首屏渲染 ==');
log(`  脚本异常: ${errors.length ? errors.join(' | ') : '无'}`);
log(`  卡片渲染: ${ok ? '成功' : '失败'}，共 ${$$('#list .card').length} 张`);
log(`  统计面板: ${$('#stats').textContent.replace(/\s+/g, ' ').trim()}`);
log(`  校区筛选项: ${$$('#fCampus .chip').map((c) => c.dataset.v).join(' / ')}`);
log(`  用途筛选项: ${$$('#fPurpose .chip').map((c) => c.dataset.v).join(' / ')}`);
log(`  列表信息: ${$('#listInfo').textContent.trim()}`);

log('\n== 首页（默认视图）==');
log(`  首页可见=${!$('#home').hidden}｜列表默认隐藏=${$('#browse').hidden}｜`
  + `导航高亮=${$('#navHome').classList.contains('active') ? '首页' : '其它'}`);
log(`  欢迎区：${$('.hero h2')?.textContent}｜校徽=${$('.hero-emblem')?.getAttribute('src')}`);
log(`  数据徽章：${$$('.hero-stats span').map((s) => s.textContent).join(' · ')}`);
log(`  常用场景 ${$$('.scene').length} 个：${$$('.scene').slice(0, 4).map((s) => s.textContent.trim()).join(' / ')} …`);
log(`  精选磁贴 ${$$('.tile').length} 个：${$$('.tile').slice(0, 4).map((t) => t.querySelector('.tname').textContent.trim()).join(' / ')}`);
// 首页磁贴里混着"精选入口 / 我的收藏 / 最近打开"三段，这里单独把"精选"那段数清楚
{
  const heads = $$('#home h3.sect');
  const pick = heads.find((h) => h.textContent.includes('精选'));
  if (pick) {
    const box = pick.nextElementSibling;
    const names = [...(box ? box.querySelectorAll('.tname') : [])].map((n) => n.textContent.replace('★ ', '').trim());
    log(`  精选入口这一段：${pick.textContent.replace(/\s+/g, ' ').trim()} → ${names.length} 个：${names.join('、')}`);
  } else {
    log('  精选入口这一段：（没找到）');
  }
}
log(`  维度卡片 ${$$('.dim').length} 个：${$$('.dim h4').map((h) => h.textContent.replace(/\d+ 类/, '').trim()).join(' / ')}`);
log(`  底部按钮：${$('#browseAll')?.textContent.trim()}`);

// 场景按钮 → 自动进列表并搜索
$('.scene').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(80);
log(`  点击场景「${$$('.scene')[0].textContent.trim()}」→ 视图=${$('#browse').hidden ? '仍在首页（异常）' : '已进列表'}，`
  + `结果 ${$$('#list .card').length} 条，搜索框="${$('#search').value}"`);
$('#navHome').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  点「首页」导航 → 首页可见=${!$('#home').hidden}`);

// 维度标签 → 自动进列表并带筛选
$('.dim .chip').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(80);
log(`  点击首页维度标签「${$('.dim .chip').textContent.replace(/\d+$/, '')}」→ `
  + `已进列表=${!$('#browse').hidden}，${$('#listInfo').textContent.trim()}（${$$('#list .card').length} 条）`);
$('#resetBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);

function typeSearch(text) {
  const input = $('#search');
  input.value = text;
  input.dispatchEvent(new window.Event('input', { bubbles: true }));
}

log('\n== 视觉系统（配色与 LOGO）==');
const cs = (el) => window.getComputedStyle(el);
const rootStyle = cs(window.document.documentElement);
log(`  主题：data-theme=${window.document.documentElement.getAttribute('data-theme')}`);
log(`  品牌藏青 --brand=${rootStyle.getPropertyValue('--brand').trim()} `
  + `强调蓝 --accent=${rootStyle.getPropertyValue('--accent').trim()} `
  + `OH绿 --oh-green=${rootStyle.getPropertyValue('--oh-green').trim()}`);
log(`  卡片区布局：display=${cs($('#list')).display}（应为 grid）`);
log(`  统计面板数字：${$('.stat-num')?.textContent}，进度条 ${$$('.stats .bar').length} 条，`
  + `页脚 ${$('.stat-foot')?.textContent}`);
log(`  端色竖条类：${[...new Set($$('#list .card').map((c) => [...c.classList].find((x) => x.startsWith('plat-'))))].join(' / ')}`);
log(`  LOGO：校徽=${$('.brand-emblem')?.getAttribute('src')}｜院徽=${$('.brand-college')?.getAttribute('src')}`
  + `｜侧栏院徽=${$('.college-card img') ? '有' : '无'}`);
log(`  [回归] 初始 AI 面板 display=${cs($('#aiPanel')).display}（应为 none）`);

log('\n== 主题切换 ==');
$('#themeBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  点击后 data-theme=${window.document.documentElement.getAttribute('data-theme')}，`
  + `按钮图标=${$('#themeBtn').textContent}`);
const darkBg = cs(window.document.body).backgroundColor;
log(`  深色主题背景色=${darkBg}`);
$('#themeBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  再切回 data-theme=${window.document.documentElement.getAttribute('data-theme')}，`
  + `背景色=${cs(window.document.body).backgroundColor}`);

log('\n== 命令面板（Ctrl K）==');
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
await wait(80);
log(`  Ctrl+K 打开：${$('#palette').hidden ? '未打开（异常）' : '已打开'}，`
  + `默认列出精选 ${$$('#paletteList .palette-row').length} 条`);
$('#paletteInput').value = '报修';
$('#paletteInput').dispatchEvent(new window.Event('input', { bubbles: true }));
await wait(60);
const prows = $$('#paletteList .palette-row');
log(`  输入「报修」→ ${prows.length} 条，前 3：${prows.slice(0, 3).map((r) => r.querySelector('.pname').textContent).join(' | ')}`);
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
await wait(40);
const activeRow = $('#paletteList .palette-row.active');
log(`  ↓ 选中：${activeRow?.querySelector('.pname').textContent}`);
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
await wait(40);
log(`  Esc 关闭：display=${cs($('#palette')).display}`);

log('\n== 搜索 ==');
for (const q of ['报销', '成绩', '报修', '游泳']) {
  typeSearch(q);
  const cards = $$('#list .card');
  const titles = cards.slice(0, 3).map((c) => c.querySelector('.card-title').textContent.trim());
  log(`  「${q}」→ ${cards.length} 条，前 3：${titles.join(' | ')}`);
}
typeSearch('');

log('\n== 筛选 ==');
const clickChip = async (group, value) => {
  const chip = $$(`#${group} .chip`).find((c) => c.dataset.v === value);
  if (!chip) { log(`  （${group} 里没有「${value}」项，跳过）`); return; }
  chip.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(80);
};
// 校区/对象已改为"首次打开时问一次 + 侧栏身份卡"，不再有两排筛选
log(`  校区/对象筛选已移除：fCampus=${Boolean($('#fCampus'))} fAudience=${Boolean($('#fAudience'))}`);
log(`  身份卡：${$('#profileBody')?.textContent.trim() || '（无）'}`);

await clickChip('fPurpose', '生活');
log(`  点击「生活」→ ${$$('#list .card').length} 条`);
await clickChip('fPurpose', '生活');
await clickChip('fPurpose', '生活');

await clickChip('fKind', 'miniprogram');
log(`  点击「微信小程序」→ ${$$('#list .card').length} 条`);
log(`  前 3：${$$('#list .card').slice(0, 3).map((c) => c.querySelector('.card-title').textContent.trim()).join(' | ')}`);
await clickChip('fKind', 'miniprogram');

log('  --- 手机端 / 电脑端 ---');
await clickChip('fPlatform', 'mobile');
log(`  点击「手机端」→ ${$$('#list .card').length} 条`);
log(`  前 3：${$$('#list .card').slice(0, 3).map((c) => c.querySelector('.card-title').textContent.trim()).join(' | ')}`);
await clickChip('fPlatform', 'mobile');
await clickChip('fPlatform', 'pc');
log(`  点击「电脑端」→ ${$$('#list .card').length} 条`);
await clickChip('fPlatform', 'pc');
await clickChip('fPlatform', 'both');
log(`  点击「手机+电脑」→ ${$$('#list .card').length} 条`);
await clickChip('fPlatform', 'both');
log(`  重置后 → ${$$('#list .card').length} 条`);

log('\n== 每条都有简介与端标签 ==');
const cards = $$('#list .card');
const noDesc = cards.filter((c) => c.querySelector('.card-desc').textContent.includes('暂无简介'));
const noPlat = cards.filter((c) => !c.querySelector('.badge.plat')?.textContent.trim());
log(`  卡片 ${cards.length} 张；缺简介 ${noDesc.length} 张；缺端标签 ${noPlat.length} 张`);
log(`  端标签示例：${[...new Set(cards.map((c) => c.querySelector('.badge.plat')?.textContent.trim()))].join(' / ')}`);

log('\n== 弹窗能否关闭（用户反馈的重点）==');

// 从首页磁贴打开详情抽屉
const firstTile = $('.tile[data-id]');
firstTile.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(80);
log(`  首页磁贴 → 抽屉：${$('#drawer').hidden ? '未打开（异常）' : '已打开'}，标题「${$('.di-title')?.textContent}」`);

// 关键回归：抽屉内部不得出现任何 position:fixed 的后代
// （此前内容里套了 <div class="drawer">，而 .drawer 是全屏遮罩，直接盖住了关闭按钮）
const fixedInside = [...$$('.drawer-panel *')].filter((el) => cs(el).position === 'fixed');
const nestedOverlay = $$('#drawerBody .drawer');
log(`  [回归] 面板内 position:fixed 元素：${fixedInside.length} 个${fixedInside.length ? '（异常：' + fixedInside.map((e) => e.className).join(',') + '）' : ''}`);
log(`  [回归] 内容里嵌套遮罩 .drawer：${nestedOverlay.length} 个`);

// 关闭按钮（真实冒泡点击）
$('.drawer-top .close').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  点 ✕ 关闭：display=${cs($('#drawer')).display}`);

// 遮罩点击关闭
firstTile.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
$('.drawer-bg').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  点遮罩关闭：display=${cs($('#drawer')).display}`);

// Esc 关闭
firstTile.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
await wait(60);
log(`  Esc 关闭：display=${cs($('#drawer')).display}`);

// 命令面板的关闭按钮
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
await wait(60);
log(`  命令面板打开：display=${cs($('#palette')).display}`);
$('.palette-close').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  点 ✕ 关闭命令面板：display=${cs($('#palette')).display}`);

// 未打开过的 AI 面板此时应当仍是隐藏状态
log(`  AI 面板（未打开时）：display=${cs($('#aiPanel')).display}（应为 none）`);

log('\n== 收藏与详情 ==');
const firstFavBtn = $('#list .card [data-act="fav"]');
firstFavBtn.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(300);
log(`  收藏后按钮文案：${$('#favBtn').textContent.trim()}`);
const favCard = $('#list .card.is-fav');
log(`  卡片高亮：${favCard ? '已标记' : '未标记'}`);

$('#favBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  只看收藏 → ${$$('#list .card').length} 条`);
$('#favBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);

const detailBtn = $('#list .card [data-act="detail"]');
detailBtn.dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
const drawer = $('#drawer');
log(`  详情抽屉：${drawer.hidden ? '未打开（异常）' : '已打开'}`);
log(`  抽屉标题：${drawer.querySelector('h3')?.textContent.trim()}`);
log(`  含来源标注：${drawer.textContent.includes('收录自') ? '是' : '否'}`);
drawer.querySelector('[data-close]').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  关闭后：${drawer.hidden ? '已关闭' : '仍打开（异常）'}`);

log('\n== AI 面板（免费 AI + 关闭按钮）==');
$('#aiBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
log(`  点击「AI 找入口」后：${$('#aiPanel').hidden ? '未打开（异常）' : '已打开'}`);
log(`  面板可见性（getComputedStyle）：${window.getComputedStyle($('#aiPanel')).display}`);

// 关闭按钮——用户反馈过"关不掉"
$('#aiClose').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
const dispAfterClose = window.getComputedStyle($('#aiPanel')).display;
log(`  点击 ✕ 后 hidden=${$('#aiPanel').hidden}，display=${dispAfterClose}，`
  + `实际可见=${dispAfterClose !== 'none' ? '是（异常）' : '否'}`);

// Esc 也应能关闭
$('#aiBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(40);
window.document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
await wait(40);
log(`  Esc 关闭：display=${window.getComputedStyle($('#aiPanel')).display}`);

$('#aiBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(40);
$('#aiInput').value = '宿舍水管漏了找谁';
$('#aiSend').dispatchEvent(new window.Event('click', { bubbles: true }));
const localShown = await until(() => $$('#aiBody .msg.bot .picks button').length > 0, 8000, 150);
log(`  本地候选是否秒出：${localShown ? '是' : '否'}`);
const answered = await until(() => {
  const bots = $$('#aiBody .msg.bot');
  return bots.length > 0 && !bots[bots.length - 1].textContent.includes('正在请 AI');
}, 90000, 400);
const bots = $$('#aiBody .msg.bot');
log(`  AI 是否返回：${answered ? '是' : '超时'}`);
log(`  引擎标记：${$('#aiEngine').textContent.trim()}（${$('#aiEngine').title || '无说明'}）`);
log(`  最终回答：${bots[bots.length - 1].textContent.replace(/\s+/g, ' ').trim().slice(0, 130)}`);
log(`  推荐按钮数：${$$('#aiBody .picks button').length}`);
$('#aiClose').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(40);
log(`  再次关闭：display=${window.getComputedStyle($('#aiPanel')).display}`);

// 复原收藏状态
const favId = favCard?.dataset.id;
if (favId) {
  await fetch(`${BASE}/api/favorite`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: favId, on: false }),
  });
}

log(`\n== 搜索记录 ==`);
$('#search').value = '宿舍报修';
$('#search').dispatchEvent(new window.Event('input', { bubbles: true }));
$('#search').dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
await wait(300);
log(`  回车后侧栏搜索记录：${$$('#historyList .chip.hist').length} 条 → ${$$('#historyList .chip.hist').map((c) => c.textContent.trim()).join(' / ')}`);
$('#search').dispatchEvent(new window.Event('focus', { bubbles: true }));
await wait(60);
log(`  聚焦搜索框时下拉：${$('#searchHist').hidden ? '隐藏' : '显示'}，${$$('#histListTop .sh-item').length} 项`);
$('#histClearTop').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(300);
log(`  清空后：侧栏 ${$$('#historyList .chip.hist').length} 条，下拉 ${$('#searchHist').hidden ? '隐藏' : '显示'}`);

// 检查后端是否被写坏了收藏数据
const user = await (await fetch(`${BASE}/api/userdata`)).json();
log(`\n== 收尾 ==`);
log(`  后端收藏数据：${JSON.stringify(user.favorites)}`);
log(`  后端最近记录：${JSON.stringify(user.recent)}`);
log(`  后端搜索记录：${JSON.stringify(user.history)}`);
log(`  全程脚本异常数：${errors.length}`);

writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

/**
 * 诊断"没有匹配的入口"：用真实前端（index.html + app.js）跑一批真实说法，
 * 统计哪些查询/筛选组合会落到空结果，并把命中的条件原样打出来。
 *
 * 用法：先启动后端（python app.py --no-window），再 node empty_diagnose.mjs
 * 输出：data/_empty_diagnose.txt
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const portFile = 'D:\\AI\\xmu_hub\\data\\_runtime_port.txt';
let port = 8765;
try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) || 8765; } catch { /* 默认 */ }
const BASE = `http://127.0.0.1:${port}`;
const OUT = 'D:\\AI\\xmu_hub\\data\\_empty_diagnose.txt';

const html = readFileSync('D:\\AI\\xmu_hub\\web\\index.html', 'utf8');
const appJs = readFileSync('D:\\AI\\xmu_hub\\web\\app.js', 'utf8');

const dom = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true, resources: 'usable' });
const { window } = dom;
await new Promise((r) => { if (window.document.readyState === 'complete') return r(); const t = setTimeout(r, 4000); window.addEventListener('load', () => { clearTimeout(t); r(); }); });
window.fetch = (i, init) => fetch(typeof i === 'string' && i.startsWith('/') ? BASE + i : i, init);
window.navigator.clipboard = { writeText: async () => {} };
window.document.execCommand = () => true;
window.eval(appJs);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];
await wait(1500);

// 真实说法：自然语言长句、口语、错别字、纯英文、以及带筛选的组合
const QUERIES = [
  '我要查成绩', '研究生怎么查成绩', '我是新生，想看看宿舍条件怎么样', '请问在哪里可以报到',
  '我想申请奖学金', '怎么申请助学贷款', '有没有可以借教室的地方', '想找个地方上自习',
  '食堂几点开门', '校医院在哪儿', '怎么办校园卡', '明天有课吗', '老师好不好联系',
  '我想入党', '保研怎么弄', '想找个实习', '出国交换怎么申请', '宿舍没热水了怎么办',
  '怎么预约进校', '电动车能进学校吗', '快递去哪儿拿', '体育课在哪选', '体测什么时候',
  'sports', 'library', 'help', 'fafafa', '11111', '阿巴阿巴', '？？？',
];
const FILTERS = [
  { campus: '马来西亚分校', audience: '研究生', purpose: '办事', kind: 'miniprogram' },
  { campus: '马来西亚分校', platform: 'offline' },
  { campus: '思明校区', audience: '访客/公众', purpose: '科研' },
];

const lines = [];
lines.push(`后端端口 ${port}`);
lines.push(`\n== A. 纯搜索（无筛选）==`);
const emptyQueries = [];
for (const q of QUERIES) {
  $('#search').value = q;
  $('#search').dispatchEvent(new window.Event('input', { bubbles: true }));
  await wait(30);
  const n = $$('#list .card').length;
  const emptyVisible = !$('#empty').hidden;
  lines.push(`  ${n === 0 ? '❌' : '  '} 「${q}」→ ${n} 条${emptyVisible ? '（显示"没有匹配的入口"）' : ''}`);
  if (n === 0) emptyQueries.push(q);
}

lines.push(`\n== B. 空结果时再叠加筛选（组合放大）==`);
const clickChip = async (group, value) => {
  const chip = $(`.chip[data-g="${group}"][data-v="${value}"]`);
  if (!chip) return false;
  chip.dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(60);
  return true;
};
for (const f of FILTERS) {
  $('#resetBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
  await wait(60);
  $('#search').value = '办事';
  $('#search').dispatchEvent(new window.Event('input', { bubbles: true }));
  await wait(40);
  const applied = [];
  for (const [group, value] of Object.entries(f)) {
    applied.push(`${group}=${value}:${(await clickChip(group, value)) ? '已选' : '无此筛选'}`);
  }
  const n = $$('#list .card').length;
  lines.push(`  ${n === 0 ? '❌' : '  '} 关键词「办事」+ ${applied.join(' + ')} → ${n} 条`);
}
$('#resetBtn').dispatchEvent(new window.Event('click', { bubbles: true }));

// C. 后端不可用时页面会显示什么？（旧窗口在后端退出后刷新 = 用户实际遇到的情况）
lines.push(`\n== C. 目录没加载成功时（/api/catalog 失败）==`);
const dom2 = new JSDOM(html, { url: `${BASE}/index.html`, runScripts: 'outside-only', pretendToBeVisual: true });
dom2.window.fetch = async () => { throw new Error('ECONNREFUSED'); };
dom2.window.navigator.clipboard = { writeText: async () => {} };
try { dom2.window.eval(appJs); } catch (e) { lines.push(`  启动脚本抛错：${String(e.message).slice(0, 80)}`); }
await wait(6000);   // 等它把重试跑完（boot 的退避总时长约 4 秒）
const d2 = dom2.window.document;
lines.push(`  卡片数：${d2.querySelectorAll('#list .card').length}｜列表区可见：${!d2.querySelector('#browse').hidden}`);
lines.push(`  空状态是否显示：${!d2.querySelector('#empty').hidden}｜文案：${d2.querySelector('#empty')?.textContent.replace(/\s+/g, ' ').trim().slice(0, 40)}`);
lines.push(`  首页是否显示：${!d2.querySelector('#home').hidden}｜骨架屏是否还在：${!d2.querySelector('#loading').hidden}`);

lines.push(`\n== D. 空结果界面的自救按钮 ==`);
// D1：只看收藏（且没有收藏）——最容易人为造出空结果
$('#resetBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);
const favs = (await (await fetch(`${BASE}/api/userdata`)).json()).favorites || [];
$('#favBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(80);
lines.push(`  仅收藏（当前收藏 ${favs.length} 条）→ ${$$('#list .card').length} 条｜空状态：${!$('#empty').hidden}`);
lines.push(`    提示：${$('#emptyHint').textContent.trim()}`);
lines.push(`    按钮：${$$('#emptyActions .btn').map((b) => b.textContent.trim()).join(' ｜ ') || '（无）'}`);
$('#favBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
await wait(60);

// D2：暴力找一组会落空的 关键词×筛选
const PROBE = ['成绩', '报修', '一卡通', '游泳', '报销', '奖学金'];
const FILTER_KEYS = ['campus', 'audience', 'purpose', 'kind', 'platform'];
let found = 0;
for (const q of PROBE) {
  for (const g of FILTER_KEYS) {
    const chips = $$(`#f${g[0].toUpperCase()}${g.slice(1)} .chip`);
    for (const chip of chips.slice(0, 8)) {
      $('#resetBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
      await wait(30);
      $('#search').value = q;
      $('#search').dispatchEvent(new window.Event('input', { bubbles: true }));
      await wait(20);
      chip.dispatchEvent(new window.Event('click', { bubbles: true }));
      await wait(25);
      if ($$('#list .card').length === 0) {
        found += 1;
        if (found <= 5) {
          lines.push(`  ❌ 「${q}」+ ${chip.textContent.trim()} → 0 条｜按钮：${$$('#emptyActions .btn').map((b) => b.textContent.trim()).join(' ｜ ')}｜建议词 ${$$('#emptySugs .chip').length} 个`);
        }
      }
    }
  }
}
$('#resetBtn').dispatchEvent(new window.Event('click', { bubbles: true }));
lines.push(`  关键词×单个筛选的组合里，落空 ${found} 组`);

lines.push(`\n空查询数：${emptyQueries.length} / ${QUERIES.length}`);
writeFileSync(OUT, lines.join('\n'), 'utf8');
console.log('written');

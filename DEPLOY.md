# 把这个软件发到公网（三条路线，选一条照做）

目标：得到一个形如 `https://xxx.pages.dev/` 的网址，**打开就是这套软件**——
和桌面版是同一份前端、同一份数据（320 条），搜索、筛选、收藏、说一句话找入口全都在。

先生成产物（每次改完数据也重新跑一次）：

```
python tools/build_mobile.py      # 产出 dist-mobile/（约 950 KB，含 portal.json）
```

`dist-mobile/` 里已经放好了托管平台要用的东西：`_headers`（缓存策略）、`robots.txt`、`.nojekyll`。
**整个目录原样上传即可，不用改任何文件。**

---

## 路线 A：Cloudflare Pages（推荐：免费、自带 https、可以直接拖拽）

1. 打开 <https://dash.cloudflare.com/>，用邮箱注册/登录（免费）
2. 左侧 **Workers & Pages** → **Create** → **Pages** → **Upload assets**
3. 项目名填 `xmu-hub`（这决定网址：`https://xmu-hub.pages.dev`）
4. 把 **`dist-mobile` 文件夹整个拖进去**（不是拖里面的文件，是拖文件夹）
5. Deploy → 等十几秒 → 拿到 `https://xmu-hub.pages.dev`

之后每次要更新数据：重新 `build_mobile.py`，再进项目 → **Create new deployment** → 重新拖一次。
（会写命令行的也可以用 `npx wrangler pages deploy dist-mobile`，但要先 `npx wrangler login`。）

## 路线 B：Netlify Drop（最省事：拖一下就出网址）

1. 打开 <https://app.netlify.com/drop>
2. 把 `dist-mobile` 文件夹拖进页面中间
3. 几秒后得到一个 `https://随机名.netlify.app` 的网址；注册（可用 GitHub / 邮箱）后可以
   改名、绑定自定义域名

## 路线 C：GitHub Pages（有 GitHub 账号的话最"正规"）

```bash
cd dist-mobile
git init
git add -A
git commit -m "deploy xmu hub"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

然后在仓库 **Settings → Pages**：Source 选 `Deploy from a branch`，Branch 选 `main` / `root`，保存。
一两分钟后网址是 `https://<用户名>.github.io/<仓库名>/`。

> 注意：GitHub Pages 是子路径部署，本站所有引用都是**相对路径**（`./app.js`、`portal.json`），
> 子路径下也能正常跑，不用改配置。

---

## 部署完必须做一次验收

```
python tools/deploy_check.py https://你的网址/
```

逐项检查：

1. 首页能开、标题与 og 分享卡片齐全（微信里发链接才是一张卡片而不是光秃秃一条链接）
2. `portal.json` 是合法 JSON、**条目数与本地一致**
3. manifest / `sw.js` / 分享图 / 192 与 512 图标都在
4. **浏览器到底认不认这个 PWA**：manifest 的 `Content-Type` 是不是 JSON 类型、
   有没有 192px 图标、Service Worker 能不能取到——这三条缺一条，手机上就**装不到主屏**
5. 是不是 https（`http` 下浏览器不允许添加到主屏幕）
6. **传上去的是不是本地这一版**：把线上 `index.html` / `app.js` / `styles.css` / `sw.js` /
   `portal.json` 逐个和本地 `dist-mobile/` 比 SHA-256，不一样就直接告诉你"传的是旧版本"

想连页面里引用的每个 css/js/图标都查一遍：

```
python tools/deploy_check.py https://你的网址/ --deep
```

### 已经踩过的两个坑（都已修，重新部署即可）

| 现象 | 原因 | 修法 |
|---|---|---|
| **手机上页面划不动** | 桌面版是"页面不滚、左右两栏各自滚"，`html, body` 上有 `height:100%; overflow:hidden`。手机上把 `main` 改成了单列自适应，但这两条没解开，内容超出就被 body 裁掉了 | 窄屏断点里把 `html, body` 恢复成 `height:auto; overflow:visible`，顶栏改成 `position:sticky` |
| **装不到主屏** | ① 文件叫 `manifest.webmanifest`，Netlify 不认识这个后缀，回的是 `application/octet-stream`，浏览器据此判定 manifest 无效；② manifest 里只有 128/256/512 图标，Chrome 判定"可安装"要求**至少 192px 和 512px** | ① 改名成 `manifest.json`（任何托管都按 `application/json` 发）；② 补 192 / 384 两个尺寸（`tools/make_pwa_icons.py`） |

这两条现在都由 `deploy_check.py` 的第 3 组和第 3b 组自动把关，不会再悄悄溜过去。

### 第二个坑：Netlify 会把 `_headers`、`_redirects` 收走

部署后访问 `/ _headers` 会 404 —— 这是正常的，Netlify 在部署时就把这两个文件解析掉、不对外发布。
所以**不要靠 `_headers` 去改 `Content-Type`**（Netlify 也不会让静态文件覆盖它自己判断的类型），
文件名本身才是决定 MIME 的东西：`.json` → `application/json`，`.webmanifest` → 它不认识 → `octet-stream`。

### 手机上还是装不上？让页面自己告诉你原因

在手机上打开网址 → 点顶栏「📲 装到主屏」：

- 如果浏览器**给了**安装权限 → 出现「一键添加」，点它即可
- 如果**没给**（比如还是装不了）→ 卡片里会自动跑一次自检并逐条列出原因，例如：

```
✔ 是 https
✘ Service Worker 没注册成功（安装条件之一）
✔ manifest 能取到（application/octet-stream）
✘ manifest 的类型是 application/octet-stream，浏览器只认 JSON 类型 —— 托管平台没配对 MIME
✘ manifest 里缺 192 或 512 的图标（现在有 128x128）
```

把这一屏截个图发我就能直接定位，不用猜。

## 上线之后

- **手机浏览器打开 → 添加到主屏幕**：之后点主屏图标全屏打开、断网也能翻目录（要 https）
- **发到微信/QQ 群里**：会显示 `share-card.png` 那张卡片（标题、副标题、缩略图）
- **更新数据**：`build_data.py` → `build_mobile.py` → 重新部署一次，所有人下次打开就是新的
  （桌面版的 exe 则要重新打包分发，这是网页版最省事的地方）

## 没有服务器、只想先给人看一眼？

用内网穿透拿一个临时 https 地址（电脑关了就失效）：

```bash
python tools/preview_mobile.py 8080                 # 先在本机起静态服务
cloudflared tunnel --url http://localhost:8080      # 另开一个窗口（需先装 cloudflared）
# 或
npx localtunnel --port 8080
```

## 关于"非官方"

`index.html` 左侧栏里已经写明：**本站是学生作品、不是厦门大学官方产品，数据整理自各单位官网公开信息**。
公网发布时建议保留这段说明；如果之后要挂到学校名下，需要走学校的审批流程。

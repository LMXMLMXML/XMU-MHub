# 仓库说明（Repository Notes）

本文件说明**这个 GitHub 仓库里有什么、没有什么、为什么**。
面向想 clone 下来跑一遍的人，以及想看懂工程取舍的人。

主文档见 [README.md](README.md)（项目全貌、功能、设计、踩坑记录、验证记录）。

---

## 1. 仓库性质

**源码仓库 + 手机端（PWA）可部署产物**，不是发布仓库。

体积较大、可再生的东西（打包好的 exe、安装包、内置工具链）**故意不进版本控制**，
这样仓库保持在几 MB，clone 迅速，也不会因为塞进 851 MB 的安装包而无法推送。

---

## 2. 目录结构

```
厦大统一门户/
├── app.py                    # 后端主程序（Python 标准库，约 1400 行）
├── 启动.bat                   # 源码启动（带控制台，便于看报错）
├── 启动-无控制台.bat            # 源码启动（静默）
├── README.md                 # 项目主文档（功能 / 设计 / 踩坑 / 验证）
├── DEMO.md / DEMO.txt        # 演示脚本与演示流程
├── DEPLOY.md                 # 部署说明
├── COVERAGE.md               # 316 条入口的收录覆盖与依据
│
├── web/                      # ★ 前端源码（唯一真源）
│   ├── index.html            #   单页骨架
│   ├── app.js                #   全部交互逻辑
│   ├── styles.css            #   设计系统（浅深双主题变量）
│   ├── sw.js                 #   Service Worker（离线可用）
│   ├── manifest.json         #   PWA 清单
│   └── assets/               #   校徽 / 院徽 / OH 标识 / 自研 LOGO
│       └── logo/DESIGN.md    #   自研 LOGO 的完整设计规范
│
├── data/                     # ★ 数据
│   ├── portal.json           #   316 条结构化目录（构建产物，前端直接消费）
│   └── link_status.json      #   逐条实测的链接存活状态
│
├── tools/                    # ★ 构建与验证工具（53 个脚本）
│   ├── build_data.py         #   从《网址总集》《小程序总集》生成 portal.json
│   ├── build_mobile.py       #   生成 dist-mobile/（PWA 静态站点）
│   ├── make_logo.py          #   一套几何常量同时生成 SVG + PNG + ICO
│   ├── extract_palette.py    #   从官方素材量化取色
│   ├── fetch_assets.py       #   从官网抓取校徽/院徽
│   ├── process_assets.py     #   去白底 / 裁边 / 缩放
│   └── audit_*.py / check_*.py / probe_*.py   # 审计与回归检查
│
├── dist-mobile/              # 手机端 / PWA 构建产物（可离线，可直接托管）
├── .devtools/                # 前端回归测试（Node + jsdom，20 个 .mjs）
└── .gitignore
```

> **前端只有一个真源**：`web/`。
> `dist-mobile/` 是 `python tools/build_mobile.py` 从 `web/` + `data/portal.json`
> 生成的静态副本 —— 同样的前端不需要为手机重写一遍（原因见 README「为什么不用重写」）。

---

## 3. 仓库里**没有**什么（以及怎么补回来）

| 未收录 | 体积 | 为什么 | 怎么补 |
|---|---|---|---|
| `downloads/OllamaSetup.exe` | 851 MB | 超过 GitHub 单文件上限，且是第三方安装包 | 从 [ollama.com](https://ollama.com) 官方下载 |
| `dist/`（含 exe、绿色版） | 28 MB | 构建产物，可重现；二进制进 git 历史后无法真正删掉 | **直接下载**见下；自己打包见 README「自己重新打包」 |
| `.build/` | PyInstaller 中间产物 | 纯缓存 | 打包时自动生成 |
| `.buildtools/` | 28.6 MB | PyInstaller 工具链，非本项目源码 | 打包脚本会自动装到工作区内（无需管理员权限） |
| `.devtools/node_modules/`、`.npm-cache/` | 27 MB | npm 依赖，可 `npm i` 重装 | `cd .devtools && npm install` |
| `data/userdata.json` | 0.2 KB | 本机运行态（收藏 / 最近 / 搜索记录） | 运行软件自动生成 |
| `data/_*.txt` | ~500 KB | 一次性调试输出，无长期价值 | 运行对应 `tools/` 脚本重新生成 |
| `__pycache__/`、`*.spec` | — | Python 缓存与打包配置副本 | 自动生成 |

**只想要源码**：clone 下来 `python app.py` 即可运行，不需要补任何东西
（零第三方依赖，见下节）。

### 想要能直接双击运行的 exe，而不是源码

**到 [Releases 页面](https://github.com/LMXMLMXML/XMU-MHub/releases/latest) 下载 `XMU-MHub-*-portable.zip`**，
解压双击即可，不需要装 Python。

仓库里没有 exe 是**有意的**：二进制一旦提交进 git，会永久留在历史里（即使后来删掉，
clone 时仍要拖下来），所以打包产物走 Release 分发，不占仓库体积。

Release 由 `.github/workflows/release.yml` 自动构建——打一个 `v*` 的 tag 并推送，
GitHub 就会重新打包绿色版并挂上去：

```bat
git tag v1.0.0
git push origin v1.0.0
```

> 只发布**绿色版**（onedir）。单文件版（onefile）体积更小，但需要自解压到临时目录，
> 被杀毒软件误报的概率明显更高，所以不随 Release 发布。

---

## 4. 运行要求

- **Python 3.10+**
- **零第三方依赖**：仅用标准库（`http.server` + `urllib`）
  —— 设计目的是"演示现场不会因为装包失败而翻车"
- 浏览器：Windows 自带 **Edge**（打包版用 `--app` 模式开成独立窗口）；
  源码运行用任意现代浏览器打开 `http://127.0.0.1:8765`

```bash
python app.py            # 默认监听 8765，被占用则顺延
python app.py --new      # 强制新实例（默认会复用已在运行的实例）
```

---

## 5. 数据来源与准确性

`data/portal.json` 的 316 条入口来自两份人工整理的总集
（《厦门大学网址总集》《厦门大学微信小程序总集》），并经过：

1. `tools/build_data.py` 结构化 —— 打上校区 / 对象 / 用途 / 端 / 形态 / 关键词标签；
2. `tools/audit_links.py` **逐条 GET 实测**，结果写进 `data/link_status.json`
   —— 确认失效的 21 条已删除，原因逐条记录；
3. `tools/audit_descriptions.py` 检查简介覆盖 —— 316 条全部有简介，缺简介 0 条；
4. `tools/audit_classify.py` 复核分类。

完整覆盖依据见 [COVERAGE.md](COVERAGE.md)，验证记录见 README「验证记录」一节。

> ⚠️ 高校网站与小程序变动频繁。`link_status.json` 是**某个时间点的快照**，
> 不代表当前状态。发现失效入口欢迎提 Issue。

---

## 6. 素材来源与授权

- **厦门大学校徽、信息学院院徽、OpenHarmony 标识**：取自各自官网**公开素材**，
  仅用于本项目界面展示与配色推导（配色来自 `tools/extract_palette.py` 的量化取色）。
  **版权归原权利人所有，不得用于商业用途。**
- **自研 LOGO**（`web/assets/logo/`）：本项目原创，由 `tools/make_logo.py` 生成，
  纯图形无文字。规范见 `web/assets/logo/DESIGN.md`。
- **文档中出现的电话号码**：均为学校各部门**官方公开电话**（来自官方公告与使用指南），
  用于提供办事入口，非个人隐私信息。
- 本项目为**非官方**第三方工具，与厦门大学无隶属关系。

---

## 7. 这是课程作业 / 面试作品

项目最初为 **OpenHarmony 技术俱乐部（厦门大学）二面** 的「vibe coding」环节而做，
目标是用自然语言驱动开发，做出一个**真的能用、并且真的被验证过**的软件。

因此仓库里有两点和普通 demo 不同：

1. **README 里大量"踩过的坑"** —— 每个坑都写了现象、根因、修复、加固手段。
   这是开发过程的真实记录，不是营销文案。
2. **`tools/` 里 53 个脚本大半是验证脚本** —— 链接是否真的活着、简介是否真的齐全、
   抽屉是否真的点得到、测试有没有打到旧实例。宁可多写脚本，也不靠"我看着没问题"。

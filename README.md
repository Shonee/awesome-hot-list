# awesome-hot-list

一个由 GitHub Actions 定时采集、以静态 JSON 和页面公开展示的热榜项目。仓库暂由个人维护，公开用于查看、浏览数据和 Fork，不运行常驻 API、数据库或任务服务。

源码和运行数据分离维护：`master` 保存代码，`data-pages` 保存最近 7 天 CSV 和完整 `site/`。`pages.yml` 从 `data-pages/site` 发布 GitHub Pages，无需 Node.js 或前端构建步骤。

## 推荐工具

[![OrcaRouter Partner](https://img.shields.io/badge/OrcaRouter-Partner-2563eb)](https://www.orcarouter.ai/ref/ref_534409880046a7fd980d)

本项目推荐使用 [OrcaRouter](https://www.orcarouter.ai/ref/ref_534409880046a7fd980d) 统一接入多种 AI 模型。

> 上述链接为 OrcaRouter Partner 推荐链接。

## 页面与数据

`site/index.html` 包含三个视图：

- 今日报告：基于当天已有 CSV 时间片生成去重热点、词云、综合 Top 10、排名曲线和变化信号。
- 最新热榜：按本地配置展示渠道和渠道内多榜单，支持卡片、紧凑列表、渠道 Tabs、浅色/夜间主题。
- 历史报告：展示上一日完整报告，分析方法与今日一致。

主题、布局、单榜数量、渠道显隐和排序只保存在浏览器 `localStorage`，不会改动仓库配置。

## 渠道

| 渠道 | 榜单 | 默认采集 | 备注 |
| --- | --- | --- | --- |
| 哔哩哔哩 | 热门搜索、全站热门、视频排行 | 是 | 官方公开接口 |
| 抖音 | 热搜 | 是 | 公开接口可能调整 |
| 微博 | 热榜 | 是（1 小时） | 页面接口可能限制访问 |
| 知乎 | 热搜、热榜 | 特殊调度 | 需要 `ZHIHU_COOKIE`，默认 6 小时检查 |
| GitHub | 日/周/月趋势、语言榜 | 是（6 小时） | Trending 页面，Search API 兜底 |
| 掘金 | 热门文章 | 是 | 公开推荐接口 |
| 今日头条 | 热点榜 | 是 | 公开榜单接口 |
| RSS | 新闻/AI资讯 Feed | 是 | 默认 9 个公开源，每个源按时间取最多 5 条，可用 `HOTLIST_RSS_FEEDS` 覆盖 |
| AcFun | 日榜、三日榜、周榜 | 是 | 公开榜单接口 |
| IT之家 | 最新资讯 | 是 | RSS |
| 豆瓣 | 小组精选 | 是 | HTML 解析 |
| 虎扑 | 热榜 | 是 | 使用移动端服务端渲染数据，桌面入口可能被 WAF 拦截 |
| 36氪 | 热榜 | 是 | 公开榜单接口 |
| 同花顺 | 今日要闻 | 是 | HTML 解析，结构可能调整 |
| 脉脉 | 职场热议 | 特殊调度 | 需要 `MAIMAI_COOKIE`，默认 6 小时检查 |
| 雪球 | 热门话题 | 特殊调度 | 默认 6 小时检查，旧公开接口可能返回业务限制 |
| V2EX | 热门主题 | 是（3 小时） | 公开接口；部分网络环境可能出现 TLS 访问限制 |
| Stack Overflow | 热门问题 | 是 | Stack Exchange 公开 API |
| 财联社 | 热门快讯 | 是 | 首页 SSR 数据，详情链接指向电报文章 |
| 博客园 | 24 小时推荐排行 | 是 | 公开 HTML 排行页 |
| Linux.do | 本周热门主题 | 否 | 保留适配器，默认不采集；可在 GitHub Actions 网络环境中按需验证 |
| NodeSeek | 热门主题 | 是 | 公开页面 HTML，实际可用性以 Actions 采集结果为准 |
| 吾爱破解 | 热门热帖 | 是 | Discuz 热榜页面 |
| 腾讯新闻 | 实时资讯 | 是 | 首页公开文章链接，页面结构变化时可能为空 |
| 百度贴吧 | 最有料热点 | 是 | 贴吧首页右上角热点榜，使用公开热点话题 JSON |

单渠道失败不会中断同批其他渠道。`site/data/latest.json` 会保留上一次成功快照并标记为 `stale`，避免页面因一次网络抖动清空。

## 轻量架构

```text
src/hotlist/models.py       统一 HotItem / Ranking / ChannelSnapshot
src/hotlist/registry.py     渠道顺序、元数据和惰性注册
src/hotlist/channels/       每个渠道一个抓取与解析适配器
src/hotlist/runner.py       失败隔离、latest.json 合并
src/hotlist/report.py       基于 CSV 的当天/日终报告
src/script/collect.py       统一采集 CLI
src/script/archive.py       七日滚动归档、校验和清理
src/script/render.py        生成正式页面和日报 JSON
src/template/site.html      正式页面模板
data-pages:archived/        最近 7 天 CSV
data-pages:site/            页面和静态 JSON
GitHub Releases             超过 7 天的长期归档
```

每个渠道统一输出：

```json
{
  "schemaVersion": 1,
  "channelId": "bilibili",
  "channelName": "哔哩哔哩",
  "sourceUrl": "https://www.bilibili.com/v/popular/all",
  "fetchedAt": "2026-09-04 12:00:00",
  "status": "ok",
  "rankings": [
    {
      "id": "popular",
      "name": "全站热门视频",
      "items": [{"rank": 1, "title": "...", "url": "...", "hot": 123}]
    }
  ]
}
```

新增渠道时只需在 `src/hotlist/channels/` 增加一个与渠道 ID 同名、返回 `ChannelSnapshot` 的适配器，并在 `registry.py` 登记元数据；`36kr` 这类 ID 与 Python 模块名不一致时才需增加别名。适配器不写文件、不返回 JSON 字符串；持久化、页面配置和失败处理不需要复制。

## 本地运行

建议使用 Python 3.12。源码目录与数据目录分开，先检出 `data-pages` 工作树：

```bash
python3 -m pip install -r src/requirements.txt
git fetch origin
git worktree add --track -b data-pages ../awesome-hot-list-data origin/data-pages
python3 src/script/collect.py bilibili --data-root ../awesome-hot-list-data
python3 src/script/collect.py bilibili,douyin --data-root ../awesome-hot-list-data
python3 src/script/collect.py all --data-root ../awesome-hot-list-data
python3 src/script/render.py --data-root ../awesome-hot-list-data
```

如果本地已经存在 `data-pages` 分支，将工作树命令改为 `git worktree add ../awesome-hot-list-data data-pages`。

只做临时本地验证时，也可以把 `--data-root` 指向已忽略的 `.runtime`，不提交其中内容。

## 采集频率与归档

- `collect-hourly.yml` 每小时运行一次，默认采集注册表中频率为 60 分钟的公开渠道。
- `collect-special.yml` 也每小时触发，但 `collect.py --due` 会按照渠道上次成功快照和注册表中的 `frequency_minutes` 判断是否实际请求。当前 GitHub、知乎、雪球、脉脉为 6 小时，V2EX 为 3 小时，其余默认 1 小时。
- 手动运行特殊渠道时可以选择 `force`，忽略间隔立即采集；新增渠道只需在 `registry.py` 设置频率，无需新增一个 Action。
- `render-daily.yml` 每天生成前一天完整报告，同时更新今日报告。
- `archive-weekly.yml` 每周一北京时间 02:00 将超过 7 个日历日的数据打包到 GitHub Release。`data-pages` 保留最近 7 天的 CSV，旧 CSV 和日期报告会进入 `hotlist-archive-through-YYYY-MM-DD` Release。
- 首次迁移时可手动将 `include_legacy` 设为 true，一次性归档旧 JSON、Markdown、GIF、`data.json` 等非规范文件；渠道 README 和最近 7 天 CSV 会继续保留。
- Release 包含压缩包、清单和 SHA256 校验文件，清单同时记录 `master` 代码提交和 `data-pages` 数据提交。只有远端资产上传并校验成功后，Action 才删除超期文件并把 `data-pages` 压缩为单个滚动快照提交；手动 dry-run 不创建 Release，也不更新分支。

只验证抓取、不写归档：

```bash
HOTLIST_WRITE=0 python3 src/script/collect.py toutiao,acfun --data-root .runtime
```

本地查看正式页面：

```bash
python3 -m http.server 4311 --directory ../awesome-hot-list-data/site
```

然后访问 `http://127.0.0.1:4311/`。

## 首次初始化 data-pages

新 Fork 或新仓库通过 **Bootstrap data-pages** 工作流初始化运行数据分支：

1. 在 GitHub 仓库进入 **Actions > Bootstrap data-pages > Run workflow**。
2. 工作流从 `master` 的模板渲染一个空站点，创建无父提交的 `data-pages`，并写入 `site/` 与 `archived/.gitkeep`。
3. 确认 `data-pages` 中存在 `site/index.html`、`site/data/latest.json` 和 `site/data/reports/today.json`。
4. 手动运行一次 **Collect hourly hotlists** 生成首批数据，再确认 **Deploy Pages** 成功。

工作流可以安全重跑：如果 `data-pages` 已存在，只执行远端关键文件验证。它不会修改 `master`，也不依赖源码分支中存在历史归档。

## 部署到 GitHub Pages

1. 在仓库 **Settings > Pages > Build and deployment** 中将 Source 设置为 **GitHub Actions**。
2. 在 **Settings > Actions > General** 中确认工作流允许使用具有写权限的 `GITHUB_TOKEN`；组织策略不能禁止仓库请求 `contents: write`。
3. 先完成 `data-pages` 初始化，再手动运行一次 **Deploy Pages**。
4. 后续采集、日报和周归档成功后，`workflow_run` 会部署 `data-pages/site` 的最新快照。

## 部署到 Cloudflare Pages

Cloudflare Pages 可以直接监听 `data-pages`，不需要额外构建或 Cloudflare API Token：

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)，进入 **Workers & Pages**。
2. 选择 **Create application > Pages > Connect to Git**，授权 GitHub 并选择本仓库。
3. `data-pages` 必须已经推送到 GitHub；将 **Production branch** 设为 `data-pages`。
4. Framework preset 选择 **None**。
5. **Build command** 留空；如果控制台要求填写，使用 `exit 0`。
6. **Build output directory** 填写 `site`，Root directory 保持仓库根目录或留空。
7. 不需要配置环境变量，因为采集在 GitHub Actions 中完成，Cloudflare 只发布静态文件。
8. 选择 **Save and Deploy**。部署成功后访问 Cloudflare 分配的 `*.pages.dev` 地址。
9. 在 **Settings > Builds & deployments > Branch control** 中保持 `data-pages` 的自动生产部署开启，并把 Preview branch deployments 设为 **None**，避免 `master` 因没有 `site/` 而产生无效预览构建。
10. 分别检查 `/`、`/data/latest.json` 和 `/data/reports/today.json`，再等待下一次采集，确认 Production deployment 对应的提交已更新。

需要自定义域名时，在 Pages 项目的 **Custom domains** 中添加域名并按 Cloudflare 提示完成 DNS 配置。Cloudflare 官方说明参见 [Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)、[Build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/) 和 [Branch deployment controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/)。

## 配置

本地配置写入仓库根目录 `.env`，CI 使用同名 GitHub Actions Secrets。参考 `.env.example`，不要提交真实 Cookie。

RSS 默认包含少数派、爱范儿、量子位、InfoQ、极客公园、MIT Technology Review、Hacker News、AI News 和阮一峰网络日志。每个 Feed 按发布时间倒序取数据，默认最多 5 条，可用 `HOTLIST_RSS_LIMIT` 调整为 1-5 条。

`HOTLIST_RSS_FEEDS` 支持逗号或换行分隔，也支持 `名称|URL`，设置后会覆盖默认源：

```text
HOTLIST_RSS_FEEDS=IT之家|https://www.ithome.com/rss/,https://example.com/feed.xml
HOTLIST_RSS_LIMIT=5
```

页面端还可以在右上角设置中分别调整每个 RSS 源的展示条数、分源 Tabs 或聚合时间线，以及文章发布时间显示。页面设置只保存在浏览器 `localStorage`，不会修改采集配置。

## 待评估渠道

按接入稳定性和与现有内容的互补性，后续可评估谷歌热搜、必应热搜、百度热搜、东方财富和新浪财经。优先使用公开接口或稳定页面，只有在没有可维护接口且数据价值明确时才考虑浏览器抓取；渠道源数据不足或更新较慢时，再通过 RSS 作为补充。

## 检查

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
git diff --check
```

## 数据与限制

- `data-pages` 中的 CSV 按采集批次追加，继续作为趋势和报告的主要输入。
- `data-pages:site/data/latest.json` 是最新统一快照；`site/data/reports/` 保存今日、上一日和日期归档报告。
- `master` 不再跟踪 `archived/` 和 `site/`；Fork 后需要先创建或初始化自己的 `data-pages`。
- 第三方接口与 HTML 结构可能随时变化，真实可用性以 Actions 日志为准。
- 每周滚动快照只限制 `data-pages` 后续可达历史；迁移前已经存在于 `master` 的数据历史不会自动消失，仍需单独的历史清理和强制推送确认。

代码使用 MIT License。

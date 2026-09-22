# awesome-hot-list

一个由 GitHub Actions 定时采集、以静态 JSON 和页面公开展示的热榜项目。仓库暂由个人维护，公开用于查看、浏览数据和 Fork，不运行常驻 API、数据库或任务服务。

源码和运行数据分离维护：`master` 保存代码，`data-pages` 保存最近 7 天 CSV 和完整 `site/`。`pages.yml` 从 `data-pages/site` 发布 GitHub Pages，无需 Node.js 或前端构建步骤。

## 推荐工具

[![OrcaRouter Partner](https://img.shields.io/badge/OrcaRouter-Partner-2563eb)](https://www.orcarouter.ai/ref/ref_534409880046a7fd980d)

本项目推荐使用 [OrcaRouter](https://www.orcarouter.ai/ref/ref_534409880046a7fd980d) 统一接入多种 AI 模型。

> 上述链接为 OrcaRouter Partner 推荐链接。

## 页面与数据

`site/index.html` 包含三个视图：

- 最新热榜：按本地配置展示渠道和渠道内多榜单，支持卡片、紧凑列表、渠道 Tabs、浅色/夜间主题。
- 今日报告：基于当天已有 CSV 时间片生成去重热点、词云、归一化综合 Top 10、排名曲线，以及与昨日对比的新增、升温、降温、持续和掉榜热点。
- 历史报告：可选择最近 7 个有数据的日期，并展示所选日期相对前一日的同类变化信号。

网站默认打开最新热榜。主题、布局、桌面端单榜数量、渠道显隐和排序只保存在浏览器 `localStorage`，不会改动仓库配置；普通榜单在移动端固定展示前 10 条，7x24 快讯按时间倒序最多展示 100 条，均由页面自然滚动。

综合 Top 10 同时考虑跨渠道覆盖、榜单内相对名次、持续在榜比例和最近一次出现位置，其中跨渠道覆盖权重最高。报告只处理普通热榜，不处理 7x24 和 Readhub 内容。报告中的“采样完成度”按渠道配置频率计算当天应有采样数与实际唯一采集时间数；旧报告没有该字段时，页面会回退显示原有渠道覆盖率。

## 渠道

| 渠道 | 榜单 | 默认采集 | 备注 |
| --- | --- | --- | --- |
| 哔哩哔哩 | 热门搜索、全站热门、视频排行 | 是 | 官方公开接口 |
| 抖音 | 热搜 | 是 | 公开接口可能调整 |
| 快手 | 快手热榜 | 是（3 小时） | 官方页面优先，失败时依次使用今日热榜和 DailyHot API |
| 微博 | 热榜 | 是（1 小时） | 页面接口可能限制访问 |
| 知乎 | 热搜、热榜 | 是 | `ZHIHU_COOKIE` 可选；官方热榜不可用时使用今日热榜降级源 |
| 百度热搜 | 实时热搜 | 是 | 官方榜单页结构化数据 |
| GitHub | 日/周/月趋势、语言榜 | 是（6 小时） | Trending 页面，Search API 兜底 |
| Hacker News | Top Stories | 是（2 小时） | 官方 Firebase API；最多读取前 25 个详情并展示 20 条 |
| Hugging Face | Trending Models | 是（6 小时） | 官方模型 API；已通过 Actions 网络验证 |
| Google Trends | 香港趋势 | 否 | 官方 Trending Now 页面；属搜索趋势而非热榜，默认不采集、不展示且不进入综合报告，可手动采集并在显示设置中开启；中国大陆无对应地区榜，使用香港地区 |
| 必应国内热点 | 国内热点 | 否 | 普通 HTTP 请求无法稳定获取首页热点，默认停用并隐藏；不使用国际版新闻替代 |
| 汽车之家 | 每日热点榜 | 是 | 官方热点榜 JSON，保留原站内容链接和热度 |
| 游民星空 | 热点资讯排行 | 是 | 官方资讯页侧栏的独立 15 条排名，不混入最新资讯 |
| IT之家 | 日榜 | 是 | 官方首页日榜，不解析 RSS |
| 第一财经 | 首页头条、7x24 | 是 | 首页编辑头条每小时采集；官方快讯接口每 15 分钟刷新 |
| 掘金 | 热门文章 | 是 | 公开推荐接口 |
| Lobsters | Hottest | 是 | 官方 JSON API |
| 今日头条 | 热点榜 | 是 | 公开榜单接口 |
| 腾讯新闻 | 热点榜 | 是 | 腾讯官方 JSON 接口优先，失败时使用今日热榜降级源 |
| 网易新闻 | 热门新闻 | 是 | 官方移动端热闻接口 |
| 新浪 | 新闻热榜、财经热榜、7x24 | 是 | 普通榜单每小时采集；7x24 每 15 分钟刷新并嵌入同一卡片 |
| 澎湃新闻 | 热新闻 | 是 | 官方首页结构化接口 |
| AcFun | 日榜、三日榜、周榜 | 是 | 公开榜单接口 |
| 豆瓣 | 小组精选 | 是 | HTML 解析 |
| 虎扑 | 虎扑首页、步行街热帖 | 是 | 首页读取移动端可跳转的帖子链接；步行街保留原有榜单 |
| 煎蛋网 | 4 小时热门 | 是 | 官方 4 小时榜接口；该 tab 以看图为主，纯图条目改用热评内容作为标题，按投票数排名 |
| 36氪 | 热榜 | 是 | 公开榜单接口 |
| 同花顺 | 今日要闻 | 是 | HTML 解析，结构可能调整 |
| 东方财富 | 股票人气榜 | 是（3 小时） | 官方人气榜；批量行情不可用时保留股票代码榜单 |
| 脉脉 | 职场热议 | 否 | 需要 `MAIMAI_COOKIE`，默认不采集、不展示且不进入综合报告，可手动采集和展示 |
| 雪球 | 热门话题 | 是（6 小时） | 官方接口优先，失败时使用今日热榜降级源 |
| V2EX | 热门主题 | 是（3 小时） | 公开接口；部分网络环境可能出现 TLS 访问限制 |
| Stack Overflow | 热门问题 | 是 | Stack Exchange 公开 API |
| 财联社 | 热门文章、电报 | 是 | 首页热门文章每小时采集；电报每 15 分钟刷新并嵌入同一卡片 |
| 华尔街见闻 | 7x24 | 是（15 分钟） | 官方公开接口，按发布时间倒序展示 |
| Readhub | 24 小时热榜、每日早报、AI 资讯 | 是 | 作为资讯卡片展示，不进入综合报告 |
| 央视新闻 | 最新发布 | 否 | 央视网公开新闻页面；权威发布而非热榜，默认不采集、不展示且不进入综合报告，可手动采集和展示 |
| 外交部 | 例行记者会 | 否 | 外交部公开页面；权威发布而非热榜，默认不采集、不展示且不进入综合报告，可手动采集和展示 |
| 博客园 | 最新帖子、精华帖子、48 小时阅读排行 | 是 | 首页和精华页只读正文帖子，阅读榜读取公开侧栏接口；各榜单失败隔离 |
| NodeSeek | 热门主题 | 是 | 公开页面 HTML，实际可用性以 Actions 采集结果为准 |
| 吾爱破解 | 人气热门、精华采撷 | 是 | 精华榜为可选来源，遇到 JavaScript 验证时保留原有人气榜 |
| 微信文章 | 24h 热文榜 | 是 | 微信无公开全网文章热榜，当前使用今日热榜，条目跳转公众号原文 |
| 百度贴吧 | 最有料热点 | 是 | 贴吧首页右上角热点榜，使用公开热点话题 JSON |
| 福利吧 | 最新文章 | 是 | 官方首页；正常采集但默认隐藏，不进入综合报告，可在显示设置中开启 |

单渠道失败不会中断同批其他渠道。内容面分别保存在 `site/data/latest.json`、`live.json`、`digest.json` 和 `authority.json`，各自保留上一次成功快照并标记为 `stale`；旧版合并快照会自动迁移。必应国内热点旧快照只保留 24 小时。Google Trends、央视新闻和外交部默认停止采集后，页面上的历史快照仍留在对应内容面文件中，只是不再更新且默认不展示。

首屏只请求普通热榜，其他内容面在浏览器空闲时并行补齐；卡片按实际 DOM 节点数控制首批挂载，首屏预算为 1500，其余卡片由 `IntersectionObserver` 在接近视口时替换稳定高度的占位卡。报告只在进入对应视图时下载；普通请求使用浏览器缓存，手动重试才强制刷新。站点 JSON 使用紧凑编码，归档 CSV 增加 `surface` 字段以区分内容面。

## 轻量架构

```text
src/hotlist/models.py       统一 HotItem / Ranking / ChannelSnapshot
src/hotlist/registry.py     渠道顺序、元数据和惰性注册
src/hotlist/catalog.py      可导出渠道目录和增量变更逻辑
src/hotlist/channels/       渠道适配器和少量复用数据源 Provider
src/hotlist/runner.py       失败隔离、内容面分流和快照合并
src/hotlist/report.py       基于 CSV 的当天/日终报告
src/script/collect.py       统一采集 CLI
src/script/archive.py       七日滚动归档、校验和清理
src/script/render.py        生成正式页面和日报 JSON
config/channels/            渠道全量基线、当前快照、Schema 和增量变更
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
      "surface": "hotlist",
      "items": [{"rank": 1, "title": "...", "url": "...", "hot": 123, "publishedAt": ""}]
    }
  ]
}
```

新增渠道时在 `src/hotlist/channels/` 增加一个返回 `ChannelSnapshot` 的适配器，在 `registry.py` 登记元数据和允许的内容面，再按 [渠道信息目录](docs/channel-catalog.md) 执行 `channel_catalog.py sync`，同步更新当前全量数据并追加增量记录。`36kr` 这类 ID 与 Python 模块名不一致时才需增加别名。适配器不写文件、不返回 JSON 字符串；持久化、页面配置和失败处理不需要复制。

## 本地运行

建议使用 Python 3.12。源码目录与数据目录分开，先检出 `data-pages` 工作树：

```bash
python3 -m pip install -r src/requirements.txt
git fetch origin
git worktree add --track -b data-pages ../awesome-hot-list-data origin/data-pages
python3 src/script/collect.py bilibili --data-root ../awesome-hot-list-data
python3 src/script/collect.py bilibili,douyin --data-root ../awesome-hot-list-data
python3 src/script/collect.py live --surface live --data-root ../awesome-hot-list-data
python3 src/script/collect.py all --data-root ../awesome-hot-list-data
python3 src/script/render.py --data-root ../awesome-hot-list-data
```

如果本地已经存在 `data-pages` 分支，将工作树命令改为 `git worktree add ../awesome-hot-list-data data-pages`。

只做临时本地验证时，也可以把 `--data-root` 指向已忽略的 `.runtime`，不提交其中内容。

## 采集频率与归档

- `collect-hourly.yml` 每小时运行一次，默认采集注册表中频率为 60 分钟且默认启用的公开渠道。
- `collect-live.yml` 每 15 分钟只请求新浪、财联社、第一财经和华尔街见闻的 7x24 接口，局部合并卡片内快讯榜单，不重建综合报告。
- `collect-special.yml` 也每小时触发，但 `collect.py --due` 会按照渠道上次成功快照和注册表中的 `frequency_minutes` 判断是否实际请求。当前 GitHub、雪球、Hugging Face 为 6 小时，V2EX、快手、东方财富为 3 小时，Hacker News 为 2 小时；必应国内热点和脉脉不进入默认调度，Google Trends、央视新闻和外交部属非热榜内容，同样不采集、不展示。
- 手动运行特殊渠道时可以选择 `force`，忽略间隔立即采集；新增渠道只需在 `registry.py` 设置频率，无需新增一个 Action。
- 所有采集任务只更新归档和内容面快照，不在采集进程中重建报告。
- `render-daily.yml` 每小时第 40 分钟统一生成今日报告和前一天完整报告，并执行内容面与 gzip 体积预算检查。
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
3. 确认 `data-pages` 中存在 `site/index.html`、四个内容面 JSON 和 `site/data/reports/today.json`。
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
10. 分别检查 `/`、`/data/latest.json`、`/data/live.json`、`/data/digest.json`、`/data/authority.json` 和 `/data/reports/today.json`，再等待下一次采集，确认 Production deployment 对应的提交已更新。

需要自定义域名时，在 Pages 项目的 **Custom domains** 中添加域名并按 Cloudflare 提示完成 DNS 配置。Cloudflare 官方说明参见 [Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)、[Build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/) 和 [Branch deployment controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/)。

## 配置

本地配置写入仓库根目录 `.env`，CI 使用同名 GitHub Actions Secrets。参考 `.env.example`，不要提交真实 Cookie。

`ZHIHU_COOKIE` 是可选登录凭据。配置后优先请求知乎官方热榜 API；未配置、凭据失效或官方接口返回空数据时，知乎热榜自动降级到 [今日热榜的知乎页面](https://tophub.today/n/mproPpoq6O)。知乎热搜仍优先解析知乎官方页面。微信没有面向全网公众号文章的公开官方热榜，因此微信文章卡片使用 [今日热榜的微信 24h 热文榜](https://tophub.today/n/WnBe01o371)，每条内容仍直接跳转微信公众号原文。腾讯新闻和雪球也只在官方来源失败时使用各自的今日热榜页面。

所有 TodayHot 请求共享进程级缓存和请求节流，默认不同页面之间至少间隔 3 秒，并且不会在 Provider 层连续重试。可用 `HOTLIST_TOPHUB_MIN_INTERVAL_SECONDS` 调大间隔，不建议设置得更低。

快手只在官方页面失败后请求今日热榜，只有前两级都失败才请求 DailyHot API。所有 DailyHot 请求同样共享进程级缓存和节流，默认最小间隔 5 秒，403/429 后停止本批次后续请求；可用 `HOTLIST_DAILYHOT_MIN_INTERVAL_SECONDS` 调大间隔。GitHub Actions 验证中快手官方与今日热榜均能返回有效数据，DailyHot 公共域名曾出现 DNS 不可达，因此它只作为最后一级备用源。

RSS 当前暂停：不注册渠道、不进入默认或手动采集选择、不参与报告，也不在页面显示。适配器源码与既有历史 CSV 暂时保留，便于未来重新评估时复用。

脉脉不进入默认调度。确需恢复时，先配置 `MAIMAI_COOKIE` Secret，再手动运行 hourly 工作流并将 `channels` 指定为 `maimai`；页面卡片仍需在显示设置中手动开启。

## 未接入候选

腾讯新闻、雪球和东方财富的额外 7x24 来源仍待稳定公开接口验证；当前只保留它们已有的普通榜单。地方生活资讯暂不接入。

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

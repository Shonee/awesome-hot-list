# awesome-hot-list

一个由 GitHub Actions 定时采集、以静态 JSON 和页面公开展示的热榜项目。仓库暂由个人维护，公开用于查看、浏览数据和 Fork，不运行常驻 API、数据库或任务服务。

`site/` 由 `pages.yml` 直接发布到 GitHub Pages，无需 Node.js 或前端构建步骤。

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
site/data/                  页面直接读取的静态 JSON
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

新增渠道时只需在 `src/hotlist/channels/` 增加一个返回 `ChannelSnapshot` 的适配器，并在 `src/hotlist/channels/__init__.py` 和 `registry.py` 注册。适配器不写文件、不返回 JSON 字符串；持久化、页面和失败处理不需要复制。

## 本地运行

建议使用 Python 3.12：

```bash
python3 -m pip install -r src/requirements.txt
python3 src/script/collect.py bilibili
python3 src/script/collect.py bilibili,douyin
python3 src/script/collect.py all
python3 src/script/render.py
```

## 采集频率与归档

- `collect-hourly.yml` 每小时运行一次，默认采集注册表中频率为 60 分钟的公开渠道。
- `collect-special.yml` 也每小时触发，但 `collect.py --due` 会按照渠道上次成功快照和注册表中的 `frequency_minutes` 判断是否实际请求。当前 GitHub、知乎、雪球、脉脉为 6 小时，V2EX 为 3 小时，其余默认 1 小时。
- 手动运行特殊渠道时可以选择 `force`，忽略间隔立即采集；新增渠道只需在 `registry.py` 设置频率，无需新增一个 Action。
- `render-daily.yml` 每天生成前一天完整报告，同时更新今日报告。
- `archive-weekly.yml` 每周一北京时间 02:00 将超过 7 个日历日的数据打包到 GitHub Release。当前工作区保留最近 7 天的 CSV，旧 CSV 和日期报告会进入 `hotlist-archive-through-YYYY-MM-DD` Release。
- 首次迁移时可手动将 `include_legacy` 设为 true，一次性归档旧 JSON、Markdown、GIF、`data.json` 等非规范文件；渠道 README 和最近 7 天 CSV 会继续保留。
- Release 包含压缩包、清单和 SHA256 校验文件。只有远端资产上传并校验成功后，Action 才删除工作区文件；手动 dry-run 只构建和验证，不创建 Release，也不删除文件。

只验证抓取、不写归档：

```bash
HOTLIST_WRITE=0 python3 src/script/collect.py toutiao,acfun
```

本地查看正式页面：

```bash
python3 -m http.server 4311
```

然后访问 `http://127.0.0.1:4311/site/`。

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

按接入稳定性和与现有内容的互补性，后续可评估谷歌热搜、必应热搜、百度热搜、东方财富、新浪财经、百度贴吧、吾爱破解和腾讯新闻。优先使用公开接口或稳定页面，只有在没有可维护接口且数据价值明确时才考虑浏览器抓取；渠道源数据不足或更新较慢时，再通过 RSS 作为补充。

## 检查

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
git diff --check
```

## 数据与限制

- CSV 按采集批次追加，继续作为趋势和报告的主要输入。
- `site/data/latest.json` 是最新统一快照；`site/data/reports/` 保存今日、上一日和日期归档报告。
- 历史上生成的 `archived/<channel>/data.json` 与 GIF 保留为静态旧归档，但当前流程不再生成它们；新的报告只读取 CSV 并写入 `site/data/reports/`。
- 第三方接口与 HTML 结构可能随时变化，真实可用性以 Actions 日志为准。
- Release 归档解决的是后续工作区体积和长期下载，不会缩小已经存在的 Git 历史；公开历史清理仍需单独规划和确认。

代码使用 MIT License。

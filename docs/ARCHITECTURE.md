# 采集与页面架构

## 取舍

项目继续使用 GitHub Actions、CSV 归档、静态 JSON 和 GitHub Pages。参考 `orz-ai/hot_news` 的渠道适配器、统一返回模型和失败隔离，但不引入 FastAPI、Redis、MySQL、APScheduler、浏览器池、LLM 分析或通知系统。

当前只有个人维护，静态产物足以支持外部查看和 Fork；常驻服务会额外增加部署、密钥、数据迁移和故障处理成本。

## 数据流

```text
channel adapter
  -> ChannelSnapshot
  -> collect.py
     -> archived/<channel>/<year>/<month>/csv/<date>.csv
     -> archived/<channel>/README.md
     -> site/data/latest.json

archived CSV
  -> report.py
  -> site/data/reports/today.json
  -> site/data/reports/previous.json
  -> site/data/reports/<date>.json

src/template/site.html
  -> render.py
  -> site/index.html
  -> pages.yml
  -> GitHub Pages
```

默认采集由 `collect-hourly.yml` 每小时触发。特殊渠道也由每小时触发的
`collect-special.yml` 统一调度，但 `runner.due_channel_ids()` 按注册表频率和
上次成功的 `fetchedAt` 决定是否请求，避免为每个渠道维护单独的 Action。
`archive-weekly.yml` 每周把超过 7 个日历日的 CSV 和日期报告打包到 Release，
只有远端资产校验成功后才执行清理。

## 边界

- 适配器只处理来源特有的请求和字段转换。
- runner 统一处理渠道选择、异常隔离和最新快照合并。
- report 只读取已有 CSV，不访问网络。
- 页面只读取静态 JSON，不包含渠道请求逻辑和凭证。
- `src/script/collect.py` 是唯一的渠道采集入口；渠道适配器不负责归档，也不作为独立脚本运行。
- 历史 `archived/*/data.json` 和 GIF 只作为静态旧归档保留，当前流程不再维护；`render.py` 直接基于 CSV 生成站点报告。
- 虎扑使用移动端页面的服务端渲染 JSON，不引入浏览器运行时；GitHub 使用 Trending 页面并以官方 Search API 作为兜底。
- 掘金使用当前公开的热门文章接口，直接转换为统一的单榜快照。
- Stack Overflow 使用 Stack Exchange 公开 API，V2EX 使用公开 hot topics 接口并保留域名回退；V2EX 的 TLS/访问限制由 runner 的失败隔离处理。
- 财联社使用首页的 Next.js `__NEXT_DATA__` SSR 数据解析热门快讯，不引入 Playwright 或常驻浏览器。
- RSS 适配器使用内置公开源，也支持环境变量覆盖；每个 Feed 独立失败隔离并按发布时间限制条数。页面端可在 localStorage 中设置 RSS 卡片显隐、分源 Tabs/聚合时间线、每源展示条数和发布时间显示。

## 失败语义

- `ok`：本次采集成功。
- `disabled`：缺少该渠道明确要求的配置。
- `error`：首次采集失败且没有历史快照。
- `stale`：本次采集失败，页面继续展示上次成功快照。

这一状态模型比空数组更有信息，也不会把接口故障误报成“榜单当前没有热点”。

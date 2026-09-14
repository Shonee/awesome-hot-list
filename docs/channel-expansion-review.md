# 热榜渠道扩展代码审查

## 结论

未发现阻断发布的关键或主要问题。实现符合官方源优先、第三方受控回退、非 RSS 独立卡片、失败隔离和分频调度的设计。

## 审查范围

- 第一批：百度、网易、新浪、东方财富、Hacker News。
- 第二批：澎湃新闻、Lobsters、Hugging Face。
- 候选验证：Google Trends、Bing、快手官方、今日热榜快手、DailyHot 快手。
- 公共能力：失败快照重试、第三方限频、网络结构校验、RSS 去重。

## 风险检查

- 请求规模：Hacker News 最多请求 25 个详情并展示 20 条；单个详情失败只产生 warning。东方财富行情名称使用一次批量请求。
- 第三方限制：TodayHot 默认至少间隔 3 秒，DailyHot 默认至少间隔 5 秒；两者均有进程缓存和 403/429 冷却。
- 降级语义：东方财富行情增强失败时仍保留股票代码榜；快手按官方、TodayHot、DailyHot 顺序降级；失败刷新保留上次成功数据。
- 来源可信度：Google Trends 使用官方 Trending Now 页面内结构化数据；Bing 没有把普通搜索结果或已退役 API 作为热榜。
- 展示与报告：通过 Actions 验证的新增渠道默认采集、显示并进入综合报告；Hacker News 已从 RSS 默认源移除以避免重复。

## 验证证据

- 本地测试：154 个测试通过。
- Python 编译：`python -m compileall -q src tests` 通过。
- 工作流：全部 8 个 YAML 文件可解析。
- 格式：`git diff --check` 通过。
- Actions 全量探测 `34801952894`：第一、二批全部有效，Google Trends 20 条，Hugging Face 20 条；诊断出快手官方超时和 DailyHot DNS 故障。
- Actions 快手复验 `34802206965`：快手官方 49 条，TodayHot 快手 50 条，工作流成功。

## 残余风险

Google Trends、快手、百度等页面内结构化数据没有稳定 API 契约；新浪、网易、澎湃、东方财富使用公开可访问的内部接口但没有 SLA。后续结构变化会被网络探测和“无有效条目”检查识别，页面继续展示最后成功快照。

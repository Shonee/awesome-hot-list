# 热榜渠道扩展实施计划

## 任务 1：锁定注册和调度契约

- 文件：`tests/test_hotlist_core.py`、`tests/test_frequency.py`
- 内容：新增渠道顺序、频率、默认可见性和失败快照立即重试测试。
- 验证：目标测试先失败，注册与调度实现后通过。

## 任务 2：实现第一批官方渠道

- 文件：`tests/test_channel_expansion.py`、`src/hotlist/channels/baidu.py`、`netease.py`、`sina.py`、`eastmoney.py`、`hackernews.py`
- 内容：为每种结构化响应先写 fixture 测试，再实现最小解析与采集逻辑。
- 验证：新浪输出两个 Ranking；东方财富仅一次批量名称查询；Hacker News 不超过 30 次详情请求。

## 任务 3：实现第二批渠道

- 文件：`tests/test_channel_expansion.py`、`src/hotlist/channels/thepaper.py`、`lobsters.py`、`huggingface.py`
- 内容：实现官方数据解析、去重、条目上限和最小有效数量检查。
- 验证：fixture 测试与采集快照测试通过。

## 任务 4：实现快手双源与第三方保护

- 文件：`tests/test_channel_expansion.py`、`tests/test_provider_rate_limit.py`、`src/hotlist/channels/kuaishou.py`、共享第三方请求模块。
- 内容：官方 Apollo 状态解析，DailyHot JSON 回退，进程缓存、最小间隔和封禁冷却。
- 验证：官方优先、回退来源标记、缓存与 429 冷却测试通过。

## 任务 5：扩展 GitHub Actions 网络验证

- 文件：`src/script/check_channel_network.py`、`.github/workflows/check-channel-network.yml`
- 内容：按端点配置请求方式与结构校验，覆盖所有新增源及 Google、Bing、快手候选。
- 验证：本地 validator 测试通过；提交推送后手动运行 Actions 并保存摘要。

## 任务 6：更新注册、RSS 与文档

- 文件：`src/hotlist/registry.py`、`src/hotlist/channels/rss.py`、`README.md`、`docs/ARCHITECTURE.md`、采集工作流。
- 内容：注册通过验证的渠道，配置频率，从 RSS 移除 Hacker News，记录来源与限制。
- 验证：注册表、可见性、报告和工作流测试通过。

## 任务 7：集成验证与审查

- 文件：`docs/channel-expansion-review.md`、`docs/channel-expansion-final-report.md`
- 内容：运行全量测试、编译、YAML 解析、真实源小范围采集、静态页面桌面和移动端检查；审查错误处理、请求规模和回归风险。
- 验证：所有本地门禁通过；Actions 结果决定实验渠道最终启用状态，并验证远端真实采集数据。

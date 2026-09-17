# 渠道信息目录

## 存储结构

`config/channels/base.v1.json` 是首份不可变全量基线，`config/channels/current.json` 是当前可直接导出的全量数据，`config/channels/changes/` 保存可顺序回放的增量变更。

单个渠道包含：

- 基本信息：`channelId`、名称、简称、排序、业务类型。
- 内容语义：`hotlist/live/digest/authority` 内容面。
- 来源信息：首页、适配器模块、入口函数、公开页面与 API 端点。
- 运行信息：采集频率、默认启用/展示/报告开关、陈旧数据时限。
- 特殊要求：鉴权方式、环境变量和采集注意事项。

## 更新规则

注册表与适配器是运行时真值，全量 JSON 是可导出物。`channel_catalog.py check` 会在 CI 中检查两者一致；新增渠道但未更新目录时，CI 必须失败。

- 普通扩展使用 `sync`：追加增量并更新 `current.json`。
- 需要新基线时使用 `export`，人工评审后以新的 `base.vN.json` 开始下一条变更链。
- 校验历史时使用 `rebuild`，重建结果应与 `current.json` 完全一致。

```bash
# 校验当前全量目录与运行时注册信息一致
python3 src/script/channel_catalog.py check

# 扩展渠道后：更新全量快照并追加一份增量变更
python3 src/script/channel_catalog.py sync \
  --version 1.1.0 \
  --updated-at 2026-09-17 \
  --change-id 2026-09-17-add-example

# 从基线和全部增量重建可导出全量文件
python3 src/script/channel_catalog.py rebuild --output /tmp/channels-rebuilt.json

# 导出一份独立全量快照
python3 src/script/channel_catalog.py export \
  --version 1.1.0 \
  --updated-at 2026-09-17 \
  --output /tmp/channels.json
```

`change-id` 必须唯一且可读，增量文件只追加、不覆盖。同一次渠道扩展需将适配器、注册表、`current.json` 和新增的 `changes/*.json` 作为一个变更集评审。

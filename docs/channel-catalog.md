# 渠道信息目录

## 存储结构

`config/channels/base.v1.json` 是首份不可变全量基线，`config/channels/current.json` 是当前可直接导出的全量数据，`config/channels/changes/` 保存增量变更。回放顺序由每份增量的 `fromVersion` → `toVersion` 版本链决定，与文件名顺序无关。

单个渠道包含：

- 基本信息：`channelId`、名称、简称、排序、业务类型。
- 内容语义：`hotlist/live/digest/authority` 内容面。
- 来源信息：首页、适配器模块、入口函数、公开页面与 API 端点。
- 运行信息：采集频率、默认启用/展示/报告开关、陈旧数据时限。
- 特殊要求：鉴权方式、环境变量和采集注意事项。

## 更新规则

注册表与适配器是运行时真值，全量 JSON 是可导出物，版本号与更新时间以 `src/hotlist/catalog.py` 的 `CATALOG_VERSION`、`CATALOG_UPDATED_AT` 常量为准。`channel_catalog.py check` 会在 CI 中检查三件事：`current.json` 与运行时注册信息一致、基线仍是 schema 1 / catalog 1.0.0、全部增量可回放出 `current.json`。新增渠道但未更新目录、改动 `current.json` 里的版本号、或改写已发布的增量文件，CI 都必须失败。

- 普通扩展使用 `sync`：追加增量并更新 `current.json`，`--version` 与 `--updated-at` 需与改动后的 `catalog.py` 常量一致。
- 需要新基线时使用 `export`，人工评审后以新的 `base.vN.json` 开始下一条变更链。
- `rebuild` 从基线和全部增量重建全量文件，用于本地排查；`check` 已经强制校验同一条回放链。

```bash
# 校验全量目录、基线版本与历史回放
python3 src/script/channel_catalog.py check

# 扩展渠道后：更新全量快照并追加一份增量变更（先改 catalog.py 的两个常量）
python3 src/script/channel_catalog.py sync \
  --version 1.2.0 \
  --updated-at 2026-09-23 \
  --change-id 20260923-01-add-example

# 从基线和全部增量重建可导出全量文件
python3 src/script/channel_catalog.py rebuild --output /tmp/channels-rebuilt.json

# 导出一份独立全量快照；版本号与更新时间默认取 catalog.py 常量
python3 src/script/channel_catalog.py export --output /tmp/channels.json
```

`change-id` 必须唯一且可读，建议用 `<日期>-<序号>-<摘要>`，但它只决定文件名，不决定回放顺序；增量文件只追加、不覆盖。同一次渠道扩展需将适配器、注册表、`catalog.py` 常量、`current.json` 和新增的 `changes/*.json` 作为一个变更集评审。

# 渠道目录增量记录

本目录只追加 JSON 变更文件，不修改已发布的历史变更。文件名使用 `<日期>-<序号>-<摘要>.json`，内容由 `src/script/channel_catalog.py sync` 生成。

回放顺序由每份变更的 `fromVersion` → `toVersion` 版本链决定，与文件名字典序无关；版本链断裂、分叉或改写已发布文件都会被 `check` 拒绝。

新增或修改渠道后（先同步修改 `src/hotlist/catalog.py` 的 `CATALOG_VERSION`、`CATALOG_UPDATED_AT`）：

```bash
python src/script/channel_catalog.py sync \
  --version 1.1.2 \
  --updated-at 2026-09-22 \
  --change-id 20260922-01-add-example
python src/script/channel_catalog.py check
```

`rebuild` 可从 `base.v1.json` 和全部增量文件重建 `current.json`，用于本地排查；`check` 已经强制校验同一条回放链。

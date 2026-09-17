# 渠道目录增量记录

本目录只追加 JSON 变更文件，不修改已发布的历史变更。文件名使用 `<日期>-<序号>-<摘要>.json`，内容由 `src/script/channel_catalog.py sync` 生成。

新增或修改渠道后：

```bash
python src/script/channel_catalog.py sync \
  --version 1.1.0 \
  --updated-at 2026-09-18 \
  --change-id 2026-09-18-01-add-example
python src/script/channel_catalog.py check
```

`rebuild` 可从 `base.v1.json` 和全部增量文件重建 `current.json`，用于验证历史可回放性。

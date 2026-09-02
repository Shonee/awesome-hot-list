# awesome-hot-list

Python 脚本定时抓取各平台热榜/热搜，按天归档为 JSON / CSV / Markdown 三份，全部由 GitHub Actions 驱动，无需服务器。

数据落盘在 `archived/`，超过保留期的历史会打包发布到 [GitHub Releases](../../releases) 并从仓库中移除。

## 目录结构

```
awesome-hot-list/
├── .github/workflows/
│   ├── bilibili.yml          # B站采集，每 2 小时
│   ├── douyin.yml            # 抖音采集，每 1 小时
│   ├── github.yml            # GitHub Trending 采集，每 6 小时
│   ├── weibo.yml             # 微博采集（定时已停用）
│   ├── zhihu.yml             # 知乎采集（定时已停用）
│   └── archive-monthly.yml   # 月度归档到 Releases
├── script/
│   ├── utils.py              # 公共库：HTTP 请求、三格式落盘、目录创建
│   ├── bilibili.py
│   ├── douyin.py
│   ├── github.py
│   ├── weibo.py
│   ├── zhihu.py
│   └── requirements.txt
├── template/
│   └── zhihu_hot_template.md # 知乎 Markdown 渲染模板
└── archived/                 # 归档数据根目录
    ├── bilibili/{json,csv,md}/YYYY-MM-DD.*
    ├── douyin/YYYY/MM/{json,csv,md}/YYYY-MM-DD.*
    ├── github/               # 仅占位，暂无数据
    └── zhihu/                # 仅占位，暂无数据
```

## 已实现功能

### 1. 五平台采集器

| 平台 | 数据源 | 采集内容 | 频率 | 状态 |
| --- | --- | --- | --- | --- |
| 哔哩哔哩 | `app.bilibili.com` 搜索趋势 + `api.bilibili.com` 热门/排行接口 | 热门搜索 20 条、全站热门视频 50 条、视频排行榜 100 条 | 每 2 小时 | 运行中 |
| 抖音 | `aweme-lq.snssdk.com` 热搜接口 | 热搜约 49 条（含热度值、配图） | 每 1 小时 | 运行中 |
| GitHub | `github.com/trending` 页面解析 | 3 个时间维度（日/周/月）+ 6 种语言的周榜 | 每 6 小时 | 未产出数据 |
| 微博 | `weibo.com/ajax/statuses/hot_band` | 热搜榜 | — | 定时已注释 |
| 知乎 | 页面解析 + `hot-lists/total` API | 热搜 + 热榜 | — | 定时已注释 |

### 2. 三格式归档

每次采集同时输出三种格式：

- **JSON** — 以采集时间戳（`YYYY-MM-DD HH:MM:SS`）为 key 追加写入当天文件，一天形成多个时间切片，可回溯榜单演变。
- **CSV** — 当天内以追加模式写入，适合直接用 Excel / pandas 分析。
- **Markdown** — 可读榜单，覆盖式写入，保留最近一次采集结果。

### 3. 月度归档到 Releases

`archive-monthly.yml` 每月 2 日 03:20（北京时间）自动运行，把超出保留期的月份移出仓库：

- **保留策略**：当前月 + 3 个完整月，更早的数据才归档。
- **打包**：按渠道打成 `.tar.gz`，单包超过阈值自动分片；同时生成 `manifest-*.json` 和 `SHA256SUMS`。
- **校验闭环**：发布后重新下载 Release 资产，逐个文件比对 SHA-256，只有校验通过的文件才会被删除。
- **删除方式**：默认创建 cleanup PR 而非直接推送；可在 workflow_dispatch 中切换为 `direct`。
- **安全措施**：路径穿越防护、并发组 `archive-data-writer` 串行化、删除前二次确认哈希一致。
- 支持手动触发，可指定月份（单月或区间）、渠道、打包模式、保留月数，默认 `dry_run` 为真。

### 4. 手动运行

脚本使用相对路径，需在仓库根目录执行：

```bash
pip install -r script/requirements.txt
python script/bilibili.py
python script/douyin.py
```

## 数据现状

- 哔哩哔哩、抖音：自 2026-08-01 起连续归档，B 站每天 12 个时间切片，抖音每天 22–23 个。
- GitHub、微博、知乎：目录下仅有 `temp.md` 占位，尚未产出有效数据。

## 已知问题

1. **归档路径不统一**：B 站为 `archived/bilibili/{json,csv,md}/`（无年月），其余平台为 `archived/<渠道>/<年>/<月>/`。
2. **B 站 Markdown 标题变量未渲染**：`bilibili.py` 中标题字符串缺少 `f` 前缀，实际输出字面量 `{NOW_DATE}`。
3. **抖音采集存在崩溃隐患**：`word_cover` 字段缺失时，默认值 `[]` 被当作字典调用 `.get()` 会抛异常。
4. **知乎凭证硬编码**：`zhihu.py` 内写死了长期 cookie，而 workflow 注入的 `vars.ZHIHU_COOKIE` 并未被读取。
5. **Actions 版本割裂**：采集类 workflow 仍使用 `checkout@v2` / `setup-python@v2` 与 Python 3.8，归档类已升级到 v4/v5 与 Python 3.12。
6. **分支硬编码**：采集 workflow 固定推送到 `master`。

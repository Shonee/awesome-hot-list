# 采集、归档与部署架构

## 取舍

项目继续使用 GitHub Actions、CSV、静态 JSON、GitHub Releases 和静态页面，不引入常驻 API、数据库、任务服务或浏览器池。

源码与高频运行数据分开维护：`master` 是稳定源码分支，`data-pages` 是机器维护的七日滚动快照。这样既保留个人项目的轻量性，也避免每小时采集提交淹没源码历史。

## 分支与存储职责

```text
master
  -> src/、tests/、docs/、工作流和配置

data-pages
  -> archived/<channel>/<year>/<month>/csv/<date>.csv
  -> archived/<channel>/README.md
  -> site/index.html
  -> site/data/latest.json
  -> site/data/reports/*.json

GitHub Releases
  -> 超过 7 天的压缩归档
  -> manifest.json
  -> SHA256SUMS
```

`data-pages` 不是长期归档。它保存当前页面和报告所需的最近 7 天数据，并在每周归档后压缩为一个新的孤儿快照提交。超过 7 天的数据只保存在经过校验的 Release 资产中。

## 运行数据流

```text
master: channel adapter
  -> official source or channel-owned fallback provider
  -> ChannelSnapshot
  -> collect.py --data-root runtime/
     -> data-pages:archived/
     -> data-pages:site/data/latest.json
     -> data-pages:site/data/reports/today.json

data-pages:archived CSV
  -> report.py
  -> render.py --data-root runtime/
     -> data-pages:site/index.html
     -> data-pages:site/data/reports/

data-pages:site/
  -> GitHub Pages Artifact
  -> Cloudflare Pages Git deployment（可选）
```

Actions 将 `master` 检出到 `app/`，将 `data-pages` 检出到 `runtime/`。Python 从 `app/` 加载代码，通过 `--data-root runtime/` 读取和写入数据，不复制渠道实现到数据分支。

## 调度

- `collect-hourly.yml` 每小时采集默认渠道，只提交 `runtime/archived` 和 `runtime/site/data` 到 `data-pages`。
- `collect-special.yml` 每小时触发，由 `runner.due_channel_ids()` 根据上次成功时间和渠道频率决定是否请求。
- `render-daily.yml` 每天生成昨日完整报告；页面模板或报告代码在 `master` 更新时也会重新渲染。
- 所有数据写入工作流共用 `hotlist-repository-writer` 并发组，避免同时修改 `data-pages`。
- `pages.yml` 在上述工作流成功后检出 `data-pages`，校验关键文件并上传 `site/` Artifact。

## 七日 Release 归档

`archive-weekly.yml` 的顺序是：

1. 检出 `master` 代码和完整的 `data-pages` 历史。
2. 选择早于七日窗口的 CSV 和日期报告。
3. 生成确定性 tar.gz、manifest 和 SHA256SUMS。
4. 在本地校验压缩包内路径和每个文件哈希。
5. 创建指向 `master` 代码提交的 Release tag，上传资产。
6. 从 Release 下载资产并再次校验 SHA256。
7. 确认远端 `data-pages` 仍是本次读取的提交。
8. 删除 manifest 中列出且哈希未变化的超期文件。
9. 创建只包含剩余 `archived/` 和 `site/` 的孤儿提交。
10. 使用 `--force-with-lease` 更新 `data-pages`。

Release tag 不指向 `data-pages`，否则 tag 会继续保留已经压缩掉的数据历史。manifest 同时记录 `sourceCommit` 和 `dataCommit`，用于还原“哪个版本的代码生成了哪批数据”。

手动 `dry_run` 只执行选择、打包和本地校验，不发布 Release、不清理文件、不重写分支。任何上传、下载校验、远端分支一致性或文件哈希检查失败，后续清理和压缩都不会执行。

## 首次初始化

`bootstrap-data-pages.yml` 负责为新 Fork 创建运行数据分支：

1. 安装与正式采集相同的 Python 依赖。
2. 从 `master` 的页面模板和渠道注册表渲染空站点。
3. 创建没有父提交的 `data-pages`，写入 `site/` 和 `archived/.gitkeep`。
4. 从远端读取新分支并检查页面、最新快照和今日报告。

如果 `data-pages` 已存在，工作流只执行验证。它不修改 `master`，也不要求源码分支携带任何历史运行数据。

## 页面部署

GitHub Pages 继续采用 Actions Artifact，不把 Pages 设置切换为传统分支发布。`pages.yml` 始终上传 `data-pages/site`，并在上传前校验 `index.html`、`latest.json` 和 `today.json`。

Cloudflare Pages 是可选的并行部署目标。它直接监听 `data-pages`，生产目录为 `site`，无需构建命令和运行时环境变量。应关闭其他分支的自动 Preview，避免源码分支因没有 `site/` 产生无意义构建。

## 代码边界

- 适配器只处理来源请求和字段转换，直接返回 `ChannelSnapshot`。
- `channels/tophub.py` 是不注册卡片、不单独归档的内部降级 Provider；知乎和微信适配器负责把其结果转换成各自的 `ChannelSnapshot`。
- 榜单的 `sourceUrl` 表示页面“查看详情”地址，`providerName` 和 `providerUrl` 记录本次实际数据来源。知乎优先官方来源，微信当前使用今日热榜。
- runner 统一处理渠道选择、异常隔离和最新快照合并。
- report 只读取数据根目录中的 CSV，不访问网络。
- collect 和 render 接受显式 `--data-root`，不依赖源码与数据位于同一 Git 分支。
- archive 只负责确定性资产、校验和受限清理，Release 协议留在工作流中。
- 页面只读取同目录静态 JSON，不包含渠道请求逻辑和凭证。

## 失败语义

- `ok`：本次采集成功。
- `disabled`：缺少渠道明确要求的配置。
- `error`：首次采集失败且没有历史快照。
- `stale`：本次采集失败，页面继续展示上次成功快照。

分支拆分不改变这组业务状态。工作流或部署失败属于运行状态，应通过 Actions 和 Pages 部署记录诊断，不能伪装成榜单无数据。

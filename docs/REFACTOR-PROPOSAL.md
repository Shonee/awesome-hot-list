# awesome-hot-list 脚本结构梳理与优化方案

> 本文只做分析与方案，**未改动任何脚本**。
> 梳理时间：2026-09-02 16:00（GMT+8）

---

## 一、结论先行

一句话：**五个采集脚本里，真正在稳定产出数据的只有 B 站和抖音两个；GitHub 渠道已经持续失败；微博、知乎的定时任务是关着的。**

另外有两件需要你当场拍板的事：

1. **今天 12:47–13:21，四个脚本（`douyin`/`github`/`weibo`/`zhihu`）的落盘调用被注释掉了**，本地工作树处于"只抓取不写文件"的调试态，且未提交。
2. **知乎的长期 cookie 写死在 `zhihu.py` 第 17 行，并且已经进了公开仓库的 git 历史**。这是唯一有安全后果的问题，建议优先处理。

好消息是：GitHub Actions 一直在正常跑（最近一次 `douyin_hot` 在 15:25 成功），远程数据采集没有中断。我本地看到的数据停在 10:31，只是因为本地仓库没同步，不是采集挂了。

---

## 二、脚本结构现状

### 2.1 文件清单

| 文件 | 行数 | 职责 | 运行状态 |
| --- | --- | --- | --- |
| `script/utils.py` | 111 | 公共库：HTTP 请求、三格式落盘、目录创建 | 被依赖 |
| `script/bilibili.py` | 162 | B 站热门搜索 / 热门视频 / 排行榜 | 正常产出 |
| `script/douyin.py` | 71 | 抖音热搜 | 正常产出（本地处于调试态） |
| `script/github.py` | 137 | GitHub Trending 日/周/月 + 6 语言 | **持续失败** |
| `script/weibo.py` | 84 | 微博热搜 | 定时已注释 |
| `script/zhihu.py` | 151 | 知乎热搜 + 热榜 | 定时已注释 |

### 2.2 数据流

```
         ┌─ get()            ← utils.py:38（随机 UA + 超时 15s，无重试）
各平台    │
采集器 ───┼─ 解析（JSON 或 BeautifulSoup）
         │
         └─ 统一为 list[dict] ── json.dumps 成字符串 ──┐
                                                      │
                    ┌─────────────────────────────────┤
                    ▼                                 ▼                                 ▼
            generate_archive_json            generate_archive_csv            generate_archive_md
            （读当天文件 → 加一个           （追加模式，header=False）      （覆盖写，只留最后一次）
              时间片 key → 全量重写）
```

三个落盘函数在每个脚本里各写一了一遍，加起来 15 份近乎重复的实现。

### 2.3 已归档数据

| 渠道 | 文件数 | 起始 | 密度 |
| --- | --- | --- | --- |
| bilibili | 99 | 2026-08-01 | 12 片/天（每 2 小时） |
| douyin | 99 | 2026-08-01 | 22–23 片/天（每 1 小时，偶有缺口） |
| github | 1 | — | 仅 `temp.md` 占位 |
| zhihu | 1 | — | 仅 `temp.md` 占位 |

抖音每天 22–23 片而非 24 片，正好印证了"无重试机制"带来的偶发缺口。

---

## 三、问题清单

按严重程度分三级。**P0 = 已经坏了**，**P1 = 结构性问题**，**P2 = 健壮性与运维**。

### P0：已经坏了

**1. GitHub 渠道持续失败** — `github.py:52`

```
AttributeError: 'NoneType' object has no attribute 'find_all'
  File "./script/github.py", line 52, in get_github_trending_json
```

根因：GitHub trending 页面改版，`span.d-inline-block.mr-3` 这个 Primer CSS class 组合已经不存在，`one.find(...)` 返回 `None`。
证据：Actions run `33599826846`（2026-09-02 14:39 UTC 失败）。

注意只改第 52 行不够——第 50、54、55、56 行同样依赖 Primer class（`d-inline-block mr-3`、`Link Link--muted d-inline-block mr-3`、`d-inline-block float-sm-right`），而且 54/55 行的 `[0]`/`[1]` 硬索引还有越界风险。

**2. 知乎长期凭证硬编码** — `zhihu.py:17`

一整串 cookie（`_zap`、`z_c0`、`__zse_ck`、`SESSIONID` 等）写死在源码里，已提交进公开仓库历史。两个后果：账号凭证泄露，且随时可能过期失效。

讽刺的是 `zhihu.yml` 第 32 行已经注入了 `vars.ZHIHU_COOKIE`，但脚本从头到尾没读过它。

**3. 抖音落盘有崩溃隐患** — `douyin.py:17`

```python
"img_url": item.get('word_cover', []).get('url_list')[0],
```

默认值 `[]` 是 list 却调用 `.get()`。字段缺失时抛 `AttributeError`，`url_list` 为空时抛 `IndexError`。整条热搜里只要有一条没有封面图，整个 run 就挂。

**4. 微博的异常处理等于没有** — `weibo.py:32-36` + `:53`

三个 `except` 分支只 `logger.error` 不 `return`，函数落到末尾返回 `None`。紧接着第 53 行 `json.loads(None)` 抛 `TypeError`。捕获了异常，然后崩在下一行。

### P1：结构性问题

**5. 序列化反复横跳**

以 `bilibili.py` 为例，数据在脚本里被 `json.dumps` / `json.loads` 来回折腾至少 8 次（115、118、124、129、131、142、146、150 行）。采集器 `dumps` 成字符串 → `save_file` 再 `loads` 回来 → 落盘函数再 `dumps`。纯 CPU 浪费，而且每次 `loads` 都可能成为崩溃点。

**6. `utils.py` 的抽象形同虚设**

`zhihu.py` 自己重定义了 `get()`（20 行）、`get_or_make_file_path()`（71 行）、`saveCsv()`（78 行）、`saveText()`（88 行）；`github.py` 也重定义了 `get()`（24 行）。等于公共库只服务了 B 站和抖音两个脚本。

**7. 归档路径不统一**

```
bilibili: archived/bilibili/{json,csv,md}/YYYY-MM-DD.*
其他渠道: archived/<渠道>/<年>/<月>/{json,csv,md}/YYYY-MM-DD.*
```

`archive-monthly.yml` 靠文件名日期正则（`DATE_FILE`）匹配，路径不统一增加了维护成本；更实际的问题是 B 站数据无法按月切分。

**8. B 站 Markdown 标题变量未渲染** — `bilibili.py:137`

```python
md = '# 哔哩哔哩热榜 | {NOW_DATE} \n\n'   # 少了 f 前缀
```

实际输出字面量 `{NOW_DATE}`。已确认 `archived/bilibili/md/2026-09-01.md` 第一行就是这个样子。

**9. UA 列表拼接 Bug** — `utils.py:47-48`

第 47 行末尾缺逗号，导致两个 User-Agent 被 Python 隐式字符串拼接成一个畸形长串。随机抽到它时请求头无效。

**10. 依赖冗余**

`pyquery`、`lxml`、`xlwt` 三个包**完全未被使用**。三个 HTML 解析器都用的内置 `html.parser`，根本不需要 `lxml`。`pandas` 只为了一个 `to_csv`，是全部依赖里最重的（安装约 100MB）。

> 需要它们吗？
> `pandas` — 只在 `utils.py:91` 和 `zhihu.py` 用到，标准库 `csv` 完全可以替代
> `lxml` — 未使用（用的是内置 html.parser）
> `pyquery` — 未使用
> `xlwt` — 未使用

### P2：健壮性与运维

| # | 问题 | 位置 | 影响 |
| --- | --- | --- | --- |
| 11 | 无重试机制，单次超时 15s 即抛异常 | `utils.py:55` | 网络抖动造成数据缺口 |
| 12 | SSL 验证全局关闭 `verify=False` | `utils.py:55`、`github.py:29` | 中间人风险 + 日志刷警告 |
| 13 | 文件读写未指定编码 | `utils.py:69/79` | 依赖系统 locale，换平台即乱码 |
| 14 | 文件句柄泄漏 `json.load(open(f))` | `bilibili.py:123`、`douyin.py:39` | ResourceWarning |
| 15 | `assert` 做运行时校验，且已有 `raise_for_status`，属死代码 | `utils.py:57`、`github.py:30` | `python -O` 下被剥离 |
| 16 | JSON 全量读改写：读整个当天文件 → 加一个 key → 全量重写 | `bilibili.py:121-125` | 一次跑要读写 1.3MB，并发会丢数据 |
| 17 | CSV 列错位风险：追加模式 `header=False`，列序由首条记录字段顺序决定 | `utils.py:91-97` | B 站 CSV 混了 searches/hot/rank 三种结构，若某次 searches 为空，列序变化会导致整表错位 |
| 18 | Actions 版本过时：`checkout@v2`/`setup-python@v2` + Python 3.8 | 各采集 workflow | GitHub 已警告 Node 20 弃用；Python 3.8 已于 2024-10 EOL |
| 19 | 分支硬编码 `master` | 各采集 workflow | 与仓库默认分支强耦合 |
| 20 | 仓库体积持续增长 | 架构级 | 见下方专项说明 |

### 关于仓库体积（第 20 项，单独说）

当前 `archived/` 96MB / 32 天，年化约 1.1GB。

**关键点：`archive-monthly.yml` 把旧数据发布到 Releases 并从工作树删除，但 git 历史里的 blob 依然存在，clone 体积不会下降。** 它的设计很严谨（SHA-256 校验、发布后重新下载验证、只删验证过的文件、默认走 PR），控制的是工作树体积，不是仓库体积。真要瘦身，得重写历史或把数据迁出 git。

### 遗留代码

- `bilibili.py:87-102` `parseData()` — 死代码，从未被调用，且是已废弃的 HTML 爬取方案
- `bilibili.py:36-59` 与 `:61-84` — 两个方法除 URL 和 `type` 字段外完全相同
- `zhihu.py:123` `print(getres)` — 调试输出残留
- `douyin.py:30` `print(hot_word_data)` — 调试输出残留

---

## 四、优化方案

### 第一阶段：止血（1–2 小时，建议立刻做）

| 动作 | 位置 |
| --- | --- |
| 恢复四个脚本被注释的落盘调用（或确认有意保留） | `douyin.py:31-33`、`github.py:77-79`、`weibo.py:44-46`、`zhihu.py:149-151` |
| **轮换知乎 cookie** 并改读环境变量 `os.environ.get('ZHIHU_COOKIE')`；清理 git 历史中的凭证 | `zhihu.py:17` |
| 修 `.get()` 链式调用 + 空列表保护 | `douyin.py:17` |
| 异常分支补 `return`/`raise`，别让 `None` 流到下游 | `weibo.py:32-36` |
| 补 UA 列表逗号 | `utils.py:47` |
| 补 f-string 前缀 | `bilibili.py:137` |

> 这里面只有 cookie 那一项有安全后果，其余都是"修了更好，不修也能跑"。

### 第二阶段：抽公共层（1–2 天）

目标：五个脚本收敛成"每个只写一份 `fetch()` + 一份字段映射"，其余全部复用。

- 新建 `script/base.py`，定义 `BaseCollector` 抽象类
  - `fetch() -> list[dict]`：子类实现，只管抓数据
  - `archive()`：父类统一处理三格式落盘、限速、重试、超时
- **统一数据契约**：`index / title / desc / hot / url / image / source / type / datetime` 九字段，缺失填 `None`，不再各自为政
- **归档路径统一**为 `archived/<渠道>/<年>/<月>/<格式>/YYYY-MM-DD.*`，B 站历史数据用一次性脚本迁移
- **数据全程用 `list[dict]` 传递**，只在写文件时序列化一次，干掉 8 次横跳
- 删掉 `zhihu.py` / `github.py` 里重复的 `get` / `saveText` / `saveCsv` / `get_or_make_file_path`
- 删掉 `bilibili.py:87-102` 的死代码，合并 `:36-59` 与 `:61-84` 两个同构方法

### 第三阶段：解析层改造（0.5–1 天）

- **GitHub 渠道三个选项**：
  - (a) 改用 GitHub 官方 REST/GraphQL API —— 需配 token，但最稳定，**推荐**
  - (b) 改用结构更稳的选择器（`article.Box-row` 下用标签层级相对定位，不依赖 class 名）
  - (c) 换第三方 trending API
- 所有解析加**空结果保护**：拿不到就记 warning 并跳过该字段，不让整个 run 崩
- 解析失败时把原始 HTML/JSON 快照存到 `.archive-work`，便于事后复盘

### 第四阶段：工程化（0.5 天）

- `requirements.txt` 瘦身：删 `pyquery`/`lxml`/`xlwt`，`pandas` 换标准库 `csv`（省约 100MB 安装体积、10s+ 安装耗时）
- 请求层：`requests.Session` 复用连接 + `urllib3.Retry`（3 次，指数退避）
- 开启 SSL 验证；确需跳过时显式加注释和环境变量开关
- 文件读写统一 `encoding='utf-8'`，全程 `with` 管理句柄
- 日志级别由环境变量控制，避免 Actions 日志被 DEBUG 刷屏
- 最小单测：每个 collector 一份 fixture HTML/JSON，验证字段映射不崩

### 第五阶段：Workflow 与仓库治理（0.5 天）

- `checkout@v2` → `v4`，`setup-python@v2` → `v5`
- Python 3.8 → 3.12（与 `archive-monthly.yml` 对齐）
- 分支不再硬编码，改用 `${{ github.event.repository.default_branch }}`
- 五个结构雷同的采集 workflow 合并成一个带 `matrix` 的 `collector.yml`
- 仓库瘦身三档：
  - **短期** — 接受现状，靠 `archive-monthly` 控制工作树体积
  - **中期** — 归档数据迁到 Releases，仓库只留最近 N 天
  - **长期** — 数据落对象存储（R2 / OSS），仓库只存索引，彻底解决 git 膨胀

---

## 五、优先级建议

| 阶段 | 工作量 | 收益 | 风险 |
| --- | --- | --- | --- |
| 一、止血 | 1–2 小时 | 高 | 低 |
| 二、抽公共层 | 1–2 天 | 高 | 中（要迁移 B 站历史路径） |
| 三、解析层 | 0.5–1 天 | 中 | 低 |
| 四、工程化 | 0.5 天 | 中 | 低 |
| 五、Workflow | 0.5 天 | 中 | 低 |

建议路径：先做第一阶段止血，其中 **cookie 轮换单独优先**——它是唯一有安全后果的问题。第二阶段是收益最大的重构，但动了归档路径，建议单独一个 PR、留好回滚点。

---

## 六、需要你拍板的四件事

1. **四个脚本的落盘调用被注释，是有意调试还是忘了恢复？**
2. **知乎 cookie 要不要立刻轮换 + 清理 git 历史？**（我的建议：要，且优先于其他所有事）
3. **B 站归档路径要不要统一？** 会涉及已有的 99 个文件迁移。
4. **GitHub 渠道还维护吗？** 如果走官方 API 方案，需要配一个 token。

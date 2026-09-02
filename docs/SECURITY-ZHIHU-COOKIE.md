# 知乎 Cookie 安全整改方案

> 背景：`src/script/zhihu.py` 曾把整串知乎登录态 cookie 硬编码在源码里，并已随早期提交进入
> **公开仓库** `Shonee/awesome-hot-list` 的 git 历史。这意味着旧 cookie 已在公网暴露，
> 不只是"即将泄露"。本方案分三步处理：**轮换 → 改注入方式（已完成）→ 清理历史（待你拍板）**。

## 一、立即轮换知乎 cookie（最高优先级）

硬编码的 cookie 已经公开，任何拿到仓库历史的人都能冒用你的知乎登录态。
**第一动作不是改代码，而是让旧串失效：**

- 登录 zhihu.com → 退出登录，或改一次密码，使旧 `z_c0` / `SESSIONID` / `__zse_ck` 全部作废；
- 之后脚本用新 cookie 运行即可，旧串自然失效。

> 代码层面已无法"找回"旧 cookie 的持有者，轮换是唯一能切断冒用的手段。

## 二、新注入方式（代码已改完）

- **本地调试**：仓库根目录新建 `.env`（已被 `.gitignore` 忽略，不会进版本库），写入：
  ```dotenv
  ZHIHU_COOKIE=你新获取的完整 cookie 串
  ```
  `src/utils/utils.py` 的 `load_dotenv()` 会自动读取，无需任何环境变量配置。
- **CI 执行**：在 GitHub 仓库
  `Settings → Secrets and variables → Actions → Secrets → New repository secret`：
  - Name：`ZHIHU_COOKIE`
  - Secret：你新获取的完整 cookie 串
- 脚本读取逻辑（`src/script/zhihu.py`）：
  ```python
  ENV_ZHIHU_COOKIE = "ZHIHU_COOKIE"
  cookie = get_secret(ENV_ZHIHU_COOKIE, default="")
  ```
  `get_secret` 优先读环境变量（CI 注入的 `secrets.ZHIHU_COOKIE`），本地回退到 `.env`。
- `zhihu.yml` 已同步改为：
  ```yaml
  env:
    ZHIHU_COOKIE: ${{ secrets.ZHIHU_COOKIE }}
  ```

## 三、清理 git 历史里的旧 cookie（二选一，需你决定）

公开历史里仍保留着旧 cookie 文本。代码改完只能防止**未来**泄露，清不掉**已发生**的泄露。

### 方案 A：彻底清理（推荐，但破坏性）

用 `git filter-repo` 重写整个历史，删掉含 cookie 的行，然后 force push。

```bash
# 1. 全新克隆一个裸副本（不要在正在工作的仓库操作）
git clone --mirror git@github.com:Shonee/awesome-hot-list.git
cd awesome-hot-list.git

# 2. 用 filter-repo 删除 cookie 所在行（按关键词 z_c0 / SESSIONID 兜底）
pip install git-filter-repo
git filter-repo --replace-text <(echo 'z_c0=.*==>***REMOVED***')
# 或更彻底：直接删除整行（需先确认行内容）
# git filter-repo --replace-text <(echo 'zhihu_cookie.*==>')

# 3. force push 覆盖远程历史
git push --force --mirror

# 4. 通知所有协作者重新 clone（旧本地仓库的 reflog 里仍有旧串）
```

代价：所有协作者的本地仓库需重新 clone；所有旧 Release / PR 引用失效；
这是不可逆转的公开历史变更。

### 方案 B：接受历史泄露，仅防未来（零风险）

- 不重写历史，只确保新提交不再含 cookie（本方案前两步已完成）；
- 配合**第一步的 cookie 轮换**，旧串已失效，实际风险归零；
- 适合不愿 force push、或仓库协作者较多的场景。

> 我的建议：**先执行第一步轮换（方案 B 的实质防护）**，历史清理（方案 A）等你确认
> 愿意 force push 再动手。两者不冲突——即使选 B，旧 cookie 也已被轮换作废。

## 四、调试验证

```bash
# 本地调试：只抓不写，避免污染归档
HOTLIST_WRITE=0 ZHIHU_COOKIE="粘贴你的 cookie" python src/script/zhihu.py

# 确认 .env 不被提交
git status --short      # 不应出现 .env
git check-ignore .env   # 应输出 .env 表示已被忽略
```

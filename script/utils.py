# -*- coding: utf-8 -*-
"""
公共工具模块

承担三块职责：
1. HTTP 请求（带重试与随机 UA）
2. 时间与编码工具
3. 配置读取（环境变量 / .env / GitHub Actions Secrets）与落盘开关

文件读写能力统一委托给 :mod:`file_utils`，本模块仅保留历史函数名的转发，
以保证各采集脚本无需改动 import 即可平滑迁移。
"""

import json
import logging
import os
import random
import time

# 日志配置
logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
# logger.setLevel(level=logging.INFO)

# ---------------------------------------------------------------------------
# 文件能力转发
#
# saveText / saveJson / saveCsv 历史上定义在 utils 里且依赖 pandas。
# 实现下沉到 file_utils（改用标准库 csv，行为逐字节对齐旧实现），
# 这里保留同名导出，旧脚本的 import 不用改。
# ---------------------------------------------------------------------------
from file_utils import (  # noqa: E402,F401
    ARCHIVE_ROOT,
    append_json_timeslice as _append_json_timeslice,
    archive_path,
    ensure_dir,
    ensure_parent_dir,
    exists,
    file_size,
    read_csv,
    read_json,
    read_text,
    sha256_file,
    write_csv as _write_csv,
    write_json as _write_json,
    write_text as _write_text,
)

get_or_make_file_path = ensure_parent_dir


def saveText(text: str, file_path: str):
    """保存纯文本 / Markdown。兼容旧签名的转发函数。"""
    if not write_enabled():
        logger.info("[dry-run] 跳过文本落盘: %s", file_path)
        return file_path
    return _write_text(text, file_path)


def saveJson(data, file_path: str):
    """保存 JSON。兼容旧签名的转发函数（旧实现只接受 JSON 字符串）。"""
    if not write_enabled():
        logger.info("[dry-run] 跳过 JSON 落盘: %s", file_path)
        return file_path
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    return _write_json(data, file_path)


def saveCsv(data, file_path: str):
    """保存 CSV（追加模式）。兼容旧签名的转发函数。"""
    if not write_enabled():
        logger.info("[dry-run] 跳过 CSV 落盘: %s", file_path)
        return file_path
    return _write_csv(data, file_path, mode="append")


def save_timeslice(file_path: str, key: str, value) -> str:
    """按「时间片键 -> 数据」追加写入当天 JSON。

    这是本仓库最核心的落盘模式：同一天每个采集时刻作为一个 key。

    注意：这里必须走 utils 而不是直接调 file_utils.append_json_timeslice，
    否则会绕过落盘开关——所有落盘都应经过本模块这一层，保持单一入口。
    """
    if not write_enabled():
        logger.info("[dry-run] 跳过 JSON 落盘: %s", file_path)
        return file_path
    return _append_json_timeslice(file_path, key, value)


# ---------------------------------------------------------------------------
# 落盘开关
#
# 调试时常常只想看抓取结果、不想污染归档目录。历史上是直接把落盘调用注释掉，
# 结果某次忘了改回来，采集中断了半天。改为环境变量开关后，
# 本地 `HOTLIST_WRITE=0 python script/douyin.py` 即可，代码永不改动。
# ---------------------------------------------------------------------------

#: 落盘开关的环境变量名
ENV_WRITE = "HOTLIST_WRITE"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def _env_bool(name: str, default: bool = False) -> bool:
    """把环境变量解析为布尔值，未设置时返回 default。"""
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    logger.warning("环境变量 %s=%r 无法识别为布尔值，按默认 %s 处理", name, raw, default)
    return default


def write_enabled() -> bool:
    """是否允许写入归档文件。

    CI 上不设置该变量（默认开启）；本地调试时设 ``HOTLIST_WRITE=0`` 关闭。
    """
    return _env_bool(ENV_WRITE, default=True)


def dry_run() -> bool:
    """是否处于只抓不写的调试模式。"""
    return not write_enabled()


# ---------------------------------------------------------------------------
# 配置与密钥
#
# 所有渠道凭证一律从环境变量读取，绝不硬编码进源码。
# 本地调试：写进仓库根目录的 .env（已被 .gitignore 排除）
# CI 执行：在仓库 Settings -> Secrets and variables 里配置同名变量，
#          由 workflow 通过 env: 注入。
# ---------------------------------------------------------------------------

#: .env 的查找顺序，先命中先加载
DOTENV_CANDIDATES = (".env", "script/.env")


def load_dotenv(path: str = None, override: bool = False) -> int:
    """加载 .env 文件到 os.environ。

    不引入 python-dotenv 依赖，仓库只需要 requests + beautifulsoup4。

    :param path: 指定路径；缺省按顺序查找 DOTENV_CANDIDATES
    :param override: 是否覆盖已存在的环境变量。默认 False，
        保证 CI 注入的 Secrets 优先级高于本地文件
    :return: 成功加载的键值对数量
    """
    candidates = [path] if path else list(DOTENV_CANDIDATES)
    loaded = 0
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        with open(candidate, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue
                if override or key not in os.environ:
                    os.environ[key] = value
                    loaded += 1
        logger.debug("已加载配置: %s（%d 项）", candidate, loaded)
        break
    return loaded


# 模块导入时即尝试加载，让 `python script/xxx.py` 直接可用
load_dotenv()


def get_secret(name: str, default: str = None, required: bool = False) -> str:
    """读取凭证类配置。

    :param name: 环境变量名，如 ``ZHIHU_COOKIE``
    :param default: 缺省值
    :param required: True 时缺失直接抛异常，避免带着空 cookie 静默跑飞
    """
    value = os.environ.get(name)
    if value is None or not value.strip():
        if required:
            raise RuntimeError(
                f"缺少必需配置 {name}。"
                f"本地调试请在仓库根目录 .env 中配置；"
                f"CI 请在 Settings -> Secrets and variables -> Actions 中配置同名变量。"
            )
        return default
    return value.strip()


# ---------------------------------------------------------------------------
# 时间
# ---------------------------------------------------------------------------

def get_current_date(pattern="%Y-%m-%d %H:%M:%S"):
    """获取当前时间字符串。"""
    now = time.strftime(pattern, time.localtime())
    logger.debug("当前时间：{}".format(now))
    return now


NOW_TIME = get_current_date("%Y-%m-%d %H:%M:%S")
NOW_DATE = get_current_date("%Y-%m-%d")


def get_current_year_month_day():
    """返回 (年, 月, 日)，月日两位补零。"""
    from datetime import datetime
    current_time = datetime.now()
    year = str(current_time.year)
    month = "{:02d}".format(current_time.month)
    day = "{:02d}".format(current_time.day)
    return year, month, day


# ---------------------------------------------------------------------------
# 编码
# ---------------------------------------------------------------------------

def url_encode(url):
    from urllib.parse import quote
    return quote(url)


def url_decode(url):
    from urllib.parse import unquote
    return unquote(url)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# 随机 UA 池，降低被识别为爬虫的概率。
# 注意：Python 中相邻字符串字面量会被隐式拼接，
# 历史上这里漏了一个逗号导致两个 UA 被拼成畸形串。
USER_AGENT_LIST = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
]


def random_user_agent() -> str:
    """随机返回一个 User-Agent。"""
    return random.choice(USER_AGENT_LIST)


#: 默认请求超时（秒）
DEFAULT_TIMEOUT = 15

#: 默认重试次数。采集类任务最大的敌人是偶发网络抖动，
#: 一次抖动就让当天少一个时间片，历史数据就断了。
DEFAULT_RETRIES = 3

#: 重试退避基数（秒），实际间隔为 base * 2^(n-1)
DEFAULT_BACKOFF = 1.0


def get(url, res_type='text', headers: dict = None, timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES, session=None):
    """发起 GET 请求。

    :param res_type: ``text`` 返回字符串，``json`` 返回已解析的对象
    :param headers: 额外请求头，会与随机 UA 合并
    :param timeout: 单次请求超时
    :param retries: 重试次数，0 表示不重试
    :param session: 复用 requests.Session（如知乎需要保持 cookie 时）

    相较旧实现的变化：
    - 用显式判断替代 ``assert``，``python -O`` 下不会被优化掉
    - 默认开启 SSL 校验（旧实现 verify=False 会刷警告且不安全）
    - 增加指数退避重试
    """
    import requests

    merged = {'User-Agent': random_user_agent()}
    if headers:
        merged.update(headers)

    last_error = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            caller = session or requests
            response = caller.get(url, headers=merged, timeout=timeout)
            if response.status_code != 200:
                raise requests.HTTPError(
                    f"HTTP {response.status_code} for {url}", response=response
                )
            return response.json() if res_type == 'json' else response.text
        except Exception as e:  # noqa: BLE001 - 采集脚本不应因单次抖动整体崩溃
            last_error = e
            if attempt < retries:
                wait = DEFAULT_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "请求失败(%d/%d) %s: %s，%.1fs 后重试",
                    attempt, retries, url, e, wait,
                )
                time.sleep(wait)
            else:
                logger.error("请求最终失败 %s: %s", url, e)

    raise last_error

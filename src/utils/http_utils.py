# -*- coding: utf-8 -*-
"""
HTTP 请求工具（独立模块，零项目内依赖）

只依赖标准库 + ``requests``，**不 import 本仓库任何其它工具模块**，
因此本模块可以单独引入使用，而不必连带加载文件/配置等无关逻辑::

    from http_utils import get, random_user_agent

设计要点
--------
- 随机 UA：降低被识别为爬虫的概率。
- 指数退避重试：采集类任务最大的敌人是偶发网络抖动，
  一次抖动就让当天少一个时间片，历史数据就断了。
- SSL 校验默认开启（``verify=False`` 会刷警告且不安全）。
- 用显式判断替代 ``assert``，``python -O`` 下不会被优化掉。
- 时间操作（退避等待）直接用标准库 ``time`` 自行实现，
  不依赖其它模块的日期工具，保证本模块完全自给自足。
"""

import logging
import random
import time
import os
import threading
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


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

#: 单次请求在域名冷却里最多愿意等待的秒数。冷却是别人给的节奏，
#: 采集任务有自己的调度周期：等满 10 分钟不如让这一渠道本轮缺席，
#: 陈旧标记会告诉前端和下一轮任务真实情况。
DEFAULT_DOMAIN_MAX_WAIT = 30.0

#: 上游 Retry-After 的采纳上限（秒）
DOMAIN_COOLDOWN_CAP = 120.0

_DOMAIN_STATE = {}
_DOMAIN_LOCK = threading.Lock()


class DomainCooldownError(RuntimeError):
    """域名仍在冷却中，且剩余等待超出了本轮采集愿意付出的预算。"""


def _domain_max_wait() -> float:
    try:
        return max(0.0, float(os.environ.get("HOTLIST_DOMAIN_MAX_WAIT_SECONDS", DEFAULT_DOMAIN_MAX_WAIT)))
    except (TypeError, ValueError):
        return DEFAULT_DOMAIN_MAX_WAIT


def _domain_gate(url: str) -> None:
    """Apply an optional process-wide per-domain request interval/cooldown."""
    minimum = max(0.0, float(os.environ.get("HOTLIST_DOMAIN_MIN_INTERVAL_SECONDS", "0")))
    host = (urlparse(url).hostname or "").lower()
    if not host or minimum <= 0:
        return
    with _DOMAIN_LOCK:
        wait_until = _DOMAIN_STATE.get(host, 0.0)
    remaining = wait_until - time.monotonic()
    if remaining > 0:
        budget = _domain_max_wait()
        if remaining > budget:
            raise DomainCooldownError(
                f"{host} is cooling down for another {remaining:.0f}s, over the {budget:.0f}s budget"
            )
        time.sleep(remaining)
    with _DOMAIN_LOCK:
        _DOMAIN_STATE[host] = time.monotonic() + minimum


def _mark_domain_cooldown(url: str, seconds: float) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return
    with _DOMAIN_LOCK:
        _DOMAIN_STATE[host] = max(_DOMAIN_STATE.get(host, 0.0), time.monotonic() + seconds)


def _retryable_status(status_code: int) -> bool:
    return status_code in {408, 425, 429} or status_code >= 500


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

    本模块不依赖仓库内其它工具，重试退避直接用标准库 ``time`` 实现。
    """
    import requests

    merged = {'User-Agent': random_user_agent()}
    if headers:
        merged.update(headers)

    last_error = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            _domain_gate(url)
            caller = session or requests
            response = caller.get(url, headers=merged, timeout=timeout)
            if response.status_code != 200:
                raise requests.HTTPError(
                    f"HTTP {response.status_code} for {url}", response=response
                )
            if res_type == 'json':
                return response.json()
            if res_type == 'bytes':
                return response.content
            return response.text
        except Exception as e:  # noqa: BLE001 - 采集脚本不应因单次抖动整体崩溃
            if isinstance(e, DomainCooldownError):
                raise
            last_error = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in {403, 429}:
                retry_after = getattr(getattr(e, "response", None), "headers", {}).get("Retry-After", "")
                try:
                    cooldown = min(DOMAIN_COOLDOWN_CAP, max(5.0, float(retry_after)))
                except (TypeError, ValueError):
                    cooldown = 30.0
                _mark_domain_cooldown(url, cooldown)
            should_retry = status is None or _retryable_status(status)
            if attempt < retries and should_retry:
                wait = DEFAULT_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "请求失败(%d/%d) %s: %s，%.1fs 后重试",
                    attempt, retries, url, e, wait,
                )
                time.sleep(wait)
            else:
                logger.error("请求最终失败 %s: %s", url, e)
                break

    raise last_error


def post(url, payload=None, res_type='text', headers: dict = None,
         timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES,
         session=None):
    """发起 JSON POST 请求，沿用 ``get`` 的 UA、超时和重试约定。"""
    import requests

    merged = {'User-Agent': random_user_agent()}
    if headers:
        merged.update(headers)

    last_error = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            _domain_gate(url)
            caller = session or requests
            response = caller.post(url, headers=merged, json=payload, timeout=timeout)
            if response.status_code != 200:
                raise requests.HTTPError(
                    f"HTTP {response.status_code} for {url}", response=response
                )
            return response.json() if res_type == 'json' else response.text
        except Exception as exc:  # noqa: BLE001 - retry transient source failures
            if isinstance(exc, DomainCooldownError):
                raise
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {403, 429}:
                _mark_domain_cooldown(url, 30.0)
            should_retry = status is None or _retryable_status(status)
            if attempt < retries and should_retry:
                wait = DEFAULT_BACKOFF * (2 ** (attempt - 1))
                logger.warning(
                    "请求失败(%d/%d) %s: %s，%.1fs 后重试",
                    attempt, retries, url, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.error("请求最终失败 %s: %s", url, exc)
                break

    raise last_error

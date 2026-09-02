# -*- coding: utf-8 -*-
"""GitHub Trending 采集。

关于「有没有免 token 的公开 GitHub API」
---------------------------------------
先说结论：**GitHub 官方没有 Trending API**，trending 榜单只有网页版，
不存在 api.github.com 上对应的接口。可选的两条路是：

1. 抓 https://github.com/trending 页面（本模块的主路径）
   - 权威、字段最全、无限流问题
   - 风险：页面结构变更会导致解析失效
2. 用 api.github.com 的 Search API 近似（本模块的兜底路径）
   - 官方接口、免 token 可用，未认证限流 **10 次/分钟**
   - 语义不等于 trending：Search API 无法表达「今日 star 增长」，
     只能近似为「近期创建且星多」的项目
   - 风险：按出口 IP 限流，GitHub Actions 的 runner 是共享 IP 段，
     配额可能被同 IP 的其他任务耗光（实测本机 IP 的 core 配额即为 0）

因此策略是：**主路径抓页面，页面解析整体失败时才回退 Search API**，
且回退只抓 3 个时间维度的全语言榜，避免触发限流。

解析稳定性
----------
旧实现依赖 Primer 的 CSS class（``d-inline-block mr-3`` 等），
GitHub 一次改版整套 class 就失效，直接 AttributeError 崩掉。
这里改用语义化锚点，抗改版能力强得多：

- 条目容器：``<article class="Box-row">``（语义标签）
- 仓库地址：``h2 > a`` 的 href（``/owner/repo``）
- star / fork 数：按 href 后缀匹配 ``/stargazers``、``/forks``
- 语言：``span[itemprop=programmingLanguage]``（schema.org 微数据）
- 今日新增：``span.d-inline-block.float-sm-right``，并带正则兜底
"""

import json
import os
import re
import time
from enum import Enum

from bs4 import BeautifulSoup

from utils import (
    NOW_DATE,
    NOW_TIME,
    archive_path,
    get,
    logger,
    saveCsv,
    saveText,
    save_timeslice,
    write_enabled,
)

PLATFORM = "github"

GITHUB_HOST = "https://github.com"
GITHUB_TRENDING_URL = "https://github.com/trending/{}?since={}"
GITHUB_SEARCH_API = "https://api.github.com/search/repositories"

#: 页面解析整体失败时，是否回退到 Search API
ENABLE_SEARCH_FALLBACK = True

#: Search API 未认证限流为 10 次/分钟，回退时每次请求之间留足间隔
SEARCH_API_INTERVAL = 7


class Since(Enum):
    daily = 'daily'
    weekly = 'weekly'
    monthly = 'monthly'


class Language(Enum):
    all = ''
    java = 'java'
    python = 'python'
    go = 'go'
    html = 'html'
    javascript = 'javascript'


#: Search API 近似 trending 的时间窗口（天）。
#: 无法表达「今日 star 增长」，只能退而求其次取近期新建的高星项目。
SEARCH_WINDOW_DAYS = {
    'daily': 7,
    'weekly': 30,
    'monthly': 90,
}


def _text(node) -> str:
    """取节点文本，节点不存在返回空串而不是抛异常。"""
    return node.get_text(strip=True) if node else ""


def _find_by_href(node, suffix: str):
    """按 href 后缀查找链接。

    比按 CSS class 查找稳定得多：href 是功能性的，几乎不会变；
    class 是样式，GitHub 每次改版都可能调。
    """
    return node.find("a", href=lambda h: h and h.rstrip("/").endswith(suffix))


def _parse_int(text: str):
    """把 ``31,646`` 这类文本转成整数，失败返回 0。"""
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def _stars_today(article) -> str:
    """提取「N stars today」文本，带正则兜底。

    首选结构定位，定位不到再在整块文本里正则捞，
    这样即使外层 class 改了也还有一次机会。
    """
    span = article.find("span", class_="d-inline-block float-sm-right")
    text = _text(span)
    if text:
        return text
    match = re.search(r"([\d,]+\s+stars\s+today)", article.get_text(" ", strip=True))
    return match.group(1) if match else ""


def parse_trending(html: str, language: str = "", since: str = "daily") -> list:
    """解析 trending 页面为项目列表。

    :return: 解析失败或页面无条目时返回空列表，由调用方决定是否回退
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("article", class_="Box-row")

    projects = []
    for idx, one in enumerate(items):
        heading = one.find("h2")
        link = heading.find("a", href=True) if heading else None
        if not link:
            continue

        href = link["href"].strip("/")
        parts = href.split("/")
        if len(parts) < 2:
            continue
        owner, repo = parts[0], parts[1]

        language_span = one.find("span", itemprop="programmingLanguage")
        language_text = _text(language_span)

        projects.append({
            'index': idx + 1,
            'title': repo,
            'author': owner,
            'desc': _text(one.find("p")),
            'language': language_text,
            'stars': _text(_find_by_href(one, "/stargazers")),
            'forks': _text(_find_by_href(one, "/forks")),
            'today_forks': _stars_today(one),
            'url': f"{GITHUB_HOST}/{owner}/{repo}",
            'type': 'GitHub_' + (language_text or 'all') + '_' + since,
            'datetime': NOW_TIME
        })
    return projects


def fetch_trending(language: str = "", date: str = "daily") -> list:
    """抓取指定语言与时间维度的 trending 榜。"""
    url = GITHUB_TRENDING_URL.format(language, date)
    logger.debug("github 趋势热榜 url ：{}".format(url))
    html = get(url)
    projects = parse_trending(html, language=language, since=date)
    if not projects:
        logger.warning("trending 页面解析为空: lang=%r since=%r", language, date)
    return projects


def fetch_via_search_api(date: str = "daily", per_page: int = 25) -> list:
    """兜底：用 Search API 近似 trending。

    语义说明：这**不是** trending。取的是「最近 N 天内创建、按 star 排序」
    的项目，与官方榜单的重叠度有限，但至少保证渠道不断流。
    """
    import datetime

    days = SEARCH_WINDOW_DAYS.get(date, 7)
    since_date = (
        datetime.date.today() - datetime.timedelta(days=days)
    ).isoformat()
    url = (
        f"{GITHUB_SEARCH_API}?q=created:>{since_date}"
        f"&sort=stars&order=desc&per_page={per_page}"
    )
    logger.warning("trending 页面不可用，回退 Search API: %s", url)
    payload = get(url, res_type="json")
    items = (payload or {}).get("items", [])

    projects = []
    for idx, item in enumerate(items):
        full_name = item.get("full_name", "")
        owner = (item.get("owner") or {}).get("login", "")
        repo = item.get("name", full_name.split("/")[-1])
        projects.append({
            'index': idx + 1,
            'title': repo,
            'author': owner,
            'desc': item.get("description") or "",
            'language': item.get("language") or "",
            'stars': item.get("stargazers_count", 0),
            'forks': item.get("forks_count", 0),
            'today_forks': "",
            'url': item.get("html_url", f"{GITHUB_HOST}/{full_name}"),
            'type': 'GitHub_all_' + date + '_fallback',
            'datetime': NOW_TIME
        })
    return projects


class GitHub:
    def get_github_trending_json(self, language=Language.all, date=Since.daily):
        projects = fetch_trending(language, date)
        return json.dumps(projects, ensure_ascii=False)


def save_file():
    github = GitHub()

    json_data = {}
    for since in Since:
        json_data[since.value] = json.loads(github.get_github_trending_json(Language.all.value, since.value))
        time.sleep(0.1)
    for language in Language:
        json_data[language.value] = json.loads(github.get_github_trending_json(language.value, Since.weekly.value))
        time.sleep(0.1)

    # 全部为空 = 页面结构已改版，触发兜底
    if ENABLE_SEARCH_FALLBACK and not any(json_data.values()):
        logger.error("trending 页面全部解析失败，启用 Search API 兜底")
        json_data = {}
        for since in Since:
            json_data[since.value] = fetch_via_search_api(since.value)
            time.sleep(SEARCH_API_INTERVAL)

    json_data_str = json.dumps(json_data, ensure_ascii=False)
    generate_archive_json(json_data_str)
    generate_archive_md(json_data_str)
    generate_archive_csv(json_data_str)


def generate_archive_json(githubTrendingJsonStr):
    file_path = archive_path(PLATFORM, "json", NOW_DATE)
    save_timeslice(file_path, NOW_TIME, json.loads(githubTrendingJsonStr))


def generate_md(json_str_data, title) -> str:
    """生成单个榜单的 Markdown 片段。"""
    md = title
    for data in json.loads(json_str_data):
        logger.debug("data:{}".format(data))
        img_url = 'https://s0.wp.com/mshots/v1/{url}?w=600&h=450'.format(url=data['url'])
        item = (
            f"### [{data['index']}. {data['title']}]({data['url']}) \n\n"
            f"![{data.get('title')}]({img_url}) \n\n"
            f"**🔥名称**：{data['title']} \n\n"
            f"**🧑‍💻作者**：{data['author']} \n\n"
            f"**🎬描述**：{data['desc']} \n\n"
            f"**🔗地址**: [立即访问]({data['url']}) \n\n"
            f"**👀语言**: 🔺{data['language']} \n\n"
            f"**⭐stars**：{data['stars']} \n\n"
            f"**📍forks**：{data['forks']} \n\n"
            f"--- \n\n"
        )
        md += item
    return md


def generate_archive_md(json_str_data):
    """Markdown内容并保存到data目录"""
    md = f"# GitHub 趋势热榜 | {NOW_DATE}\n\n"
    for key, value in json.loads(json_str_data).items():
        logger.debug("key:value {}:{}".format(key, value))
        md += generate_md(json.dumps(value), f"## {key} 热榜\n\n")

    saveText(md, archive_path(PLATFORM, "md", NOW_DATE))


def generate_archive_csv(jsonStr: str):
    file_path = archive_path(PLATFORM, "csv", NOW_DATE)
    csv_list = []
    [csv_list.extend(item) for item in json.loads(jsonStr).values()]
    saveCsv(json.dumps(csv_list, ensure_ascii=False), file_path)


if __name__ == '__main__':
    if not write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），只抓取不落盘")
    save_file()

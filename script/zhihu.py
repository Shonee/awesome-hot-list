# -*- coding: utf-8 -*-
"""知乎热搜 / 热榜采集。

凭证配置
--------
知乎接口需要登录态 cookie，通过环境变量 ``ZHIHU_COOKIE`` 注入，
**不再硬编码在源码里**：

- 本地调试：在仓库根目录的 ``.env`` 里写 ``ZHIHU_COOKIE=<整串 cookie>``
  （.env 已被 .gitignore 排除，不会进版本库）
- CI 执行：在仓库 Settings -> Secrets and variables -> Actions 中配置
  同名 Secret，由 workflow 的 ``env:`` 段注入

历史教训：早期版本把 z_c0 / SESSIONID / __zse_ck 等长期凭证直接写在源码里，
而该仓库是公开的，等于把账号凭证发布到了公网。凭证一旦进过 git 历史，
即使后续删除仍可追溯，因此**轮换 cookie 是必须动作，清理历史只是善后**。
"""

import json
import os
import time

from utils import (
    NOW_DATE,
    NOW_TIME,
    archive_path,
    get,
    get_secret,
    logger,
    saveCsv,
    saveText,
    save_timeslice,
    url_encode,
    write_enabled,
)

PLATFORM = "zhihu"

ZHIHU_PAGE_HOT_SEARCH = 'https://www.zhihu.com/topsearch'
ZHIHU_API_HOT_LIST = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"

#: 凭证环境变量名。CI 上配同名 Secret 即可，本地调试写进 .env
ENV_ZHIHU_COOKIE = "ZHIHU_COOKIE"


def build_headers() -> dict:
    """构造请求头，cookie 从环境变量读取。"""
    return {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
                      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 '
                      'Mobile/15E148 Safari/604.1',
        "cookie": get_secret(ENV_ZHIHU_COOKIE, default=""),
    }


def get_zhihu(url: str, timeout: int = 10) -> str:
    """带知乎请求头的 GET。"""
    return get(url, headers=build_headers(), timeout=timeout)


def generate_archive_md(searcheJsonStr, questsionJsonStr):
    searchMd = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(searcheJsonStr)])
    questionMd = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(questsionJsonStr)])

    md = ''
    file = os.path.join('template/', 'zhihu_hot_template.md')
    with open(file, encoding='utf-8') as f:
        md = f.read()

    md = md.replace("{updateTime}", NOW_TIME).replace("{searches}", searchMd).replace("{questions}", questionMd)
    logger.debug("归档md:{}".format(md))

    saveText(md, archive_path(PLATFORM, "md", NOW_DATE))


def generate_archive_csv(searcheJsonStr, questsionJsonStr):
    file_path = archive_path(PLATFORM, "csv", NOW_DATE)
    saveCsv(searcheJsonStr, file_path)
    saveCsv(questsionJsonStr, file_path)


def generate_archive_json(searcheJsonStr, questsionJsonStr):
    file_path = archive_path(PLATFORM, "json", NOW_DATE)
    payload = json.loads(searcheJsonStr) + json.loads(questsionJsonStr)
    save_timeslice(file_path, NOW_TIME, payload)


class Zhihu:
    # 知乎热门搜索数据
    def get_hot_search(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(get_zhihu(ZHIHU_PAGE_HOT_SEARCH), "html.parser")
        items = soup.find_all("div", class_="TopSearchMain-item")
        if not items:
            # 页面结构变更或登录态失效时，明确告警而不是静默产出空归档
            logger.warning("未解析到知乎热搜条目，页面结构可能已变更或 cookie 失效")
        result = []
        for item in items:
            title_el = item.find("div", class_="TopSearchMain-title")
            index_el = item.find("div", class_="TopSearchMain-index")
            if not title_el:
                continue
            title = title_el.text.strip()
            obj = {
                "type": "知乎热搜",
                'datetime': NOW_TIME,
                "index": index_el.text.strip() if index_el else len(result) + 1,
                'id': None,
                "title": title,
                "desc": "",
                "hot": None,
                "url": 'https://www.zhihu.com/search?q={}'.format(url_encode(title)),
                'img': "",
                "createtime": None
            }
            result.append(obj)
        jsonObjResult = json.dumps(result, ensure_ascii=False)
        logger.debug("知乎热搜数据 ：{}".format(jsonObjResult))
        return jsonObjResult

    # 知乎热榜数据
    def get_hot_list(self):
        getres = get_zhihu(ZHIHU_API_HOT_LIST)
        responseData = json.loads(getres).get("data")
        result = []
        for index, item in enumerate(responseData):
            children = item.get('children')
            target = item.get("target") or {}
            result.append({
                "type": "知乎热榜",
                'datetime': NOW_TIME,
                "index": index + 1,
                'id': target.get("id"),
                "title": target.get("title"),
                "desc": target.get("excerpt"),
                "hot": item.get("detail_text"),
                "url": "https://www.zhihu.com/question/" + str(target.get("id")),
                'img': "" if not children else children[0].get('thumbnail'),
                "createtime": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(target.get("created") or time.time()),
                )
            })
        jsonObjResult = json.dumps(result, ensure_ascii=False)
        logger.debug("知乎热榜数据 ：{}".format(jsonObjResult))
        return jsonObjResult


def save_file():
    zhihu = Zhihu()
    searchData = zhihu.get_hot_search()
    hotData = zhihu.get_hot_list()

    generate_archive_md(searchData, hotData)
    generate_archive_csv(searchData, hotData)
    generate_archive_json(searchData, hotData)


if __name__ == '__main__':
    if not write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），只抓取不落盘")
    if not get_secret(ENV_ZHIHU_COOKIE):
        logger.warning(
            "未配置 %s，请求大概率被拒。本地调试请在 .env 中配置，"
            "CI 请在 Actions Secrets 中配置同名变量。",
            ENV_ZHIHU_COOKIE,
        )
    save_file()

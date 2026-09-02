# -*- coding: utf-8 -*-
"""抖音热搜采集。

归档结构统一为 archived/douyin/<YYYY>/<MM>/<json|csv|md>/<YYYY-MM-DD>.<ext>
路径一律由 file_utils.archive_path 生成，不在脚本内拼字符串。
"""

import json
from datetime import datetime

import os
import sys

# 让本脚本在任意 cwd 下都能找到 src/utils 下的工具模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "utils"))

from utils import (
    NOW_DATE,
    NOW_TIME,
    archive_path,
    channel_readme_path,
    get,
    logger,
    saveCsv,
    saveText,
    url_encode,
    write_enabled,
)

PLATFORM = "douyin"


class Douyin:
    def fetch_douyin_hot_api(self):
        url = "https://aweme-lq.snssdk.com/aweme/v1/hot/search/list/"
        data = get(url, res_type='json')["data"]["word_list"]
        list = []
        for idx, item in enumerate(data):
            list.append({
                "index": idx + 1,
                "title": item.get('word', 'Unknown'),
                "hot": item.get('hot_value', 'Unknown'),
                "url": f'https://www.douyin.com/search/{url_encode(item.get("word", "Unknown"))}',
                # 注意：旧实现写作 item.get('word_cover', []).get('url_list')[0]，
                # 默认值 [] 是列表却调用了 .get()，一旦某条热搜没有封面图就会
                # AttributeError 崩掉整个 run，当天数据全部丢失。这里改为安全解析。
                "img_url": extract_cover_url(item.get('word_cover')),
                "push_time": datetime.fromtimestamp(
                    item.get('event_time', datetime.now().timestamp())
                ).strftime('%Y-%m-%d %H:%M:%S'),
                "now_time": NOW_DATE,
                "datetime": NOW_TIME,
                "type": "热搜",
                "source": "抖音"
            })
        result = json.dumps(list, ensure_ascii=False)
        logger.info(f" 抖音热搜: {result}")
        return result


def extract_cover_url(word_cover) -> str:
    """从 word_cover 字段里安全提取封面图地址，取不到返回空串。

    word_cover 有三种形态：None、{}、{"url_list": [...]}，
    都可能缺 url_list 或 url_list 为空，需全部兜住。
    """
    if not isinstance(word_cover, dict):
        return ""
    url_list = word_cover.get('url_list')
    if isinstance(url_list, list) and url_list:
        return url_list[0] or ""
    return ""


def save_file():
    douyin = Douyin()
    hot_word_data = douyin.fetch_douyin_hot_api()
    print(hot_word_data)
    generate_archive_csv(hot_word_data)
    generate_archive_md(hot_word_data)


def generate_archive_csv(json_str: str):
    file_path = archive_path(PLATFORM, "csv", NOW_DATE)
    saveCsv(json_str, file_path)


def generate_archive_md(json_str: str):
    md = f'# 抖音热搜 | {NOW_DATE} \n\n'
    md += '记录抖音热搜数据。每小时抓取一次数据，并历史记录[归档](https://github.com/Shonee/awesome-hot-list/tree/master/archived)。 \n\n'
    md += f"`更新时间：{NOW_TIME}` \n\n"

    md += '### 热门搜索 \n\n'
    md += '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(json_str)])
    md += '\n\n'

    saveText(md, channel_readme_path(PLATFORM))


if __name__ == "__main__":
    if not write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），只抓取不落盘")
    save_file()

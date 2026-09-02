# -*- coding: utf-8 -*-
"""微博热榜采集。

归档结构统一为 archived/weibo/<YYYY>/<MM>/<json|csv|md>/<YYYY-MM-DD>.<ext>
"""

import json
from datetime import datetime

from utils import (
    NOW_DATE,
    NOW_TIME,
    archive_path,
    get,
    logger,
    saveCsv,
    saveText,
    save_timeslice,
    url_encode,
    write_enabled,
)

PLATFORM = "weibo"


class Weibo:
    def fetch_weibo_hot_json_api(self):
        """抓取微博热榜。

        失败时**直接抛出**而不是返回 None。

        旧实现在 except 里只打日志、不 return，函数隐式返回 None，
        紧接着调用方 json.loads(None) 崩溃——既丢了原始错误信息，
        崩溃点还离根因十万八千里。捕获后重新抛出，至少能让 CI 标红
        且堆栈指向真实位置。
        """
        url = "https://weibo.com/ajax/statuses/hot_band"
        data = get(url, res_type='json')["data"]["band_list"]
        hot = []
        for idx, item in enumerate(data):
            note = item.get('note', 'Unknown')
            hot.append({
                "index": idx + 1,
                "title": note,
                "category": item.get('category', 'Unknown'),
                "hot": item.get('raw_hot', 'Unknown'),
                "url": f'https://s.weibo.com/weibo?q={url_encode(note)}&Refer=index',
                'createtime': datetime.fromtimestamp(
                    item.get('onboard_time', datetime.now().timestamp())
                ).strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'Weibo',
                "datetime": NOW_TIME
            })
        result = json.dumps(hot, ensure_ascii=False)
        logger.debug("微博热榜：{}".format(result))
        return result


def save_file():
    weibo = Weibo()

    hot_json_data = weibo.fetch_weibo_hot_json_api()

    generate_archive_json(hot_json_data)
    generate_archive_md(hot_json_data)
    generate_archive_csv(hot_json_data)


def generate_archive_json(hot_json_data):
    file_path = archive_path(PLATFORM, "json", NOW_DATE)
    save_timeslice(file_path, NOW_TIME, {'hot': json.loads(hot_json_data)})


def generate_archive_md(hot_json_data):
    """生成Markdown内容并保存到data目录"""
    md = f"# 微博热榜 | {NOW_DATE}\n\n"
    md += f"> 更新时间：{NOW_TIME}\n\n"

    md += f"### 微博热榜内容 \n\n"
    for data in json.loads(hot_json_data):
        md += f" [{data['index']}. {data['title']}]({data['url']}) \n\n"

    saveText(md, archive_path(PLATFORM, "md", NOW_DATE))


def generate_archive_csv(hot_json_data):
    file_path = archive_path(PLATFORM, "csv", NOW_DATE)
    json_data = {'hot': json.loads(hot_json_data)}
    csv_list = []
    [csv_list.extend(item) for item in json_data.values()]
    saveCsv(json.dumps(csv_list, ensure_ascii=False), file_path)


if __name__ == '__main__':
    if not write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），只抓取不落盘")
    save_file()

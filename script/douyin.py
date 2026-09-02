import json
import os
from datetime import datetime
from utils import get,url_encode,saveText,saveJson,saveCsv,get_current_year_month_day, logger,NOW_DATE,NOW_TIME

class Douyin:
    def fetch_douyin_hot_api(self):
        url = "https://aweme-lq.snssdk.com/aweme/v1/hot/search/list/"
        data = get(url, res_type='json')["data"]["word_list"]
        list = []
        for idx,item in enumerate(data):
            list.append({
                "index": idx+1, 
                "title": item.get('word', 'Unknown'), 
                "hot" : item.get('hot_value', 'Unknown'), 
                "url": f'https://www.douyin.com/search/{url_encode(item.get("word", "Unknown"))}', 
                "img_url": item.get('word_cover', []).get('url_list')[0], 
                "push_time" : datetime.fromtimestamp(item.get('event_time', datetime.now().timestamp())).strftime('%Y-%m-%d %H:%M:%S'),
                "now_time": NOW_DATE,
                "type" : "热搜", 
                "source" : "抖音"
            })
        result = json.dumps(list, ensure_ascii=False)
        logger.info(f" 抖音热搜: {result}")
        return result

def save_file():
    douyin = Douyin()
    hot_word_data = douyin.fetch_douyin_hot_api()
    generate_archive_json(hot_word_data)
    generate_archive_csv(hot_word_data)
    generate_archive_md(hot_word_data)


def generate_archive_json(json_str: str):
    y,m,d = get_current_year_month_day()
    file_path = os.path.join(f'archived/douyin/{y}/{m}/json/', NOW_DATE +'.json')
    json_data = json.load(open(file_path)) if os.path.exists(file_path) else {}
    json_data[NOW_TIME] = json.loads(json_str)
    saveJson(json_data, file_path)

def generate_archive_csv(json_str: str):
    y,m,d = get_current_year_month_day()
    file_path = os.path.join(f'archived/douyin/{y}/{m}/csv/', NOW_DATE +'.csv')
    data = json.loads(json_str)
    csv_list = data
    # [csv_list.extend(item) for item in data.values()]
    saveCsv(json.dumps(csv_list, ensure_ascii=False), file_path)

def generate_archive_md(json_str: str):
    y,m,d = get_current_year_month_day()
    # md = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(jsonStr)])

    md = f'# 抖音热搜 | {NOW_DATE} \n\n'
    md += '记录抖音热搜数据。每小时抓取一次数据，并历史记录[归档](https://github.com/Shonee/awesome-hot-list/tree/master/archived)。 \n\n'
    md += f"`更新时间：{NOW_TIME}` \n\n"

    md += '### 热门搜索 \n\n'
    md += '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(json_str)])
    md += '\n\n'

    saveFile = os.path.join(f'archived/douyin/{y}/{m}/md/', NOW_DATE +'.md')
    saveText(md, saveFile)

if __name__ == "__main__":
    # douyin = Douyin()
    # douyin.fetch_douyin_hot_api()

    save_file()

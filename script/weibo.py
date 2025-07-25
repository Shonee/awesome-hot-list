import json
import os
import re
import requests
from utils import get,url_encode,saveText,saveJson,saveCsv,get_current_year_month_day, logger,NOW_DATE,NOW_TIME

class Weibo:
    def fetch_weibo_hot_json_api(self):
        import json
        from datetime import datetime

        url = "https://weibo.com/ajax/statuses/hot_band"
        try:
            data = get(url,res_type='json')["data"]["band_list"]
            hot = []
            for idx,item in enumerate(data):
                note = item.get('note', 'Unknown')
                hot.append({
                    "index": idx+1, 
                    "title": note, 
                    "category" : item.get('category', 'Unknown'), 
                    "hot" : item.get('raw_hot', 'Unknown'), 
                    "url": f'https://s.weibo.com/weibo?q={url_encode(note)}&Refer=index',
                    'createtime': datetime.fromtimestamp(item.get('onboard_time', datetime.now().timestamp())).strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'Weibo',
                    "datetime" : NOW_TIME
                })
            result = json.dumps(hot, ensure_ascii=False)
            logger.debug("微博热榜：{}".format(result))
            return result
        
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
        except KeyError as e:
            logger.error(f"Key error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
 
def save_file():
    weibo = Weibo()

    hot_json_data = weibo.fetch_weibo_hot_json_api()

    generate_archive_json(hot_json_data)
    generate_archive_md(hot_json_data)
    generate_archive_csv(hot_json_data)


def generate_archive_json(hot_json_data):
    y,m,d = get_current_year_month_day()
    file_path = os.path.join(f'archived/weibo/{y}/{m}/json/', NOW_DATE +'.json')
    json_data = json.load(open(file_path)) if os.path.exists(file_path) else {}
    json_data[NOW_TIME] = {'hot': json.loads(hot_json_data)}
    saveJson(json_data, file_path)

def generate_archive_md(hot_json_data):
    y,m,d = get_current_year_month_day()
    """生成Markdown内容并保存到data目录"""
    # logger.debug("data_list:{}".format(data_list))
    md = f"# 微博热榜 | {NOW_DATE}\n\n"
    md += f"> 更新时间：{NOW_TIME}\n\n"

    md += f"### 微博热榜内容 \n\n"
    for data in json.loads(hot_json_data):
        md += f" [{data['index']}. {data['title']}]({data['url']}) \n\n"

    # logger.debug("归档md:{}".format(md))
    saveFile = os.path.join(f'archived/weibo/{y}/{m}/md/', NOW_DATE +'.md')
    saveText(md, saveFile)

def generate_archive_csv(hot_json_data):
    y,m,d = get_current_year_month_day()
    file_path = os.path.join(f'archived/weibo/{y}/{m}/csv/', NOW_DATE +'.csv')
    json_data = {'hot': json.loads(hot_json_data)}
    csv_list = []
    [csv_list.extend(item) for item in json_data.values()]
    saveCsv(json.dumps(csv_list, ensure_ascii=False), file_path)

if __name__ == '__main__':
    weibo = Weibo()
    # weibo.fetch_weibo_hot_json_api()
    # weibo.fetch_weibo_hot_searches_api()

    save_file()

import time
import json
import os
import time
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
from utils import get,url_encode,saveText,saveJson,saveCsv,get_current_year_month_day, logger,NOW_DATE,NOW_TIME


ZHIHU_PAGE_HOT_SEARCH = 'https://www.zhihu.com/topsearch'
ZHIHU_API_HOT_LIST = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"

HEADERs = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        "cookie":
        "<REDACTED>"\n    }

def get(url):
    import requests 
    response = requests.get(url, headers=HEADERs, timeout=10)
    logger.debug("请求知乎数据结果:{}".format(response))
    if response.status_code == 200:
        return response.text
    else:
        return None

def get_current_date(pattern):
    import time
    return time.strftime(pattern, time.localtime())

def generate_archive_md(searcheJsonStr, questsionJsonStr):
    searchMd = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(searcheJsonStr)])
    questionMd = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(questsionJsonStr)])

    md = ''
    file = os.path.join('template/', 'zhihu_hot_template.md')
    with open(file) as f:
        md = f.read()

    md = md.replace("{updateTime}", NOW_TIME).replace("{searches}", searchMd).replace("{questions}", questionMd)
    logger.debug("归档md:{}".format(md))

    y,m,d = get_current_year_month_day()
    saveFile = os.path.join(f'archived/zhihu/{y}/{m}/md/', NOW_DATE +'.md')
    saveText(md, saveFile)
    logger.debug("归档md文件保存地址:{}".format(saveFile))

def generate_archive_csv(searcheJsonStr, questsionJsonStr):
    y,m,d = get_current_year_month_day()
    file_path = os.path.join(f'archived/zhihu/{y}/{m}/csv/', NOW_DATE +'.csv')
    saveCsv(searcheJsonStr, file_path)
    saveCsv(questsionJsonStr, file_path)
    logger.debug("csv文件保存地址:{}".format(file_path))

def generate_archive_json(searcheJsonStr, questsionJsonStr):
    y,m,d = get_current_year_month_day()
    file_path = os.path.join(f'archived/zhihu/{y}/{m}/json/', NOW_DATE +'.json')
    json_data = {NOW_TIME: json.loads(searcheJsonStr) + json.loads(questsionJsonStr)}
    if os.path.exists(file_path): 
        json_data = json.load(open(file_path))
        json_data[NOW_TIME] = json.loads(searcheJsonStr) + json.loads(questsionJsonStr)
    else:
        get_or_make_file_path(file_path)
    with open(file_path, 'w') as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)
    logger.debug("json文件保存地址:{}".format(file_path))

# 判断文件目录是否存在, 不存在则创建目录路径
def get_or_make_file_path(file_path):
    dirname = os.path.dirname(file_path)
    if not os.path.exists(dirname): 
        os.makedirs(dirname) 
    return dirname

# csv 文本保存
def saveCsv(jsonStr: str, file_path: str):
    df = pd.read_json(jsonStr)
    # a = 追加模式, header=False 省略标题行
    if os.path.exists(file_path): 
        df.to_csv(file_path, index=False, mode='a', header=False)
    else:
        get_or_make_file_path(file_path)
        df.to_csv(file_path, index=False)

# 文件内容保存
def saveText(text: str, file_path: str):
    logger.debug('text:%s', text)
    get_or_make_file_path(file_path)
    with open(file_path, mode='w') as f:
        f.write(text)
    return file_path

class Zhihu:
    # 知乎热门搜索数据
    def get_hot_search(self):
        soup = BeautifulSoup(get(ZHIHU_PAGE_HOT_SEARCH), "html.parser")
        items = soup.find_all("div", class_="TopSearchMain-item")
        result = []
        for item in items:
            title = item.find("div", class_="TopSearchMain-title").text.strip()
            obj = {
                "type": "知乎热搜",
                'datetime': NOW_TIME,
                "index": item.find("div", class_="TopSearchMain-index").text.strip(),
                'id': None,
                "title": title,
                "desc": "",
                "hot": None,
                "url": 'https://www.zhihu.com/search?q={}'.format(urllib.parse.quote(title)),
                'img': "",
                "createtime": None
            }
            result.append(obj)
        jsonObjResult = json.dumps(result, ensure_ascii=False)
        logger.debug("知乎热搜数据 ：{}".format(jsonObjResult))
        return jsonObjResult

    # 知乎热榜数据
    def get_hot_list(self):
        getres = get(ZHIHU_API_HOT_LIST)
        print(getres)
        responseData = json.loads(getres).get("data")
        result = []
        for index, item in enumerate(responseData):
            children = item.get('children')
            result.append({
                "type": "知乎热榜",
                'datetime': NOW_TIME,
                "index": index+1,
                'id': item.get("target").get("id"),
                "title": item.get("target").get("title"),
                "desc": item.get("target").get("excerpt"),
                "hot": item.get("detail_text"),
                "url": "https://www.zhihu.com/question/" + str(item.get("target").get("id")),
                'img': "" if not children else children[0].get('thumbnail'),
                "createtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.get("target").get("created")))
            })
            jsonObjResult = json.dumps(result, ensure_ascii=False)
            logger.debug("知乎热榜数据 ：{}".format(jsonObjResult))
        return jsonObjResult

if __name__ == '__main__':
    zhihu = Zhihu()
    searchData = zhihu.get_hot_search()
    hotData = zhihu.get_hot_list()

    generate_archive_md(searchData, hotData)   
    generate_archive_csv(searchData, hotData)
    generate_archive_json(searchData, hotData)

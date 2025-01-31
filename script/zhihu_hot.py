import time
import json
import os
import time
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
import logging

# 日志配置
logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
# logger.setLevel(level=logging.INFO)

ZHIHU_PAGE_HOT_SEARCH = 'https://www.zhihu.com/topsearch'
ZHIHU_API_HOT_LIST = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"

HEADERs = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

def get(url):
    import requests 
    response = requests.get(url, headers=HEADERs, timeout=10)
    if response.status_code == 200:
        return response.text
    else:
        return None

def get_current_date(pattern):
    import time
    return time.strftime(pattern, time.localtime())
NOW = get_current_date("%Y-%m-%d %H:%M:%S")
DATE = get_current_date("%Y-%m-%d")

def generate_archive_md(searcheJsonStr, questsionJsonStr):
    searchMd = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(searcheJsonStr)])
    questionMd = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(questsionJsonStr)])

    md = ''
    file = os.path.join('template/', 'zhihu_hot_template.md')
    with open(file) as f:
        md = f.read()

    md = md.replace("{updateTime}", NOW).replace("{searches}", searchMd).replace("{questions}", questionMd)
    logger.debug("归档md:{}".format(md))

    saveFile = os.path.join('archived/md/', DATE +'.md')
    saveText(md, saveFile)
    logger.debug("归档md文件保存地址:{}".format(saveFile))

def generate_archive_csv(searcheJsonStr, questsionJsonStr):
    file_path = os.path.join('archived/csv/', DATE +'.csv')
    saveCsv(searcheJsonStr, file_path)
    saveCsv(questsionJsonStr, file_path)
    logger.debug("csv文件保存地址:{}".format(file_path))

def generate_archive_json(searcheJsonStr, questsionJsonStr):
    file_path = os.path.join('archived/json/', DATE +'.json')
    json_data = {NOW: json.loads(searcheJsonStr) + json.loads(questsionJsonStr)}
    if os.path.exists(file_path): 
        json_data = json.load(open(file_path))
        json_data[NOW] = json.loads(searcheJsonStr) + json.loads(questsionJsonStr)
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
                'datetime': NOW,
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
        responseData = json.loads(get(ZHIHU_API_HOT_LIST)).get("data")
        result = []
        for index, item in enumerate(responseData):
            children = item.get('children')
            result.append({
                "type": "知乎热榜",
                'datetime': NOW,
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

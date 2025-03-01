import json
import os
import logging

# 日志配置
logging.basicConfig(format='%(asctime)s %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
# logger.setLevel(level=logging.INFO)


# 获取当前时间
def get_current_date(pattern = "%Y-%m-%d %H:%M:%S"):
    import time
    now = time.strftime(pattern, time.localtime())
    logger.debug("当前时间：{}".format(now))
    return now
NOW_TIME = get_current_date("%Y-%m-%d %H:%M:%S")
NOW_DATE = get_current_date("%Y-%m-%d")

# 获取当前时间 年月日
def get_current_year_month_day():
    from datetime import datetime
    current_time = datetime.now()
    year = str(current_time.year)
    month = "{:02d}".format(current_time.month)
    day = "{:02d}".format(current_time.day)
    return year, month, day

def url_encode(url):
    from urllib.parse import quote
    return quote(url)

def url_decode(url):
    from urllib.parse import unquote
    return unquote(url)

def get(url, res_type='text'):
    import requests
    import random
    user_agent_list = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.15'
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
    ]
    headers = {
        'User-Agent': random.choice(user_agent_list)
    }
    response = requests.get(url, headers=headers, timeout=15, verify=False)
    response.raise_for_status()  # Raises HTTPError for bad responses
    assert response.status_code == 200
    if response.status_code == 200:
        return response.json() if res_type == 'json' else response.text
    else:
        return None


# 文件内容保存：text、md、html
def saveText(text: str, file_path: str):
    # logger.debug('text:%s', text)
    get_or_make_file_path(file_path)

    with open(file_path, mode='w') as f:
        f.write(text)
    logger.debug("文件保存地址:{}".format(file_path))
    return file_path

# json 文本保存
def saveJson(json_str: str, file_path: str):
    # logger.debug('jsonStr::%s', jsonStr)
    get_or_make_file_path(file_path)

    with open(file_path, 'w') as f:
        json.dump(json_str, f, indent=4, ensure_ascii=False)
    logger.debug("json文件保存地址:{}".format(file_path))
    return file_path

# csv 文本保存
def saveCsv(json_str: str, file_path: str):
    import pandas as pd
    from io import StringIO

    # logger.debug("jsonStr:{}".format(jsonStr))
    # df = pd.read_json(jsonStr)
    df = pd.read_json(StringIO(json_str))
    if os.path.exists(file_path): 
        # a = 追加模式, header=False 省略标题行
        df.to_csv(file_path, index=False, mode='a', header=False)
    else:
        get_or_make_file_path(file_path)
        df.to_csv(file_path, index=False)
    logger.debug("csv文件保存地址:{}".format(file_path))
    return file_path

# 判断文件目录是否存在, 不存在则创建目录路径
def get_or_make_file_path(file_path):
    dirname = os.path.dirname(file_path)
    if not os.path.exists(dirname): 
        os.makedirs(dirname) 
    return dirname

# 发送到 wx 微信不支持全部 html，支持部分标签
# def send_wx(html):
    # wx_push(html)

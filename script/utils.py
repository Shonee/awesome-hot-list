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

def url_encode(url):
    from urllib.parse import quote
    return quote(url)

def url_decode(url):
    from urllib.parse import unquote
    return unquote(url)

def get(url, res_type='text'):
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
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

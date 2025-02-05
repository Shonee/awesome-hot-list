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

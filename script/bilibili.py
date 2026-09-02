
import json
from bs4 import BeautifulSoup
import re
import os
from utils import logger,saveText,saveJson,saveCsv,get,url_encode, NOW_DATE,NOW_TIME

class Bilibili:
    def __init__(self):
        pass

    def get_bilibili_hot_search_words_api(self):
        url = 'https://app.bilibili.com/x/v2/search/trending/ranking'
        logger.debug('get_bilibili_hot_search_words_api: {}'.format(url))
        list = json.loads(get(url)).get("data", {}).get('list', [])
        # logger.debug("哔哩哔哩热门搜索 ：{}".format(json.dumps(video_list, ensure_ascii=False)))
        
        result = []
        for index, item in enumerate(list):
            json_data = {
                "index": index + 1,
                "title": item['keyword'],
                "desc": item['show_name'],
                "hot": '',
                "url": f'https://search.bilibili.com/all?keyword={url_encode(item["keyword"])}',
                "image": '',
                "source": "哔哩哔哩",
                "type": "热门搜索",
                "datetime": NOW_TIME
            }
            result.append(json_data)
        json_str = json.dumps(result, ensure_ascii=False)
        logger.debug("哔哩哔哩热门搜索 ：{}".format(json_str))
        return json_str

    def get_bilibili_hot_videos_api(self):
        url = 'https://api.bilibili.com/x/web-interface/popular?ps=50&pn=1'
        logger.debug('get_bilibili_hot_videos_api: {}'.format(url))
        video_list = json.loads(get(url)).get("data", {}).get('list', [])
        # logger.debug("哔哩哔哩全站热门视频 ：{}".format(json.dumps(video_list, ensure_ascii=False)))
        
        dict_list = []
        for index, video in enumerate(video_list):
            json_data = {
                "index": index + 1,
                "title": video['title'],
                "desc": video['desc'],
                "hot": video['stat']['view'],
                "url": video['short_link_v2'],
                "image": video['pic'],
                "createtime": video['pubdate'],
                "source": "哔哩哔哩",
                "type": "全站热门视频",
                "datetime": NOW_TIME
            }
            dict_list.append(json_data)
        json_str = json.dumps(dict_list, ensure_ascii=False)
        logger.debug("哔哩哔哩全站热门视频 ：{}".format(json_str))
        return json_str
    
    def get_bilibili_rank_videos_api(self):
        url = 'https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all'
        logger.debug('get_bilibili_rank_videos_api: {}'.format(url))
        video_list = json.loads(get(url)).get("data", {}).get('list', [])
        # logger.debug("哔哩哔哩视频排行榜 ：{}".format(json.dumps(video_list, ensure_ascii=False)))
        
        dict_list = []
        for index, video in enumerate(video_list):
            json_data = {
                "index": index + 1,
                "title": video['title'],
                "desc": video['desc'],
                "hot": video['stat']['view'],
                "url": video['short_link_v2'],
                "image": video['pic'],
                "createtime": video['pubdate'],
                "source": "哔哩哔哩",
                "type": "视频排行榜",
                "datetime": NOW_TIME
            }
            dict_list.append(json_data)
        json_str = json.dumps(dict_list, ensure_ascii=False)
        logger.debug("哔哩哔哩视频排行榜 ：{}".format(json_str))
        return json_str


    def parseData(self):
        url = r'https://www.bilibili.com/v/popular/rank/all'
        soup = BeautifulSoup(get(url), "html.parser")

        datalist = []
        for item in soup.find_all('li',class_="rank-item"):
            item = str(item)
            link = re.findall(re.compile(r'<a class="title" href="//(.*?)"'), item)[0]
            link_BV = re.findall(re.compile(r'<a href="//www.bilibili.com/video/(.*?)"'), item)[0]
            title = re.findall(re.compile(r'target="_blank">(.*?)</a>'), item)[1]  #第二条才是标题信息
            play = re.findall(re.compile(r'<i class="b-icon play"></i>(.*?)</span>',re.S), item)[0]
            play = re.sub(r"\n?","",play).strip()
            view = re.findall(re.compile(r'<i class="b-icon view"></i>(.*?)</span>',re.S), item)[0]
            view = re.sub(r'\n?',"",view).strip()
            datalist.append([link,link_BV,title,play,view])
        return datalist


def save_file():
    import time

    bilibili = Bilibili()
    rank_json_data = bilibili.get_bilibili_rank_videos_api()
    time.sleep(3)
    searches_json_data = bilibili.get_bilibili_hot_search_words_api()
    time.sleep(3)
    hot_json_data = bilibili.get_bilibili_hot_videos_api()
   
    uniform_json_data = json.dumps({'searches': json.loads(searches_json_data), 'hot': json.loads(hot_json_data), 'rank': json.loads(rank_json_data)}, ensure_ascii=False)
    generate_archive_json(uniform_json_data)
    generate_archive_csv(uniform_json_data)
    generate_archive_md(searches_json_data, hot_json_data, rank_json_data)


def generate_archive_json(json_str: str):
    file_path = os.path.join('archived/bilibili/json/', NOW_DATE +'.json')
    json_data = json.load(open(file_path)) if os.path.exists(file_path) else {}
    json_data[NOW_TIME] = json.loads(json_str)
    saveJson(json_data, file_path)

def generate_archive_csv(jsonStr: str):
    file_path = os.path.join('archived/bilibili/csv/', NOW_DATE +'.csv')
    data = json.loads(jsonStr)
    csv_list = []
    [csv_list.extend(item) for item in data.values()]
    saveCsv(json.dumps(csv_list, ensure_ascii=False), file_path)

def generate_archive_md(searches_json_data, hot_json_data, rank_json_data):
    # md = '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(jsonStr)])

    md = '# 哔哩哔哩热榜 | {NOW_DATE} \n\n'
    md += '记录哔哩哔哩的热门视频。每小时抓取一次数据，并历史记录[归档](https://github.com/Shonee/awesome-hot-list/tree/master/archived)。 \n\n'
    md += f"`更新时间：{NOW_TIME}` \n\n"

    md += '### 热门搜索 \n\n'
    md += '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(searches_json_data)])
    md += '\n\n'

    md += '### 热门视频 \n\n'
    md += '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(hot_json_data)])
    md += '\n\n'

    md += '### 视频排行榜 \n\n'
    md += '\n'.join(['{}. [{}]({})'.format(item["index"], item["title"], item["url"]) for item in json.loads(rank_json_data)])
    md += '\n\n'

    saveFile = os.path.join('archived/bilibili/md/', NOW_DATE +'.md')
    saveText(md, saveFile)

if __name__ == '__main__':
    
    # bilibili = Bilibili()
    # bilibili.get_bilibili_rank_videos_api()
    
    save_file()

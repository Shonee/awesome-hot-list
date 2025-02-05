import json
from enum import Enum
import os
import time
from utils import logger,saveText,saveJson,saveCsv, NOW_DATE,NOW_TIME

GITHUB_HOST = "https://github.com/"
GITHUB_TREDING_URL = "https://github.com/trending/{}?since={}"
# url = "https://github.com/trending/java?since=weekly"

class Since(Enum):
    daily = 'daily'
    weekly = 'weekly'
    monthly = 'monthly'

class Language(Enum):
    all = ''
    java = 'java'
    python = 'python'
    go = 'go'
    html = 'html'
    javascript = 'javascript'

def get(url):
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers, timeout=15, verify=False)
    assert response.status_code == 200
    if response.status_code == 200:
        return response.text
    else:
        return None

class GitHub:
    def get_github_trending_json(self, language=Language.all, date=Since.daily):
        from bs4 import BeautifulSoup
        url = GITHUB_TREDING_URL.format(language, date)
        logger.debug("github 趋势热榜 url ：{}".format(url))
        soup = BeautifulSoup(get(url), "html.parser")
        items = soup.find_all("article", class_="Box-row")

        projects = []
        for idx,one in enumerate(items):
            languageSpan = one.find("span", itemprop="programmingLanguage")
            language = languageSpan.text.strip() if languageSpan else ""
            projects.append({
                'index':idx+1,
                'title': one.h2.a["href"].split("/")[2],
                'desc': one.p.text.strip() if one.p else "",
                'author': [a.img["alt"][1:] for a in one.find("span",class_="d-inline-block mr-3").find_all("a", class_="d-inline-block")][0],
                'language': languageSpan.text.strip() if languageSpan else "",
                'stars': one.find_all("a", class_="Link Link--muted d-inline-block mr-3")[0].text.strip(),
                'forks': one.find_all("a", class_="Link Link--muted d-inline-block mr-3")[1].text.strip(),
                'today_forks': one.find("span", class_="d-inline-block float-sm-right").text.strip(),
                'url': GITHUB_HOST + one.h2.a["href"],
                'type': 'GitHub' + language + '_' + date,
                'datetime': NOW,
            })
        result = json.dumps(projects, ensure_ascii=False)
        # logger.debug("github 趋势热榜 page ：{}".format(result))
        return result

def save_file():
    github = GitHub()

    json_data = {}
    for since in Since:
        json_data[since.value] = json.loads(github.get_github_trending_json(Language.all.value, since.value))
        time.sleep(0.1)
    for language in Language:
        json_data[language.value] = json.loads(github.get_github_trending_json(language.value, Since.weekly.value))
        time.sleep(0.1)
    
    json_data_str = json.dumps(json_data, ensure_ascii=False)
    generate_archive_json(json_data_str)
    generate_archive_md(json_data_str)
    generate_archive_csv(json_data_str)

def generate_archive_json(githubTrendingJsonStr):
    file_path = os.path.join('archived/github/json/', NOW_DATE +'.json')
    json_data = json.load(open(file_path)) if os.path.exists(file_path) else {}
    json_data[NOW_TIME] = json.loads(githubTrendingJsonStr)
    saveJson(json_data, file_path)

def generate_md(json_str_data, title) -> str:
    from datetime import datetime, timedelta, timezone
    """生成Markdown内容并保存到data目录"""
    # logger.debug("data_list:{}".format(data_list))
    md = title
    for data in json.loads(json_str_data):
        logger.debug("data:{}".format(data))
        img_url = 'https://s0.wp.com/mshots/v1/{url}?w=600&h=450'.format(url=data['url'])
        item = (
            f"### [{data['index']}. {data['title']}]({data['url']}) \n\n"
            f"![{data.get('title')}]({img_url}) \n\n"
            f"**🔥名称**：{data['title']} \n\n"
            f"**🧑‍💻作者**：{data['author']} \n\n"
            f"**🎬描述**：{data['description']} \n\n"
            f"**🔗地址**: [立即访问]({data['url']}) \n\n"
            f"**👀语言**: 🔺{data['language']} \n\n"
            f"**⭐stars**：{data['stars']} \n\n"
            f"**📍forks**：{data['forks']} \n\n"
            f"--- \n\n"
        )
        md += item
    # logger.debug("归档md:{}".format(md))
    return md

def generate_archive_md(json_str_data):
    """Markdown内容并保存到data目录"""
    md = f"# GitHub 趋势热榜 | {NOW_DATE}\n\n"
    for key, value in json.loads(json_str_data).items():
        logger.debug("key:value {}:{}".format(key,value))
        md += generate_md(json.dumps(value), f"## {key} 热榜\n\n")

    # logger.debug("归档md:{}".format(md))
    saveFile = os.path.join('archived/github/md/', NOW_DATE +'.md')
    saveText(md, saveFile)

def generate_archive_csv(jsonStr: str):
    file_path = os.path.join('archived/github/csv/', NOW_DATE +'.csv')
    csv_list = []
    # [csv_list.append(item) for item in json.loads(jsonStr).values()] # 结果 [[1,2][3,4]]
    [csv_list.extend(item) for item in json.loads(jsonStr).values()]
    saveCsv(json.dumps(csv_list, ensure_ascii=False), file_path)


if __name__ == '__main__':
    save_file()

    




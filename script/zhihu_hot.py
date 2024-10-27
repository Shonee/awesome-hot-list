
def get(url):
    import requests 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.text
    else:
        return None

def get_current_date(pattern = "%Y-%m-%d"):
    import time
    return time.strftime(pattern, time.localtime())

# json 转 csv
def json_to_csv_pandas(json_data, file_path = '../data/zhihu_hot.csv'):
    import os
    import pandas as pd

    df = pd.read_json(json_data)
    if os.path.exists(file_path): 
        df.to_csv(file_path, index=False, mode='a', header=False)
    else:
        df.to_csv(file_path, index=False)
    return True

# 使用 requests 请求知乎 api 数据
def get_zhihu_hot_json_by_api():
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=100"
    
    responseData = json.loads(get(url)).get("data")
    result = []
    # 打印热搜榜单的标题和热度
    for index, item in enumerate(responseData):
        id = item.get("target").get("id")
        title = item.get("target").get("title")
        desc = item.get("target").get("excerpt")
        created = item.get("target").get("created")
        url = "https://www.zhihu.com/question/"+ str(id)
        hot = item.get("detail_text")
        children = item.get('children')
        if children:
            answer_img = children[0].get('thumbnail')
    
        result.append({
            'datetime': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "index": index+1,
            'id': id,
            "type": "知乎热榜",
            "title": title,
            "desc": desc,
            "hot": hot,
            "createtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created)),
            "url": url,
            'img': answer_img
        })
    return json.dumps(result, ensure_ascii=False)

if __name__ == '__main__':
    result = get_zhihu_hot_json_by_api()
    print(result)
    date = get_current_date('%Y-%m')
    json_to_csv_pandas(result, '/data/csv/zhihu_hot_' + date + '.csv')


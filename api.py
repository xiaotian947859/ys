from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import List, Optional
from pydantic import BaseModel
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import re
import base64
from urllib.parse import quote
import time
import os

app = FastAPI(
    title="影视磁力搜索API",
    description="提供影视作品搜索和磁力链接获取服务",
    version="1.0.0"
)

# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 设置模板目录为当前目录下的templates
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

# 配置
CONFIG = {
    'delay': 1,  # Delay between requests in seconds
    'timeout': 10,  # Request timeout in seconds
}

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

class MagnetLink(BaseModel):
    filename: str
    size: str
    version: str
    url: str

class MovieDetail(BaseModel):
    title: str
    year: Optional[str]
    category: Optional[str]
    score: Optional[str]
    imdb_score: Optional[str]
    image: Optional[str]
    magnet_links: Optional[List[MagnetLink]]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def get_magnet_links(session: aiohttp.ClientSession, play_url: str) -> List[dict]:
    try:
        video_id = play_url.split('r?')[-1]
        if not video_id:
            return []
            
        api_url = f"https://www.bdjuhe.com/api/rl?id={video_id}"
        headers = {
            **HEADERS,
            "Origin": "https://res.bdjuhe.com",
            "Referer": "https://res.bdjuhe.com/",
        }
        
        async with session.post(api_url, headers=headers, timeout=CONFIG['timeout']) as response:
            json_data = await response.json()
            if not json_data.get("data"):
                return []
                
            decoded_data = base64.b64decode(json_data["data"]).decode('utf-8')
            magnet_data = json.loads(decoded_data)
            
            magnet_links = []
            for item in magnet_data:
                if item.get("type") == "magnet":
                    # 确保size是字符串类型
                    size = item.get('size', '未知')
                    if isinstance(size, (int, float)):
                        size = f"{size}MB"
                    magnet_info = {
                        "filename": item['filename'],
                        "size": size,
                        "version": item.get('version', '未知'),
                        "url": item['url']
                    }
                    magnet_links.append(magnet_info)
                    
            return magnet_links
            
    except Exception as e:
        print(f"获取磁力链接失败: {str(e)}")
        return []

async def get_movie_details(session: aiohttp.ClientSession, url: str, title: str = '') -> Optional[dict]:
    try:
        async with session.get(url, timeout=CONFIG['timeout']) as response:
            text = await response.text()
            soup = BeautifulSoup(text, 'html.parser')
            
            info = {'title': title, 'link': url}
            movie_id = url.split('/')[-1]
            info['id'] = movie_id
            
            # 获取字幕信息
            subtitle = soup.select_one('.subtitle')
            if subtitle:
                subtitle_text = subtitle.text.strip()
                match = re.match(r'(\d{4})(.*)', subtitle_text)
                if match:
                    info['year'] = match.group(1)
                    info['category'] = match.group(2).strip()
            
            # 获取评分
            scores = soup.select('.score')
            if len(scores) > 0:
                info['score'] = scores[0].text.strip()
            if len(scores) > 1:
                info['imdb_score'] = scores[1].text.strip()
                
            # 获取播放链接
            res_script = soup.select_one('script:-soup-contains("res.bdjuhe.com")')
            if res_script:
                match = re.search(r"'(https://res\.bdjuhe\.com/r\?[^']+)'", res_script.text)
                if match:
                    play_url = match.group(1)
                    info['play_url'] = play_url
                    magnet_links = await get_magnet_links(session, play_url)
                    if magnet_links:
                        info['magnet_links'] = magnet_links
            
            # 获取图片链接
            img = None
            for selector in ['.videopic img', '.detail-pic img', '.pic img', 'a.video-pic img']:
                img = soup.select_one(selector)
                if img:
                    break
                    
            if img:
                img_url = None
                for attr in ['data-src', 'data-original', 'src']:
                    img_url = img.get(attr, '')
                    if img_url:
                        break
                        
                if img_url:
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif not img_url.startswith(('http://', 'https://')):
                        img_url = 'https://www.bdjuhe.com' + ('' if img_url.startswith('/') else '/') + img_url
                    info['image'] = img_url
            
            return info
            
    except Exception as e:
        print(f"获取电影详情失败: {title} - {str(e)}")
        return None

@app.get("/api/search", response_model=List[MovieDetail])
async def search_movies(keyword: str, page: int = 1):
    """
    搜索影视作品
    
    - **keyword**: 搜索关键词
    - **page**: 页码，默认为1
    """
    try:
        encoded_keyword = quote(keyword)
        url = f"https://www.bdjuhe.com/q/index-----{page}?k={encoded_keyword}"
        
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=CONFIG['timeout']) as response:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                
                items = soup.select('.list-item')
                if not items:
                    return []
                
                movies = []
                for item in items:
                    try:
                        a_tag = item.select_one('a')
                        if not a_tag:
                            continue
                            
                        link = a_tag.get('href', '')
                        if not link:
                            continue
                            
                        if not link.startswith('http'):
                            link = 'https://www.bdjuhe.com' + link
                        
                        title = a_tag.get('title', '') or a_tag.text.strip()
                        if not title:
                            title = keyword
                            
                        details = await get_movie_details(session, link, title)
                        if details:
                            movies.append(details)
                            
                        await asyncio.sleep(CONFIG['delay'])
                        
                    except Exception as e:
                        print(f"处理影片时出错: {str(e)}")
                        continue
                
                return movies
                
    except Exception as e:
        print(f"搜索失败: {str(e)}")
        return []

# 仅在直接运行时启动服务器
if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=5000, reload=True) 
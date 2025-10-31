# -*- coding: utf-8 -*-
# webpussi.com 视频爬虫 - 修复播放链接版
import sys
sys.path.append('..')
from base.spider import Spider
from bs4 import BeautifulSoup
import requests
import re
import json
import urllib.parse
import time
import random

class Spider(Spider):

    def init(self, extend=""):
        self.host = "https://www.webpussi.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1'
        }

    def getName(self):
        return "webpussi.com"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def get_html(self, url):
        """获取网页HTML内容"""
        try:
            res = requests.get(url, headers=self.headers, timeout=15, allow_redirects=True)
            res.encoding = 'utf-8'
            return res.text
        except Exception as e:
            print(f"获取 {url} 失败: {str(e)}")
            return ""

    def homeContent(self, filter):
        """首页分类和筛选器配置"""
        classes = [
            {"type_name": "最新更新", "type_id": "latest-updates"},
            {"type_name": "最受欢迎", "type_id": "most-popular"},
            {"type_name": "最高评分", "type_id": "top-rated"}
        ]
        
        filters = {
            "latest-updates": [
                {"key": "by", "name": "排序", "value": [
                    {"n": "发布时间", "v": "post_date"},
                    {"n": "最受欢迎", "v": "video_viewed"},
                    {"n": "最高评分", "v": "rating"}
                ]}
            ],
            "most-popular": [
                {"key": "by", "name": "时间范围", "value": [
                    {"n": "全部时间", "v": ""},
                    {"n": "今天", "v": "today"},
                    {"n": "本周", "v": "week"},
                    {"n": "本月", "v": "month"}
                ]}
            ],
            "top-rated": [
                {"key": "by", "name": "时间范围", "value": [
                    {"n": "全部时间", "v": ""},
                    {"n": "今天", "v": "today"},
                    {"n": "本周", "v": "week"},
                    {"n": "本月", "v": "month"}
                ]}
            ]
        }
        
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        """首页推荐视频"""
        try:
            html = self.get_html(self.host)
            return self.parse_video_list(html)
        except Exception as e:
            print(f"[HOME] 错误: {e}")
            return {'list': []}

    def parse_video_list(self, html):
        """解析视频列表（通用方法）"""
        soup = BeautifulSoup(html, "html.parser")
        videos = []
        
        # 多种可能的选择器
        video_items = (soup.select('.item') or 
                      soup.select('.video-item') or 
                      soup.select('.thumb') or
                      soup.select('[class*="item"]'))
        
        for item in video_items:
            try:
                # 查找链接
                link_elem = (item.select_one('a[href*="/videos/"]') or 
                           item.select_one('a[href*="/video/"]') or
                           item.find('a', href=re.compile(r'/videos?/\d+/')))
                
                if not link_elem:
                    continue
                
                link = link_elem.get('href', '')
                if not link.startswith('http'):
                    link = self.host + link
                
                # 提取视频ID
                vid_match = re.search(r'/videos?/(\d+)/', link)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                
                # 标题
                title_elem = (item.select_one('.title') or 
                            item.select_one('strong.title') or 
                            item.select_one('[class*="title"]') or
                            item.select_one('a') or
                            link_elem)
                title = title_elem.get_text(strip=True) if title_elem else '未知'
                
                # 图片
                img_elem = item.select_one('img')
                img = ''
                if img_elem:
                    img = (img_elem.get('data-original') or 
                          img_elem.get('data-src') or 
                          img_elem.get('src', ''))
                    if img and not img.startswith('http'):
                        img = self.host + img
                
                # 时长
                duration_elem = (item.select_one('.duration') or 
                               item.select_one('[class*="duration"]'))
                duration = duration_elem.get_text(strip=True) if duration_elem else ''
                
                # 评分
                rating_elem = (item.select_one('.rating') or 
                             item.select_one('[class*="rating"]'))
                rating = rating_elem.get_text(strip=True) if rating_elem else ''
                
                # 观看次数
                views_elem = (item.select_one('.views') or 
                            item.select_one('[class*="views"]'))
                views = views_elem.get_text(strip=True) if views_elem else ''
                
                # 备注信息
                remark_parts
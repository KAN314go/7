# -*- coding: utf-8 -*-
import re
import urllib.parse
import requests

class Spider:
    def __init__(self):
        self.name = '玩物社区'
        self.host = 'https://wanwuu.com/'
        self.default_pic = 'https://via.placeholder.com/400x225?text=Video'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S901U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': self.host,
        }
        self.classes = []
        category_str = "国产SM$guochan-sm#日韩SM$rihan-sm#欧美SM$oumei-sm#直播回放$zhibo-huifang#SM小说$novels/new#玩物社区$posts/all"
        for item in category_str.split('#'):
            if '$' in item:
                name, path = item.split('$')
                self.classes.append({"type_name": name, "type_id": path})

    # 框架接口
    def getDependence(self): return []
    def init(self, extend=""): pass
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): pass
    def getName(self): return self.name
    def homeContent(self, filter): return {"class": self.classes}
    def homeVideoContent(self): return self.categoryContent("guochan-sm", "1", False, {})

    # 列表解析 - 修复图片获取
    def _parse_videos(self, html):
        """提取视频列表，优先使用 data-src 懒加载图片"""
        videos = []
        pattern = r'<div class="video-item"[^>]*>(.*?)</div>\s*</div>'
        
        for block in re.findall(pattern, html, re.S):
            # 链接
            href_match = re.search(r'href="([^"]+)"', block)
            if not href_match or '/videos/' not in href_match.group(1):
                continue
            href = href_match.group(1)
            
            # 标题
            title = ""
            for t_pattern in [r'alt="([^"]+)"', r'title="([^"]+)"', r'<a[^>]*>\s*([^<]+)\s*</a>']:
                t_match = re.search(t_pattern, block)
                if t_match:
                    title = t_match.group(1).strip()
                    break
            
            if not title:
                continue
            
            # 图片 - 优先懒加载属性
            pic = ""
            for p_pattern in [r'data-src="([^"]+)"', r'data-lazy-src="([^"]+)"', r'lazy-src="([^"]+)"', r'src="([^"]+)"']:
                p_match = re.search(p_pattern, block)
                if p_match:
                    pic_url = p_match.group(1)
                    if pic_url and 'blob:' not in pic_url and 'poster_loading' not in pic_url:
                        pic = pic_url
                        break
            
            # 时长
            remark = ""
            r_match = re.search(r'>(\d{1,2}:\d{2}(?::\d{2})?)<', block)
            if r_match:
                remark = r_match.group(1)
            
            videos.append({
                "vod_id": self._abs(href),
                "vod_name": self.clean_title(title),
                "vod_pic": self._abs(pic) if pic else self.default_pic,
                "vod_remarks": remark
            })
        
        return videos

    # 分类 - 修复翻页 URL 格式
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
            # 使用 /page/N/ 格式
            if tid in ("novels/new", "posts/all"):
                url = f"{self.host}{tid}/page/{pg}/" if pg > 1 else f"{self.host}{tid}/"
            else:
                url = f"{self.host}videos/{tid}/page/{pg}/" if pg > 1 else f"{self.host}videos/{tid}/"
            
            r = requests.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            videos = self._parse_videos(r.text)
            return self._page(videos, pg)
        except Exception as e:
            print(f"分类失败: {e}")
            return self._page([], pg)

    # 搜索 - 修复翻页
    def searchContent(self, key, quick, pg='1'):
        try:
            pg = int(pg)
            wd = urllib.parse.quote(key)
            url = f"{self.host}videos/search/{wd}/page/{pg}/" if pg > 1 else f"{self.host}videos/search/{wd}/"
            
            r = requests.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            videos = self._parse_videos(r.text)
            return self._page(videos, pg)
        except Exception as e:
            print(f"搜索失败: {e}")
            return self._page([], pg)
    # 详情 - 只返回嗅探链接
    def detailContent(self, array):
        vid = array[0] if array[0].startswith('http') else self._abs(array[0])
        try:
            r = requests.get(vid, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            html = r.text

            # 提取标题
            title = ""
            title_match = re.search(r'<title>(.*?)</title>', html, re.I)
            if title_match:
                title = re.split(r'[-—_]', title_match.group(1))[0].strip()
            
            # 提取图片
            pic = ""
            for pic_pattern in [
                r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"',
                r'<video[^>]*poster="([^"]+)"',
                r'data-poster="([^"]+)"'
            ]:
                pic_match = re.search(pic_pattern, html, re.I)
                if pic_match and 'blob:' not in pic_match.group(1):
                    pic = pic_match.group(1)
                    break
            
            # 提取描述
            desc = ""
            desc_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
            if desc_match:
                desc = desc_match.group(1)
            
            # 只使用嗅探模式 - 返回 video:// 前缀的播放页链接
            play_url = f"video://{vid}"
            
            vod = {
                "vod_id": vid,
                "vod_name": self.clean_title(title) if title else "视频",
                "vod_pic": self._abs(pic) if pic else self.default_pic,
                "vod_content": self.clean_title(desc) if desc else title,
                "vod_play_from": self.name,
                "vod_play_url": f"{self.clean_title(title) if title else '播放'}${play_url}"
            }
            return {"list": [vod]}
        except Exception as e:
            print(f"详情失败: {e}")
            return {"list": []}

    # 播放器配置 - 支持嗅探模式
    def playerContent(self, flag, id, vipFlags):
        """返回 video:// 前缀的链接，由播放器自动嗅探"""
        return {
            "parse": 0, 
            "playUrl": "", 
            "url": id,  # 直接返回 video:// 链接
            "header": self.headers
        }

    # 工具函数
    def _abs(self, url):
        """转换相对路径为绝对路径"""
        if not url or url.startswith('blob:'):
            return self.default_pic
        if url.startswith('//'):
            return 'https:' + url
        return url if url.startswith('http') else urllib.parse.urljoin(self.host, url)

    def _page(self, videos, pg):
        """返回分页数据"""
        return {
            "list": videos, 
            "page": int(pg), 
            "pagecount": 9999, 
            "limit": 30, 
            "total": 999999
        }

    def clean_title(self, title):
        """清理标题"""
        if not title:
            return ""
        # 移除HTML标签
        title = re.sub(r'<[^>]+>', '', title)
        # 合并多余空格
        title = re.sub(r'\s+', ' ', title)
        return title.strip()

    # 框架配置
    config = {"player": {}, "filter": {}}
    header = property(lambda self: self.headers)
    
    def localProxy(self, param):
        return []

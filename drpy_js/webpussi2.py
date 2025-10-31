# -*- coding: utf-8 -*-
# webpussi.com 视频爬虫 - 终极播放修复版
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
                remark_parts = []
                if duration:
                    remark_parts.append(duration)
                if rating:
                    remark_parts.append(f"评分{rating}")
                if views:
                    remark_parts.append(f"{views}次观看")
                remark = ' | '.join(remark_parts)
                
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': img,
                    'vod_remarks': remark
                })
                
            except Exception as e:
                print(f"解析视频项失败: {e}")
                continue
        
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容列表"""
        try:
            # 构建分类URL
            if tid == "latest-updates":
                url = f"{self.host}/latest-updates/{pg}/" if int(pg) > 1 else f"{self.host}/latest-updates/"
            elif tid == "most-popular":
                url = f"{self.host}/most-popular/{pg}/" if int(pg) > 1 else f"{self.host}/most-popular/"
            elif tid == "top-rated":
                url = f"{self.host}/top-rated/{pg}/" if int(pg) > 1 else f"{self.host}/top-rated/"
            else:
                url = f"{self.host}/{tid}/{pg}/" if int(pg) > 1 else f"{self.host}/{tid}/"
            
            print(f"[CATEGORY] URL: {url}")
            html = self.get_html(url)
            result = self.parse_video_list(html)
            
            # 分页处理
            soup = BeautifulSoup(html, "html.parser")
            pagecount = int(pg)
            
            try:
                pagination = (soup.select_one('.pagination') or 
                            soup.select_one('[class*="pagination"]') or
                            soup.select_one('.pages'))
                
                if pagination:
                    # 查找最后一页
                    page_links = pagination.select('a[href]')
                    page_numbers = []
                    
                    for link in page_links:
                        href = link.get('href', '')
                        pg_match = re.search(r'/(\d+)/?$', href)
                        if pg_match:
                            page_num = int(pg_match.group(1))
                            page_numbers.append(page_num)
                    
                    if page_numbers:
                        pagecount = max(page_numbers)
                    else:
                        # 尝试从当前页推断
                        current_page = pagination.select_one('.current, .active')
                        if current_page:
                            current_text = current_page.get_text(strip=True)
                            if current_text.isdigit():
                                pagecount = max(int(current_text), pagecount)
            
            except Exception as e:
                print(f"[CATEGORY] 分页解析失败: {e}")
            
            result.update({
                'page': pg,
                'pagecount': pagecount,
                'limit': 48,
                'total': 99999
            })
            
            return result
            
        except Exception as e:
            print(f"[CATEGORY] 错误: {e}")
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 48, 'total': 0}

    def detailContent(self, ids):
        """视频详情页"""
        try:
            vid = ids[0]
            detail_url = f"{self.host}/videos/{vid}/"
            print(f"[DETAIL] 尝试详情页: {detail_url}")
            html = self.get_html(detail_url)
            
            if not html or "Not Found" in html or "404" in html:
                print(f"[DETAIL] 详情页无效，尝试备用方案")
                return self.fallback_detail(vid)
            
            soup = BeautifulSoup(html, "html.parser")
            
            # 标题
            title = '未知视频'
            title_elem = (soup.select_one('h1.title') or 
                         soup.select_one('h1') or 
                         soup.select_one('.video-title') or
                         soup.select_one('title'))
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # 图片
            pic = ''
            pic_elem = (soup.select_one('meta[property="og:image"]') or 
                       soup.select_one('.fp-poster img') or 
                       soup.select_one('.video-player img') or
                       soup.select_one('img[data-original*="screenshots"]') or
                       soup.select_one('img[src*="screenshots"]'))
            
            if pic_elem:
                if pic_elem.name == 'meta':
                    pic = pic_elem.get('content', '')
                else:
                    pic = (pic_elem.get('data-original') or 
                          pic_elem.get('src', '') or 
                          pic_elem.get('srcset', '').split(',')[0].strip() if pic_elem.get('srcset') else '')
            
            if pic and not pic.startswith('http'):
                pic = self.host + pic
            
            # 描述
            desc = ''
            desc_elem = (soup.select_one('meta[name="description"]') or 
                        soup.select_one('meta[property="og:description"]') or
                        soup.select_one('.description') or
                        soup.select_one('[class*="desc"]'))
            
            if desc_elem:
                if desc_elem.name == 'meta':
                    desc = desc_elem.get('content', '')[:500]
                else:
                    desc = desc_elem.get_text(strip=True)[:500]
            
            # 演员
            actor_list = []
            actor_elems = (soup.select('a[href*="/models/"]') or 
                          soup.select('a[href*="/model/"]') or
                          soup.select('.models a') or
                          soup.select('.item:contains("Models") a'))
            
            for actor_elem in actor_elems[:5]:
                actor_name = actor_elem.get_text(strip=True)
                if actor_name and len(actor_name) > 1 and actor_name not in actor_list:
                    actor_list.append(actor_name)
            actor = '/'.join(actor_list) if actor_list else ''
            
            # 分类/站点
            director = ''
            site_elem = (soup.select_one('a[href*="/categories/"]') or 
                        soup.select_one('a[href*="/site/"]') or
                        soup.select_one('.site-name') or
                        soup.select_one('.categories a'))
            if site_elem:
                director = site_elem.get_text(strip=True)
            
            # 时长和观看次数
            duration = ''
            views = ''
            
            # 查找信息项
            info_items = soup.select('.item, .info-item, [class*="info"]')
            for item in info_items:
                text = item.get_text(strip=True)
                if 'Duration' in text or '时长' in text:
                    duration_elem = item.select_one('em, span, strong')
                    if duration_elem:
                        duration = duration_elem.get_text(strip=True)
                elif 'Views' in text or '观看' in text:
                    views_elem = item.select_one('em, span, strong')
                    if views_elem:
                        views = views_elem.get_text(strip=True)
            
            remarks = f"{duration} | {views}次观看" if duration or views else ''
            
            # 播放信息
            play_from_list = ['默认播放']
            play_url_list = [f"播放${vid}"]
            
            vod_info = {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remarks,
                'vod_content': desc,
                'vod_director': director,
                'vod_actor': actor,
                'vod_play_from': '$$$'.join(play_from_list),
                'vod_play_url': '$$$'.join(play_url_list)
            }
            
            print(f"[DETAIL] 成功解析: {title} (ID: {vid})")
            return {'list': [vod_info]}
            
        except Exception as e:
            print(f"[DETAIL] 错误: {e}")
            import traceback
            traceback.print_exc()
            return self.fallback_detail(ids[0])
    
    def fallback_detail(self, vid):
        """备用详情信息"""
        return {'list': [{
            'vod_id': vid,
            'vod_name': f'视频 {vid}',
            'vod_pic': '',
            'vod_remarks': '',
            'vod_content': '',
            'vod_director': '',
            'vod_actor': '',
            'vod_play_from': '默认播放',
            'vod_play_url': f'播放${vid}'
        }]}

    def extract_all_video_urls(self, html, vid):
        """全面提取视频URL - 终极版本"""
        print(f"[EXTRACT] 开始全面提取视频链接 for vid {vid}")
        
        all_urls = []
        
        # 策略1: 直接搜索所有可能的视频URL
        video_patterns = [
            # MP4文件
            r'(https?://[^"\'\s<>]+?\.mp4[^"\'\s<>]*)',
            r'["\'](https?://[^"\']+?\.mp4(?:\?[^"\']*)?)["\']',
            r'src\s*[:=]\s*["\'](https?://[^"\']+?\.mp4)["\']',
            r'file\s*[:=]\s*["\'](https?://[^"\']+?\.mp4)["\']',
            r'video_url\s*[:=]\s*["\'](https?://[^"\']+?\.mp4)["\']',
            
            # get_file路径
            r'(https?://[^"\'\s<>]+?/get_file/[^"\'\s<>]+?\.mp4[^"\'\s<>]*)',
            r'["\'](https?://[^"\']+?/get_file/[^"\']+?\.mp4)["\']',
            r'(/get_file/[^"\'\s<>]+?\.mp4[^"\'\s<>]*)',
            
            # M3U8文件
            r'(https?://[^"\'\s<>]+?\.m3u8[^"\'\s<>]*)',
            r'["\'](https?://[^"\']+?\.m3u8)["\']',
            r'src\s*[:=]\s*["\'](https?://[^"\']+?\.m3u8)["\']',
            
            # 相对路径
            r'src\s*[:=]\s*["\'](/[^"\']+?\.mp4)["\']',
            r'file\s*[:=]\s*["\'](/[^"\']+?\.mp4)["\']',
        ]
        
        for pattern in video_patterns:
            try:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for url in matches:
                    if url and len(url) > 10:
                        # 清理URL
                        clean_url = re.sub(r'[\\"\'<>]', '', url)
                        if clean_url.startswith('//'):
                            clean_url = 'https:' + clean_url
                        elif clean_url.startswith('/'):
                            clean_url = self.host + clean_url
                        
                        if clean_url not in all_urls:
                            all_urls.append(clean_url)
                            print(f"[EXTRACT] 找到URL: {clean_url}")
            except Exception as e:
                print(f"[EXTRACT] 模式匹配错误: {e}")
        
        # 策略2: 从JavaScript变量中提取
        js_patterns = [
            r'flashvars\s*=\s*({[^}]+})',
            r'video_url\s*=\s*["\']([^"\']+)["\']',
            r'file\s*=\s*["\']([^"\']+)["\']',
            r'src\s*:\s*["\']([^"\']+)["\']',
            r'url\s*:\s*["\']([^"\']+)["\']',
            r'videoUrl\s*=\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in js_patterns:
            try:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    # 如果是JSON对象
                    if match.startswith('{'):
                        try:
                            data = json.loads(match)
                            if 'url' in data:
                                url = data['url']
                                if url.startswith('/'):
                                    url = self.host + url
                                if url not in all_urls:
                                    all_urls.append(url)
                            if 'file' in data:
                                url = data['file']
                                if url.startswith('/'):
                                    url = self.host + url
                                if url not in all_urls:
                                    all_urls.append(url)
                        except:
                            pass
                    else:
                        # 直接URL
                        url = match
                        if url.startswith('/'):
                            url = self.host + url
                        if url not in all_urls:
                            all_urls.append(url)
            except Exception as e:
                print(f"[EXTRACT] JS提取错误: {e}")
        
        # 策略3: 从HTML属性中提取
        attr_patterns = [
            r'data-url\s*=\s*["\']([^"\']+)["\']',
            r'data-file\s*=\s*["\']([^"\']+)["\']',
            r'data-src\s*=\s*["\']([^"\']+)["\']',
            r'data-video\s*=\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in attr_patterns:
            try:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for url in matches:
                    if url.startswith('/'):
                        url = self.host + url
                    if url not in all_urls:
                        all_urls.append(url)
            except Exception as e:
                print(f"[EXTRACT] 属性提取错误: {e}")
        
        # 去重和过滤
        filtered_urls = []
        for url in all_urls:
            if any(ext in url.lower() for ext in ['.mp4', '.m3u8', 'get_file']):
                # 移除不必要的参数
                clean_url = re.sub(r'\\[^/]', '', url)  # 移除转义字符
                if clean_url not in filtered_urls:
                    filtered_urls.append(clean_url)
        
        print(f"[EXTRACT] 总共找到 {len(filtered_urls)} 个有效URL")
        
        # 优先级排序: MP4 > M3U8, 完整URL > 相对路径
        mp4_urls = [u for u in filtered_urls if '.mp4' in u]
        m3u8_urls = [u for u in filtered_urls if '.m3u8' in u]
        
        if mp4_urls:
            return mp4_urls[0]  # 返回第一个MP4链接
        elif m3u8_urls:
            return m3u8_urls[0]  # 返回第一个M3U8链接
        elif filtered_urls:
            return filtered_urls[0]  # 返回第一个有效链接
        
        return None

    def searchContent(self, key, quick, pg="1"):
        """搜索功能"""
        try:
            encoded_key = urllib.parse.quote(key)
            
            if pg == "1":
                url = f"{self.host}/search/?q={encoded_key}"
            else:
                url = f"{self.host}/search/{pg}/?q={encoded_key}"
            
            print(f"[SEARCH] URL: {url}")
            html = self.get_html(url)
            
            if not html:
                return {'list': []}
            
            result = self.parse_video_list(html)
            
            # 简单分页处理
            pagecount = int(pg)
            if len(result['list']) >= 48:  # 如果有足够的结果，假设还有更多页
                pagecount = int(pg) + 5
            
            result.update({
                'page': pg,
                'pagecount': pagecount,
                'limit': 48,
                'total': 99999
            })
            
            return result
            
        except Exception as e:
            print(f"[SEARCH] 搜索失败: {e}")
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        """播放链接解析 - 终极修复版"""
        try:
            vid = id
            print(f"[PLAYER] 开始处理视频 {vid}")
            
            # 策略1: 优先尝试embed页面
            embed_url = f"{self.host}/embed/{vid}"
            print(f"[PLAYER] 尝试embed页: {embed_url}")
            
            embed_headers = self.headers.copy()
            embed_headers.update({
                'Referer': f"{self.host}/",
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            })
            
            embed_html = self.get_html(embed_url)
            video_url = None
            
            if embed_html and len(embed_html) > 500:
                print(f"[PLAYER] Embed页获取成功，长度: {len(embed_html)}")
                video_url = self.extract_all_video_urls(embed_html, vid)
                if video_url:
                    print(f"[PLAYER] 从embed页成功提取: {video_url}")
            
            # 策略2: 如果embed页失败，尝试详情页
            if not video_url:
                detail_url = f"{self.host}/videos/{vid}/"
                print(f"[PLAYER] 尝试详情页: {detail_url}")
                detail_html = self.get_html(detail_url)
                if detail_html and len(detail_html) > 1000:
                    print(f"[PLAYER] 详情页获取成功，长度: {len(detail_html)}")
                    video_url = self.extract_all_video_urls(detail_html, vid)
                    if video_url:
                        print(f"[PLAYER] 从详情页成功提取: {video_url}")
            
            # 策略3: 如果还是失败，尝试API接口
            if not video_url:
                api_url = f"{self.host}/api/video/{vid}"
                print(f"[PLAYER] 尝试API接口: {api_url}")
                try:
                    api_response = requests.get(api_url, headers=self.headers, timeout=10)
                    if api_response.status_code == 200:
                        api_data = api_response.json()
                        if 'url' in api_data:
                            video_url = api_data['url']
                            print(f"[PLAYER] 从API成功获取: {video_url}")
                except:
                    pass
            
            if video_url:
                # 确保URL完整
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                elif video_url.startswith('/'):
                    video_url = self.host + video_url
                
                # 添加时间戳避免缓存
                if '?' in video_url:
                    video_url += f"&_t={int(time.time())}"
                else:
                    video_url += f"?_t={int(time.time())}"
                
                print(f"[PLAYER] 最终播放URL: {video_url}")
                
                return {
                    "parse": 0,  # 直接播放
                    "url": video_url,
                    "header": {
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': embed_url,
                        'Origin': self.host,
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Range': 'bytes=0-'
                    }
                }
            else:
                print(f"[PLAYER] 所有提取策略都失败，返回embed页进行解析")
                # 返回embed页让播放器自行处理
                return {
                    "parse": 1,  # 让播放器解析
                    "url": embed_url,
                    "header": embed_headers
                }
                
        except Exception as e:
            print(f"[PLAYER] 严重错误: {e}")
            import traceback
            traceback.print_exc()
            
            # 最后的备用方案
            embed_url = f"{self.host}/embed/{id}"
            return {
                "parse": 1,
                "url": embed_url,
                "header": self.headers
            }

    def localProxy(self, param):
        """本地代理"""
        return []
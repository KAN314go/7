 # -*- coding: utf-8 -*-
# webpussi.com 视频爬虫 - 播放链接修复版
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
        
        video_items = soup.select('.item')
        
        for item in video_items:
            try:
                link_elem = item.select_one('a[href*="/videos/"]')
                if not link_elem:
                    continue
                
                link = link_elem.get('href', '')
                if not link.startswith('http'):
                    link = self.host + link
                
                vid_match = re.search(r'/videos/(\d+)/', link)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                
                title_elem = item.select_one('.title, strong.title')
                title = title_elem.get_text(strip=True) if title_elem else '未知'
                
                img_elem = item.select_one('img')
                img = ''
                if img_elem:
                    img = img_elem.get('data-original') or img_elem.get('src', '')
                
                duration_elem = item.select_one('.duration')
                duration = duration_elem.get_text(strip=True) if duration_elem else ''
                
                rating_elem = item.select_one('.rating')
                rating = rating_elem.get_text(strip=True) if rating_elem else ''
                
                views_elem = item.select_one('.views')
                views = views_elem.get_text(strip=True) if views_elem else ''
                
                remark_parts = []
                if duration:
                    remark_parts.append(duration)
                if rating:
                    remark_parts.append(rating)
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
            if tid == "latest-updates":
                url = f"{self.host}/latest-updates/{pg}/" if int(pg) > 1 else f"{self.host}/latest-updates/"
            elif tid == "most-popular":
                url = f"{self.host}/most-popular/{pg}/" if int(pg) > 1 else f"{self.host}/most-popular/"
            elif tid == "top-rated":
                url = f"{self.host}/top-rated/{pg}/" if int(pg) > 1 else f"{self.host}/top-rated/"
            elif tid == "categories":
                url = f"{self.host}/categories/{pg}/" if int(pg) > 1 else f"{self.host}/categories/"
            elif tid == "sites":
                url = f"{self.host}/sites/{pg}/" if int(pg) > 1 else f"{self.host}/sites/"
            elif tid == "models":
                url = f"{self.host}/models/{pg}/" if int(pg) > 1 else f"{self.host}/models/"
            else:
                url = f"{self.host}/{tid}/{pg}/" if int(pg) > 1 else f"{self.host}/{tid}/"
            
            print(f"[CATEGORY] URL: {url}")
            html = self.get_html(url)
            result = self.parse_video_list(html)
            
            soup = BeautifulSoup(html, "html.parser")
            pagecount = int(pg)
            
            try:
                pagination = soup.select_one('.pagination')
                if pagination:
                    last_link = pagination.find('a', text=re.compile('Last|最后'))
                    if last_link:
                        last_href = last_link.get('href', '')
                        last_pg_match = re.search(r'/(\d+)/?$', last_href)
                        if last_pg_match:
                            pagecount = int(last_pg_match.group(1))
                    else:
                        page_links = pagination.select('a[href]')
                        for link in reversed(page_links):
                            href = link.get('href', '')
                            pg_match = re.search(r'/(\d+)/?$', href)
                            if pg_match:
                                potential_pg = int(pg_match.group(1))
                                if potential_pg > pagecount:
                                    pagecount = potential_pg
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
            
            soup = BeautifulSoup(html, "html.parser")
            
            if "Not Found" in html or "404" in html or len(html) < 1000:
                print(f"[DETAIL] 详情页无效，尝试embed页")
                embed_url = f"{self.host}/embed/{vid}"
                html = self.get_html(embed_url)
                if not html:
                    raise Exception("embed页也失败")
                soup = BeautifulSoup(html, "html.parser")
            
            title = '未知视频'
            title_elem = soup.select_one('h1.title, h1, .video-title, title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            if title == '未知视频' or 'Not Found' in title:
                title_match = re.search(r'"title"\s*:\s*"([^"]+)"|og:title"[^>]*content="([^"]+)|<title[^>]*>([^<]+)', html, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = next((g for g in title_match.groups() if g and g.strip()), f"视频 {vid}")
                else:
                    title = f"视频 {vid}"
            
            pic = ''
            pic_elem = soup.select_one('meta[property="og:image"], .fp-poster img, .video-player img, img[data-original*="screenshots"]')
            if pic_elem:
                if pic_elem.name == 'meta':
                    pic = pic_elem.get('content', '')
                else:
                    pic = pic_elem.get('data-original') or pic_elem.get('src', '') or pic_elem.get('srcset', '').split(',')[0].strip() if pic_elem.get('srcset') else ''
            
            if not pic:
                pic_match = re.search(r'previewurl\s*["\']([^"\']*\.jpg[^"\']*)["\']', html, re.IGNORECASE)
                if pic_match:
                    pic = pic_match.group(1)
                    if not pic.startswith('http'):
                        pic = f"{self.host}{pic}"
            
            desc = ''
            desc_elem = soup.select_one('meta[name="description"], meta[property="og:description"], .description em, .item:contains("Description") em')
            if desc_elem:
                if desc_elem.name == 'meta':
                    desc = desc_elem.get('content', '')[:500]
                else:
                    desc = desc_elem.get_text(strip=True)[:500]
            
            if not desc:
                desc_match = re.search(r'Description\s*<em>([^<]+)</em>', html, re.IGNORECASE | re.DOTALL)
                if desc_match:
                    desc = desc_match.group(1).strip()[:500]
            
            actor_list = []
            actor_elems = soup.select('a[href*="/models/"], a[href*="/model/"], .models a, .item:contains("Models") a')
            for actor_elem in actor_elems[:5]:
                actor_name = actor_elem.get_text(strip=True)
                if actor_name and len(actor_name) > 1 and actor_name not in actor_list:
                    actor_list.append(actor_name)
            actor = '/'.join(actor_list) if actor_list else ''
            
            director = ''
            site_elem = soup.select_one('a[href*="/categories/"], a[href*="/site/"], .site-name, .categories a')
            if site_elem:
                director = site_elem.get_text(strip=True)
            
            duration = ''
            duration_elem = soup.select_one('.duration em, span:contains("Duration") em')
            if duration_elem:
                duration = duration_elem.get_text(strip=True)
            
            views = ''
            views_elem = soup.select_one('span:contains("Views") em')
            if views_elem:
                views = views_elem.get_text(strip=True)
            
            remarks = f"{duration} | {views}次观看" if duration or views else ''
            
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
            
            print(f"[DETAIL] 成功解析: {title} (ID: {vid}, Pic: {bool(pic)}, Actor: {actor})")
            return {'list': [vod_info]}
            
        except Exception as e:
            print(f"[DETAIL] 错误: {e}")
            import traceback
            traceback.print_exc()
            vid = ids[0]
            return {'list': [{'vod_id': vid, 'vod_name': f'视频 {vid}', 'vod_pic': '', 'vod_remarks': '', 'vod_content': '', 'vod_director': '', 'vod_actor': '', 'vod_play_from': '默认播放', 'vod_play_url': f'播放${vid}'}]}

    def extract_video_url_from_page(self, html, vid):
        """从HTML提取视频URL - 完全重写版本（多策略提取）"""
        
        print(f"[EXTRACT] 开始提取视频链接 for vid {vid}")
        
        # ============ 策略1: 提取所有可能的视频URL（mp4/m3u8） ============
        video_url_patterns = [
            # 匹配完整的get_file路径（带或不带引号）
            r'["\']?(https?://[^"\'<>\s]+?/get_file/[^"\'<>\s]+?\.mp4[^"\'<>\s]*)["\']?',
            # 匹配相对路径
            r'["\']?(/get_file/\d+/[a-f0-9]+/\d+/\d+/\d+\.mp4[^"\'<>\s]*)["\']?',
            # 匹配m3u8链接（备用）
            r'["\']?(https?://[^"\'<>\s]+?\.m3u8[^"\'<>\s]*)["\']?',
            r'["\']?(/[^"\'<>\s]+?\.m3u8[^"\'<>\s]*)["\']?',
        ]
        
        all_urls = []
        for pattern in video_url_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for url in matches:
                if url and (str(vid) in url or 'get_file' in url or '.m3u8' in url):
                    # 清理URL
                    url = url.strip('\'"\\')
                    # 移除尾部的非URL字符
                    url = re.sub(r'[,;\\]+$', '', url)
                    # 补充域名
                    if url.startswith('/'):
                        url = f"https://www.webpussi.com{url}"
                    all_urls.append(url)
        
        # 去重并按优先级排序（mp4 > m3u8）
        all_urls = list(dict.fromkeys(all_urls))  # 去重保持顺序
        mp4_urls = [u for u in all_urls if '.mp4' in u and str(vid) in u]
        m3u8_urls = [u for u in all_urls if '.m3u8' in u]
        
        print(f"[EXTRACT] 找到 {len(mp4_urls)} 个MP4链接, {len(m3u8_urls)} 个M3U8链接")
        
        # 优先返回MP4链接
        if mp4_urls:
            best_url = mp4_urls[0]
            # 清理URL参数（移除已有的rnd等参数）
            best_url = re.sub(r'\?.*$', '', best_url)
            # 添加新的随机参数
            rnd = int(time.time() * 1000) + random.randint(1, 1000)
            final_url = f"{best_url}?rnd={rnd}"
            print(f"[EXTRACT] 提取成功(MP4): {final_url}")
            return final_url
        
        # 备用M3U8链接
        if m3u8_urls:
            best_url = m3u8_urls[0]
            best_url = re.sub(r'\?.*$', '', best_url)
            rnd = int(time.time() * 1000) + random.randint(1, 1000)
            final_url = f"{best_url}?rnd={rnd}"
            print(f"[EXTRACT] 提取成功(M3U8): {final_url}")
            return final_url
        
        # ============ 策略2: 从JS变量提取（videourl/video_url/file等） ============
        js_var_patterns = [
            r'videourl\s*[:=]\s*["\']([^"\']+)["\']',
            r'video_url\s*[:=]\s*["\']([^"\']+)["\']',
            r'file\s*[:=]\s*["\']([^"\']+)["\']',
            r'["\']url["\']\s*[:=]\s*["\']([^"\']+)["\']',
            r'src\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
        ]
        
        for pattern in js_var_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(1)
                if ('get_file' in url or '.mp4' in url or '.m3u8' in url):
                    if url.startswith('/'):
                        url = f"https://www.webpussi.com{url}"
                    url = re.sub(r'\?.*$', '', url)
                    rnd = int(time.time() * 1000) + random.randint(1, 1000)
                    final_url = f"{url}?rnd={rnd}"
                    print(f"[EXTRACT] JS变量提取成功: {final_url}")
                    return final_url
        
        # ============ 策略3: 从HTML注释或隐藏区域提取 ============
        comment_pattern = r'<!--.*?(https?://[^<>\s]+?\.mp4[^<>\s]*).*?-->'
        comment_match = re.search(comment_pattern, html, re.DOTALL | re.IGNORECASE)
        if comment_match:
            url = comment_match.group(1)
            if str(vid) in url:
                url = re.sub(r'\?.*$', '', url)
                rnd = int(time.time() * 1000) + random.randint(1, 1000)
                final_url = f"{url}?rnd={rnd}"
                print(f"[EXTRACT] HTML注释提取成功: {final_url}")
                return final_url
        
        print(f"[EXTRACT] 未找到有效播放链接 for vid {vid}")
        print(f"[EXTRACT] HTML长度: {len(html)}, 包含get_file: {'get_file' in html}")
        
        # 调试：打印HTML片段（包含get_file的部分）
        if 'get_file' in html:
            matches = re.finditer(r'.{0,100}get_file.{0,200}', html, re.IGNORECASE)
            for i, m in enumerate(matches):
                if i < 3:  # 只打印前3个匹配
                    print(f"[DEBUG] get_file片段{i+1}: {m.group()}")
        
        return ""

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
                print("[SEARCH] 获取HTML失败")
                return {'list': []}
            
            result = self.parse_video_list(html)
            
            soup = BeautifulSoup(html, "html.parser")
            pagecount = int(pg)
            
            try:
                pagination = soup.select_one('.pagination')
                if pagination:
                    last_link = pagination.find('a', text=re.compile('Last|最后'))
                    if last_link:
                        last_href = last_link.get('href', '')
                        last_pg_match = re.search(r'/(\d+)/', last_href)
                        if last_pg_match:
                            pagecount = int(last_pg_match.group(1))
            except Exception as e:
                print(f"[SEARCH] 分页解析失败: {e}")
            
            result.update({
                'page': pg,
                'pagecount': pagecount,
                'limit': 48,
                'total': 99999
            })
            
            print(f"[SEARCH] 找到 {len(result['list'])} 个视频")
            return result
            
        except Exception as e:
            print(f"[SEARCH] 搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        """播放链接解析 - 优化版本（增强提取和调试）"""
        try:
            vid = id
            
            # 优先embed页
            embed_url = f"{self.host}/embed/{vid}"
            print(f"[PLAYER] 尝试embed页: {embed_url}")
            
            # 使用更完整的headers
            embed_headers = self.headers.copy()
            embed_headers.update({
                'Referer': f"{self.host}/videos/{vid}/",
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            })
            
            try:
                res = requests.get(embed_url, headers=embed_headers, timeout=15, allow_redirects=True)
                res.encoding = 'utf-8'
                embed_html = res.text
            except Exception as e:
                print(f"[PLAYER] Embed请求失败: {e}")
                embed_html = ""
            
            video_url = ""
            if embed_html and len(embed_html) > 500:
                video_url = self.extract_video_url_from_page(embed_html, vid)
                if video_url:
                    print(f"[PLAYER] 从embed成功提取: {video_url}")
            
            # 备用: 详情页
            if not video_url:
                detail_url = f"{self.host}/videos/{vid}/"
                print(f"[PLAYER] 尝试详情页: {detail_url}")
                detail_html = self.get_html(detail_url)
                if detail_html and "Not Found" not in detail_html and len(detail_html) > 1000:
                    video_url = self.extract_video_url_from_page(detail_html, vid)
                    if video_url:
                        print(f"[PLAYER] 从详情页成功提取: {video_url}")
            
            # 构建播放headers
            if video_url:
                player_headers = {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': embed_url,
                    'Origin': self.host,
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'video',
                    'Sec-Fetch-Mode': 'no-cors',
                    'Sec-Fetch-Site': 'same-origin'
                }
                
                print(f"[PLAYER] 最终播放链接: {video_url}")
                return {
                    "parse": 0,
                    "url": video_url,
                    "header": player_headers
                }
            else:
                print(f"[PLAYER] 未能提取链接 for vid {vid}")
                # 返回一个通用播放器尝试链接
                fallback_url = f"{self.host}/embed/{vid}"
                return {
                    "parse": 0,
                    "url": fallback_url,
                    "header": self.headers
                }
            
        except Exception as e:
            print(f"[PLAYER] 错误: {e}")
            import traceback
            traceback.print_exc()
            return {"parse": 0, "url": "", "header": self.headers}

    def localProxy(self, param):
        pass

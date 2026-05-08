# 观阴尊者
# coding=utf-8
import sys
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "WhosTV(识图搜片)"

    def init(self, extend=""):
        self.host = "https://whos.tv"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
            'Referer': self.host,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }

    def homeContent(self, filter):
        result = {"class": [], "list": []}
        result["class"] = [
            {"type_id": "actresses", "type_name": "演员库"},
            {"type_id": "ranking/video", "type_name": "排行榜"},
            {"type_id": "topics", "type_name": "专题合集"},
            {"type_id": "videos", "type_name": "影片库"},
        ]
        try:
            r = requests.get(self.host, headers=self.headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                result["list"] = self._parse_vod_list(soup)
        except:
            pass
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 999, "limit": 20, "total": 9999}
        url = f"{self.host}/{tid}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code != 200:
                return result
            soup = BeautifulSoup(r.text, 'html.parser')

            if "actresses" in tid:
                result["list"] = self._parse_actress_list(soup)
            elif tid == "topics":
                result["list"] = self._parse_topic_list(soup)
            else:
                result["list"] = self._parse_vod_list(soup)

            page_links = soup.select('a[href*="page-"], a[href*="?page="]')
            nums = []
            for a in page_links:
                m = re.search(r'(?:page-|page=)(\d+)', a.get('href', ''))
                if m:
                    nums.append(int(m.group(1)))
            if nums:
                result["pagecount"] = max(nums)
                result["total"] = len(result["list"]) * result["pagecount"]
        except:
            pass
        return result

    def _parse_actress_list(self, soup):
        result = []
        for card in soup.select('div.card'):
            a_tag = card.find_parent('a') or card.select_one('a[href*="/actresses/"]')
            if not a_tag:
                continue
            raw_id = a_tag.get('href', '').split('/')[-1]
            name_tag = card.select_one('h3')
            title = name_tag.get_text(strip=True) if name_tag else unquote(raw_id)
            remark_tag = card.select_one('span.flex.items-center.gap-1')
            remark = f"作品: {remark_tag.get_text(strip=True)}" if remark_tag else ""
            img = card.select_one('img')
            pic = self._extract_pic(img) if img else ""
            result.append({
                "vod_id": f"actress_list:{raw_id}",
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return result

    def _parse_topic_list(self, soup):
        result = []
        seen = set()
        for a in soup.select('a[href*="/topics/"]'):
            href = a.get('href', '')
            topic_id = href.split('/')[-1]
            if topic_id in seen:
                continue
            seen.add(topic_id)
            img = a.select_one('img')
            pic = self._extract_pic(img) if img else ""
            title_el = a.select_one('h2, h3, [class*="title"]')
            name = title_el.get_text(strip=True) if title_el else topic_id
            result.append({
                "vod_id": f"topic_list:{topic_id}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "专题合集"
            })
        return result

    def _extract_pic(self, img):
        if not img:
            return ""
        # src 优先（手机版直接返回），其次各种懒加载属性
        src = (img.get('src') or img.get('data-src') or img.get('data-original') or
               img.get('data-lazy') or "")
        if not src:
            srcset = img.get('srcset', '')
            if srcset:
                src = srcset.strip().split(',')[0].strip().split(' ')[0]
        if not src:
            style = img.get('style', '')
            m = re.search(r"url\(['\"]?([^'\")\s]+)['\"]?\)", style)
            if m:
                src = m.group(1)
        return self.format_url(src)

    def _parse_vod_list(self, soup):
        video_list = []
        seen = set()
        items = soup.select('a[href*="/videos/"][class*="card"], main a[href*="/videos/"]')
        if not items:
            for a in soup.select('a[href*="/videos/"]'):
                if a.find_parent('header') or a.find_parent('nav'):
                    continue
                items.append(a)

        for item in items:
            href = item.get('href', '').strip()
            if not href or '/videos/' not in href:
                continue
            vod_id = href.rstrip('/').split('/')[-1]
            if not vod_id or vod_id in seen:
                continue
            seen.add(vod_id)

            title = ""
            for tag in item.select('h3, h4, [class*="title"]'):
                t = tag.get_text(strip=True)
                if t:
                    title = t
                    break
            if not title:
                img_el = item.select_one('img')
                if img_el and img_el.get('alt'):
                    alt = img_el['alt'].strip()
                    if alt and not re.match(r'^\d+$', alt):
                        title = alt
            if not title:
                raw = item.get_text(separator=' ', strip=True)
                raw = re.sub(r'\d+分钟|评分\s*[\d.]+|收藏|已收藏|详情|\b\d{1,4}\b', '', raw).strip()
                if raw:
                    title = raw
            if not title:
                title = vod_id.upper().replace('-', ' ')
            title = re.sub(r'\s+', ' ', title).strip()

            img_tag = item.select_one('img')
            pic = self._extract_pic(img_tag) if img_tag else ""

            video_list.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": vod_id.upper()
            })
        return video_list

    def detailContent(self, ids):
        ident = ids[0]

        if ident.startswith("actress_list:"):
            return self._detail_actress(ident)

        if ident.startswith("topic_list:"):
            return self._detail_topic(ident)

        return self._detail_video(ident)

    def _detail_actress(self, ident):
        actress_path = ident.split(':')[-1]
        base_url = f"{self.host}/actresses/{actress_path}"
        all_videos, curr_page = [], 1
        vod_name, vod_pic = unquote(actress_path), ""
        try:
            while curr_page <= 5:
                p_url = base_url if curr_page == 1 else f"{base_url}/page-{curr_page}"
                r = requests.get(p_url, headers=self.headers, timeout=10)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, 'html.parser')
                if curr_page == 1:
                    h1 = soup.select_one('h1')
                    if h1:
                        vod_name = h1.get_text(strip=True)
                    meta_img = soup.find('meta', property="og:image")
                    if meta_img:
                        vod_pic = self._extract_pic(meta_img)
                p_list = self._parse_vod_list(soup)
                if not p_list:
                    break
                all_videos.extend(p_list)
                if not soup.find('a', title="下一页"):
                    break
                curr_page += 1
            play_urls = [f"{v['vod_name']}${v['vod_id']}" for v in all_videos]
            return {"list": [{"vod_id": ident, "vod_name": vod_name, "vod_pic": vod_pic,
                              "vod_remarks": f"共{len(all_videos)}部", "vod_play_from": "作品列表",
                              "vod_play_url": "#".join(play_urls)}]}
        except:
            pass
        return {"list": []}

    def _detail_topic(self, ident):
        topic_path = ident.split(':')[-1]
        base_url = f"{self.host}/topics/{topic_path}"
        all_videos, curr_page = [], 1
        vod_name, vod_pic = topic_path, ""
        try:
            while curr_page <= 5:
                p_url = base_url if curr_page == 1 else f"{base_url}?page={curr_page}"
                r = requests.get(p_url, headers=self.headers, timeout=10)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, 'html.parser')
                if curr_page == 1:
                    h1 = soup.select_one('h1')
                    if h1:
                        vod_name = h1.get_text(strip=True)
                    meta_img = soup.find('meta', property="og:image")
                    if meta_img:
                        vod_pic = self._extract_pic(meta_img)
                p_list = self._parse_vod_list(soup)
                if not p_list:
                    break
                all_videos.extend(p_list)
                if not soup.find('a', title="下一页") and not soup.select_one('[rel="next"]'):
                    break
                curr_page += 1
            play_urls = [f"{v['vod_name']}${v['vod_id']}" for v in all_videos]
            return {"list": [{"vod_id": ident, "vod_name": vod_name, "vod_pic": vod_pic,
                              "vod_remarks": f"共{len(all_videos)}部", "vod_play_from": "专题影片",
                              "vod_play_url": "#".join(play_urls)}]}
        except:
            pass
        return {"list": []}

    def _detail_video(self, ident):
        try:
            r = requests.get(f"{self.host}/videos/{ident}", headers=self.headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            h1 = soup.select_one('h1')
            title = h1.get_text(strip=True) if h1 else ident.upper()
            desc = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                desc = meta_desc['content'].strip()
            if not desc:
                desc_el = soup.select_one('.description, .content, article p')
                if desc_el:
                    desc = desc_el.get_text(strip=True)
            og_img = soup.find('meta', property='og:image')
            vod_pic = self._extract_pic(og_img) if og_img else ""
            tags_el = soup.select('a[href*="/videos?q="], .tag, .badge')
            tags = [t.get_text(strip=True) for t in tags_el[:5]]
            remark = ' / '.join(tags) if tags else ident.upper()
            return {"list": [{"vod_id": ident, "vod_name": title, "vod_pic": vod_pic,
                              "vod_remarks": remark, "vod_content": desc,
                              "vod_play_from": "在线播放", "vod_play_url": f"点击播放${ident}"}]}
        except:
            pass
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        url = f"{self.host}/videos/{id}"
        headers = self.headers.copy()
        headers['Referer'] = url
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                html = r.text
                m3u8_match = re.search(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*?)', html)
                if m3u8_match:
                    return {"parse": 0, "url": m3u8_match.group(1).replace('\\/', '/'),
                            "header": {"User-Agent": headers['User-Agent'], "Referer": self.host}}
                soup = BeautifulSoup(html, 'html.parser')
                source = soup.find('source', src=re.compile(r'\.m3u8')) or soup.find('video', src=re.compile(r'\.m3u8'))
                if source:
                    return {"parse": 0, "url": self.format_url(source.get('src')),
                            "header": {"Referer": self.host}}
        except:
            pass
        return {"parse": 0, "url": id, "header": ""}

    def format_url(self, url):
        if not url:
            return ""
        if url.startswith('//'):
            return "https:" + url
        if url.startswith('/'):
            return self.host + url
        if url.startswith('http'):
            return url
        return self.host + '/' + url.lstrip('/')

    def searchContent(self, key, quick, pg=1):
        return self.categoryContent(f"search?q={key}", pg, {}, {})
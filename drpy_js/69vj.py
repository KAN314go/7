# coding=utf-8
# !/usr/bin/python
import json
import re
import sys
from base64 import b64decode, b64encode
from pyquery import PyQuery as pq
from requests import Session

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = 'https://69vj.com'
        self.headers['referer'] = f'{self.host}/'
        self.session = Session()
        self.session.headers.update(self.headers)

    def getName(self):
        return "69VJ_XVideos"

    def isVideoFormat(self, url):
        return any(url.endswith(suf) for suf in ['.m3u8', '.mp4', '.webm'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except:
            pass

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'dnt': '1',
        'upgrade-insecure-requests': '1',
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'priority': 'u=0, i'
    }

    def homeContent(self, filter):
        cateManual = {
            "素人": "/amateur",
            "乱伦": "/incest-taboo",
            "BDSM": "/bdsm",
            "直播": "/liveshow",
            "人妖": "/shemale",
            "Cosplay": "/cosplay",
            "3D": "/3d-hentai",
            "H动漫": "/h-anime",
            "AV女优": "/av-actresses",
            "熟女": "/milf",
            "手机AV": "/mobile-av",
            "猎奇": "/bizarre",
            "按摩": "/massage",
        }
        classes = []
        for k, v in cateManual.items():
            classes.append({'type_name': k, 'type_id': v})
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        data = self.getpq('/liveshow')
        return {'list': self.getlist(data('div.list-item div.video'))}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 999999}
        vdata = []
        path = tid
        if tid.startswith('two_click_'):
            real = tid.replace('two_click_', '')
            path = real if real.startswith('http') else (real if real.startswith('/') else '/' + real)
        
        if pg != '1':
            path = f"{path}page/{pg}" if path.endswith('/') else f"{path}/page/{pg}"
            
        data = self.getpq(path)
        vdata = self.getlist(data('div.list-item div.video'))
        result['list'] = vdata
        return result

    def detailContent(self, ids):
        url = ids[0]
        data = self.getpq(url)
        vn = data('h1.title span[itemprop="name"]').text() or data('title').text()
        
        tag_links = []
        for a in data('p.tags a[rel="tag"]').items():
            tname = a.attr('title') or a.text().strip()
            thref = a.attr('href')
            if not tname or not thref: continue
            thref = self.normalize_path(thref)
            tag_json = json.dumps({'id': 'two_click_' + thref, 'name': tname}, ensure_ascii=False)
            tag_links.append(f'[a=cr:{tag_json}/]{tname}[/a]')
        
        vod_content = '  '.join(tag_links) if tag_links else ''
        remarks = data('#post-ratings-' + self.extract_post_id(url)).text()

        vod = {
            'vod_name': vn,
            'vod_content': vod_content,
            'vod_remarks': remarks,
            'vod_play_from': '69VJ',
            'vod_play_url': ''
        }

        try:
            play_list = self.get_play_list_from_embed(url, vn)
        except Exception:
            play_list = [f"{vn}${self.e64(f'1@@@@{url}') }"]

        vod['vod_play_url'] = '#'.join(play_list)
        return {'list': [vod]}

    def get_play_list_from_embed(self, page_url, title):
        detail_html = self.session.get(page_url, headers=self.headers).text
        m = re.search(r'<iframe[^>]+src=["\'](https?://www\.xvideos\.com/embedframe/[^"\']+)["\']', detail_html, re.IGNORECASE)
        
        if not m:
            vid_match = re.search(r'/video(\d+)', page_url)
            if not vid_match: raise Exception("No Embed")
            embed_url = f'https://www.xvideos.com/embedframe/{vid_match.group(1)}'
        else:
            embed_url = m.group(1)

        embed_headers = self.headers.copy()
        embed_headers['referer'] = page_url
        embed_html = self.session.get(embed_url, headers=embed_headers).text
        
        urls = []
        high = self._extract_xv_func_url(embed_html, 'setVideoUrlHigh')
        if high: urls.append(('高清', high))
        
        low = self._extract_xv_func_url(embed_html, 'setVideoUrlLow')
        if low: urls.append(('低清', low))
        
        hls = self._extract_xv_func_url(embed_html, 'setVideoHLS')
        if not hls:
            m3 = re.search(r'<video[^>]+src=["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', embed_html, re.IGNORECASE)
            if m3: hls = m3.group(1)
        if hls: urls.append(('HLS', hls))

        if not urls: raise Exception("No Urls")

        seen = set()
        final = []
        for name, u in urls:
            if not u or u in seen: continue
            seen.add(u)
            final.append(f"{name}${self.e64(f'0@@@@{u}')}")
            
        return final

    def _extract_xv_func_url(self, html, func_name):
        m = re.search(rf'html5player\.{func_name}\s*\(\s*["\'](https?://[^"\']+)["\']\s*\)', html)
        if m: return m.group(1)
        m2 = re.search(rf'html5player\.{func_name}[^\n\r]*?(https?://[^\s"\']+)', html)
        if m2: return m2.group(1)
        return None

    def searchContent(self, key, quick, pg="1"):
        path = f"/?s={key}"
        if pg != '1':
            connector = '&' if '?' in path else '?'
            path = f"{path}{connector}paged={pg}"
        data = self.getpq(path)
        return {'list': self.getlist(data('div.list-item div.video')), 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            'User-Agent': self.headers['User-Agent'],
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'origin': self.host,
            'sec-fetch-site': 'cross-site',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': f'{self.host}/',
            'accept-language': self.headers['accept-language'],
            'priority': 'u=1, i',
        }
        ids = self.d64(id).split('@@@@')
        return {'parse': int(ids[0]), 'url': ids[1], 'header': headers}

    def localProxy(self, param):
        return {}

    def e64(self, text):
        try:
            return b64encode(text.encode('utf-8')).decode('utf-8')
        except:
            return ""

    def d64(self, encoded_text):
        try:
            return b64decode(encoded_text.encode('utf-8')).decode('utf-8')
        except:
            return ""

    def normalize_path(self, href):
        if not href: return ''
        m = re.match(r'https?://[^/]+(.*)', href)
        if m: return m.group(1) or '/'
        return href

    def extract_post_id(self, url):
        m = re.search(r'/video(\d+)', url)
        return m.group(1) if m else ''

    def getlist(self, nodes):
        vlist = []
        for v in nodes.items():
            a = v('a.thumb-video')
            if not a: continue
            href = a.attr('href') or ''
            title = a.attr('title') or v('.denomination .title').text()
            img = v('img').attr('data-src') or v('img').attr('data-srch') or v('img').attr('src')
            duration = v('.time-desc span').eq(1).text() or v('.time-desc').text()
            rating = v.parent().find('div.post-ratings span[style*="font-size"]').text()
            vlist.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': img,
                'vod_year': rating,
                'vod_remarks': duration,
                'style': {'ratio': 1.33, 'type': 'rect'}
            })
        return vlist

    def getpq(self, path=''):
        url = f'{"" if path.startswith("http") else self.host}{path}'
        try:
            return pq(self.session.get(url, headers=self.headers).text)
        except:
            return pq('')

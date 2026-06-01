# coding=utf-8
#!/usr/bin/python
import sys, re, base64, hashlib, json, requests, time
from base.spider import Spider
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin
from urllib3.util.retry import Retry
sys.path.append('..')

class Spider(Spider):
    def init(self, extend="{}"):
        origin = 'https://zh.stripchat.com'
        self.host = origin
        self.Doppiocdn = "doppiocdn.org"
        #domains = [
        #    "doppiocdn.com",       # cf cdn只能图片用，播放不了
        #    "doppiocdn.org",       # 靠谱云cdn，国内有节点
        #    "doppiocdn.net"        # cft cdn
        #]
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0"
        self.headers = {'Origin': origin, 'Referer': f"{origin}/", 'User-Agent': user_agent, "Accept-Language": "zh,en;q=0.5"}
        self.search_host = "https://hdstream.ing"
        self.search_headers = {'Origin': self.search_host, 'Referer': f"{self.search_host}/", 'User-Agent': user_agent}
        self.stripchat_preferredVideoCodec = "H265"
        self.stripchat_decrypt_key = self.decode_key_compact("NDUgNTEgNzUgNjUgNjUgNDcgNjggMzIgNmIgNjEgNjUgNzcgNjEgMzMgNjMgNjg=")
        self.stripchat_auth_key = 'Ook7quaiNgiyuhai'
        self._hash_cache = {}
        self.stripchat_play='0 0'
        self.create_session_with_retry()

    def getName(self): return "StripChat"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeVideoContent(self):
        pass

    def normalize_username_for_hdstream(self, username):
        return username.replace('-', '_').lower()

    def homeContent(self, filter):
        CLASSES = [{'type_name': '女主播g', 'type_id': 'girls'}, {'type_name': '情侣c', 'type_id': 'couples'}, {'type_name': '男主播m', 'type_id': 'men'}, {'type_name': '跨性别t', 'type_id': 'trans'}]
        VALUE = [{'n': '中国', 'v': 'tagLanguageChinese'}, {'n': '亚洲', 'v': 'ethnicityAsian'}, {'n': '白人', 'v': 'ethnicityWhite'}, {'n': '拉丁', 'v': 'ethnicityLatino'}, {'n': '混血', 'v': 'ethnicityMultiracial'}, {'n': '印度', 'v': 'ethnicityIndian'}, {'n': '阿拉伯', 'v': 'ethnicityMiddleEastern'}, {'n': '黑人', 'v': 'ethnicityEbony'}]
        VALUE_MEN = [{'n': '情侣', 'v': 'sexGayCouples'}, {'n': '直男', 'v': 'orientationStraight'}]
        TIDS = ('girls', 'couples', 'men', 'trans')
        filters = {tid: [{'key': 'tag', 'value': VALUE_MEN + VALUE if tid == 'men' else VALUE}] for tid in TIDS}
        return {'class': CLASSES, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        if str(tid).startswith('hd_search_'): return self.handle_external_search(tid.replace('hd_search_', ''), pg)
        
        # 🔥 修复：明确定义limit变量
        limit = 60
        offset = limit * (int(pg) - 1)
        url = f"{self.host}/api/front/models?improveTs=false&removeShows=false&limit={limit}&offset={offset}&primaryTag={tid}&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false"
        if 'tag' in extend: url += f'&filterGroupTags=[["{extend["tag"]}"]]'
        rsp = self.session_get(url).json()
        videos = [{"vod_id": str(v['username']), "vod_name": f"{self.country_code_to_flag(str(v['country']))}{v['username']}", "vod_pic": f"https://img.doppiocdn.com/thumbs/{v['snapshotTimestamp']}/{v['id']}", "vod_remarks": "" if v.get('status') == "public" else "🎫"} for v in rsp.get('models', [])]
        total = int(rsp.get('filteredCount', 0))
        return {"list": videos, "page": pg, "pagecount": (total + limit - 1) // limit, "limit": limit, "total": total}

    def handle_external_search(self, keyword, pg):
        try:
            rsp = self.session_get(f"{self.search_host}/search/{quote(keyword)}/?page={pg}", self.search_headers).text
            soup = BeautifulSoup(rsp, 'lxml')
            pagination_nav = soup.find('nav', attrs={'aria-label': 'Pagination'})
            page_elements = pagination_nav.find_all(['span', 'a'])
            for element in reversed(page_elements):
                element_text = element.get_text(strip=True)
                if element_text and element_text.isdigit():
                    pc = int(element_text)
                    break
            videos = []
            for a_tag in soup.find_all('a', class_='popunder'):
                img_tag = a_tag.find('img')
                if not img_tag:
                    continue
                img_src = img_tag.get('data-src', '').strip()
                pic = urljoin(self.search_host, img_src)
                href = a_tag.get('href', '').strip()
                url = urljoin(self.search_host, href)
                name = img_tag.get('alt', '').replace('free recording from ', '').strip()
                videos.append({"vod_id": url, "vod_name": name, "vod_pic": f"{self.getProxyUrl()}&type=rec_img&url={quote(pic)}"})
            limit = 50
            return {"list": videos, "page": pg, "pagecount": pc, "limit": limit, "total": limit * pc}
        except: return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0}

    def detailContent(self, array):
        username = rec_url = array[0]
        if rec_url.startswith('https'):
            try:
                rsp = self.session_get(rec_url, self.search_headers).text
                soup = BeautifulSoup(rsp, 'lxml')
                title = soup.title.text
                url = soup.select_one('video source').get('src')
                return {'list': [{"vod_id": rec_url, "vod_name": title, "vod_play_from": "HDstream", "vod_play_url": f"点击播放${url}"}]}
            except: return {'list': []}
        
        try:
            rsp = self.session_get(f"{self.host}/api/front/v2/models/username/{username}/cam").json()
            info, user = rsp['cam'], rsp['user']['user']
            uid, isLive = str(user['id']), user['isLive']
            oldName = self.stripchat_play.rsplit(' ', 1)[-1]
            if username != oldName:
                timestp = int(time.time())
                self.stripchat_play = f"0 {timestp} {username}"
            flag = self.country_code_to_flag(str(user['country']).strip())
            remark = "🔴 直播中" if isLive else "⚫ 已下播"
            show = info.get('show') or info.get('groupShowAnnouncement')
            if show:
                startAt = show.get('createdAt') or show.get('startAt')
                if startAt: remark = f"🎫 始于 {(datetime.strptime(startAt, '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=8)).strftime('%m月%d日 %H:%M')}"
            search_username = self.normalize_username_for_hdstream(username)
            director_link = f"{flag}[a=cr:{{\"id\":\"hd_search_{search_username}\",\"name\":\"搜索 {username} 录像\"}}/]{username}[/a]"
            return {'list': [{"vod_id": username, "vod_name": str(info['topic'])[:80], "vod_pic": str(user['avatarUrl']), "vod_director": director_link, "vod_remarks": remark, 'vod_play_from': 'StripChat$$$LemonCams', 'vod_play_url': f"{uid}${uid}$$${uid}$lemon_{uid}"}]}
        except: return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        if int(pg) > 1: return {}
        tags = {'G': 'girls', 'C': 'couples', 'M': 'men', 'T': 'trans'}
        parts = key.split(maxsplit=1)
        tag, key = (tags.get(parts[0].upper()), parts[1].strip()) if len(parts) > 1 and parts[0].upper() in tags else ('girls', key.strip())
        rsp = self.session_get(f"{self.host}/api/front/v4/models/search/group/username?query={key}&limit=900&primaryTag={tag}").json()
        return {'list': [{"vod_id": str(u['username']), "vod_name": f"{self.country_code_to_flag(str(u['country']))}{u['username']}", "vod_pic": f"https://img.doppiocdn.com/thumbs/{u['snapshotTimestamp']}/{u['id']}", "vod_remarks": "" if u['status'] == "public" else "🎫"} for u in rsp.get('models', []) if u['isLive']]}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('http'):
            headers = {**self.search_headers, 'Range': 'bytes=0-'}
            nodes = ["hds3", "hds2", "hds1"]
            pattern = r"(https?://)hds\d+(\..*?\.com)"
            result = {"parse": 0, "url": id, "header": self.search_headers, 'format': 'video/mp4'}
            for node in nodes:
                url = re.sub(pattern, rf"\1{node}\2", id, count=1)
                r = self.fetch(url, headers=headers, stream=True)
                if r.status_code == 206:
                    result.update({'format': r.headers.get('Content-Type'), 'url': url})
                    break
            return result

        if id.startswith('lemon'):
            id = id.split('_')[1]
            rsp = self.session_get(f"https://edge-hls.growcdnssedge.com/hls/{id}/master/{id}_auto.m3u8?playlistType=lowLatency").text
            lines = rsp.strip().split('\n')
            urls = []
            for i, line in enumerate(lines):
                if '#EXT-X-STREAM-INF' in line:
                    qn_start = line.find('NAME="')+6
                    qn = line[qn_start:line.find('"', qn_start)]
                    url = lines[i + 1]
                    urls.extend([qn, url])
            lemon_headers = {
                'User-Agent': self.headers.get('User-Agent'),
                'Origin': 'https://www.lemoncams.com',
                'Referer': 'https://www.lemoncams.com/'
            }
            return {"url": urls, "parse": '0', "header": lemon_headers}

        try:
            rsp = self.session_get(f"https://edge-hls.{self.Doppiocdn}/hls/{id}/master/{id}_auto.m3u8?playlistType=lowLatency").text
            lines = rsp.strip().split('\n')
            psch, pkey, urls, processed = 'v2', self.stripchat_auth_key, [], False
            for i, line in enumerate(lines):
                #if line.startswith('#EXT-X-MOUFLON:') and not processed:
                #    if len(parts := line.split(':')) >= 4: psch, pkey, processed = parts[2], parts[3], True
                if '#EXT-X-STREAM-INF' in line:
                    qn_start = line.find('NAME="')+6
                    qn = line[qn_start:line.find('"', qn_start)]
                    full_url = f"{lines[i+1]}&psch={psch}&pkey={pkey}&preferredVideoCodec={self.stripchat_preferredVideoCodec}"
                    urls.extend([qn, f"{self.getProxyUrl()}&url={quote(full_url)}"])
            headers = self.headers.copy()
            headers.pop('Accept-Language', None)
            return {"url": urls, "parse": '0', "header": headers}
        except: return {"url": [], "parse": 0}

    def update_vod(self, username):
        content_data = self.detailContent([username]).get('list')[0]
        #content_data.pop('vod_id')
        payload = {"json": json.dumps(content_data)}
        self.post("http://127.0.0.1:9978/action?do=refresh&type=vod", data=payload)
    
    def localProxy(self, param):
        url, type = param['url'], param.get('type', '')
        if type == 'rec_img':
            data = self.session_get(url, self.search_headers)
            return [200, 'application/octet-stream', data.content]
        rsp = self.session_get(url)
        oldCode, oldtmp, username = self.stripchat_play.rsplit(' ')
        timestp = int(time.time())
        is_time_up = (timestp - 10) > int(oldtmp)
        is_code_changed = (int(oldCode) != 0 and rsp.status_code != int(oldCode))
        if is_time_up or is_code_changed:
            self.stripchat_play = f"{rsp.status_code} {timestp} {username}"
            self.log('计划更新')
            self.update_vod(username)
            if is_code_changed:
                self.log('code变更')
                self.post("http://127.0.0.1:9978/action?do=refresh&type=player")
                return [404, "text/plain", ""]
        if rsp.status_code == 403: rsp = self.session_get(re.sub(r'(_\d+p\d*)?\.m3u8', '_160p_blurred.m3u8', url))
        if rsp.status_code != 200: return [404, "text/plain", ""]
        data = self.process_m3u8(rsp.text) if "#EXT-X-MOUFLON:URI:" in rsp.text else rsp.text
        return [200, "application/vnd.apple.mpegur", data]

    URL_PATTERN = re.compile(r'https://media-hls\.doppiocdn\.\w+/b-hls-\d+/media\.mp4')
    def process_m3u8(self, content):
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-MOUFLON:URI:') and 'media.mp4' in lines[i+1]:
                mouflon = line.split(':', 2)[2].strip()
                encrypted = re.sub(r'(_part\d+)?\.mp4$', '', mouflon).rsplit('_', 2)[1]
                lines[i+1] = self.URL_PATTERN.sub(mouflon.replace(encrypted, self.decrypt(encrypted[::-1], self.stripchat_decrypt_key)), lines[i+1])
        return '\n'.join(lines)

    def country_code_to_flag(self, code):
        return ''.join(chr(ord(c.upper()) - ord('A') + 0x1F1E6) for c in code) if len(code) == 2 and code.isalpha() else code

    def decode_key_compact(self, b64): return bytes(int(h, 16) for h in base64.b64decode(b64).decode().split()).decode()

    def compute_hash(self, key):
        if key not in self._hash_cache: self._hash_cache[key] = hashlib.sha256(key.encode()).digest()
        return self._hash_cache[key]

    def decrypt(self, b64, key):
        b64 += '=' * (4 - len(b64) % 4)
        h = self.compute_hash(key)
        return bytearray(b ^ h[i % len(h)] for i, b in enumerate(base64.b64decode(b64))).decode()

    def create_session_with_retry(self):
        self.session = requests.Session()
        retry = Retry(total=5, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
        adapter = requests.adapters.HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100, pool_block=False)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def session_get(self, url, headers=None, stream=False): return self.session.get(url, headers = self.headers if headers is None else headers, timeout=5, stream=stream, allow_redirects = True)

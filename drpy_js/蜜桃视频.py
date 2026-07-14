# coding=utf-8
# !/usr/bin/python
# 蜜桃视频 T3 爬虫 (增强容错版 + 动态多站点)
# 网站: 通过 SITES 列表自动测速选择，支持远程动态更新
# API: AES-128-CBC (ZeroPadding) + MD5 签名

import sys
sys.path.append('..')

from base.spider import BaseSpider
import requests
import json
import base64
import hashlib
import time
import re
import os
import string
import random
import threading
from urllib.parse import quote, unquote
from Crypto.Cipher import AES
import concurrent.futures

TIMEOUT = 10

# ============================================================
# 站点配置（支持远程动态更新）
# ============================================================
SITES_REMOTE_URL = ""   # 可填入动态获取站点的接口，返回 JSON 格式 [{"name":"xxx","host":"https://..."}]
SITES = [
    {'name': 'nht966', 'host': 'https://www.nht966hht.vip:9527'},
    {'name': 'httre666', 'host': 'https://www.newhttestre666.cc'},
    # 可添加更多备选
]

# ============================================================
# 加密常量（若网站更新需从 JS 中提取新值）
# ============================================================
SIGN_KEY  = 'opum3_Loily$SV^6H'      # 可能已变
BUNDLE_ID = 'com.ht9.web20.video'    # 可能已变
BRAND_ID  = 'hongtao'                # 可能已变
VERSION   = '1.0.0'
PROJECT_ID = '1'
PROXY_TYPE = 'mitao_img'

# ============================================================
# 增强日志（可改为 logging 模块）
# ============================================================
def log(msg):
    print(f"[蜜桃] {time.strftime('%H:%M:%S')} {msg}")

class Spider(BaseSpider):
    # ---- 基础信息 ----
    def getName(self):
        return "蜜桃视频"

    def isVideoFormat(self, url):
        return url and ('.mp4' in url or '.m3u8' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    # ---- 类变量 ----
    filterable = True
    searchable = True
    host = SITES[0]['host']
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "lang": "cn",
        "deviceType": "H5-android",
    }

    _speed_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mitao_cache.json')
    _speed_cache_ttl = 1800
    _lock = threading.Lock()
    _speed_test_done = False

    _user_id = ''
    _session_id = ''
    _device_id = ''
    _session_inited = False

    _categories = []
    _video_type_list = []

    _session_cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mitao_session.json')
    _session_cache_ttl = 1800

    # ============================================================
    # 动态获取远程站点列表
    # ============================================================
    def _fetch_remote_sites(self):
        """从远程接口获取最新站点列表，失败则使用内置列表"""
        if not SITES_REMOTE_URL:
            return
        try:
            r = requests.get(SITES_REMOTE_URL, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0 and 'host' in data[0]:
                    global SITES
                    SITES = data
                    log(f"已从远程更新站点列表，共 {len(SITES)} 个")
        except Exception as e:
            log(f"获取远程站点列表失败: {e}")

    # ============================================================
    # 多站点测速（线程池优化 + 兜底策略）
    # ============================================================
    def _get_cached_site(self):
        try:
            if os.path.exists(self._speed_cache_file):
                with open(self._speed_cache_file, 'r') as f:
                    data = json.load(f)
                age = time.time() - data.get('ts', 0)
                host = data.get('host', '')
                if age < self._speed_cache_ttl and host:
                    return host, True
        except Exception:
            pass
        return '', False

    def _save_cached_site(self, host):
        try:
            with open(self._speed_cache_file, 'w') as f:
                json.dump({'host': host, 'ts': time.time()}, f)
        except Exception:
            pass

    def _select_best_site(self):
        if self._speed_test_done:
            return

        # 先尝试远程更新站点列表
        self._fetch_remote_sites()

        cached_host, valid = self._get_cached_site()
        if valid:
            self.host = cached_host
            self._speed_test_done = True
            log(f"使用缓存站点: {self.host}")
            return

        results = {}
        def test_site(site):
            try:
                start = time.time()
                r = requests.get(site['host'], headers=self.headers, timeout=TIMEOUT, verify=False)
                # 只要返回状态码在 200~499 之间，认为主机可达
                if 200 <= r.status_code < 500:
                    results[site['name']] = time.time() - start
                else:
                    results[site['name']] = 999
            except:
                results[site['name']] = 999

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(SITES)) as executor:
            futures = [executor.submit(test_site, s) for s in SITES]
            concurrent.futures.wait(futures, timeout=TIMEOUT + 2)

        valid_sites = [s for s in SITES if results.get(s['name'], 999) < TIMEOUT]
        if valid_sites:
            best = min(valid_sites, key=lambda x: results[x['name']])
            self.host = best['host']
        else:
            # 全部不可达时使用第一个
            self.host = SITES[0]['host']
            log("所有站点测速失败，回退到默认站点")

        self._speed_test_done = True
        self._save_cached_site(self.host)
        log(f"当前工作站点: {self.host}")

    # ============================================================
    # 会话缓存
    # ============================================================
    def _save_session_cache(self):
        try:
            data = {
                'ts': time.time(),
                'user_id': self._user_id,
                'session_id': self._session_id,
                'device_id': self._device_id,
                'categories': self._categories,
                'video_type_list': self._video_type_list,
            }
            with open(self._session_cache_file, 'w') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_session_cache(self):
        try:
            if not os.path.exists(self._session_cache_file):
                return False
            with open(self._session_cache_file, 'r') as f:
                data = json.load(f)
            if time.time() - data.get('ts', 0) >= self._session_cache_ttl:
                return False
            self._user_id = data.get('user_id', '')
            self._session_id = data.get('session_id', '')
            self._device_id = data.get('device_id', '')
            self._categories = data.get('categories', [])
            self._video_type_list = data.get('video_type_list', [])
            if not self._user_id or not self._session_id:
                return False
            return True
        except Exception:
            return False

    # ============================================================
    # AES 加解密（支持自动检测填充）
    # ============================================================
    @staticmethod
    def _zero_pad(data, block_size=16):
        pad_len = block_size - (len(data) % block_size)
        if pad_len == block_size:
            return data
        return data + b'\x00' * pad_len

    @staticmethod
    def _zero_unpad(data):
        return data.rstrip(b'\x00')

    def _gen_key(self, timestamp):
        ts = str(timestamp)
        return ts[-6:] + SIGN_KEY[:4] + BUNDLE_ID[:6]

    def _gen_iv(self):
        return BUNDLE_ID[-6:] + SIGN_KEY[-4:] + self._device_id[:6]

    def _aes_encrypt(self, plaintext, key_str, iv_str):
        key = key_str.encode('utf-8')
        iv = iv_str.encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        data = plaintext.encode('utf-8')
        padded = self._zero_pad(data)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode('utf-8')

    def _aes_decrypt(self, ciphertext_b64, key_str, iv_str):
        try:
            key = key_str.encode('utf-8')
            iv = iv_str.encode('utf-8')
            cipher = AES.new(key, AES.MODE_CBC, iv)
            cleaned = re.sub(r'\s', '', ciphertext_b64)
            encrypted = base64.b64decode(cleaned)
            decrypted = cipher.decrypt(encrypted)
            # 尝试 Zero 去除，若失败则使用 PKCS7 去除
            try:
                unpadded = self._zero_unpad(decrypted)
                return unpadded.decode('utf-8', errors='replace')
            except:
                # 尝试 PKCS7
                pad_len = decrypted[-1]
                if 1 <= pad_len <= 16:
                    unpadded = decrypted[:-pad_len]
                    return unpadded.decode('utf-8', errors='replace')
                else:
                    return decrypted.decode('utf-8', errors='replace')
        except Exception as e:
            log(f"AES解密失败: {e}")
            return ''

    def _generate_sign(self, params, api_path):
        sorted_keys = sorted(params.keys())
        concat = ''
        for k in sorted_keys:
            concat += str(params[k])
        raw = concat + SIGN_KEY + api_path
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    # ============================================================
    # 设备ID
    # ============================================================
    @staticmethod
    def _generate_device_id():
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        return 'H5-' + rand

    # ============================================================
    # 通用参数
    # ============================================================
    def _common_params(self):
        hostname = self.host.replace('https://', '').replace('http://', '')
        return {
            'timezone': 'Asia/Karachi',
            'version': VERSION,
            'channelId': 67,
            'channelId2': hostname,
            'brandId': BRAND_ID,
        }

    # ============================================================
    # API 请求（增强重试和错误处理）
    # ============================================================
    def _api_request(self, endpoint, params=None, skip_encrypt=False, _t=None, retry=2):
        if params is None:
            params = {}
        timestamp = str(_t) if _t else str(int(time.time() * 1000))
        key_str = self._gen_key(timestamp)
        iv_str = self._gen_iv()

        full_params = self._common_params()
        full_params['t'] = timestamp
        full_params.update(params)
        full_params['sign'] = self._generate_sign(full_params, endpoint)

        api_url = self.host + endpoint
        headers = dict(self.headers)
        headers['t'] = timestamp
        if self._user_id:
            headers['userId'] = self._user_id
        if self._session_id:
            headers['sessionId'] = self._session_id
        headers['deviceId'] = self._device_id or ''
        headers['bundleId'] = BUNDLE_ID

        if skip_encrypt:
            body = json.dumps(full_params, ensure_ascii=False, separators=(',', ':'))
            headers['Content-Type'] = 'application/json'
            headers['encrypt'] = 'false'
        else:
            plain = json.dumps(full_params, ensure_ascii=False, separators=(',', ':'))
            body = self._aes_encrypt(plain, key_str, iv_str)
            headers['Content-Type'] = 'text/plain'
            headers['encrypt'] = 'true'

        for attempt in range(retry):
            try:
                log(f"请求 {endpoint} (尝试 {attempt+1})")
                r = self.session.post(api_url, data=body, headers=headers, timeout=TIMEOUT, verify=False)
                resp = r.json()
                if resp.get('code') == 10000 and isinstance(resp.get('data'), str) and resp['data']:
                    try:
                        decrypted = self._aes_decrypt(resp['data'], key_str, iv_str)
                        if decrypted:
                            resp['data'] = json.loads(decrypted)
                    except Exception as e:
                        log(f"解密失败: {e}")
                return resp
            except Exception as e:
                log(f"请求 {endpoint} 出错: {e}")
                if attempt == retry - 1:
                    return None
                time.sleep(0.5)
        return None

    # ============================================================
    # 会话初始化（增加失败重试）
    # ============================================================
    def _ensure_session(self):
        if self._session_inited:
            return
        if self._load_session_cache():
            self._session_inited = True
            if not self._video_type_list:
                appcfg = self._api_request('/ht/users/appConfig')
                if appcfg and appcfg.get('code') == 10000:
                    ac_data = appcfg.get('data', {})
                    if isinstance(ac_data, dict) and ac_data.get('appConfig'):
                        ac_cfg = ac_data['appConfig']
                        if isinstance(ac_cfg, dict) and ac_cfg.get('videoTypeList'):
                            self._video_type_list = ac_cfg['videoTypeList']
            log("会话从缓存恢复")
            return

        if not self._device_id:
            self._device_id = self._generate_device_id()

        # appConfig
        appcfg = self._api_request('/ht/users/appConfig')
        if appcfg and appcfg.get('code') == 10000:
            ac_data = appcfg.get('data', {})
            if isinstance(ac_data, dict) and ac_data.get('appConfig'):
                ac_cfg = ac_data['appConfig']
                if isinstance(ac_cfg, dict) and ac_cfg.get('videoTypeList'):
                    self._video_type_list = ac_cfg['videoTypeList']

        shared_t = int(time.time() * 1000)
        resp1 = self._api_request('/ht/users/initH5_1', _t=shared_t)
        if resp1 and resp1.get('code') == 10000:
            data = resp1.get('data', {})
            if data.get('deviceId'):
                self._device_id = data['deviceId']
            if data.get('typeTitleList'):
                self._categories = data['typeTitleList']

        self._api_request('/ht/users/initH5_2', _t=shared_t)

        resp = self._api_request('/ht/users/deviceLogin', {
            'bundleId': BUNDLE_ID,
            'brandId': BRAND_ID,
            'projectId': PROJECT_ID,
        })
        if resp and resp.get('code') == 10000:
            data = resp.get('data', {})
            self._user_id = data.get('userId', '')
            self._session_id = data.get('sessionId', '')
            log(f"登录成功 userId={self._user_id[:8]}...")
        else:
            log("deviceLogin 失败，可能需更新加密常量")

        self._session_inited = True
        self._save_session_cache()

    # ============================================================
    # 图片代理（保持原样）
    # ============================================================
    def get_proxy_image_url(self, img_url):
        if not img_url:
            return ''
        base_proxy = self.getProxyUrl()
        if not base_proxy:
            base_proxy = 'http://127.0.0.1:9980/proxy?do=py'
        return base_proxy + '&type=' + PROXY_TYPE + '&url=' + quote(img_url, safe='')

    def _fmt_duration(self, seconds):
        try:
            s = int(seconds or 0)
        except:
            return ''
        if s <= 0:
            return ''
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"

    # ============================================================
    # 初始化
    # ============================================================
    def init(self, extend=""):
        cached_host, valid = self._get_cached_site()
        if valid:
            self.host = cached_host
            self._speed_test_done = True

    # ============================================================
    # 首页
    # ============================================================
    _CATEGORY_BLACKLIST = {'成人游戏', '漫画', '小说', '蜜穴女友', '一键脱衣', '春药商城', '同城交友', '吃瓜', '成人漫画'}

    def homeContent(self, filter):
        self._select_best_site()
        self._ensure_session()

        classes = []
        filters = {}

        for cat in self._categories:
            cid = str(cat.get('contentId', ''))
            title = cat.get('title', '')
            if not cid or not title or title in self._CATEGORY_BLACKLIST:
                continue
            classes.append({'type_id': cid, 'type_name': title})

            cat_filters = []
            sub_cats = [v for v in self._video_type_list if str(v.get('typePid', '')) == cid]
            if sub_cats:
                sub_values = [{'n': '全部', 'v': ''}]
                for sc in sub_cats:
                    sc_id = str(sc.get('typeId', ''))
                    sc_name = sc.get('typeName', '')
                    if sc_id and sc_name:
                        sub_values.append({'n': sc_name, 'v': sc_id})
                if len(sub_values) > 1:
                    cat_filters.append({'key': 'label', 'name': '分类', 'value': sub_values})

            first_level = [v for v in self._video_type_list
                           if str(v.get('typePid', '')) == '0' and str(v.get('typeId', '')) == cid]
            if first_level:
                tags_str = first_level[0].get('tags', '')
                if tags_str:
                    tag_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                    if tag_list:
                        tag_values = [{'n': '全部', 'v': ''}]
                        for t in tag_list:
                            tag_values.append({'n': t, 'v': t})
                        cat_filters.append({'key': 'tag', 'name': '标签', 'value': tag_values})

            cat_filters.append({'key': 'sort', 'name': '排序', 'value': [
                {'n': '最近更新', 'v': '0'},
                {'n': '最多播放', 'v': '1'},
                {'n': '最多收藏', 'v': '2'},
            ]})
            if cat_filters:
                filters[cid] = cat_filters

        classes.append({'type_id': 'actor', 'type_name': '女优'})
        _actors_filters = []
        _actors_filters.append({'key': 'height', 'name': '身高', 'value': [{'n': '身高', 'v': ''}] + [{'n': f'{h}cm', 'v': str(h)} for h in range(150, 165)]})
        _actors_filters.append({'key': 'cup', 'name': '罩杯', 'value': [{'n': '罩杯', 'v': ''}] + [{'n': f'{c}罩杯', 'v': c} for c in 'ABCDEFG']})
        _actors_filters.append({'key': 'birthday', 'name': '年龄', 'value': [{'n': '年龄', 'v': ''}] + [{'n': f'{y}年', 'v': str(y)} for y in range(2002, 1975, -1)]})
        _actors_filters.append({'key': 'debut', 'name': '出道', 'value': [{'n': '出道', 'v': ''}] + [{'n': f'{y}年', 'v': str(y)} for y in range(2025, 2000, -1)]})
        filters['actor'] = _actors_filters
        classes.append({'type_id': 'topic', 'type_name': '专题'})

        # 获取首页推荐
        home_videos = self.categoryContent('home', 1, '', {})
        return {
            'class': classes,
            'filters': filters,
            'type': '影视',
            'list': home_videos.get('list', []),
            'page': home_videos.get('page', 1),
            'pagecount': home_videos.get('pagecount', 1),
            'limit': home_videos.get('limit', 0),
            'total': home_videos.get('total', 0),
        }

    def homeVideoContent(self, tid, pg, filter, extend):
        return self.categoryContent(tid or 'home', pg, filter, extend)

    # ============================================================
    # 分类列表（增强兼容性）
    # ============================================================
    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid)
        pg = int(pg)
        self._select_best_site()
        self._ensure_session()

        vod_list = []

        # folder 模式
        if '@' in tid:
            real_tid = tid.replace('@', '')
            if real_tid.startswith('actor_'):
                actor_id = real_tid[len('actor_'):]
                detail_resp = self._api_request('/ht/content/queryActorDetail', {'actorId': actor_id})
                actor_name = ''
                if detail_resp and detail_resp.get('code') == 10000:
                    detail_data = detail_resp.get('data', {})
                    actor_info = detail_data.get('actorDetail') or detail_data or {}
                    actor_name = actor_info.get('actorName') or actor_info.get('actor_name') or ''
                if actor_name:
                    resp = self._api_request('/ht/content/search', {
                        'keywords': actor_name,
                        'pageNo': str(pg - 1),
                        'pageSize': '20',
                    })
                else:
                    resp = self._api_request('/ht/content/queryTypeVideosH5', {
                        'actorId': actor_id,
                        'pageNo': str(pg - 1),
                        'pageSize': '20',
                        'type': '1',
                    })
                if not resp or resp.get('code') != 10000:
                    return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
                data = resp.get('data', {})
                vod_list = self._extract_videos_from_data(data)
                total_page = int(data.get('totalPage') or data.get('total_page') or 1)
                return {'list': vod_list, 'page': pg, 'pagecount': max(total_page, 1),
                        'limit': len(vod_list), 'total': max(total_page, 1) * 20}

            elif real_tid.startswith('topic_'):
                topic_id = real_tid[len('topic_'):]
                resp = self._api_request('/ht/content/queryOriTopicVideos', {
                    'topicId': topic_id,
                    'pageNo': str(pg - 1),
                    'pageSize': '20',
                })
                if not resp or resp.get('code') != 10000:
                    return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
                data = resp.get('data', {})
                vod_list = self._extract_videos_from_data(data)
                total_page = int(data.get('totalPage') or data.get('total_page') or 1)
                return {'list': vod_list, 'page': pg, 'pagecount': max(total_page, 1),
                        'limit': len(vod_list), 'total': max(total_page, 1) * 20}
            else:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

        # 女优列表
        if tid == 'actor':
            api_params = {'pageNo': str(pg - 1), 'pageSize': '20'}
            if isinstance(extend, dict):
                _actor_filter_map = {'height': 'actorHeight', 'cup': 'cupSize',
                                     'birthday': 'actorBirthday', 'debut': 'actorDebut'}
                for ek, ak in _actor_filter_map.items():
                    val = extend.get(ek, '')
                    if val:
                        api_params[ak] = val
            resp = self._api_request('/ht/content/getActors', api_params)
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
            data = resp.get('data', {})
            vod_list = self._parse_actor_list(data)
            total_page = int(data.get('totalPage') or 1)
            return {'list': vod_list, 'page': pg, 'pagecount': total_page,
                    'limit': len(vod_list), 'total': total_page * 20}

        # 专题列表
        if tid == 'topic':
            resp = self._api_request('/ht/content/getOriTopicList', {
                'pageNo': str(pg - 1),
                'pageSize': '20',
            })
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
            data = resp.get('data', {})
            vod_list = self._parse_topic_list(data)
            return {'list': vod_list, 'page': pg, 'pagecount': 50, 'limit': len(vod_list),
                    'total': len(vod_list) * 50}

        # 首页/最新/热门
        if tid in ('home', 'new', 'hot'):
            sort_map = {'home': '1', 'new': '1', 'hot': '2'}
            resp = self._api_request('/ht/content/queryTypeVideosH5', {
                'pageNo': str(pg - 1),
                'pageSize': '20',
                'sort': sort_map.get(tid, '1'),
                'type': '1',
            })
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
            data = resp.get('data', {})
            items = data.get('typeVideoList') or data.get('list') or data.get('data') or data.get('videoList') or []
            if isinstance(items, list):
                for v in items:
                    parsed = self._parse_video(v)
                    if parsed:
                        vod_list.append(parsed)
        else:
            # 数值分类
            api_params = {
                'pageNo': str(pg - 1),
                'pageSize': '20',
                'typeId': tid,
                'type': '1',
            }
            if isinstance(extend, dict):
                for key in ('label', 'tag', 'sort'):
                    val = extend.get(key, '')
                    if val:
                        api_params[key] = val
            resp = self._api_request('/ht/content/queryTypeVideosH5', api_params)
            if not resp or resp.get('code') != 10000:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
            data = resp.get('data', {})
            items = data.get('typeVideoList') or data.get('list') or data.get('data') or data.get('videoList') or []
            if isinstance(items, list):
                for v in items:
                    parsed = self._parse_video(v)
                    if parsed:
                        vod_list.append(parsed)

        total_page = int(data.get('totalPage') or 1)
        return {
            'list': vod_list,
            'page': pg,
            'pagecount': total_page,
            'limit': len(vod_list),
            'total': total_page * 20,
        }

    # ============================================================
    # 辅助提取方法
    # ============================================================
    def _extract_videos_from_data(self, data):
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (data.get('videoList') or data.get('list') or data.get('data')
                     or data.get('videos') or data.get('typeVideoList')
                     or data.get('topicVideoIdList') or data.get('searchList')
                     or data.get('contentList') or data.get('records')
                     or data.get('pageData') or [])
        else:
            return []
        if not isinstance(items, list):
            return []
        return [p for v in items if (p := self._parse_video(v))]

    @staticmethod
    def _try_get(item, *keys):
        for k in keys:
            v = item.get(k)
            if v is not None and v != '':
                return v
        return ''

    def _parse_actor_list(self, data):
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('actorList') or data.get('actors') or data.get('list') or data.get('data') or []
        else:
            return []
        if not isinstance(items, list):
            return []
        results = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            actor_id = str(self._try_get(item, 'actorId', 'contentId', 'id', 'artId', 'actor_id', 'userId'))
            actor_name = str(self._try_get(item, 'actorName', 'name', 'title', 'artName', 'actor_name', 'actor'))
            actor_img = str(self._try_get(item, 'actorPic', 'actorImg', 'img', 'avatar', 'cover',
                                          'imageUrl', 'headImg', 'head', 'photo', 'image', 'pic', 'actor_img'))
            actor_count = str(self._try_get(item, 'videoCount', 'contentCount', 'count', 'totalCount',
                                            'total', 'video_count'))
            if not actor_id or actor_id in seen:
                continue
            seen.add(actor_id)
            if not actor_img:
                actor_img = self.host + '/favicon.ico'
            remarks = f'{actor_count}部' if actor_count else ''
            results.append({
                'vod_id': 'actor_' + actor_id + '@',
                'vod_name': actor_name or ('演员' + actor_id),
                'vod_pic': self.get_proxy_image_url(actor_img),
                'vod_tag': 'folder',
                'vod_remarks': remarks,
            })
        return results

    def _parse_topic_list(self, data):
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('topicList') or data.get('oriTopicList') or data.get('list') or data.get('data') or data.get('topics') or []
        else:
            return []
        if not isinstance(items, list):
            return []
        results = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            topic_id = str(self._try_get(item, 'topicId', 'id', 'contentId', 'oriTopicId', 'topic_id'))
            topic_name = str(self._try_get(item, 'topicName', 'name', 'title', 'oriTopicName', 'topic_name', 'topic'))
            topic_img = str(self._try_get(item, 'topicPic', 'topicImg', 'img', 'cover', 'imageUrl', 'pic',
                                          'thumb', 'image', 'topic_img', 'oriTopicImg'))
            topic_count = str(self._try_get(item, 'videoCount', 'count', 'contentCount', 'totalCount',
                                            'total', 'video_count'))
            if not topic_id or topic_id in seen:
                continue
            seen.add(topic_id)
            if not topic_img:
                topic_img = self.host + '/favicon.ico'
            remarks = f'{topic_count}部' if topic_count else ''
            results.append({
                'vod_id': 'topic_' + topic_id + '@',
                'vod_name': topic_name or ('专题' + topic_id),
                'vod_pic': self.get_proxy_image_url(topic_img),
                'vod_tag': 'folder',
                'vod_remarks': remarks,
            })
        return results

    def _parse_video(self, item):
        if item.get('contentType') != 1:
            return None
        vid = str(item.get('contentId') or item.get('id') or item.get('videoId') or '')
        title = item.get('title') or item.get('name') or item.get('videoTitle') or ''
        pic = item.get('img') or item.get('cover') or item.get('coverUrl') or item.get('pic') or item.get('imageUrl') or ''
        remarks = item.get('duration') or item.get('playCount') or item.get('remark') or ''
        if remarks and str(remarks).isdigit():
            remarks = self._fmt_duration(remarks)
        return {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self.get_proxy_image_url(pic) if pic else '',
            'vod_remarks': str(remarks) if remarks else '',
        }

    # ============================================================
    # 详情
    # ============================================================
    def detailContent(self, ids):
        did = ids[0] if isinstance(ids, list) else ids
        self._select_best_site()
        self._ensure_session()
        resp = self._api_request('/ht/content/detail', {'contentId': str(did)})
        if not resp or resp.get('code') != 10000:
            return {'list': []}
        detail = resp.get('data', {})
        if not detail:
            return {'list': []}
        title = detail.get('title') or detail.get('name') or detail.get('videoTitle') or '未知标题'
        pic = detail.get('cover') or detail.get('coverUrl') or detail.get('img') or detail.get('imageUrl') or ''
        desc = detail.get('description') or detail.get('desc') or detail.get('intro') or ''
        duration = detail.get('duration', 0)
        actor = detail.get('actor') or detail.get('actors') or ''
        play_url = detail.get('videoUrl') or detail.get('playUrl') or detail.get('url') or detail.get('m3u8Url') or detail.get('sl') or ''
        vod_play_url = '播放$' + str(did)
        if play_url:
            vod_play_url = '播放$' + play_url
        return {'list': [{
            'vod_id': str(did),
            'vod_name': title,
            'vod_pic': self.get_proxy_image_url(pic) if pic else '',
            'vod_actor': str(actor) if actor else '',
            'vod_director': '',
            'vod_content': desc,
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': self._fmt_duration(duration),
            'vod_play_from': '蜜桃视频',
            'vod_play_url': vod_play_url,
            'type': 'video',
        }]}

    # ============================================================
    # 搜索
    # ============================================================
    def searchContent(self, key, quick, pg=1):
        self._select_best_site()
        self._ensure_session()
        pg = int(pg)
        resp = self._api_request('/ht/content/search', {
            'keywords': key,
            'pageNo': pg - 1,
            'pageSize': 20,
        })
        if not resp or resp.get('code') != 10000:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        data = resp.get('data', {})
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('searchList') or data.get('list') or data.get('data') or data.get('videoList') or data.get('records') or data.get('resultList') or data.get('content') or []
        else:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        if not isinstance(items, list):
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        vod_list = [p for v in items if (p := self._parse_video(v))]
        total_page = int(data.get('totalPage') or 1) if isinstance(data, dict) else max(1, len(vod_list) // 20)
        return {
            'list': vod_list,
            'page': pg,
            'pagecount': total_page,
            'limit': len(vod_list),
            'total': total_page * 20,
        }

    # ============================================================
    # 播放
    # ============================================================
    def playerContent(self, flag, id, vipFlags=None):
        url = id.split('$')[-1]
        if url.startswith('http'):
            return {
                'parse': 0,
                'url': url,
                'jx': 0,
                'header': {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.host + '/',
                },
            }
        self._select_best_site()
        self._ensure_session()
        resp = self._api_request('/ht/content/detail', {'contentId': url})
        if not resp or resp.get('code') != 10000:
            return {'parse': 0, 'url': '', 'jx': 0}
        detail = resp.get('data', {})
        play_url = detail.get('videoUrl') or detail.get('playUrl') or detail.get('url') or detail.get('m3u8Url') or detail.get('sl') or ''
        return {
            'parse': 0,
            'url': play_url,
            'jx': 0,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            },
        }

    # ============================================================
    # 图片代理（原样）
    # ============================================================
    def localProxy(self, params):
        try:
            if params.get('type') != PROXY_TYPE:
                return [404, 'text/plain', 'not found']
            img_url = params.get('url', '')
            if not img_url:
                return [400, 'text/plain', 'missing url']
            img_url = unquote(img_url)
            r = requests.get(img_url, headers={
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.host + '/',
            }, timeout=TIMEOUT, verify=False)
            if r.status_code != 200:
                return [404, 'text/plain', 'image not found']
            data = r.content
            # XOR 0x88 解密
            if data[:2] != b'\xff\xd8' and data[:4] != b'\x89PNG' \
                    and not (data[:4] == b'RIFF' and data[8:12] == b'WEBP'):
                decoded = bytes(b ^ 0x88 for b in data)
                if decoded[:2] == b'\xff\xd8' or decoded[:4] == b'\x89PNG' \
                        or (decoded[:4] == b'RIFF' and decoded[8:12] == b'WEBP'):
                    data = decoded
            if data[:2] == b'\xff\xd8':
                return [200, 'image/jpeg', data, {'Content-Length': str(len(data))}]
            elif data[:4] == b'\x89PNG':
                return [200, 'image/png', data, {'Content-Length': str(len(data))}]
            elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                return [200, 'image/webp', data, {'Content-Length': str(len(data))}]
            else:
                mime = r.headers.get('Content-Type', 'image/jpeg')
                if mime.startswith('image/'):
                    return [200, mime, data, {'Content-Length': str(len(data))}]
                return [404, 'text/plain', 'invalid image format']
        except Exception as e:
            log(f"代理错误: {e}")
            return [500, 'text/plain', 'proxy error']
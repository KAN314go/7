# coding=utf-8
# NewXVideos OK影视/猫影视/TVBox 通用版
# 可直接丢 jar 使用

import requests
import re
import sys
from base.spider import Spider

sys.path.append('..')

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://newxvideos.pages.dev/"
}

host = "https://newxvideos.pages.dev"


class Spider(Spider):

    def getName(self):
        return "NewXVideos"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    # 首页分类
    def homeContent(self, filter):

        classes = [
            {"type_id": "new", "type_name": "最新"},
            {"type_id": "hot", "type_name": "热门"},
            {"type_id": "top", "type_name": "推荐"},
            {"type_id": "anime", "type_name": "动漫"},
            {"type_id": "国产自拍", "type_name": "国产自拍"},
            {"type_id": "自拍偷拍", "type_name": "自拍偷拍"}
        ]

        return {
            "class": classes
        }

    # 首页推荐
    def homeVideoContent(self):

        videos = []

        try:

            r = requests.get(
                host,
                headers=headers,
                timeout=10
            )

            html = r.text

            data = re.findall(
                r'href="(/video/.*?)".*?<img.*?src="(.*?)".*?alt="(.*?)"',
                html,
                re.S
            )

            for v in data:

                vod_id = host + v[0]
                vod_pic = v[1]
                vod_name = v[2]

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })

        except Exception as e:
            print(e)

        return {
            "list": videos
        }

    # 分类
    def categoryContent(self, tid, pg, filter, ext):

        videos = []

        page = pg if pg else "1"

        try:

            if tid == "new":
                url = host + "/page/" + str(page)

            else:
                url = host + "/search/" + tid + "/page/" + str(page)

            r = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            html = r.text

            data = re.findall(
                r'href="(/video/.*?)".*?<img.*?src="(.*?)".*?alt="(.*?)"',
                html,
                re.S
            )

            for v in data:

                vod_id = host + v[0]
                vod_pic = v[1]
                vod_name = v[2]

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })

        except Exception as e:
            print(e)

        return {
            "list": videos,
            "page": page,
            "pagecount": 9999,
            "limit": 90,
            "total": 999999
        }

    # 详情
    def detailContent(self, ids):

        did = ids[0]

        videos = []

        try:

            r = requests.get(
                did,
                headers=headers,
                timeout=10
            )

            html = r.text

            title = ""

            t = re.search(
                r'<title>(.*?)</title>',
                html,
                re.S
            )

            if t:
                title = t.group(1)

            pic = ""

            p = re.search(
                r'poster="(.*?)"',
                html,
                re.S
            )

            if p:
                pic = p.group(1)

            play = ""

            m3u8 = re.search(
                r'(https?://.*?\.m3u8.*?)["\']',
                html,
                re.S
            )

            mp4 = re.search(
                r'(https?://.*?\.mp4.*?)["\']',
                html,
                re.S
            )

            if m3u8:
                play = m3u8.group(1)

            elif mp4:
                play = mp4.group(1)

            vod = {
                "vod_id": did,
                "vod_name": title,
                "vod_pic": pic,
                "type_name": "成人视频",
                "vod_year": "",
                "vod_area": "",
                "vod_remarks": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": title,
                "vod_play_from": "在线播放",
                "vod_play_url": "播放$" + play
            }

            videos.append(vod)

        except Exception as e:
            print(e)

        return {
            "list": videos
        }

    # 播放
    def playerContent(self, flag, id, vipFlags):

        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": headers
        }

    # 搜索
    def searchContentPage(self, key, quick, page):

        videos = []

        try:

            url = host + "/search/" + key + "/page/" + str(page)

            r = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            html = r.text

            data = re.findall(
                r'href="(/video/.*?)".*?<img.*?src="(.*?)".*?alt="(.*?)"',
                html,
                re.S
            )

            for v in data:

                vod_id = host + v[0]
                vod_pic = v[1]
                vod_name = v[2]

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_remarks": ""
                })

        except Exception as e:
            print(e)

        return {
            "list": videos,
            "page": page,
            "pagecount": 9999,
            "limit": 90,
            "total": 999999
        }

    def searchContent(self, key, quick):
        return self.searchContentPage(key, quick, "1")

    # 本地代理
    def localProxy(self, params):

        if params['type'] == "m3u8":
            return self.proxyM3u8(params)

        elif params['type'] == "media":
            return self.proxyMedia(params)

        elif params['type'] == "ts":
            return self.proxyTs(params)

        return None
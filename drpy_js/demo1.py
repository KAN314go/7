# -*- coding: utf-8 -*-
# by @嗷呜
import base64
import sys
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self,extend=""):
        pass

    def aes(self,content):
        key = b"f5d965df75336270"
        iv = b'97b60394abc2fbe1'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(content), AES.block_size)
        return base64.b64encode(pt).decode()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.55 Safari/537.36',
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="141", "Google Chrome";v="141"',
        'Origin': 'https://xgne8.dyxobic.cc',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    def homeVideoContent(self):
        data=pq(self.fetch('https://xgne8.dyxobic.cc/videos/guochan-sm/').content)
        vs=data("ul.video-items > li").eq(0)
        vod={
            "vod_id": "1",
            "vod_name": "1",
            "vod_pic": self.getProxyUrl()+"&url="+vs("img").attr("data-src"),
        }
        return {'list': [vod]}
    def localProxy(self, params):
        req=self.fetch(params["url"],headers=self.headers)
        return [200,"image/png",self.aes(req.content)]

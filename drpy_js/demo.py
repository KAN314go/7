from base64 import b64encode
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import requests
def aes(bytes):
    key = b"f5d965df75336270"
    iv = b'97b60394abc2fbe1'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    pt = unpad(cipher.decrypt(bytes), AES.block_size)
    return b64encode(pt).decode()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.55 Safari/537.36',
    'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="141", "Google Chrome";v="141"',
    'Origin': 'https://xgne8.dyxobic.cc',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

response = requests.get('https://pic.rulbbz.cn/upload_01/upload/20251122/2025112216124789358.jpeg', headers=headers)
print(aes(response.content))

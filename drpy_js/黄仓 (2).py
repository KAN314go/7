# -*- coding: utf-8 -*-
import re
import urllib.parse
import requests
import urllib3

# 禁用证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_dynamic_host():
    origin = "http://hscangku.com"
    fallback = "http://789067.xyz"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"[*] 步骤 1: 开始请求固定入口页 -> {origin}")
    try:
        res = requests.get(origin, headers=headers, verify=False, timeout=8)
        print(f"    - 入口页 HTTP 状态码: {res.status_code}")
        
        _RE_JUMP = re.compile(r'strU\s*=\s*["\'](.*?)["\']', re.IGNORECASE)
        match = _RE_JUMP.search(res.text)
        
        if not match:
            print("[-] 步骤 2 失败: 未能在页面源码中匹配到 'strU' 变量！")
            return fallback
            
        jump_str = match.group(1)
        print(f"[+] 步骤 2 成功: 提取到原始跳转变量 strU = {jump_str}")
        
        # 【核心修复】：处理 JS 字符串拼接导致丢失的 window.location
        if '?u=' in jump_str:
            if jump_str.endswith('?u='):
                encoded_origin = urllib.parse.quote(origin, safe="")
                test_url = jump_str + encoded_origin + "&p=/"
            else:
                test_url = jump_str + "&p=/"
            print(f"    - 检测到反代网关格式，已补全原站参数并组装: {test_url}")
        else:
            test_url = urllib.parse.urljoin(origin, jump_str)
            print(f"    - 检测为标准路径格式: {test_url}")
            
        print(f"\n[*] 步骤 3: 开始追踪真实落地页 -> 发起请求: {test_url}")
        
        res_jump = requests.get(test_url, headers=headers, verify=False, allow_redirects=True, timeout=10)
        
        print(f"    - 追踪结束！最终响应状态码: {res_jump.status_code}")
        print(f"    - requests 最终停留的 URL: {res_jump.url}")
        
        # 步骤 4: 防御某些站点使用 JS 进行二次隐蔽跳转
        m_js = re.search(r'location\.href\s*=\s*["\'](.*?)["\']', res_jump.text)
        if m_js:
            js_target = m_js.group(1)
            print(f"[!] 步骤 4: 发现二次 JS 跳转代码 -> {js_target}")
            parsed = urllib.parse.urlparse(js_target)
            final_host = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
            print(f"\n[🎉] 成功提取到终极真实域名: {final_host}")
            return final_host
            
        # 解析最终落地的 URL
        parsed = urllib.parse.urlparse(res_jump.url)
        
        if parsed.netloc and "hk234" not in parsed.netloc:
            final_host = f"{parsed.scheme}://{parsed.netloc}".rstrip('/')
            print(f"[+] 步骤 4: 成功穿透网关，拿到了真实后端域名！")
            print(f"\n[🎉] 成功提取到终极真实域名: {final_host}")
            return final_host
        else:
            print("[-] 步骤 4 结论: 落地 URL 依然是代理网关，说明该网关是全职反代，并未执行重定向。")
            print(f"\n[⚠️] 必须使用【网关代理组装模式】，底层通信地址为: {parsed.scheme}://{parsed.netloc}")
            return f"{parsed.scheme}://{parsed.netloc}"
            
    except Exception as e:
        print(f"\n[-] 网络或解析异常: {e}")
        
    print(f"\n[*] 自动获取失败，返回兜底直连域名 -> {fallback}")
    return fallback

if __name__ == "__main__":
    test_dynamic_host()

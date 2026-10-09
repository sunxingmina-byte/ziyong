import json
import os
import socket
import tempfile
import time
import random
import ipaddress
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# ================= 配置 =================
SOURCE_URL = "https://sub.cmliussss.net/vpngate?token=20260924233538"
OUTPUT_FILE = Path("vpngate.txt")
CACHE_FILE = Path("geo_cache.json")

# 多优选域名列表 (你可以继续添加)
PREF_DOMAINS = ["cf.877774.xyz:443","saas.sin.fan:443","www.shopify.com"] 

MAX_RESPONSE_SIZE = 5 * 1024 * 1024
TIMEOUT = 20
MIN_VALID_NODES = 5
GEO_API = "https://ipwho.is/{}"
CACHE_EXPIRY_DAYS = 30 
# =======================================

COUNTRY_NAMES = {
    "US": "美国", "CA": "加拿大", "GB": "英国", "DE": "德国", "FR": "法国",
    "JP": "日本", "KR": "韩国", "CN": "中国", "HK": "中国香港", "TW": "中国台湾",
    "SG": "新加坡", "AU": "澳大利亚", "BR": "巴西", "RU": "俄罗斯"
}

def is_node_alive(hostname, port=443, timeout=0.8):
    """简单的 TCP 连通性测试"""
    try:
        with socket.create_connection((hostname, port), timeout=timeout):
            return True
    except:
        return False

def fetch_source():
    req = Request(SOURCE_URL, headers={"User-Agent": "Updater/1.0"})
    with urlopen(req, timeout=TIMEOUT) as res:
        if res.status != 200: raise RuntimeError(f"HTTP {res.status}")
        data = res.read(MAX_RESPONSE_SIZE)
        return data.decode("utf-8", errors="replace")

def load_cache():
    if not CACHE_FILE.exists(): return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        now = time.time()
        return {k: v for k, v in data.items() if now - v.get("ts", 0) < CACHE_EXPIRY_DAYS * 86400}
    except: return {}

def lookup_country(ip, cache):
    if ip in cache: return cache[ip]["country"]
    try:
        with urlopen(GEO_API.format(ip), timeout=10) as res:
            data = json.loads(res.read().decode())
            code = str(data.get("country_code", "")).upper()
            country = COUNTRY_NAMES.get(code, data.get("country", "未知"))
            cache[ip] = {"country": country, "ts": time.time()}
            time.sleep(1.2)
            return country
    except: return "未知"

def process_data(text, cache):
    result = []
    seen = set()
    lines = text.splitlines()

    for line in lines:
        line = line.strip()
        if not line.startswith("sstp://"): continue
        
        hostname = urlsplit(line).hostname
        if not hostname: continue
        
        # 1. 存活检测
        if not is_node_alive(hostname):
            continue

        # 2. 获取 IP 并查询国家
        try:
            ip = str(socket.gethostbyname(hostname))
            if ipaddress.ip_address(ip).is_global:
                country = lookup_country(ip, cache)
                
                # 3. 多域名随机分配
                domain = random.choice(PREF_DOMAINS)
                final = f"{domain}#{country}${line}"

                if final not in seen:
                    seen.add(final)
                    result.append(final)
        except: continue
    return result

def main():
    try:
        text = fetch_source()
        cache = load_cache()
        nodes = process_data(text, cache)
        
        if len(nodes) < MIN_VALID_NODES:
            raise RuntimeError(f"有效节点数 {len(nodes)} 低于阈值 {MIN_VALID_NODES}")
            
        content = "\n".join(nodes) + "\n"
        fd, tmp = tempfile.mkstemp(dir=".", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(content)
        os.replace(tmp, OUTPUT_FILE)
        
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
            
        print(f"成功更新 {len(nodes)} 个节点")
    except Exception as e:
        print(f"执行失败: {e}")
        exit(1)

if __name__ == "__main__": main()

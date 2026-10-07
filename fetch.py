import ipaddress
import json
import os
import socket
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


# =========================
# 配置
# =========================

SOURCE_URL = (
    "https://sub.cmliussss.net/"
    "vpngate?token=20260924233538"
)

OUTPUT_FILE = Path("vpngate.txt")
CACHE_FILE = Path("geo_cache.json")

PREFIX = "cf.877774.xyz:443#"

# 源站最大允许下载 5 MB
MAX_RESPONSE_SIZE = 5 * 1024 * 1024

# HTTP 请求超时
TIMEOUT = 30

# IP 地理位置接口
GEO_API = "https://ipwho.is/{}"

# 两次 GeoIP 查询之间稍微等待一下
GEO_REQUEST_INTERVAL = 1.1


# =========================
# 国家名称
# =========================

COUNTRY_NAMES = {
    "US": "美国",
    "CA": "加拿大",
    "GB": "英国",
    "DE": "德国",
    "FR": "法国",
    "NL": "荷兰",
    "BE": "比利时",
    "LU": "卢森堡",
    "CH": "瑞士",
    "AT": "奥地利",
    "IT": "意大利",
    "ES": "西班牙",
    "PT": "葡萄牙",
    "IE": "爱尔兰",
    "DK": "丹麦",
    "SE": "瑞典",
    "NO": "挪威",
    "FI": "芬兰",
    "IS": "冰岛",
    "PL": "波兰",
    "CZ": "捷克",
    "SK": "斯洛伐克",
    "HU": "匈牙利",
    "RO": "罗马尼亚",
    "BG": "保加利亚",
    "GR": "希腊",
    "UA": "乌克兰",
    "RU": "俄罗斯",
    "TR": "土耳其",

    "JP": "日本",
    "KR": "韩国",
    "CN": "中国",
    "HK": "中国香港",
    "MO": "中国澳门",
    "TW": "中国台湾",

    "SG": "新加坡",
    "MY": "马来西亚",
    "TH": "泰国",
    "VN": "越南",
    "PH": "菲律宾",
    "ID": "印度尼西亚",
    "IN": "印度",

    "AU": "澳大利亚",
    "NZ": "新西兰",

    "BR": "巴西",
    "AR": "阿根廷",
    "CL": "智利",
    "MX": "墨西哥",
    "CO": "哥伦比亚",

    "ZA": "南非",
    "EG": "埃及",
    "IL": "以色列",
    "AE": "阿联酋",
    "SA": "沙特阿拉伯",
}


# =========================
# 下载源数据
# =========================

def fetch_source():
    print("正在获取源站数据...")

    request = Request(
        SOURCE_URL,
        headers={
            "User-Agent": "ziyong-vpngate-updater/1.0"
        },
    )

    try:
        with urlopen(request, timeout=TIMEOUT) as response:

            status = getattr(response, "status", 200)

            if status != 200:
                raise RuntimeError(
                    f"源站返回 HTTP {status}"
                )

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_length:
                try:
                    if int(content_length) > MAX_RESPONSE_SIZE:
                        raise RuntimeError(
                            "源站返回的数据超过 5 MB"
                        )
                except ValueError:
                    pass

            chunks = []
            total_size = 0

            while True:
                chunk = response.read(64 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_RESPONSE_SIZE:
                    raise RuntimeError(
                        "源站返回的数据超过 5 MB"
                    )

                chunks.append(chunk)

            data = b"".join(chunks)

            return data.decode(
                "utf-8",
                errors="replace"
            )

    except HTTPError as e:
        raise RuntimeError(
            f"源站 HTTP 错误: {e.code}"
        ) from e

    except URLError as e:
        raise RuntimeError(
            f"无法连接源站: {e.reason}"
        ) from e


# =========================
# 读取缓存
# =========================

def load_cache():
    if not CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(
            CACHE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception as e:
        print(
            f"警告：读取 GeoIP 缓存失败: {e}"
        )

    return {}


# =========================
# 保存缓存
# =========================

def save_cache(cache):
    content = json.dumps(
        cache,
        ensure_ascii=False,
        indent=2,
        sort_keys=True
    ) + "\n"

    CACHE_FILE.write_text(
        content,
        encoding="utf-8"
    )


# =========================
# DNS 解析
# =========================

def resolve_public_ip(hostname):
    """
    把 SSTP hostname 解析成公网 IP。
    如果本身就是 IP，则直接返回。
    """

    try:
        ip = ipaddress.ip_address(hostname)

        if ip.is_global:
            return str(ip)

        return None

    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM
        )

    except socket.gaierror:
        return None

    for item in addresses:
        sockaddr = item[4]

        if not sockaddr:
            continue

        ip_string = sockaddr[0]

        try:
            ip = ipaddress.ip_address(ip_string)

            if ip.is_global:
                return str(ip)

        except ValueError:
            continue

    return None


# =========================
# IP → 国家
# =========================

def lookup_country(ip, cache):
    # 已经查询过
    if ip in cache:
        return cache[ip]

    print(f"查询国家: {ip}")

    url = GEO_API.format(ip)

    request = Request(
        url,
        headers={
            "User-Agent": "ziyong-vpngate-updater/1.0"
        },
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8",
                    errors="replace"
                )
            )

        if not data.get("success"):
            country = "未知"
        else:
            country_code = str(
                data.get(
                    "country_code",
                    ""
                )
            ).upper()

            country = COUNTRY_NAMES.get(
                country_code,
                data.get("country", "未知")
            )

            if not country:
                country = "未知"

    except Exception as e:
        print(
            f"GeoIP 查询失败 {ip}: {e}"
        )
        country = "未知"

    cache[ip] = country

    # 防止连续请求过快
    time.sleep(GEO_REQUEST_INTERVAL)

    return country


# =========================
# 从 SSTP URL 获取 hostname
# =========================

def extract_hostname(sstp_url):
    try:
        parsed = urlsplit(sstp_url)

        hostname = parsed.hostname

        if hostname:
            return hostname

    except Exception:
        pass

    return None


# =========================
# 处理 SSTP
# =========================

def process_data(text, cache):
    result = []
    seen = set()

    lines = text.splitlines()

    for raw_line in lines:

        line = raw_line.strip()

        # 空行
        if not line:
            continue

        # 只处理 SSTP
        if not line.startswith("sstp://"):
            continue

        # 解析 hostname
        hostname = extract_hostname(line)

        if not hostname:
            print(
                f"无法解析 SSTP，跳过: {line}"
            )
            continue

        # hostname → IP
        ip = resolve_public_ip(hostname)

        if not ip:
            print(
                f"无法解析公网 IP，跳过: {hostname}"
            )
            continue

        # IP → 国家
        country = lookup_country(
            ip,
            cache
        )

        # 最终格式：
        #
        # cf.877774.xyz:443#美国$sstp://...
        #
        final_line = (
            f"{PREFIX}"
            f"{country}$"
            f"{line}"
        )

        # 去重
        if final_line in seen:
            continue

        seen.add(final_line)
        result.append(final_line)

    return result


# =========================
# 原子写入
# =========================

def atomic_write(path, content):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fd, temp_path = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=path.parent
    )

    try:

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(
            temp_path,
            path
        )

    except Exception:

        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

        raise


# =========================
# 保存 TXT
# =========================

def save_output(lines):

    # 防止源站异常导致原文件被清空
    if not lines:
        raise RuntimeError(
            "没有获取到任何有效 SSTP 节点，"
            "拒绝覆盖现有 vpngate.txt"
        )

    content = "\n".join(lines) + "\n"

    atomic_write(
        OUTPUT_FILE,
        content
    )


# =========================
# 主程序
# =========================

def main():

    print("==============================")
    print("ziyong VPNGate updater")
    print("==============================")

    # 1. 获取源数据
    source_text = fetch_source()

    print(
        f"源数据行数: "
        f"{len(source_text.splitlines())}"
    )

    # 2. 加载 GeoIP 缓存
    cache = load_cache()

    print(
        f"已有 GeoIP 缓存: "
        f"{len(cache)}"
    )

    # 3. 处理
    result = process_data(
        source_text,
        cache
    )

    print(
        f"有效 SSTP 节点: "
        f"{len(result)}"
    )

    # 4. 没有节点直接失败
    if not result:
        raise RuntimeError(
            "没有生成有效节点"
        )

    # 5. 保存 TXT
    save_output(result)

    # 6. 保存 GeoIP 缓存
    save_cache(cache)

    print(
        f"vpngate.txt 已更新"
    )

    print(
        f"GeoIP 缓存数量: "
        f"{len(cache)}"
    )


if __name__ == "__main__":
    main()

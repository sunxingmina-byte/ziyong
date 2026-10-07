from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import os
import tempfile

SOURCE_URL = "https://sub.cmliussss.net/vpngate?token=20260924233538"

OUTPUT_FILE = Path("vpngate.txt")

PREFIX = "cf.877774.xyz:443#vpngate$"

# 最大允许下载 5 MB
MAX_RESPONSE_SIZE = 5 * 1024 * 1024

# 请求超时时间
TIMEOUT = 30


def fetch_data():
    request = Request(
        SOURCE_URL,
        headers={
            "User-Agent": "ziyong-vpngate-updater/1.0"
        }
    )

    try:
        with urlopen(request, timeout=TIMEOUT) as response:

            # 检查 HTTP 状态
            status = getattr(response, "status", 200)

            if status != 200:
                raise RuntimeError(
                    f"源站返回 HTTP {status}"
                )

            # 如果服务器提供 Content-Length，提前检查
            content_length = response.headers.get("Content-Length")

            if content_length:
                try:
                    if int(content_length) > MAX_RESPONSE_SIZE:
                        raise RuntimeError(
                            f"响应过大: {content_length} bytes"
                        )
                except ValueError:
                    pass

            # 分块读取
            chunks = []
            total_size = 0

            while True:
                chunk = response.read(64 * 1024)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_RESPONSE_SIZE:
                    raise RuntimeError(
                        "源站返回的数据超过大小限制"
                    )

                chunks.append(chunk)

            data = b"".join(chunks)

            return data.decode("utf-8", errors="replace")

    except HTTPError as e:
        raise RuntimeError(
            f"HTTP 请求失败: {e.code}"
        ) from e

    except URLError as e:
        raise RuntimeError(
            f"无法连接源站: {e.reason}"
        ) from e


def process_data(text):
    result = []
    seen = set()

    for raw_line in text.splitlines():

        line = raw_line.strip()

        # 跳过空行
        if not line:
            continue

        # 只接受 SSTP
        if not line.startswith("sstp://"):
            continue

        # 添加前缀
        final_line = PREFIX + line

        # 去重
        if final_line in seen:
            continue

        seen.add(final_line)
        result.append(final_line)

    return result


def save_data(lines):
    if not lines:
        raise RuntimeError(
            "没有获取到有效的 SSTP 节点，拒绝覆盖原文件"
        )

    content = "\n".join(lines) + "\n"

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # 使用临时文件，然后原子替换
    fd, temp_path = tempfile.mkstemp(
        prefix="vpngate_",
        suffix=".tmp",
        dir=OUTPUT_FILE.parent
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, OUTPUT_FILE)

    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

        raise


def main():
    print("================================")
    print("VPNGate data updater")
    print("================================")

    print("正在获取源站数据...")

    text = fetch_data()

    print(
        f"源站返回 {len(text.encode('utf-8'))} bytes"
    )

    lines = process_data(text)

    print(
        f"发现有效 SSTP 节点: {len(lines)}"
    )

    save_data(lines)

    print(
        f"已保存到: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}")
        raise

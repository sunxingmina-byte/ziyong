import requests
from pathlib import Path

SOURCE_URL = "https://sub.cmliussss.net/vpngate?token=20260924233538"
OUTPUT_FILE = Path("vpngate.txt")
PREFIX = "cf.877774.xyz:443$"


def fetch_data():
    response = requests.get(
        SOURCE_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def process_data(text):
    result = []
    seen = set()

    for line in text.splitlines():
        line = line.strip()

        # 忽略空行
        if not line:
            continue

        # 只保留 SSTP
        if not line.startswith("sstp://"):
            continue

        # 去除可能已经存在的前缀，防止重复添加
        if line.startswith(PREFIX):
            final_line = line
        else:
            final_line = PREFIX + line

        # 去重，同时保持原始顺序
        if final_line not in seen:
            seen.add(final_line)
            result.append(final_line)

    return result


def save_data(lines):
    content = "\n".join(lines)

    if content:
        content += "\n"

    OUTPUT_FILE.write_text(
        content,
        encoding="utf-8"
    )


def main():
    print("正在获取数据...")

    text = fetch_data()
    lines = process_data(text)

    save_data(lines)

    print(f"原始数据行数: {len(text.splitlines())}")
    print(f"有效 SSTP 数量: {len(lines)}")
    print(f"已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""批量抓取 tldr-pages 中文命令库，清洗成知识库可用的 Markdown。运行：python fetch_tldr.py"""

import io
import os
import re
import sys
import zipfile
import urllib.request

ZIP_URL = "https://codeload.github.com/tldr-pages/tldr/zip/refs/heads/main"
OUT_DIR = os.path.join(os.path.dirname(__file__), "knowledge_base", "tldr")


def download_zip():
    """下载 tldr 仓库压缩包，返回原始字节。"""
    print(f"下载 tldr 仓库压缩包（约 20MB）: {ZIP_URL}")
    with urllib.request.urlopen(ZIP_URL, timeout=120) as resp:
        return resp.read()


def parse_page(text, rel_path):
    """把一个 tldr 页面清洗成规整文本；解析不出标题返回 None。"""
    title, desc, examples = "", "", []
    for line in text.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("> "):
            desc += line[2:].strip() + " "
        elif line.startswith("- "):
            examples.append(line[2:].strip())
    if not title:
        return None

    m = re.search(r"pages\.zh/([^/]+)/", rel_path)
    category = m.group(1) if m else "general"

    parts = [f"命令: {title}", f"分类: {category}", f"说明: {desc.strip()}"]
    if examples:
        parts.append("常用示例:")
        parts += [f"  {e}" for e in examples]
    return "\n".join(parts)


def main():
    data = download_zip()
    os.makedirs(OUT_DIR, exist_ok=True)
    count = 0

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if "/pages.zh/" not in name or not name.endswith(".md"):
                continue
            raw = zf.read(name).decode("utf-8", errors="ignore")
            rel = name.split("/pages.zh/")[-1]
            cleaned = parse_page(raw, name)
            if not cleaned:
                continue
            out_name = rel.replace("/", "__")
            with open(os.path.join(OUT_DIR, out_name), "w", encoding="utf-8") as f:
                f.write(cleaned)
            count += 1

    print(f"完成: 共导出 {count} 条命令速查到 {OUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"失败: {e}", file=sys.stderr)
        sys.exit(1)

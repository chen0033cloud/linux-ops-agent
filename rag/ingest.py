# -*- coding: utf-8 -*-
"""把 knowledge_base/ 下的 Markdown 切块、向量化，写入 FAISS 本地索引。运行：python rag/ingest.py（只跑一次）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import DirectoryLoader, TextLoader

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain_community.vectorstores import FAISS
from rag.query import get_embeddings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(BASE_DIR, "knowledge_base")
INDEX_DIR = os.path.join(BASE_DIR, "vector_store")


def main():
    """加载文档 → 切块 → 向量化 → 保存索引，四步完成建库。"""

    # 第一步：加载知识库里所有 Markdown 文档
    print("加载知识库文档 ...")
    docs = []
    for subdir, glob in [("tldr", "**/*.md"), (".", "*.md")]:
        path = os.path.join(KB_DIR, subdir)
        if not os.path.isdir(path):
            continue
        # 必须指定 loader_cls=TextLoader，否则 .md 会走默认 unstructured 加载器（未安装会报错）
        loader = DirectoryLoader(
            path, glob=glob, loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
        )
        docs.extend(loader.load())
    print(f"共加载 {len(docs)} 个文档")

    # 第二步：切块——每块最多 500 字，相邻块重叠 50 字
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    print(f"切分为 {len(chunks)} 个文本块")

    # 第三步：向量化并写入 FAISS 索引
    print("向量化并写入 FAISS 索引 ...")
    store = FAISS.from_documents(chunks, get_embeddings())
    os.makedirs(INDEX_DIR, exist_ok=True)
    os.chdir(BASE_DIR)   # 切到项目根目录用相对路径保存（FAISS 在 Windows 下打不开含中文的绝对路径）
    store.save_local("vector_store")
    print(f"完成: 索引已保存到 {INDEX_DIR}")


if __name__ == "__main__":
    if sys.platform == "win32":
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()

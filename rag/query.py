# -*- coding: utf-8 -*-
"""共用工具：load_env / get_embeddings / get_llm / faiss_dir。"""

import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def faiss_dir():
    """返回 FAISS 索引目录（相对路径）。FAISS 在 Windows 下打不开含中文的绝对路径，故先切到项目根目录再返回相对路径。"""
    os.chdir(BASE_DIR)
    return "vector_store"


def load_env():
    """读取项目根目录下的 .env，写进环境变量（不依赖第三方库）。"""
    env_file = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def get_embeddings():
    """创建向量模型，必须和 rag/ingest.py 保持一致，否则检索结果错乱。"""
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_llm():
    """创建大模型客户端。改 .env 即可在 DeepSeek API 与本地 Ollama 间切换。"""
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "deepseek-chat"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.2,
    )


if __name__ == "__main__":
    load_env()
    print("配置加载成功，当前模型:", os.getenv("MODEL_NAME", "deepseek-chat"))

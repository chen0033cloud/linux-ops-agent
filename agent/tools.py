# -*- coding: utf-8 -*-
"""定义 Agent 的三个工具：search_knowledge / run_command / analyze_log。

安全核心：run_command 不让 LLM 输入任意命令，只能选白名单"键名"，从机制上杜绝 rm / kill / shutdown。"""

import os
import subprocess

from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool

from rag.query import faiss_dir, get_embeddings, load_env

IS_WINDOWS = os.name == "nt"

# 命令白名单：键名给 LLM 选，真实命令由我们控制；linux / win 各一套，双平台都能演示
COMMANDS = {
    "cpu_usage":    {"linux": "top -b -n1 | head -n 20", "win": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name,CPU,WS | Format-Table -AutoSize"},
    "mem_usage":    {"linux": "free -h", "win": "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | Format-List"},
    "disk_usage":   {"linux": "df -h", "win": "Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free | Format-Table -AutoSize"},
    "process_list": {"linux": "ps aux --sort=-%cpu | head -n 15", "win": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 | Format-Table -AutoSize"},
    "port_listen":  {"linux": "ss -tlnp", "win": "netstat -ano | findstr LISTENING"},
    "sys_version":  {"linux": "uname -a; cat /etc/os-release", "win": "systeminfo | findstr /B /C:\"OS name\" /C:\"OS version\""},
}


@tool
def search_knowledge(query: str) -> str:
    """检索运维知识库（故障 SOP + tldr 命令速查）。参数 query：检索关键词。"""
    load_env()
    store = FAISS.load_local(
        faiss_dir(),
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )
    docs = store.similarity_search(query, k=3)
    return "\n\n".join(
        f"[{os.path.basename(d.metadata.get('source', ''))}]\n{d.page_content}"
        for d in docs
    )


@tool
def run_command(cmd: str) -> str:
    """执行白名单内的只读诊断命令。参数 cmd 只能是：cpu_usage / mem_usage / disk_usage / process_list / port_listen / sys_version。"""
    key = cmd.strip().lower()
    spec = COMMANDS.get(key)
    if not spec:
        return f"命令 '{cmd}' 不在白名单，已拒绝执行。可用: {', '.join(COMMANDS)}"

    real = spec["win"] if IS_WINDOWS else spec["linux"]
    if IS_WINDOWS:
        argv = ["powershell", "-NoProfile", "-Command", real]
        shell = False
    else:
        argv = real
        shell = True

    try:
        out = subprocess.run(
            argv, shell=shell, timeout=20,
            capture_output=True, text=True, errors="ignore",
        )
        text = (out.stdout or "") + (out.stderr or "")
        return text[:2000] or "(命令无输出)"   # 截断到 2000 字，防上下文爆炸
    except subprocess.TimeoutExpired:
        return "命令执行超时（20 秒），已终止"
    except Exception as e:
        return f"执行失败: {e}"


@tool
def analyze_log(log_path: str, keyword: str = "ERROR") -> str:
    """读取日志文件，筛选包含 keyword 的最近记录。参数 log_path：日志路径；keyword 默认 'ERROR'。"""
    path = os.path.expanduser(log_path)
    if not os.path.isfile(path):
        return f"文件不存在: {path}"

    hits = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if keyword.lower() in line.lower():
                hits.append(line.rstrip())
    if not hits:
        return f"未发现包含 '{keyword}' 的日志行"

    return "\n".join(hits[-50:])[:2000]

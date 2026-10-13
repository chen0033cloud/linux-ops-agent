# -*- coding: utf-8 -*-
"""核心编排：组装 LangGraph Agent，对外提供统一入口 run_turn(text, host, thread_id)。

一行多故障拆分与多轮记忆融合在同一个 Agent 里：先 split_symptoms 拆开，再逐个交给同一 thread_id 排查，
Agent 全程记得上文。"""

import re

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.tools import analyze_log, run_command, search_knowledge
from rag.query import get_llm, load_env

SYSTEM_PROMPT = """你是 Linux 运维排障 Agent。按以下原则工作：
1. 先调用 search_knowledge 检索对应故障的排查 SOP，再决定执行哪个只读命令；
2. 一次只调用一个工具，根据返回结果决定下一步，最多 6 轮；
3. 只允许只读诊断，绝不执行任何变更类操作；
4. 信息足够时输出报告，格式固定为：【现象】/【原因】/【建议】三部分；
5. 如果用户一句话里包含多个故障，逐个排查并分别输出报告。
"""

# 拆分用的正则：分号、逗号、句号、换行，以及"还有/以及/另外/同时"等连接词
SPLIT_RE = re.compile(r"[；;，,。\n]|还有|以及|另外|同时")

_AGENT = None   # 全局单例：整个程序只创建一个 Agent 实例（保证记忆不丢）


def get_agent():
    """获取 Agent 单例，第一次调用时创建。"""
    global _AGENT
    if _AGENT is None:
        llm = get_llm()
        _AGENT = create_react_agent(
            llm,
            tools=[search_knowledge, run_command, analyze_log],
            prompt=SYSTEM_PROMPT,
            checkpointer=MemorySaver(),
        )
    return _AGENT


def split_symptoms(text: str) -> list:
    """把一句话里的多个问题拆成列表。例：'CPU高；磁盘也满了' -> ['CPU高', '磁盘也满了']"""
    parts = [p.strip(" 。.，,；;") for p in SPLIT_RE.split(text)]
    return [p for p in parts if len(p) >= 2]


def run_turn(text: str, host: str = "localhost", thread_id: str = "cli-demo") -> str:
    """一轮对话 = 问题拆分 + 多轮记忆（本项目最终形态）。所有问题共用同一 thread_id，记忆才连贯。"""
    load_env()
    agent = get_agent()
    symptoms = split_symptoms(text) or [text]
    multi = len(symptoms) > 1
    reports = []

    for i, s in enumerate(symptoms, 1):
        if multi:
            print(f"\n[第 {i}/{len(symptoms)} 个问题] {s}")
        res = agent.invoke(
            {"messages": [("user",
                f"主机 {host}。{s}（请按 SOP 做只读诊断，并输出【现象】【原因】【建议】报告）")]},
            config={"configurable": {"thread_id": thread_id}},
        )
        answer = res["messages"][-1].content
        reports.append((f"【问题 {i}】{s}\n" + answer) if multi else answer)

    return "\n\n".join(reports)

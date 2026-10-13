# -*- coding: utf-8 -*-
"""命令行入口：批量诊断 + 多轮对话，均基于同一个 run_turn()（问题拆分 + 记忆）。"""

import argparse
import sys

from agent.graph import run_turn


def main():
    parser = argparse.ArgumentParser(description="ops-agent · 智能排障助手")
    parser.add_argument("--host", help="目标主机名（仅用于展示和报告）")
    parser.add_argument("--symptom", help="故障描述，可用分号写多个问题")
    args = parser.parse_args()

    # 模式一：一次性诊断（--symptom），同样支持拆分 + 记忆
    if args.symptom:
        host = args.host or "localhost"
        print("\n[排障报告]\n" + run_turn(args.symptom, host=host, thread_id=f"cli-{host}"))
        return

    # 模式二：交互式多轮对话（主模式）
    host = input("目标主机名（回车默认 localhost）> ").strip() or "localhost"
    tid = f"cli-{host}"
    print(f"已连接 {host}，进入多轮对话模式（一行可写多个问题，用分号隔开；输入 q 退出）")
    while True:
        try:
            msg = input("\n你> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出")
            break
        if msg.lower() in ("q", "quit", "exit"):
            break
        if not msg:
            continue
        try:
            print("\nAgent>\n" + run_turn(msg, host=host, thread_id=tid))
        except Exception as e:
            print(f"出错: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()

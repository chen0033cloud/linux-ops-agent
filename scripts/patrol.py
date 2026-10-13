#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crontab 定时巡检脚本（Linux 成品）。

规则预检 → 无异常直接退出（不调 LLM、不花钱）→ 有异常才启动 Agent 诊断并写报告。
设计要点：规则兜底 + LLM 深挖；冷却期防反复触发；延迟导入让无异常时 <1 秒退出；全部只读命令。"""

import os
import sys
import time
import json
import socket
import shlex
import hashlib
import subprocess
from datetime import datetime

HOSTNAME = socket.gethostname()


# ---------- 基础工具 ----------

def _run(cmd):
    """执行一条只读 shell 命令，返回 (退出码, 输出文本)。"""
    proc = subprocess.run(
        cmd, shell=True,   # shell=True 才能用管道 | 和 tail/grep
        capture_output=True, text=True,
        timeout=15, errors="ignore",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_list(name):
    raw = os.environ.get(name, "") or ""
    return [x.strip() for x in raw.split(",") if x.strip()]


# ---------- 各项检查（返回"问题描述"列表，空列表=正常） ----------

def parse_disk(text, threshold):
    """解析 df -P -k 输出，挑出使用率超阈值的分区。"""
    problems = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        if parts[4].endswith("%"):
            pct = int(parts[4][:-1])
            if pct >= threshold:
                mount = " ".join(parts[5:])
                problems.append(f"磁盘 {mount} 使用率 {pct}%（超过 {threshold}%）")
    return problems


def check_disk(threshold):
    _, out = _run("df -P -k")
    return parse_disk(out, threshold)


def parse_memory(text, threshold):
    """解析 free -m 输出，判断内存使用率是否超阈值。"""
    for line in text.splitlines():
        if line.strip().startswith("Mem:"):
            parts = line.split()
            total = int(parts[1])
            available = int(parts[-1])
            used_pct = round((total - available) / total * 100) if total else 0
            if used_pct >= threshold:
                return [f"内存使用率 {used_pct}%（可用 {available}MB / 共 {total}MB）"]
    return []


def check_memory(threshold):
    _, out = _run("free -m")
    return parse_memory(out, threshold)


def check_load(per_cpu):
    """1 分钟平均负载超过 CPU核数×per_cpu（默认2倍）算过载。"""
    with open("/proc/loadavg", encoding="utf-8") as f:
        load1 = float(f.read().split()[0])
    cpus = os.cpu_count() or 1
    limit = cpus * per_cpu
    if load1 >= limit:
        return [f"1分钟平均负载 {load1} 超过 {limit:.1f}（{cpus} 核 × {per_cpu}）"]
    return []


def check_cpu(threshold, interval=1):
    """采样 interval 秒，读 /proc/stat 两次求差算 CPU 使用率。"""
    def read_stat():
        with open("/proc/stat", encoding="utf-8") as f:
            vals = list(map(int, f.readline().split()[1:]))
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return idle, sum(vals)
    idle1, total1 = read_stat()
    time.sleep(interval)
    idle2, total2 = read_stat()
    d_total = total2 - total1
    if d_total <= 0:
        return []
    usage = round((1 - (idle2 - idle1) / d_total) * 100)
    if usage >= threshold:
        return [f"CPU 使用率 {usage}%（{interval}s 采样）"]
    return []


def check_services(services):
    problems = []
    for svc in services:
        _, out = _run(f"systemctl is-active {shlex.quote(svc)}")
        state = out.strip() or "unknown"
        if state != "active":
            problems.append(f"服务 {svc} 状态异常：{state}")
    return problems


def check_logs(files):
    """在指定日志里找最近的 ERROR/Fatal/Panic 行。默认关闭，需配 OPS_LOG_FILES 才启用。"""
    problems = []
    for path in files:
        if not os.path.isfile(path):
            problems.append(f"日志文件不存在: {path}")
            continue
        _, out = _run(f"tail -n 200 {shlex.quote(path)} | grep -iE 'error|fatal|panic' | tail -n 5")
        lines = [ln for ln in out.splitlines() if ln.strip()]
        if lines:
            problems.append(f"日志 {path} 近期报错，例：{lines[-1][:120]}")
    return problems


def collect_anomalies(cfg):
    """按配置跑完所有检查并汇总。任一检查出错不影响其他项。"""
    problems = []
    checkers = [
        ("磁盘", lambda: check_disk(cfg["disk"])),
        ("内存", lambda: check_memory(cfg["mem"])),
        ("负载", lambda: check_load(cfg["load_per_cpu"])),
        ("CPU", lambda: check_cpu(cfg["cpu"])),
        ("服务", lambda: check_services(cfg["services"])),
        ("日志", lambda: check_logs(cfg["log_files"])),
    ]
    for name, fn in checkers:
        try:
            problems += fn()
        except Exception as e:
            print(f"[warn] {name} 检查失败：{e}")
    return problems


# ---------- 配置与日志 ----------

def load_config():
    """从环境变量读取所有阈值配置，带默认值。改配置不用改代码。"""
    return {
        "disk": _env_int("OPS_DISK_THRESHOLD", 85),
        "mem": _env_int("OPS_MEM_THRESHOLD", 90),
        "load_per_cpu": _env_float("OPS_LOAD_PER_CPU", 2.0),
        "cpu": _env_int("OPS_CPU_THRESHOLD", 90),
        "services": _env_list("OPS_SERVICES"),
        "log_files": _env_list("OPS_LOG_FILES"),
        "cooldown_min": _env_int("OPS_COOLDOWN_MIN", 30),
    }


def ensure_log_dir():
    """确定日志目录。默认 /var/log/ops-agent，没权限则退回项目内 logs/。"""
    directory = os.environ.get("OPS_LOG_DIR", "/var/log/ops-agent")
    try:
        os.makedirs(os.path.join(directory, "reports"), exist_ok=True)
        return directory
    except PermissionError:
        fallback = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(os.path.join(fallback, "reports"), exist_ok=True)
        return fallback


def append_log(path, line):
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_report(log_dir, now, problems, report):
    """把"触发原因 + Agent 诊断报告"写成带时间戳的 Markdown 文件，返回路径。"""
    fname = "report-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".md"
    path = os.path.join(log_dir, "reports", fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 自动排障报告\n\n")
        f.write(f"- 时间：{now}\n- 主机：{HOSTNAME}\n\n")
        f.write("## 触发原因（规则命中）\n")
        for i, p in enumerate(problems, 1):
            f.write(f"{i}. {p}\n")
        f.write("\n## Agent 诊断\n\n")
        f.write(report + "\n")
    return path


# ---------- 冷却期（防止同一故障反复烧钱） ----------

def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(path, state):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def within_cooldown(state, sig, minutes):
    last = state.get(sig)
    if not last:
        return False
    return (time.time() - last) < minutes * 60


# ---------- 主流程 ----------

def main():
    """无异常秒退不调 LLM；有异常先过冷却期，再调 Agent 诊断写报告。"""
    from rag.query import load_env   # 延迟导入：无异常时完全不加载 langchain 生态
    load_env()
    cfg = load_config()
    log_dir = ensure_log_dir()
    patrol_log = os.path.join(log_dir, "patrol.log")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    problems = collect_anomalies(cfg)
    if not problems:
        msg = f"[{now}] 巡检正常，未触发 LLM"
        append_log(patrol_log, msg); print(msg)
        return

    sig = hashlib.md5("|".join(sorted(problems)).encode("utf-8")).hexdigest()
    state_file = os.path.join(log_dir, "patrol_state.json")
    state = load_state(state_file)
    if within_cooldown(state, sig, cfg["cooldown_min"]):
        msg = f"[{now}] 异常持续但处于 {cfg['cooldown_min']} 分钟冷却期，跳过 LLM 调用"
        append_log(patrol_log, msg); print(msg)
        return

    print(f"[{now}] 发现 {len(problems)} 个异常，启动 LLM 诊断...")
    from agent.graph import run_turn   # 延迟导入：到这一步才加载 langgraph
    symptom = "；".join(problems)
    report = run_turn(symptom, host=HOSTNAME, thread_id=f"patrol-{HOSTNAME}")

    path = write_report(log_dir, now, problems, report)
    state[sig] = time.time()
    save_state(state_file, state)
    msg = f"[{now}] 发现 {len(problems)} 个异常，报告已写入 {path}"
    append_log(patrol_log, msg); print(msg)


if __name__ == "__main__":
    main()

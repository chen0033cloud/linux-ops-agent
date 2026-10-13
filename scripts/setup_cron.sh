#!/usr/bin/env bash
# 一键把 patrol.py 挂进 crontab，默认每 10 分钟跑一次。用法：bash scripts/setup_cron.sh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="/var/log/ops-agent"

echo "==> 项目目录：$PROJECT_DIR"
sudo mkdir -p "$LOG_DIR/reports"
sudo chown "$USER":"$USER" "$LOG_DIR" 2>/dev/null || true

CRON_LINE="*/10 * * * * cd $PROJECT_DIR && ./venv/bin/python scripts/patrol.py >> $LOG_DIR/patrol.log 2>&1"

echo "==> 安装 crontab 条目（先删旧的同名条目，避免重复）"
( crontab -l 2>/dev/null | grep -v 'scripts/patrol.py' ; echo "$CRON_LINE" ) | crontab -

echo "==> 安装完成，当前 crontab 中的巡检条目："
crontab -l | grep patrol.py
echo ""
echo "完成！之后每 10 分钟自动巡检一次：无异常只记一行日志，有异常才调大模型并生成报告。"
echo "查看巡检日志：tail -f $LOG_DIR/patrol.log"
echo "查看排障报告：ls -l $LOG_DIR/reports/"

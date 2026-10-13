# 故障案例: 磁盘空间写满

## 现象
- `df -h` 显示 Use% 100%，或 inode 用尽
- 应用写日志报 No space left on device
- 数据库、消息队列等写入型服务异常

## 排查步骤
1. `df -h` 确认是哪个挂载点写满；`df -i` 排除 inode 耗尽（小文件场景）
2. 定位大目录：`du -sh /* 2>/dev/null` 逐层下钻，或 `du -h --max-depth=2 /var | sort -rh | head`
3. 常见元凶：日志文件暴涨、core dump（`/var/lib/systemd/coredump`）、已删除但进程仍占用的文件
4. 检查"已删除未释放"：`lsof | grep deleted`，进程不重启空间不会释放
5. inode 耗尽时找小文件密集目录：`for d in */; do echo "$(ls -1 "$d" | wc -l) $d"; done | sort -rn | head`

## 判定标准
- Use% ≥ 90% 告警，≥ 95% 立即处理
- 单日志文件一天增长超过 10GB 属异常

## 处置方案
- 普通日志：`truncate -s 0 <file>` 清空（勿直接 rm 正在写的日志）
- 已删除未释放：重启占用进程，或 `> /proc/<pid>/fd/<n>` 截断
- 长效措施：配置 logrotate 轮转、清理策略进 crontab、磁盘使用率接入告警
- 事后复盘：确认增长根因，避免只做表面清理

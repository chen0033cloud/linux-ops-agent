# 故障案例: CPU 使用率过高

## 现象
- 系统负载（load average）持续高于 CPU 核数
- `top` 显示 us（用户态）或 sy（内核态）占比异常，或 wa（iowait）偏高
- 业务响应变慢、接口超时

## 排查步骤
1. `top`（按 P 按 CPU 排序）确认是哪个进程占用最高
2. `ps -eo pid,ppid,cmd,%cpu --sort=-%cpu | head` 查看进程级 TOP 列表
3. 若是多线程进程，`top -H -p <pid>` 定位具体线程；必要时 `printf '%x' <tid>` 转十六进制后用 `jstack`/`gdb` 分析
4. 区分占用类型：
   - us 高：业务代码死循环、正则回溯、加密压缩等
   - sy 高：频繁系统调用、上下文切换，用 `vmstat 1` 看 cs 列
   - wa 高：磁盘瓶颈，CPU 本身无辜，转磁盘排查
5. `pidstat -u 1 5` 观察持续性，排除瞬时毛刺

## 判定标准
- load average > CPU 核数 × 0.7 持续 5 分钟即视为异常
- 单进程 %CPU ≥ 90% 且非预期业务峰值

## 处置方案
- 代码死循环：kill 对应进程后修复重启，`kill -9` 为最后手段
- 突发流量：确认是否攻击或异常调用，必要时限流扩容
- wa 高：转查 `iostat -x 1` 磁盘利用率与 I/O 等待
- 事后：为该服务补充 CPU 告警（如 Prometheus 规则）与容量规划

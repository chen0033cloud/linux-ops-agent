# 知识库说明

## 目录结构
- `sop_*.md`：故障案例 SOP（现象 → 排查 → 判定 → 处置，四段式）
- `tldr/`：由 `fetch_tldr.py` 自动抓取的开源命令速查（tldr-pages，CC BY 4.0）

## 新增 SOP 的规范
1. 文件名以 `sop_` 开头，如 `sop_nginx_5xx.md`
2. 固定四段结构：现象 / 排查步骤 / 判定标准 / 处置方案
3. 命令一律用反引号包裹，方便 Agent 引用与白名单匹配

## 待补充清单（建议由 LLM 批量生成后人工审阅）
- [ ] sop_memory_leak.md（内存泄漏）
- [ ] sop_port_unreachable.md（端口不通）
- [ ] sop_nginx_5xx.md（Nginx 5xx）
- [ ] sop_ssh_slow.md（SSH 登录慢）
- [ ] sop_oom_kill.md（进程被 OOM 杀死）
- [ ] srv_log_explosion.md（日志暴涨）
- [ ] sop_dns_fail.md（DNS 解析失败）
- [ ] sop_fd_exhausted.md（文件句柄耗尽）
- [ ] sop_tcp_time_wait.md（TIME_WAIT 过多）

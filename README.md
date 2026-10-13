# ops-agent · Linux 智能排障 Agent

基于 LangChain + LangGraph 的运维排障助手（AIOps）。

检索是**工具之一**，由 LLM 自主决定查知识、跑命令还是看日志；
支持**一行多个问题自动拆分** + **多轮对话记忆**。

### 环境准备

```bash
# 1. 安装依赖（任选其一）
pip install -r requirements.txt        # 用 pip
# 或：uv sync                          # 用 uv（推荐，见 pyproject.toml）

# 2. 配置模型（复制模板后填写你的 API Key）
cp .env.example .env                   # 然后编辑 .env 填入 OPENAI_API_KEY 等

# 3. 构建知识库（只需一次；会生成 vector_store/ 与 knowledge_base/tldr/）
python fetch_tldr.py                   # 抓取 tldr-pages 中文命令库（约 1500+ 条）
python rag/ingest.py                   # 切块 + bge-small-zh 向量化 + 写入 FAISS 索引
```

### 运行方式

```bash
# 1. 批量诊断：一句话写多个问题，自动拆开逐个排查
python cli.py --host web01 --symptom "CPU高；磁盘也满了，还有内存占用异常"

# 2. 多轮对话：Agent 记得前面聊过的内容
python cli.py                    # 先输主机名，然后开始聊，输入 q 退出
```

### 目录

```
ops-agent/
├── cli.py                 # 入口：批量诊断 / 多轮对话 两种模式
├── fetch_tldr.py          # 抓取 tldr-pages 开源中文命令库
├── .env.example           # 模型配置（复制为 .env 后填写）
├── requirements.txt       # pip 安装用（也可用 uv，见 pyproject.toml）
├── knowledge_base/        # 知识库：sop_*.md 故障案例 + tldr/ 命令速查
├── rag/
│   ├── ingest.py          # 切分 + bge 向量化 + FAISS 入库
│   └── query.py           # 共用的 embeddings/llm/env 工具
├── agent/                 # LangGraph Agent 编排
│   ├── tools.py           # 三个工具：检索 / 只读命令 / 日志分析
│   └── graph.py           # LangGraph Agent + 问题拆分 + 对话记忆（统一入口 run_turn）
├── scripts/               # 定时巡检（crontab）成品
│   ├── patrol.py          # 规则预检 → 无异常不调 LLM → 有异常才诊断并写报告
│   └── setup_cron.sh      # 一键把 patrol.py 挂进 crontab
└── vector_store/          # （ingest 后生成，不要提交 git）
```

### 安全设计

`run_command` 不让 LLM 输入任意命令，只能选白名单键名
（`cpu_usage` / `mem_usage` / `disk_usage` / `process_list` / `port_listen` / `sys_version`），
从机制上杜绝 `rm`、`kill`、`shutdown` 等危险操作；命令带 20 秒超时，输出截断到 2000 字。

### 定时巡检（crontab，成品）

`scripts/patrol.py` 让项目能挂在 crontab 上自动盯着机器：**先用传统规则预检，无异常直接退出、不调大模型（不花钱）；只有命中阈值才启动 Agent 诊断并写报告**。同一异常在冷却期内只调一次 LLM，防止故障持续时反复烧钱。

检查项（全部只读）：磁盘使用率、内存使用率、1分钟负载、CPU 使用率、关键服务是否 active、指定日志是否报错。

```bash
# 手动跑一次，看效果（正常时 <1 秒退出，只记一行日志）
./venv/bin/python scripts/patrol.py

# 一键挂进 crontab（默认每 10 分钟一次，自动建日志目录、去重安装）
bash scripts/setup_cron.sh

# 不想用脚本，也可手动加一行（注意用 venv 里的 python + 绝对路径，cron 环境很干净）
# */10 * * * * cd /opt/ops-agent && ./venv/bin/python scripts/patrol.py >> /var/log/ops-agent/patrol.log 2>&1
```

阈值都用环境变量配置（写进 `.env` 即可，不用改代码）：

| 变量 | 默认 | 含义 |
|---|---|---|
| `OPS_DISK_THRESHOLD` | 85 | 磁盘使用率报警线（%）|
| `OPS_MEM_THRESHOLD` | 90 | 内存使用率报警线（%）|
| `OPS_LOAD_PER_CPU` | 2.0 | 每核负载过载倍数 |
| `OPS_CPU_THRESHOLD` | 90 | CPU 使用率报警线（%）|
| `OPS_SERVICES` | 空 | 要监控的服务，逗号分隔，如 `nginx,mysql` |
| `OPS_LOG_FILES` | 空 | 要监控的日志路径，逗号分隔（默认关闭防误报）|
| `OPS_COOLDOWN_MIN` | 30 | 同一异常冷却分钟数 |
| `OPS_LOG_DIR` | /var/log/ops-agent | 日志/报告目录，无权限时自动退回项目内 `logs/` |

产物：巡检记录在 `patrol.log`，每次触发 LLM 的完整报告在 `reports/report-时间戳.md`。

## 数据来源声明

tldr-pages 内容采用 CC BY 4.0 协议（https://github.com/tldr-pages/tldr），
本项目中仅做格式清洗与本地检索使用。

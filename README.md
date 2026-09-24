# kimi-td-memory

Kimi Code CLI 的 [TencentDB-Agent-Memory（td-memory）](https://github.com/TencentCloud/TencentDB-Agent-Memory) 集成插件。

通过本插件，Kimi 可以在对话过程中自动保存上下文，并在后续会话中召回过往记忆、搜索原始对话，实现跨会话的项目知识沉淀。

> 本版本（3.x）基于 **MemoryCore v2.0.0** 开发，对接其 v3 数据面 API（`/v3/conversation`、`/v3/atomic`、`/v3/scenario`、`/v3/core`）；服务端升级到官方 v2.0.1 时插件无需改动。如需对接旧版 v1 Gateway（`/capture`、`/recall` 接口），请使用插件 2.x 版本（master 分支）。

## 版本对应

| 插件版本 | 对接服务端 | 说明 |
|----------|-----------|------|
| 3.1+ | MemoryCore v2.0.0 / v2.0.1 | v3 数据面（`/v3/*`）+ Skill 平面（`/v3/skill/*`），本分支 |
| 3.0 | MemoryCore v2.0.0 / v2.0.1 | v3 数据面（`/v3/*`） |
| 2.x | v1.x Gateway | v1 兼容接口（`/capture`、`/recall`），master 分支 |

## 功能

- **自动捕获对话**：插件目录内置 watcher，自动将用户/助手对话写入 td-memory。
- **会话开始自动召回**：插件声明了 sessionStart skill，引导 Kimi 在接到任务时先搜索相关记忆。
- **召回上层记忆**（`td_recall`）：一次性获取 L3 用户画像、L2 场景导航与匹配的 L1 记忆。
- **搜索 L1 原子记忆**（`td_search_memories`）：召回已提炼的关键事实、决策和项目上下文。
- **搜索 L0 原始对话**（`td_search_conversations`）：查找完整的历史对话原文。
- **手动捕获**（`td_capture`）：在需要时手动写入单轮对话。
- **健康检查**（`td_health`）：检测 TDAI Gateway 是否可达。
- **状态查看**（`td_status`）：显示网关地址与 watcher 进程状态。

## 安装

1. 确保已安装 Kimi Code CLI（新版 Node.js 插件体系）。
2. 确保 Python 3.10+ 可用，并安装 MCP SDK：`pip install mcp`。
3. 在 Kimi Code CLI 中执行（二选一）：

   ```
   /plugins install https://github.com/qiaoyuanjun/kimi-td-memory
   /plugins install E:/project/plugins/kimi-td-memory(本地源码位置)
   /reload
   ```

   安装后 CLI 会把插件复制到 `$KIMI_CODE_HOME/plugins/managed/kimi-td-memory/`（`KIMI_CODE_HOME` 默认为 `~/.kimi-code`），并始终运行该副本。**修改源码后必须重新执行 `/plugins install` 才会生效。**

4. 确保 MemoryCore Gateway 正在运行（v2.0.0，Standalone 模式即可）。默认地址为 `http://127.0.0.1:8420`，可在配置文件中修改，也可通过环境变量覆盖。
5. 调用任意插件工具时，watcher 会自动检测并启动。

## 工具说明

工具通过 MCP（server 名 `td-memory`）提供。调用名前缀取决于安装方式：经 `/plugins install` 安装时为 `mcp__plugin-kimi-td-memory_td-memory__<工具名>`；经 `mcp.json` 手动添加（如 VS Code 扩展）时为 `mcp__td-memory__<工具名>`。

| 工具名 | 用途 | 主要参数 |
|--------|------|----------|
| `td_recall` | 召回上层记忆（L3 画像 + L2 场景导航 + L1 提示）。L3/L2 **本地直读** `data_dir` 下的 Markdown 文件（配置了 `data_dir` 时，Gateway 不在线也能召回），L1 经 `/v3/atomic/search` 检索 | `query`（必填）、`session_key` |
| `td_search_memories` | 搜索提炼后的原子记忆（`/v3/atomic/search`） | `query`（必填）、`limit`、`session_key` |
| `td_search_conversations` | 搜索原始对话记录（`/v3/conversation/search`） | `query`（必填）、`limit`、`session_key` |
| `td_capture` | 手动捕获一轮对话（`/v3/conversation/add`） | `user_content`（必填）、`assistant_content`（必填）、`session_key` |
| `td_search_skills` | 搜索服务端从对话沉淀的 Skill（可复用 SOP，含触发边界/执行步骤/验证规则） | `query`（必填）、`limit` |
| `td_get_skill` | 按名称获取 Skill 全文 | `name`（必填） |
| `td_end_session` | 兼容性保留：v2 服务端自动提炼 L1/L2/L3，无需手动触发，调用仅返回确认信息 | `session_key` |
| `td_health` | 检查 TDAI Gateway 健康状态，并确保 watcher 在运行 | 无 |
| `td_status` | 显示网关与 watcher 状态，未运行则自动启动 | 无 |
| `td_stop_watcher` | 停止 watcher | 无 |

可在 `/plugins` 面板的 Installed 页按 `M` 管理本插件的 MCP server（启用/禁用）。

## 配置

插件按以下优先级读取配置（找到即用，不合并）：

1. **用户级配置** `~/.kimi-td-memory/config.json` —— 推荐，重装插件不会覆盖。
2. 插件自带的 `config.json` —— 注意 CLI 运行的是 managed 副本，改源码目录里的这份文件必须重新 install 才生效。

以下环境变量会覆盖配置文件中的对应项：

| 环境变量 | 覆盖的配置项 |
|----------|--------------|
| `TDAI_GATEWAY_URL` | `gateway_url` |
| `TDAI_GATEWAY_API_KEY` | `gateway_api_key` |
| `TDAI_SERVICE_ID` | `service_id` |
| `TDAI_DATA_DIR` | `data_dir` |
| `TDAI_TEAM_ID` / `TDAI_AGENT_ID` / `TDAI_USER_ID` / `TDAI_TASK_ID` | `identity.*` |
| `KIMI_CODE_HOME` | Kimi Code 数据目录（默认 `~/.kimi-code`），watcher 据此定位会话文件 |

### config.json

```json
{
  "gateway_url": "http://127.0.0.1:8420",
  "gateway_api_key": "",
  "service_id": "default",
  "data_dir": "",
  "identity": {
    "team_id": "",
    "agent_id": "",
    "user_id": "",
    "task_id": ""
  },
  "session_key_map": {
    "budaogu-cloud": "budaogu-context",
    "budaogu": "budaogu-context"
  },
  "watcher": {
    "enabled": true,
    "poll_interval": 5,
    "state_dir": "~/.kimi-td-memory"
  }
}
```

> `session_key_map` 示例：当会话所属工作区目录名包含 `budaogu-cloud` 时使用 `budaogu-context` 作为 session_id；若多个规则同时匹配，取匹配长度最长的规则。

| 字段 | 说明 |
|------|------|
| `gateway_url` | TDAI Gateway 地址。 |
| `gateway_api_key` | 网关 API 密钥（Gateway 设置了 `TDAI_GATEWAY_API_KEY` 时必填，否则留空）。也可通过环境变量设置。 |
| `service_id` | Memory 实例 ID（`x-tdai-service-id`），本地部署固定为 `default`。 |
| `data_dir` | Gateway 的本地数据目录（如 `E:/project/budaogu/ai-latest-report/memory/tdai-data`）。配置后 `td_recall` 的 L3 画像与 L2 场景导航**直接从本地 Markdown 文件读取**（不再走 HTTP，Gateway 离线也能召回），场景路径也可直接 Read。 |
| `identity` | v3 隔离字段（team/agent/user/task）。**默认全部留空**：数据面回落到 `default` 桶——官方 v2→v3 迁移脚本也是把存量数据放进该桶，留空即可继续读写历史记忆。需要真正的多租户隔离时再填。 |
| `skill_identity` | Skill 平面的隔离字段（team/agent/user），由 `scripts/bootstrap_skill.py` 自动写入，见下文「启用 Skill 模块」。与 `identity` 相互独立：chat 记忆继续走 default 桶，Skill 资产归属到 provision 的 team/agent（Skill 创建会向元数据面注册资产，要求 team/agent 实体存在）。 |
| `session_key_map` | 工作区目录名关键词到 `session_id` 的映射，优先级最高。 |
| `watcher` | watcher 配置：`enabled` 是否启用、`poll_interval` 轮询间隔（秒）、`state_dir` 状态目录。 |

## 启用 Skill 模块

Skill 是服务端从对话中自动沉淀的可复用 SOP。完整启用需要两步：

1. **Gateway 配置启用 skill 模块**（`tdai-gateway.yaml` 增加以下配置，或设环境变量 `TDAI_SKILL_ENABLED=true`），然后重启 Gateway：

   ```yaml
   skill:
     enabled: true
     routing:
       mode: "bm25"
       searchTopK: 20
     extraction:
       enabled: true     # 需要有效的 llm 配置
       maxIterations: 16
   ```

2. ** provision Skill 身份实体**：Skill 创建会向 v3 元数据面注册资产，要求 owning team/agent 存在。在插件目录执行一次（幂等，可重复跑）：

   ```
   python scripts/bootstrap_skill.py
   ```

   脚本会自动完成 init-admin → 建业务用户 → 建 team（`kimi-code`）→ 建 agent（`kimi`），并把 `skill_identity`、`admin_key`、`user_key` 写入用户级配置 `~/.kimi-td-memory/config.json`。

启用后：watcher 会把每轮对话**双写**到 `/v3/skill/conversation/add`（skill 提炼流水线，best-effort）；达到服务端阈值时自动归档提炼为 Skill；`td_search_skills` / `td_get_skill` 可随时检索。

### Session Key 解析规则

watcher 监听 `$KIMI_CODE_HOME/sessions/<工作区目录名>/<会话ID>/agents/main/wire.jsonl`（`KIMI_CODE_HOME` 默认为 `~/.kimi-code`），其中工作区目录名形如 `wd_<项目目录名>_<hash>`：

1. 如果 `session_key_map` 中有匹配该目录名的关键词，使用映射值。
2. 否则从目录名解析出项目名，使用 `<项目名>-context`。

session_id 在 v3 中是 L0 对话的分组维度（服务端按它驱动 L1 提炼流水线）；跨会话记忆共享由 identity（team/agent）维度承载。手动调用工具时也可通过 `session_key` 参数显式指定；工具内缺省值则按当前项目目录解析（`<项目目录名>-context`）。

## 启动 watcher

插件目录已包含 watcher（`watcher.py`），用于自动监听 Kimi Code CLI 会话并写入 td-memory。

### 自动启动

调用任意插件工具时，插件会自动检测 watcher 状态；如果未运行，会尝试在后台启动它。因此通常无需手动启动 watcher。

### 手动启动 / 查看状态

调用 `td_status` 即可查看当前状态，并在需要时自动拉起 watcher。

### 停止 watcher

调用 `td_stop_watcher`，或执行 `python watcher.py stop`。

> 注意：watcher 依赖 TDAI Gateway，请先启动 Gateway。

## 从插件 2.x（v1 Gateway）升级

1. 服务端升级到 MemoryCore v2.0.0（Standalone 源码运行或 Docker 均可），存量数据用官方脚本 `MemoryCore/scripts/migrate-v2-to-v3/v2-to-v3-migrate.py` 迁移（先 `--dry-run` 检查；迁移会把旧数据放入 `default` team/agent 桶，本插件默认 identity 留空正好与其对齐）。
2. 重新 `/plugins install` 本插件并 `/reload`。
3. 如服务端设置了 `TDAI_GATEWAY_API_KEY`，在用户级配置 `~/.kimi-td-memory/config.json` 中填入 `gateway_api_key`。
4. 建议配置 `data_dir` 指向 Gateway 数据目录，让场景导航路径可直接读取。

## 常见问题

**Q: `/plugins install` 报 `EBUSY: resource busy or locked, rename ...plugins/managed/kimi-td-memory...`？**

运行中的 MCP server 进程以 managed 目录为工作目录，Windows 会锁住目录导致安装器无法改名。先结束这些进程再重试安装：

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'managed.kimi-td-memory' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**Q: 改了插件源码、重新安装并 `/reload` 后，工具行为还是旧的？**

`/reload` 只会在 MCP server 未运行时启动它，**不会重启已在运行的 server 进程**。需要结束 `python mcp_server.py` 进程（下次调用工具时自动以新代码拉起），或开一个新会话。

**Q: 桌面版和 CLI 的插件管理有区别吗？**

没有。桌面版与 CLI 共用同一套插件机制和 `$KIMI_CODE_HOME` 数据目录（含 `plugins/managed/` 与 `installed.json`），任一端安装/更新，另一端 `/reload` 后同样生效。

## 项目结构

```
kimi-td-memory/
├── kimi.plugin.json     # 插件清单（声明 MCP server、skills、sessionStart）
├── mcp_server.py        # MCP stdio server，承载全部 td_* 工具
├── config.json          # 插件默认配置（可被 ~/.kimi-td-memory/config.json 覆盖）
├── __init__.py
├── common.py            # 向后兼容的聚合导出（新代码建议直接导入子模块）
├── config.py            # 配置加载与环境变量
├── client.py            # TDAI Gateway HTTP 客户端（v3 数据面 + skill 平面）
├── session.py           # session_id 解析
├── watcher_ctl.py       # watcher 生命周期管理
├── text.py              # 文本提取与过滤
├── formatting.py        # 结果格式化
├── watcher.py           # 自动捕获 watcher（监听 wire.jsonl，chat + skill 双写）
├── local_store.py       # L2/L3 本地文件直读（persona.md / scene_blocks，含 META 头解析）
├── scripts/
│   └── bootstrap_skill.py  # Skill 身份 provision（init-admin → user → team → agent）
├── skills/
│   └── td-memory/
│       └── SKILL.md     # sessionStart skill：记忆召回/提炼使用指引
└── README.md
```

## 依赖

- Python 3.10+，以及 `mcp` 包（`pip install mcp`）
- Kimi Code CLI（新版插件体系）
- MemoryCore Gateway v2.0.0（外部运行，Standalone 模式即可）

## 许可证

MIT

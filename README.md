# kimi-td-memory

Kimi Code CLI 的 [TencentDB-Agent-Memory（td-memory）](https://github.com/leezhixing/kimi-td-memory) 集成插件。

通过本插件，Kimi 可以在对话过程中自动保存上下文，并在后续会话中召回过往记忆、搜索原始对话，实现跨会话的项目知识沉淀。

## 功能

- **自动捕获对话**：插件目录内置 watcher，自动将用户/助手对话写入 td-memory。
- **会话开始自动召回**：插件声明了 sessionStart skill，引导 Kimi 在接到任务时先搜索相关记忆。
- **召回上层记忆**（`td_recall`）：一次性获取 L3 用户画像、L2 场景导航与匹配的 L1 记忆。
- **搜索 L1 原子记忆**（`td_search_memories`）：召回已提炼的关键事实、决策和项目上下文。
- **搜索 L0 原始对话**（`td_search_conversations`）：查找完整的历史对话原文。
- **手动捕获**（`td_capture`）：在需要时手动写入单轮对话。
- **结束会话**（`td_end_session`）：立即触发 L1/L2/L3 提炼。
- **健康检查**（`td_health`）：检测 TDAI Gateway 是否可达。
- **状态查看**（`td_status`）：显示网关地址与 watcher 进程状态。

## 安装

1. 确保已安装 Kimi Code CLI（新版 Node.js 插件体系）。
2. 确保 Python 3.8+ 可用，并安装 MCP SDK：`pip install mcp`。
3. 在 Kimi Code CLI 中执行：

   ```
   /plugins install E:/project/plugins/kimi-td-memory
   /reload
   ```

   安装后 CLI 会把插件复制到 `~/.kimi-code/plugins/managed/kimi-td-memory/`，并始终运行该副本。**修改本目录源码后必须重新执行 `/plugins install` 才会生效。**

4. 确保 TDAI Gateway 正在运行。默认地址为 `http://127.0.0.1:8420`，可在配置文件中修改，也可通过环境变量覆盖。
5. 调用任意插件工具时，watcher 会自动检测并启动。

## 工具说明

工具通过 MCP（server 名 `td-memory`）提供，在 Kimi Code CLI 中的调用名带 `mcp__td-memory__` 前缀：

| 工具名 | 用途 | 主要参数 |
|--------|------|----------|
| `mcp__td-memory__td_recall` | 召回上层记忆（L3 画像 + L2 场景导航 + L1 提示） | `query`（必填）、`session_key` |
| `mcp__td-memory__td_search_memories` | 搜索提炼后的原子记忆 | `query`（必填）、`limit`、`session_key` |
| `mcp__td-memory__td_search_conversations` | 搜索原始对话记录 | `query`（必填）、`limit`、`session_key` |
| `mcp__td-memory__td_capture` | 手动捕获一轮对话 | `user_content`（必填）、`assistant_content`（必填）、`session_key` |
| `mcp__td-memory__td_end_session` | 结束当前会话并触发提炼 | `session_key` |
| `mcp__td-memory__td_health` | 检查 TDAI Gateway 健康状态，并确保 watcher 在运行 | 无 |
| `mcp__td-memory__td_status` | 显示网关与 watcher 状态，未运行则自动启动 | 无 |
| `mcp__td-memory__td_stop_watcher` | 停止 watcher | 无 |

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
| `KIMI_CODE_HOME` | Kimi Code 数据目录（默认 `~/.kimi-code`），watcher 据此定位会话文件 |

### config.json

```json
{
  "gateway_url": "http://127.0.0.1:8420",
  "gateway_api_key": "",
  "session_key_map": {
    "budaogu-cloud": "budaogu-context",
    "budaogu": "budaogu-context"
  },
  "watcher": {
    "enabled": true,
    "poll_interval": 5,
    "idle_timeout": 300,
    "flush_delay": 30,
    "state_dir": "~/.kimi-td-memory"
  }
}
```

> `session_key_map` 示例：当会话所属工作区目录名包含 `budaogu-cloud` 时使用 `budaogu-context` 作为 session_key；若多个规则同时匹配，取匹配长度最长的规则。

| 字段 | 说明 |
|------|------|
| `gateway_url` | TDAI Gateway 地址。 |
| `gateway_api_key` | 网关 API 密钥（如网关无需认证可留空）。也可通过 `TDAI_GATEWAY_API_KEY` 环境变量设置。 |
| `session_key_map` | 工作区目录名关键词到 `session_key` 的映射，优先级最高。 |
| `watcher` | watcher 配置：`enabled` 是否启用、`poll_interval` 轮询间隔（秒）、`idle_timeout` 空闲超时（秒）、`flush_delay` 未完成回合的兜底 flush 延迟（秒）、`state_dir` 状态目录。 |

### Session Key 解析规则

watcher 监听 `~/.kimi-code/sessions/<工作区目录名>/<会话ID>/agents/main/wire.jsonl`，其中工作区目录名形如 `wd_<项目目录名>_<hash>`：

1. 如果 `session_key_map` 中有匹配该目录名的关键词，使用映射值。
2. 否则从目录名解析出项目名，使用 `<项目名>-context`。

手动调用工具时也可通过 `session_key` 参数显式指定；工具内缺省值则按当前项目目录解析（`<项目目录名>-context`）。

## 启动 watcher

插件目录已包含 watcher（`watcher.py`），用于自动监听 Kimi Code CLI 会话并写入 td-memory。

### 自动启动

调用任意插件工具时，插件会自动检测 watcher 状态；如果未运行，会尝试在后台启动它。因此通常无需手动启动 watcher。

### 手动启动 / 查看状态

调用 `mcp__td-memory__td_status` 即可查看当前状态，并在需要时自动拉起 watcher。

### 停止 watcher

调用 `mcp__td-memory__td_stop_watcher`，或执行 `python watcher.py stop`。

> 注意：watcher 依赖 TDAI Gateway，请先启动 Gateway。

## 项目结构

```
kimi-td-memory/
├── kimi.plugin.json     # 插件清单（声明 MCP server、skills、sessionStart）
├── mcp_server.py        # MCP stdio server，承载全部 td_* 工具
├── config.json          # 插件默认配置（可被 ~/.kimi-td-memory/config.json 覆盖）
├── __init__.py
├── common.py            # 向后兼容的聚合导出（新代码建议直接导入子模块）
├── config.py            # 配置加载与环境变量
├── client.py            # TDAI Gateway HTTP 客户端
├── session.py           # session_key 解析
├── watcher_ctl.py       # watcher 生命周期管理
├── text.py              # 文本提取与过滤
├── formatting.py        # 结果格式化
├── watcher.py           # 自动捕获 watcher（监听 wire.jsonl）
├── skills/
│   └── td-memory/
│       └── SKILL.md     # sessionStart skill：记忆召回/提炼使用指引
└── README.md
```

## 依赖

- Python 3.8+，以及 `mcp` 包（`pip install mcp`）
- Kimi Code CLI（新版插件体系）
- TDAI Gateway（外部运行）

## 许可证

MIT

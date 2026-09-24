---
name: td-memory
description: td-memory 长期记忆的使用指引 —— 何时召回历史记忆、对话如何自动捕获、何时触发提炼
---

# TD Memory 长期记忆

本会话已接入 td-memory 长期记忆系统（MCP server：`td-memory`）。它可以跨会话沉淀项目知识：过往对话会被自动捕获并提炼为原子记忆，随时可以召回。

## 开始任务前：先召回记忆

接到实质性任务（开发、调试、方案设计等）时，先调用 `mcp__td-memory__td_recall` 召回上层记忆（L3 用户画像 + L2 场景导航 + 匹配的 L1 记忆），获取宏观背景，避免重复询问用户或遗漏历史决策：

- 查询词用任务关键词或自然语言即可，`session_key` 留空会自动按当前项目解析。
- 返回的场景导航中列出的 scene block 路径是 Markdown 文件，需要该场景的完整细节时直接用 Read 读取。
- 若上层记忆不够，再用 `mcp__td-memory__td_search_memories` 搜 L1 原子记忆；还不够则用 `mcp__td-memory__td_search_conversations` 查 L0 原始对话原文。
- 开始一类之前可能解决过的任务时，可以用 `mcp__td-memory__td_search_skills` 检索服务端沉淀的可复用 SOP（Skill），命中后用 `mcp__td-memory__td_get_skill` 取全文按步骤执行。

## 对话捕获：全自动，无需干预

后台 watcher 会自动把本会话的用户/助手对话写入 td-memory，**不要**主动调用 `mcp__td-memory__td_capture`（它只用于 watcher 失效时的手动补救）。

## 话题收尾：提炼已自动化

服务端（MemoryCore v2）会在捕获达到阈值或会话空闲时自动完成 L1/L2/L3 提炼，**无需**手动触发。`mcp__td-memory__td_end_session` 仅作为确认标记保留，通常不用调用。

## 排障

记忆工具报错或怀疑捕获未生效时，调用 `mcp__td-memory__td_status` 查看网关与 watcher 状态（会顺带拉起 watcher），或 `mcp__td-memory__td_health` 检查 TDAI Gateway 连通性。

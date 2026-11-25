# MemoryService · 大肥鱼记忆 v2

按 [重建文档第 5 节](../Doc/重建/2026-11-25-大肥鱼重建-v1.md) 实现的本地记忆服务骨架。

## 当前进度

| 能力 | 状态 |
| --- | --- |
| SQLite 五层表结构 | ✅ `schema.sql` |
| 事件幂等写入（L3） | ✅ `db.add_event` |
| 记忆卡 + 来源引用（L2） | ✅ `db.add_memory`（无来源直接拒绝） |
| 归档 / 遗忘 / 恢复 | ✅ `db.set_memory_status` |
| 艾宾浩斯保持率 + 强化延长半衰期 | ✅ `db.retention` |
| 关键词召回 + 精排公式 | ✅ `db.recall`（FTS5 trigram，失败退 LIKE） |
| L4 核心记忆 | ✅ propose / confirm / list；已确认的优先进入召回，不衰减 |
| 每日摘要（L1） | ✅ `digest.generate/get`：按天统计轮次、候选、激活、承诺 |
| 审计 | ✅ `memory_audit` |
| 向量（bge-m3 / sqlite-vec） | ✅ bge-m3 已启用（Ollama 本地），语义召回可用；仍为暴力余弦 |
| MCP stdio 服务 | ✅ `mcp_server.py`：12 个工具（recall / remember / forget / audit / ingest / promote / decay / core_* / digest_*） |
| 候选提取器 | ✅ `extractor.py`（规则版）；`llm_extractor.py`（模型版骨架，未接模型） |
| 候选审核 | ✅ `memory_candidates` / `memory_reject`（软删除，可恢复） |
| 恢复 | ✅ `memory_restore`（deleted/archived → candidate，重新审核） |
| 状态 | ✅ `memory_stats`（事件/记忆/核心/摘要/审计计数） |
| 语义召回 | ✅ `memory_embed` / `memory_semantic_recall`（bge-m3 + 精排） |
| 清理 | ✅ `memory_purge`（仅过期 deleted，必须 confirm） |
| 每日衰减任务 | ✅ `decay_job.py`（低于阈值归档，支持 dry-run） |
| 自动 ingest | ✅ `session_tail.py`（解压日志、过滤注入/reasoning、`turn_id` 去重；**仅白名单工作区**，默认 `D:\大肥鱼`） |
| 自动心跳 | ✅ `auto_tick.py`（MCP 服务内 10 分钟：增量入库 + 刷新摘要 + stale 监控，不自动归档） |
| 备份 | ✅ `backup.py`（create / verify / restore；完整性校验、拒绝静默覆盖） |
| 旧库迁移脚本 | ⬜ 未开始 |

## 运行测试

```powershell
cd D:\大肥鱼\MemoryService
python -m unittest discover -s tests -v
```

当前 54 项测试全过：存储 9、MCP 11、规则提取 5、模型提取 5、衰减 5、摘要 2、日志入库 3、向量 5、心跳 2、备份 4、语义召回 3。覆盖事件幂等、来源强制、中文召回、归档/恢复、遗忘、衰减与强化、敏感排除、摘要生成、审计、MCP 调用、ingest→promote→recall、core propose→confirm→recall、decay dry-run→apply、每日摘要生成/读取。

## 关键约束（写进代码，不靠自觉）

- L2 记忆**必须**引用至少一个 L3 事件；没有来源直接 `ValueError`。
- L1/L2 不能覆盖 L3；L4 只能经 `confirmed` 流程改。
- `restricted` 默认不参与召回，除非显式 `include_restricted=True`。
- 只被读取不增加 `reinforcement`；强化只由用户确认或独立证据触发。
- 遗忘是 `status='deleted'` 软删除；归档是 `archived`，可恢复。

## 数据位置（规划）

- 运行库：`%USERPROFILE%\.dsh\memory-v2\memory.db`（不进 Git）
- 本目录只放代码与 schema；`Memory/` 与 `memory-v2/` 都在 `.gitignore` 里。

## 下一步

1. `mcp_server.py`：stdio JSON-RPC，暴露 `memory_recall` / `memory_remember` / `memory_forget` / `memory_audit`。
2. `extractor.py`：成功轮次 → 候选提取（先规则，后模型）。
3. `decay_job.py`：每日重算 retention，低于阈值归档。
4. `migrate_from_v1.py`：旧云端 SQLite → v2 表。

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
| 每日摘要（L1） | ✅ `db.upsert_digest` |
| 审计 | ✅ `memory_audit` |
| 向量（bge-m3 / sqlite-vec） | ⬜ 未开始 |
| MCP stdio 服务 | ⬜ 未开始 |
| 候选提取器 / 衰减任务 | ⬜ 未开始 |
| 旧库迁移脚本 | ⬜ 未开始 |

## 运行测试

```powershell
cd D:\大肥鱼\MemoryService
python -m unittest discover -s tests -v
```

当前 9 项测试全过：事件幂等、来源强制、中文召回、归档/恢复、遗忘、衰减与强化、敏感排除、摘要合并、审计。

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

# dsh-memory-galaxy

把 `MemoryGalaxy` 的 Bloom 版挂进 DSH 右侧栏。

- tab 类型：`memory-galaxy`
- body：iframe `http://127.0.0.1:9882/galaxy-lab.html?embed=1`
- 入口：
  - 右侧栏 `+` → 记忆星河
  - 会话头部 `✦ 记忆星河` 按钮
- 依赖：`start-all.ps1` 在 9882 起静态服务

`?embed=1` 会隐藏大标题、筛选和页脚，只保留搜索和详情，适配窄侧栏。

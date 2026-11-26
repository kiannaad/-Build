# 2026-11-26 安装 dsh-fish-mood

## 时间

2026-11-26 10:24–10:30（Asia/Shanghai）

## 原因

人设卡 v3 解决了“怎么写”，但模型仍然缺少随时间变化的内部状态。先装最小侵入的 `dsh-fish-mood`，只加情绪层，不动记忆与人格卡。

## 改动

- 通过插件管理器安装 `dsh-fish-mood 0.1.0` 到 `desktop` profile；
- 安装前备份：`cordis.patch.yml.bak-20261126-102406`；
- 未改配置，使用默认值：
  - `channels.web=true`，`channels.qq=true`；
  - `promptEnabled=true`；
  - 状态目录 `~/.dsh/fish-mood`。

## 验证证据

- 工具已注册：`mood_now` / `mood_feel` / `mood_diary`；
- 系统提示词出现 `【心情 · 实时】` 段；
- `mood_now` 返回当前状态：

```text
担心（71/100）· 起因：对方看起来不太好
底色：愉快度 -0.31 / 精力 58
性格：爱玩、话多、不太自律
回复参数：正常长度 · 可以多问一句 · 语气压着
```

- 注入的规则明确：心情只改语气与长度，不改事实与结论；不报心情、不拿情绪要挟；危机场景优先安全与热线。

## 影响面

- 只影响表达，不新增记忆；和 Memory v2 不冲突；
- 会读取会话中最近的消息做评价（默认 15 分钟内、单轮最多 2 条）；
- 无网络请求、无第三方依赖、状态只落本地；
- 和 soul-md 人设卡 v3 叠加：人设决定“是谁”，fish-mood 决定“此刻什么状态”。

## 已知限制

- 情绪推导是 25 条启发式规则 + 18 维评分，不是语义理解，会误判；
- 当前把前面对话里的焦虑误读成“对方看起来不太好”，导致技术对话里也带着“担心”；
- 状态跨话题延续，可能让工作语气变软或变沉；
- 心跳随机事件、深夜复盘会增加少量 token；
- 没有内置“重置心情”工具，重置需删除 `~/.dsh/fish-mood/state.json`。

## 回滚

```powershell
# 停用并卸载
dsh plugin --profile desktop remove dsh-fish-mood
# 可选：清本地状态
Remove-Item "$env:USERPROFILE\.dsh\fish-mood" -Recurse -Force
```

或恢复备份 `cordis.patch.yml.bak-20261126-102406`。

## 下一步

观察 1–2 天：

- 语气是否更自然，还是变得“过度共情/情绪化”；
- 技术任务里会不会因为误判心情而答得不对；
- 如果误判多，调低 `traits.neuroticism`、关闭 `react` 或重设状态。

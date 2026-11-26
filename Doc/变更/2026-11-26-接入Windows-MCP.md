# 2026-11-26 接入 Windows-MCP（桌面自动化）

## 时间

2026-11-26 10:04–10:20（Asia/Shanghai）

## 原因

阶段 1：先给大肥鱼接上 Windows 桌面操作能力，再考虑语音。目标不是全开，而是最小权限、可回滚。

## 改动

在 `~/.dsh/profiles/desktop/cordis.patch.yml` 追加 MCP 客户端行：

```yaml
- insert:
    - id: mcp-windows
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: windows
        transport: stdio
        command: 'C:\Users\XHLENOVO\.local\bin\uvx.exe'
        args:
          - '--python'
          - '3.14'
          - 'windows-mcp'
          - 'serve'
          - '--tools'
          - 'Snapshot,Screenshot,Click,Type,Scroll,Move,Shortcut,Wait,WaitFor,DisplayInventory'
          - '--control-policy'
          - 'strict'
        env:
          ANONYMIZED_TELEMETRY: 'false'
          WINDOWS_MCP_DISABLE_FLASH: '1'
        failOnStartupError: false
        startupTimeoutMs: 60000
```

改前备份：`cordis.patch.yml.bak-20261126-100431`。

## 安全取舍

- **不开放** `PowerShell`、`FileSystem`、`Registry`、`Process`、`Clipboard`、`App`；先用最小 UI 工具集。
- `--control-policy strict`：所有工具都走桌面控制权门；操作完要 `ControlStatus(release=true)`。
- 关遥测、关截图闪光。
- 仅 stdio 本地通信，不开 HTTP/SSE。

## 验证证据

- DSH 热加载后工具列表出现 `mcp__windows__*`；
- 进程：`uvx.exe → uv.exe → windows-mcp.exe → python.exe`，命令行与配置一致；
- `DisplayInventory`：2560×1600，DPI 144，scale 1.5；
- `Screenshot(region=[0,0,120,80])` 返回真实桌面图（dxcam 后端）；
- `ControlStatus(release=true)` 从 `ai` 回到 `user`，控制权正常释放。

一个已知行为：并行调用两个工具会触发 `CONTROL_PREEMPTED`，因为 strict 只允许一个控制代次；**串行调用即可**。

### 端到端点击/输入测试（2026-11-26 10:15）

- `Shortcut(win+r)` → `Snapshot` 找到“运行”编辑框 `#7` → `Type` 清空并输入 `cmd` → Enter；
- 在 cmd 窗口中心 `Type` 输入 `echo 大肥鱼桌面测试`，`Screenshot` 确认屏幕回显成功；
- 原计划的记事本测试失败：本机 `Notepad.exe` 报缺 `Microsoft.UI.Windowing.Core.dll`，无法启动（环境问题，不是 MCP 问题）；
- `Click` 调用本身成功（坐标与 label 都能点），但记事本错误框的“确定”按钮点击后窗口未关闭，最终用 `Alt+F4` 关闭；
- 操作后 `ControlStatus(release=true)`，状态回到 `ready`。

### 打开抖音创作者中心（2026-11-26 10:12）

- `Shortcut(win+r)` → `Type` 输入 `https://creator.douyin.com/` → Enter；
- Chrome 正常打开创作者中心首页，页面显示**扫码登录**；
- 没有扫码、没有点击登录、没有发布任何内容；
- 普通 Chrome 会话没有创作者中心登录态；抖音 duty 的 Cookie 在独立 Chrome profile 里，不是同一个浏览器；
- 结论：Windows-MCP 能驱动浏览器进入目标页面；登录与发布仍需单独授权和登录流程。

## 影响面

- 所有 desktop profile 会话都会看到 `mcp__windows__*` 工具，不只 `D:\大肥鱼`。
- 未改插件、未改工作区、未动账号。
- 没有点击、输入或启动任何应用；只做了读取与截图。

## 限制

- 记事本本身损坏（缺 `Microsoft.UI.Windowing.Core.dll`），需要修复系统应用后才能用它做测试；
- 端到端已用 cmd 验证，尚未覆盖浏览器/复杂应用；
- 白名单里的 `Click`/`Type` 本身仍能操作大部分界面，权限边界靠“不开放 App/文件/注册表”和控制权门；
- UAC 提权窗口、部分全屏游戏/受保护窗口可能无法操作；
- Windows-MCP 依赖 Python 3.14 与 uvx；升级需重新验证；
- 桌面内容可能含敏感信息，截图/Snapshot 会进入会话；只在需要时调用。

## 回滚

删除 `mcp-windows` 这一段，保存后等热加载或重启 DSH；或恢复备份：

```powershell
Copy-Item "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml.bak-20261126-100431" `
  "$env:USERPROFILE\.dsh\profiles\desktop\cordis.patch.yml" -Force
```

## 下一步

1. 用记事本做一次 `Click`/`Type` 安全测试（不保存）；
2. 再选一个真实桌面流程（如打开某应用、填表但不发布）；
3. 稳定后再评估是否加 `App` 或专用 `douyin-upload`。

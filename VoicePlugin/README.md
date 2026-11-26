# dsh-voice-read

大肥鱼的本地语音插件。

## 功能

- `conversation.chat.assistant-actions`：每条回复的「朗读这条回复」按钮；
- `conversation.composer.dock`：自动朗读开关；
- `conversation.view`：`语音` 视图，助手回复渲染成语音气泡，点播放、点「生成文字」展开原文；
- `conversation.chat.assistant-actions`：自动解析回复里的语音标记，生成语音气泡。

## 模型决策协议

大肥鱼自己决定要不要用声音。想用声音时，在回复里写：

```markdown
[dfy-voice-1]: # "tender|我在呢，先靠一会儿。"
```

这一行是 Markdown 链接引用定义，渲染时不可见；语音正文藏在 title 里。多段依次用 `dfy-voice-2`、`dfy-voice-3`。不要在聊天里调用 `voice_speak`，它会把音频变成文件卡。

其余文字、代码、图片照常。客户端会把这段变成可点击播放的语音气泡；标记本身是 HTML 注释，不进入可见正文。

情绪值可选：`neutral`、`happy`、`playful`、`tender`、`sad`、`love`。

## 依赖

- `http://127.0.0.1:9881/speak`：本地语音桥；
- `start-all.ps1` 负责拉起 9880 / 9881 / 9882。

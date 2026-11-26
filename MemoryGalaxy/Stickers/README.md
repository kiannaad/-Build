# 大肥鱼表情包

原创透明底 PNG，512×512，共 8 个。

| 名字 | 中文 | 用途 |
| --- | --- | --- |
| `happy` | 开心 | 翘尾巴、眼睛发亮 |
| `comfort` | 抱抱 | 张开小鳍靠过来 |
| `sleepy` | 困困 | 闭眼冒 Z |
| `speechless` | 无语 | 平嘴加省略点 |
| `angry` | 生气 | 竖眉冒怒气 |
| `shy` | 害羞 | 脸红冒星星 |
| `love` | 喜欢 | 心形眼睛 |
| `thinking` | 想想 | 歪嘴冒问号 |

## 在聊天里用

单独一行写隐藏引用定义：

```markdown
[dfy-sticker-1]: # "comfort"
```

客户端会渲染成图片，标记本身不显示。多张用 `dfy-sticker-2`、`dfy-sticker-3`。

## 静态资源

由 `http://127.0.0.1:9882/Stickers/<name>.png` 提供，不需要外网图床。

重新生成：

```powershell
cd 'D:\大肥鱼'
python Stickers\generate_stickers.py
```

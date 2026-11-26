# 大肥鱼参考音频指南

> 用途：用 BreezeBlue 生成 GPT-SoVITS 的零样本参考音频。
> 目标不是“好听”，是“同一个人、干净、自然、文本对得上”。

## 1. 声音方向

大肥鱼不是客服，也不是播音；她像住在电脑里、跟熟人说话的一条鱼。

- 青年，偏中性或女声，中低音偏软；
- 语速中慢，句尾放松，带一点笑意；
- 近场、干声、无混响、无背景音乐；
- 不幼态、不甜腻、不夸张、不新闻腔；
- 允许自然呼吸和轻微停顿，不要一字一顿。

## 2. Voice Design 提示词

### 英文（BreezeBlue 界面可直接用）

```text
A young adult Mandarin voice, warm and soft, medium-low pitch, slightly androgynous, natural conversational delivery, like talking to someone close at home. Gentle smile in the voice, relaxed pace, soft sentence endings, natural breaths, clear articulation, close-mic studio recording, dry signal, no reverb, no background music, no broadcast or customer-service tone, not childish, not overly sweet, stable volume.
```

### 中文（如果界面支持中文描述）

```text
普通话，青年声线，温柔偏软的中低音，略偏中性；像跟熟人聊天，不像播音或客服；语速自然稍慢，句尾放松，带一点笑意；近场录音，干声，无混响、无背景音乐、无其他人声；吐字清楚，音量稳定；不要幼态、不要甜腻、不要夸张。
```

## 3. 参考文本

一条一句，每句 5–10 秒；同一音色、同一语速、同一麦克风距离。

| 文件 | 情绪 | 文本 | 风格指令 |
| --- | --- | --- | --- |
| `neutral.wav` | 平静 | 嗯，我在。今天过得怎么样？不用急着说，慢慢来就好。 | 平静、自然，像熟人聊天；语速稍慢，尾音放松。 |
| `neutral_2.wav` | 平静（补音素） | 今天早上有点凉，我把窗户关小了一点，又给自己倒了杯温水。 | 同上，不要念成朗读课文。 |
| `happy.wav` | 轻快 | 你回来啦。我刚还在想，今天要不要偷偷多吃一块小饼干。 | 轻快一点，带笑意，不要兴奋过头。 |
| `tender.wav` | 温柔 | 先歇一会儿吧。事情做不完也没关系，我陪你坐一会儿。 | 放轻、放慢，像哄人休息；不要甜腻。 |
| `sad.wav` | 低落 | 其实我也有点闷。不过没关系，今天不想说话的话，我们就安静待着。 | 低一点、慢一点，不哭腔；像承认自己也有点闷。 |

## 4. BreezeBlue 操作顺序

1. 打开 **Voice Design**，粘贴上面的英文提示词，生成 3 个候选；
2. 试听，选“像熟人说话”的那个，不要选最甜/最幼的；
3. 打开 **Text to Speech**，用这个音色逐条生成上表文本；
4. 每条单独导出，不要拼接；优先 WAV，只有 MP3 也行；
5. 导出后检查：有没有背景音乐、混响、爆音、吞字、多音色。

## 5. 后处理

```powershell
ffmpeg -i input.wav -af "silenceremove=start_periods=1:start_silence=0.2,areverse,silenceremove=start_periods=1:start_silence=0.2,areverse,loudnorm=I=-16:TP=-1.5:LRA=11" -ar 44100 -ac 1 -c:a pcm_s16le output.wav
```

- 目标：44.1kHz / 16bit / 单声道；
- 只切首尾静音，不要过度降噪、不要压缩动态；
- 时长控制在 5–10 秒；超过就换更短的句子，不要硬切句子中间。

## 6. 验收清单

- [ ] 同一个人，五种语气只是语气不同，不是五个声音；
- [ ] 无音乐、无混响、无第二人声；
- [ ] 无爆音、无电流、无吞字；
- [ ] 文本与音频逐字一致（GPT-SoVITS 会用这段文本做参考）；
- [ ] 每条 5–10 秒；
- [ ] 首尾静音已切，音量大致一致。

## 7. 和 dsh-fish-mood 的映射

| 心情 | 参考音频 |
| --- | --- |
| happy / playful | `happy.wav` |
| tender / gentle | `tender.wav` |
| sad / down | `sad.wav` |
| 其它 | `neutral.wav` |

## 8. 关于 RVC

如果 BreezeBlue 生成的就是你想要的音色，GPT-SoVITS 零样本已经能直接用，**RVC 不是必须的**。

RVC 只在两种情况下有意义：

- 你手里已经有 `feiyu_v2.pth`，想统一转成那个音色；
- GPT-SoVITS 出来的音色总差一点，需要后处理。

先别把 RVC 接进主链路，等 GPT-SoVITS 的参考音频效果确认后再决定。

## 9. 隐私

- 参考文本都是通用句子，不含个人信息；
- BreezeBlue 会把文本发到云端合成，生成音频后本地保存；
- 不要用未经授权的人声做参考或克隆。

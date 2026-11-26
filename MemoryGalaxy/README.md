# 大肥鱼 · 记忆星河

零依赖的本地 3D 记忆星图。数据来自 `MemoryService` 的 Memory v2 SQLite。

## 运行

```powershell
cd 'D:\大肥鱼'
python MemoryService\export_galaxy.py

cd MemoryGalaxy
python -m http.server 9882
```

浏览器打开 `http://127.0.0.1:9882/`。

## 操作

- 拖拽：旋转
- 滚轮：缩放
- 点击星星：查看记忆正文、标签、来源事件
- 顶部搜索/分类：过滤
- 双击或「重置」：回到初始视角
- 选中记忆后可点「让大肥鱼读给我听」（需要 9881 语音桥）

## 数据与隐私

- `galaxy.json` 由本机记忆库导出，含私人记忆，**不要提交到公开仓库**；
- 已加入 `.gitignore`；
- 默认排除 `sensitivity=restricted`；
- 页面不联网（朗读按钮除外，只访问本机 9881）。

## 下一步

- 换 `3d-force-graph` / React Three Fiber 做更漂亮的辉光；
- 时间轴回放；
- 嵌进 DSH 右侧栏或对话视图。

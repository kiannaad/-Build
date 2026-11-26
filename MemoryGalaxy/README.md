# 大肥鱼 · 记忆星河

本地 3D 记忆星图。数据来自 `MemoryService` 的 Memory v2 SQLite。

- 稳定主页：`index.html`（3d-force-graph / ThreeJS，WebGL）
- Bloom 实验版：`galaxy-lab.html`（自定义 Three.js + 22k 粒子 + UnrealBloomPass）
- 退路：`index-2d.html`（零依赖 Canvas 版，仍可打开）
- 图库：`vendor/3d-force-graph.min.js`（1.80.2，离线，1.33MB）
- 特效层：`#dust`（背景星海/银河尘埃）+ `#glow`（节点光晕），Canvas 2D + `screen` 混合

## 运行

```powershell
cd 'D:\大肥鱼'
python MemoryService\export_galaxy.py

cd MemoryGalaxy
python -m http.server 9882
```

浏览器打开 `http://127.0.0.1:9882/`。

## 操作

- 拖拽旋转、滚轮缩放；
- 点星星：相机靠近，右侧打开正文、标签、来源事件；
- 标签星：展开相关记忆，点条目跳转；
- 来源事件可点击；
- 顶部搜索/分类过滤；
- 「重置」回到全景。

## 数据与隐私

- `galaxy.json` 由本机记忆库导出，含私人记忆，**不要提交到公开仓库**；
- `preview-3d*` / `preview*` / `detail-*` 都在 `.gitignore`；
- 默认排除 `sensitivity=restricted`；
- 页面不联网（朗读按钮除外，只访问本机 9881）。

## 备注

3D 版用固定坐标布局：记忆按 kind 分环，事件贴来源，标签在星云中心，核心在正中。这样比纯力导向更像“星图”，也避免 56 个节点摊成孤岛。

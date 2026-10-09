---
name: "ugc-ad-studio"
description: "制作 UGC 手机实拍风竖屏视频广告：拆解参考广告的分镜脚本，按锁定的实拍风格生成/混剪素材，配 TTS 旁白与烧录字幕，组装成符合 Meta 投放规格的成片。用户说"做一条 UGC 广告""照着某条广告改一版"时用。"
metadata: { "includeInPrompt": true }
---

# UGC Ad Studio

## Purpose

把一条参考广告（通常是 Facebook 广告库里的竞品 UGC 广告）复刻/改造成自有品牌的竖屏视频广告，
全程走"手机实拍感"风格。产出：55 秒完整版 + 30 秒精简版，1080x1920，可直接投 Meta。

## Workflow

### 1. 参考片分析
- 拿到参考广告的视频文件（FB 广告库经 1089 专线 + Selenium 抓取，见 `references/sourcing.md`）。
- 完整看一遍，输出 beat sheet：钩子（0-3s）→ 对比 → 故事 → 机制 → 恐惧诉求 → 佐证 →
  演示 → 保证 → CTA。记录每段话术、画面、节奏。**先发用户过目，用户点头再动手。**

### 2. 风格锁定
- 默认风格见 `references/style-guide.md`（用户 2026-10-03 亲批）：iPhone 手持实拍感，
  去电影感，多源拼贴。新项目先跟用户确认沿用还是调整。

### 3. 素材轨道（二选一或并行）
- **A. 混剪**：YouTube 经 yt-dlp + 1089 代理找实拍素材（见 `references/sourcing.md`）。
  第三方素材仅作内部测试对比；正式投放用 AI 生成或自有/可商用素材（版权红线，见 Operating Rules）。
- **B. AI 生成**：`media.generate_video`（零付费）按 style-guide 的 prompt 规范逐镜头生成，
  每个镜头抽帧 QC，有"AI 精致感"即重生成。hypit 官方链路（HypiHub/BYOK）需用户授权才可用。

### 4. 旁白
- `/opt/hatch/bin/tts speak --voice avocado_v2:MAI_01`（Aria，温暖女声），英文，分段生成，
  每段时长决定对应镜头的剪辑长度（音频驱动 timing）。

### 5. 组装（ffmpeg）
- 9:16 竖屏，烧录字幕（白字黑边，一次 1-2 行短句），字幕必须进安全区（底部 35% 留空）。
- 模板脚本：`bin/assemble.py`（按 beat sheet 配置源素材/旁白/字幕）。
- 输出：55 秒完整版 + 30 秒精简版（Reels/Stories）。

### 6. 交付前检查
- [ ] 1080x1920, H.264 + AAC, 30fps, MP4
- [ ] 字幕在安全区内，全程静音可读
- [ ] 前 3 秒有钩子，结尾 CTA 停留 ≥3 秒
- [ ] 无品牌名（除非用户明确要求）、无第三方水印/尾卡
- [ ] 文案无绝对化功效宣称（参照 references/meta-specs.md 的政策红线）

## Tooling

- **FB 专线**：sing-box SOCKS5 `127.0.0.1:1089`（配置 `~/workspace/fb-ad-node/config.json`，
  经用户提供的两个 VLESS Reality 节点自动选优）。**仅用于 Facebook 广告库/素材抓取**，
  与账号养号的干净节点（1088 / 192.220.59.232，铁律）是两条独立通道，不得混用。
  若 1089 不通：先 `curl --proxy socks5h://127.0.0.1:1089 https://ipinfo.io/ip` 验出口，
  期望 `38.92.14.150` 或 `38.150.35.60`。
- **抓取**：Selenium + geckodriver + 官方 Firefox（`~/workspace/remote-browser/firefox/firefox`），
  专用 profile（proxy 指 1089），不碰被常驻浏览器占用的主 profile。模板见 `references/sourcing.md`。
- **下载**：`python3 -m yt_dlp --proxy socks5h://127.0.0.1:1089`。
- **TTS**：`/opt/hatch/bin/tts`（读 tts skill）。
- **生成**：`media.generate_video`（读 media skill 的 video 部分）。
- **剪辑**：系统 `ffmpeg`。

## Output Contract

- 成片 MP4（55s + 30s）+ 每版一句话说明 + 与参考片的差异点。
- 素材来源清单（混剪：视频 ID 列表；AI：镜头 prompt 存档），供复用和追责。

## Operating Rules

1. 参考片分析发用户过目，用户点头才进入制作；成片发布/投放前必须再过目一次。
2. 不产生任何付费（media 管道免费；hypit 官方链路、任何订阅都要用户明确批准）。
3. 第三方平台（YouTube/TikTok/IG）下载的他人视频**仅限内部测试对比**，不得直接用于正式投放；
   正式版只用 AI 生成、自有实拍或明确可商用的素材。向用户说明这一区别。
4. 品牌名、产品名默认不出现，用户说加才加。
5. 节点凭证（VLESS URL）只写 600 权限配置文件，不进聊天、不进 skill 文档、不进 memory；
   聊天里出现过的视为已泄露，提醒用户轮换。
6. 保持与 `~/workspace/fb-ad-node/UGC-STYLE-GUIDE.md` 一致；风格有变先更新那份规范再动手。

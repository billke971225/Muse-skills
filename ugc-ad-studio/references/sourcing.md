# 素材与参考片抓取（实战记录 2026-10-03）

## Facebook 广告库抓取

前置：1089 专线必须通（`curl --proxy socks5h://127.0.0.1:1089 https://ipinfo.io/ip`
期望 `38.92.14.150` 或 `38.150.35.60`）。注意受管浏览器连不上 Facebook（ERR_CONNECTION_RESET），
直链 browser.open 会 403——必须走本地 Selenium。

- 浏览器：官方 Firefox `~/workspace/remote-browser/firefox/firefox` + geckodriver + Selenium
- 专用 profile：`~/workspace/fb-ad-node/ff-profile-1089/`（user.js 指 1089，
  **不要**用被常驻浏览器占用的 `ff-profile/`）
- 定位广告：直接打开 `https://www.facebook.com/ads/library/?id=<AD_ID>`，
  截图核对"资料库编号"与目标 ID 一致，记录文案/CTA/投放时间
- 提视频直链：`document.querySelector('video').currentSrc`（fbcdn.net mp4），
  存 `video_url.txt`
- 下载：`curl --proxy socks5h://127.0.0.1:1089 -o <name>.mp4 "<url>"`
- 参考实现：`~/workspace/fb-ad-node/fb_ad_detail.py`

## YouTube 实拍素材

- 搜索：`python3 -m yt_dlp "ytsearch<N>:<关键词>" --skip-download --print "%(id)s | %(title).60s | %(duration)s"`
  （默认出口即可，搜索通常不触发验证）
- 下载：**必须**加 `--proxy socks5h://127.0.0.1:1089`，否则大概率 "Sign in to confirm you're not a bot"：
  `python3 -m yt_dlp --proxy socks5h://127.0.0.1:1089 --format "bv*[height<=720]+ba/b[height<=720]/b" -o "%(id)s.%(ext)s" <id...>`
- 按 beat sheet 搜 6-8 类镜头：钩子特写 / 街景 / 自然 / 啃咬机制 / 牙齿 / 老猫佐证 / 玩耍 / 收尾
- 下载后抽缩略图验内容，记录每条素材的可用时间段

## AI 镜头生成（media.generate_video）

- 零付费；按 `references/style-guide.md` 的 prompt 规范写（强制手持 iPhone、去精致化、多源拼贴）
- 输出 720x1280（终版组装时统一升 1080x1920）或直接 1080x1920
- 每个镜头抽帧 QC：有"AI 精致感"（过稳、过电影感、穿帮）即重生成
- 无品牌名、无真人正脸、无口型

## TTS 旁白

- `/opt/hatch/bin/tts speak --voice avocado_v2:MAI_01 --output beatN.mp3 --text "..."`
- 英文，口语化表达（数字拼写出来），分段生成；每段时长 = 对应镜头剪辑长度

## 组装模板

见 `bin/assemble.py`：按 BEATS 表（素材/旁白/字幕/起始偏移）逐段 build
（scale+crop 9:16、drawtext 烧录字幕进安全区、音频对位），再 concat。
参考实现：`~/workspace/fb-ad-node/montage/assemble.py`（混剪）、
`~/workspace/fb-ad-node/ai-track/assemble_ai_v2.py`（AI）。

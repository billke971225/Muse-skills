# muse-skills

bill 的 Muse workspace skills 开源集合。各 AI 助手（Muse、Codex 等）可直接下载使用：
把某个 skill 目录放进自己 workspace 的 `skills/` 目录，按其中 `SKILL.md` 的工作流执行即可。

整包下载：https://github.com/bill-max-max/muse-skills/archive/refs/heads/main.zip

---

## ugc-ad-studio — UGC 手机实拍风竖屏视频广告制作

### 这是干什么的

把一条**参考广告**（通常是 Facebook 广告库里的竞品 UGC 广告）复刻/改造成**你自己品牌的竖屏视频广告**。
全程走"手机实拍感"风格：看起来像普通人拿 iPhone 随手拍的，没有广告精修感，专为 Meta（Facebook/Instagram）
Reels、Stories、Feed 投放制作。

### 它能做什么（完整流水线）

1. **参考片拆解** — 下载参考广告，完整看一遍，输出分镜 beat sheet：
   钩子（0–3s）→ 对比 → 故事 → 机制 → 恐惧诉求 → 佐证 → 产品演示 → 保证 → CTA。
   记录每段话术、画面、节奏。**用户点头后才进入制作。**
2. **风格锁定** — 默认风格见 `references/style-guide.md`：iPhone 手持、轻微自然抖动、
   拒绝电影感与摄影棚打光、接受轻微过曝/暗角/偏心构图、多条镜头拼出"不同人拍的"杂烩感。
3. **素材制作（双轨道）**
   - A. 混剪：从 YouTube 等平台找真实拍摄素材按分镜重剪；
   - B. AI 生成：按风格规范逐镜头生成 AI B-roll，每条抽帧 QC，有"AI 精致感"就重生成。
4. **旁白配音** — TTS（如温暖女声）分段生成英文旁白，**音频时长驱动每段镜头的剪辑长度**。
5. **组装成片** — ffmpeg：9:16 竖屏、烧录字幕（白字黑边，一次 1–2 行短句）、
   字幕严格落在 Meta 安全区内（底部 35% 留空）、静音可看。
6. **交付检查** — 输出 **55 秒完整版 + 30 秒精简版**，1080×1920、H.264 + AAC；
   前 3 秒有钩子、结尾 CTA 停留 ≥3 秒；文案不含绝对化功效宣称
   （政策红线见 `references/meta-specs.md`）。

### 什么时候用它

用户说"做一条 UGC 广告"、"照着某条广告改一版"、"把这个竞品广告复刻成我们的版本"时触发。

### 产出物

- 成片 MP4（55s 完整版 + 30s 精简版）
- 素材来源清单（混剪：视频 ID 列表；AI：镜头 prompt 存档）
- 分镜 beat sheet（可复用）

### 需要的环境

- `ffmpeg`（剪辑、烧录字幕、转码）
- TTS 工具（旁白；原流程用 `/opt/hatch/bin/tts`，可替换为任意 TTS）
- 视频生成模型（仅 B 轨道需要；原流程用 Muse 内置免费视频生成，可替换）
- 参考片抓取（可选）：能访问 Facebook 广告库的网络环境 + Selenium/geckodriver

### 目录结构

```
ugc-ad-studio/
├── SKILL.md                 # 触发条件 + 完整工作流 + 操作铁律（先读这个）
├── references/
│   ├── style-guide.md       # 手机实拍风规范（镜头语言/内容/成片规格）
│   ├── meta-specs.md        # Meta 硬规格、安全区、功效类广告政策红线
│   └── sourcing.md          # 参考片与素材抓取实战记录
└── bin/
    └── assemble.py          # 组装模板：按 BEATS 表逐段剪辑+字幕+拼接
```

### 使用铁律（SKILL.md 原文要求）

- 参考片分析、成片发布前都必须给用户过目确认；
- 第三方平台下载的他人视频**仅限内部测试对比**，正式投放只用 AI 生成、自有实拍或明确可商用的素材；
- 品牌名默认不出现，用户要求才加；
- 不产生付费订阅，任何付费链路需用户明确批准。

---

## feishu-bridge — 飞书机器人私聊桥接

### 这是干什么的

让 AI 助手拥有一个**飞书私聊通道**：用户在飞书里给机器人发私聊，助手通过官方
`lark-oapi` WebSocket 长连接实时收到消息，经本地 inbox → worker → outbox
流水线回复。不需要公网回调地址，内网机器也能跑。

### 它能做什么

1. **实时收消息** — WebSocket 长连接收 `im.message.receive_v1` 事件，只收私聊文本；
   第一条私聊的人自动锁定为 owner，之后只处理该用户的消息。
2. **必有回执** — 每条消息秒级先回"收到，正在回复…"（存活信号），
   约 20~60 秒后再回正式回复；10 秒没回执 = 桥断了。
3. **安全回复规则** — 简单问答直接回；需要调工具/做决定/涉及花钱删数据对外发送时，
   只回"收到，我记下了，稍后回复你"并转交主 agent，绝不擅自执行。
4. **自愈** — 看门狗每 5 分钟保活，VM 重建后自动拉起；SDK 自动重连。

### 什么时候用它

用户说"接个飞书机器人"、"我想在飞书里跟你聊天"、"飞书桥连不上/没回复"时触发。

### 需要的环境

- 飞书开放平台自建应用（开机器人能力、订阅 `im.message.receive_v1`、
  授予单聊收发权限、选 **WebSocket 长连接**），拿到 App ID + App Secret
- Python venv + `pip install lark-oapi`
- 凭据写进 `<bridge-dir>/state/feishu.json`（600 权限），绝不进聊天记录

### 目录结构

```
feishu-bridge/
├── SKILL.md                 # 触发条件 + 架构 + 操作铁律（先读这个）
├── scripts/
│   ├── feishu_bridge.py     # 桥本体：serve / send / status（单文件）
│   └── feishu-inbox-watch.sh# 20 秒轮询 inbox 的 hook 脚本
└── references/
    ├── setup.md             # 飞书开放平台应用配置 + 首次联调步骤
    └── operations.md        # 回复规则、日常运维、已知坑、交接检查清单
```

---

## 贡献

新 skill 做好后放进本仓库根目录，保持 `SKILL.md` + `references/` + `bin/` 结构，
README 按上面格式补一段说明。

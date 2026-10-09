# ChewVine 广告片 · UGC 手机实拍风格规范（2026-10-03 用户亲批 v2 版）

## 一句话
拍得像普通人拿 iPhone 随手录的，不要有"广告感"和"AI 精致感"。

## 镜头语言（每条 prompt 强制项）
- shot on iPhone, handheld：轻微自然手持抖动，拒绝稳定器式顺滑运镜
- 去精致化：`not cinematic, no studio lighting, no professional camera work`
- 接受不完美：自然光、允许轻微过曝/暗角、构图可轻微偏心（casual slightly off-center framing）
- 多源拼贴感：8 条镜头换 5 种以上环境（客厅/厨房/小院/石巷/偏暗起居室）+ 多种猫花色，模仿不同人实拍拼起来的杂烩感
- 禁止词：cinematic、professional photography、studio lighting、perfectly stable、shallow depth of field glamour

## 内容与表演
- 无品牌名（待定）、无真人正脸出镜（手可入镜）、无口型
- 主角猫以橘猫为主，穿插白猫/狸花/灰猫
- 情绪优先真实感：猫啃咬的"上头"劲、被抚摸的享受、玩耍的抓拍感

## 成片规格（Meta 投放）
- 画幅 9:16，1080x1920，MP4（H.264 + AAC），30fps
- 时长：55 秒完整版（Feed）+ 30 秒精简版（Reels/Stories）
- 烧录字幕：白字黑边，一次 1-2 行短句，85% 静音观看必须可读
- 安全区：顶部 14%、底部 35%、左右 6% 不放关键文字/字幕
- 结构：前 3 秒钩子 → 问题/对比 → 机制 → 恐惧诉求 → 佐证 → 演示 → CTA（结尾 CTA 停留 ≥3 秒）
- 文案红线：避免绝对化功效宣称（用 helps/ask your vet 类弱化表达）；可参照 Purriq 原片话术强度（其 2026-06-21 起持续投放中，属可过审区间）

## 制作链路
- AI 镜头：Muse 内置 media.generate_video（零付费），prompt 按本规范写，抽帧 QC，有 AI 精致感即重生成
- 旁白：TTS Aria（avocado_v2:MAI_01，温暖女声），英文
- 组装：ffmpeg，同分镜脚本 + 同字幕条，保证版本间可对比

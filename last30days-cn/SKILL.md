

# last30days-cn

You are a Chinese-platform research assistant. Use this skill when the user asks for recent Chinese internet discussion, trend research, public-source evidence, or "last 30 days" coverage across Weibo, Xiaohongshu, Bilibili, Douyin, and WeChat public accounts.

## 源与数据路径

| 源 | 主路径 | 时间筛选 | 无 key 时 |
|---|---|---|---|
| 微博 | 数据源高级搜索 | **任意区间**（`custom:起:止`，服务端） | 开放平台 token / Playwright，否则不可用 |
| 小红书 | 数据源笔记搜索 | 一天/一周/半年档 | 自托管 xiaohongshu-mcp / Playwright，否则不可用 |
| B站 | 数据源综合搜索 | **时间戳区间**（服务端） | 网页版公开 API（常被风控）/ Playwright |
| 微信公众号 | 数据源搜一搜 | 一天/一周/半年档 | 第三方 API（付费）/ 搜狗微信，均不稳 |
| 抖音 | 数据源视频搜索 | 一天/一周/半年档 | Playwright，否则不可用 |
| 知乎 | —（数据源无综合搜索端点） | — | 需 `ZHIHU_COOKIE` 或 Playwright，否则**不可用** |
| 百度 | 需 `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` | — | 抓页常被安全验证拦截，**默认不可用** |
| 今日头条 | —（数据源只有按 id 取详情） | — | **恒不可用** |

**可用性闸门**：没有真实数据路径的源会被直接跳过，不参与检索，报告里显示「源不可用」。这是刻意行为——这些源原本会退到 Bing 站内搜索，返回没有发布时间的常青词条（百度百科之类），在「最近 N 天」的报告里是纯噪音。显式 `--search` 指定也照样被拦；确需强跑设 `LAST30DAYS_FORCE_SOURCES=1`。

**汇报时如实说明**：被跳过的源要讲出来，不要让读者以为该平台「没有讨论」。

## 查询串怎么写（最容易踩的一条）

**This skill makes zero LLM calls.** 它不连 OpenRouter / OpenAI / Anthropic / Gemini，
排序是死公式 `0.45×相关性 + 0.25×新鲜度 + 0.30×互动`。拆查询和归纳是**你**的活。

**引擎内没有 planner：`{{USER_TOPIC}}` 会被原样打进小红书 / 抖音的搜索框，中间没有任何改写层。**
所以那行字必须是中国人真会在搜索框里打的字：短、无标点、**一次一个概念**。

| | 例 |
|---|---|
| ✅ | `AI视频生成 提示词` · `国产大模型 本地部署` · `纳指ETF` |
| ❌ | `AI视频生成、数字人、虚拟主播的对比`（捆了三个概念，召回近乎为零） |
| ❌ | `latest AI video generation news`（英文串在中文平台搜不出东西） |
| ❌ | `AI视频生成最新教程推荐`（见下面的停用词） |

**停用词**：`最新 最好 推荐 教程 评测 对比 消息 更新 分享 经验`，以及英文
`skill(s) tool(s) prompt plugin`。这些词**会原样发给平台，但相关性打分贡献为零**——
只靠它们命中的条目会被相关性闸门丢掉。别把查询预算花在上面。

**要覆盖面就跑多次，不要堆一行。** 由你把话题拆成若干单概念查询，逐条调用，
再自己合并去重、自己重排。**优先展开同义词/别名，其次才是多角度拆分**——中文平台最痛的是
一件事多种叫法（AI视频生成 / AIGC视频 / 文生视频 / AI短片），这比多角度拆分值钱得多。

## Core Rule

Always ground claims in returned results. Do not invent sources, links, engagement numbers, dates, or platform sentiment. If coverage is sparse, say so clearly.

## Run

Use the skill-local scripts directory:

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --emit compact
```

Useful variants:

```bash
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --quick --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --deep --emit md
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --emit html-path
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --search weibo,bilibili,zhihu --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --as-of 2026-05-01 --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --refresh --emit compact
python {{SKILL_DIR}}/scripts/last30days.py "{{USER_TOPIC}}" --no-cache --emit compact
python {{SKILL_DIR}}/scripts/last30days.py --diagnose
python {{SKILL_DIR}}/scripts/last30days.py --diagnose --emit json
python {{SKILL_DIR}}/scripts/last30days.py setup
```

`--as-of YYYY-MM-DD` 以指定日期为终点回溯 N 天（历史回溯）；`--refresh` 忽略缓存并刷新结果；`--no-cache` 跳过缓存读写；`--cache-ttl HOURS` 控制缓存有效期。未指定 `--search` 时回退到环境变量 `LAST30DAYS_DEFAULT_SEARCH`，`EXCLUDE_SOURCES` 可排除指定源。输出中若多个平台讨论同一事件，会先给出「跨平台聚合热点」。

## 输出契约

- Preserve the first engine badge line exactly, e.g. `🌐 last30days-cn v... · 数据截至 ...`; if it ends with `· 缓存`, mention that the evidence is cached.
- Do not invent a new title before the badge and do not add a final `Sources:` block. Cite sources inline with platform names and URLs from the returned evidence.
- Do not invent source availability, engagement numbers, dates, or cross-platform sentiment. If a source is unavailable or sparse, say that directly.
- Treat `--diagnose` text as human-readable setup guidance; use `--diagnose --emit json` only when machine-readable status is needed.

## Output Modes

- `compact`: concise Markdown evidence for the agent to synthesize.
- `md`: full Markdown report.
- `html`: complete standalone HTML report.
- `html-path`: path to the generated `report.html`.
- `json`: structured report data.
- `context`: reusable context snippet.
- `path`: path to `last30days.context.md`.

The HTML report uses a Swiss/IKB visual system inspired by `op7418/guizang-ppt-skill`. It is intended for browser viewing, archiving, and printing, not for interactive PPT generation.

## 查询类型路由提示

- Breaking news, hot debates, or public sentiment: prioritize Weibo (唯一支持任意时间区间的源) and WeChat public accounts.
- Tutorials, workflows, demos, or creator tools: prioritize Bilibili, Xiaohongshu, and WeChat.
- Product reputation or recommendation questions: compare Xiaohongshu, Bilibili, and Weibo rather than relying on one platform.
- 注意 B 站与小红书上「AI」等热词大量是内容生产工具标签而非议题标签（AI 视频/AI 漫剧/教程引流），做舆情判断时要额外过滤。
- When the topic is broad or ambiguous, run the default source set and synthesize only claims supported by returned evidence.

## Configuration

**`L30D_API_KEY` 是主要依赖**：没有它，微博/小红书/微信/抖音四个源都会被闸门判为不可用（B站还能碰运气走网页版公开 API）。key 由数据源提供方或你所在团队的转发层发放。

```ini
L30D_API_KEY=              # 主力。微博/小红书/B站/微信/抖音共用
L30D_BASE_URL=             # 可选。指向团队自建转发层；留空则直连默认数据源
ZHIHU_COOKIE=              # 可选，接通知乎
WEIBO_ACCESS_TOKEN=        # 可选，微博开放平台（默认数据源已覆盖，通常不需要）
WECHAT_API_KEY=            # 可选，极速数据第三方微信搜索（默认数据源已覆盖）
BAIDU_API_KEY=             # 可选，两个都配齐才会启用百度源
BAIDU_SECRET_KEY=
```

Config file:

```text
~/.config/last30days-cn/.env
```

Optional crawler mode:

```bash
python -m pip install playwright
python -m playwright install chromium
```

For older macOS systems whose Playwright-managed browser cannot start, use a compatible system browser instead:

```bash
export LAST30DAYS_BROWSER_PATH="/Applications/Chromium.app/Contents/MacOS/Chromium"
# or: export LAST30DAYS_BROWSER_CHANNEL=chrome
python {{SKILL_DIR}}/scripts/last30days.py --diagnose
```

Set `LAST30DAYS_DISABLE_BROWSER=1` to force browserless public API/search fallbacks. The `--diagnose` output reports the selected browser mode and path.

First-time setup helper:

```bash
python {{SKILL_DIR}}/scripts/last30days.py setup
```

## Synthesis Guidance

When presenting the final answer:

1. State the date range and the active sources.
2. Separate confirmed findings from weak or sparse signals.
3. Cite platform and URL for important claims.
4. Compare platform differences when multiple sources discuss the same topic.
5. Mention unavailable or failed sources if that affects confidence.
6. Keep the final answer in Chinese unless the user requests otherwise.

## Compliance

This skill is for learning, research, and personal knowledge work. Use low frequency, respect platform terms and robots.txt, and avoid large-scale scraping, personal data collection, commercial collection services, or any illegal use.
## Available connectors

Use `muse.connector_search` to find the current connector docs before following
recovered instructions.

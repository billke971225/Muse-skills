# last30days-cn (数据源 版) v3.3.0-cn-tikhub

中文平台舆情检索引擎。给定一个话题，从**微博、小红书、B站、微信公众号、抖音**拉回最近 N 天的真实讨论，
带发布时间、作者、互动数和原链接，输出给 agent 做归纳。

**零 LLM 调用。** 不连 OpenRouter，不连 OpenAI / Anthropic / Gemini，不读任何模型 API key。
拆查询、重排序、归纳——都是装载方（你的 agent）自己的活。因此成本只有 数据源 一项、
排序是可复现的死公式、没有静默降级的模型调用。自己验：

```bash
grep -rn "openrouter\|api.openai\|generativelanguage" scripts/ tools/   # 无输出
```

> **要装进 agent 的，先读 [`AGENTS.md`](AGENTS.md)。** 那里有一条最容易踩的约束：
> **本引擎没有 planner，你输入的话题串会被原样打进小红书搜索框**，所以一次只能一个概念，
> 不能捆多个、不能带标点、`最新/推荐/教程` 这类词相关性打分为零。

基于 [Jesseovo/last30days-skill-cn](https://github.com/Jesseovo/last30days-skill-cn) v3.2.0 修改，
改动见 `CHANGELOG.md`。

## 它和上游的核心区别

**五个源改走统一数据源**，因此时间窗是在**服务端**筛选的，拿回来的每条都带真实发布时间戳：

| 源 | 时间筛选能力 |
|---|---|
| 微博 | **任意区间**（`custom:起:止`，响应会回显生效区间） |
| B站 | **时间戳区间** |
| 小红书 / 微信 / 抖音 | 一天 / 一周 / 半年档 |

**没有真实数据路径的源会被跳过，而不是退化成搜索引擎兜底。** 上游的行为是：知乎/头条/百度接口挂掉后，
去 Bing 搜 `site:zhihu.com xxx`，捞回几条没有发布时间的常青词条（百度百科之类），在报告里挂上「知乎」
标题。那不是该平台的舆情，是噪音。本版本改为如实标注「源不可用」。

## 依赖

- **Python 3.9+，无第三方依赖**（纯标准库）
- **一个数据源 API key** —— 这是主要依赖。没有它，微博/小红书/微信/抖音四个源都会被判为不可用。
  两种取法，二选一：
  - **团队用户**：向你所在团队的转发层管理员要一个 key，同时拿到 `L30D_BASE_URL`。
    这样你不需要自己注册任何账号。
  - **自己装**：本项目默认上游是 [TikHub](https://tikhub.io)（$0.001/次、非 200 不计费，
    注册送额度够跑几十次）。注册后把 key 填进 `L30D_API_KEY`，`L30D_BASE_URL` 留空即可。

可选：`pip install playwright && playwright install chromium` 启用爬虫模式（可让知乎等源恢复可用）；
`pip install jieba` 改善中文分词（否则退回 CJK bigram）。

## 安装

这是一个**自包含目录**，放到宿主能读到的地方即可，没有安装脚本，没有构建步骤。

```bash
git clone https://github.com/sunnyseed/last30days-cn-skill.git <你的技能目录>/last30days-cn
```

配置 key，三选一（优先级：进程环境 > 项目配置 > 全局配置）：

```bash
# 1. 进程环境变量（最简单，也适合容器/CI）
export L30D_API_KEY=your_key

# 2. 全局配置文件
mkdir -p ~/.config/last30days-cn
cp .env.example ~/.config/last30days-cn/.env && chmod 600 ~/.config/last30days-cn/.env
# 然后填 key

# 3. 项目级配置：在工作目录（或其任一上级）放 .claude/last30days-cn.env
#    权限必须 600，否则引擎每次告警
```

自检：

```bash
python3 scripts/last30days.py --diagnose
```

看到微博/小红书/B站/微信/抖音为 ✅ 即可用。知乎/头条/百度显示 ❌ 是**预期行为**，原因见上。

## 跑起来

```bash
python3 scripts/last30days.py "话题" --emit compact          # 给 agent 归纳用，最常用
python3 scripts/last30days.py "话题" --days 1                 # 只看最近一天
python3 scripts/last30days.py "话题" --search weibo,wechat    # 指定源
python3 scripts/last30days.py "话题" --deep --emit md         # 深度检索，完整 Markdown
python3 scripts/last30days.py "话题" --emit html-path         # 生成独立 HTML 报告，返回路径
python3 scripts/last30days.py "话题" --refresh                # 忽略缓存重新检索
python3 scripts/last30days.py --diagnose                      # 源状态自检
```

输出格式：`compact`（精简证据，喂给模型）/ `md` / `html` / `html-path` / `json` / `context` / `path`。

**失败结果也会进缓存**。调试时记得带 `--refresh`，否则你会一直看到上一次的空结果。

## 接进一个 bot / agent

**完整的接入说明在 [`AGENTS.md`](AGENTS.md)**（查询串怎么写、输出契约、可用性闸门、已知失真）。
这里只列三种接法：

**A. 子进程（推荐，最省事）** —— 宿主能跑 shell 就行：

```python
import subprocess, os
out = subprocess.run(
    ["python3", "scripts/last30days.py", topic, "--emit", "compact"],
    capture_output=True, text=True, timeout=300,
    env={**os.environ, "L30D_API_KEY": key},
).stdout
```

把 `out` 连同「只能引用返回结果里的链接和数字，不得编造」的指令一起塞给模型。

**B. 直接 import** —— 宿主是 Python：

```python
import sys; sys.path.insert(0, "<包目录>/scripts")
from lib import env
from last30days import search_all_sources

config = env.get_config()
result = search_all_sources("话题", config, "2026-09-01", "2026-09-14", depth="default")
```

**C. 当 skill 装** —— 宿主支持 Agent Skill 规范：`SKILL.md` 就是技能清单，里面的
`{{SKILL_DIR}}` 占位符按宿主约定替换成包所在路径。

## 给模型的硬约束

`SKILL.md` 里写了，宿主不读 SKILL.md 的话请手工加进 system prompt：

1. **只用返回结果里的内容**。不得编造链接、互动数、日期、平台情绪。
2. **被跳过的源要如实说出来**，不要让读者以为该平台「没有讨论」。
3. **微博的互动数当前恒为 0**（上游解析层未提供，不是真实为零），因此不要按热度排序，也不要
   说「某条点赞为零」。
4. B站/小红书上「AI」这类热词大量是**内容生产工具标签**而非议题标签（AI 视频、AI 漫剧、教程引流），
   做舆情判断时要额外过滤。
5. 单一信源、无交叉印证的说法要标注为未证实。

## 验证

```bash
python3 tests/test_tikhub_sources.py        # 四源解析回归（桩掉网络，不计费）
python3 tests/test_xiaohongshu_tikhub.py    # 小红书链路回归
```

fixture 是**实测响应**裁到 2 条——数据源的 OpenAPI 把 1063 个端点的 200 响应全标成同一个通用
`ResponseModel`，字段没有任何约定，所以回归必须拿真实结构跑。

全量 23 个测试**都能用 `python3` 直接跑，不需要 pytest**，且全部离线：

```bash
for t in tests/test_*.py; do python3 "$t" >/dev/null 2>&1 \
  && echo "PASS $t" || echo "FAIL $t"; done
```

## 附带工具

`tools/xhs_note.py` —— 取小红书单条笔记的正文、评论和配图。存在理由：搜索结果只有标题和摘要，
而「限购额度一览表」这类笔记的干货全在配图里。

```bash
python3 tools/xhs_note.py <note_id|分享链接> [--comments 30] [--images]
```

不属于检索引擎，独立使用。

## 已知边界

- **响应时间抖动**：数据源上游 2s~30s+ 不等，B站见过 34s。引擎内置 45s 超时 + 3 次退避重试
  （超时不计费，重试免费），但微博单页最慢，引擎对每个源有 60s 硬超时，故微博额外压了 40s 的
  翻页时间预算，宁可少翻一页也不整源超时。
- **必带 UA**：所有数据源请求都带 UA，不带会被数据源前面的 Cloudflare 拦成 `403 error code 1010`。
  自己扩端点时别忘了。
- **知乎无解**：数据源只有文章/专栏/话题分类搜索，没有综合搜索，要接得自己拼几个端点。
- **头条无解**：数据源只有按 id 取详情，没有搜索端点。
- **百度**：抓页时灵时不灵（会被安全验证拦），配齐 `BAIDU_API_KEY` + `BAIDU_SECRET_KEY` 才启用。
- **成本**：一次默认检索约 5~15 次调用，$0.005~0.015。

## 合规

仅供学习、研究与个人知识工作。低频使用，尊重平台条款，不做大规模抓取、个人数据收集或商业化采集。

MIT License，继承自上游。

# 相对上游的改动

基线：[Jesseovo/last30days-skill-cn](https://github.com/Jesseovo/last30days-skill-cn) v3.2.0-cn
本版本：v3.3.0-cn-tikhub

## 新增：`lib/tikhub.py` 共享客户端

鉴权、UA、45s 超时、3 次退避重试、`bucket()` 时间分档统一收在这里。各平台模块只写自己的
参数与解析。

## 五个源改走 TikHub

| 源 | 端点 | 说明 |
|---|---|---|
| 小红书 | `xiaohongshu/app_v2/search_notes` | 原本无 TikHub 路径 |
| 微博 | `weibo/web_v2/fetch_advanced_search` | `timescope=custom:起:止`，**唯一支持任意时间区间**的源 |
| B站 | `bilibili/web/fetch_general_search` | `pubtime_begin_s/end_s` 时间戳区间；返回结构与网页版一致，复用 `_parse_video` |
| 微信 | `wechat_search/v2/fetch_search` | 搜一搜；替代付费的极速数据 `api.jisuapi.com` |
| 抖音 | `douyin/search/fetch_video_search_v1` | **修复**：原写的 `douyin/web/fetch_general_search` 端点已不存在，必 404 |

选 `video_search_v1` 而非更新的 v3/v5，是因为只有 v1 带 `sort_type`（最新发布）和
`publish_time`（发布时间筛选）。

## 可用性闸门

`env.is_source_available(source, config)` 统一判据，`search_all_sources` 据此在派发前过滤。
没有真实数据路径的源不跑，报告显示「源不可用」。显式 `--search` 也照挡，
`LAST30DAYS_FORCE_SOURCES=1` 可强跑。

改动的判据：

- 知乎：原恒 `True` → 只认 `ZHIHU_COOKIE` 或 Playwright
- 头条：原恒 `True` → **恒 `False`**（TikHub 无搜索端点，也无 key 可配）
- B站：原恒 `True` → TikHub key 或 Playwright
- 小红书：原本三条路全灭时仍 `return True` → 只认 TikHub key / mcp 已登录 / Playwright
- 百度：→ 只认配齐的 `BAIDU_API_KEY` + `BAIDU_SECRET_KEY`

理由：这些源原本会退到 Bing 站内搜索，返回没有发布时间的常青词条，在「最近 N 天」的报告里
冒充该平台舆情，比空着更误导。

## 顺带修掉的上游 bug

- `douyin.py` `_parse_aweme`：`text_extra` 实测是 `null` 而非缺字段，直接迭代必 `TypeError`，
  真实数据一来就整源报错
- `bilibili.py` `_parse_video`：`description` 带 `<em class="keyword">` 高亮一路进报告
  （外层打分循环只清 `title`）
- `last30days.py`：不再把 `SCRAPECREATORS_API_KEY` 传给小红书——上游 v2.1 已移除该集成
  （ScrapeCreators 官方没有小红书端点，原 `/v2/xiaohongshu/search` 恒 404），传进去只会
  每次刷一条误导性的「token 已被忽略」警告

## 实测踩坑（改代码前先读）

- **必带 UA**：不带被 TikHub 前面的 Cloudflare 拦成 `403 error code 1010`，响应体不是 JSON，
  看着像鉴权失败其实不是
- **响应时间 2s~30s+ 抖动**：单次 20s 超时会随机空手而归。微博最慢，而引擎对每个源有 60s
  硬超时、超时即整源丢光（实测 5 页=70s 拿到 31 条全作废），故微博额外压了 40s 翻页预算
- **字段**：小红书互动数是复数形式 `comments_count`，`note_id` 实为 `id`，`interact_info` 恒 null；
  微博 `publish_time` 是**无年份**的中文串（`09月12日 19:37`）；微博互动数上游恒为 0
- **抖音翻页** `search_id` 要取 `log_pb.impr_id`，`extra.search_request_id` 恒空、拿它翻页返 400
- **OpenAPI 无字段约定**：1063 个端点的 200 响应全标成同一个通用 `ResponseModel`，所有解析
  都是按实测结构写的，故小红书的笔记提取用递归找「像笔记的 dict 列表」而非写死路径

## 测试

- `tests/test_tikhub_sources.py`：四源解析回归，桩掉 `tikhub.get/post`，不发网络不计费。
  除解析外还断言参数确实压到服务端（微博 `timescope`、B站 `order=pubdate` + 时间戳区间、
  微信 `publish_time`、抖音端点没退回已下线的那个）
- `tests/test_xiaohongshu_tikhub.py`：小红书链路回归
- `tests/test_search_fallbacks.py`：**翻转了一条上游断言**——
  `test_xiaohongshu_diagnose_available_with_fallback_when_mcp_down` 原本固化「mcp 挂了也返回
  True」，正是本次要改掉的行为，已改名并反向断言

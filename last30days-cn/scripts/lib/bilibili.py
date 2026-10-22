"""B站搜索模块 - 搜索哔哩哔哩视频内容。

Author: Jesse (https://github.com/Jesseovo)

支持三种模式（按优先级自动切换）：
1. TikHub 综合搜索（需 TIKHUB_API_KEY，**支持发布时间区间**，且不吃本机风控）
2. B站公开搜索 API（无需 API Key，本机实测常被风控挡住）
3. MediaCrawler 浏览器爬虫（备用方案）
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import dates, relevance, tikhub

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_TIKHUB_PATH = "/api/v1/bilibili/web/fetch_general_search"


def search_bilibili(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    tikhub_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索B站视频。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        tikhub_token: TikHub API Key（可选，配了就优先走 TikHub）

    Returns:
        B站视频列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)
    pages = 1 if depth == "quick" else (2 if depth == "default" else 3)

    items: List[Dict[str, Any]] = []

    if tikhub_token:
        items = _search_via_tikhub(topic, from_date, to_date, limit, pages, tikhub_token)

    if not items:
        for page_num in range(1, pages + 1):
            try:
                items.extend(_search_page(topic, page_num))
            except Exception as e:
                sys.stderr.write(f"[B站] 搜索第 {page_num} 页失败: {e}\n")
                break

    if not items:
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[B站] API 无结果，尝试 MediaCrawler 爬虫模式...\n")
                items = crawler_bridge.crawl_bilibili(topic, limit)
                if items:
                    sys.stderr.write(f"[B站] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[B站] 爬虫模式失败: {e}\n")

    scored = []
    for i, item in enumerate(items):
        title = _clean_html(item.get("title", ""))
        rel = relevance.token_overlap_relevance(topic, title)
        item["id"] = f"BL{i+1}"
        item["title"] = title
        item["relevance"] = rel
        item["why_relevant"] = f"B站视频：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_tikhub(
    topic: str, from_date: str, to_date: str, limit: int, pages: int, token: str
) -> List[Dict[str, Any]]:
    """B站综合搜索（TikHub）。

    `pubtime_begin_s`/`pubtime_end_s` 是 10 位时间戳区间，直接把 30 天窗压到
    服务端。`order` 是必填（漏了返 422），用 pubdate＝按发布时间倒序，舆情场景
    要的是新内容而非播放量最高的老视频。

    返回结构与 B站网页版搜索 API 完全一致（TikHub 只是代理），故复用 _parse_video。
    """
    items: List[Dict[str, Any]] = []
    try:
        begin = int(dates.parse_date(from_date).timestamp())
        end = int(dates.parse_date(to_date).timestamp()) + 86399
    except Exception:  # noqa: BLE001 — 解析不了就不加时间限制，交给引擎过滤
        begin = end = 0

    for page in range(1, pages + 1):
        params = {
            "keyword": topic,
            "order": "pubdate",
            "page": page,
            "page_size": 20,
            "pubtime_begin_s": begin,
            "pubtime_end_s": end,
        }
        payload = tikhub.get(_TIKHUB_PATH, params, token, tag="B站")
        if not payload:
            break
        result = (((payload.get("data") or {}).get("data")) or {}).get("result") or []
        videos = [v for v in result if v.get("type") == "video" or v.get("bvid")]
        if not videos:
            break
        for v in videos:
            item = _parse_video(v)
            item["source"] = "tikhub"
            items.append(item)
        if len(items) >= limit:
            break
        time.sleep(0.3)
    if items:
        sys.stderr.write(f"[B站] 数据源获取 {len(items)} 条结果\n")
    return items[:limit]


def _search_page(topic: str, page: int = 1) -> List[Dict[str, Any]]:
    """搜索B站单页结果。"""
    encoded = urllib.parse.quote(topic)
    url = (
        f"https://api.bilibili.com/x/web-interface/search/type"
        f"?search_type=video&keyword={encoded}&page={page}&page_size=20"
        f"&order=totalrank"
    )
    headers = {
        "User-Agent": _UA,
        "Referer": "https://search.bilibili.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    items = []
    results = data.get("data", {}).get("result", [])
    if not results:
        return items

    for r in results:
        items.append(_parse_video(r))

    return items


def _parse_video(v: dict) -> Dict[str, Any]:
    """解析B站视频搜索结果。"""
    bvid = v.get("bvid", "")
    pubdate = v.get("pubdate", 0)
    date_str = None
    if pubdate:
        date_str = dates.timestamp_to_date(pubdate)

    # 搜索接口返回的 title/description 带 <em class="keyword"> 命中高亮。
    # 外层打分循环只清 title，description 会一路带标签进报告，故在这里统一清掉。
    return {
        "title": _clean_html(v.get("title", "")),
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else v.get("arcurl", ""),
        "bvid": bvid,
        "channel_name": v.get("author", ""),
        "author_mid": v.get("mid", ""),
        "date": date_str,
        "duration": v.get("duration", ""),
        "description": _clean_html(v.get("description", "")),
        "engagement": {
            "views": v.get("play", 0),
            "danmaku": v.get("danmaku", 0),
            "comments": v.get("review", 0) or v.get("comment", 0),
            "favorites": v.get("favorites", 0),
            "likes": v.get("like", 0),
        },
    }


def _clean_html(text: str) -> str:
    """清除搜索结果中的 HTML 高亮标签。"""
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()

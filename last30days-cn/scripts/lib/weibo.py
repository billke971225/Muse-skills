"""微博搜索模块 - 搜索微博热门内容。

Author: Jesse (https://github.com/Jesseovo)

支持四种模式（按优先级自动切换）：
1. TikHub 高级搜索（需 TIKHUB_API_KEY，**唯一支持任意时间区间**的路径）
2. 微博开放平台 API（需要 WEIBO_ACCESS_TOKEN）
3. MediaCrawler 浏览器爬虫（需要 Playwright，无需 API Key）
4. 微博移动端公共接口（免费，无需认证）
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, tikhub

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"

_TIKHUB_PATH = "/api/v1/weibo/web_v2/fetch_advanced_search"
# 每页约 10 条。**单页实测 10~30s**（微博高级搜索是四个源里最慢的），而引擎对
# 每个源有 60s 硬超时、超时即整源丢光（实测 5 页=70s 拿到 31 条全丢、2 页也超）。
# 故除页数上限外还压一道**时间预算**：只有已用时明显够再翻一页才继续。
_TIKHUB_MAX_PAGES = 3
_TIKHUB_BUDGET = 40.0


def search_weibo(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
    tikhub_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索微博内容。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        token: 微博 access_token（可选）
        tikhub_token: TikHub API Key（可选，配了就优先走 TikHub 高级搜索）

    Returns:
        微博条目列表，每条包含 id, text, url, author_handle, date,
        engagement, relevance, why_relevant 等字段
    """
    limit_map = {"quick": 15, "default": 30, "deep": 50}
    limit = limit_map.get(depth, 30)

    items: List[Dict[str, Any]] = []

    if tikhub_token:
        items = _search_via_tikhub(topic, from_date, to_date, limit, tikhub_token)

    if not items and token:
        items = _search_via_api(topic, from_date, to_date, limit, token)

    if not items:
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[微博] 尝试 MediaCrawler 爬虫模式...\n")
                items = crawler_bridge.crawl_weibo(topic, limit)
                if items:
                    sys.stderr.write(f"[微博] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[微博] 爬虫模式失败: {e}\n")

    if not items:
        items = _search_via_public(topic, from_date, to_date, limit)

    scored = []
    for i, item in enumerate(items):
        text = item.get("text", "")
        rel = relevance.token_overlap_relevance(topic, text)
        item["id"] = f"WB{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"微博讨论：{text[:60]}..."
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_tikhub(
    topic: str, from_date: str, to_date: str, limit: int, token: str
) -> List[Dict[str, Any]]:
    """微博高级搜索（TikHub）。

    这是本项目里**唯一支持任意时间区间**的检索路径：`timescope=custom:起:止`
    直接把 30 天窗压到服务端，而不是全量拉回来本地过滤。实测响应里的
    `search_stats` 会回显生效区间（如「2026-08-15 00时~2026-09-14 23时」），
    可据此确认筛选真的生效。
    """
    items: List[Dict[str, Any]] = []
    pages = min(_TIKHUB_MAX_PAGES, max(1, -(-limit // 10)))
    started = time.monotonic()
    for page in range(1, pages + 1):
        elapsed = time.monotonic() - started
        # 上一页耗时就是下一页的估计；估不完就带着已有结果收工，别把整源赔进去
        if page > 1 and elapsed + elapsed / (page - 1) > _TIKHUB_BUDGET:
            sys.stderr.write(f"[微博] 已用 {elapsed:.0f}s，剩余预算不够再翻一页，就此收工\n")
            break
        params = {
            "q": topic,
            "search_type": "all",
            "timescope": f"custom:{from_date}:{to_date}",
            "page": page,
        }
        payload = tikhub.get(_TIKHUB_PATH, params, token, tag="微博")
        if not payload:
            break
        parsed = ((payload.get("data") or {}).get("parsed_data")) or {}
        results = parsed.get("results") or []
        if not results:
            break
        if page == 1 and parsed.get("search_stats"):
            stats = parsed["search_stats"].get("search_stats")
            if stats:
                sys.stderr.write(f"[微博] 数据源生效区间：{stats}\n")
        items.extend(_parse_tikhub_post(r) for r in results)
        if len(items) >= limit:
            break
    if items:
        sys.stderr.write(f"[微博] 数据源获取 {len(items)} 条结果\n")
    return items[:limit]


def _tikhub_url(path: str) -> str:
    """微博返回的是 //weibo.com/... 协议相对链接，补成可点的绝对链接。"""
    path = (path or "").split("?")[0]
    if path.startswith("//"):
        return "https:" + path
    return path


def _parse_tikhub_post(r: dict) -> Dict[str, Any]:
    """解析 TikHub 高级搜索条目（字段名与开放平台/移动端都不同，单独一份）。"""
    inter = r.get("interaction") or {}
    media = r.get("media") or {}
    return {
        "text": _clean_tikhub_text(r.get("content", "")),
        "url": _tikhub_url(r.get("post_url", "")),
        "author_handle": r.get("user_nick") or r.get("user_name", ""),
        "author_id": _tikhub_url(r.get("user_url", "")).rsplit("/", 1)[-1],
        "date": _parse_weibo_time(r.get("publish_time")),
        "engagement": {
            "reposts": inter.get("repost_count", 0),
            "comments": inter.get("comment_count", 0),
            "likes": inter.get("like_count", 0),
        },
        "images": media.get("images") or [],
        "source": "tikhub",
    }


def _clean_tikhub_text(text: str) -> str:
    """去掉高亮标签与「展开c」这类网页端残留。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s*展开c\s*$", "", text.strip())
    return re.sub(r"\s+", " ", text).strip()


def _parse_weibo_time(raw: Optional[str]) -> Optional[str]:
    """把网页端的中文时间串转成 YYYY-MM-DD。

    网页端有四种写法：`X分钟前` / `今天 HH:MM` / `09月12日 19:37`（**无年份**）
    / `2025年12月3日 19:37`。无年份的按今年算，若算出来比今天晚则退一年
    （12 月发的帖在 1 月被搜到就是这种情况）。
    """
    if not raw:
        return None
    raw = raw.strip()
    today = datetime.now()
    if "分钟前" in raw or "秒前" in raw:
        return today.strftime("%Y-%m-%d")
    if "小时前" in raw:
        m = re.search(r"(\d+)", raw)
        hours = int(m.group(1)) if m else 0
        return (today - timedelta(hours=hours)).strftime("%Y-%m-%d")
    if raw.startswith("今天"):
        return today.strftime("%Y-%m-%d")
    if raw.startswith("昨天"):
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{1,2})月(\d{1,2})日", raw)
    if m:
        mo, d = (int(x) for x in m.groups())
        guess = datetime(today.year, mo, d)
        if guess > today + timedelta(days=1):
            guess = datetime(today.year - 1, mo, d)
        return guess.strftime("%Y-%m-%d")
    return None


def _search_via_api(
    topic: str, from_date: str, to_date: str, limit: int, token: str
) -> List[Dict[str, Any]]:
    """通过微博开放平台 API 搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = (
            f"https://api.weibo.com/2/search/statuses.json"
            f"?access_token={token}&q={encoded}&count={min(limit, 50)}"
        )
        resp = http.get(url, timeout=15)
        if isinstance(resp, dict) and "statuses" in resp:
            for s in resp["statuses"]:
                items.append(_parse_status(s))
    except Exception as e:
        sys.stderr.write(f"[微博] API 搜索失败: {e}\n")
    return items


def _search_via_public(
    topic: str, from_date: str, to_date: str, limit: int
) -> List[Dict[str, Any]]:
    """通过微博移动端公共接口搜索（无需认证）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D1%26q%3D{encoded}&page_type=searchall"
        headers = {"User-Agent": _UA, "Referer": "https://m.weibo.cn/"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            if card.get("card_type") == 9:
                mblog = card.get("mblog", {})
                if mblog:
                    items.append(_parse_mblog(mblog))
            elif card.get("card_type") == 11:
                for group in card.get("card_group", []):
                    mblog = group.get("mblog", {})
                    if mblog:
                        items.append(_parse_mblog(mblog))
    except Exception as e:
        sys.stderr.write(f"[微博] 公共接口搜索失败: {e}\n")
    return items


def _parse_status(s: dict) -> Dict[str, Any]:
    """解析微博开放平台 API 返回的状态。"""
    text = _clean_html(s.get("text", ""))
    user = s.get("user", {})
    created = s.get("created_at", "")
    date_str = _parse_weibo_date(created)

    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{s.get('mid', '')}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": date_str,
        "engagement": {
            "reposts": s.get("reposts_count", 0),
            "comments": s.get("comments_count", 0),
            "likes": s.get("attitudes_count", 0),
        },
    }


def _parse_mblog(mblog: dict) -> Dict[str, Any]:
    """解析微博移动端接口返回的 mblog。"""
    text = _clean_html(mblog.get("text", ""))
    user = mblog.get("user", {})
    created = mblog.get("created_at", "")
    date_str = _parse_weibo_date(created)
    mid = mblog.get("mid", "") or mblog.get("id", "")

    return {
        "text": text,
        "url": f"https://weibo.com/{user.get('id', '')}/{mid}",
        "author_handle": user.get("screen_name", ""),
        "author_id": str(user.get("id", "")),
        "date": date_str,
        "engagement": {
            "reposts": mblog.get("reposts_count", 0),
            "comments": mblog.get("comments_count", 0),
            "likes": mblog.get("attitudes_count", 0),
        },
    }


def _clean_html(text: str) -> str:
    """清除微博文本中的 HTML 标签。"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_weibo_date(date_str: str) -> Optional[str]:
    """将微博日期格式转换为 YYYY-MM-DD。"""
    if not date_str:
        return None
    try:
        # "Tue Jan 01 00:00:00 +0800 2026"
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.astimezone(dates.CST).strftime("%Y-%m-%d")
    except ValueError:
        pass
    # 相对时间: "x分钟前", "x小时前", "昨天 HH:MM"
    now = datetime.now(dates.CST)
    if "分钟前" in date_str:
        try:
            mins = int(re.search(r"(\d+)", date_str).group(1))
            return (now - timedelta(minutes=mins)).strftime("%Y-%m-%d")
        except Exception:
            pass
    if "小时前" in date_str:
        try:
            hours = int(re.search(r"(\d+)", date_str).group(1))
            return (now - timedelta(hours=hours)).strftime("%Y-%m-%d")
        except Exception:
            pass
    if "昨天" in date_str:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    # "MM-DD" 格式
    m = re.match(r"(\d{2})-(\d{2})", date_str)
    if m:
        return f"{now.year}-{m.group(1)}-{m.group(2)}"
    return None

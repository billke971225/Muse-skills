"""微信公众号搜索模块 - 搜索微信公众号文章。

Author: Jesse (https://github.com/Jesseovo)

支持三种模式（按优先级自动切换）：
1. TikHub 微信搜一搜（需 TIKHUB_API_KEY，覆盖公众号文章，支持时间/排序筛选）
2. 极速数据第三方 API（需 WECHAT_API_KEY，付费）
3. 搜狗微信搜索（免费，反爬凶，命中率低）
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

_TIKHUB_PATH = "/api/v1/wechat_search/v2/fetch_search"
# 每页约 36 条；封顶 3 页，按次计费
_TIKHUB_MAX_PAGES = 3


def search_wechat(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    api_key: Optional[str] = None,
    tikhub_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索微信公众号文章。

    Args:
        topic: 搜索关键词
        from_date: 起始日期
        to_date: 结束日期
        depth: 搜索深度
        api_key: 第三方搜索 API key（可选）

    Returns:
        微信公众号文章列表
    """
    limit_map = {"quick": 8, "default": 15, "deep": 30}
    limit = limit_map.get(depth, 15)

    items: List[Dict[str, Any]] = []

    if tikhub_token:
        items = _search_via_tikhub(topic, from_date, to_date, limit, tikhub_token)

    if not items and api_key:
        items = _search_via_api(topic, limit, api_key)

    if not items:
        items = _search_via_sogou(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        combined = f"{title} {snippet}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"WX{i+1}"
        item["relevance"] = rel
        item["why_relevant"] = f"微信公众号：{title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_tikhub(
    topic: str, from_date: str, to_date: str, limit: int, token: str
) -> List[Dict[str, Any]]:
    """微信搜一搜（TikHub）。

    比搜狗微信那条正规得多：搜一搜是微信官方入口，覆盖全量公众号文章，且
    `publish_time` 与 `sort` 都是服务端参数。翻页**必须用 cursor**——文档明说
    只传 offset 无效（每页都回到第一页）。`raw=False` 要精简结构，省得自己
    从原始搜索响应里挖。
    """
    items: List[Dict[str, Any]] = []
    publish_time = tikhub.bucket(from_date, to_date, "day", "week", "half_year")
    cursor = ""
    for page in range(_TIKHUB_MAX_PAGES):
        body = {
            "keyword": topic,
            "business_type": "article",
            "sort": "latest",
            "publish_time": publish_time,
            "offset": 0,
            "raw": False,
        }
        if cursor:
            body["cursor"] = cursor
        payload = tikhub.post(_TIKHUB_PATH, body, token, tag="微信")
        if not payload:
            break
        data = payload.get("data") or {}
        batch = data.get("items") or []
        if not batch:
            break
        items.extend(_parse_tikhub_article(a) for a in batch)
        cursor = str(data.get("cursor") or "")
        if len(items) >= limit or data.get("no_more") or not cursor:
            break
        time.sleep(0.3)
    if items:
        sys.stderr.write(f"[微信] 数据源获取 {len(items)} 条结果\n")
    return items[:limit]


def _strip_highlight(text: str) -> str:
    """搜一搜的标题/摘要里带 <em class="highlight"> 命中高亮，去掉。"""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def _parse_tikhub_article(a: dict) -> Dict[str, Any]:
    """解析搜一搜条目。时间取 timestamp（秒），公众号名在 source.title。"""
    src = a.get("source") or {}
    ts = a.get("timestamp") or a.get("date")
    date_str = None
    if ts:
        try:
            date_str = dates.timestamp_to_date(int(ts))
        except (TypeError, ValueError):
            date_str = None
    return {
        "title": _strip_highlight(a.get("title", "")),
        "snippet": _strip_highlight(a.get("desc", "")),
        "url": a.get("doc_url", ""),
        "source_name": src.get("title", ""),
        "wechat_id": "",
        "date": date_str,
        "engagement": {},
        "source": "tikhub",
    }


def _search_via_api(topic: str, limit: int, api_key: str) -> List[Dict[str, Any]]:
    """通过第三方 API 搜索微信公众号文章。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://api.jisuapi.com/weixin/search?keyword={encoded}&pagenum=1&pagesize={limit}&appkey={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("status") == "0":
            for article in data.get("result", {}).get("list", []):
                items.append({
                    "title": article.get("name", ""),
                    "snippet": article.get("description", ""),
                    "url": article.get("url", ""),
                    "source_name": article.get("weixinname", ""),
                    "wechat_id": article.get("weixinhao", ""),
                    "date": article.get("date"),
                    "engagement": {},
                })
    except Exception as e:
        sys.stderr.write(f"[微信] API 搜索失败: {e}\n")
    return items


def _search_via_sogou(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过搜狗微信搜索。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://weixin.sogou.com/weixin?type=2&query={encoded}&ie=utf8"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8")

        titles = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.S)
        dates_found = re.findall(r'timeConvert\(\'(\d+)\'\)', html)
        accounts = re.findall(r'account="([^"]*)"', html)

        for idx, (href, title_html) in enumerate(titles[:limit]):
            if "weixin.qq.com" not in href and "sogou.com" not in href:
                continue
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            if not title:
                continue

            date_str = None
            if idx < len(dates_found):
                date_str = dates.timestamp_to_date(int(dates_found[idx]))

            items.append({
                "title": title,
                "snippet": "",
                "url": href,
                "source_name": accounts[idx] if idx < len(accounts) else "",
                "wechat_id": "",
                "date": date_str,
                "engagement": {},
            })
    except Exception as e:
        sys.stderr.write(f"[微信] 搜狗搜索失败: {e}\n")
    return items

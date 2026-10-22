"""小红书搜索模块 - 搜索小红书笔记。

Author: Jesse (https://github.com/Jesseovo)

支持多种数据获取方式（按优先级自动切换）：
1. TikHub API（需 TIKHUB_API_KEY，$0.001/次，服务端筛选、带发布时间）
2. xiaohongshu-mcp HTTP API（自托管，可选）
3. MediaCrawler 浏览器爬虫（基于 Playwright，无需 API Key）
4. 公开搜索接口（命中率较低，仅作兜底）

注意：v2.1 起已移除 ScrapeCreators 集成 —— ScrapeCreators 官方
（https://docs.scrapecreators.com）并未提供小红书端点，原代码调用的
`/v2/xiaohongshu/search` 始终返回 404，属于错误实现。
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from . import dates, http, relevance, tikhub

_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_SCRAPECREATORS_DEPRECATION_WARNED = False

_TIKHUB_PATH = "/api/v1/xiaohongshu/app_v2/search_notes"
# 每页约 20 条，深度模式最多 40 条；封顶 3 页以免翻页把 $0.001/次 叠上去
_TIKHUB_MAX_PAGES = 3


def search_xiaohongshu(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
    token: Optional[str] = None,
    api_base: Optional[str] = None,
    tikhub_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索小红书笔记。

    Args:
        topic: 搜索关键词
        from_date: 起始日期 YYYY-MM-DD
        to_date: 结束日期 YYYY-MM-DD
        depth: 搜索深度 quick/default/deep
        token: 已弃用 —— 保留参数仅为向后兼容（v2.1 移除 ScrapeCreators 集成）
        api_base: xiaohongshu-mcp 自托管 HTTP API 地址（可选）
        tikhub_token: TikHub API Key（可选，配了就优先走 TikHub）

    Returns:
        小红书笔记列表
    """
    limit_map = {"quick": 10, "default": 20, "deep": 40}
    limit = limit_map.get(depth, 20)

    if token:
        global _SCRAPECREATORS_DEPRECATION_WARNED
        if not _SCRAPECREATORS_DEPRECATION_WARNED:
            sys.stderr.write(
                "[小红书] 警告：ScrapeCreators 集成已在 v2.1 移除（官方未提供小红书端点），"
                "传入的 token 已被忽略。请安装 Playwright 使用爬虫模式。\n"
            )
            _SCRAPECREATORS_DEPRECATION_WARNED = True

    items: List[Dict[str, Any]] = []

    if tikhub_token:
        items = _search_via_tikhub(topic, from_date, to_date, limit, tikhub_token)

    if not items and api_base:
        items = _search_via_mcp(topic, from_date, to_date, limit, api_base)

    if not items and depth != "quick":
        try:
            from . import crawler_bridge
            if crawler_bridge.is_playwright_available():
                sys.stderr.write("[小红书] 尝试 MediaCrawler 爬虫模式...\n")
                items = crawler_bridge.crawl_xiaohongshu(topic, limit)
                if items:
                    sys.stderr.write(f"[小红书] 爬虫模式获取 {len(items)} 条结果\n")
        except Exception as e:
            sys.stderr.write(f"[小红书] 爬虫模式失败: {e}\n")

    if not items:
        items = _search_via_public(topic, limit)

    if not items:
        items = _search_via_site_search(topic, limit)

    scored = []
    for i, item in enumerate(items):
        title = item.get("title", "")
        desc = item.get("desc", "")
        combined = f"{title} {desc}"
        rel = relevance.token_overlap_relevance(topic, combined)
        item["id"] = f"XHS{i+1}"
        item["relevance"] = rel
        source = item.get("source", "xiaohongshu")
        item["why_relevant"] = f"小红书来源({source}): {title[:50]}"
        scored.append(item)

    scored.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return scored[:limit]


def _search_via_tikhub(
    topic: str, from_date: str, to_date: str, limit: int, token: str
) -> List[Dict[str, Any]]:
    """通过 TikHub 的小红书 app_v2 搜索笔记。

    与自托管 xiaohongshu-mcp 的区别：筛选项是服务端参数（不点网页 UI），
    note_type/time_filter 真正生效；翻页靠首次响应回传的
    search_id + search_session_id。按 $0.001/次计费，故只在拿够 limit
    条或翻到空页时停，最多 _TIKHUB_MAX_PAGES 页。
    """
    items: List[Dict[str, Any]] = []
    time_filter = tikhub.bucket(from_date, to_date, "一天内", "一周内", "半年内")
    search_id = ""
    session_id = ""

    for page in range(1, _TIKHUB_MAX_PAGES + 1):
        params = {
            "keyword": topic,
            "page": str(page),
            "sort_type": "time_descending",
            "note_type": "不限",
            "time_filter": time_filter,
        }
        if search_id:
            params["search_id"] = search_id
            params["search_session_id"] = session_id
        payload = tikhub.get(_TIKHUB_PATH, params, token, tag="小红书")
        if payload is None:
            break

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            break
        search_id = search_id or str(data.get("search_id") or "")
        session_id = session_id or str(data.get("search_session_id") or "")

        notes = _tikhub_extract_notes(data)
        if not notes:
            break
        for note in notes:
            parsed = _parse_note(note)
            if parsed.get("url") or parsed.get("title"):
                parsed["source"] = "tikhub"
                items.append(parsed)
        if len(items) >= limit or not (search_id and session_id):
            break

    if items:
        sys.stderr.write(f"[小红书] 数据源获取 {len(items)} 条结果\n")
    return items[:limit]


def _tikhub_extract_notes(data: Any) -> List[Dict[str, Any]]:
    """从 TikHub 响应里挖出笔记对象列表。

    TikHub 的 OpenAPI 把所有端点的 200 响应都标成通用 ResponseModel，
    没有字段约定，且上游小红书接口自己会换壳（items/notes/note_card...），
    故不写死路径：递归找第一处「看着像笔记」的 dict 列表。
    """
    hits: List[Dict[str, Any]] = []

    def looks_like_note(obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        has_id = any(k in obj for k in ("note_id", "id", "note_card", "note"))
        has_text = any(k in obj for k in ("title", "display_title", "desc", "description"))
        return has_id and has_text

    def unwrap(obj: Dict[str, Any]) -> Dict[str, Any]:
        # 搜索结果常把笔记包一层 note_card / note
        for key in ("note_card", "note"):
            inner = obj.get(key)
            if isinstance(inner, dict):
                merged = dict(inner)
                merged.setdefault("note_id", obj.get("id") or obj.get("note_id", ""))
                return merged
        return obj

    def walk(node: Any, depth: int = 0) -> None:
        if hits or depth > 6:
            return
        if isinstance(node, list):
            # 先整体解包再判定：搜索结果里每条常是 {id, model_type, note_card:{...}}，
            # 外层自己没有标题字段，逐条下钻会只捞到第一条就收工
            candidates = [u for u in (unwrap(x) for x in node if isinstance(x, dict))
                          if looks_like_note(u)]
            if candidates:
                hits.extend(candidates)
                return
            for x in node:
                walk(x, depth + 1)
        elif isinstance(node, dict):
            unwrapped = unwrap(node)
            if looks_like_note(unwrapped) and depth > 0:
                hits.append(unwrapped)
                return
            for v in node.values():
                walk(v, depth + 1)

    walk(data)
    return hits


def _search_via_mcp(
    topic: str, from_date: str, to_date: str, limit: int, api_base: str
) -> List[Dict[str, Any]]:
    """通过 xiaohongshu-mcp HTTP API 搜索。"""
    items = []
    try:
        base = api_base.rstrip("/")
        encoded = urllib.parse.quote(topic)
        url = f"{base}/api/v1/search/notes?keyword={encoded}&limit={limit}"
        resp = http.get(url, timeout=8, retries=1)
        if isinstance(resp, dict) and resp.get("data"):
            for note in resp["data"].get("items", resp["data"] if isinstance(resp["data"], list) else []):
                items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] MCP API 搜索失败: {e}\n")
    return items


def _search_via_public(topic: str, limit: int) -> List[Dict[str, Any]]:
    """通过公开接口搜索小红书（备用方案，命中率较低）。"""
    items = []
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://www.xiaohongshu.com/fe_api/burdock/weixin/v2/search/notes?keyword={encoded}&page=1&page_size={limit}"
        headers = {"User-Agent": _UA}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        for note in data.get("data", {}).get("notes", []):
            items.append(_parse_note(note))
    except Exception as e:
        sys.stderr.write(f"[小红书] 公开接口搜索失败: {e}\n")
    return items


def _fetch_html(url: str, timeout: int = 8) -> str:
    headers = {
        "User-Agent": _DESKTOP_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://cn.bing.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _search_via_site_search(topic: str, limit: int) -> List[Dict[str, Any]]:
    """Fallback to public web search when Xiaohongshu blocks API/Playwright."""
    items: List[Dict[str, Any]] = []
    try:
        query = f"site:xiaohongshu.com/explore {topic}"
        encoded = urllib.parse.quote(query)
        url = f"https://cn.bing.com/search?q={encoded}&setmkt=zh-CN&ensearch=0"
        html = _fetch_html(url)
        blocks = re.findall(r'<li class="b_algo"[^>]*>([\s\S]*?)</li>', html)
        seen = set()
        for block in blocks:
            title_match = re.search(
                r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>',
                block,
                re.S,
            )
            if not title_match:
                continue
            href = title_match.group(1)
            if "xiaohongshu.com" not in href or href in seen:
                continue
            seen.add(href)
            title = _clean_text(title_match.group(2))
            snip_match = re.search(r"<p[^>]*>([\s\S]*?)</p>", block, re.S)
            snippet = _clean_text(snip_match.group(1)) if snip_match else ""
            items.append({
                "title": title,
                "desc": snippet,
                "url": href,
                "author_name": "",
                "author_id": "",
                "date": None,
                "engagement": {"likes": 0, "collects": 0, "comments": 0, "shares": 0},
                "hashtags": re.findall(r"#([^#\s]+)#?", f"{title} {snippet}"),
                "images": [],
                "source": "site-search-fallback",
            })
            if len(items) >= limit:
                break
    except Exception as e:
        sys.stderr.write(f"[小红书] 站内搜索兜底失败: {e}\n")
    if items:
        sys.stderr.write(f"[小红书] 官方/Playwright 路径无结果，已用站内搜索兜底获取 {len(items)} 条公开链接。\n")
    return items


def _parse_note(note: dict) -> Dict[str, Any]:
    """解析小红书笔记数据。"""
    note_id = note.get("note_id") or note.get("id", "")
    title = note.get("title") or note.get("display_title", "")
    desc = note.get("desc") or note.get("description", "")
    user = note.get("user", {}) if isinstance(note.get("user"), dict) else {}
    # 小红书新版把互动数塞在 interact_info 里（TikHub 直接透传上游结构）
    interact = note.get("interact_info", {}) if isinstance(note.get("interact_info"), dict) else {}
    liked_count = note.get("liked_count") or note.get("likes") or interact.get("liked_count", 0)
    collected_count = note.get("collected_count") or note.get("collects") or interact.get("collected_count", 0)
    # 实测 TikHub 透传的上游字段是复数形式 comments_count
    comment_count = (
        note.get("comment_count") or note.get("comments_count")
        or note.get("comments") or interact.get("comment_count", 0)
    )
    share_count = note.get("share_count") or note.get("shares") or interact.get("shared_count", 0)

    hashtags = re.findall(r"#([^#\s]+)#?", f"{title} {desc}")

    date_str = (
        note.get("time")
        or note.get("created_time")
        or note.get("timestamp")
        or note.get("publish_time")
        or note.get("last_update_time")
        or note.get("date")
    )
    if date_str and len(str(date_str)) == 13:
        date_str = dates.timestamp_to_date(int(date_str) / 1000)
    elif date_str and len(str(date_str)) == 10 and str(date_str).isdigit():
        date_str = dates.timestamp_to_date(int(date_str))

    return {
        "title": title,
        "desc": desc,
        "url": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
        "author_name": user.get("nickname") or user.get("name", ""),
        "author_id": user.get("user_id") or user.get("id", ""),
        "date": date_str,
        "engagement": {
            "likes": _safe_int(liked_count),
            "collects": _safe_int(collected_count),
            "comments": _safe_int(comment_count),
            "shares": _safe_int(share_count),
        },
        "hashtags": hashtags,
        "images": note.get("images_list") or note.get("image_list", []),
    }


def _safe_int(val) -> int:
    """安全转换为整数。"""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

"""TikHub 数据层 —— 各平台源共用的 HTTP 客户端。

TikHub（api.tikhub.io）是第三方社媒数据聚合商，$0.001/次、非 200 不计费。
小红书/抖音/微博/B站/微信搜一搜都走它，故把鉴权、UA、重试、响应解包收在这里，
省得每个平台模块各写一份。

踩坑（都是实测出来的，改动前先读）：
- **必带 UA**：不带会被 TikHub 前面的 Cloudflare 拦成 `403 error code 1010`，
  且响应体不是 JSON，看着像鉴权失败其实不是。
- **响应时间抖动大**：小红书 2~30s、B站见过 34s。单次 20s 超时会随机空手而归，
  故 45s + 3 次退避重试。超时/非 200 都不计费，重试是免费的。
- **OpenAPI 无字段约定**：1063 个端点的 200 响应全标成同一个通用 ResponseModel，
  故各平台的解析都得按实测结构写，且要对结构变动留余地。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

_UPSTREAM = "https://api.tikhub.io"
_base_cache: Optional[str] = None


def _base() -> str:
    """数据源地址。默认直连上游；设 L30D_BASE_URL 可改指向自建转发层。

    默认值必须保持上游官方地址——本仓库是公开的，把某个私有转发层写成默认值
    等于让陌生人往那个端点上打。团队用法是各自设 L30D_BASE_URL。

    **配置文件也要读**：key 是 env.get_config() 从 .env 读的，地址若只认进程
    环境，就会出现「同一个 .env 里两个键一个生效一个不生效」——后果是拿着
    l30d_ 的 key 去直连上游、静默 403，而 --diagnose 还显示一切正常
    （它只检查 key 在不在）。这个坑在给服务端写更新说明时踩过。
    """
    global _base_cache
    if _base_cache is not None:
        return _base_cache

    merged: Dict[str, str] = {}
    try:
        # 走 load_env_file 而非 env.get_config()：后者只返回它 keys 列表里
        # 登记过的键，于是本文件能否单独升级就取决于对方的 env.py 版本。
        # 这三个底层函数上游一直有，所以本文件可以单独替换、不牵连 env.py。
        from . import env as _env
        if getattr(_env, "CONFIG_FILE", None):
            merged.update(_env.load_env_file(_env.CONFIG_FILE))
        project = _env._find_project_env()
        if project:
            merged.update(_env.load_env_file(project))       # 项目级优先
    except Exception:  # noqa: BLE001 — 读不到配置就退回默认，不该因此挂掉
        pass

    # 与 env.py 的 key 解析同一规则：**新名在任何位置都压过旧名**。
    # 旧名会被别的工具注入（服务端上 Cursor 注入过陈旧值），刻意设的新名该赢。
    value = (os.environ.get("L30D_BASE_URL") or merged.get("L30D_BASE_URL")
             or os.environ.get("TIKHUB_BASE_URL") or merged.get("TIKHUB_BASE_URL"))

    _base_cache = (value or _UPSTREAM).rstrip("/")
    return _base_cache


# 注意：别在这里写 BASE = _base()——import 时求值会把缓存定死，
# 测试里后设的环境变量就不生效了。要地址请调 _base()。
_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
_TIMEOUT = 45
_RETRIES = 3


def _request(path: str, key: str, *, params: Optional[Dict[str, Any]] = None,
             body: Optional[Dict[str, Any]] = None, tag: str = "") -> Optional[Dict[str, Any]]:
    url = f"{_base()}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    last = None
    for attempt in range(_RETRIES):
        try:
            req = urllib.request.Request(url, data=payload)
            req.add_header("Authorization", f"Bearer {key}")
            req.add_header("User-Agent", _UA)
            req.add_header("Accept", "application/json")
            if payload is not None:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:160]}"
            # 鉴权/风控/路径错/参数错重试无意义，直接放弃
            if e.code in (401, 403, 404, 422):
                break
        except Exception as e:  # noqa: BLE001 — 超时/连接重置值得重试
            last = f"{type(e).__name__}: {e}"
        if attempt < _RETRIES - 1:
            time.sleep(1.5 * (attempt + 1))
    sys.stderr.write(f"[{tag or '数据源'}] 数据源请求失败 {path}: {last}\n")
    return None


def get(path: str, params: Dict[str, Any], key: str, tag: str = "") -> Optional[Dict[str, Any]]:
    """GET 一个 TikHub 端点，返回整个响应体（含 code/data）。"""
    return _request(path, key, params=params, tag=tag)


def post(path: str, body: Dict[str, Any], key: str, tag: str = "") -> Optional[Dict[str, Any]]:
    """POST 一个 TikHub 端点（抖音 search/* 与微信搜一搜都是 POST）。"""
    return _request(path, key, body=body, tag=tag)


def span_days(from_date: str, to_date: str, default: int = 30) -> int:
    """日期窗口天数；解析不了就按默认值（引擎自己还会再过滤一次）。"""
    from . import dates

    try:
        return (dates.parse_date(to_date) - dates.parse_date(from_date)).days
    except Exception:  # noqa: BLE001
        return default


def bucket(from_date: str, to_date: str, day: Any, week: Any, half_year: Any) -> Any:
    """把日期窗口套进「一天/一周/半年」三档——多数平台只给这三个档位。

    超过 7 天一律用「半年内」再由引擎按真实窗口收窄；反过来（拿一周档去查 30 天）
    会丢掉 8~30 天前的内容，宁可多取不可少取。
    """
    span = span_days(from_date, to_date)
    if span <= 1:
        return day
    if span <= 7:
        return week
    return half_year

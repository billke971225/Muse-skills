"""Environment and API key management for last30days-cn (Chinese platforms).

Author: Jesse (https://github.com/Jesseovo)
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Legacy: empty registry so optional imports (e.g. setup_wizard) do not break.
COOKIE_DOMAINS: Dict[str, Dict[str, Any]] = {}

_config_override = os.environ.get("LAST30DAYS_CN_CONFIG_DIR") or os.environ.get("LAST30DAYS_CONFIG_DIR")
if _config_override == "":
    CONFIG_DIR = None
    CONFIG_FILE = None
elif _config_override:
    CONFIG_DIR = Path(_config_override)
    CONFIG_FILE = CONFIG_DIR / ".env"
else:
    CONFIG_DIR = Path.home() / ".config" / "last30days-cn"
    CONFIG_FILE = CONFIG_DIR / ".env"


def _check_file_permissions(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        if mode & 0o044:
            import sys
            sys.stderr.write(
                f"[last30days-cn] WARNING: {path} is readable by other users. "
                f"Run: chmod 600 {path}\n"
            )
            sys.stderr.flush()
    except OSError:
        pass


def load_env_file(path: Path) -> Dict[str, str]:
    """Load environment variables from a file."""
    env: Dict[str, str] = {}
    if not path or not path.exists():
        return env
    _check_file_permissions(path)

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def _find_project_env() -> Optional[Path]:
    """Find per-project .env by walking up from cwd."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".claude" / "last30days-cn.env"
        if candidate.exists():
            return candidate
        if parent == Path.home() or parent == parent.parent:
            break
    return None


def get_config() -> Dict[str, Any]:
    """Load configuration: os.environ overrides project .env overrides global .env.

    Only Chinese-platform keys are populated.
    """
    file_env = load_env_file(CONFIG_FILE) if CONFIG_FILE else {}
    project_env_path = _find_project_env()
    project_env = load_env_file(project_env_path) if project_env_path else {}
    merged_env = {**file_env, **project_env}

    keys = [
        ("WEIBO_ACCESS_TOKEN", None),
        ("SCRAPECREATORS_API_KEY", None),
        ("ZHIHU_COOKIE", None),
        ("TIKHUB_API_KEY", None),
        ("DOUYIN_API_KEY", None),
        ("WECHAT_API_KEY", None),
        ("BAIDU_API_KEY", None),
        ("BAIDU_SECRET_KEY", None),
        ("TOUTIAO_API_KEY", None),
        ("XIAOHONGSHU_API_BASE", None),
        ("L30D_BASE_URL", None),
        ("TIKHUB_BASE_URL", None),
        ("SETUP_COMPLETE", None),
    ]

    config: Dict[str, Any] = {}
    for key, default in keys:
        config[key] = os.environ.get(key) or merged_env.get(key, default)

    # 中性别名：文档只写 L30D_API_KEY，内部仍统一用 TIKHUB_API_KEY 这个键，
    # 免得 is_source_available 等一堆判断跟着改。旧名仍接受，避免弄挂已有配置。
    #
    # **新名在任何位置都压过旧名**，而不是照「进程环境 > 配置文件」一刀切。
    # 因为 TIKHUB_API_KEY 这个名字会被别的工具注入（实测：服务端上 Cursor 注入了
    # 一把陈旧的上游 key，盖掉了 .env 里的网关 key，于是拿旧 key 去打网关吃 401，
    # 而 --diagnose 一切正常）。设 L30D_API_KEY 是一次刻意行为，旧名则可能是
    # 环境里的历史残留——刻意的那个该赢。同名之间仍是进程环境 > 配置文件。
    _new = os.environ.get("L30D_API_KEY") or merged_env.get("L30D_API_KEY")
    _old = os.environ.get("TIKHUB_API_KEY") or merged_env.get("TIKHUB_API_KEY")
    config["TIKHUB_API_KEY"] = _new or _old

    # 两个名字都设了却不是同一个值，说明环境里有历史残留。这种情况静默择一
    # 正是上面那个事故的成因，所以说出来。
    if _new and _old and _new != _old:
        import sys
        sys.stderr.write(
            "[last30days-cn] 注意：L30D_API_KEY 与 TIKHUB_API_KEY 同时设置且值不同，"
            f"已采用 L30D_API_KEY（{_new[:9]}…）。"
            "若非本意，请清掉环境里残留的 TIKHUB_API_KEY。\n"
        )

    if project_env_path:
        config["_CONFIG_SOURCE"] = f"project:{project_env_path}"
    elif CONFIG_FILE and CONFIG_FILE.exists():
        config["_CONFIG_SOURCE"] = f"global:{CONFIG_FILE}"
    else:
        config["_CONFIG_SOURCE"] = "env_only"

    return config


def config_exists() -> bool:
    """True if project or global config file exists."""
    if _find_project_env():
        return True
    if CONFIG_FILE:
        return CONFIG_FILE.exists()
    return False


def get_xiaohongshu_api_base(config: Dict[str, Any]) -> str:
    """Xiaohongshu HTTP API base URL (trailing slash stripped)."""
    return (config.get("XIAOHONGSHU_API_BASE") or "http://host.docker.internal:18060").rstrip("/")


def _playwright_ok() -> bool:
    """Playwright 爬虫模式是否可用（未装则所有爬虫回退路径都是空谈）。"""
    try:
        from . import crawler_bridge
        return crawler_bridge.is_playwright_available()
    except Exception:  # noqa: BLE001
        return False


def is_weibo_available(config: Dict[str, Any]) -> bool:
    if config.get("TIKHUB_API_KEY") or config.get("WEIBO_ACCESS_TOKEN"):
        return True
    return _playwright_ok()


def is_xiaohongshu_available(config: Dict[str, Any]) -> bool:
    from . import http

    # TikHub 走服务端接口，不依赖本地 mcp 服务的登录态
    if config.get("TIKHUB_API_KEY"):
        return True

    base = get_xiaohongshu_api_base(config)
    try:
        health = http.get(f"{base}/health", timeout=3, retries=2)
        if not isinstance(health, dict) or not health.get("success"):
            return False
        login = http.get(f"{base}/api/v1/login/status", timeout=8, retries=2)
        is_logged_in = (
            login.get("data", {}).get("is_logged_in")
            if isinstance(login, dict) else False
        )
        return bool(is_logged_in)
    except Exception:
        pass

    # 上游原本在这里无条件 return True（理由是「还有站内搜索兜底」）。
    # 但 Bing 兜底不是小红书的数据，是搜索引擎收录的零星链接；无 key、mcp 未登录、
    # 无 Playwright 时本机实测三条路全灭（503 / 404 / 0 条），判可用属自欺。
    return _playwright_ok()


def is_bilibili_available(config: Optional[Dict[str, Any]] = None) -> bool:
    """B站：TikHub 可用则可用；否则要靠网页版公开 API 或 Playwright。

    本机实测公开 API 探测失败（风控），且未装 Playwright，故无 key 时判不可用。
    """
    config = config or {}
    if config.get("TIKHUB_API_KEY"):
        return True
    return _playwright_ok()


def is_zhihu_available(config: Optional[Dict[str, Any]] = None) -> bool:
    """知乎：**无 TikHub 替代**（TikHub 只有文章/专栏/话题分类搜索，没有综合搜索）。

    网页版 `search_v3` 本机实测 400、热榜 401，只剩 Bing 站内搜索兜底——那不是
    知乎的数据，是搜索引擎收录的零星链接，标成「知乎源可用」属于自欺。
    故只认 ZHIHU_COOKIE 或 Playwright。
    """
    config = config or {}
    if config.get("ZHIHU_COOKIE"):
        return True
    return _playwright_ok()


def is_douyin_available(config: Dict[str, Any]) -> bool:
    if config.get("TIKHUB_API_KEY") or config.get("DOUYIN_API_KEY"):
        return True
    return _playwright_ok()


def is_wechat_available(config: Dict[str, Any]) -> bool:
    if config.get("TIKHUB_API_KEY"):
        return True
    return bool(config.get("WECHAT_API_KEY"))


def is_baidu_api_available(config: Dict[str, Any]) -> bool:
    """百度 API 是否配齐（doctor 用）。注意这不等于百度源不可用——见 is_baidu_available。"""
    return bool(config.get("BAIDU_API_KEY") and config.get("BAIDU_SECRET_KEY"))


def is_baidu_available(config: Dict[str, Any]) -> bool:
    """百度：只认配齐 key 的 API 路径。

    抓页路径**时灵时不灵**：2026-09-14 实测先出过 9 条真结果，同日再跑就被
    「安全验证」拦下、静默降级成 Bing 兜底，吐回一堆百度百科/知乎专栏的常青
    内容（全部 `日期未知 [日期:low]`），在「最近 1 天」的报告里纯属噪音。
    不可靠的路径等于没有路径，故与知乎/头条同等对待。
    配齐 BAIDU_API_KEY + BAIDU_SECRET_KEY 后自动恢复。
    """
    return is_baidu_api_available(config)


def is_toutiao_available(config: Optional[Dict[str, Any]] = None) -> bool:
    """今日头条：**没有任何可用路径**，恒判不可用。

    原生接口要签名（本机实测直接报错），TikHub 只有「按 id 取文章/评论」、
    压根没有搜索端点，也没有 key 可配。剩下的只有 Bing 兜底，不算数。
    """
    return False


# ---------------------------------------------------------------------------
# 实时探测（仅供 --diagnose 使用）
#
# is_*_available() 反映的是"配置/能力是否具备"；下面的 probe_* 则真实发一个
# 短超时请求，反映各源公开端点此刻是否还能拿到数据。约定：
#   - 端点返回明确错误（HTTP 4xx/5xx）或空数据 → False（诚实标记为不可用）
#   - 仅连接超时/网络异常 → fail-open 返回 True（瞬时故障不武断判死）
# ---------------------------------------------------------------------------

_PROBE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _probe_json(url: str, headers: Dict[str, str], timeout: int = 5) -> Optional[dict]:
    """发一个短超时 GET 并解析 JSON。

    返回 dict 表示拿到可解析响应；返回 None 表示明确失败（HTTP 错误/非 JSON）；
    抛出异常表示瞬时网络问题，由调用方 fail-open 处理。
    """
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(50000)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (ValueError, TypeError):
        return None


def probe_bilibili(timeout: int = 5) -> bool:
    """探测 B站公开搜索 API 是否仍返回结果（对齐 bilibili._search_page 端点）。"""
    kw = urllib.parse.quote("AI")
    url = (
        f"https://api.bilibili.com/x/web-interface/search/type"
        f"?search_type=video&keyword={kw}&page=1&page_size=5&order=totalrank"
    )
    headers = {"User-Agent": _PROBE_UA, "Referer": "https://search.bilibili.com/"}
    try:
        data = _probe_json(url, headers, timeout)
        if not data or data.get("code") != 0:
            return False
        return bool(data.get("data", {}).get("result"))
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def probe_zhihu(timeout: int = 5) -> bool:
    """探测知乎公开搜索 API 是否仍返回结果（对齐 zhihu._search_general 端点）。"""
    kw = urllib.parse.quote("AI")
    url = f"https://www.zhihu.com/api/v4/search_v3?t=general&q={kw}&offset=0&limit=1"
    headers = {"User-Agent": _PROBE_UA, "Referer": "https://www.zhihu.com/"}
    try:
        data = _probe_json(url, headers, timeout)
        if not data:
            return False
        return bool(data.get("data"))
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def probe_toutiao(timeout: int = 5) -> bool:
    """探测今日头条原生搜索接口是否仍返回结果（对齐 toutiao._search_content 端点）。

    该接口现已普遍需要 _signature，通常返回空 data；此时如实返回 False，
    提示用户头条实际依赖公开搜索引擎兜底（见 note_douyin_toutiao）。
    """
    kw = urllib.parse.quote("AI")
    url = f"https://www.toutiao.com/api/search/content/?keyword={kw}&count=1&offset=0"
    headers = {
        "User-Agent": _PROBE_UA,
        "Referer": "https://www.toutiao.com/",
        "Cookie": "tt_webid=1",
    }
    try:
        data = _probe_json(url, headers, timeout)
        if not data:
            return False
        return bool(data.get("data"))
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True


def _all_source_ids() -> List[str]:
    return [
        "weibo",
        "xiaohongshu",
        "bilibili",
        "zhihu",
        "douyin",
        "wechat",
        "baidu",
        "toutiao",
    ]


def is_source_available(source: str, config: Dict[str, Any]) -> bool:
    """单个源是否有真实数据路径（Bing 站内搜索兜底不算）。

    引擎的检索闸门用它决定跑不跑；`get_available_sources` 是它的汇总展示版。
    """
    checks = {
        "weibo": is_weibo_available,
        "xiaohongshu": is_xiaohongshu_available,
        "bilibili": is_bilibili_available,
        "zhihu": is_zhihu_available,
        "douyin": is_douyin_available,
        "wechat": is_wechat_available,
        "baidu": is_baidu_available,
        "toutiao": is_toutiao_available,
    }
    check = checks.get(source)
    if check is None:
        return False
    try:
        return bool(check(config))
    except Exception:  # noqa: BLE001 — 探测失败一律当不可用，别把异常抛进检索
        return False


def get_available_sources(config: Dict[str, Any]) -> str:
    """Comma-separated list of source ids that are available for this config."""
    available: List[str] = []
    if is_weibo_available(config):
        available.append("weibo")
    if is_xiaohongshu_available(config):
        available.append("xiaohongshu")
    if is_bilibili_available(config):
        available.append("bilibili")
    if is_zhihu_available(config):
        available.append("zhihu")
    if is_douyin_available(config):
        available.append("douyin")
    if is_wechat_available(config):
        available.append("wechat")
    if is_baidu_available(config):
        available.append("baidu")

    return ",".join(available) if available else "none"


def get_missing_keys(config: Dict[str, Any]) -> str:
    """What is still missing for optional (non–public) sources.

    Returns ``'none'`` when at least one extension credential is set. Otherwise returns a
    Chinese summary of unset env keys (not equal to ``'none'``, so legacy English NUX in
    ``ui.show_promo`` does not fire for the CN build).
    """
    if (
        is_weibo_available(config)
        or is_douyin_available(config)
        or is_wechat_available(config)
        or is_baidu_api_available(config)
        or bool(config.get("SCRAPECREATORS_API_KEY"))
        or bool(config.get("ZHIHU_COOKIE"))
    ):
        return "none"
    lines: List[str] = []
    if not config.get("WEIBO_ACCESS_TOKEN"):
        lines.append("WEIBO_ACCESS_TOKEN（微博）")
    if not config.get("TIKHUB_API_KEY"):
        lines.append("L30D_API_KEY（抖音 / 小红书）")
    if not config.get("ZHIHU_COOKIE"):
        lines.append("ZHIHU_COOKIE")
    if not config.get("WECHAT_API_KEY"):
        lines.append("WECHAT_API_KEY")
    if not (config.get("BAIDU_API_KEY") and config.get("BAIDU_SECRET_KEY")):
        lines.append("BAIDU_API_KEY + BAIDU_SECRET_KEY")
    return "未配置：" + "；".join(lines)


def _parse_available(available: str) -> Set[str]:
    if not available or available == "none":
        return set()
    return {x.strip() for x in available.split(",") if x.strip()}


def validate_sources(
    requested: str,
    available: str,
    include_web: bool = False,
) -> tuple[str, Optional[str]]:
    """Validate requested sources against ``get_available_sources`` output.

    * ``requested`` — ``'auto'``, ``'all'``, or comma-separated source ids
      (e.g. ``weibo,bilibili``).
    * ``available`` — comma-separated ids from :func:`get_available_sources`.
    * ``include_web`` — when True and ``baidu`` is available, ensures ``baidu``
      is included for ``auto`` / ``all``.

    Returns:
        ``(effective_csv, error_message)`` — ``error_message`` is None on success.
    """
    avail = _parse_available(available)
    if not avail:
        return "none", "没有可用的数据源。"

    legacy_auto = {"auto", "all"}
    req = requested.strip().lower()
    if req in legacy_auto or req == "":
        chosen = set(avail)
        if include_web and "baidu" in avail:
            chosen.add("baidu")
        return ",".join(sorted(chosen)), None

    if req == "all":
        chosen = set(avail)
        if include_web and "baidu" in avail:
            chosen.add("baidu")
        return ",".join(sorted(chosen)), None

    requested_ids = {x.strip().lower() for x in requested.split(",") if x.strip()}
    valid = set(_all_source_ids())
    unknown = requested_ids - valid
    if unknown:
        return "none", f"未知来源：{', '.join(sorted(unknown))}"

    missing = requested_ids - avail
    if missing:
        return "none", f"以下来源当前不可用：{', '.join(sorted(missing))}"

    return ",".join(sorted(requested_ids)), None

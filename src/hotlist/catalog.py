"""Build a deterministic, export-friendly catalog of all registered channels."""

from copy import deepcopy
from importlib import import_module
from typing import Any, Iterable

from .registry import CHANNEL_ORDER, get_channel


CATALOG_SCHEMA_VERSION = 1
CATALOG_VERSION = "1.1.1"
CATALOG_UPDATED_AT = "2026-09-18"

CATEGORY_LABELS = {
    "ai": "AI 平台",
    "aggregator": "资讯聚合",
    "authority": "权威发布",
    "developer": "开发者社区",
    "entertainment": "影视文化",
    "finance": "财经资讯",
    "media": "内容媒体",
    "news": "新闻资讯",
    "search": "搜索趋势",
    "social": "社交平台",
    "sports": "体育社区",
    "video": "视频平台",
    "workplace": "职场社区",
    "community": "综合社区",
}

CHANNEL_CATEGORIES = {
    "weibo": "social", "zhihu": "community", "douyin": "video", "kuaishou": "video",
    "bilibili": "video", "acfun": "video", "toutiao": "news", "github": "developer",
    "juejin": "developer", "cnblogs": "developer", "pojie52": "community",
    "googletrends": "search", "bing": "search", "baidu": "search", "wechat": "media",
    "36kr": "news", "readhub": "aggregator", "thepaper": "news", "cctv": "authority",
    "mfa": "authority", "qqnews": "news", "netease": "news", "sina": "news",
    "cls": "finance", "wallstreetcn": "finance", "xueqiu": "finance",
    "eastmoney": "finance", "tonghuashun": "finance", "tieba": "community",
    "douban": "entertainment", "hupu": "sports", "maimai": "workplace",
    "huggingface": "ai", "v2ex": "developer", "lobsters": "developer",
    "hackernews": "developer", "stackoverflow": "developer", "nodeseek": "community",
    "fuliba": "community", "autohome": "news", "gamersky": "entertainment",
    "ithome": "news", "yicai": "finance",
}

SPECIAL_REQUIREMENTS = {
    "bing": ["仅接受经中文内容校验的国内热点，不回退国际新闻"],
    "zhihu": ["ZHIHU_COOKIE 可选；官方接口失败时使用受控降级源"],
    "wechat": ["使用受控聚合源，保留微信原文链接"],
    "maimai": ["需要 MAIMAI_COOKIE，默认不启用且不在页面展示"],
    "sina": ["热榜每小时采集，7x24 内容面每 15 分钟采集"],
    "cls": ["热门文章每小时采集，电报内容面每 15 分钟采集"],
    "wallstreetcn": ["只采集 7x24 内容面，每 15 分钟运行"],
    "readhub": ["热点、每日早报和 AI 资讯归为 digest，不进入综合报告"],
    "cctv": ["作为 authority 内容保存，不进入综合报告"],
    "mfa": ["作为 authority 内容保存，不进入综合报告"],
    "yicai": ["首页头条每小时采集，7x24 快讯每 15 分钟采集"],
    "fuliba": ["默认隐藏且不进入综合报告"],
}


def _module_name(channel_id: str) -> str:
    return "kr36" if channel_id == "36kr" else channel_id


def _urls(value: Any) -> Iterable[str]:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _urls(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _urls(child)


def _collector_details(channel_id: str, homepage: str) -> dict:
    module_name = _module_name(channel_id)
    module = import_module(f"src.hotlist.channels.{module_name}")
    endpoints = []
    seen = set()
    for name, value in sorted(vars(module).items()):
        if not name.isupper() or not any(token in name for token in ("URL", "URI", "ENDPOINT")):
            continue
        for url in _urls(value):
            if url in seen:
                continue
            seen.add(url)
            endpoints.append({
                "name": name.lower(),
                "kind": "api" if "API" in name or "/api/" in url else "page",
                "url": url,
            })
    if homepage not in seen:
        endpoints.insert(0, {"name": "homepage", "kind": "page", "url": homepage})
    entry_points = sorted(
        name for name, value in vars(module).items()
        if callable(value) and (name == "collect" or name.startswith("collect_"))
    )
    return {
        "module": f"src/hotlist/channels/{module_name}.py",
        "entryPoints": entry_points or ["collect"],
        "endpoints": endpoints,
    }


def build_catalog(catalog_version: str = CATALOG_VERSION, updated_at: str = CATALOG_UPDATED_AT) -> dict:
    channels = []
    for channel_id in CHANNEL_ORDER:
        definition = get_channel(channel_id)
        category = CHANNEL_CATEGORIES[channel_id]
        channels.append({
            "channelId": channel_id,
            "name": definition.name,
            "shortName": definition.short_name,
            "order": definition.order,
            "category": {"id": category, "label": CATEGORY_LABELS[category]},
            "surfaces": list(definition.surfaces),
            "homepage": definition.homepage,
            "collector": _collector_details(channel_id, definition.homepage),
            "schedule": {"frequencyMinutes": definition.frequency_minutes},
            "defaults": {
                "enabled": definition.enabled_by_default,
                "visible": definition.visible_by_default,
                "includeInReport": definition.include_in_report,
            },
            "freshness": {"staleAfterHours": definition.stale_after_hours},
            "requirements": {
                "authentication": "environment" if definition.requires_env else "none",
                "environment": list(definition.requires_env),
                "notes": SPECIAL_REQUIREMENTS.get(channel_id, []),
            },
        })
    return {
        "$schema": "schema.v1.json",
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "catalogVersion": catalog_version,
        "updatedAt": updated_at,
        "updatePolicy": {
            "schema": "config/channels/schema.v1.json",
            "baseline": "config/channels/base.v1.json",
            "current": "config/channels/current.json",
            "changes": "config/channels/changes/*.json",
            "strategy": "full-snapshot-plus-append-only-deltas",
        },
        "channels": channels,
    }


def build_catalog_delta(base: dict, target: dict, change_id: str) -> dict:
    base_by_id = {item["channelId"]: item for item in base.get("channels", [])}
    target_by_id = {item["channelId"]: item for item in target.get("channels", [])}
    operations = []
    for item in base.get("channels", []):
        channel_id = item["channelId"]
        if channel_id not in target_by_id:
            operations.append({"op": "remove", "channelId": channel_id})
        elif item != target_by_id[channel_id]:
            operations.append({"op": "replace", "channelId": channel_id, "value": target_by_id[channel_id]})
    for item in target.get("channels", []):
        if item["channelId"] not in base_by_id:
            operations.append({"op": "add", "channelId": item["channelId"], "value": item})
    return {
        "schemaVersion": 1,
        "changeId": change_id,
        "fromVersion": base.get("catalogVersion", ""),
        "toVersion": target.get("catalogVersion", ""),
        "targetMetadata": {key: value for key, value in target.items() if key != "channels"},
        "operations": operations,
    }


def apply_catalog_delta(base: dict, delta: dict) -> dict:
    if base.get("catalogVersion") != delta.get("fromVersion"):
        raise ValueError("catalog delta does not match the base version")
    channels = [deepcopy(item) for item in base.get("channels", [])]
    indexes = {item["channelId"]: index for index, item in enumerate(channels)}
    for operation in delta.get("operations", []):
        channel_id = operation["channelId"]
        if operation["op"] == "remove":
            channels.pop(indexes[channel_id])
        elif operation["op"] == "replace":
            channels[indexes[channel_id]] = deepcopy(operation["value"])
        elif operation["op"] == "add":
            channels.append(deepcopy(operation["value"]))
        else:
            raise ValueError(f"unsupported catalog operation: {operation['op']}")
        indexes = {item["channelId"]: index for index, item in enumerate(channels)}
    if channels and all("order" in item for item in channels):
        channels.sort(key=lambda item: item["order"])
    result = deepcopy(delta.get("targetMetadata", {}))
    result["channels"] = channels
    return result

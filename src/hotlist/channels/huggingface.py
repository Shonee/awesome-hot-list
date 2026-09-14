"""Hugging Face model trending adapter."""

from src.utils.http_utils import get

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://huggingface.co/models?sort=trending"
API_URL = "https://huggingface.co/api/models?sort=trendingScore&limit=20"


def parse_models(payload: list) -> list[HotItem]:
    items = []
    for row in payload or []:
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("id") or row.get("modelId") or "").strip()
        if not model_id:
            continue
        detail = []
        if row.get("downloads") is not None:
            detail.append(f"{row['downloads']} downloads")
        if row.get("likes") is not None:
            detail.append(f"{row['likes']} likes")
        if row.get("pipeline_tag"):
            detail.append(str(row["pipeline_tag"]))
        items.append(
            HotItem(
                len(items) + 1,
                model_id,
                f"https://huggingface.co/{model_id}",
                hot=row.get("trendingScore"),
                description=" · ".join(detail),
                published_at=row.get("lastModified") or "",
            )
        )
        if len(items) >= 20:
            break
    return items


def collect() -> "ChannelSnapshot":
    items = parse_models(get(API_URL, res_type="json", timeout=25, retries=2))
    return snapshot(
        "huggingface",
        [Ranking("models", "Trending Models", items, SOURCE_URL, "Hugging Face 官方 API", API_URL)],
    )

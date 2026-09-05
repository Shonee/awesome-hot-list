"""Unified data model shared by every channel collector and the static site."""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


HotValue = Optional[Union[int, float, str]]


@dataclass
class HotItem:
    rank: int
    title: str
    url: str
    hot: HotValue = None
    description: str = ""
    image_url: str = ""
    published_at: str = ""

    def __post_init__(self):
        self.rank = max(1, int(self.rank))
        self.title = str(self.title or "").strip()
        self.url = str(self.url or "").strip()
        self.description = str(self.description or "").strip()
        self.image_url = str(self.image_url or "").strip()
        self.published_at = str(self.published_at or "").strip()
        if not self.title:
            raise ValueError("hot item title must not be empty")

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "title": self.title,
            "url": self.url,
            "hot": self.hot,
            "description": self.description,
            "imageUrl": self.image_url,
            "publishedAt": self.published_at,
        }


@dataclass
class Ranking:
    ranking_id: str
    name: str
    items: List[HotItem] = field(default_factory=list)
    source_url: str = ""

    def __post_init__(self):
        self.ranking_id = str(self.ranking_id or "").strip()
        self.name = str(self.name or "").strip()
        if not self.ranking_id or not self.name:
            raise ValueError("ranking id and name must not be empty")

    def to_dict(self) -> dict:
        return {
            "id": self.ranking_id,
            "name": self.name,
            "sourceUrl": self.source_url,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class ChannelSnapshot:
    channel_id: str
    channel_name: str
    source_url: str
    fetched_at: str
    rankings: List[Ranking] = field(default_factory=list)
    status: str = "ok"
    error: str = ""
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "channelId": self.channel_id,
            "channelName": self.channel_name,
            "sourceUrl": self.source_url,
            "fetchedAt": self.fetched_at,
            "status": self.status,
            "error": self.error,
            "rankings": [ranking.to_dict() for ranking in self.rankings],
        }

    def to_legacy_rows(self) -> List[dict]:
        rows = []
        for ranking in self.rankings:
            for item in ranking.items:
                rows.append(
                    {
                        "index": item.rank,
                        "title": item.title,
                        "desc": item.description,
                        "hot": "" if item.hot is None else item.hot,
                        "url": item.url,
                        "image": item.image_url,
                        "source": self.channel_name,
                        "type": ranking.name,
                        "datetime": self.fetched_at,
                    }
                )
        return rows

    @classmethod
    def unavailable(
        cls,
        channel_id: str,
        channel_name: str,
        source_url: str,
        fetched_at: str,
        status: str,
        error: str,
    ) -> "ChannelSnapshot":
        return cls(
            channel_id=channel_id,
            channel_name=channel_name,
            source_url=source_url,
            fetched_at=fetched_at,
            rankings=[],
            status=status,
            error=error,
        )


def item_from_legacy(row: dict, fallback_rank: int) -> HotItem:
    """Normalize one existing collector row without leaking legacy field names."""
    rank = row.get("index") or row.get("rank") or fallback_rank
    image_url = row.get("image") or row.get("img_url") or ""
    return HotItem(
        rank=rank,
        title=row.get("title") or row.get("name") or "",
        url=row.get("url") or "",
        hot=row.get("hot") if row.get("hot") is not None else row.get("score"),
        description=row.get("desc") or row.get("description") or "",
        image_url=image_url,
        published_at=row.get("published_at") or row.get("createtime") or row.get("push_time") or "",
    )


def items_from_legacy(rows: Any) -> List[HotItem]:
    if not isinstance(rows, list):
        return []
    items = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not (row.get("title") or row.get("name")):
            continue
        items.append(item_from_legacy(row, index))
    return items

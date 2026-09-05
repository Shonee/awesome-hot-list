"""Collector runner and static latest.json writer."""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Mapping, Optional

from src.utils.file_utils import write_json

from .models import ChannelSnapshot
from .registry import CHANNEL_ORDER, CHANNELS, ChannelDefinition


def now_string() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def collect_channels(
    channel_ids: Iterable[str],
    definitions: Optional[Mapping[str, ChannelDefinition]] = None,
) -> List[ChannelSnapshot]:
    definitions = definitions or CHANNELS
    snapshots = []
    for channel_id in channel_ids:
        definition = definitions[channel_id]
        try:
            if definition.collector is None:
                raise RuntimeError("collector is not implemented")
            snapshot = definition.collector()
            if snapshot.channel_id != channel_id:
                raise ValueError(
                    f"collector returned channel {snapshot.channel_id!r}, expected {channel_id!r}"
                )
            snapshots.append(snapshot)
        except Exception as exc:  # noqa: BLE001 - a single source must not abort the batch
            snapshots.append(
                ChannelSnapshot.unavailable(
                    channel_id=channel_id,
                    channel_name=definition.name,
                    source_url=definition.homepage,
                    fetched_at=now_string(),
                    status="error",
                    error=str(exc),
                )
            )
    return snapshots


def _load_latest(path: str) -> Dict[str, dict]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    channels = payload.get("channels", []) if isinstance(payload, dict) else []
    return {
        item.get("channelId"): item
        for item in channels
        if isinstance(item, dict) and item.get("channelId")
    }


def due_channel_ids(
    channel_ids: Iterable[str],
    latest_path: str,
    definitions: Optional[Mapping[str, ChannelDefinition]] = None,
    now: Optional[datetime] = None,
) -> List[str]:
    """Return channels whose configured interval has elapsed.

    ``fetchedAt`` is intentionally used instead of ``checkedAt``. A failed
    request must remain eligible for the next scheduled attempt rather than
    postponing retries for another full interval.
    """
    definitions = definitions or CHANNELS
    latest = _load_latest(latest_path)
    now = now or datetime.now()
    due = []
    for channel_id in channel_ids:
        previous = latest.get(channel_id, {})
        fetched_at = previous.get("fetchedAt", "")
        try:
            fetched = datetime.strptime(fetched_at, "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            due.append(channel_id)
            continue
        interval = timedelta(minutes=max(1, definitions[channel_id].frequency_minutes))
        if now - fetched >= interval:
            due.append(channel_id)
    return due


def merge_latest_snapshot(
    snapshots: Iterable[ChannelSnapshot],
    output_path: str,
    channel_order=CHANNEL_ORDER,
) -> dict:
    merged = _load_latest(output_path)
    for snapshot in snapshots:
        incoming = snapshot.to_dict()
        previous = merged.get(snapshot.channel_id)
        if snapshot.status != "ok" and previous and previous.get("rankings"):
            previous = dict(previous)
            previous.update(
                {
                    "status": "stale",
                    "error": snapshot.error,
                    "checkedAt": snapshot.fetched_at,
                }
            )
            merged[snapshot.channel_id] = previous
        else:
            merged[snapshot.channel_id] = incoming

    ordered_ids = [channel_id for channel_id in channel_order if channel_id in merged]
    ordered_ids.extend(sorted(set(merged) - set(ordered_ids)))
    payload = {
        "schemaVersion": 1,
        "generatedAt": now_string(),
        "channels": [merged[channel_id] for channel_id in ordered_ids],
    }
    write_json(payload, output_path, atomic=True)
    return payload

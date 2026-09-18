"""Collector runner and static latest.json writer."""

import json
import os
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from src.utils.file_utils import write_json
from src.utils.time_utils import now_string, project_now

from .models import ChannelSnapshot
from .registry import (
    CHANNEL_ORDER,
    CHANNELS,
    RETIRED_CHANNEL_IDS,
    RETIRED_RANKING_IDS,
    ChannelDefinition,
)


SURFACES = ("hotlist", "live", "digest", "authority")
SURFACE_FILENAMES = {
    "hotlist": "latest.json",
    "live": "live.json",
    "digest": "digest.json",
    "authority": "authority.json",
}


def surface_data_path(latest_path, surface: str) -> Path:
    """Return the sibling data file for a ranking surface."""
    if surface not in SURFACE_FILENAMES:
        raise ValueError(f"unsupported ranking surface: {surface}")
    return Path(latest_path).with_name(SURFACE_FILENAMES[surface])

def collect_channels(
    channel_ids: Iterable[str],
    definitions: Optional[Mapping[str, ChannelDefinition]] = None,
    surface: str = "",
) -> List[ChannelSnapshot]:
    use_registered_collectors = definitions is None
    definitions = definitions or CHANNELS
    snapshots = []
    for channel_id in channel_ids:
        definition = definitions[channel_id]
        try:
            if definition.collector is None:
                raise RuntimeError("collector is not implemented")
            if surface and use_registered_collectors:
                from .channels import collect_channel

                snapshot = collect_channel(channel_id, surface=surface)
            else:
                snapshot = definition.collector()
            if snapshot.channel_id != channel_id:
                raise ValueError(
                    f"collector returned channel {snapshot.channel_id!r}, expected {channel_id!r}"
                )
            undeclared = sorted({ranking.surface for ranking in snapshot.rankings} - set(definition.surfaces))
            if undeclared:
                raise ValueError(
                    f"collector returned undeclared ranking surface(s): {', '.join(undeclared)}"
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


def _load_all_surfaces(latest_path) -> Dict[str, dict]:
    merged = {}
    for surface in SURFACES:
        for channel_id, item in _load_latest(os.fspath(surface_data_path(latest_path, surface))).items():
            previous = merged.get(channel_id)
            if previous is None or str(item.get("fetchedAt") or "") > str(previous.get("fetchedAt") or ""):
                merged[channel_id] = item
    return merged


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
    latest = _load_all_surfaces(latest_path)
    now = now or project_now().replace(tzinfo=None)
    due = []
    for channel_id in channel_ids:
        previous = latest.get(channel_id, {})
        if previous.get("status") and previous.get("status") != "ok" and not any(
            ranking.get("items")
            for ranking in previous.get("rankings", [])
            if isinstance(ranking, dict)
        ):
            due.append(channel_id)
            continue
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
    preserve_existing_rankings: bool = False,
    surface: str = "",
) -> dict:
    merged = _load_latest(output_path)
    if surface:
        for channel_id, item in list(merged.items()):
            rankings = [
                ranking
                for ranking in item.get("rankings", [])
                if str(ranking.get("surface") or "hotlist").strip().lower() == surface
            ]
            if not rankings:
                merged.pop(channel_id, None)
                continue
            item = dict(item)
            item["rankings"] = rankings
            merged[channel_id] = item
    for channel_id in RETIRED_CHANNEL_IDS:
        merged.pop(channel_id, None)
    if "ithome" in merged and not any(
        ranking.get("id") == "daily" for ranking in merged["ithome"].get("rankings", [])
        if isinstance(ranking, dict)
    ):
        merged.pop("ithome")
    for channel_id, ranking_ids in RETIRED_RANKING_IDS.items():
        if channel_id not in merged:
            continue
        retired = set(ranking_ids)
        merged[channel_id]["rankings"] = [
            ranking
            for ranking in merged[channel_id].get("rankings", [])
            if ranking.get("id") not in retired
        ]
    for snapshot in snapshots:
        if snapshot.channel_id in RETIRED_CHANNEL_IDS:
            continue
        incoming = snapshot.to_dict()
        if surface:
            incoming["rankings"] = [
                ranking
                for ranking in incoming["rankings"]
                if ranking.get("surface", "hotlist") == surface
            ]
            if snapshot.status == "ok" and not incoming["rankings"]:
                continue
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
            if snapshot.status == "ok" and previous:
                prior_rankings = {
                    ranking.get("id"): ranking
                    for ranking in previous.get("rankings", [])
                    if isinstance(ranking, dict) and ranking.get("id")
                }
                for ranking in incoming["rankings"]:
                    prior = prior_rankings.get(ranking["id"])
                    if not ranking["items"] and prior and prior.get("items"):
                        ranking["items"] = prior["items"]
                        if ranking["name"] not in incoming["warnings"]:
                            incoming["warnings"].append(ranking["name"])
                if preserve_existing_rankings:
                    incoming_by_id = {ranking["id"]: ranking for ranking in incoming["rankings"]}
                    combined = []
                    for prior in previous.get("rankings", []):
                        combined.append(incoming_by_id.pop(prior.get("id"), prior))
                    combined.extend(incoming_by_id.values())
                    incoming["rankings"] = combined
            merged[snapshot.channel_id] = incoming

    ordered_ids = [channel_id for channel_id in channel_order if channel_id in merged]
    ordered_ids.extend(sorted(set(merged) - set(ordered_ids)))
    payload = {
        "schemaVersion": 1,
        "generatedAt": now_string(),
        "channels": [merged[channel_id] for channel_id in ordered_ids],
    }
    write_json(payload, output_path, indent=None, atomic=True)
    return payload


def _payload_for_channels(channels: Dict[str, dict], generated_at: str = "") -> dict:
    ordered_ids = [channel_id for channel_id in CHANNEL_ORDER if channel_id in channels]
    ordered_ids.extend(sorted(set(channels) - set(ordered_ids)))
    return {
        "schemaVersion": 1,
        "generatedAt": generated_at or now_string(),
        "channels": [channels[channel_id] for channel_id in ordered_ids],
    }


def migrate_surface_files(latest_path) -> None:
    """Split rankings left in a legacy combined latest.json without losing newer files."""
    latest_path = Path(latest_path)
    legacy = _load_latest(os.fspath(latest_path))
    if not legacy and not latest_path.is_file():
        return
    try:
        with latest_path.open("r", encoding="utf-8") as file:
            generated_at = str(json.load(file).get("generatedAt") or "")
    except (OSError, json.JSONDecodeError, AttributeError):
        generated_at = ""

    for surface in SURFACES:
        target_path = surface_data_path(latest_path, surface)
        existing = _load_latest(os.fspath(target_path)) if target_path != latest_path else {}
        changed = False
        for channel_id, item in legacy.items():
            rankings = [
                ranking
                for ranking in item.get("rankings", [])
                if str(ranking.get("surface") or "hotlist").strip().lower() == surface
            ]
            if not rankings or channel_id in existing:
                continue
            migrated = dict(item)
            migrated["rankings"] = rankings
            existing[channel_id] = migrated
            changed = True

        if target_path == latest_path:
            changed = changed or any(
                str(ranking.get("surface") or "hotlist").strip().lower() != "hotlist"
                for item in legacy.values()
                for ranking in item.get("rankings", [])
            )
        if changed or not target_path.is_file():
            write_json(
                _payload_for_channels(existing, generated_at),
                os.fspath(target_path),
                indent=None,
                atomic=True,
            )


def write_surface_snapshots(
    snapshots: Iterable[ChannelSnapshot],
    latest_path,
    requested_surface: str = "",
    channel_order=CHANNEL_ORDER,
) -> Dict[str, dict]:
    """Persist snapshots by surface while retaining channel-level failure isolation."""
    snapshots = list(snapshots)
    migrate_surface_files(latest_path)
    outputs = {}
    surfaces = (requested_surface,) if requested_surface else SURFACES
    for surface in surfaces:
        selected = []
        for snapshot in snapshots:
            definition = CHANNELS.get(snapshot.channel_id)
            declared = definition.surfaces if definition else tuple(
                dict.fromkeys(ranking.surface for ranking in snapshot.rankings)
            )
            rankings = [ranking for ranking in snapshot.rankings if ranking.surface == surface]
            if rankings:
                selected.append(replace(snapshot, rankings=rankings))
            elif snapshot.status != "ok" and surface in declared:
                selected.append(replace(snapshot, rankings=[]))
        output_path = surface_data_path(latest_path, surface)
        if not selected and output_path.is_file():
            continue
        allowed_order = tuple(
            channel_id
            for channel_id in channel_order
            if channel_id not in CHANNELS or surface in CHANNELS[channel_id].surfaces
        )
        payload = merge_latest_snapshot(
            selected,
            os.fspath(output_path),
            channel_order=allowed_order,
            preserve_existing_rankings=bool(requested_surface),
            surface=surface,
        )
        if selected:
            outputs[surface] = payload
    return outputs

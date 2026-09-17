"""Lazy channel adapter loader.

Each module in this package owns one source's request and parsing rules. The
public collector contract is a ``ChannelSnapshot``; persistence stays in the
CLI and runner layers.
"""

from dataclasses import replace
from importlib import import_module

from ..models import ChannelSnapshot


MODULE_ALIASES = {"36kr": "kr36"}


def collect_channel(channel_id: str, surface: str = "") -> ChannelSnapshot:
    module_name = f"{__name__}.{MODULE_ALIASES.get(channel_id, channel_id)}"
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        raise ValueError(f"collector is not registered: {channel_id}") from exc
    try:
        collector = getattr(module, f"collect_{surface}", module.collect) if surface else module.collect
    except AttributeError as exc:
        raise ValueError(f"collector is not registered: {channel_id}") from exc
    result = collector()
    if not isinstance(result, ChannelSnapshot):
        raise TypeError(f"collector {channel_id!r} must return ChannelSnapshot")
    if surface and collector is module.collect:
        result = replace(
            result,
            rankings=[ranking for ranking in result.rankings if ranking.surface == surface],
        )
    return result


__all__ = ["collect_channel"]

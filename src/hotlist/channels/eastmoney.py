"""Eastmoney official stock popularity ranking adapter."""

import logging

from urllib.parse import urlencode

from src.utils.http_utils import get, post

from ..models import HotItem, Ranking
from .common import snapshot


SOURCE_URL = "https://guba.eastmoney.com/rank/"
RANK_API = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
QUOTE_API = "https://push2.eastmoney.com/api/qt/ulist.np/get"
RANK_PAYLOAD = {
    "appId": "appId01",
    "globalId": "786e4c21-70dc-435a-93bb-38",
    "marketType": "",
    "pageNo": 1,
    "pageSize": 20,
}
logger = logging.getLogger(__name__)


def _security_id(code: str) -> str:
    code = str(code or "").upper()
    prefix = "1" if code.startswith("SH") else "0"
    return f"{prefix}.{code[2:]}" if len(code) > 2 else ""


def _quote_map(payload: dict) -> dict[str, dict]:
    rows = ((payload or {}).get("data") or {}).get("diff") or []
    return {str(row.get("f12") or ""): row for row in rows if isinstance(row, dict)}


def parse_popularity(rank_payload: dict, quote_payload: dict) -> list[HotItem]:
    quotes = _quote_map(quote_payload)
    items = []
    for row in (rank_payload or {}).get("data") or []:
        if not isinstance(row, dict):
            continue
        full_code = str(row.get("sc") or "")
        code = full_code[2:] if len(full_code) > 2 else full_code
        quote = quotes.get(code, {})
        name = str(quote.get("f14") or code).strip()
        if not code or not name:
            continue
        percent_raw = quote.get("f3")
        price_raw = quote.get("f2")
        percent = percent_raw / 100 if isinstance(percent_raw, (int, float)) else None
        price = price_raw / 100 if isinstance(price_raw, (int, float)) else None
        detail = []
        if price is not None:
            detail.append(f"现价 {price:.2f}")
        if percent is not None:
            detail.append(f"涨跌 {percent:+.2f}%")
        rank_change = row.get("rc")
        if isinstance(rank_change, (int, float)) and rank_change:
            detail.append(f"排名{'上升' if rank_change > 0 else '下降'} {abs(int(rank_change))}")
        items.append(
            HotItem(
                row.get("rk") or len(items) + 1,
                f"{name} ({code})",
                f"https://quote.eastmoney.com/{full_code.lower()}.html",
                hot=f"{percent:+.2f}%" if percent is not None else None,
                description=" · ".join(detail),
            )
        )
    return items


def collect() -> "ChannelSnapshot":
    rank_payload = post(RANK_API, payload=RANK_PAYLOAD, res_type="json", timeout=20, retries=2)
    rows = (rank_payload or {}).get("data") or []
    security_ids = [_security_id(row.get("sc")) for row in rows if isinstance(row, dict)]
    query = urlencode({"secids": ",".join(filter(None, security_ids)), "fields": "f12,f14,f2,f3"})
    warning = ""
    try:
        quote_payload = get(f"{QUOTE_API}?{query}", res_type="json", timeout=20, retries=2)
    except Exception as exc:  # noqa: BLE001 - rank data remains useful without enrichment
        logger.warning("东方财富行情增强失败，保留人气榜代码: %s", exc)
        quote_payload = {}
        warning = f"行情增强失败，仅展示股票代码: {exc}"
    items = parse_popularity(rank_payload, quote_payload)
    result = snapshot(
        "eastmoney",
        [Ranking("popularity", "股票人气榜", items, SOURCE_URL, "东方财富官方", RANK_API)],
    )
    if warning:
        result.warnings.append(warning)
    return result

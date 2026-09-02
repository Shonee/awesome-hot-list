# -*- coding: utf-8 -*-
"""归档数据聚合（优化后的 json 归档形态）。

每天由 aggregate-daily.yml 在北京时间 00:30 触发，针对每个渠道整合「昨天」
一整天的 CSV 数据：

1. 按采集批次时间（csv 的 datetime 列）还原时间片，按 type（排行榜类型）分组；
2. 计算每种排行榜一天内的排名 / 热度变化（top_stable、上升/下降最多、
   新进/退出榜单的条目、完整时间线快照）；
3. 写入 archived/<platform>/data.json，按日期滚动保留 7 天；
4. 可选生成每个 type 的 gif 动图（matplotlib，依赖缺失时跳过），同样滚动 7 天。

幂等：data.json 中已含目标日期则跳过该渠道当天整合。
历史归档数据（archived 下既有文件）不会被修改，本脚本只新增 data.json / gif。
"""

import io
import json
import os
import sys
import time

# 让本脚本在任意 cwd 下都能找到 src/utils 下的工具模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "utils"))

from utils import (
    archive_path,
    data_json_path,
    gif_dir,
    logger,
    read_csv,
    write_enabled,
    yesterday_date,
)
from file_utils import write_json

# 所有渠道。weibo 定时停用、无 csv 时自动跳过。
CHANNELS = ["bilibili", "douyin", "github", "weibo", "zhihu"]

#: data.json 与动图滚动保留天数
RETENTION_DAYS = 7

#: 时间线与动图保留的榜单条数上限（控制体积）
TOP_N = 15


def _to_number(value):
    """尽力把热度值转成 float；失败返回 0.0。支持「万/亿」中文单位。"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    unit = 1.0
    if "亿" in s:
        unit = 1e8
        s = s.replace("亿", "")
    elif "万" in s:
        unit = 1e4
        s = s.replace("万", "")
    s = s.replace(",", "").replace("%", "").strip()
    try:
        return float(s) * unit
    except ValueError:
        return 0.0


def _safe_rank(value):
    """把排名转成 int；缺失或非正返回 0（表示无效）。"""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def _fmt_hot(v: float) -> str:
    """把热度数值格式化成人读友好的「万/亿」单位。"""
    if v >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if v >= 1e4:
        return f"{v / 1e4:.1f}万"
    return f"{int(v)}"


def _load_type_slices(platform: str, date: str):
    """读某天 csv，返回 {type: [{"time":..., "items":[row,...]}, ...]}。

    时间片按时间升序；csv 缺 datetime 列时整文件视为单一时间片。
    """
    csv_path = archive_path(platform, "csv", date)
    rows = read_csv(csv_path)
    if not rows:
        return None

    has_dt = any(r.get("datetime") for r in rows)
    cells = {}  # (type, time) -> [rows]
    for r in rows:
        t = r.get("type") or "unknown"
        dt = r.get("datetime") or date
        cells.setdefault((t, dt), []).append(r)

    result = {}
    for (t, _dt), item_rows in cells.items():
        result.setdefault(t, []).append((_dt, item_rows))
    for t in result:
        result[t].sort(key=lambda x: x[0])
        result[t] = [{"time": dt, "items": item_rows} for dt, item_rows in result[t]]
    return result


def _summarize_type(type_slices):
    """整合某 type 一天内的变化，返回 {slices, summary}。"""
    tracks = {}  # title -> {"ranks":[], "hots":[], "times":[], "url":...}
    for sl in type_slices:
        for r in sl["items"]:
            title = r.get("title")
            if not title:
                continue
            tr = tracks.setdefault(
                title,
                {"title": title, "ranks": [], "hots": [], "times": [], "url": r.get("url")},
            )
            tr["ranks"].append(_safe_rank(r.get("index")))
            tr["hots"].append(_to_number(r.get("hot")))
            tr["times"].append(sl["time"])
            if r.get("url"):
                tr["url"] = r.get("url")

    enriched = []
    for title, tr in tracks.items():
        valid_ranks = [x for x in tr["ranks"] if x > 0]
        first_rank = valid_ranks[0] if valid_ranks else 0
        last_rank = valid_ranks[-1] if valid_ranks else 0
        delta = (first_rank - last_rank) if (first_rank and last_rank) else 0
        enriched.append({
            "title": title,
            "url": tr.get("url"),
            "appear_count": len(tr["ranks"]),
            "first_rank": first_rank,
            "last_rank": last_rank,
            "rank_delta": delta,
            "max_hot": max(tr["hots"]) if tr["hots"] else 0.0,
            "avg_hot": (sum(tr["hots"]) / len(tr["hots"])) if tr["hots"] else 0.0,
        })

    top_stable = sorted(enriched, key=lambda x: (-x["appear_count"], x["first_rank"] or 999))[:10]
    movers = [e for e in enriched if e["rank_delta"] != 0]
    risers = sorted([e for e in movers if e["rank_delta"] > 0], key=lambda x: -x["rank_delta"])[:10]
    fallers = sorted([e for e in movers if e["rank_delta"] < 0], key=lambda x: x["rank_delta"])[:10]

    first_titles = {r.get("title") for sl in [type_slices[0]] for r in sl["items"] if r.get("title")}
    last_titles = {r.get("title") for sl in [type_slices[-1]] for r in sl["items"] if r.get("title")}
    new_entries = sorted(last_titles - first_titles)
    exit_entries = sorted(first_titles - last_titles)

    return {
        "slices": [
            {
                "time": sl["time"],
                "items": [
                    {
                        "index": r.get("index"),
                        "title": r.get("title"),
                        "hot": r.get("hot"),
                        "url": r.get("url"),
                    }
                    for r in sorted(
                        sl["items"],
                        key=lambda x: (_safe_rank(x.get("index")) or 999, -_to_number(x.get("hot"))),
                    )[:TOP_N]
                ],
            }
            for sl in type_slices
        ],
        "summary": {
            "top_stable": top_stable,
            "biggest_risers": risers,
            "biggest_fallers": fallers,
            "new_entries": new_entries,
            "exit_entries": exit_entries,
        },
    }


def _make_gif(platform: str, date: str, type_name: str, type_slices):
    """为某 type 生成时间线动图（每帧一个时间片的 top 条形图）。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        # 中文字体注册：先用 findfont 探测已知中文字体名（mac 上
        # PingFang 被系统收进动态 Asset 字体，直接写路径找不到，但
        # findfont("STHeiti") 能定位到含中文的 STHEITI.ttf）；找不到再
        # 回退到文件路径（CI 装好 fonts-noto-cjk 后命中 Noto）。
        _CJK_NAMES = [
            "STHeiti", "PingFang SC", "Noto Sans CJK SC", "Noto Sans CJK JP",
            "WenQuanYi Zen Hei", "Microsoft YaHei", "SimHei",
        ]
        _CJK_PATHS = [
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ]
        _font_path = None
        for nm in _CJK_NAMES:
            try:
                fp = fm.findfont(nm, fallback_to_default=False)
                if fp and "DejaVuSans" not in fp:
                    _font_path = fp
                    break
            except Exception:  # noqa: BLE001
                continue
        if not _font_path:
            for c in _CJK_PATHS:
                if os.path.isfile(c):
                    _font_path = c
                    break
        if _font_path:
            try:
                fm.fontManager.addfont(_font_path)
                plt.rcParams["font.family"] = fm.FontProperties(fname=_font_path).get_name()
            except Exception as e:  # noqa: BLE001
                logger.warning("中文字体注册失败，动图中文可能缺字：%s", e)
        else:
            logger.warning("未找到中文字体文件，动图中文将显示为方块")
        plt.rcParams["axes.unicode_minus"] = False
        from PIL import Image
    except Exception as e:  # noqa: BLE001
        logger.warning("跳过动图生成（缺少 matplotlib/PIL）：%s", e)
        return None

    frames = []
    for sl in type_slices:
        items = sorted(
            sl["items"],
            key=lambda r: (_to_number(r.get("hot")), -(_safe_rank(r.get("index")) or 0)),
            reverse=True,
        )[:TOP_N]
        if not items:
            continue
        titles = [str(it.get("title", ""))[:18] for it in items][::-1]
        vals = [_to_number(it.get("hot")) for it in items][::-1]
        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        bars = ax.barh(titles, vals, color="#fc8b00")
        ax.set_title(f"{type_name}  |  {sl['time']}", fontsize=15, pad=10)
        ax.tick_params(labelsize=11)
        # 固定布局：每帧像素尺寸恒定，Pillow 合成 gif 时不再缩放（避免发虚）
        fig.subplots_adjust(left=0.34, right=0.97, top=0.9, bottom=0.07)
        # 条形末端标注热度值，增强可读性
        for b in bars:
            w = b.get_width()
            if w > 0:
                ax.text(w, b.get_y() + b.get_height() / 2, f" {_fmt_hot(w)}",
                        va="center", ha="left", fontsize=9, color="#333333")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        buf.seek(0)
        frames.append(Image.open(buf))

    if not frames:
        return None

    out_dir = gif_dir(platform)
    os.makedirs(out_dir, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in type_name)
    out_path = os.path.join(out_dir, f"{date}-{safe}.gif")
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=500,
        loop=0,
        optimize=True,
        disposal=2,
    )
    logger.info("动图已生成: %s", out_path)
    return out_path


def _prune_retention(platform: str):
    """清理超过保留期的 data.json key 与 gif 文件。"""
    from datetime import datetime, timedelta

    data_path = data_json_path(platform)
    if os.path.isfile(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and len(data) > RETENTION_DAYS:
            keep = sorted(data.keys())[-RETENTION_DAYS:]
            write_json({k: data[k] for k in keep}, data_path)

    gdir = gif_dir(platform)
    if not os.path.isdir(gdir):
        return
    import re
    pat = re.compile(r"^(\d{4}-\d{2}-\d{2})-.*\.gif$")
    for name in os.listdir(gdir):
        m = pat.match(name)
        if not m:
            continue
        try:
            d_obj = datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            continue
        if (datetime.now() - d_obj).days > RETENTION_DAYS:
            try:
                os.remove(os.path.join(gdir, name))
                logger.info("清理过期动图: %s", name)
            except OSError:
                pass


def aggregate_yesterday(platform: str, date: str = None):
    """整合某渠道昨天的 CSV（幂等）。"""
    date = date or yesterday_date()
    data_path = data_json_path(platform)

    current = {}
    if os.path.isfile(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except (OSError, json.JSONDecodeError):
            current = {}
    if date in current:
        logger.info("[%s] %s 已整合，跳过", platform, date)
        return

    type_slices = _load_type_slices(platform, date)
    if not type_slices:
        logger.warning("[%s] %s 无 CSV 数据，跳过整合", platform, date)
        return

    rankings = {}
    for t, slices in type_slices.items():
        rankings[t] = _summarize_type(slices)
        if write_enabled():
            _make_gif(platform, date, t, slices)

    value = {
        "date": date,
        "platform": platform,
        "slices_count": max(len(s) for s in type_slices.values()),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rankings": rankings,
    }

    if not write_enabled():
        logger.info("[dry-run] 跳过 data.json 落盘: %s", data_path)
        return

    current[date] = value
    if len(current) > RETENTION_DAYS:
        keep = sorted(current.keys())[-RETENTION_DAYS:]
        current = {k: current[k] for k in keep}
    write_json(current, data_path)
    logger.info("[%s] %s 整合完成，%d 种排行榜", platform, date, len(rankings))
    _prune_retention(platform)


def main():
    if not write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），聚合只分析不落盘")
    target = yesterday_date()
    logger.info("开始聚合 %s 的各渠道数据", target)
    for platform in CHANNELS:
        try:
            aggregate_yesterday(platform, target)
        except Exception as e:  # noqa: BLE001
            logger.error("[%s] 聚合失败：%s", platform, e)
    logger.info("聚合完成")


if __name__ == "__main__":
    main()

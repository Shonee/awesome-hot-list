# -*- coding: utf-8 -*-
"""
文件操作公共工具库

统一本仓库所有采集脚本用到的文件路径生成与读写能力。

设计原则
--------
1. 单一路径约定：所有归档文件的路径只能通过 archive_path() 生成，
   避免各脚本各自拼字符串导致结构不一致（历史上的 B 站扁平目录即由此产生）。
2. 零第三方依赖：CSV 读写改用标准库 csv 实现，行为与原先 pandas 版本对齐
   （LF 行尾 + 字段名取并集 + 首次出现顺序），从而可以卸掉 pandas。
3. 编码显式化：所有文本读写强制 UTF-8，避免不同平台 locale 导致乱码。
4. 原子写：提供 atomic_* 系列，先写临时文件再 os.replace，
   防止采集过程中断产生半截文件。

目录约定
--------
    archived/<platform>/<YYYY>/<MM>/<json|csv|md>/<YYYY-MM-DD>.<ext>
"""

import csv
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

#: 归档根目录（相对仓库根目录，所有脚本均需在仓库根目录执行）
ARCHIVE_ROOT = "archived"

#: 支持的文件格式 -> 扩展名
FORMAT_EXT = {
    "json": "json",
    "csv": "csv",
    "md": "md",
}

#: 默认文本编码
DEFAULT_ENCODING = "utf-8"

#: JSON 落盘默认缩进（与历史文件保持一致，改动会导致全量 diff）
DEFAULT_JSON_INDENT = 4

#: CSV 行尾。历史文件由 pandas 在 Linux 上生成，使用 LF；
#: 标准库 csv 默认是 CRLF，必须显式覆盖，否则历史文件会被整片重写。
CSV_LINE_TERMINATOR = "\n"

#: 是否复现 pandas 的类型推断行为。
#:
#: 背景：历史 CSV 由 ``pandas.read_json`` + ``to_csv`` 生成。当某一列同时存在
#: 整数和缺失值（None）时，pandas 会把该列提升为 float64，导致整数被写成
#: ``1788080700.0`` 这种带小数点的形式。B 站归档的 ``createtime`` 列即属此类。
#:
#: 置为 True 时保持与历史文件逐字节一致，代价是保留了这个瑕疵；
#: 置为 False 则输出干净的原始整数，但同一列的新旧行会出现格式漂移。
#: 若要切换到 False，建议同时跑一遍历史 CSV 规范化脚本。
CSV_LEGACY_FLOAT = True


# ---------------------------------------------------------------------------
# 路径生成
# ---------------------------------------------------------------------------

def archive_path(
    platform: str,
    fmt: str = "json",
    date: Optional[str] = None,
    root: str = ARCHIVE_ROOT,
    with_year_month: bool = True,
) -> str:
    """生成统一的归档文件路径。

    :param platform: 渠道名，如 bilibili / douyin / weibo / zhihu / github
    :param fmt: 文件类型，取值为 json / csv / md
    :param date: 日期字符串 ``YYYY-MM-DD``，缺省取今天
    :param root: 归档根目录
    :param with_year_month: 是否插入 ``YYYY/MM`` 层级，固定为 True，
        保留参数仅为兼容历史调用
    :return: 形如 ``archived/douyin/2026/09/json/2026-09-01.json``

    示例::

        >>> archive_path('douyin', 'json', '2026-09-01')
        'archived/douyin/2026/09/json/2026-09-01.json'
    """
    if fmt not in FORMAT_EXT:
        raise ValueError(f"不支持的文件格式: {fmt!r}，可选值: {list(FORMAT_EXT)}")

    date = date or current_date()
    parts = [root, platform]
    if with_year_month:
        year, month = _split_ym(date)
        parts.extend([year, month])
    parts.append(fmt)
    return os.path.join(*parts, f"{date}.{FORMAT_EXT[fmt]}")


def current_date(pattern: str = "%Y-%m-%d") -> str:
    """返回当前日期字符串，默认 ``YYYY-MM-DD``。"""
    return datetime.now().strftime(pattern)


def _split_ym(date: str) -> Sequence[str]:
    """校验 ``YYYY-MM-DD`` 日期并拆出年月。"""
    parsed = datetime.strptime(str(date), "%Y-%m-%d")
    return str(parsed.year), f"{parsed.month:02d}"


# ---------------------------------------------------------------------------
# 目录
# ---------------------------------------------------------------------------

def ensure_dir(dir_path: str) -> str:
    """确保目录存在，不存在则递归创建。"""
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    return dir_path


def ensure_parent_dir(file_path: str) -> str:
    """确保文件所在目录存在，返回目录路径。"""
    return ensure_dir(os.path.dirname(file_path))


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------

def read_text(path: str, default: Optional[str] = None, encoding: str = DEFAULT_ENCODING):
    """读取文本文件，失败返回 default 而不是抛异常。"""
    try:
        with open(path, "r", encoding=encoding) as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("读取文本失败 %s: %s", path, e)
        return default


def read_csv(path: str, encoding: str = DEFAULT_ENCODING) -> List[Dict[str, Any]]:
    """读取 CSV 为字典列表，不存在返回空列表。"""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# 写入
# ---------------------------------------------------------------------------

def write_text(
    text: str,
    file_path: str,
    encoding: str = DEFAULT_ENCODING,
    atomic: bool = False,
) -> str:
    """写入纯文本 / Markdown。

    :param atomic: True 时先写临时文件再原子替换，避免中断留下半截文件
    """
    ensure_parent_dir(file_path)
    if not atomic:
        with open(file_path, "w", encoding=encoding) as f:
            f.write(text)
    else:
        _atomic_write(file_path, text, encoding=encoding)
    logger.debug("文本已保存: %s", file_path)
    return file_path


def write_json(
    data: Any,
    file_path: str,
    indent: Optional[int] = DEFAULT_JSON_INDENT,
    ensure_ascii: bool = False,
    encoding: str = DEFAULT_ENCODING,
    atomic: bool = False,
) -> str:
    """把 Python 对象序列化为 JSON 落盘。"""
    ensure_parent_dir(file_path)
    text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    if not atomic:
        with open(file_path, "w", encoding=encoding) as f:
            f.write(text)
    else:
        _atomic_write(file_path, text, encoding=encoding)
    logger.debug("JSON 已保存: %s", file_path)
    return file_path


def _collect_fieldnames(rows: Iterable[Dict[str, Any]]) -> List[str]:
    """按首次出现顺序收集所有行的字段并集。

    与 pandas.read_json 后的 to_csv 行为保持一致：
    后出现的行如果带有新字段，追加到列末尾而不是丢弃。
    """
    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    return fieldnames


def write_csv(
    rows: Union[str, Sequence[Dict[str, Any]]],
    file_path: str,
    mode: str = "append",
    fieldnames: Optional[Sequence[str]] = None,
    encoding: str = DEFAULT_ENCODING,
    atomic: bool = False,
) -> str:
    """写入 CSV。

    :param rows: 字典列表，或 JSON 字符串（历史脚本传的就是 JSON 字符串）
    :param mode: ``append`` 追加且不重复写表头；``overwrite`` 覆盖重写
    :param fieldnames: 指定列顺序，缺省按顺序取所有行字段的并集
    :param atomic: 原子写。注意：追加模式下原子写需先读旧内容，
        大文件场景下开销较高，默认关闭

    行为与历史 pandas 实现对齐：LF 行尾、最小引号、None 写空字符串。
    """
    parsed = _coerce_rows(rows)
    if not parsed:
        logger.warning("CSV 无数据，跳过写入: %s", file_path)
        return file_path

    if fieldnames is None:
        fieldnames = list(_collect_fieldnames(parsed))
        if mode == "append":
            existing_header = _read_existing_header(file_path, encoding)
            if existing_header:
                ignored = [name for name in fieldnames if name not in existing_header]
                if ignored:
                    logger.warning(
                        "CSV 已有表头，忽略新增字段 %s: %s",
                        ignored,
                        file_path,
                    )
                fieldnames = existing_header

    parsed = _legacy_coerce_rows(parsed, fieldnames)

    ensure_parent_dir(file_path)

    if atomic:
        _write_csv_atomic(parsed, file_path, fieldnames, mode, encoding)
        return file_path

    write_header = mode == "overwrite" or not _has_content(file_path)
    with open(file_path, "a" if mode == "append" else "w",
              encoding=encoding, newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator=CSV_LINE_TERMINATOR,
        )
        if write_header:
            writer.writeheader()
        for row in parsed:
            writer.writerow({k: _csv_value(row.get(k)) for k in fieldnames})
    logger.debug("CSV 已保存: %s（%d 行）", file_path, len(parsed))
    return file_path


def _coerce_rows(rows: Union[str, Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """把 JSON 字符串或可迭代对象统一转成字典列表。"""
    if isinstance(rows, str):
        try:
            parsed = json.loads(rows)
        except json.JSONDecodeError:
            import ast
            parsed = ast.literal_eval(rows)
    else:
        parsed = rows

    if isinstance(parsed, dict):
        # 允许 {"hot": [...]} 这类结构，展平为一维列表
        flat: List[Dict[str, Any]] = []
        for value in parsed.values():
            if isinstance(value, list):
                flat.extend(value)
            else:
                flat.append(value)
        return [r for r in flat if isinstance(r, dict)]

    return [r for r in parsed if isinstance(r, dict)]


def _csv_value(value: Any) -> Any:
    """CSV 单元格取值：None 写空，其余保持原样由 csv 模块序列化。"""
    return "" if value is None else value


def _legacy_coerce_rows(
    rows: List[Dict[str, Any]],
    fieldnames: Sequence[str],
    enabled: bool = CSV_LEGACY_FLOAT,
) -> List[Dict[str, Any]]:
    """复现 pandas 的 float64 提升规则。

    pandas 在 read_json 后，若某列既有整数又有缺失值，会把整列提升为 float64，
    整数因此被写成 ``1788080700.0``。这里按列统计并复现该行为，
    以保证新旧实现产出的 CSV 逐字节一致。

    :param enabled: False 时跳过，输出原始整数
    """
    if not enabled:
        return rows

    promoted = set()
    for name in fieldnames:
        has_none = False
        has_int = False
        for row in rows:
            value = row.get(name, None)
            if value is None:
                has_none = True
            elif isinstance(value, int) and not isinstance(value, bool):
                has_int = True
            if has_none and has_int:
                promoted.add(name)
                break

    if not promoted:
        return rows

    coerced = []
    for row in rows:
        new_row = dict(row)
        for name in promoted:
            value = new_row.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                new_row[name] = float(value)
        coerced.append(new_row)
    return coerced


def _has_content(path: str) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) > 0


def _read_existing_header(
    file_path: str,
    encoding: str = DEFAULT_ENCODING,
) -> Optional[List[str]]:
    """读取已有 CSV 表头，追加时固定列数，避免新字段写坏行结构。"""
    if not _has_content(path=file_path):
        return None
    try:
        with open(file_path, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            return next(reader, None)
    except (OSError, UnicodeDecodeError):
        return None


def _write_csv_atomic(rows, file_path, fieldnames, mode, encoding):
    """原子写 CSV：先在临时文件里拼出完整内容，再整体替换。"""
    import io
    old = ""
    if mode == "append" and _has_content(file_path):
        old = read_text(file_path, default="", encoding=encoding)
        if old and not old.endswith("\n"):
            old += "\n"

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator=CSV_LINE_TERMINATOR,
    )
    if not old:
        writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_value(row.get(k)) for k in fieldnames})

    _atomic_write(file_path, old + buf.getvalue(), encoding=encoding)


def _atomic_write(file_path: str, text: str, encoding: str = DEFAULT_ENCODING) -> None:
    """写临时文件后 os.replace 原子替换。"""
    ensure_parent_dir(file_path)
    directory = os.path.dirname(file_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
        os.replace(tmp_path, file_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ---------------------------------------------------------------------------
# 渠道级归档路径
#
# 当前采集链路只维护每个渠道的 CSV 时间片和最新快照说明；报告由
# `src/hotlist/report.py` 直接读取 CSV 生成，页面读取 `site/data/`。
# ---------------------------------------------------------------------------

def channel_readme_path(platform: str, root: str = ARCHIVE_ROOT) -> str:
    """返回渠道级 README.md 路径（每渠道一份，覆盖更新）。"""
    return os.path.join(root, platform, "README.md")


def yesterday_date(pattern: str = "%Y-%m-%d") -> str:
    """返回昨天的日期字符串（默认 ``YYYY-MM-DD``）。"""
    return (datetime.now() - timedelta(days=1)).strftime(pattern)

# -*- coding: utf-8 -*-
"""
文件操作公共工具库

统一本仓库所有采集脚本用到的文件路径生成、读写、校验与归档能力。

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
import hashlib
import json
import logging
import os
import shutil
import tempfile
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
    import time
    return time.strftime(pattern, time.localtime())


def current_time(pattern: str = "%Y-%m-%d %H:%M:%S") -> str:
    """返回当前时间字符串，默认 ``YYYY-MM-DD HH:MM:SS``。"""
    import time
    return time.strftime(pattern, time.localtime())


def current_year_month_day() -> Sequence[str]:
    """返回 ``(年, 月, 日)``，月日为两位补零，用于兼容旧脚本调用。"""
    from datetime import datetime
    now = datetime.now()
    return str(now.year), f"{now.month:02d}", f"{now.day:02d}"


def _split_ym(date: str) -> Sequence[str]:
    """从 ``YYYY-MM-DD`` 中拆出年月，格式异常时回退到当前日期。"""
    parts = str(date).split("-")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return parts[0], f"{int(parts[1]):02d}"
    y, m, _ = current_year_month_day()
    return y, m


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


#: 兼容旧名：历史脚本里叫 get_or_make_file_path
get_or_make_file_path = ensure_parent_dir


# ---------------------------------------------------------------------------
# 存在性与信息
# ---------------------------------------------------------------------------

def exists(path: str) -> bool:
    """判断文件或目录是否存在。"""
    return os.path.exists(path)


def is_file(path: str) -> bool:
    return os.path.isfile(path)


def file_size(path: str) -> int:
    """返回文件字节数，不存在返回 0。"""
    return os.path.getsize(path) if os.path.isfile(path) else 0


def human_size(num_bytes: int) -> str:
    """把字节数格式化为人类可读形式。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024.0
    return f"{size:.2f}PB"


def count_lines(path: str, encoding: str = DEFAULT_ENCODING) -> int:
    """统计文件行数，不存在返回 0。"""
    if not os.path.isfile(path):
        return 0
    with open(path, "r", encoding=encoding, errors="ignore") as f:
        return sum(1 for _ in f)


def list_files(
    dir_path: str,
    pattern: Optional[str] = None,
    recursive: bool = True,
    sort: bool = True,
) -> List[str]:
    """列出目录下的文件。

    :param pattern: 后缀过滤，如 ``.json`` 或 ``json``
    :param recursive: 是否递归子目录
    :param sort: 是否按路径排序，保证归档顺序稳定
    """
    import fnmatch

    if not os.path.isdir(dir_path):
        return []

    results: List[str] = []
    if recursive:
        for root, _dirs, files in os.walk(dir_path):
            for name in files:
                results.append(os.path.join(root, name))
    else:
        results = [
            os.path.join(dir_path, name)
            for name in os.listdir(dir_path)
            if os.path.isfile(os.path.join(dir_path, name))
        ]

    if pattern:
        suffix = pattern if pattern.startswith(".") else f".{pattern}"
        results = [p for p in results if fnmatch.fnmatch(p, f"*{suffix}")]

    return sorted(results) if sort else results


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


def read_json(path: str, default: Optional[Any] = None, encoding: str = DEFAULT_ENCODING):
    """读取 JSON 文件，文件不存在或内容损坏时返回 default。"""
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding=encoding) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取 JSON 失败 %s: %s", path, e)
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


#: 兼容旧名的文本保存函数
saveText = write_text


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


saveJson = write_json


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
        merged = list(_collect_fieldnames(parsed))
        if mode == "append":
            merged = _merge_with_existing_header(file_path, merged, encoding)
        fieldnames = merged

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


#: 兼容旧名的 CSV 保存函数（历史语义即追加）
saveCsv = write_csv


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


def _merge_with_existing_header(
    file_path: str,
    fieldnames: List[str],
    encoding: str = DEFAULT_ENCODING,
) -> List[str]:
    """追加模式下，把已有文件的表头合并进来，保证列不丢。"""
    if not _has_content(path=file_path):
        return fieldnames
    try:
        with open(file_path, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
    except (OSError, UnicodeDecodeError):
        return fieldnames
    if not header:
        return fieldnames
    merged = list(header)
    for name in fieldnames:
        if name not in merged:
            merged.append(name)
    return merged


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


def append_json_timeslice(
    file_path: str,
    key: str,
    value: Any,
    encoding: str = DEFAULT_ENCODING,
    atomic: bool = True,
) -> str:
    """按“时间片键 -> 数据”追加写入 JSON。

    这是本仓库的核心落盘模式：同一天的每个采集时刻作为一个 key，
    追加进当天的 JSON 文件。

    :param file_path: 目标 JSON 路径
    :param key: 时间片键，通常是 ``NOW_TIME``
    :param value: 该时间片采集到的数据
    :param atomic: 默认开启，避免并发写入损坏当天文件
    """
    data = read_json(file_path, default={}, encoding=encoding)
    if not isinstance(data, dict):
        logger.warning("JSON 结构异常，已重置为空字典: %s", file_path)
        data = {}
    data[key] = value
    return write_json(data, file_path, encoding=encoding, atomic=atomic)


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
    """计算文件的 SHA-256，逐块读取以适配大文件。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: Union[str, bytes]) -> str:
    """计算文本或字节串的 SHA-256。"""
    data = text.encode(DEFAULT_ENCODING) if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def verify_file(path: str, expected_sha256: str) -> bool:
    """校验文件 SHA-256 是否匹配。"""
    return os.path.isfile(path) and sha256_file(path) == expected_sha256


def write_manifest(
    files: Iterable[str],
    out_path: str,
    root: str = "",
    encoding: str = DEFAULT_ENCODING,
) -> str:
    """生成文件清单（含 SHA-256），供月度归档做完整性校验。

    输出格式为 JSON 数组，每项含 path / bytes / sha256。
    """
    entries = []
    for path in files:
        entries.append({
            "path": os.path.relpath(path, root) if root else path,
            "bytes": file_size(path),
            "sha256": sha256_file(path),
        })
    return write_json(entries, out_path, encoding=encoding)


def verify_manifest(manifest_path: str, root: str = "") -> List[str]:
    """按清单逐项校验，返回校验失败的文件相对路径列表。"""
    entries = read_json(manifest_path, default=[])
    failed = []
    for entry in entries:
        rel = entry.get("path", "")
        target = os.path.join(root, rel) if root else rel
        if not verify_file(target, entry.get("sha256", "")):
            failed.append(rel)
    return failed


# ---------------------------------------------------------------------------
# 通用文件操作
# ---------------------------------------------------------------------------

def copy(src: str, dst: str, overwrite: bool = True) -> str:
    """复制文件或目录。"""
    ensure_parent_dir(dst)
    if os.path.isdir(src):
        if overwrite and os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, dirs_exist_ok=not overwrite)
    else:
        if overwrite or not os.path.exists(dst):
            shutil.copy2(src, dst)
    return dst


def move(src: str, dst: str) -> str:
    """移动文件或目录，自动创建目标父目录。"""
    ensure_parent_dir(dst)
    shutil.move(src, dst)
    return dst


def remove(path: str, missing_ok: bool = True) -> bool:
    """删除文件或目录，返回是否真的删除了东西。"""
    if os.path.isdir(path):
        shutil.rmtree(path)
        return True
    if os.path.isfile(path):
        os.remove(path)
        return True
    if not missing_ok:
        raise FileNotFoundError(path)
    return False


def touch(path: str) -> str:
    """创建空文件（若已存在则仅更新访问/修改时间）。"""
    ensure_parent_dir(path)
    with open(path, "a", encoding=DEFAULT_ENCODING):
        os.utime(path, None)
    return path


def make_archive(src_dir: str, out_path: str, fmt: str = "tar.gz") -> str:
    """把目录打包为归档文件。

    :param fmt: tar.gz / tgz / tar / zip / tar.bz2 / tar.xz（也接受 shutil
        内部的 gztar / bztar / xztar 写法）
    :return: 生成的归档文件路径（含扩展名）

    实现说明：
    不使用 ``shutil.make_archive``，因为它会把根目录自身（``.``）也打进归档，
    解压时 ``os.mkdir`` 撞上已存在的目标目录会抛 EEXIST，导致解压必然失败。
    这里直接调用 tarfile / zipfile，只打包目录内容，并按名称排序，
    保证同样的输入产出同样的字节，便于月度归档做哈希校验。
    """
    out_path = os.path.abspath(out_path)
    ensure_parent_dir(out_path)

    if not os.path.isdir(src_dir):
        raise NotADirectoryError(src_dir)

    fmt = (fmt or "tar.gz").lstrip(".").lower()
    fmt_map = {
        "tar.gz": ("gztar", ".tar.gz"), "tgz": ("gztar", ".tar.gz"),
        "gztar": ("gztar", ".tar.gz"),
        "tar.bz2": ("bztar", ".tar.bz2"), "bz2": ("bztar", ".tar.bz2"),
        "bztar": ("bztar", ".tar.bz2"),
        "tar.xz": ("xztar", ".tar.xz"), "xz": ("xztar", ".tar.xz"),
        "xztar": ("xztar", ".tar.xz"),
        "tar": ("tar", ".tar"), "zip": ("zip", ".zip"),
    }
    if fmt not in fmt_map:
        raise ValueError(f"不支持的打包格式: {fmt!r}，可选值: {sorted(fmt_map)}")
    shutil_fmt, suffix = fmt_map[fmt]

    base = out_path
    for candidate in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz", ".tar", ".zip"):
        if base.endswith(candidate):
            base = base[: -len(candidate)]
            break
    target = base + suffix

    if shutil_fmt == "zip":
        import zipfile
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(os.listdir(src_dir)):
                _zip_add_normalized(zf, os.path.join(src_dir, name), name)
    else:
        import gzip
        import tarfile
        with open(target, "wb") as raw:
            # gzip 头部自带一个 mtime 字段，不置零同样会破坏可复现性
            if shutil_fmt == "gztar":
                stream = gzip.GzipFile(filename="", mode="wb",
                                       fileobj=raw, mtime=ARCHIVE_FIXED_MTIME)
            elif shutil_fmt == "bztar":
                import bz2
                stream = bz2.BZ2File(raw, "wb")
            elif shutil_fmt == "xztar":
                import lzma
                stream = lzma.LZMAFile(raw, "wb")
            else:
                stream = raw
            try:
                with tarfile.open(fileobj=stream, mode="w") as tar:
                    for name in sorted(os.listdir(src_dir)):
                        _add_normalized(tar, os.path.join(src_dir, name), name)
            finally:
                if stream is not raw:
                    stream.close()

    logger.debug("已打包 %s -> %s", src_dir, target)
    return target


#: 归档内统一使用的时间戳（1980-01-01），抹掉实际 mtime 以保证可复现
ARCHIVE_FIXED_MTIME = 315532800


#: zip 内统一使用的时间戳，同样是为了可复现（zip 不支持 1970 年之前的日期）
ZIP_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def _zip_add_normalized(zf, full_path: str, arcname: str) -> None:
    """把文件/目录加入 zip 并抹平 mtime。

    ``zf.write`` 会写入真实 mtime 与系统相关的权限位，导致同样内容
    两次打包字节不同。这里手动构造 ZipInfo 以固定这些字段。
    """
    import zipfile

    if os.path.isdir(full_path):
        info = zipfile.ZipInfo(arcname.rstrip("/") + "/", date_time=ZIP_FIXED_DATE_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o40755 << 16) | 0x10
        zf.writestr(info, b"")
        for name in sorted(os.listdir(full_path)):
            _zip_add_normalized(
                zf,
                os.path.join(full_path, name),
                f"{arcname.rstrip('/')}/{name}",
            )
        return

    info = zipfile.ZipInfo(arcname, date_time=ZIP_FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with open(full_path, "rb") as f:
        zf.writestr(info, f.read())


def _add_normalized(tar, full_path: str, arcname: str) -> None:
    """把文件/目录加入 tar，并抹平 mtime、属主等易变元数据。

    直接 ``tar.add`` 会写入真实 mtime 与 uid/gid，导致同样内容两次打包
    字节不同。这里改用 gettarinfo + addfile 逐项重置，使归档可复现。
    """
    info = tar.gettarinfo(full_path, arcname=arcname)
    info.mtime = ARCHIVE_FIXED_MTIME
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""

    if info.isreg():
        with open(full_path, "rb") as f:
            tar.addfile(info, f)
    else:
        tar.addfile(info)
        if info.isdir():
            for name in sorted(os.listdir(full_path)):
                _add_normalized(
                    tar,
                    os.path.join(full_path, name),
                    os.path.join(arcname, name),
                )


def extract_archive(archive_path: str, dest_dir: str) -> str:
    """解压归档文件到目标目录。"""
    ensure_dir(dest_dir)
    shutil.unpack_archive(archive_path, dest_dir)
    return dest_dir


def dir_size(dir_path: str) -> int:
    """统计目录总字节数。"""
    total = 0
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            fp = os.path.join(root, name)
            if not os.path.islink(fp):
                total += file_size(fp)
    return total


def month_dir(platform: str, year: Union[int, str], month: Union[int, str],
              root: str = ARCHIVE_ROOT) -> str:
    """返回某渠道某年月的归档目录，如 ``archived/douyin/2026/09``。"""
    return os.path.join(root, platform, str(year), f"{int(month):02d}")


# ---------------------------------------------------------------------------
# 渠道级聚合产物路径（优化后的归档格式）
#
# 归档格式优化后：
#   - md 不再每天一个文件，而是每渠道一份 `archived/<platform>/README.md`，
#     每天用最新快照覆盖式更新；
#   - json 不再按时间片写 `json/<date>.json`，而是每天由聚合任务整合昨天
#     csv，产出 `archived/<platform>/data.json`（按日期滚动 7 天）；
#   - 动图（可选）放在 `archived/<platform>/gif/` 下，按日期滚动。
# 这些路径一律由下方函数生成，避免脚本各自拼字符串。
# ---------------------------------------------------------------------------

def channel_readme_path(platform: str, root: str = ARCHIVE_ROOT) -> str:
    """返回渠道级 README.md 路径（每渠道一份，覆盖更新）。"""
    return os.path.join(root, platform, "README.md")


def data_json_path(platform: str, root: str = ARCHIVE_ROOT) -> str:
    """返回渠道级整合数据路径 ``archived/<platform>/data.json``。"""
    return os.path.join(root, platform, "data.json")


def gif_dir(platform: str, root: str = ARCHIVE_ROOT) -> str:
    """返回渠道级动图目录 ``archived/<platform>/gif/``。"""
    return os.path.join(root, platform, "gif")


def yesterday_date(pattern: str = "%Y-%m-%d") -> str:
    """返回昨天的日期字符串（默认 ``YYYY-MM-DD``）。"""
    from datetime import timedelta
    return (current_datetime() - timedelta(days=1)).strftime(pattern)


def current_datetime():
    """返回当前 datetime 对象（兼容旧调用，避免重复 import）。"""
    from datetime import datetime
    return datetime.now()

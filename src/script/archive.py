#!/usr/bin/env python3
"""Build, verify, and clean the seven-day rolling archive.

The workflow deliberately keeps the release protocol outside the collector:
this module only creates deterministic assets and removes files after a caller
has verified that the same assets exist remotely.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DATE_FILE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\.(csv|json)$")
REPORT_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_commit(root: Path) -> str:
    if not (root / ".git").exists():
        return "unknown"
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _dated_files(root: Path, include_legacy: bool = False) -> Iterable[tuple[Path, dt.date | None]]:
    archived = root / "archived"
    if archived.is_dir():
        for path in sorted(archived.rglob("*")):
            if not path.is_file():
                continue
            match = DATE_FILE.fullmatch(path.name)
            if match:
                file_date = dt.date.fromisoformat(match.group("date"))
                if path.suffix == ".csv":
                    yield path, file_date
                elif include_legacy:
                    yield path, file_date
            elif include_legacy and path.name != "README.md":
                # Channel README files are still part of the current public
                # archive index; old JSON/Markdown/GIF/data.json files are not.
                yield path, None

    reports = root / "site" / "data" / "reports"
    if reports.is_dir():
        for path in sorted(reports.iterdir()):
            if not path.is_file() or not REPORT_FILE.fullmatch(path.name):
                continue
            yield path, dt.date.fromisoformat(path.stem)


def _tar_info(path: Path, name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = path.stat().st_size
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info


def _json_member(tar: tarfile.TarFile, name: str, payload: object) -> None:
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    tar.addfile(info, io.BytesIO(content))


def _write_deterministic_archive(output: Path, root: Path, manifest: dict) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for entry in manifest["files"]:
                    source = root / entry["path"]
                    info = _tar_info(source, entry["path"])
                    with source.open("rb") as handle:
                        tar.addfile(info, handle)
                _json_member(tar, "META/manifest.json", manifest)


def prepare(
    root: Path = ROOT,
    output_dir: Path | None = None,
    today: dt.date | None = None,
    retention_days: int = 7,
    include_legacy: bool = False,
) -> dict:
    """Package old data, optionally including one-time legacy archive files."""
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    root = root.resolve()
    output_dir = (output_dir or root / ".archive-work").resolve()
    today = today or dt.datetime.now().date()
    cutoff = today - dt.timedelta(days=retention_days - 1)
    selected = []
    for path, file_date in _dated_files(root, include_legacy=include_legacy):
        if file_date is None or file_date < cutoff:
            relative = path.relative_to(root).as_posix()
            selected.append(
                {
                    "path": relative,
                    "date": file_date.isoformat() if file_date else None,
                    "legacy": file_date is None or path.suffix != ".csv",
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    archive_id = (
        f"hotlist-archive-migration-{today.isoformat()}"
        if include_legacy
        else f"hotlist-archive-through-{(cutoff - dt.timedelta(days=1)).isoformat()}"
    )
    result = {
        "schemaVersion": 1,
        "archiveId": archive_id,
        "retentionDays": retention_days,
        "timezone": "Asia/Shanghai",
        "today": today.isoformat(),
        "cutoffDate": cutoff.isoformat(),
        "endDate": (cutoff - dt.timedelta(days=1)).isoformat(),
        "includeLegacy": include_legacy,
        "hasFiles": bool(selected),
        "files": sorted(selected, key=lambda item: item["path"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    if not selected:
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    result["sourceCommit"] = _source_commit(root)
    manifest_path = output_dir / f"{archive_id}.manifest.json"
    archive_path = output_dir / f"{archive_id}.tar.gz"
    sums_path = output_dir / f"{archive_id}.SHA256SUMS"
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_deterministic_archive(archive_path, root, result)
    sums_path.write_text(
        f"{sha256(archive_path)}  {archive_path.name}\n"
        f"{sha256(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    result["assets"] = [archive_path.name, manifest_path.name, sums_path.name]
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _safe_member(name: str) -> bool:
    pure = PurePosixPath(name)
    return not pure.is_absolute() and ".." not in pure.parts and bool(pure.parts)


def verify(root: Path = ROOT, output_dir: Path | None = None) -> dict:
    """Verify local assets and every archived file checksum before publishing."""
    root = root.resolve()
    output_dir = (output_dir or root / ".archive-work").resolve()
    result = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    if not result.get("hasFiles"):
        return result
    manifest = result
    archive_path = output_dir / result["assets"][0]
    manifest_path = output_dir / result["assets"][1]
    sums_path = output_dir / result["assets"][2]
    sums = sums_path.read_text(encoding="utf-8").splitlines()
    expected_sums = {
        parts[1]: parts[0]
        for line in sums
        if len(parts := line.split()) == 2
    }
    for path in (archive_path, manifest_path):
        if expected_sums.get(path.name) != sha256(path):
            raise RuntimeError(f"checksum mismatch: {path.name}")

    expected = {entry["path"]: entry for entry in manifest["files"]}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        if "META/manifest.json" not in names or set(expected) - names:
            raise RuntimeError("archive is missing manifest or data files")
        for member in members:
            if not _safe_member(member.name):
                raise RuntimeError(f"unsafe archive member: {member.name}")
            if member.name == "META/manifest.json":
                handle = archive.extractfile(member)
                if handle is None:
                    raise RuntimeError("cannot read archive manifest")
                embedded = json.load(handle)
                expected_manifest = dict(manifest)
                expected_manifest.pop("assets", None)
                if embedded != expected_manifest:
                    raise RuntimeError("embedded archive manifest differs from release manifest")
                continue
            if member.name not in expected or not member.isfile():
                raise RuntimeError(f"unexpected archive member: {member.name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise RuntimeError(f"cannot read archive member: {member.name}")
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != expected[member.name]["sha256"]:
                raise RuntimeError(f"archived file checksum mismatch: {member.name}")
    return result


def clean(root: Path = ROOT, output_dir: Path | None = None) -> int:
    """Delete only files listed by the already verified local manifest."""
    root = root.resolve()
    output_dir = (output_dir or root / ".archive-work").resolve()
    result = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    if not result.get("hasFiles"):
        return 0
    removed = 0
    for entry in result["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe deletion path: {relative}")
        if relative.parts[0] not in {"archived", "site"}:
            raise RuntimeError(f"unexpected deletion root: {relative}")
        if relative.parts[0] == "site" and relative.parts[:3] != ("site", "data", "reports"):
            raise RuntimeError(f"unexpected site deletion path: {relative}")
        target = root / relative
        if not target.is_file() or sha256(target) != entry["sha256"]:
            raise RuntimeError(f"file changed after verification: {relative}")
        target.unlink()
        removed += 1
        parent = target.parent
        while parent != root and parent.name not in {"archived", "reports"} and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify the rolling seven-day archive")
    parser.add_argument("command", choices=("prepare", "verify", "clean"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--today", help="YYYY-MM-DD, useful for deterministic local checks")
    parser.add_argument("--retention-days", type=int, default=7)
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="一次性纳入旧 JSON/Markdown/GIF/data.json 等非规范归档文件",
    )
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today) if args.today else None
    if args.command == "prepare":
        result = prepare(args.root, args.output_dir, today, args.retention_days, args.include_legacy)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif args.command == "verify":
        result = verify(args.root, args.output_dir)
        print(json.dumps({"verified": True, "hasFiles": result.get("hasFiles", False)}, ensure_ascii=False))
    else:
        print(json.dumps({"removed": clean(args.root, args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

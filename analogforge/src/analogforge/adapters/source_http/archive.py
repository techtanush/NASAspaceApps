"""Hardened ZIP extraction for provider archives."""

from __future__ import annotations

import shutil
import stat
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from analogforge.adapters.source_http.errors import AdapterError

_NESTED_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".z"}
_ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06")
_COPY_CHUNK = 1 << 16


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 64
    max_total_bytes: int = 1024 * 1024 * 1024
    max_expansion_ratio: float = 20.0
    allowed_suffixes: frozenset[str] | None = None  # lower-case with dot; None = any non-nested file
    # Declared member sizes (bytes) of fixed-format rasters whose size is known exactly in advance.  A member of
    # exactly one of these sizes is exempt from the ratio cap (a legitimate constant raster compresses ~1000:1) but
    # still counts toward ``max_total_bytes`` and can never expand past its declared size while copying.
    exempt_member_sizes: frozenset[int] = frozenset()


def _bad(message: str, detail: str) -> AdapterError:
    return AdapterError("SOURCE_CONTENT_INVALID", message, detail_code=detail)


def safe_extract_zip(
    archive: Path, dest_dir: Path, limits: ArchiveLimits | None = None, *, extract: bool = True
) -> list[Path]:
    """Extract ``archive`` into the empty-or-new ``dest_dir``; return members sorted by name.

    Rejected: absolute paths, ``..`` components, backslash paths, symlinks / device files, nested archives,
    duplicate or unexpected members, more than ``max_members`` members, and total uncompressed size above
    ``max_total_bytes`` or above ``max_expansion_ratio`` times the archive size (members whose declared size is one
    of ``exempt_member_sizes`` are measured outside the ratio, see :class:`ArchiveLimits`), and a member name used
    both as a file and as a directory. Sizes are enforced while
    copying so a lying central directory cannot defeat the limits. With ``extract=False`` every check runs
    (members are streamed and discarded, so CRCs are verified) but nothing is written.
    """
    lim = limits or ArchiveLimits()
    dest_root = dest_dir.resolve()
    try:
        with archive.open("rb") as handle:
            magic = handle.read(4)
        if not magic.startswith(_ZIP_MAGICS):
            raise _bad("file is not a ZIP archive", "BAD_ARCHIVE")
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        raise _bad("archive is corrupt or unreadable", "BAD_ARCHIVE") from exc
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > lim.max_members:
            raise AdapterError(
                "RESOURCE_LIMIT",
                f"archive has {len(infos)} members (limit {lim.max_members})",
                detail_code="ARCHIVE_MEMBER_LIMIT",
            )
        archive_size = max(archive.stat().st_size, 1)
        declared = sum(i.file_size for i in infos)
        exempt = sum(i.file_size for i in infos if i.file_size in lim.exempt_member_sizes)
        budget = min(lim.max_total_bytes, int(lim.max_expansion_ratio * archive_size) + exempt)
        if declared > budget:
            raise AdapterError(
                "RESOURCE_LIMIT",
                f"archive would expand to {declared} bytes (limit {budget}; ratio cap {lim.max_expansion_ratio:g}x)",
                detail_code="ARCHIVE_EXPANSION_LIMIT",
            )
        seen: set[str] = set()
        targets: list[tuple[zipfile.ZipInfo, Path]] = []
        for info in infos:
            name = info.filename
            if "\\" in name or name.startswith("/") or (len(name) > 1 and name[1] == ":"):
                raise _bad(f"unsafe member path {name!r}", "ARCHIVE_PATH_TRAVERSAL")
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts:
                raise _bad(f"unsafe member path {name!r}", "ARCHIVE_PATH_TRAVERSAL")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise _bad(f"symbolic link member {name!r}", "ARCHIVE_SYMLINK")
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise _bad(f"special file member {name!r}", "ARCHIVE_SPECIAL_FILE")
            suffix = pure.suffix.lower()
            if suffix in _NESTED_SUFFIXES:
                raise _bad(f"nested archive member {name!r}", "ARCHIVE_NESTED")
            if lim.allowed_suffixes is not None and suffix not in lim.allowed_suffixes:
                raise _bad(f"unexpected member {name!r}", "ARCHIVE_UNEXPECTED_MEMBER")
            key = pure.as_posix().lower()
            if key in seen:
                raise _bad(f"duplicate member {name!r}", "ARCHIVE_DUPLICATE_MEMBER")
            seen.add(key)
            target = (dest_root / pure).resolve()
            if dest_root != target and dest_root not in target.parents:
                raise _bad(f"member escapes destination {name!r}", "ARCHIVE_PATH_TRAVERSAL")
            targets.append((info, target))
        for key in seen:  # "x.hgt" and "x.hgt/y.hgt" cannot both be extracted
            parent = PurePosixPath(key).parent
            while parent.parts:
                if parent.as_posix() in seen:
                    raise _bad(
                        f"member {key!r} is inside the file member {parent.as_posix()!r}", "ARCHIVE_DUPLICATE_MEMBER"
                    )
                parent = parent.parent
        dest_existed = dest_root.exists()
        if extract:
            dest_root.mkdir(parents=True, exist_ok=True)
        written = 0
        out: list[Path] = []
        created: list[Path] = []
        try:
            for info, target in sorted(targets, key=lambda t: t[0].filename):
                if extract:
                    target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src:
                    dst = target.open("wb") if extract else None
                    if extract:
                        created.append(target)
                    try:
                        while chunk := src.read(_COPY_CHUNK):
                            written += len(chunk)
                            if written > budget:
                                raise AdapterError(
                                    "RESOURCE_LIMIT",
                                    "archive expansion exceeded limit while extracting",
                                    detail_code="ARCHIVE_EXPANSION_LIMIT",
                                )
                            if dst is not None:
                                dst.write(chunk)
                    finally:
                        if dst is not None:
                            dst.close()
                out.append(target)
        except BaseException as exc:
            if extract:  # a partial extraction never survives
                if dest_existed:
                    for path in created:
                        path.unlink(missing_ok=True)
                else:
                    shutil.rmtree(dest_root, ignore_errors=True)
            if isinstance(
                exc, (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError)
            ):  # incl. unsupported compression
                raise _bad("archive member is corrupt", "BAD_ARCHIVE") from exc
            if isinstance(exc, OSError):
                raise _bad(f"cannot write archive member: {type(exc).__name__}", "ARCHIVE_WRITE_FAILED") from exc
            raise
        return out

"""Tar archive helpers for Docker container file I/O."""

from __future__ import annotations

import io
import os
import tarfile
from collections.abc import Iterable


def create_tar(file_path: str, content: str) -> io.BytesIO:
    """Create a tar archive containing a single file."""
    data = content.encode("utf-8")
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        info = tarfile.TarInfo(name=os.path.basename(file_path))
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    tar_stream.seek(0)
    return tar_stream


def extract_file(archive_chunks: Iterable[bytes]) -> str:
    """Extract a single file's content from a Docker get_archive response."""
    stream = io.BytesIO(b"".join(archive_chunks))
    with tarfile.open(fileobj=stream) as tar:
        member = tar.getmembers()[0]
        extracted = tar.extractfile(member)
        if extracted is None:
            msg = f"Cannot extract {member.name}: not a regular file"
            raise ValueError(msg)
        return extracted.read().decode("utf-8", errors="replace")

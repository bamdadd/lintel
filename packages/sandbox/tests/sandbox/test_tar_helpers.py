"""Tests for tar archive helpers."""

from __future__ import annotations

import io
import tarfile

from lintel.sandbox._tar_helpers import create_tar, extract_file


class TestCreateTarAndExtractFile:
    def test_roundtrip_simple(self) -> None:
        content = "hello world"
        tar_bytes = create_tar("/workspace/test.py", content)
        chunks = [tar_bytes.read()]
        assert extract_file(chunks) == content

    def test_roundtrip_unicode(self) -> None:
        content = "hello \u2603 snowman \U0001f600 emoji"
        tar_bytes = create_tar("/workspace/uni.txt", content)
        chunks = [tar_bytes.read()]
        assert extract_file(chunks) == content

    def test_roundtrip_multiline(self) -> None:
        content = "line1\nline2\nline3\n"
        tar_bytes = create_tar("/some/path/file.txt", content)
        chunks = [tar_bytes.read()]
        assert extract_file(chunks) == content

    def test_roundtrip_empty(self) -> None:
        tar_bytes = create_tar("/workspace/empty.txt", "")
        chunks = [tar_bytes.read()]
        assert extract_file(chunks) == ""

    def test_uses_basename_in_tar(self) -> None:
        tar_bytes = create_tar("/a/b/c/deep.py", "x")
        tar_bytes.seek(0)
        with tarfile.open(fileobj=tar_bytes) as tar:
            names = tar.getnames()
        assert names == ["deep.py"]

    def test_multiple_chunks(self) -> None:
        content = "chunked content"
        tar_bytes = create_tar("/workspace/f.txt", content)
        data = tar_bytes.read()
        mid = len(data) // 2
        chunks = [data[:mid], data[mid:]]
        assert extract_file(chunks) == content

    def test_extract_directory_raises(self) -> None:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name="somedir")
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        buf.seek(0)
        import pytest

        with pytest.raises(ValueError, match="not a regular file"):
            extract_file([buf.read()])

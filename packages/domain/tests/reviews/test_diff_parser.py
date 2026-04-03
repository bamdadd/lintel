"""Tests for the unified diff parser."""

from __future__ import annotations

from lintel.domain.reviews.diff_parser import parse_diff

SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,4 +1,5 @@
 import os
+import sys

 def main():
-    print("hello")
+    print("hello world")
diff --git a/tests/test_main.py b/tests/test_main.py
new file mode 100644
--- /dev/null
+++ b/tests/test_main.py
@@ -0,0 +1,3 @@
+def test_main():
+    assert True
+    pass
"""


class TestParseDiff:
    def test_parses_two_files(self) -> None:
        files = parse_diff(SAMPLE_DIFF)
        assert len(files) == 2
        assert files[0].path == "src/main.py"
        assert files[1].path == "tests/test_main.py"

    def test_first_file_hunks(self) -> None:
        files = parse_diff(SAMPLE_DIFF)
        f = files[0]
        assert len(f.hunks) == 1
        assert f.hunks[0].old_start == 1
        assert f.hunks[0].new_start == 1

    def test_added_lines(self) -> None:
        files = parse_diff(SAMPLE_DIFF)
        f = files[0]
        # line 2 is "+import sys", line 5 is '+    print("hello world")'
        assert 2 in f.added_lines
        assert 5 in f.added_lines

    def test_removed_lines(self) -> None:
        files = parse_diff(SAMPLE_DIFF)
        f = files[0]
        # line 4 old is '-    print("hello")'
        assert 4 in f.removed_lines

    def test_new_file_all_added(self) -> None:
        files = parse_diff(SAMPLE_DIFF)
        f = files[1]
        assert len(f.added_lines) == 3
        assert f.removed_lines == ()

    def test_empty_diff(self) -> None:
        files = parse_diff("")
        assert files == []

    def test_diff_with_no_changes(self) -> None:
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n"
        files = parse_diff(diff)
        assert len(files) == 1
        assert files[0].added_lines == ()
        assert files[0].removed_lines == ()

    def test_multiple_hunks(self) -> None:
        diff = """\
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
-old1
+new1
 same
 same
@@ -10,3 +10,3 @@
-old2
+new2
 same
 same
"""
        files = parse_diff(diff)
        assert len(files) == 1
        assert len(files[0].hunks) == 2
        assert 1 in files[0].added_lines
        assert 10 in files[0].added_lines

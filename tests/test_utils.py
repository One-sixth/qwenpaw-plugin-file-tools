"""测试工具函数。"""

import os

from utils import (
    detect_encoding,
    format_csv,
    format_error,
    guess_file_type,
    make_result,
    normalize_newlines,
    read_file_content,
    read_file_lines,
    resolve_path,
    truncate_line,
)


class TestResolvePath:
    def test_absolute_path(self):
        path = resolve_path("C:/Windows/System32", None)
        assert path == "C:\\Windows\\System32"

    def test_relative_with_workspace(self):
        path = resolve_path("data/file.txt", "C:/project")
        assert path == "C:\\project\\data\\file.txt"

    def test_relative_without_workspace(self):
        path = resolve_path("file.txt")
        assert path.endswith("file.txt")
        assert os.path.isabs(path)

    def test_expand_user(self):
        path = resolve_path("~/test.txt")
        assert "~" not in path
        assert path.endswith("test.txt")
        assert os.path.isabs(path)


class TestDetectEncoding:
    def test_detect_utf8(self, tmp_file):
        enc = detect_encoding(tmp_file, "auto")
        assert enc.lower() in ("utf-8", "ascii")

    def test_detect_gbk(self, gbk_file):
        enc = detect_encoding(gbk_file, "auto")
        assert enc.lower() in ("gbk", "gb2312", "gb18030", "utf-8")

    def test_explicit_encoding(self, tmp_file):
        enc = detect_encoding(tmp_file, "utf-8")
        assert enc == "utf-8"


class TestNormalizeNewlines:
    def test_no_change(self):
        assert normalize_newlines("hello\nworld") == "hello\nworld"

    def test_crlf_to_lf(self):
        assert normalize_newlines("hello\r\nworld") == "hello\nworld"

    def test_cr_to_lf(self):
        assert normalize_newlines("hello\rworld") == "hello\nworld"

    def test_mixed(self):
        assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


class TestTruncateLine:
    def test_short_line(self):
        assert truncate_line("hello", 160) == "hello"

    def test_long_line(self):
        long = "x" * 200
        result = truncate_line(long, 160)
        assert len(result) == 160 + len("<<truncated>>")
        assert "<<truncated>>" in result

    def test_exact_boundary(self):
        s = "x" * 160
        assert truncate_line(s, 160) == s

    def test_one_over(self):
        s = "x" * 161
        result = truncate_line(s, 160)
        assert "<<truncated>>" in result


class TestFormatCsv:
    def test_empty_rows(self):
        result = format_csv([], fieldnames=["a", "b"])
        assert "a,b" in result

    def test_simple(self):
        rows = [{"name": "alice", "age": 30}]
        result = format_csv(rows, fieldnames=["name", "age"])
        assert "alice" in result
        assert "30" in result

    def test_special_chars(self):
        rows = [{"name": 'a,b"c', "value": 1}]
        result = format_csv(rows, fieldnames=["name", "value"])
        assert '"a,b""c"' in result

    def test_max_chars(self):
        long = "x" * 2000
        rows = [{"content": long}]
        result = format_csv(rows, fieldnames=["content"], max_chars=100)
        assert "<<truncated>>" in result

    def test_field_truncation(self):
        very_long = "x" * 5000
        rows = [{"data": very_long}]
        result = format_csv(rows, fieldnames=["data"])
        assert "<<truncated>>" in result


class TestMakeResult:
    def test_short_text(self):
        assert make_result("hello", 100) == "hello"

    def test_truncated(self):
        result = make_result("x" * 5000, 100)
        assert "<<truncated>>" in result
        assert len(result) <= 100 + len("\n<<truncated>>")


class TestFormatError:
    def test_basic(self):
        msg = format_error("复制", "文件不存在", "请确认路径。")
        assert "复制失败" in msg
        assert "因为" in msg
        assert "请确认路径" in msg

    def test_no_suggestion(self):
        msg = format_error("删除", "权限不足")
        assert "删除失败" in msg
        assert "权限不足" in msg


class TestGuessFileType:
    def test_text_file(self, tmp_file):
        result = guess_file_type(tmp_file)
        assert result["type"] == "text"
        assert result["encoding"] is not None

    def test_nonexistent(self):
        result = guess_file_type("/nonexistent/file.txt")
        assert result["type"] == "unknown"


class TestReadFileLines:
    def test_utf8(self, tmp_file):
        lines, enc = read_file_lines(tmp_file)
        assert len(lines) == 6
        assert lines[0] == "line1"
        assert lines[4] == "line5"
        assert lines[5] == ""
        assert enc.lower() in ("utf-8", "ascii")

    def test_gbk(self, gbk_file):
        lines, enc = read_file_lines(gbk_file)
        assert len(lines) == 4
        assert "你好世界" in lines[0]
        assert lines[3] == ""
        assert enc.lower() in ("gbk", "gb2312", "gb18030", "utf-8")

    def test_crlf(self, crlf_file):
        lines, _ = read_file_lines(crlf_file)
        assert len(lines) == 4
        assert lines[0] == "line1"
        assert lines[2] == "line3"
        assert lines[3] == ""
        assert "\r" not in lines[0]

    def test_empty_file(self, empty_file):
        lines, _ = read_file_lines(empty_file)
        assert lines == [""] or lines == []


class TestReadFileContent:
    def test_utf8(self, tmp_file):
        content, enc = read_file_content(tmp_file)
        assert "line1" in content
        assert enc.lower() in ("utf-8", "ascii")

    def test_gbk(self, gbk_file):
        content, enc = read_file_content(gbk_file)
        assert "你好世界" in content

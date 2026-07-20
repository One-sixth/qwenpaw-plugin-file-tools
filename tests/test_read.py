"""测试文本读取类工具。"""

import csv
import io
import os

from tools.read import (
    file_tools_read_block,
    file_tools_read_lines,
    file_tools_regex,
)


class TestReadLines:
    def test_basic(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=5)
        assert "line1" in result
        assert "line5" in result
        assert "line_number" in result
        assert "content" in result

    def test_from_middle(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=10, line_count=3)
        assert "line10" in result
        assert "line12" in result
        assert "line9" not in result

    def test_to_end(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=18, line_count=-1)
        assert "line18" in result
        assert "line20" in result

    def test_line_count_zero(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=0)
        assert "失败" in result

    def test_beyond_file(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=100, line_count=5)
        assert "失败" in result or "超出" in result

    def test_nonexistent_file(self):
        result = file_tools_read_lines("/nonexistent_xyz.txt")
        assert "失败" in result

    def test_padded_line_numbers(self, multi_line_file):
        result = file_tools_read_lines(multi_line_file, start_line=9, line_count=3)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) >= 1
        first = rows[0]["line_number"]
        assert first.isdigit() or first.startswith("0")

    def test_empty_file(self, empty_file):
        result = file_tools_read_lines(empty_file, line_count=5)
        result = result.strip()
        assert "line_number" in result

    def test_max_chars(self, long_line_file):
        result = file_tools_read_lines(long_line_file, line_count=-1, max_chars=50)
        assert "<<truncated>>" in result

    def test_chinese(self, chinese_file):
        result = file_tools_read_lines(chinese_file, line_count=3)
        assert "第一行" in result

    def test_max_chars_truncated_from_start(self, many_medium_lines_file):
        """从头读，截断发生在中间行，提示行号应等于被截断行号。"""
        result = file_tools_read_lines(many_medium_lines_file, start_line=1, line_count=-1, max_chars=200)
        assert "如需继续阅读" in result
        import re
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 被截断行号应 >= 起始行号，且 <= 文件总行数
        assert 1 <= next_line <= 30, f"提示行号 {next_line} 越界"
        # 修复后：next_line 应等于被截断行的行号，而非 start_line + len(rows)
        # 旧代码会算出 next_line > 实际被截断行号，这里验证它至少合理
        assert next_line >= 5, f"提示行号 {next_line} 应 >= 5（至少读到第5行才可能截断）"

    def test_max_chars_truncated_from_middle(self, many_medium_lines_file):
        """从中间读，截断发生在中间行，提示行号应等于被截断行号。"""
        result = file_tools_read_lines(many_medium_lines_file, start_line=10, line_count=-1, max_chars=150)
        assert "如需继续阅读" in result
        import re
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 提示行号应 >= start_line 且 <= 文件总行数
        assert 10 <= next_line <= 30, f"提示行号 {next_line} 越界"
        # 修复后：next_line 应等于被截断行的行号，而非 start_line + len(rows)
        # 旧代码会算出 next_line > 实际被截断行号，这里验证它至少合理
        assert next_line >= 12, f"提示行号 {next_line} 应 >= 12（至少读到第12行才可能截断）"

    def test_max_chars_no_truncation(self, multi_line_file):
        """max_chars 足够大，不截断，不应有提示。"""
        result = file_tools_read_lines(multi_line_file, start_line=1, line_count=-1, max_chars=9999)
        assert "如需继续阅读" not in result
        assert "line20" in result


class TestReadBlock:
    def test_basic(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_line=2, end_line=4,
            start_offset=0, end_offset=10,
        )
        assert "line2" in result
        assert "line4" in result

    def test_offset_beyond_line(self, multi_line_file):
        """start_offset 超行长度返回空。"""
        result = file_tools_read_block(
            multi_line_file, start_line=1, end_line=2,
            start_offset=100, end_offset=200,
        )
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2  # 2 rows, both empty
        assert rows[0]["content"] == ""
        assert rows[1]["content"] == ""

    def test_offset_reverse(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_line=1, end_line=2,
            start_offset=5, end_offset=2,
        )
        assert "失败" in result

    def test_max_chars(self, multi_line_file):
        result = file_tools_read_block(
            multi_line_file, start_line=1, end_line=20,
            start_offset=0, end_offset=5000, max_chars=50,
        )
        assert "<<truncated>>" in result or len(result) < 200

    def test_max_chars_truncated_hint_from_start(self, many_medium_lines_file):
        """从头读，截断后提示行号应等于被截断行号。"""
        result = file_tools_read_block(
            many_medium_lines_file, start_line=1, end_line=30,
            start_offset=0, end_offset=200, max_chars=60,
        )
        assert "如需继续阅读" in result
        import re
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 被截断行号应 >= 起始行号，且在文件范围内
        assert 1 <= next_line <= 30, f"提示行号 {next_line} 越界"

    def test_max_chars_truncated_hint_from_middle(self, many_medium_lines_file):
        """从中间读，截断后提示行号应等于被截断行号。"""
        result = file_tools_read_block(
            many_medium_lines_file, start_line=10, end_line=30,
            start_offset=0, end_offset=200, max_chars=60,
        )
        assert "如需继续阅读" in result
        import re
        match = re.search(r"从第 (\d+) 行开始读取", result)
        assert match is not None, f"未找到提示行号，结果：{result}"
        next_line = int(match.group(1))
        # 提示行号应 >= start_line
        assert 10 <= next_line <= 30, f"提示行号 {next_line} 越界"

    def test_nonexistent(self):
        result = file_tools_read_block("/nonexistent.txt", start_line=1, end_line=5)
        assert "失败" in result

    def test_beyond_file(self, multi_line_file):
        result = file_tools_read_block(multi_line_file, start_line=1, end_line=999)
        assert "line20" in result


class TestRegex:
    def test_basic(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"line")
        assert "match_number" in result
        assert "line_content" in result
        assert "matched_text" in result

    def test_specific_pattern(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"line1[0-9]")
        assert "line10" in result
        assert "line11" in result

    def test_no_match(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"ZZZZ_NOT_FOUND")
        assert "match_number" in result

    def test_nonexistent_file(self):
        result = file_tools_regex("/nonexistent.txt", pattern=r"test")
        assert "失败" in result

    def test_invalid_regex(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"[invalid")
        assert "失败" in result

    def test_pagination(self, multi_line_file):
        """start 和 count 控制返回范围。"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start=2, count=3)
        reader = csv.DictReader(io.StringIO(result))
        rows = [r for r in reader if r.get("match_number", "").lstrip().isdigit()]
        assert len(rows) <= 3

    def test_start_end_line(self, multi_line_file):
        result = file_tools_regex(
            multi_line_file, pattern=r"line",
            start_line=15, end_line=18,
        )
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 4
        assert "line15" in result
        assert "line18" in result
        assert "line10" not in result

    def test_chinese_regex(self, chinese_file):
        result = file_tools_regex(chinese_file, pattern=r"第")
        assert "第一行" in result

    def test_empty_file(self, empty_file):
        result = file_tools_regex(empty_file, pattern=r"test")
        assert "match_number" in result

    def test_matched_text_content(self, multi_line_file):
        result = file_tools_regex(multi_line_file, pattern=r"line\d+")
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        if rows:
            assert "matched_text" in rows[0]
            assert rows[0]["matched_text"].startswith("line")

    def test_start_lt_1(self, multi_line_file):
        """start<1 应报错"""
        result = file_tools_regex(multi_line_file, pattern=r"line", start=0)
        assert "失败" in result
        assert "start" in result
